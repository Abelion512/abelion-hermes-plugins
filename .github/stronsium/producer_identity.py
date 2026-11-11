"""Trusted producer identity for the default-branch proof workflow (pull_request_target: automatic, no human trigger).
Everything is derived from the workflow's own pinned commit (GITHUB_SHA on the default branch) and fixed literals.
There is no input from the PR, the comment text or the model. The Hermes worker holds its OWN pinned policy (workflow_id,
expected closure digest, expected test-definition digest); a proof is accepted there only when those equal this run's record, so this
module cannot self-authorise: a copy of it with different closure members yields a different digest and is rejected by the worker.
The closure digest pins CONTENT (closure_manifest.json members), not the exact commit: unrelated default-branch merges keep
the worker pin valid. workflow_id is not known inside a run and the producer never uses it (placeholder 1; the verifier
checks the real id)."""
import hashlib, os, pathlib, re
import p4_semantic
from proof_closure import local_closure_digest
from proof_evidence import ProducerPolicy
from proof_producer import FrozenProgram

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IDENTITY = {'repo_id': 1291653534, 'bot_id': 353707643, 'owner_id': 206803862, 'bot_slug': 'stronsium'}
WORKFLOW_PATH = '.github/workflows/stronsium-proof.yml'
CHECK_FILE = 'p4_checks_program.py'
TEST_IDS = ('diff-covers-files',)
SEMANTIC = p4_semantic.classify_semantic


def program():
    d = hashlib.sha256((HERE / CHECK_FILE).read_bytes()).hexdigest()
    return FrozenProgram(HERE, ((CHECK_FILE, d),), (CHECK_FILE, 'classify_unused'),
                         (('diff-covers-files', CHECK_FILE, 'check_diff_covers_exactly_the_changed_files'),))


def load(env, event='pull_request_target'):
    """Return (POLICY, PROGRAM) or raise. Refuses anything but the default branch of the exact repository."""
    sha = env.get('GITHUB_SHA', '')
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError('producer_sha_missing')
    if env.get('GITHUB_REPOSITORY') != 'Abelion512/abelion-hermes-plugins' or env.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('producer_not_on_default_branch')
    prog = program()
    closure = local_closure_digest(str(ROOT))
    pol = ProducerPolicy(1, WORKFLOW_PATH, closure, prog.definition_digest(), TEST_IDS, (IDENTITY['owner_id'], IDENTITY['bot_id']), 'main', event)
    return pol, prog
