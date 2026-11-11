"""Offline producer tests: issue_comment producer -> proof.json -> real ProofVerifier. No network, no subprocess."""
import base64, hashlib, io, os, pathlib, tempfile, unittest, zipfile
from unittest import mock
import producer_test as T
import producer_identity as I
import run_producer_comment as RC
import p4_semantic as S
from producer_context import collect_context
from proof_context import context_digest
from proof_evidence import ProofVerifier, REPO

SHA = 'a' * 40
FIX = dict(I.IDENTITY, repo_id=1111, bot_id=4242)  # ids used by the synthetic ReadService fixture
ENV = {'GITHUB_RUN_ID': '10', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_EVENT_NAME': 'pull_request_target', 'GITHUB_SHA': SHA}
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
HEAD_SRC = "import os\n\n# explain\ndef f(x):\n    return x + 1\n"
HDR = "diff --git a/plugins/a/m.py b/plugins/a/m.py\nindex 1..2 100644\n--- a/plugins/a/m.py\n+++ b/plugins/a/m.py\n"
GOOD = HDR + "@@ -1,4 +1,5 @@\n import os\n \n+# explain\n def f(x):\n     return x + 1\n"
BAD = HDR + "@@ -1,5 +1,5 @@\n import os\n \n # explain\n def f(x):\n-    return x + 0\n+    return x + 1\n"


class Svc(T.ReadService):
    def __init__(s, src=HEAD_SRC, diff=GOOD, status='modified'):
        super().__init__(); s.source = src; s.diff = diff; s.status = status

    def pages(s, path, **kw):
        if path.endswith('/files'):
            s.calls.append(('GET', path)); return [{'filename': 'plugins/a/m.py', 'status': s.status}]
        return super().pages(path, **kw)


class Flow(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.addCleanup(self.d.cleanup)
        cwd = os.getcwd(); os.chdir(self.d.name); self.addCleanup(os.chdir, cwd)
        self.pol, self.prog = I.load({'GITHUB_SHA': SHA, 'GITHUB_REPOSITORY': REPO, 'GITHUB_REF': 'refs/heads/main'})
        for n in ('socket.create_connection', 'subprocess.run', 'subprocess.Popen'):
            p = mock.patch(n, side_effect=AssertionError('network/process forbidden')); p.start(); self.addCleanup(p.stop)
        ENV['GITHUB_WORKSPACE'] = str(ROOT)

    def produce(self, svc, env=ENV):
        return RC.run(1, 0, 'proof.json', env, dict(FIX), self.pol, self.prog, svc, I.SEMANTIC)

    def zipped(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z: z.write('proof.json')
        return b.getvalue()

    def test_positive_digest_in_run_and_verifier_accepts(self):
        digest = self.produce(Svc())
        self.assertEqual(pathlib.Path('digest.txt').read_text().strip(), digest)
        ctx = collect_context(Svc(), 1, request_comment_id=0, **FIX)
        self.assertEqual(context_digest(ctx), digest)
        raw = self.zipped()
        run = {'id': 10, 'run_attempt': 1, 'repository': {'full_name': REPO}, 'workflow_id': 1, 'path': I.WORKFLOW_PATH, 'head_sha': SHA,
               'event': 'pull_request_target', 'status': 'completed', 'conclusion': 'success', 'actor': {'id': 206803862},
               'triggering_actor': {'id': 353707643}, 'head_branch': 'main'}
        art = {'id': 11, 'expired': False, 'workflow_run': {'id': 10, 'head_sha': SHA}, 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest()}
        def get(p):
            if '/contents/' in p:  # the real closure, served from this checkout
                rel = p.split('/contents/')[1].split('?')[0]
                return {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode((ROOT / rel).read_bytes()).decode()}
            return run if '/runs/' in p else art
        rc = ProofVerifier(self.pol, get).verify(raw, ctx, run_id=10, attempt=1, artifact_id=11)
        self.assertEqual(rc.test_ids, ('diff-covers-files',))
        self.assertEqual(self.pol.event, 'pull_request_target'); self.assertEqual(self.pol.allowed_actor_ids, (206803862, 353707643))

    def test_behavior_change_and_added_file_yield_no_proof(self):
        with self.assertRaisesRegex(ValueError, 'p4_sem_ast_changed'): self.produce(Svc(diff=BAD))
        self.assertFalse(pathlib.Path('proof.json').exists())
        with self.assertRaises(ValueError): self.produce(Svc(status='added'))

    def test_wrong_event_inputs_and_moving_head(self):
        for ev in ('workflow_dispatch', 'pull_request', 'issue_comment', None):
            env = dict(ENV); env.pop('GITHUB_EVENT_NAME') if ev is None else env.update(GITHUB_EVENT_NAME=ev)
            with self.assertRaisesRegex(ValueError, 'wrong_event'): self.produce(Svc(), env)
        for pr, c in ((0, 0), (1, -1), (True and 1, 'x')):
            with self.assertRaises(ValueError): RC.run(pr, c, 'proof.json', ENV, dict(FIX), self.pol, self.prog, Svc(), I.SEMANTIC)
        s = Svc(); s.mutate_head = True
        with self.assertRaises(ValueError): self.produce(s)

    def test_issue_comment_variant_needs_real_comment_id(self):
        pol, prog = I.load({'GITHUB_SHA': SHA, 'GITHUB_REPOSITORY': REPO, 'GITHUB_REF': 'refs/heads/main'}, event='issue_comment')
        with self.assertRaisesRegex(ValueError, 'invalid_comment'):
            RC.run(1, 0, 'proof.json', dict(ENV, GITHUB_EVENT_NAME='issue_comment'), dict(FIX), pol, prog, Svc(), I.SEMANTIC)

    def test_identity_refuses_off_default_branch(self):
        env = {'GITHUB_SHA': SHA, 'GITHUB_REPOSITORY': REPO, 'GITHUB_REF': 'refs/heads/main'}
        for bad in (dict(env, GITHUB_REF='refs/heads/x'), dict(env, GITHUB_REPOSITORY='x/y'), dict(env, GITHUB_SHA='zz'), {}):
            with self.assertRaises(ValueError): I.load(bad)

    def test_proof_binds_run_commit_and_closure_digest(self):
        self.produce(Svc())
        import json
        prod = json.loads(pathlib.Path('proof.json').read_text())['producer']
        self.assertEqual(prod['head_sha'], SHA)
        self.assertEqual(prod['closure_sha256'], self.pol.closure_sha256)
        from proof_closure import local_closure_digest
        self.assertEqual(prod['closure_sha256'], local_closure_digest(str(ROOT)))


if __name__ == '__main__':
    unittest.main()
