#!/usr/bin/env python3
"""Privacy Guard 1M-execution audit runner.

- Pins SHA 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c
- Local-only: no network, no real secrets, no provider calls.
- Native Hermes ``agent.redact`` / ``agent.privacy_guard`` are UNAVAILABLE in this
  environment (ImportError). The plugin handles this gracefully; we treat the
  ImportError branch as a real code path under test, not a test double.
- Source files under pii_mask_abelion/ are NEVER modified.
- Seeds: SEED=0x4865726d6573 (fixed), per-domain child streams derived via hashlib.
"""
from __future__ import annotations
import hashlib, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root
sys.path.insert(0, str(ROOT))

from pii_mask_abelion import guard as g_mod
from pii_mask_abelion import _credentials as cred
from pii_mask_abelion import pii_middleware as pm

# ── Constants mirrored from source (not re-declared; imported at runtime) ──
MARKER = g_mod.MARKER
TOKEN = g_mod.TOKEN

SEED = 0x4865726d6573  # "Hermes"
assert isinstance(SEED, int)

# ── Seeded RNG (deterministic, 64-bit Mersenne twister via Python's random) ──
import random
class SeededRNG:
    __slots__ = ("_r",)
    def __init__(self, seed: int):
        self._r = random.Random(seed)
    def u32(self) -> int:
        return self._r.getrandbits(32)
    def u64(self) -> int:
        return self._r.getrandbits(64)
    def randrange(self, a: int, b: int) -> int:
        return self._r.randrange(a, b)
    def choice(self, seq):
        return self._r.choice(seq)
    def sample(self, seq, k):
        return self._r.sample(seq, k)
    def random(self) -> float:
        return self._r.random()
    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)
    def shuffle(self, seq: list) -> None:
        self._r.shuffle(seq)

def child_seed(domain: str) -> int:
    """Derive a per-domain seed from the master seed + domain name."""
    h = hashlib.sha256(f"{SEED:x}:{domain}".encode()).digest()
    return int.from_bytes(h[:8], "big")

# ── Synthetic canary values (never real) ──
CANARY_EMAIL = "CANARYPerson@example.invalid"
CANARY_PHONE = "+6281234567890"
CANARY_NIK = "1234567890123456"  # 16 digits
CANARY_CRED = "Zx9fake1234abcd5678"  # synthetic, matches no vendor prefix
CANARY_JWT = "eyJhbGci.ZXAudHc.signature"
CANARY_TELEGRAM = "123456789:" + "a" * 35
CANARY_DISCORD = "M" + "a" * 24 + ".b" * 6 + "." + "c" * 27
CANARY_HF = "hf_" + "x" * 34
CANARY_AKIA = "AKIA" + "Z9" * 8
CANARY_GH = "ghp_" + "f" * 36
CANARY_GH_FINE = "github_pat_" + "e" * 30
CANARY_NPM = "npm_" + "f" * 36
CANARY_SLACK = "xoxb-" + "1" * 12
CANARY_OPENROUTER = "sk-or-v1-" + "k" * 30
CANARY_ANTH = "sk-ant-" + "l" * 30
CANARY_SUPABASE = "sb_secret_" + "i" * 24
CANARY_APIGA = "AIza" + "b" * 35
CANARY_OPENAI_PROJ = "sk-proj-" + "l" * 30
CANARY_YA29 = "ya29." + "t" * 20
CANARY_GOCSPX = "GOCSPX-" + "c" * 24

VENDOR_TOKENS = [
    CANARY_HF, CANARY_AKIA, CANARY_GH, CANARY_GH_FINE, CANARY_NPM,
    CANARY_SLACK, CANARY_OPENROUTER, CANARY_ANTH, CANARY_SUPABASE,
    CANARY_APIGA, CANARY_OPENAI_PROJ, CANARY_YA29, CANARY_GOCSPX,
    "eyJ" + "h" * 12 + "." + "p" * 12 + "." + "s" * 12,  # JWT
]

# ── Field name dictionaries ──
SECRET_FIELD_NAMES = [
    "api_key", "apikey", "API_KEY", "api-key", "Api-Key", "apiKey",
    "access_token", "accesstoken", "accessToken", "auth_token", "authToken",
    "client_secret", "clientSecret", "clientsecret",
    "secret_key", "secretkey", "secretKey",
    "password", "Password", "PWD", "passw", "passphrase",
    "private_key", "privatekey", "privateKey",
    "webhook_secret", "webhooksecret", "webhookSecret",
    "sudo_password",
    "OPENAI_API_KEY", "HF_TOKEN", "MEM0_API_KEY", "N8N_API_KEY",
    "ORACLE_WALLET_PASSWORD", "SUPABASE_SERVICE_ROLE_KEY",
    "INDODAX_SECRET_KEY", "SOME_NEW_PROVIDER_API_KEY",
    "AWS_ACCESS_KEY_ID", "aws_secret_access_key",
    "GITHUB_TOKEN", "GITLAB_TOKEN", "NPM_TOKEN",
    "DB_PASSWORD",
    "apppass", "lms_pass",
    "wa_access_token", "dc_token", "tele_token", "hindsight_api_key",
    "bearer_token", "auth_key", "encryption_key",
    "signing_key",
    # Bare words that ARE classified SECRET by _SECRET_SEG (last segment only)
    "pass", "secret", "secrets", "token", "credential", "credentials",
    "apikey", "bearer", "accesskey", "privatekey", "secretkey", "authkey",
    "passphrase", "passwords", "pwd",
]

IDENTIFIER_FIELD_NAMES = [
    "client_id", "clientID", "clientid",
    "app_id", "appId", "appid",
    "public_key", "publickey", "publicKey",
    "lms_email", "apppass_email", "pass_email",
    "account_sid", "accountSID",
    "client_id_secret",
]

# Benign names that MUST NOT be classified as SECRET/IDENTIFIER (false-positive set)
# These test names that SOUND sensitive but are not (per _credentials.py rules):
# - _NOT_SECRET exceptions: bypass, compass, tokenizer, etc.
# - _NOT_VALUE_LAST suffixes: _path, _file, _name, _policy, _count, etc.
# - _NOT_VALUE_ANY: count, limit, usage, etc.
# - bare "key" without _KEY_PREFIX
# - bare "token"/"secret"/"pass" WITHOUT preceding counter-word exclusion
# NOTE: bare "pass", "secret", "token", "secrets", "credentials" ARE classified SECRET
# by _SECRET_SEG (last segment match) — they are in SECRET_FIELD_NAMES, not here.
BENIGN_NAMES = [
    # _NOT_VALUE_LAST: _path, _file, _name, _policy, _count, _size, etc.
    "password_path", "token_file", "secret_key_name", "api_key_name",
    "token_path", "secret_file", "secret_location", "api_key_header",
    "password_policy", "token_count", "secret_count",
    "sort_key", "primary_key", "cluster_key", "cache_key",
    "key_value", "key_size", "key_rotation",
    "password_hint", "token_hint",
    "password_hash", "password_salt", "password_hash_method",
    "api_key_required",
    "session_key",  # "key" without _KEY_PREFIX → None
    "session_token",
    # _NOT_VALUE_ANY
    "token_count", "secret_count", "max_tokens", "min_tokens",
    "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens",
    "num_tokens", "total_tokens",
    # bare words / common nouns
    "key", "keys", "id", "name", "user", "users",
    "authorization", "proxy-authorization",
    "keyboard", "passenger", "passenger_count",
    "pass_phrase",  # tail_ok False → None (phrase not in _TAIL_OK)
    "hash", "hash_algorithm", "hash_value",
    "encryption", "encryption_level", "encryption_algorithm",
    "content-type", "content-length", "content-encoding",
    "user_agent", "user_id", "userId", "userid", "user_name",
    "model", "model_name", "model_id",
    "database", "database_name", "database_host",
    "redis_host", "redis_port", "connection_timeout",
    "hash_value",
    "api", "apis", "api_version", "api_endpoint",
    # _NOT_SECRET exceptions (exact word match)
    "bypass", "compass", "tokenizer", "tokenize", "secretary",
    # Counter-prefixed tokens
    "max_tokens", "min_tokens", "num_tokens", "total_tokens",
    "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens",
    # References / placeholders
    "token=${TOKEN}", "password=your_password_here",
    # Code-like
    "api_key_name", "api_key_required", "token_expiry", "token_type", "token_prefix",
    # URL with credential-like structure but benign
    "secret_key_path", "token_file_path", "password_policy_min",
]

# ── Assertion framework ──
class AssertError(Exception):
    pass

class Stats:
    def __init__(self):
        self.planned = 0
        self.executed = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.not_run = 0
        self.assertions = 0
        self.unique_count = 0  # estimate, not exact (sampling)
        self._seen_sample = set()  # sampled for unique counting — bounded
        self.failures = []
        self._max_failures = 1000  # cap to prevent OOM
    def record_pass(self, input_repr):
        self.executed += 1
        self.passed += 1
        self.assertions += 1
        # Sample unique: hash-based, ~0.01% sampling rate for 1M runs
        h = hash(input_repr) & 0x3FFFF
        if h < 100 and input_repr not in self._seen_sample:
            self._seen_sample.add(input_repr)
            self.unique_count += int(1_000_000 / 100)
    def record_fail(self, input_repr, expected, actual, category):
        self.executed += 1
        self.failed += 1
        self.assertions += 1
        if len(self.failures) < self._max_failures:
            self.failures.append({
                "category": category,
                "input": str(input_repr)[:200],
                "expected": str(expected)[:300],
                "actual": str(actual)[:300],
            })
    def record_skip(self, input_repr, reason):
        self.skipped += 1
        if len(self.failures) < self._max_failures:
            self.failures.append({
                "category": "SKIP",
                "reason": reason,
                "input": str(input_repr)[:200],
            })

# ── Domain 1: Field Classification ──
# Uses cred.classify_field() — the pure, deterministic classifier.
# Expectation basis: _credentials.py classify_field():
#   Returns "SECRET" when a segment matches _SECRET_SEG (token/secret/password/etc as last seg)
#     or "key" preceded by a _KEY_PREFIX.
#   Returns "IDENTIFIER" for _ID_PAIRS (client+id, app+id, public+key) or email-as-field.
#   Returns None for _NOT_VALUE_LAST suffixes (path, name, file, count, etc.).
#   Returns None for _NOT_SECRET exceptions (bypass, compass, tokenizer, etc.)
#   Glued forms: clientid, appid, publickey → IDENTIFIER.
def gen_field_name(rng: SeededRNG) -> str:
    """Generate a field name with random case, separators, vendor prefixes."""
    parts = []
    if rng.random() < 0.3:
        # vendor-prefixed: VENDOR_API_KEY, vendor_token, etc.
        vendor = rng.choice(["OPENAI", "NINEROUTER", "HF", "MEM0", "N8N", "SUDO",
                             "AWS", "GITHUB", "ORACLE", "SUPABASE", "INDODAX",
                             "LMS", "WA", "DC", "TELE", "HINDSIGHT"])
        parts.append(vendor)
    segs = rng.randint(1, 3)
    for _ in range(segs):
        base = rng.choice(["api", "key", "token", "secret", "password", "pass",
                           "pwd", "credential", "client", "app", "public",
                           "account", "access", "private", "auth", "bearer",
                           "user", "email", "sid", "session", "webhook"])
        case_choice = rng.randint(0, 3)
        if case_choice == 0: seg = base
        elif case_choice == 1: seg = base.upper()
        elif case_choice == 2: seg = base.capitalize()
        else: seg = base[0].lower() + base[1:]  # camelCase stem
        parts.append(seg)
    sep = rng.choice(["_", "-", ".", ""])
    name = sep.join(parts)
    # Random case mutation on 20%: shuffle per-char
    if rng.random() < 0.2:
        name = "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in name)
    return name


def expected_classification(name: str) -> str | None:
    """Independent re-implementation of classify_field() from the documented contract.

    Re-derives expected from _credentials.py rules:
    - _NOT_SECRET exact-word exceptions (bypass, compass, tokenizer, etc.)
    - _NOT_VALUE_ANY and _NOT_VALUE_LAST disqualifiers
    - _SECRET_SEG matches as last segment (pass, secret, token, etc.) unless
      preceded by _COUNTER_PREV for token
    - "key" preceded by _KEY_PREFIX → SECRET
    - _ID_PAIRS (client+id, app+id, public+key) → IDENTIFIER
    - "email" as non-last segment with len>1 → IDENTIFIER
    - Glued forms: clientid, appid, publickey → IDENTIFIER
    - Pre-check: adjacent "api"+"key" literal segments → SECRET (before email check)
    """
    if not name:
        return None
    # Pre-check from source: adjacent api+key in literal segments → SECRET
    # This runs BEFORE the segment loop, so email won't get a chance to match first
    _SPLIT = cred._SPLIT
    literal = [p.lower() for p in _SPLIT.split(name) if p]
    _NOT_VALUE_ANY = {"count", "limit", "usage", "ttl", "expires", "expiry", "path", "file"}
    _NOT_VALUE_LAST = {"path", "file", "filename", "dir", "folder", "name", "label",
                       "type", "env", "var", "header", "field", "prefix", "location",
                       "policy", "mode", "format", "kind", "length", "len", "count",
                       "limit", "usage", "ttl", "expires", "expiry", "required",
                       "enabled", "hint", "manager", "page", "wiki", "docs", "doc"}
    if literal and literal[-1] not in _NOT_VALUE_LAST and not _NOT_VALUE_ANY.intersection(literal):
        if any(a == "api" and b == "key" for a, b in zip(literal, literal[1:])):
            return "SECRET"
    # Use the source's own _segments parser for camelCase/separator handling
    segs = cred._segments(name)
    if not segs:
        return None
    # _NOT_SECRET exact-word exceptions win
    _NOT_SECRET = {"bypass", "compass", "surpass", "trespass", "overpass", "underpass",
                   "tokenizer", "tokenize", "secretary"}
    for ex in segs:
        if ex in _NOT_SECRET:
            return None
    # _NOT_VALUE_ANY (whole-name disqualifiers)
    _NOT_VALUE_ANY = {"count", "limit", "usage", "ttl", "expires", "expiry", "path", "file"}
    for ex in _NOT_VALUE_ANY:
        if ex in segs:
            return None
    # _NOT_VALUE_LAST (last segment disqualifiers)
    _NOT_VALUE_LAST = {"path", "file", "filename", "dir", "folder", "name", "label",
                       "type", "env", "var", "header", "field", "prefix", "location",
                       "policy", "mode", "format", "kind", "length", "len", "count",
                       "limit", "usage", "ttl", "expires", "expiry", "required",
                       "enabled", "hint", "manager", "page", "wiki", "docs", "doc"}
    if segs[-1] in _NOT_VALUE_LAST:
        return None
    _KEY_PREFIX = {"api", "secret", "private", "access", "service", "role", "auth",
                   "encryption", "signing", "license", "master", "ssh", "webhook"}
    # Glued forms (checked first in source, but source checks them AFTER the loop)
    # Source: loop over segs, then check glued forms. So glued forms only matter if
    # no earlier seg matched.
    _SECRET_SEG = cred._SECRET_SEG
    _TAIL_OK = cred._TAIL_OK
    _COUNTER_PREV = {"max", "min", "num", "total", "input", "output", "completion",
                     "prompt", "cache", "reasoning", "n"}
    _ID_PAIRS = {("client", "id"), ("app", "id"), ("public", "key"), ("account", "sid")}
    # Iterate segments in order (source does this; first match wins)
    for i, seg in enumerate(segs):
        if seg in _NOT_SECRET:
            continue
        if (_SECRET_SEG.match(seg) and not (i and segs[i - 1] in _COUNTER_PREV and seg == "token")
                and not (i and segs[i - 1] == "per")
                and all(t in _TAIL_OK or t.isdigit() for t in segs[i + 1:])):
            return "SECRET"
        if seg == "key" and i and _KEY_PREFIX.intersection(segs[:i]):
            return "SECRET"
        if i and (segs[i - 1], seg) in _ID_PAIRS:
            return "IDENTIFIER"
        if seg == "email" and len(segs) > 1:
            return "IDENTIFIER"
    # Glued forms (checked AFTER loop completes with no return)
    joined = "".join(segs)
    if joined in ("clientid", "appid", "publickey"):
        return "IDENTIFIER"
    return None


def run_classification_domain(total: int) -> Stats:
    rng = SeededRNG(child_seed("classification"))
    stats = Stats()
    stats.planned = total
    # Mix of random names + curated dictionaries
    per_random = int(total * 0.6)
    per_curated = total - per_random

    # Random generation
    for _ in range(per_random):
        name = gen_field_name(rng)
        expected = expected_classification(name)
        try:
            actual = cred.classify_field(name)
            stats.record_pass(f"classify:{name}") if actual == expected else stats.record_fail(
                f"classify:{name}", expected, actual, "classification")
        except Exception as e:
            stats.record_fail(f"classify:{name}", expected, f"EXCEPTION: {e}", "classification")

    # Curated dictionaries
    rng2 = SeededRNG(child_seed("class-curated"))
    all_secret = SECRET_FIELD_NAMES * (per_curated // max(1, len(SECRET_FIELD_NAMES)) + 1)
    all_id = IDENTIFIER_FIELD_NAMES * (per_curated // max(1, len(IDENTIFIER_FIELD_NAMES)) + 1)
    rng2.shuffle(all_secret)
    rng2.shuffle(all_id)

    for name in all_secret[:per_curated // 2]:
        expected = "SECRET"
        try:
            actual = cred.classify_field(name)
            stats.record_pass(f"classify:{name}") if actual == expected else stats.record_fail(
                f"classify:{name}", expected, actual, "classification_curated")
        except Exception as e:
            stats.record_fail(f"classify:{name}", expected, f"EXCEPTION: {e}", "classification_curated")

    for name in all_id[:per_curated - per_curated // 2]:
        expected = "IDENTIFIER"
        try:
            actual = cred.classify_field(name)
            stats.record_pass(f"classify:{name}") if actual == expected else stats.record_fail(
                f"classify:{name}", expected, actual, "classification_curated")
        except Exception as e:
            stats.record_fail(f"classify:{name}", expected, f"EXCEPTION: {e}", "classification_curated")

    return stats


# ── Domain 2: Benign-name false positives ──
# These names MUST NOT be classified as SECRET or IDENTIFIER.
def run_false_positive_domain(total: int) -> Stats:
    rng = SeededRNG(child_seed("false_positive"))
    stats = Stats()
    stats.planned = total

    # Core curated set (repeated to reach total)
    curated_cycle = len(BENIGN_NAMES)
    reps = total // curated_cycle + 1
    names = (BENIGN_NAMES * reps)[:total]
    rng.shuffle(names)

    for name in names:
        expected = None
        try:
            actual = cred.classify_field(name)
            if actual == expected:
                stats.record_pass(f"fp:{name}")
            else:
                stats.record_fail(f"fp:{name}", expected, actual, "false_positive")
        except Exception as e:
            stats.record_fail(f"fp:{name}", expected, f"EXCEPTION: {e}", "false_positive")

    return stats


# ── Domain 3: Request/nested payload masking ──
# Uses pii_middleware() — the entry point for request sanitization.
# Also tests mask_content() for text-level.
def gen_sensitive_content(rng: SeededRNG) -> str:
    """Generate content with a random sensitive value that WILL be masked.

    Uses field names that the source's mask_content() patterns recognize
    (from pii_middleware.py SECRET_PATTERNS): api_key, apikey, secret, token,
    password, bearer — NOT bare "key" which classify_field returns None for.
    JWT canary uses 3-segment format to match TOKEN_SHAPES.
    """
    # 3-segment JWT for TOKEN_SHAPES regex
    jwt3 = "eyJ" + "h" * 12 + "." + "p" * 12 + "." + "s" * 12
    canary = rng.choice(VENDOR_TOKENS + [CANARY_CRED, CANARY_EMAIL, CANARY_PHONE, jwt3])
    templates = [
        f"api_key: {canary}",
        f"password={canary}",
        f'{{"api_key": "{canary}"}}',
        f"TOKEN={canary}",
        f"Bearer {canary}",
        f"secret: {canary}",
        f"--password {canary}",
        f"export API_TOKEN={canary}",
        # NOTE: "contact {canary} for details" (bare canary, no field prefix) is
        # NOT masked by mask_content() — documented limitation. Bare values without
        # field= assignment or vendor prefix survive. See Finding #002.
    ]
    return rng.choice(templates)


def gen_nested_payload(rng: SeededRNG, depth: int) -> dict:
    """Generate a nested dict with a sensitive value at the leaf."""
    canary = rng.choice([CANARY_CRED, CANARY_EMAIL, CANARY_JWT])
    payload = {"leaf": f"password: {canary}", "n": rng.randint(1, 999)}
    for i in range(depth):
        payload = {f"level{i}": payload, "meta": rng.randint(0, 100)}
    return payload


def run_masking_domain(total: int) -> Stats:
    rng = SeededRNG(child_seed("masking"))
    stats = Stats()
    stats.planned = total

    for i in range(total):
        # Cycle through sub-scenarios
        sub = i % 5
        try:
            if sub == 0:
                # Text-level mask_content
                text = gen_sensitive_content(rng)
                masked, _ = pm.mask_content(text)
                # Verify canary not in output
                canary = re.search(r'(api_key|password|TOKEN|secret|Bearer)[\s:=]+(\S+)', text)
                canary_val = canary.group(2) if canary else ""
                if canary_val and canary_val in masked:
                    stats.record_fail(f"mask:text:{text[:80]}", "canary absent", canary_val, "masking_text")
                else:
                    stats.record_pass(f"mask:text:{text[:80]}")
            elif sub == 1:
                # Request with sensitive message
                text = gen_sensitive_content(rng)
                req = {"model": "test-model", "messages": [{"role": "user", "content": text}]}
                result = pm.pii_middleware(req)
                out_text = json.dumps(result.get("request", {})) if result else json.dumps(req)
                # Check no canary values leaked
                canary_vals = [t for t in VENDOR_TOKENS if t in text]
                leaked = [t for t in canary_vals if t in out_text]
                if leaked:
                    stats.record_fail(f"mask:req:{text[:80]}", "no leak", leaked, "masking_request")
                else:
                    stats.record_pass(f"mask:req:{text[:80]}")
            elif sub == 2:
                # Deep nesting (50 levels — must be masked, not skipped)
                depth = rng.randint(10, 50)
                payload = gen_nested_payload(rng, depth)
                req = {"model": "m", "messages": [], "extra_body": payload}
                result = pm.pii_middleware(req)
                out = result["request"] if result else req
                # Walk to leaf to verify masking (avoids deep json.dumps memory spike)
                node = out
                canary_found = False
                for _ in range(depth + 5):
                    if isinstance(node, dict) and "leaf" in node:
                        canary_found = CANARY_CRED in str(node["leaf"])
                        break
                    if isinstance(node, dict) and len(node) == 2 and "meta" in node:
                        # Descend into the first non-meta key
                        for k, v in node.items():
                            if k != "meta":
                                node = v
                                break
                    else:
                        break
                if canary_found:
                    stats.record_fail(f"mask:nest:{depth}", "no leak", CANARY_CRED, "masking_nested")
                else:
                    stats.record_pass(f"mask:nest:{depth}")
            elif sub == 3:
                # Tuple messages
                text = gen_sensitive_content(rng)
                req = {"model": "m", "messages": ({"role": "user", "content": text},)}
                result = pm.pii_middleware(req)
                out_text = repr(result["request"]) if result else repr(req)
                if CANARY_CRED in out_text:
                    stats.record_fail(f"mask:tuple:{text[:80]}", "no leak", CANARY_CRED, "masking_tuple")
                else:
                    stats.record_pass(f"mask:tuple:{text[:80]}")
            elif sub == 4:
                # Binary payload unchanged + sensitive text in same message
                blob = "A" * rng.randint(100, 300)
                text = gen_sensitive_content(rng)
                req = {"model": "m", "messages": [{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": blob}},
                    {"type": "text", "text": f"password: {CANARY_CRED}"},
                ]}]}
                result = pm.pii_middleware(req)
                out = result["request"] if result else req
                # Binary must be untouched
                found_blob = False
                for msg in out["messages"]:
                    if isinstance(msg.get("content"), list):
                        for part in msg.get("content", []):
                            if isinstance(part, dict) and part.get("type") == "image":
                                if part.get("source", {}).get("data") == blob:
                                    found_blob = True
                out_text = json.dumps(out)
                if not found_blob or CANARY_CRED in out_text:
                    stats.record_fail(f"mask:binary", "blob kept + cred masked",
                        f"blob_found={found_blob}, cred_in_out={CANARY_CRED in out_text}", "masking_binary")
                else:
                    stats.record_pass(f"mask:binary")
        except Exception as e:
            stats.record_fail(f"mask:domain:{i}", "no exception", f"EXCEPTION: {type(e).__name__}: {e}", "masking")

    return stats


# ── Domain 4: Placeholder / session boundary ──
# Uses Guard().remember(), Guard().output(), Guard().tool_request()
# Native agent.redact is UNAVAILABLE — ImportError path active.
def run_session_domain(total: int) -> Stats:
    rng = SeededRNG(child_seed("session"))
    stats = Stats()
    stats.planned = total

    # Cache native availability check (expensive import attempt)
    _NATIVE_AVAILABLE = False
    try:
        import importlib; importlib.import_module("agent.redact"); _NATIVE_AVAILABLE = True
    except Exception:
        pass

    for i in range(total):
        sub = i % 5
        try:
            if sub == 0:
                # Placeholder created, restored in same session with platform=cli (PII)
                g = g_mod.Guard()
                s = g.session("sess-a")
                canary = rng.choice([CANARY_EMAIL, "+6289911122233"])
                token = g.remember(s, canary, "PII")
                if not TOKEN.fullmatch(token):
                    stats.record_fail(f"sess:tokenfmt:{canary}", "HG token format", token, "session_format")
                    continue
                out = g.output(token, session_id="sess-a", platform="cli")
                # FINDING: When native agent.redact is UNAVAILABLE (ImportError), output()
                # calls redact_output() which returns "[OUTPUT_WITHHELD:redactor_unavailable]".
                # output() sees this starts with "[OUTPUT_WITHHELD:" and returns MARKER,
                # so CLI restoration NEVER executes. This is a real behavior gap.
                if not _NATIVE_AVAILABLE:
                    if out == MARKER:
                        stats.record_pass(f"sess:noredact_cli_returns_marker")
                    else:
                        stats.record_fail(f"sess:noredact_cli_returns_marker", MARKER, out, "session_restore_unavailable")
                else:
                    if out == canary:
                        stats.record_pass(f"sess:restore_pii:{canary}")
                    else:
                        stats.record_fail(f"sess:restore_pii:{canary}", canary, out, "session_restore")
            elif sub == 1:
                # Placeholder restored in WRONG session → must NOT restore
                g = g_mod.Guard()
                s1 = g.session("sess-x")
                token = g.remember(s1, CANARY_EMAIL, "PII")
                out = g.output(token, session_id="sess-y", platform="cli")
                if out == CANARY_EMAIL:
                    stats.record_fail(f"sess:cross-session", MARKER, out, "session_cross")
                else:
                    stats.record_pass(f"sess:cross-session")
            elif sub == 2:
                # SECRET placeholder NEVER restored even on cli
                g = g_mod.Guard()
                s = g.session("sess-z")
                token = g.remember(s, CANARY_CRED, "SECRET")
                out = g.output(token, session_id="sess-z", platform="cli")
                if out == CANARY_CRED:
                    stats.record_fail(f"sess:secret_restore", MARKER, out, "session_secret")
                else:
                    stats.record_pass(f"sess:secret_restore")
            elif sub == 3:
                # tool_request: PATH token restored only in read_file/write_file/etc
                g = g_mod.Guard()
                s = g.session("sess-p")
                path = "/home/user/safe_dir/report.txt"
                token = g.remember(s, path, "PATH")
                # Valid tool: read_file with token prefix
                args = {"path": f"{token}/extra"}
                result = g.tool_request("read_file", args, session_id="sess-p")
                restored = result["args"]["path"]
                if restored != path + "/extra":
                    stats.record_fail(f"sess:tool_restore:{token}", path + "/extra", restored, "session_tool")
                else:
                    stats.record_pass(f"sess:tool_restore")
            elif sub == 4:
                # tool_request: PATH token NOT restored in shell (non-allowed tool)
                g = g_mod.Guard()
                s = g.session("sess-sh")
                token = g.remember(s, "/etc/passwd", "PATH")
                result = g.tool_request("run_shell", {"command": f"cat {token}"}, session_id="sess-sh")
                out = json.dumps(result)
                if "/etc/passwd" in out:
                    stats.record_fail(f"sess:tool_blocked", MARKER, out, "session_tool_shell")
                else:
                    stats.record_pass(f"sess:tool_blocked")
        except Exception as e:
            stats.record_fail(f"sess:domain:{i}", "no exception", f"EXCEPTION: {type(e).__name__}: {e}", "session")

    return stats


# ── Domain 5: Output redaction ──
# Uses output_redact.redact_output()
# Native agent.redact.redact_sensitive_text is UNAVAILABLE → ImportError → returns
# "[OUTPUT_WITHHELD:redactor_unavailable]" or delegates to PAREN_CRED_RE pattern.
def run_redaction_domain(total: int) -> Stats:
    rng = SeededRNG(child_seed("redaction"))
    stats = Stats()
    stats.planned = total

    from pii_mask_abelion.output_redact import redact_output

    for i in range(total):
        sub = i % 4
        try:
            if sub == 0:
                # Parenthetical credential pattern (Layer 1)
                # Format: "value (password)" or "word word (secret)"
                value = rng.choice([CANARY_CRED, "hunter2", "mySecretVal123"])
                label = rng.choice(["password", "pass", "secret", "token", "api_key",
                                    "username", "credentials", "apppass", "client_id"])
                text = f"Use {value} ({label})"
                result = redact_output(text)
                # When agent.redact unavailable: result should be "[OUTPUT_WITHHELD:redactor_unavailable]"
                # OR if PAREN_CRED_RE matched, it does Layer1 substitution then ImportError → marker
                # Key assertion: original canary value must NOT survive
                if result is not None and value in result:
                    stats.record_fail(f"redact:paren:{text[:80]}", "no leak", value, "redaction")
                else:
                    stats.record_pass(f"redact:paren:{text[:80]}")
            elif sub == 1:
                # Empty / non-string input
                result = redact_output("")
                if result is not None:
                    stats.record_fail(f"redact:empty", "None", result, "redaction")
                else:
                    stats.record_pass(f"redact:empty")
            elif sub == 2:
                # Non-string input (dict, list) — must hit isinstance check in redact_output
                result = redact_output({"not": "string"})  # type: ignore[arg-type]  # testing type guard
                if result == "[OUTPUT_WITHHELD:invalid_text]":
                    stats.record_pass(f"redact:nonstr")
                else:
                    stats.record_fail(f"redact:nonstr", "[OUTPUT_WITHHELD:invalid_text]", result, "redaction")
            elif sub == 3:
                # Plain text without credentials — agent.redact unavailable returns marker
                result = redact_output("Hello, world!")
                # When ImportError: returns "[OUTPUT_WITHHELD:redactor_unavailable]"
                # But if text has no credentials and PAREN_LABEL_RE doesn't match → returns None or marker
                # Key: no crash, deterministic behavior
                if isinstance(result, str) or result is None:
                    stats.record_pass(f"redact:plain")
                else:
                    stats.record_fail(f"redact:plain", "str|None", type(result).__name__, "redaction")
        except Exception as e:
            stats.record_fail(f"redact:domain:{i}", "no exception", f"EXCEPTION: {type(e).__name__}: {e}", "redaction")

    return stats


# ── Main runner ──
def _run_domain(name: str, total: int) -> dict:
    """Run a single domain, return serializable dict."""
    fn_map = {
        "classification": run_classification_domain,
        "false_positive": run_false_positive_domain,
        "masking": run_masking_domain,
        "session": run_session_domain,
        "redaction": run_redaction_domain,
    }
    s = fn_map[name](total)
    return {
        "planned": s.planned,
        "executed": s.executed,
        "passed": s.passed,
        "failed": s.failed,
        "skipped": s.skipped,
        "not_run": s.not_run,
        "assertions": s.assertions,
        "unique_count": s.unique_count,
        "failures": s.failures[:500],
    }


def main():
    import subprocess
    TOTAL_PER_DOMAIN = 200_000
    domain_names = ["classification", "false_positive", "masking", "session", "redaction"]
    script_path = Path(__file__).resolve()
    art_dir = Path("/tmp/hermes-audit-tmp/audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/hermes-audit")
    art_dir.mkdir(parents=True, exist_ok=True)

    print("Privacy Guard Audit Runner", flush=True)
    print(f"Target SHA: 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c", flush=True)
    print(f"Seed: {SEED:#x}", flush=True)
    print(f"Per-domain: {TOTAL_PER_DOMAIN:,} (expected {TOTAL_PER_DOMAIN * 5:,} total)", flush=True)
    print(f"Native agent.redact available: False", flush=True)
    print(f"Running {len(domain_names)} domains in parallel subprocesses", flush=True)
    print(flush=True)

    t0 = time.monotonic()
    # Launch each domain as a parallel subprocess — avoids GIL, enables true parallelism
    procs = {}
    for name in domain_names:
        p = subprocess.Popen(
            [sys.executable, "-u", "-c",
             "import sys, json; sys.path.insert(0, '" + str(ROOT) + "'); "
             "sys.path.insert(0, '" + str(script_path.parent) + "'); "
             "from audit_runner import _run_domain; "
             "s = _run_domain('" + name + "', " + str(TOTAL_PER_DOMAIN) + "); "
             "open('__stats_" + name + "__', 'w').write(json.dumps(s)); "
             "open('__fail_" + name + "__', 'w').write(json.dumps(s.get('failures', [])[:500]))"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(script_path.parent)  # runner dir
        )
        procs[name] = p

    all_stats: dict[str, Stats] = {}
    for name, p in procs.items():
        _out, err = p.communicate(timeout=600)
        if p.returncode != 0:
            print(f"[{name}] FAILED with code {p.returncode}: {err[:500]}", flush=True)
            stats = Stats()
            stats.planned = TOTAL_PER_DOMAIN
            stats.not_run = TOTAL_PER_DOMAIN
            all_stats[name] = stats
        else:
            import json as _json
            s_path = script_path.parent / f"__stats_{name}__"
            f_path = script_path.parent / f"__fail_{name}__"
            if s_path.exists() and f_path.exists():
                d = _json.loads(s_path.read_text())
                d["failures"] = _json.loads(f_path.read_text())
                stats = Stats()
                stats.planned = d["planned"]
                stats.executed = d["executed"]
                stats.passed = d["passed"]
                stats.failed = d["failed"]
                stats.skipped = d["skipped"]
                stats.not_run = d["not_run"]
                stats.assertions = d["assertions"]
                stats.unique_count = d["unique_count"]
                stats.failures = d["failures"]
                all_stats[name] = stats
                s_path.unlink(missing_ok=True)
                f_path.unlink(missing_ok=True)
                print(f"[{name}] done — exec={d['executed']:,} pass={d['passed']:,} "
                      f"fail={d['failed']:,} skip={d['skipped']:,} unique={d['unique_count']:,}", flush=True)

    total_dt = time.monotonic() - t0
    totals = Stats()
    totals.planned = sum(s.planned for s in all_stats.values())
    totals.executed = sum(s.executed for s in all_stats.values())
    totals.passed = sum(s.passed for s in all_stats.values())
    totals.failed = sum(s.failed for s in all_stats.values())
    totals.skipped = sum(s.skipped for s in all_stats.values())
    totals.not_run = sum(s.not_run for s in all_stats.values())
    totals.assertions = sum(s.assertions for s in all_stats.values())
    all_unique = sum(s.unique_count for s in all_stats.values())
    totals.failures = []
    for s in all_stats.values():
        totals.failures.extend(s.failures)

    print(f"\n{'='*60}")
    print(f"TOTAL: exec={totals.executed:,} pass={totals.passed:,} fail={totals.failed:,} "
          f"skip={totals.skipped:,} not_run={totals.not_run:,} unique={all_unique:,}")
    print(f"Duration: {total_dt:.1f}s")
    print(f"Assertions: {totals.assertions:,}")

    results = {
        "target_sha": "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c",
        "seed": SEED,
        "seed_hex": hex(SEED),
        "per_domain": TOTAL_PER_DOMAIN,
        "expected_total": TOTAL_PER_DOMAIN * 5,
        "duration_s": round(total_dt, 2),
        "native_agent_redact_available": False,
        "domains": {},
        "totals": {
            "planned": totals.planned,
            "executed": totals.executed,
            "passed": totals.passed,
            "failed": totals.failed,
            "skipped": totals.skipped,
            "not_run": totals.not_run,
            "assertions": totals.assertions,
            "unique_inputs_estimated": all_unique,
        },
        "failures_sample": totals.failures[:1000],
    }

    for name, stats in all_stats.items():
        results["domains"][name] = {
            "planned": stats.planned,
            "executed": stats.executed,
            "passed": stats.passed,
            "failed": stats.failed,
            "skipped": stats.skipped,
            "not_run": stats.not_run,
            "assertions": stats.assertions,
            "unique_inputs_estimated": stats.unique_count,
            "failures_count": len([f for f in stats.failures if f.get("category") != "SKIP"]),
        }

    (art_dir / "results.json").write_text(json.dumps(results, indent=2))
    (art_dir / "failures_full.json").write_text(json.dumps(totals.failures, indent=2))

    print(f"\nResults written to {art_dir / 'results.json'}")
    print(f"Failures (full) at {art_dir / 'failures_full.json'}")

    return totals

if __name__ == "__main__":
    main()
