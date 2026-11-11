import json,tempfile,unittest,pathlib
import run_producer as R
import producer_test as T
from proof_test import write_closure
from producer_context import collect_context
from proof_context import context_digest
ID=dict(repo_id=1111,bot_id=4242,owner_id=777,bot_slug='stronsium',request_comment_id=1)
ENV={'GITHUB_RUN_ID':'10','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'c'*40}
class RP(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.addCleanup(self.d.cleanup);self.out='proof.json';self.cwd=__import__('os').getcwd();__import__('os').chdir(self.d.name);self.addCleanup(__import__('os').chdir,self.cwd)
  self.prog=T.program();self.pol=T.policy(self.prog);self.gh=T.ReadService()
  write_closure(self.d.name);ENV['GITHUB_WORKSPACE']=self.d.name
  self.digest=context_digest(collect_context(T.ReadService(),1,**ID))
 def go(self,digest=None,env=ENV):
  R.run(1,digest or self.digest,self.out,env,ID,self.pol,self.prog,self.gh)
 def test_writes_single_proof_json_record(self):
  self.go();rec=json.loads(pathlib.Path(self.out).read_text())
  self.assertEqual(rec['producer']['run_id'],10);self.assertEqual(rec['context_sha256'],self.digest)
  self.assertTrue(all(m=='GET' for m,p in self.gh.calls))
 def test_digest_mismatch_writes_nothing(self):
  with self.assertRaises(ValueError):self.go('0'*64)
  self.assertFalse(pathlib.Path(self.out).exists())
 def test_runner_identity_required(self):
  for env in ({},{'GITHUB_RUN_ID':'x','GITHUB_RUN_ATTEMPT':'1'},{'GITHUB_RUN_ID':'10'}):
   with self.subTest(env=env),self.assertRaises(ValueError):self.go(env=env)

 def test_strict_inputs(self):
  for pr,dg,out in ((0,self.digest,'proof.json'),(10**10,self.digest,'proof.json'),(True and 1,'A'*64,'proof.json'),(1,self.digest+'x','proof.json'),(1,self.digest,'../x'),(1,self.digest,'/tmp/x'),(1,'$(id)'*16,'proof.json')):
   with self.subTest(pr=pr,dg=dg[:8],out=out),self.assertRaises(ValueError):R.run(pr,dg,out,ENV,ID,self.pol,self.prog,self.gh)
 def test_main_fails_closed_without_identity_module(self):
  with self.assertRaises((ImportError,ValueError)):R.main(['x','1','0'*64,self.out],dict(ENV,GH_TOKEN='t'))
if __name__=='__main__':unittest.main()
