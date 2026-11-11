"""Content-hash pin of the trusted producer closure, replacing the exact-commit-SHA pin.

The closure is the pinned workflow file plus every file the producer depends on:
producer modules, the semantic lane, tests, fixtures and this manifest. The manifest
is an explicit member list, never a glob: a file added to .github/stronsium without
being listed changes nothing, and changing or removing any listed member breaks the
digest. Ordinary default-branch merges that do not touch a member keep the pin valid,
so the worker policy does not go stale on every unrelated merge; any merge that does
touch a member fails closed until the owner re-pins.

The same digest is computed two independent ways and both must match the policy pin:
the producer computes it from the default-branch checkout at run time (local), and the
verifier recomputes it from GitHub contents at the run's head_sha (remote).
"""
import base64
import hashlib
import json
import pathlib
import re
from urllib.parse import quote

MANIFEST_PATH = '.github/stronsium/closure_manifest.json'
MAX_MEMBERS = 64
MAX_MEMBER_BYTES = 1_000_000
MAX_MANIFEST_BYTES = 100_000
SHA = re.compile('[a-f0-9]{40}')
HASH = re.compile('[a-f0-9]{64}')


def _safe_path(path):
    return (type(path) is str and path and path.startswith('.github/')
            and not path.startswith('/') and '\\' not in path
            and all(part not in ('', '.', '..') for part in path.split('/'))
            and all(ord(c) >= 32 for c in path))


def parse_manifest(raw):
    """Strict manifest: {"version":1,"members":[...]}. The manifest never lists itself;
    the digest covers it implicitly."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        raise ValueError('closure_manifest_size')
    try:
        doc = json.loads(raw.decode('utf-8', 'strict'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('closure_manifest_json') from exc
    if type(doc) is not dict or set(doc) != {'version', 'members'} or doc['version'] != 1:
        raise ValueError('closure_manifest_schema')
    members = doc['members']
    if (type(members) is not list or not members or len(members) > MAX_MEMBERS
            or any(not _safe_path(p) for p in members)
            or len(set(members)) != len(members) or MANIFEST_PATH in members):
        raise ValueError('closure_manifest_members')
    return tuple(sorted(members))


def closure_digest(files):
    """sha256 over canonical [[path, content_sha256], ...] sorted by path."""
    if type(files) is not dict or not files or MANIFEST_PATH not in files:
        raise ValueError('closure_files_missing')
    items = []
    for path, raw in files.items():
        if (not _safe_path(path) or type(raw) is not bytes
                or not 0 < len(raw) <= MAX_MEMBER_BYTES):
            raise ValueError('closure_member_invalid')
        items.append([path, hashlib.sha256(raw).hexdigest()])
    items.sort()
    return hashlib.sha256(json.dumps(items, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def local_closure_digest(root):
    """Digest from a checked-out tree (the producer run's default-branch workspace)."""
    if type(root) is not str or not root:
        raise ValueError('closure_root_invalid')
    root = pathlib.Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('closure_root_invalid')
    root = root.resolve(strict=True)

    def read(p):
        path = root / p
        if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
            raise ValueError('closure_member_symlink')
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('closure_member_missing')
        raw = path.read_bytes()
        if not 0 < len(raw) <= MAX_MEMBER_BYTES:
            raise ValueError('closure_member_size')
        return raw

    manifest = read(MANIFEST_PATH)
    files = {MANIFEST_PATH: manifest}
    for member in parse_manifest(manifest):
        files[member] = read(member)
    return closure_digest(files)


def _content_bytes(doc):
    if (type(doc) is not dict or doc.get('type', 'file') != 'file'
            or doc.get('encoding') != 'base64' or type(doc.get('content')) is not str):
        raise ValueError('closure_remote_encoding')
    try:
        raw = base64.b64decode(''.join(doc['content'].split()), validate=True)
    except ValueError as exc:
        raise ValueError('closure_remote_encoding') from exc
    if not 0 < len(raw) <= MAX_MEMBER_BYTES:
        raise ValueError('closure_member_size')
    return raw


def remote_closure_digest(get, ref, repo):
    """Digest from the GitHub contents API at ref (a run's head_sha). `get` is the
    caller's authenticated READ transport; no ref or path comes from proof bytes."""
    if type(ref) is not str or not SHA.fullmatch(ref):
        raise ValueError('closure_ref_invalid')
    if type(repo) is not str or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('closure_repo_invalid')

    def fetch(p):
        return _content_bytes(get('/repos/' + repo + '/contents/' + quote(p, safe='/') + '?ref=' + ref))

    manifest = fetch(MANIFEST_PATH)
    files = {MANIFEST_PATH: manifest}
    for member in parse_manifest(manifest):
        files[member] = fetch(member)
    return closure_digest(files)
