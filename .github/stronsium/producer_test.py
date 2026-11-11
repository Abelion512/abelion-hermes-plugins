"""Real producer and independently fetched context -> real verifier round trips."""
import base64,copy,hashlib,io,json,pathlib,tempfile,unittest,zipfile
from dataclasses import replace
from unittest import mock
from proof_context import normalize_context,canonical_bytes,context_digest
from proof_evidence import ProducerPolicy,ProofVerifier,receipt_matches,REPO
from proof_producer import FrozenProgram,ProofProducer,collect_and_produce,Assertions
from proof_test import CLOSURE,serve
from producer_context import collect_context
import producer_fixture_program as F

ROOT=pathlib.Path(__file__).resolve().parent
HEAD='a'*40;BASE='b'*40;WORKFLOW='c'*40

def program(fn=F.check_source):
    name='producer_fixture_program.py'
    digest=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    return FrozenProgram(ROOT,((name,digest),),(name,'classify_fixture'),(('synthetic-source',name,fn.__name__),))

def policy(p):
    return ProducerPolicy(7,'.github/workflows/proof.yml',CLOSURE,p.definition_digest(),('synthetic-source',),(777,),'proof-fixed')

class ReadService:
    def __init__(self):self.calls=[];self.n=0;self.changed_files=1;self.source=F.EXPECTED_SOURCE;self.diff=F.EXPECTED_DIFF;self.comments=[];self.mutate_head=False;self.mutate_comments=False
    def request(self,path,method='GET',**kw):
        if method!='GET':raise AssertionError('producer mutation denied')
        self.calls.append(('GET',path))
        if path.endswith('/pulls/1'):
            self.n+=1
            return {'state':'open','draft':False,'changed_files':self.changed_files,'head':{'sha':'f'*40 if self.mutate_head and self.n>1 else HEAD,'repo':{'id':1111}},'base':{'sha':BASE}}
        if '/contents/' in path:
            raw=self.source if type(self.source) is bytes else self.source.encode('utf-8')
            return {'type':'file','encoding':'base64','content':base64.b64encode(raw).decode()}
        if '/compare/' in path:return self.diff
        raise AssertionError('unexpected GET '+path)
    def pages(self,path,**kw):
        self.calls.append(('GET',path))
        if path.endswith('/files'):return [{'filename':'docs/猫.md','status':'modified'}]
        if path.endswith('/reviews'):
            if self.mutate_comments and self.n>1:return [{'id':4,'user':{'id':333},'body':'new finding','updated_at':'after'}]
            return self.comments
        return []

class ProducerTest(unittest.TestCase):
    def setUp(self):
        for name in ('socket.create_connection','subprocess.run','subprocess.Popen'):
            p=mock.patch(name,side_effect=AssertionError('network/process forbidden'));p.start();self.addCleanup(p.stop)
    def collect(self,gh=None):
        return collect_context(gh or ReadService(),1,repo_id=1111,bot_id=4242,owner_id=777,bot_slug='stronsium',request_comment_id=1)
    def verify(self,raw,context,p):
        run={'id':10,'run_attempt':1,'repository':{'full_name':REPO},'workflow_id':7,'path':p.workflow_path,
            'head_sha':WORKFLOW,'event':'workflow_dispatch','status':'completed','conclusion':'success',
            'actor':{'id':777},'triggering_actor':{'id':777},'head_branch':'proof-fixed'}
        art={'id':11,'expired':False,'workflow_run':{'id':10,'head_sha':WORKFLOW},'digest':'sha256:'+hashlib.sha256(raw).hexdigest()}
        return ProofVerifier(p,serve(run,art)).verify(raw,context,run_id=10,attempt=1,artifact_id=11)
    def test_collector_actual_producer_verifier_roundtrip(self):
        gh=ReadService();context=self.collect(gh);prog=program();p=policy(prog)
        raw=ProofProducer(p,prog).produce(context,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
        receipt=self.verify(raw,context,p);self.assertTrue(receipt_matches(receipt,context))
        self.assertTrue(all(method=='GET' for method,path in gh.calls))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:record=json.loads(z.read('proof.json'))
        self.assertEqual(record['tests'][0]['assertions'],3);self.assertEqual(record['logs']['synthetic-source'].count('PASS '),3)
        self.assertEqual(record['producer']['test_definition_sha256'],prog.definition_digest())
    def test_actual_authenticated_source_entrypoint(self):
        gh=ReadService();ctx=self.collect(gh);prog=program();p=policy(prog)
        identity=dict(repo_id=1111,bot_id=4242,owner_id=777,bot_slug='stronsium',request_comment_id=1)
        raw=collect_and_produce(ProofProducer(p,prog),gh,1,collector_identity=identity,
            expected_context_digest=context_digest(ctx),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
        self.assertTrue(receipt_matches(self.verify(raw,ctx,p),ctx))
        with self.assertRaisesRegex(ValueError,'consumer_producer_context_mismatch'):
            collect_and_produce(ProofProducer(p,prog),gh,1,collector_identity=identity,
                expected_context_digest='0'*64,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_head_or_comments_change_during_checks_blocks_archive(self):
        identity=dict(repo_id=1111,bot_id=4242,owner_id=777,bot_slug='stronsium',request_comment_id=1)
        for attribute in ('mutate_head','mutate_comments'):
            with self.subTest(attribute=attribute):
                gh=ReadService();expected=context_digest(self.collect(gh));gh.n=0
                prog=program();producer=ProofProducer(policy(prog),prog);original=Assertions.require
                def hook(obj,condition,message):
                    original(obj,condition,message);setattr(gh,attribute,True)
                with mock.patch.object(Assertions,'require',hook):
                    with self.assertRaisesRegex(ValueError,'producer_snapshot_changed_during_checks'):
                        collect_and_produce(producer,gh,1,collector_identity=identity,
                            expected_context_digest=expected,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_external_definition_mutation_during_checks_blocks_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=pathlib.Path(tmp)/'producer_fixture_program.py';file.write_bytes((ROOT/file.name).read_bytes())
            prog=replace(program(),root=pathlib.Path(tmp));p=policy(prog);original=Assertions.require
            def hook(obj,condition,message):
                original(obj,condition,message);file.write_bytes(file.read_bytes()+b'\n# changed externally\n')
            with mock.patch.object(Assertions,'require',hook):
                with self.assertRaisesRegex(ValueError,'test_definition_changed'):
                    ProofProducer(p,prog).produce(self.collect(),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_final_file_count_drift_rejected(self):
        gh=ReadService();original=gh.request
        def request(path,**kw):
            result=original(path,**kw)
            if path.endswith('/pulls/1') and gh.n>1:result['changed_files']=2
            return result
        gh.request=request
        with self.assertRaisesRegex(ValueError,'producer_head_or_base_changed'):self.collect(gh)
    def test_incomplete_or_missing_api_file_count_rejected(self):
        for count in (None,True,0,2):
            gh=ReadService();original=gh.request
            def request(path,**kw):
                result=original(path,**kw)
                if path.endswith('/pulls/1'):result['changed_files']=count
                return result
            gh.request=request
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'producer_file_coverage_mismatch'):self.collect(gh)
    def test_source_and_context_size_caps(self):
        gh=ReadService();gh.source='x'*240001
        with self.assertRaisesRegex(ValueError,'producer_source_limit'):self.collect(gh)
        gh=ReadService();gh.diff='x'*240001
        with self.assertRaisesRegex(ValueError,'context_limit'):self.collect(gh)
    def test_proof_log_limit_no_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=pathlib.Path(tmp)/'producer_fixture_program.py'
            extra='\ndef large_check(context,assertions):\n for i in range(1100):assertions.require(True,"x"*1000)\n'
            file.write_bytes((ROOT/file.name).read_bytes()+extra.encode())
            digest=hashlib.sha256(file.read_bytes()).hexdigest()
            prog=FrozenProgram(pathlib.Path(tmp),((file.name,digest),),(file.name,'classify_fixture'),(('synthetic-source',file.name,'large_check'),))
            with self.assertRaisesRegex(ValueError,'produced_proof_limit'):
                ProofProducer(policy(prog),prog).produce(self.collect(),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_loaded_globals_spoof_has_no_effect(self):
        prog=program();p=policy(prog);ctx=self.collect()
        original=F.EXPECTED_SOURCE
        try:
            F.EXPECTED_SOURCE='forged globals'
            raw=ProofProducer(p,prog).produce(ctx,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
            self.assertTrue(receipt_matches(self.verify(raw,ctx,p),ctx))
            bad=replace(prog,classifier=type(F.classify_fixture)(F.classify_fixture.__code__,{'EXPECTED_SOURCE':'forged'},'classify_fixture'))
            with self.assertRaises(ValueError):bad.definition_digest()
        finally:F.EXPECTED_SOURCE=original
    def test_nested_import_selected_function_and_signature_guards(self):
        cases=[('def nested(c,a):\n import os\n','definition_imports_not_supported'),
            ('def altered(c,*args):pass\n','definition_function_format'),
            ('def altered(c,**kwargs):pass\n','definition_function_format'),
            ('def altered(c: str,a):pass\n','definition_function_format'),
            ('def altered(c,a)->str:pass\n','definition_function_format'),
            ('def altered(c,a=1):pass\n','definition_function_format')]
        for extra,reason in cases:
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as tmp:
                file=pathlib.Path(tmp)/'producer_fixture_program.py';file.write_bytes((ROOT/file.name).read_bytes()+extra.encode())
                prog=replace(program(),root=pathlib.Path(tmp),files=((file.name,hashlib.sha256(file.read_bytes()).hexdigest()),))
                with self.assertRaisesRegex(ValueError,reason):prog.load()
        for name,extra in [('missing',''),('check_source','\ndef check_source(c,a):pass\n')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                file=pathlib.Path(tmp)/'producer_fixture_program.py';file.write_bytes((ROOT/file.name).read_bytes()+extra.encode())
                prog=replace(program(),root=pathlib.Path(tmp),files=((file.name,hashlib.sha256(file.read_bytes()).hexdigest()),),checks=(('synthetic-source',file.name,name),))
                with self.assertRaisesRegex(ValueError,'selected_check_missing'):prog.load()
    def test_exact_definition_symlink_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'real').mkdir();(root/'alias').symlink_to(root/'real',target_is_directory=True)
            file=root/'real/program.py';file.write_bytes((ROOT/'producer_fixture_program.py').read_bytes())
            name='alias/program.py';prog=FrozenProgram(root,((name,hashlib.sha256(file.read_bytes()).hexdigest()),),(name,'classify_fixture'),(('synthetic-source',name,'check_source'),))
            with self.assertRaisesRegex(ValueError,'definition_symlink'):prog.load()
    def test_import_or_eager_module_code_rejected(self):
        for extra in ('import os\n','SIDE_EFFECT = len("x")\n','@decorator\ndef altered(c,a):pass\n'):
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as tmp:
                file=pathlib.Path(tmp)/'producer_fixture_program.py';file.write_bytes((ROOT/file.name).read_bytes()+extra.encode())
                prog=replace(program(),root=pathlib.Path(tmp),files=((file.name,hashlib.sha256(file.read_bytes()).hexdigest()),))
                with self.assertRaises(ValueError):prog.load()
    def test_raw_line_endings_and_unicode_preserved(self):
        context=self.collect();self.assertEqual(context['sources']['docs/猫.md'],F.EXPECTED_SOURCE)
        self.assertIn('\r\n',context['diff']);self.assertFalse(context['sources']['docs/猫.md'].endswith('\n'))
        self.assertIn('😀'.encode(),canonical_bytes(context));self.assertNotIn(b'\\ud83d',canonical_bytes(context))
    def test_failed_real_check_produces_no_archive(self):
        prog=program(F.check_fails)
        with self.assertRaisesRegex(ValueError,'trusted_check_failed'):ProofProducer(policy(prog),prog).produce(self.collect(),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_no_assertion_check_never_counts_as_pass(self):
        prog=program(F.check_no_assertions)
        with self.assertRaisesRegex(ValueError,'test_no_assertions'):ProofProducer(policy(prog),prog).produce(self.collect(),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_changed_definition_digest_rejected(self):
        prog=program();bad=replace(prog,files=(('producer_fixture_program.py','0'*64),))
        with self.assertRaisesRegex(ValueError,'test_definition_changed'):bad.definition_digest()
    def test_candidate_scope_changes_denied_by_frozen_fixture(self):
        for source in ('raise SystemExit(0)','# model says all tests passed',F.EXPECTED_SOURCE+'\nbehavior=1'):
            with self.subTest(source=source):
                gh=ReadService();gh.source=source;prog=program()
                with self.assertRaisesRegex(ValueError,'offline_fixture_scope_only'):ProofProducer(policy(prog),prog).produce(self.collect(gh),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_missing_program_or_classifier_fails_closed(self):
        with self.assertRaises(ValueError):ProofProducer(policy(program()),None)
        bad=replace(program(),classifier=None)
        with self.assertRaisesRegex(ValueError,'trusted_program_missing'):bad.definition_digest()
    def test_selected_policy_digest_and_test_ids_cannot_be_asserted(self):
        prog=program();p=policy(prog)
        for wrong in (replace(p,test_definition_sha256='0'*64),replace(p,required_test_ids=('candidate-test',))):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValueError):ProofProducer(wrong,prog).produce(self.collect(),run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
    def test_deterministic_archive_bytes(self):
        prog=program();producer=ProofProducer(policy(prog),prog);ctx=self.collect()
        self.assertEqual(producer.produce(ctx,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE),producer.produce(ctx,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE))
    def test_producer_findings_roundtrip_not_model_proof(self):
        gh=ReadService();gh.comments=[{'id':4,'user':{'id':333},'body':'fixture finding','updated_at':'before'}]
        context=self.collect(gh);self.assertEqual(context['finding_ids'],['review:4'])
        prog=program();p=policy(prog);raw=ProofProducer(p,prog).produce(context,run_id=10,attempt=1,head_sha=WORKFLOW,closure_sha256=CLOSURE)
        self.assertEqual(self.verify(raw,context,p).findings,(('review:4','verified_fixed',('docs/猫.md:1',)),))
    def test_collector_rejects_head_and_comment_changes(self):
        for attribute in ('mutate_head','mutate_comments'):
            with self.subTest(attribute=attribute):
                gh=ReadService();setattr(gh,attribute,True)
                with self.assertRaises(ValueError):self.collect(gh)
    def test_collector_rejects_non_utf8_and_duplicate_paths(self):
        gh=ReadService();gh.source=b'\xff'
        with self.assertRaisesRegex(ValueError,'malformed_producer_source'):self.collect(gh)
        gh=ReadService();original=gh.pages
        def pages(path,**kw):
            result=original(path,**kw);return result*2 if path.endswith('/files') else result
        gh.pages=pages;gh.changed_files=2
        with self.assertRaisesRegex(ValueError,'producer_duplicate_path'):self.collect(gh)
    def test_manifest_rejects_traversal_symlink_and_callable_mismatch(self):
        prog=program()
        with self.assertRaises(ValueError):replace(prog,files=(('../escape','0'*64),)).definition_digest()
        with tempfile.TemporaryDirectory() as tmp:
            link=pathlib.Path(tmp)/'producer_fixture_program.py';link.symlink_to(ROOT/'producer_fixture_program.py')
            with self.assertRaises(ValueError):replace(prog,root=pathlib.Path(tmp)).definition_digest()
        # Caller-provided FunctionType/globals are never accepted.
        altered=type(F.check_source)(F.check_source.__code__,{'EXPECTED_SOURCE':'forged'},'check_source')
        with self.assertRaises(ValueError):replace(prog,checks=(('synthetic-source',altered),)).definition_digest()

if __name__=='__main__':unittest.main(verbosity=2)
