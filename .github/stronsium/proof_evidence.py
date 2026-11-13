"""Exact-head proof verification. Candidate data never supplies trust policy.

No network writes or candidate execution. A separately reviewed, fixed producer
is required. This module does NOT create that producer or authenticate arbitrary
local JSON. The GitHub reader is an injected read-only source of truth.
"""
import hashlib
import json
import re
import io
import zipfile
import stat
from dataclasses import dataclass

SHA = re.compile(r'[a-f0-9]{40}')
HASH = re.compile(r'[a-f0-9]{64}')
REPO = 'Abelion512/abelion-hermes-plugins'
MAX_BYTES = 1_000_000
_SEAL = object()


from proof_context import context_digest as digest,normalize_context
from proof_closure import remote_closure_digest


@dataclass(frozen=True)
class ProducerPolicy:
    """Application-selected trust anchors, NEVER loaded from PR/model/config.

    Selecting these anchors requires a real review of producer code and tests.
    Its pinned workflow must handle candidate content only as data, never run it.
    No production anchors are shipped by this module.
    closure_sha256 pins the CONTENT of the workflow plus its whole dependency
    closure (proof_closure.closure_manifest.json members), not an exact main
    commit: unrelated default-branch merges do not stale the pin, and any change
    to a closure member fails closed.
    """
    workflow_id: int
    workflow_path: str
    closure_sha256: str
    test_definition_sha256: str
    required_test_ids: tuple
    allowed_actor_ids: tuple
    head_branch: str
    event: str = 'workflow_dispatch'   # or 'issue_comment' / 'pull_request_target' (producers that run the default-branch file)

    def __post_init__(self):
        if (type(self.workflow_id) is not int or self.workflow_id <= 0
                or type(self.workflow_path) is not str
                or type(self.closure_sha256) is not str or type(self.test_definition_sha256) is not str
                or not self.workflow_path.startswith('.github/workflows/')
                or not HASH.fullmatch(self.closure_sha256)
                or not HASH.fullmatch(self.test_definition_sha256)
                or type(self.required_test_ids) is not tuple
                or not self.required_test_ids
                or any(type(t) is not str or not t for t in self.required_test_ids)
                or len(set(self.required_test_ids)) != len(self.required_test_ids)
                or type(self.allowed_actor_ids) is not tuple or not self.allowed_actor_ids
                or any(type(i) is not int or i<=0 for i in self.allowed_actor_ids)
                or type(self.head_branch) is not str or not self.head_branch.strip()
                or self.event not in ('workflow_dispatch', 'issue_comment', 'pull_request_target')):
            raise ValueError('invalid_producer_policy')


@dataclass(frozen=True)
class VerifiedProof:
    context_digest: str
    head_sha: str
    base_sha: str
    test_ids: tuple
    run_id: int
    run_attempt: int
    _seal: object
    findings: tuple = ()


def receipt_matches(receipt, context):
    try:
        return (type(context) is dict and type(receipt) is VerifiedProof and receipt._seal is _SEAL
            and receipt.context_digest == digest(context)
            and receipt.head_sha == context.get('sha')
            and receipt.base_sha == context.get('base'))

    except (ValueError,TypeError,UnicodeError):
        return False


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate_proof_key')
        out[key] = value
    return out


class ProofVerifier:
    """Verify bytes plus independent GitHub metadata against fixed policy.

    `get` must be the owner's normal authenticated READ transport, not a client
    offered by PR data. The caller supplies raw proof artifact bytes fetched from
    the actual run artifact. This reader revalidates run/artifact provenance and
    exact content digest, not a filename or a self-claimed `verified` flag.

    Raw archive digest is verified before opening. Only one bounded regular
    proof.json is supported. No extraction, code execution or trust-on-first-use.
    A valid receipt still grants no permission to publish, approve or merge.
    """
    def __init__(self, policy, get):
        if type(policy) is not ProducerPolicy or not callable(get):
            raise ValueError('untrusted_proof_source')
        self.policy = policy
        self.get = get

    def verify(self, raw, context, *, run_id, attempt, artifact_id):
        """Return a sealed local receipt or raise a named fail-closed error.

        No catch-all green fallback. The Consumer handles failures as rejection.
        """
        try:
            return self._verify(raw,context,run_id=run_id,attempt=attempt,artifact_id=artifact_id)
        except (TypeError,AttributeError,KeyError,RecursionError) as exc:
            raise ValueError('malformed_proof_input') from exc

    def _verify(self,raw,context,*,run_id,attempt,artifact_id):
        p = self.policy
        context=normalize_context(context)
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
            raise ValueError('invalid_proof_size')
        if any(type(n) is not int or n <= 0 for n in (run_id, attempt, artifact_id)):
            raise ValueError('invalid_proof_identity')
        if (type(context) is not dict or not SHA.fullmatch(context.get('sha', ''))
                or not SHA.fullmatch(context.get('base', ''))):
            raise ValueError('invalid_proof_context')
        if (set(context) != {'pr', 'sha', 'base', 'paths', 'sources', 'diff', 'comments_fingerprint', 'finding_ids'}
                or type(context['pr']) is not int or context['pr'] <= 0
                or type(context['paths']) is not list or not context['paths']
                or any(type(f) is not dict or set(f) != {'filename', 'status'} for f in context['paths'])
                or type(context['sources']) is not dict or not context['sources']
                or set(context['sources']) != {f['filename'] for f in context['paths']}
                or len(context['paths']) != len(context['sources'])
                or any(type(v) is not str for v in context['sources'].values())
                or type(context['diff']) is not str or not context['diff']
                or type(context['comments_fingerprint']) is not str or not context['comments_fingerprint']
                or type(context['finding_ids']) is not list
                or any(type(i) is not str or not i for i in context['finding_ids'])
                or len(context['finding_ids']) != len(set(context['finding_ids']))):
            raise ValueError('incomplete_proof_context')
        # Path/extension is not a P4 proof; it only rejects unsafe input shape.
        for f in context['paths']:
            path = f['filename']
            if (type(path) is not str or not path or path.startswith('/')
                    or any(part in ('', '.', '..') for part in path.split('/'))
                    or '\\' in path or any(ord(c) < 32 for c in path)
                    or f['status'] not in ('added', 'modified')):
                raise ValueError('unsafe_or_incomplete_source_path')
        run = self.get(f'/repos/{REPO}/actions/runs/{run_id}')
        if (type(run) is not dict or type(run.get('id')) is not int
                or type(run.get('run_attempt')) is not int or type(run.get('workflow_id')) is not int
                or type(run.get('repository')) is not dict
                or type(run.get('actor')) is not dict or type(run.get('triggering_actor')) is not dict
                or type(run['actor'].get('id')) is not int or type(run['triggering_actor'].get('id')) is not int
                or run['actor']['id'] not in p.allowed_actor_ids or run['triggering_actor']['id'] not in p.allowed_actor_ids
                or run.get('head_branch')!=p.head_branch
                or run.get('id') != run_id or run.get('run_attempt') != attempt
                or run.get('repository', {}).get('full_name') != REPO
                or run.get('workflow_id') != p.workflow_id
                or run.get('path') != p.workflow_path
                or type(run.get('head_sha')) is not str or not SHA.fullmatch(run['head_sha'])
                or run.get('event') != p.event
                or run.get('status') != 'completed'
                or run.get('conclusion') != 'success'):
            raise ValueError('untrusted_or_incomplete_producer_run')
        head_sha = run['head_sha']
        artifact = self.get(f'/repos/{REPO}/actions/artifacts/{artifact_id}')
        if (type(artifact) is not dict or type(artifact.get('id')) is not int
                or type(artifact.get('workflow_run')) is not dict
                or type(artifact['workflow_run'].get('id')) is not int
                or artifact.get('id') != artifact_id
                or artifact.get('expired') is not False
                or artifact.get('workflow_run', {}).get('id') != run_id
                or artifact.get('workflow_run', {}).get('head_sha') != head_sha
                or artifact.get('digest') != 'sha256:' + hashlib.sha256(raw).hexdigest()):
            raise ValueError('artifact_provenance_or_digest_mismatch')
        # Content pin: the workflow plus its whole dependency closure, recomputed
        # from GitHub at the run's head_sha, must equal the pinned digest. The run's
        # exact commit is NOT pinned, so unrelated main merges keep the pin valid.
        if remote_closure_digest(self.get, head_sha, REPO) != p.closure_sha256:
            raise ValueError('producer_closure_mismatch')
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                entries = z.infolist()
                if len(entries) != 1:
                    raise ValueError('unexpected_artifact_entries')
                info = entries[0]
                mode = info.external_attr >> 16
                if (info.filename != 'proof.json' or info.is_dir()
                        or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                        or info.flag_bits & 1
                        or not 0 < info.file_size <= MAX_BYTES
                        or info.file_size > max(info.compress_size, 1) * 100):
                    raise ValueError('unsafe_proof_archive')
                body = z.read(info)
            record = json.loads(body.decode('utf-8'), object_pairs_hook=_unique,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid_json_number')))
        except (OSError, UnicodeError, zipfile.BadZipFile, RuntimeError) as exc:
            raise ValueError('invalid_proof_archive') from exc
        self._verify_record(record, context, run_id, attempt, head_sha)
        return VerifiedProof(digest(context), context['sha'], context['base'],
                             p.required_test_ids, run_id, attempt, _SEAL,
                             tuple((f['id'],f['disposition'],tuple(f['source_refs'])) for f in record['findings']))

    def _verify_record(self, record, context, run_id, attempt, head_sha):
        if type(record) is not dict or set(record) != {
                'version', 'repository', 'producer', 'context_sha256', 'scope', 'tests', 'findings', 'logs'}:
            raise ValueError('invalid_proof_schema')
        if record['version'] != 1 or type(record['version']) is not int or record['repository'] != REPO:
            raise ValueError('invalid_proof_schema')
        producer = record['producer']
        if (type(producer) is not dict or type(producer.get('run_id')) is not int
                or type(producer.get('attempt')) is not int):
            raise ValueError('invalid_producer_identity')
        if producer != {'run_id': run_id, 'attempt': attempt,
                        'head_sha': head_sha,
                        'closure_sha256': self.policy.closure_sha256,
                        'test_definition_sha256': self.policy.test_definition_sha256}:
            raise ValueError('producer_definition_mismatch')
        if record['context_sha256'] != digest(context):
            raise ValueError('stale_or_partial_proof_context')
        scope = record['scope']
        if (type(scope) is not dict or set(scope) != {'classification', 'ast_equivalent_only', 'coverage_complete', 'reasons'}
                or scope['classification'] != 'P4_python_ast_equivalent'
                or scope['ast_equivalent_only'] is not True
                or scope['coverage_complete'] is not True
                or type(scope['reasons']) is not list or not scope['reasons']
                or any(type(r) is not str or not r.strip() for r in scope['reasons'])):
            raise ValueError('unproven_P4_scope')
        logs = record['logs']
        if type(logs) is not dict or set(logs) != set(self.policy.required_test_ids):
            raise ValueError('raw_test_logs_missing')
        tests = record['tests']
        if type(tests) is not list or len(tests) != len(self.policy.required_test_ids):
            raise ValueError('required_test_evidence_missing')
        seen = set()
        for test in tests:
            if (type(test) is not dict or set(test) != {'id', 'executed', 'exit_code', 'assertions', 'skipped', 'definition_sha256', 'log_sha256'}
                    or test['id'] not in self.policy.required_test_ids or test['id'] in seen
                    or test['executed'] is not True
                    or type(test['exit_code']) is not int or test['exit_code'] != 0
                    or type(test['assertions']) is not int or test['assertions'] <= 0
                    or type(test['skipped']) is not int or test['skipped'] != 0
                    or test['definition_sha256'] != self.policy.test_definition_sha256
                    or type(test['log_sha256']) is not str or not HASH.fullmatch(test['log_sha256'])):
                raise ValueError('test_execution_or_definition_unproven')
            log = logs[test['id']]
            if (type(log) is not str or not log.strip()
                    or hashlib.sha256(log.encode()).hexdigest() != test['log_sha256']):
                raise ValueError('test_log_digest_mismatch')
            seen.add(test['id'])
        findings = record['findings']
        expected = context.get('finding_ids')
        if type(expected) is not list or type(findings) is not list or len(findings) != len(expected):
            raise ValueError('finding_evidence_missing')
        found = set()
        for f in findings:
            if (type(f) is not dict or set(f) != {'id', 'head_sha', 'disposition', 'test_id', 'source_refs'}
                    or f['id'] not in expected or f['id'] in found
                    or f['head_sha'] != context['sha']
                    or f['disposition'] not in ('verified_fixed', 'rejected_with_evidence')
                    or f['test_id'] not in seen
                    or type(f['source_refs']) is not list or not f['source_refs']
                    or any(type(r) is not str or not r.strip() for r in f['source_refs'])):
                raise ValueError('finding_evidence_unproven')
            found.add(f['id'])
