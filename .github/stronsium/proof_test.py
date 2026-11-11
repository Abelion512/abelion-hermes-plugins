"""Independent proof verifier fixtures. Offline source, never production proof."""
import base64
import copy
import hashlib
import io
import json
import pathlib
import stat
import unittest
import zipfile
from dataclasses import replace
from urllib.parse import unquote
from proof_closure import MANIFEST_PATH, closure_digest
from proof_evidence import ProducerPolicy, ProofVerifier, VerifiedProof, digest, receipt_matches

HEAD='a'*40; BASE='b'*40; WORKFLOW='c'*40; TEST_HASH='d'*64
# Synthetic closure: a manifest plus two members. Any verifier get() serving these
# bytes at any ref matches the CLOSURE pin; editing one member breaks it.
MEMBERS=('.github/workflows/proof.yml','.github/stronsium/run_producer_comment.py')
MANIFEST=json.dumps({'version':1,'members':list(MEMBERS)},sort_keys=True,separators=(',',':')).encode()
CLOSURE_FILES={MANIFEST_PATH:MANIFEST,'.github/workflows/proof.yml':b'synthetic workflow bytes',
 '.github/stronsium/run_producer_comment.py':b'synthetic producer bytes'}
CLOSURE=closure_digest(CLOSURE_FILES)

def write_closure(root,files=None):
 root=pathlib.Path(root)
 for path,raw in (files or CLOSURE_FILES).items():
  p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)

def closure_content(path):
 p=unquote(path.split('/contents/')[1].split('?')[0])
 return {'type':'file','encoding':'base64','content':base64.b64encode(CLOSURE_FILES[p]).decode()}

def serve(run,artifact,calls=None):
 def get(path):
  if calls is not None:calls.append(('GET',path))
  if '/contents/' in path:return closure_content(path)
  return copy.deepcopy(run if '/runs/' in path else artifact)
 return get
CONTEXT={'pr':1,'sha':HEAD,'base':BASE,
 'paths':[{'filename':'docs/note.md','status':'modified'}],
 'sources':{'docs/note.md':'note\n'},'diff':'synthetic diff',
 'comments_fingerprint':'e'*64,'finding_ids':['review:1']}


def fixture():
 log='one independently selected assertion passed\n'
 return {'version':1,'repository':'Abelion512/abelion-hermes-plugins',
 'producer':{'run_id':10,'attempt':1,'head_sha':WORKFLOW,'closure_sha256':CLOSURE,'test_definition_sha256':TEST_HASH},
 'context_sha256':digest(CONTEXT),'scope':{'classification':'P4_python_ast_equivalent',
 'ast_equivalent_only':True,'coverage_complete':True,'reasons':['Synthetic offline fixture, not production approval']},
 'tests':[{'id':'fixed-regression','executed':True,'exit_code':0,'assertions':1,'skipped':0,
 'definition_sha256':TEST_HASH,'log_sha256':hashlib.sha256(log.encode()).hexdigest()}],
 'logs':{'fixed-regression':log},
 'findings':[{'id':'review:1','head_sha':HEAD,'disposition':'verified_fixed',
 'test_id':'fixed-regression','source_refs':['docs/note.md:1']}]} 


def archive(record=None, name='proof.json', mode=None, extra=False, payload=None):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
  info=zipfile.ZipInfo(name)
  if mode is not None:info.external_attr=mode<<16
  z.writestr(info, payload if payload is not None else json.dumps(record or fixture()))
  if extra:z.writestr('extra.txt','no')
 return out.getvalue()


class ProofTest(unittest.TestCase):
 def setUp(self):
  self.policy=ProducerPolicy(7,'.github/workflows/proof.yml',CLOSURE,TEST_HASH,('fixed-regression',),(777,),'trusted-proof')
  self.run={'id':10,'run_attempt':1,'repository':{'full_name':'Abelion512/abelion-hermes-plugins'},
   'workflow_id':7,'actor':{'id':777},'triggering_actor':{'id':777},'head_branch':'trusted-proof','path':'.github/workflows/proof.yml','head_sha':WORKFLOW,
   'event':'workflow_dispatch','status':'completed','conclusion':'success'}
  self.artifact={'id':11,'expired':False,'workflow_run':{'id':10,'head_sha':WORKFLOW}}
  self.calls=[]
 def verify(self,record=None,raw=None,context=None):
  raw=raw if raw is not None else archive(record)
  self.artifact.setdefault('digest','sha256:'+hashlib.sha256(raw).hexdigest())
  return ProofVerifier(self.policy,serve(self.run,self.artifact,self.calls)).verify(raw,context or CONTEXT,run_id=10,attempt=1,artifact_id=11)
 def test_malformed_api_payloads_fail_named_closed(self):
  for payload in (None,[],True,'success'):
   with self.subTest(payload=payload):
    v=ProofVerifier(self.policy,lambda path:payload)
    with self.assertRaises(ValueError):v.verify(archive(),CONTEXT,run_id=10,attempt=1,artifact_id=11)
 def test_malformed_context_has_named_error(self):
  for field,value in [('sha',None),('paths',[{'filename':[],'status':'added'}]),('finding_ids',[{}])]:
   with self.subTest(field=field):
    c=copy.deepcopy(CONTEXT);c[field]=value
    with self.assertRaises(ValueError):self.verify(context=c)
 def test_actual_verifier_positive_receipt(self):
  r=self.verify();self.assertTrue(receipt_matches(r,CONTEXT))
  self.assertEqual(len(self.calls),2+1+len(MEMBERS))  # run + artifact + manifest + members
 def test_closure_content_pin_replaces_exact_commit_pin(self):
  # A run on ANY commit whose closure members match the pin verifies; no exact-sha staleness.
  rec=fixture();rec['producer']['head_sha']='0'*40
  self.run['head_sha']='0'*40;self.artifact['workflow_run']['head_sha']='0'*40
  self.assertTrue(receipt_matches(self.verify(rec),CONTEXT))
 def test_closure_member_change_fails_closed(self):
  for path,raw in [(m,b'changed') for m in MEMBERS]+[(MANIFEST_PATH,b'{"version":1,"members":[]}')]:
   with self.subTest(path=path):
    old=CLOSURE_FILES[path];CLOSURE_FILES[path]=raw
    try:
     with self.assertRaises(ValueError):self.verify()
    finally:CLOSURE_FILES[path]=old;self.artifact.pop('digest',None)
 def test_closure_member_removed_fails_closed(self):
  old=CLOSURE_FILES.pop(MEMBERS[0])
  try:
   with self.assertRaises(ValueError):self.verify()
  finally:CLOSURE_FILES[MEMBERS[0]]=old
 def test_receipt_not_dict_or_forged_object(self):
  self.assertFalse(receipt_matches({'verified':True},CONTEXT))
  self.assertFalse(receipt_matches(VerifiedProof(digest(CONTEXT),HEAD,BASE,(),10,1,object()),CONTEXT))
 def test_receipt_head_drift(self):
  r=self.verify();c=copy.deepcopy(CONTEXT);c['sha']='f'*40;self.assertFalse(receipt_matches(r,c))
 def test_producer_mutants(self):
  for field,value in [('workflow_id',8),('path','another.yml'),('head_sha',HEAD),('run_attempt',2),
    ('actor',{'id':999}),('triggering_actor',{'id':999}),('head_branch','candidate-branch'),('actor',None),('triggering_actor',{'id':True}),('run_attempt',True),('workflow_id',True),('repository',None),('event','pull_request'),('status','in_progress'),('conclusion','failure'),('repository',{'full_name':'attacker/repo'})]:
   with self.subTest(field=field):
    old=copy.deepcopy(self.run);self.run[field]=value
    with self.assertRaises(ValueError):self.verify()
    self.run=old
 def test_artifact_mutants(self):
  for field,value in [('id',True),('id',12),('workflow_run',None),('expired',True),('digest','sha256:'+'0'*64),('workflow_run',{'id':9,'head_sha':WORKFLOW})]:
   with self.subTest(field=field):
    old=copy.deepcopy(self.artifact);self.artifact[field]=value
    with self.assertRaises(ValueError):self.verify()
    self.artifact=old
 def test_scope_mutants(self):
  for field,value in [('classification','P3'),('coverage_complete',False),('ast_equivalent_only',1),('reasons',[])]:
   with self.subTest(field=field):
    r=fixture();r['scope'][field]=value
    with self.assertRaises(ValueError):self.verify(r)
    self.artifact.pop('digest',None)
 def test_test_execution_mutants(self):
  for field,value in [('executed',False),('exit_code',1),('exit_code',False),('skipped',1),('assertions',0),
   ('definition_sha256','0'*64),('log_sha256','0'*64),('id','candidate-chosen')]:
   with self.subTest(field=field):
    r=fixture();r['tests'][0][field]=value
    with self.assertRaises(ValueError):self.verify(r)
    self.artifact.pop('digest',None)
 def test_missing_duplicate_and_forged_fields(self):
  for field,value in [('tests',[]),('tests',fixture()['tests']*2),('findings',[]),('logs',{}),('version',True)]:
   with self.subTest(field=field):
    r=fixture();r[field]=value
    with self.assertRaises(ValueError):self.verify(r)
    self.artifact.pop('digest',None)
  r=fixture();r['verified']=True
  with self.assertRaises(ValueError):self.verify(r)
 def test_changed_context_every_binding(self):
  for field,value in [('sha','f'*40),('base','f'*40),('sources',{'docs/note.md':'partial'}),
   ('diff','partial'),('comments_fingerprint','new'),('finding_ids',[]),('pr',2)]:
   with self.subTest(field=field):
    c=copy.deepcopy(CONTEXT);c[field]=value
    with self.assertRaises(ValueError):self.verify(context=c)
 def test_incomplete_sources(self):
  c=copy.deepcopy(CONTEXT);c['sources']={}
  with self.assertRaises(ValueError):self.verify(context=c)
 def test_archive_safety(self):
  for kwargs in [{'name':'../proof.json'},{'mode':stat.S_IFLNK|0o777},{'extra':True},{'payload':'{}'},
    {'payload':'{"version":1,"version":1}'},{'payload':b'\xff'}]:
   with self.subTest(kwargs=kwargs):
    with self.assertRaises(ValueError):self.verify(raw=archive(**kwargs))
    self.artifact.pop('digest',None)
 def test_digest_checked_before_parsing(self):
  self.artifact['digest']='sha256:'+'0'*64
  with self.assertRaisesRegex(ValueError,'artifact_provenance_or_digest_mismatch'):self.verify(raw=b'not zip')
 def test_record_run_attempt_and_definition(self):
  for field,value in [('run_id',9),('attempt',2),('attempt',True),('head_sha',HEAD),('closure_sha256','0'*64),('test_definition_sha256','0'*64)]:
   with self.subTest(field=field):
    r=fixture();r['producer'][field]=value
    with self.assertRaises(ValueError):self.verify(r)
    self.artifact.pop('digest',None)
 def test_finding_proof_mutants(self):
  for field,value in [('id','review:2'),('head_sha',BASE),('test_id','fake'),('source_refs',[]),('disposition','resolved')]:
   with self.subTest(field=field):
    r=fixture();r['findings'][0][field]=value
    with self.assertRaises(ValueError):self.verify(r)
    self.artifact.pop('digest',None)

if __name__=='__main__':unittest.main(verbosity=2)
