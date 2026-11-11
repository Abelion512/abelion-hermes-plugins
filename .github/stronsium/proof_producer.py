"""Execute application-selected frozen checks over data and emit bounded proof.

No production classifier/test policy is shipped. No workflow, network client,
subprocess, candidate import or candidate checkout is created here. This runner
is not a sandbox for hostile Python; reviewed check code is trusted application.
"""
import copy
from dataclasses import dataclass
import hashlib
import io
import json
import pathlib
import stat
import zipfile
from proof_context import canonical_bytes,normalize_context,context_digest
from proof_evidence import ProducerPolicy,ProofVerifier,REPO,MAX_BYTES,SHA,HASH

@dataclass(frozen=True)
class FrozenProgram:
    root: pathlib.Path
    files: tuple
    # Names only. Never accept functions, module objects or caller globals.
    classifier: tuple
    checks: tuple

    def _verified(self):
        import ast
        root=pathlib.Path(self.root)
        if root.is_symlink() or not root.is_dir():raise ValueError('untrusted_definition_root')
        root=root.resolve(strict=True)
        if type(self.files) is not tuple or not self.files:raise ValueError('test_definition_missing')
        blobs={};manifest=[]
        for entry in self.files:
            if type(entry) is not tuple or len(entry)!=2:raise ValueError('definition_manifest_schema')
            name,expected=entry
            if (type(name) is not str or not name or name.startswith('/') or not name.endswith('.py')
                    or any(p in ('','.','..') for p in name.split('/')) or '\\' in name or name in blobs):
                raise ValueError('definition_manifest_path')
            path=root/name
            if any(p.is_symlink() for p in [path,*path.parents] if p!=root.parent):raise ValueError('definition_symlink')
            if not path.is_file() or not path.resolve().is_relative_to(root):raise ValueError('definition_file_missing')
            raw=path.read_bytes()
            if len(raw)>1000000:raise ValueError('definition_file_limit')
            got=hashlib.sha256(raw).hexdigest()
            if type(expected) is not str or got!=expected:raise ValueError('test_definition_changed')
            # Deliberately small trusted-program format: literal constants and
            # top-level plain functions, no imports, decorators or eager code.
            tree=ast.parse(raw,filename=str(path))
            if any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(tree)):
                raise ValueError('definition_imports_not_supported')
            for node in tree.body:
                if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):continue
                if isinstance(node,ast.Assign):
                    if any(not isinstance(t,ast.Name) or t.id.startswith('__') for t in node.targets):raise ValueError('definition_top_level_code')
                    try:ast.literal_eval(node.value)
                    except (ValueError,TypeError):raise ValueError('definition_top_level_code')
                elif isinstance(node,ast.FunctionDef):
                    args=node.args
                    if (node.decorator_list or args.defaults or any(v is not None for v in args.kw_defaults)
                            or node.returns or any(arg.annotation for arg in [*args.posonlyargs,*args.args,*args.kwonlyargs])
                            or args.vararg or args.kwarg or node.name.startswith('__')):
                        raise ValueError('definition_function_format')
                else:raise ValueError('definition_top_level_code')
            blobs[name]=(raw,tree);manifest.append([name,got])
        def selected(spec):
            if (type(spec) is not tuple or len(spec)!=2 or any(type(v) is not str for v in spec)
                    or spec[0] not in blobs or not spec[1].isidentifier() or spec[1].startswith('__')):
                raise ValueError('trusted_program_missing')
            matches=[n for n in blobs[spec[0]][1].body if isinstance(n,ast.FunctionDef) and n.name==spec[1]]
            if len(matches)!=1:raise ValueError('selected_check_missing')
            return list(spec)
        classifier=selected(self.classifier)
        if type(self.checks) is not tuple or not self.checks:raise ValueError('trusted_program_missing')
        checks=[];ids=set()
        for item in self.checks:
            if type(item) is not tuple or len(item)!=3 or type(item[0]) is not str or not item[0] or item[0] in ids:
                raise ValueError('check_definition_schema')
            ids.add(item[0]);checks.append([item[0],*selected(item[1:])])
        definition={'files':sorted(manifest),'classifier':classifier,'checks':checks}
        digest=hashlib.sha256(json.dumps(definition,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        return root,blobs,digest

    def definition_digest(self):
        return self._verified()[2]

    def load(self):
        # Execute ONLY hash-verified trusted program bytes in fresh namespaces.
        # No candidate bytes, loaded modules, imported globals or dispatch code.
        # Restricted builtins reduce mistakes; this is NOT a hostile-code sandbox.
        root,blobs,digest=self._verified()
        import builtins
        permitted=('len','str','ValueError','sorted','all','any','tuple','list','dict','set','range','enumerate','zip','type','int','bool','isinstance','Exception','min','max','sum')
        modules={}
        for name,(raw,tree) in blobs.items():
            namespace={'__builtins__':{key:getattr(builtins,key) for key in permitted},'__name__':'trusted_checks'}
            exec(compile(tree,str(root/name),'exec',dont_inherit=True,optimize=0),namespace,namespace)
            modules[name]=namespace
        classifier=modules[self.classifier[0]][self.classifier[1]]
        checks=tuple((identifier,modules[file][function]) for identifier,file,function in self.checks)
        return digest,classifier,checks

class Assertions:
    """Counts only assertions the selected check actually invokes."""
    def __init__(self):self.count=0;self.lines=[]
    def require(self,condition,message):
        if type(message) is not str or not 0<len(message)<=1000:raise ValueError('check_message_invalid')
        self.count+=1
        self.lines.append(('PASS ' if condition is True else 'FAIL ')+message)
        if condition is not True:raise ValueError('trusted_check_failed')

class ProofProducer:
    def __init__(self,policy,program,semantic=None):
        if type(policy) is not ProducerPolicy or type(program) is not FrozenProgram:
            raise ValueError('trusted_producer_configuration_missing')
        if semantic is not None and not callable(semantic):raise ValueError('trusted_producer_configuration_missing')
        self.policy=policy;self.program=program
        # Optional trusted-application semantic lane (e.g. p4_semantic.classify_semantic). It runs from the pinned
        # default-branch commit and REPLACES the frozen classifier result; a ValueError from it means no proof.
        self.semantic=semantic

    def produce(self,context,*,run_id,attempt,head_sha,closure_sha256):
        """Return proof ZIP bytes only after actual selected checks succeed.

        Context must come from producer_context.collect_context with the
        independent authenticated reader, not a PR-provided JSON document.
        run_id/attempt/head_sha must come from authenticated runner environment
        wiring, not workflow-dispatch payload fields; closure_sha256 must be the
        producer's own local computation over the pinned checkout, and it has to
        match the policy pin. No environment is read implicitly.
        """
        if any(type(n) is not int or n<=0 for n in (run_id,attempt)):raise ValueError('invalid_producer_run')
        if type(head_sha) is not str or not SHA.fullmatch(head_sha):raise ValueError('invalid_producer_head_sha')
        if type(closure_sha256) is not str or not HASH.fullmatch(closure_sha256):raise ValueError('invalid_producer_closure')
        if closure_sha256!=self.policy.closure_sha256:raise ValueError('producer_closure_not_selected')
        c=normalize_context(context);before=canonical_bytes(c)
        definition,classifier,selected_checks=self.program.load()
        if definition!=self.policy.test_definition_sha256:raise ValueError('producer_definition_not_selected')
        if tuple(i for i,f in selected_checks)!=self.policy.required_test_ids:raise ValueError('producer_test_ids_not_selected')
        # Candidate content remains strings/maps. Never eval, import, run, or
        # source a candidate file. Application-selected check code is trusted.
        scope=(self.semantic or classifier)(copy.deepcopy(c))
        if type(scope) is not dict or set(scope)!={'scope','findings'}:raise ValueError('classifier_result_schema')
        tests=[];logs={}
        for identifier,check in selected_checks:
            assertions=Assertions()
            check(copy.deepcopy(c),assertions)
            if assertions.count<=0:raise ValueError('test_no_assertions')
            log='\n'.join(assertions.lines)+'\n'
            logs[identifier]=log
            tests.append({'id':identifier,'executed':True,'exit_code':0,'assertions':assertions.count,
                'skipped':0,'definition_sha256':definition,'log_sha256':hashlib.sha256(log.encode()).hexdigest()})
        if self.program.definition_digest()!=definition:raise ValueError('test_definition_changed_during_run')
        if canonical_bytes(c)!=before:raise ValueError('producer_context_changed')
        record={'version':1,'repository':REPO,'producer':{'run_id':run_id,'attempt':attempt,
            'head_sha':head_sha,'closure_sha256':closure_sha256,'test_definition_sha256':definition},
            'context_sha256':context_digest(c),'scope':scope['scope'],'findings':scope['findings'],
            'tests':tests,'logs':logs}
        # Same strict record validation, without inventing success metadata.
        ProofVerifier(self.policy,lambda path:None)._verify_record(record,c,run_id,attempt,head_sha)
        raw=json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8','strict')
        if len(raw)>MAX_BYTES:raise ValueError('produced_proof_limit')
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
            info=zipfile.ZipInfo('proof.json',date_time=(1980,1,1,0,0,0))
            info.external_attr=(stat.S_IFREG|0o600)<<16
            z.writestr(info,raw)
        archive=output.getvalue()
        if len(archive)>MAX_BYTES:raise ValueError('produced_archive_limit')
        return archive

def collect_and_produce(producer,gh,pr_number,*,collector_identity,expected_context_digest,run_id,attempt,head_sha,closure_sha256):
    """Authenticated-source entry point. Reject stale consumer/producer context.

    No dispatch is performed. Caller identity/grants and the authenticated read
    adapter must be reviewed application wiring. Never obtain them from PR text.
    """
    from producer_context import collect_context
    if type(producer) is not ProofProducer or type(collector_identity) is not dict:
        raise ValueError('producer_source_wiring_missing')
    if type(expected_context_digest) is not str or len(expected_context_digest)!=64:
        raise ValueError('consumer_context_digest_missing')
    context=collect_context(gh,pr_number,**collector_identity)
    if context_digest(context)!=expected_context_digest:raise ValueError('consumer_producer_context_mismatch')
    archive=producer.produce(context,run_id=run_id,attempt=attempt,head_sha=head_sha,closure_sha256=closure_sha256)
    latest=collect_context(gh,pr_number,**collector_identity)
    if context_digest(latest)!=expected_context_digest:raise ValueError('producer_snapshot_changed_during_checks')
    return archive
