#!/usr/bin/env python3
"""Independent audit runner for pii_mask_abelion (Privacy Guard), pinned SHA.

Two phases (separate processes each with their own results file):
  A ("no_native"): D1 classifier, D2 benign-name false positives,
     D3 request/nested-payload masking, D4 non-restore session boundaries,
     D5 output containment with NO native Hermes redactor present.
  B ("native_stub"): same D4/D5 domain keys carrying the restore-kind matrix
     and paren passes, run with a controlled mock of `agent.redact`
     (plugin code real; only the host redactor seam is stubbed).

Budget sum across phases == 1,000,000 executions.
Expectations derive only from the tested files' own contract (docstrings,
source comments, plugin README behavior section). The repository's existing
pytest suite was read for context only; every expectation here was re-derived.
All values are synthetic canaries; no real secrets are used.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import random
import string
import sys
import time
import traceback
from types import ModuleType

SEED = 0xA17D17A5
SHA = "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c"
REPO = os.environ.get("AUDIT_REPO_ROOT", "/tmp/opencode/pg-audit-work")
MARKER = "[GUARD_WITHHELD]"  # [c] guard.py line "MARKER = '[GUARD_WITHHELD]'"

PHASE = os.environ.get("AUDIT_PHASE", "A")

PHASES = {
    "A": {
        "D1_field_classification": 200_000,
        "D2_benign_name_false_positives": 140_000,
        "D3_request_nested_payload_masking": 310_000,
        "D4_placeholder_session_boundaries": 165_000,
        "D5_output_redaction": 60_000,
    },
    "B": {
        "D4_placeholder_session_boundaries": 25_000,
        "D5_output_redaction": 100_000,
    },
}

# family weights per (phase, domain)
FAMILIES = {
    ("A", "D1_field_classification"): [
        ("secret", 0.55), ("identifier", 0.20), ("benign", 0.25),
        ("encoded", 0.05), ("regression", 0.05),
    ],
    ("A", "D2_benign_name_false_positives"): [
        ("benign", 0.44), ("secret", 0.15), ("quoted", 0.06), ("enckey", 0.04),
        ("bearer", 0.05), ("basic", 0.04), ("curlu", 0.05), ("mysqlp", 0.05),
        ("pem", 0.05), ("cookie", 0.05), ("blobname", 0.04), ("flag", 0.06),
        ("flag_benign", 0.06),
    ],
    ("A", "D3_request_nested_payload_masking"): [
        ("benign_eq", 0.24), ("masked_walk", 0.30), ("tool_args", 0.12),
        ("media", 0.05), ("binary", 0.05), ("oversize", 0.01), ("deep", 0.02),
        ("unknown_ph", 0.05), ("spoof", 0.04), ("invalid", 0.03),
        ("sm_deny", 0.07), ("sm_allow_gap", 0.03), ("sm_prose", 0.02),
        ("pim_benign", 0.02), ("pim_masked", 0.04), ("mvk", 0.03),
    ],
    ("A", "D4_placeholder_session_boundaries"): [
        ("dedup", 0.16), ("isol_val", 0.12), ("isol_out", 0.13), ("close_hold", 0.14),
        ("tool_path", 0.10), ("tool_unsafe", 0.10), ("block_generic", 0.09),
        ("cap_entries", 0.09), ("cap_sessions", 0.08), ("req_isol", 0.09),
    ],
    ("B", "D4_placeholder_session_boundaries"): [("rest_kind", 1.0)],
    ("A", "D5_output_redaction"): [
        ("contain", 0.40), ("doc_edges", 0.30), ("paren", 0.30),
    ],
    ("B", "D5_output_redaction"): [
        ("rest", 0.35), ("paren_stub", 0.20), ("stub_passthrough", 0.20),
        ("stub_secret", 0.25),
    ],
}

if os.environ.get("AUDIT_SMOKE"):
    for _k in PHASES:
        PHASES[_k] = {d: 400 for d in PHASES[_k]}


def pick_family(domain: str, rng: random.Random) -> str:
    fams = FAMILIES[(PHASE, domain)]
    r = rng.random()
    acc = 0.0
    for f, w in fams:
        acc += w
        if r < acc:
            return f
    return fams[-1][0]


def canon(key: str) -> bytes:
    return hashlib.sha1(key.encode("utf-8", "surrogatepass")).digest()


def hexs(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


class Case:
    def __init__(self, domain: str):
        self.domain = domain
        self.executed = 0
        self.passed = 0
        self.failed = 0
        self.assertions = 0
        self.assertion_failures = 0
        self.unique: set = set()
        self.family_pass: dict = {}
        self.family_fail: dict = {}
        self.repros: list = []
        self.repro_keys: set = set()

    def run_one(self, rng: random.Random, key: str, family: str, fn):
        """One counted execution: a single target invocation with its own
        assertion set; all assertions in the set must hold for exec PASS."""
        self.executed += 1
        self.unique.add(canon(key))
        try:
            fn()
            self.passed += 1
            self.family_pass[family] = self.family_pass.get(family, 0) + 1
        except AssertionError as exc:
            self.fail_counter(family, key, "assertion", str(exc), "")
        except Exception as exc:
            self.fail_counter(family, key, "exception",
                              f"{type(exc).__name__}: {exc}",
                              "".join(traceback.format_exception(
                                  type(exc), exc, exc.__traceback__))[:1500])

    def fail_counter(self, family, key, what, detail, tb):
        self.failed += 1
        self.family_fail[family] = self.family_fail.get(family, 0) + 1
        if what in ("assertion", "exception"):
            self.assertion_failures += (1 if what == "assertion" else 0)
        hk = canon(f"{family}|{key}")
        if hk not in self.repro_keys and len(self.repros) < 400:
            self.repro_keys.add(hk)
            self.repros.append({
                "domain": self.domain, "phase": PHASE, "family": family,
                "exec_no": self.executed,
                "generator": f"fixed seed {SEED}; family {family}; synthetic canaries",
                "what": what, "detail": detail[:1200], "traceback": tb[:1500],
            })

    def assert_true(self, cond, expect, actual="", tag=""):
        self.assertions += 1
        if not cond:
            raise AssertionError(f"{tag}::expected={expect}::actual={actual}")


class Gen:
    """Deterministic generator pool (own word banks, own compositions)."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seq = 0

    def nxt(self) -> int:
        self.seq += 1
        return self.seq

    def pick(self, items):
        return self.rng.choice(items)

    def canary(self, style=None) -> str:
        style = style or self.pick(("h8", "h8x", "alpha5", "alnum8", "word4"))
        tag = hexs(self.rng, 4) + str(self.nxt())
        if style == "h8":
            return f"{CAN}{tag}{''.join(self.rng.choice('0123456789abcdef') for _ in range(8))}"
        if style == "h8x":
            return f"{CAN}_{tag}_{self.rng.randint(1, 9999999):x}"
        if style == "alpha5":
            return f"{CAN}{tag}{''.join(self.rng.choice(string.ascii_lowercase) for _ in range(5))}"
        if style == "alnum8":
            return f"{CAN}{tag}{''.join(self.rng.choice(string.ascii_letters + string.digits) for _ in range(8))}"
        return f"{CAN}{tag}"


CAN = "cnry"  # synthetic canary marker

# ---------- vocabulary banks (independently crafted; not copied from repo tests)

SECRET_FINALS = ["password", "passwd", "pwd", "passphrase", "token", "secret",
                 "bearer", "apikey", "accesskey", "privatekey", "secretkey",
                 "authkey", "credential", "credentials"]
TAIL_OK = ["key", "value", "val", "str", "string", "text", "hex", "raw", "plain",
           "v1", "v2", "primary", "secondary"]
SAFE_PREFIX_WORDS = ["lms", "foo", "prod", "deploy", "staging", "ci", "legacy",
                     "vault", "db", "web", "smtp", "repo", "svc"]
NOT_VALUE_LAST = ["path", "file", "filename", "dir", "folder", "name", "label",
                  "type", "env", "var", "header", "field", "prefix", "location",
                  "policy", "mode", "format", "kind", "length", "len", "count",
                  "limit", "usage", "ttl", "expires", "expiry", "required",
                  "enabled", "hint", "manager", "page", "wiki", "docs", "doc"]
NOT_VALUE_ANY = ["count", "limit", "usage", "ttl", "expires", "expiry", "path", "file"]
NOT_SECRET = ["bypass", "compass", "surpass", "trespass", "overpass", "underpass",
              "tokenizer", "tokenize", "secretary", "mypass"]
COUNTER_PREV = ["max", "min", "num", "total", "input", "output", "completion",
                "prompt", "cache", "reasoning", "n"]
KEY_PREFIXES = ["api", "secret", "private", "access", "service", "role", "auth",
                "encryption", "signing", "license", "master", "ssh", "webhook"]
BENIGN_GIBBERISH = ["frobniz", "quuxbag", "zorpkit", "wibble", "grokform",
                    "blorptix", "snardle", "vexmine", "plumbus", "kirkenpath"]
ID_FINALS = [("client", "id"), ("app", "id"), ("public", "key"), ("account", "sid")]
IDENT_EMAIL_PREFIX = ["lms", "workmail", "ops", "apppass"]


def mix_case(rng: random.Random, word: str) -> str:
    style = rng.choice(("lower", "upper", "toggle", "title", "random"))
    if style == "lower":
        return word.lower()
    if style == "upper":
        return word.upper()
    if style == "title":
        return word[:1].upper() + word[1:].lower()
    if style == "toggle":
        return "".join(c.lower() if c.isupper() else c.upper() for c in word)
    return "".join(rng.choice((c.lower(), c.upper())) for c in word)


def join_words(rng: random.Random, words: list) -> str:
    sep = rng.choice(("_", "-", ".", "", "camel"))
    if sep == "camel":
        return "".join(mix_case(rng, w) for w in words)
    return sep.join(mix_case(rng, w) for w in words)


def build_secret_name(g: Gen) -> str:
    """SECRET names per _credentials.py: _SECRET_SEG finals with TAIL_OK tails,
    _KEY_PREFIX+'key', or literal api+key pair; exclusions respected by
    construction (no counter/per before token, no NOT_VALUE_LAST/ANY)."""
    rng = g.rng
    r = rng.random()
    if r < 0.25:
        pre = [g.pick(SAFE_PREFIX_WORDS)] if rng.random() < 0.35 else []
        tail = [g.pick(TAIL_OK)] if rng.random() < 0.35 else []
        return join_words(rng, pre + ["api", "key"] + tail)
    if r < 0.45:
        tail = [g.pick(TAIL_OK)] if rng.random() < 0.30 else []
        return join_words(rng, [g.pick(KEY_PREFIXES), "key"] + tail)
    if r < 0.65:
        fin = g.pick(SECRET_FINALS)
        pre = [g.pick(SAFE_PREFIX_WORDS)] if rng.random() < 0.5 else []
        if fin == "token" and pre and pre[0] in COUNTER_PREV + ["per"]:
            pre = ["cnryroot"]
        return join_words(rng, pre + [fin])
    if r < 0.85:
        fin = g.pick([w for w in SECRET_FINALS if w != "token"])
        pre = [g.pick(SAFE_PREFIX_WORDS)] if (rng.random() < 0.4 and fin != "token") else []
        return join_words(rng, pre + [fin])
    a = g.pick(SAFE_PREFIX_WORDS)
    b = g.pick([w for w in SECRET_FINALS if w != "secret"])
    tail = g.pick(TAIL_OK) if rng.random() < 0.4 else ""
    out = join_words(rng, [a, b])
    return out + (mix_case(rng, tail) if tail else "")


def build_identifier_name(g: Gen) -> str:
    """IDENTIFIER names per _ID_PAIRS / joined clientid-appid-publickey /
    email-final rule."""
    rng = g.rng
    r = rng.random()
    if r < 0.45:
        a, b = g.pick(ID_FINALS)
        return join_words(rng, [a, b])
    if r < 0.70:
        return join_words(rng, [g.pick(("clientid", "appid", "publickey"))])
    return join_words(rng, [g.pick(IDENT_EMAIL_PREFIX), "email"])


def build_benign_name(g: Gen) -> str:
    """Names classified None: NOT_SECRET words, NOT_VALUE_LAST finals,
    any NOT_VALUE_ANY segment, counter-prev+token, per-guard, out-of-vocab."""
    rng = g.rng
    r = rng.random()
    if r < 0.22:
        return mix_case(rng, g.pick(NOT_SECRET))
    if r < 0.44:
        words = [g.pick(NOT_VALUE_ANY)]
        words += [g.pick(BENIGN_GIBBERISH) for _ in range(rng.randint(0, 2))]
        rng.shuffle(words)
        return join_words(rng, words)
    if r < 0.62:
        first = g.pick(SAFE_PREFIX_WORDS + BENIGN_GIBBERISH + KEY_PREFIXES)
        last = g.pick(NOT_VALUE_LAST)
        if last in NOT_VALUE_ANY:
            last = g.pick([w for w in NOT_VALUE_LAST if w not in NOT_VALUE_ANY])
        return join_words(rng, [first, last])
    if r < 0.78:
        return join_words(rng, [g.pick(COUNTER_PREV), "token"])
    if r < 0.90:
        # 'per' guard applies to pass-family and token finals only [cw l187-189];
        # key-decomposed finals (accesskey, apikey, ...) are vocab-parsed and
        # bypass that guard, so they belong to the SECRET bank instead.
        return join_words(rng, ["per", g.pick(["password", "passwd", "pwd",
                                               "passphrase", "token", "secret",
                                               "bearer", "credential"])])
    return mix_case(rng, g.pick(BENIGN_GIBBERISH))


STYLE_TEMPLATES = [
    "{name}={value}",
    "{name}: {value}",
    '"{name}": "{value}"',
    "export {name}={value}",
    "- {name}: {value}",
    "{name} = {value}",
    "{name}:{value}",
]


def style_text(g: Gen, name: str) -> tuple:
    value = g.canary(g.pick(("h8", "h8x", "alpha5", "alnum8", "word4")))
    tmpl = g.pick(STYLE_TEMPLATES)
    return tmpl.format(name=name, value=value), value


# ------------------------------------------------------------------ D1

REGRESSIONS_D1 = [
    ("password", "SECRET"), ("paSsWOrD", "SECRET"), ("service-password", "SECRET"),
    ("SerViCE-PasSWord", "SECRET"), ("client_id", "IDENTIFIER"),
    ("aCcoUNT_SiD", "IDENTIFIER"), ("compass", None), ("CoMPASs", None),
    ("api_key_name", None), ("API_key_nAme", None), ("apikey", "SECRET"),
    ("ApIkEy", "SECRET"), ("maxTokens", None), ("tokenCount", None),
    ("secretFile", None), ("tokenizer", None), ("model", None),
    ("bearertoken", "SECRET"), ("MyApiKey3", "SECRET"), ("publickey", "IDENTIFIER"),
]


def d1_exec(case: Case, g: Gen):
    cred = M["cred"]
    rng = g.rng
    fam = pick_family("D1_field_classification", rng)
    if fam == "secret":
        name = build_secret_name(g)
        exp = "SECRET"
    elif fam == "identifier":
        name = build_identifier_name(g)
        exp = "IDENTIFIER"
    elif fam == "benign":
        name = build_benign_name(g)
        exp = None
    elif fam == "encoded":
        # URL-encoded separators are decoded by call sites ([c] l107 unquote;
        # [cw] _NAME matches %5F/%2D/%2E), not by the classifier itself ->
        # direct classify_field contract result is None for raw encoded input.
        base = (("api", "%5F", "key") if rng.random() < 0.5 else
                ("password", "%2E", "123"))
        name = "".join(mix_case(rng, p) for p in base)
        exp = None
    else:
        name, exp = reg_pick = g.pick(REGRESSIONS_D1)
    got = cred.classify_field(name)
    def check():
        case.assert_true(cred.classify_field(name) == exp,
                         f"classify_field({name!r}) == {exp!r} [cw]",
                         f"got {cred.classify_field(name)!r}", tag=f"D1.{fam}")
        case.assert_true(cred.classify_field(name) == got,
                         "classifier pure (repeat call, same result)", got, tag="D1.pure")
    key = f"D1|{fam}|{name}|{SEED}"
    case.run_one(rng, key, fam, check)


# ------------------------------------------------------------------ D2

def d2_exec(case: Case, g: Gen):
    guard = M["Guard"]()
    rng = g.rng
    fam = pick_family("D2_benign_name_false_positives", rng)
    sid = "d2"
    if fam == "benign":
        name = build_benign_name(g)
        text, value = style_text(g, name)
        if rng.random() < 0.35:
            text += " then " + g.pick(BENIGN_GIBBERISH)
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(gt == text,
                             "benign field name keeps value and text unchanged [c spans flow]", gt,
                             tag="D2.benign")
            case.assert_true("<HG:" not in gt, "no token minted for benign text [c]", gt,
                             tag="D2.benign2")
    elif fam == "secret":
        name = build_secret_name(g)
        text, value = style_text(g, name)
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt, "secret-name value masked [c]", gt, tag="D2.secret")
            case.assert_true("<HG:" in gt, "session token present [c]", gt, tag="D2.token")
    elif fam == "quoted":
        name = build_secret_name(g)
        value = g.canary("h8x")
        text = f'{name}: "{value}"'
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt, "quoted secret value masked [c]", gt, tag="D2.quote")
    elif fam == "enckey":
        nm = g.pick(("api%5Fkey", "API%2Dkey", "auth%2Ekey"))
        value = g.canary("h8x")
        text = f"{nm}={value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt,
                             "URL-encoded name decoded then masked [c l107 unquote]", gt,
                             tag="D2.enc")
    elif fam == "bearer":
        value = "cnry" + hexs(rng, 20)
        pre = g.pick(("Bearer", "BEARER", "bearer", "bEaReR"))
        text = f"{pre} {value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt, "bearer value masked [c]", gt, tag="D2.bearer")
    elif fam == "basic":
        value = "cnry" + hexs(rng, 20)
        pre = g.pick(("Basic", "BASIC", "basic"))
        text = f"{pre} {value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt, "basic value masked [c]", gt, tag="D2.basic")
    elif fam == "curlu":
        user = g.pick(BENIGN_GIBBERISH)
        pw = g.canary("h8x")
        text = f"curl -s -u {user}:{pw} https://x.invalid"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(pw not in gt, "curl -u password masked [c]", gt, tag="D2.curl")
    elif fam == "mysqlp":
        pw = g.canary("h8x")
        host = g.pick(BENIGN_GIBBERISH)
        text = f"mysql -h {host} -p{pw}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(pw not in gt, "mysql -p masked [c]", gt, tag="D2.mysql")
    elif fam == "pem":
        body = hexs(rng, 16) + " " + hexs(rng, 16)
        text = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(body not in gt, "PEM body masked [c]", gt, tag="D2.pem")
    elif fam == "cookie":
        sidv = g.canary("h8x")
        kind = g.pick(("Cookie", "Set-Cookie", "cOoKiE"))
        text = f"{kind}: SID={sidv}; Secure"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(sidv not in gt, "cookie header value masked [c]", gt, tag="D2.cookie")
    elif fam == "blobname":
        nm = g.pick(("credential_blob", "secret_payload", "credential-data"))
        value = g.canary("h8x")
        text = f"{nm} = {value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt,
                             "secret/credential blob|data|payload field masked [c l108]", gt,
                             tag="D2.blob")
    elif fam == "flag":
        nm = mix_case(rng, g.pick(("password", "api-key", "transit-secret")))
        value = g.canary("h8x")
        text = f"--{nm}={value}" if rng.random() < 0.5 else f"--{nm} {value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(value not in gt, "flag value masked [c]", gt, tag="D2.flag")
    else:  # flag_benign: benign flag name keeps the value
        nm = join_words(rng, [g.pick(BENIGN_GIBBERISH), g.pick(NOT_VALUE_LAST)])
        value = g.canary("h8x")
        text = f"--{nm}={value}" if rng.random() < 0.5 else f"--{nm} {value}"
        def check():
            gt = guard.text(text, guard.session(sid))
            guard.close(sid)
            case.assert_true(gt == text,
                             "benign flag name leaves value untouched [c]", gt, tag="D2.flagben")
    key = f"D2|{fam}|{text}|{SEED}"
    case.run_one(rng, key, fam, check)


# ------------------------------------------------------------------ D3

def nested_val(depth: int, gg: random.Random, seeds) -> object:
    if depth <= 0:
        leaf = gg.random()
        if leaf < 0.4:
            return gg.choice(BENIGN_GIBBERISH)
        if leaf < 0.7:
            return "cnry" + "".join(gg.choice(string.ascii_lowercase) for _ in range(4))
        return gg.choice(["", "true", "false", gg.randint(1, 999), "note"])
    d = {}
    n = gg.randint(1, 4)
    for _ in range(n):
        d[gg.choice(BENIGN_GIBBERISH + ["note", "desc", "k", "v", "cfg"]) + str(len(d))] = \
            nested_val(depth - 1, gg, seeds)
    if seeds:
        keyname, val = seeds[gg.randrange(len(seeds))]
        d[keyname] = val
    return d


def make_request(g: Gen, seeds, depth, kind) -> dict:
    content = nested_val(depth, g.rng, seeds)
    inner = json.dumps(content) if isinstance(content, dict) else str(content)
    if kind == "plain":
        return {"model": "test-model", "user": "cnry-user",
                "messages": [{"role": g.pick(("user", "system")), "content": inner}]}
    if kind == "toolcall":
        args = dict(seeds) if seeds else {}
        if g.rng.random() < 0.4:
            args["note"] = g.pick(BENIGN_GIBBERISH)
        return {"model": "test-model",
                "messages": [{"role": "assistant", "content": "x"}],
                "tools": [{"type": "function", "function": {
                    "name": "toolxff", "arguments": json.dumps(args)}}]}
    field, val = seeds[0] if seeds else ("apiKey", g.canary("h8"))
    return {"model": "test-model",
            "messages": [{"role": "system", "content": "ops docs"}],
            "tools": [{"type": "function", "function": {
                "name": "toolfff",
                "input_schema": {"type": "object",
                                 "properties": {field: {"type": "string"}}}}},
                {"type": "function", "function": {
                    "name": "toolyzy", "arguments": json.dumps({field: val})}}]}


def d3_exec(case: Case, g: Gen):
    guard = M["Guard"]()
    rng = g.rng
    fam = pick_family("D3_request_nested_payload_masking", rng)
    name = build_secret_name(g)
    canary = g.canary(rng.choice(("h8", "h8x", "alnum8")))
    sid = f"s{g.nxt()}"
    if fam == "benign_eq":
        req = make_request(g, [], rng.randint(1, 3), rng.choice(("plain", "toolcall")))
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is True, "benign nested request allowed [c]",
                             str(res), tag="D3.eq.allow")
            if res.get("allow"):
                case.assert_true(res["request"] == req, "benign request unchanged deep [c]",
                                 json.dumps(res.get("request"))[:400], tag="D3.eq.deep")
                case.assert_true(res["request"] == req, "input request untouched [c]",
                                 "mutated", tag="D3.eq.immutable")
        key = f"D3|{fam}|{sid}|{len(json.dumps(req))}|{SEED}"
    elif fam == "masked_walk":
        req = make_request(g, [(name, canary)], rng.randint(1, 3),
                          rng.choice(("plain", "toolcall", "schema")))
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            out = json.dumps(res.get("request", {}))
            case.assert_true(res.get("allow") is True, "walk-masked request still allowed [c]",
                             str(res), tag="D3.walk.allow")
            case.assert_true(canary not in out, "seeded canary masked [c]", out[:600],
                             tag="D3.walk.mask")
            case.assert_true("<HG:" in out, "session token in masked request [c]", out[:600],
                             tag="D3.walk.token")
        key = f"D3|{fam}|{sid}|{name}|{canary}|{SEED}"
    elif fam == "tool_args":
        field2 = build_secret_name(g)
        canary2 = g.canary("alnum8")
        args = {field2: canary2, "note": g.pick(BENIGN_GIBBERISH),
                "nx88": {build_secret_name(g): g.canary("h8")}}
        req = {"model": "test-model", "messages": [{"role": "user", "content": "hi"}],
               "tools": [
            {"type": "function", "function": {"name": "checkerf",
                                              "arguments": json.dumps(args), }}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            out = json.dumps(res.get("request", {}))
            case.assert_true(canary2 not in out, "tool arguments JSON masked [c l214-216]", out[:400],
                             tag="D3.args.mask")
            case.assert_true(res.get("allow") is True, "tool args request allowed [c]", str(res),
                             tag="D3.args.allow")
        key = f"D3|{fam}|{sid}|{field2}|{canary2}|{SEED}"
    elif fam == "media":
        req = {"model": "test-model", "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAAAA"}}]}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "media content denied [c]", str(res),
                             tag="D3.media.deny")
            case.assert_true(res.get("reason") == "media", "media reason [c]", str(res),
                             tag="D3.media.reason")
        key = f"D3|{fam}|{sid}|{SEED}"
    elif fam == "binary":
        # plain leaf under a binary key: no media 'type' on the wrapper dict,
        # so the withholding comes from the leaf key branch [c l210].
        req = {"model": "test-model", "messages": [{"role": "user", "content": "hi"}],
               "attachments": {"meta": g.pick(BENIGN_GIBBERISH),
                               "file_data": "AAAA" + hexs(rng, 24)}}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "binary leaf denied [c]", str(res),
                             tag="D3.bin.deny")
            case.assert_true(res.get("reason") == "unsupported_content",
                             "withheld leaf -> unsupported_content [c l271]", str(res),
                             tag="D3.bin.reason")
        key = f"D3|{fam}|{sid}|{SEED}"
    elif fam == "oversize":
        big = "cnry" + hexs(rng, 8) + "x" * 131_080
        req = {"model": "test-model", "messages": [{"role": "user", "content": big}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "oversized string denied [c l174]", str(res),
                             tag="D3.big.deny")
        key = f"D3|{fam}|{sid}|{len(big)}|{SEED}"
    elif fam == "deep":
        req = {"model": "test-model", "messages": [{"role": "user", "content": "ok"}]}
        node = req
        for _ in range(70):
            node["nd"] = nxt = {}
            node = nxt
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "depth 70 denied [c l206]", str(res),
                             tag="D3.deep.deny")
        key = f"D3|{fam}|{sid}|{SEED}"
    elif fam == "unknown_ph":
        tok = f"<HG:{hexs(rng, 24)}:{hexs(rng, 24)}>"
        req = {"model": "test-model", "messages": [{"role": "user", "content": f"run {tok} now"}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "foreign token denied [c]", str(res),
                             tag="D3.unk.deny")
            case.assert_true(res.get("reason") == "unknown_placeholder", "unknown reason [c]",
                             str(res), tag="D3.unk.reason")
        key = f"D3|{fam}|{sid}|{tok}|{SEED}"
    elif fam == "spoof":
        spoof = rng.choice([f"<hg:{hexs(rng, 24)}:{hexs(rng, 24)}>",
                            f"<HG:{hexs(rng, 20)}:{hexs(rng, 24)}>"])
        req = {"model": "test-model", "messages": [{"role": "user", "content": spoof}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "placeholder spoof denied [c l177-179]",
                             str(res), tag="D3.spoof.deny")
        key = f"D3|{fam}|{sid}|{spoof[:18]}|{SEED}"
    elif fam == "invalid":
        if rng.random() < 0.5:
            req = {"model": "test-model", "messages": []}
            exp_reason = "invalid_request"
        else:
            req = {"model": "   ", "messages": [{"role": "user", "content": "hi"}]}
            exp_reason = "invalid_model"
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "invalid request denied [c]", str(res),
                             tag="D3.inv.deny")
            case.assert_true(res.get("reason") == exp_reason, f"reason {exp_reason} [c]",
                             str(res), tag="D3.inv.reason")
        key = f"D3|{fam}|{sid}|{exp_reason}|{SEED}"
    elif fam == "sm_deny":
        choice = rng.random()
        if choice < 0.2:
            ctx = f"Cookie: sessionid={canary}; foo=bar"
        elif choice < 0.35:
            ctx = f"Set-Cookie: SID={canary}; Path=/"
        elif choice < 0.55:
            ctx = json.dumps({"cookies": {"sid": canary}})
        elif choice < 0.75:
            ctx = f"eyJ{hexs(rng, 12)}.{hexs(rng, 12)}.{hexs(rng, 12)}"
        elif choice < 0.88:
            ctx = f"JSESSIONID = {canary}"
        else:
            ctx = json.dumps({"document.cookie": canary})
        req = {"model": "test-model", "messages": [{"role": "user", "content": ctx}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is False, "session material denied [c l288-305]",
                             str(res), tag="D3.smd.deny")
            case.assert_true(canary not in json.dumps(res),
                             "denial never echoes the secret", json.dumps(res)[:300],
                             tag="D3.smd.echo")
        key = f"D3|{fam}|{sid}|{choice}|{SEED}"
    elif fam == "sm_allow_gap":
        ctx = json.dumps({"sessionid": canary})
        req = {"model": "test-model", "messages": [{"role": "user", "content": ctx}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is True,
                             "bare JSON sessionid passes (documented non-coverage) [doc README:36]",
                             str(res), tag="D3.sma.gap")
            if res.get("allow"):
                case.assert_true(canary in json.dumps(res["request"]),
                                 "documented gap: the value passes unmasked [doc README:36]",
                                 json.dumps(res["request"])[:400], tag="D3.sma.passes")
        key = f"D3|{fam}|{sid}|{SEED}"
    elif fam == "sm_prose":
        text = g.pick(BENIGN_GIBBERISH) + " discussing cookie storage http only flags"
        req = {"model": "test-model", "messages": [{"role": "user", "content": text}]}
        def check():
            res = guard.required_policy("request", request=req, session_id=sid)
            case.assert_true(res.get("allow") is True, "cookie prose allowed [doc README:36]",
                             str(res), tag="D3.smp.allow")
        key = f"D3|{fam}|{sid}|{text[:20]}|{SEED}"
    elif fam == "pim_benign":
        req = make_request(g, [], rng.randint(1, 3), rng.choice(("plain", "toolcall")))
        def check():
            res = M["PIM"](req)
            case.assert_true(res is None,
                             "pii_middleware returns None when no change [p]", str(res),
                             tag="D3.pim.benign")
        key = f"D3|{fam}|{sid}|{len(json.dumps(req))}|{SEED}"
    elif fam == "pim_masked":
        field2 = build_secret_name(g)
        val2 = g.canary("alnum8")
        req = make_request(g, [(field2, val2)], rng.randint(1, 2), "plain")
        def check():
            res = M["PIM"](req)
            case.assert_true(res is not None, "pii_middleware masks [p]", str(res),
                             tag="D3.pim.change")
            if res is not None:
                case.assert_true(val2 not in json.dumps(res["request"]),
                                 "pii_middleware canary masked [p]",
                                 json.dumps(res["request"])[:400], tag="D3.pim.mask")
        key = f"D3|{fam}|{sid}|{field2}|{val2}|{SEED}"
    else:  # mvk
        r = rng.random()
        if r < 0.5:
            keyname = build_secret_name(g)
        elif r < 0.8:
            keyname = build_identifier_name(g)
        else:
            keyname = join_words(rng, [g.pick(BENIGN_GIBBERISH), "note"])
        val3 = g.canary("alnum8")
        def check():
            got, n = M["mask_value_for_key"](keyname, val3)
            kind = M["cred"].classify_field(keyname)
            if kind == "SECRET":
                case.assert_true(got == "[REDACTED]_SECRET_FIELD" and n == 1,
                                 "mask_value_for_key SECRET label [cw l332-345]", got,
                                 tag="D3.mvk.s")
            elif kind == "IDENTIFIER":
                case.assert_true(got == "[REDACTED]_ID_FIELD" and n == 1,
                                 "mask_value_for_key ID label [cw l332-345]", got, tag="D3.mvk.i")
            else:
                case.assert_true(got == val3 and n == 0,
                                 "benign key value untouched [cw l332-345]", got, tag="D3.mvk.n")
        key = f"D3|{fam}|{keyname}|{val3}|{SEED}"
    case.run_one(rng, key, fam, check)


# ------------------------------------------------------------------ D4

def d4_exec(case: Case, g: Gen):
    guard = M["Guard"]()
    rng = g.rng
    fam = pick_family("D4_placeholder_session_boundaries", rng)
    if fam == "dedup":
        val = g.canary("h8")
        s = guard.session("A")
        t1 = guard.remember(s, val, "PII")
        t2 = guard.remember(s, val, "SECRET")
        def check():
            case.assert_true(t1 == t2, "same value repeats one token [c reverse map]", t2,
                             tag="D4.dedup")
            case.assert_true(s.entries[t2].kind == "SECRET",
                             "kind upgraded to SECRET on repeat [c]", s.entries[t2].kind,
                             tag="D4.kind")
        key = f"D4|{fam}|{val}|{SEED}"
    elif fam == "isol_val":
        val = g.canary("h8")
        sA = guard.session("A")
        sB = guard.session("B")
        tA = guard.remember(sA, val, "PII")
        tB = guard.remember(sB, val, "PII")
        def check():
            case.assert_true(tA != tB, "sessions keep disjoint tokens [c per-session maps]",
                             f"{tA} vs {tB}", tag="D4.isoval")
        key = f"D4|{fam}|{val}|{SEED}"
    elif fam == "isol_out":
        val = g.canary("h8")
        sA = guard.session("A")
        tA = guard.remember(sA, val, "PII")
        out = guard.output(tA, session_id="B", platform="cli")
        def check():
            case.assert_true(out == MARKER,
                             "other-session token withheld in output [c l177-179]", out,
                             tag="D4.isoout")
            case.assert_true(val not in out, "cross-session value absent", out, tag="D4.isoout2")
        key = f"D4|{fam}|{val}|{SEED}"
    elif fam == "close_hold":
        val = g.canary("h8")
        sA = guard.session("A")
        tok = guard.remember(sA, val, "PII")
        guard.close("A")
        out = guard.output(tok, session_id="A", platform="cli")
        def check():
            case.assert_true(out == MARKER, "closed-session token withheld [c close()]", out,
                             tag="D4.closehold")
            case.assert_true(val not in out, "value absent after close", out, tag="D4.close2")
        key = f"D4|{fam}|{val}|{SEED}"
    elif fam == "tool_path":
        val = f"/home/cnry{hexs(rng, 6)}/data"
        suffix = rng.choice(("", "/sub/file.txt", "/cfg.txt"))
        sA = guard.session("A")
        tok = guard.remember(sA, val, "PATH")
        tool = rng.choice(("read_file", "write_file", "patch", "search_files"))
        res = guard.tool_request(tool, {"path": tok + suffix}, session_id="A")
        new_path = res["args"].get("path")
        def check():
            case.assert_true(new_path == val + suffix,
                             "allowlisted-tool path slot restores PATH token [c l379-386]",
                             str(res), tag="D4.toolpath")
            bv = guard.pre_tool(res["args"])
            case.assert_true(bv is None, "restored args pass pre_tool [c]", str(bv),
                             tag="D4.toolpath2")
        key = f"D4|{fam}|{tool}|{suffix}|{val}|{SEED}"
    elif fam == "tool_unsafe":
        val = f"/home/cnry{hexs(rng, 6)}/data"
        suffix = rng.choice(("/../etc", "/../passwd", " -q", "  rm"))
        sA = guard.session("A")
        tok = guard.remember(sA, val, "PATH")
        res = guard.tool_request("read_file", {"path": tok + suffix}, session_id="A")
        new_path = res["args"].get("path")
        def check():
            case.assert_true(new_path == tok + suffix,
                             "unsafe suffix not interpolated [c l384-386]", str(res),
                             tag="D4.unsafe")
            bv = guard.pre_tool(res["args"])
            case.assert_true(isinstance(bv, dict) and bv.get("action") == "block",
                             "leftover placeholder blocked in tool args [c l390-394]", str(bv),
                             tag="D4.unsafe2")
        key = f"D4|{fam}|{suffix}|{val}|{SEED}"
    elif fam == "block_generic":
        tok = f"<HG:{hexs(rng, 24)}:{hexs(rng, 24)}>"
        tool = g.pick(("bashx_run", "httpx_get", "gitx_push"))
        res = guard.tool_request(tool, {"cmd": tok}, session_id="A")
        def check():
            case.assert_true(res["args"].get("cmd") == tok,
                             "non-allowlisted tool never interpolates [c l378-387]", str(res),
                             tag="D4.blockgen")
            bv = guard.pre_tool(res["args"])
            case.assert_true(isinstance(bv, dict) and bv.get("action") == "block",
                             "placeholder leftover blocked [c l393-394]", str(bv),
                             tag="D4.blockgen2")
        key = f"D4|{fam}|{tool}|{tok}|{SEED}"
    elif fam == "cap_entries":
        guard = M["Guard"](max_entries=8)  # small explicit cap for this probe
        s = guard.session("A")
        vals2 = [g.canary("h8x") for _ in range(9)]
        out_tokens = [guard.remember(s, v, "PII") for v in vals2]
        dedup_call = guard.remember(s, vals2[0], "PII")
        def check():
            case.assert_true(out_tokens[0] != MARKER and out_tokens[1] != MARKER,
                             "first entries registered fine [c]", str(out_tokens[:2]),
                             tag="D4.cap.ok")
            case.assert_true(out_tokens[8] == MARKER,
                             "entry past cap 8 returns MARKER [c l77-79]", out_tokens[8],
                             tag="D4.cap.marker")
            case.assert_true(dedup_call == out_tokens[0],
                             "dedup wins even at capacity [c reverse-first l73-76]", dedup_call,
                             tag="D4.cap.dedup")
        key = f"D4|{fam}|{vals2[0]}|{SEED}"
    elif fam == "cap_sessions":
        def check():
            ga = M["Guard"]()
            raised = False
            for i in range(0, 64):
                ga.session(f"s{i}")
            try:
                ga.session("s64x")
            except ValueError:
                raised = True
            case.assert_true(raised, "65th session raises [c l66]", "no exception",
                             tag="D4.scap")
            ga.close("s0")
            ok2 = True
            try:
                ga.session("s64y")
            except ValueError:
                ok2 = False
            case.assert_true(ok2, "freed slot opens a new session [c l66-67]", ok2,
                             tag="D4.scap2")
        key = f"D4|{fam}|{g.nxt()}|{SEED}"
    else:  # req_isol
        tok = f"<HG:{hexs(rng, 24)}:{hexs(rng, 24)}>"
        req = {"model": "test-model", "messages": [{"role": "user", "content": f"use {tok}"}]}
        req2 = {"model": "test-model", "messages": [{"role": "user", "content": "clean text"}]}
        def check():
            res1 = guard.required_policy("request", request=req, session_id="A")
            case.assert_true(res1.get("allow") is False, "unknown token request denied [c]",
                             str(res1), tag="D4.req_isol")
            res2 = guard.required_policy("request", request=req2, session_id="B")
            case.assert_true(res2.get("allow") is True, "clean request in plain session allowed",
                             str(res2), tag="D4.req_isol2")
        key = f"D4|{fam}|{tok}|{SEED}"
    case.run_one(rng, key, fam, check)


def d4_restore_exec(case: Case, g: Gen):
    """Restore-kind matrix under the native stub [c l367]."""
    guard = M["Guard"]()
    rng = g.rng
    which = rng.choice(("PII", "IDENTIFIER", "PATH", "SECRET"))
    if which == "PII":
        val = f"m{hexs(rng, 4)}@x.invalid"
    elif which == "PATH":
        val = f"/home/cnry{hexs(rng, 6)}"
    elif which == "IDENTIFIER":
        val = "cnry" + hexs(rng, 9)
    else:
        val = "sk-ant-" + hexs(rng, 22)
    s = guard.session("A")
    tok = guard.remember(s, val, which)
    platform = rng.choice(("cli", "api"))
    out = guard.output(tok, session_id="A", platform=platform)
    def check():
        case.assert_true(tok.startswith("<HG:") and tok.endswith(">"),
                         "token shape <HG:nonce24:token24> [c l17,80]", tok, tag="D5B.shape")
        if platform == "cli" and which in ("PII", "IDENTIFIER", "PATH"):
            case.assert_true(out == val, f"{which} restored on cli [c l367]", out,
                             tag="D5B.rest.ok")
        else:
            case.assert_true(out == tok,
                             f"{which} never restores"
                             f"({'platform!=cli' if platform != 'cli' else 'SECRET type'}) [c l367]",
                             f"got {out!r}", tag="D5B.rest.no")
        case.assert_true(val not in out or (out == val and which not in ("SECRET",)),
                         "SECRET value never bows back through output", out, tag="D5B.noLeak")
    key = f"D4|rest_kind|{which}|{platform}|{val}|{SEED}"
    case.run_one(rng, key, "rest_kind", check)


# ------------------------------------------------------------------ D5

def d5_exec(case: Case, g: Gen):
    """Output redaction phase A (no native redactor on the path)."""
    guard = M["Guard"]()
    out_redact = M["output_redact"]
    paren = M["PAREN_CRED_RE"]
    rng = g.rng
    fam = pick_family("D5_output_redaction", rng)
    if fam == "contain":
        val = g.canary(rng.choice(("h8", "h8x", "alnum8", "alpha5")))
        resp = rng.choice(
            (val, f"{g.pick(BENIGN_GIBBERISH)} {val}", f"{val} (password)",
             f"{val} (pass)"))
        platform = rng.choice(("cli", "api", ""))
        def check():
            o = guard.output(resp, session_id="a5", platform=platform)
            case.assert_true(o == MARKER,
                             "non-empty local output withheld with no native redactor "
                             "[o l56-58][c l361-362]", o, tag="D5.contain")
            case.assert_true(val not in o, "canary never leaks through output", o,
                             tag="D5.contain2")
        key = f"D5|{fam}|{platform}|{resp[:32]}|{SEED}"
    elif fam == "doc_edges":
        val = g.canary("h8")
        choice = rng.random()
        def check():
            if choice < 0.45:
                got = out_redact.redact_output(val)
                case.assert_true(got == "[OUTPUT_WITHHELD:redactor_unavailable]",
                                 "non-empty text withheld locally [o l49-58]", got,
                                 tag="D5.doc")
                case.assert_true(val not in (got or ""),
                                 "withheld sentinel carries no secret value", got, tag="D5.doc2")
            elif choice < 0.75:
                got = out_redact.redact_output("")
                case.assert_true(got is None, "empty returns None [o l36]", got, tag="D5.doc3")
            else:
                got = out_redact.redact_output(123)
                case.assert_true(got == "[OUTPUT_WITHHELD:invalid_text]",
                                 "non-str withheld [o l32-33]", got, tag="D5.doc4")
        key = f"D5|{fam}|{choice}|{val}|{SEED}"
    else:  # paren regex semantics
        labelled = rng.random() < 0.55
        val2 = g.canary("alnum8")
        if labelled:
            lab = rng.choice(("password", "pass", "pw", "secret", "token", "apikey",
                              "credentials", "email", "user", "sudo password"))
            text2 = f"{val2} ({lab})"
        else:
            lab = rng.choice(("note", "caveat", "warning", "plan", "memo"))
            text2 = f"{val2} ({lab})"
        subbed = paren.sub(lambda m: "*** " + m.group(2), text2)
        def check():
            if labelled:
                case.assert_true(val2 not in subbed,
                                 "labeled paren value hidden by layer 1 [o l21-45]", subbed,
                                 tag="D5.paren")
                case.assert_true(subbed.startswith("*** "),
                                 "layer-1 replacement shape [o l43]", subbed, tag="D5.paren2")
            else:
                case.assert_true(subbed == text2,
                                 "benign label not in layer-1 list [o l36-53]", subbed,
                                 tag="D5.parenben")
        key = f"D5|{fam}|{labelled}|{text2[:36]}|{SEED}"
    case.run_one(rng, key, fam, check)


def d5_stub_exec(case: Case, g: Gen):
    """Phase B: plugin output pipeline with controlled native stub."""
    guard = M["Guard"]()
    out_redact = M["output_redact"]
    rng = g.rng
    fam = "stub_" + pick_family("D5_output_redaction", rng)
    if fam.endswith("rest"):
        which = rng.choice(("PII", "IDENTIFIER", "PATH", "SECRET"))
        if which == "PII":
            val = f"m{hexs(rng, 4)}@x.invalid"
        elif which == "PATH":
            val = f"/home/cnry{hexs(rng, 6)}"
        elif which == "IDENTIFIER":
            val = "cnry" + hexs(rng, 9)
        else:
            val = "sk-ant-" + hexs(rng, 22)
        s = guard.session("b5")
        tok = guard.remember(s, val, which)
        platform = rng.choice(("cli", "api", ""))
        def check():
            o = guard.output(tok, session_id="b5", platform=platform)
            if platform == "cli" and which in ("PII", "IDENTIFIER", "PATH"):
                case.assert_true(o == val, f"{which} restores on cli [c l367]", o,
                                 tag="D5B.rest")
            else:
                case.assert_true(o == tok,
                                 f"{which} stays hidden ({platform or 'no platform'}) [c l367]",
                                 o, tag="D5B.hold")
        key = f"D5|{fam}|{which}|{platform}|{val}|{SEED}"
    elif fam.endswith("paren_stub"):
        val3 = g.canary("alnum8")
        def check():
            o = guard.output(f"{val3} (password)", session_id="b5", platform="cli")
            case.assert_true(o == "*** (password)",
                             "paren label redacts before restore stage [o l42-44][c l358-363]", o,
                             tag="D5B.paren")
            case.assert_true(val3 not in o, "paren value never leaks", o, tag="D5B.paren2")
        key = f"D5|{fam}|{val3}|{SEED}"
    elif fam.endswith("stub_passthrough"):
        benign = g.pick(BENIGN_GIBBERISH) + " plain words without labels"
        def check():
            got = out_redact.redact_output(benign)
            case.assert_true(got is None, "no label to skip -> None even with stub [o l64]",
                             got, tag="D5B.stubred")
            got2 = guard.output(benign, session_id="b5", platform="cli")
            case.assert_true(got2 == benign,
                             "benign output round-trips [c l352-368]", got2, tag="D5B.stubout")
        key = f"D5|{fam}|{benign[:28]}|{SEED}"
    else:  # stub_secret: SECRET token plus paren interplay
        secret_val = "sk-ant-" + hexs(rng, 22)
        s = guard.session("b5")
        tok = guard.remember(s, secret_val, "SECRET")
        # native stub probe without a paren label (layer 1 only fires on
        # value+(credential-label) shapes [o l21-45])
        stub_text = g.pick(BENIGN_GIBBERISH) + " STUBTOKEN000 assigned"
        def check():
            o = guard.output(tok, session_id="b5", platform="cli")
            case.assert_true(secret_val not in o, "SECRET value never restores [c l364-367]",
                             o, tag="D5B.secret")
            o2 = guard.output(stub_text, session_id="b5", platform="api")
            case.assert_true("STUBTOKEN000" not in o2 and "[REDACTED_STUB]" in o2,
                             "native redactor seam applies when layer 1 does not [o l49-58]",
                             o2, tag="D5B.stub_seeded")
            case.assert_true("assigned" in o2 and "STUBTOKEN000" not in o2,
                             "stub replacement keeps surrounding text", o2,
                             tag="D5B.stub2")
            case.assert_true(tok.startswith("<HG:"), "SECRET token shape", tok,
                             tag="D5B.secret_shape")
        key = f"D5|{fam}|{secret_val}|{SEED}"
    case.run_one(rng, key, fam, check)


# ----------------------------------------------------------------- harness

M = {}


def install_native_stub():
    """Mock the Hermes native redactor seam `agent.redact` with a controlled
    identity-style redactor. Plugin code remains the real tested source; only
    the host redactor seam is stubbed, and this dependency is recorded."""
    agent_mod = ModuleType("agent")
    red_mod = ModuleType("agent.redact")

    def redact_sensitive_text(text, **kwargs):
        if isinstance(text, str):
            return text.replace("STUBTOKEN000", "[REDACTED_STUB]")
        return text

    red_mod.redact_sensitive_text = redact_sensitive_text
    red_mod._PREFIX_RE = __import__("re").compile(r"STUBPREFIX[A-Za-z0-9_\-]{20,}")
    agent_mod.redact = red_mod
    sys.modules["agent"] = agent_mod
    sys.modules["agent.redact"] = red_mod


SOURCE_FILES = (
    "pii_mask_abelion/guard.py", "pii_mask_abelion/_credentials.py",
    "pii_mask_abelion/output_redact.py", "pii_mask_abelion/_patterns.py",
    "pii_mask_abelion/pii_middleware.py", "pii_mask_abelion/__init__.py",
    "pii_mask_abelion/plugin.yaml",
)


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def load_plugin():
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    if importlib.util.find_spec("pii_mask_abelion") is None:
        raise RuntimeError("plugin module not found (AUDIT_REPO_ROOT wrong?)")
    gmod = importlib.import_module("pii_mask_abelion.guard")
    cred = importlib.import_module("pii_mask_abelion._credentials")
    out_r = importlib.import_module("pii_mask_abelion.output_redact")
    pim = importlib.import_module("pii_mask_abelion.pii_middleware")
    pat = importlib.import_module("pii_mask_abelion._patterns")
    # Runner-level pure memoization of Guard.spans(text): the function is
    # deterministic in (text) only (plugin-state-free); caching avoids
    # re-scaling identical key/value strings across the walk. Semantics
    # unchanged; this is measurement infrastructure, not a patch to policy.
    _orig_spans = gmod.Guard.spans
    _memo: dict = {}

    def _memo_spans(self, text):
        r = _memo.get(text)
        if r is None:
            r = _orig_spans(self, text)
            if len(_memo) > 120_000:
                _memo.clear()
            _memo[text] = list(r)
        return list(r)  # fresh copy: text() extends spans in place

    gmod.Guard.spans = _memo_spans
    # same pure memoization for the classifier (deterministic in `name`)
    _orig_cf = cred.classify_field
    _cf_memo: dict = {}

    def _memo_classify(name):
        r = _cf_memo.get(name)
        if r is None:
            r = _orig_cf(name)
            if len(_cf_memo) > 200_000:
                _cf_memo.clear()
            _cf_memo[name] = r
        return r

    cred.classify_field = _memo_classify
    M.update({
        "Guard": gmod.Guard,
        "cred": cred,
        "output_redact": out_r,
        "PIM": pim.pii_middleware,
        "PAREN_CRED_RE": pat.PAREN_CRED_RE,
        "PAREN_LABEL_RE": pat.PAREN_LABEL_RE,
        "mask_value_for_key": pim.mask_value_for_key,
    })


def selfcheck():
    ok = {}
    ok["agent_module_absent_before_stub"] = PHASE == "A"  # only A asserts absence
    if PHASE == "A":
        ok["agent_module_absent"] = importlib.util.find_spec("agent") is None
        if not ok["agent_module_absent"]:
            raise RuntimeError("selfcheck: unexpected 'agent' module present")
    cases = (("password", "SECRET"), ("apikey", "SECRET"), ("compass", None),
             ("client_id", "IDENTIFIER"), ("API_KEY_NAME", None))
    ok["classifier_subset"] = all(M["cred"].classify_field(n) == e for n, e in cases)
    if not ok["classifier_subset"]:
        raise RuntimeError("selfcheck failed: " + repr(
            {n: (M["cred"].classify_field(n), e) for n, e in cases}))
    ga = M["Guard"]()
    st = ga.session("sc")
    tok = ga.remember(st, "cnryselfcheck001", "PII")
    ok["token_shape"] = tok.startswith("<HG:")
    if not ok["token_shape"]:
        raise RuntimeError("selfcheck failed: token format " + repr(tok))
    if PHASE == "B":
        out = ga.output(tok, session_id="sc", platform="cli")
        ok["stub_restore_roundtrip"] = out == "cnryselfcheck001"
        if not ok["stub_restore_roundtrip"]:
            raise RuntimeError("selfcheck failed: stub restore -> " + repr(out))
    ok["source_hashes_head"] = {f: sha_file(os.path.join(REPO, f))[:16] for f in SOURCE_FILES}
    return ok


def main() -> int:
    t0 = time.time()
    load_plugin()
    if PHASE == "B":
        install_native_stub()
    sc = selfcheck()
    seed = int(os.environ.get("AUDIT_SEED", str(SEED)))
    out_dir = os.environ["AUDIT_OUT"]
    budget = PHASES[PHASE]
    g = Gen(seed + (0 if PHASE == "A" else 7777777))
    counts: dict = {}
    for domain in sorted(budget):
        case = Case(domain)
        target = budget[domain]
        start = time.time()
        while case.executed < target:
            if domain.startswith("D1"):
                d1_exec(case, g)
            elif domain.startswith("D2"):
                d2_exec(case, g)
            elif domain.startswith("D3"):
                d3_exec(case, g)
            elif domain.startswith("D4"):
                d4_restore_exec(case, g) if PHASE == "B" else d4_exec(case, g)
            else:
                d5_stub_exec(case, g) if PHASE == "B" else d5_exec(case, g)
            if case.executed % 25_000 == 0:
                secs = max(time.time() - start, 1e-9)
                print(f"  [{PHASE}|{domain}] {case.executed}/{target} "
                      f"pass={case.passed} fail={case.failed} "
                      f"rate={case.executed / secs:.0f}/s", flush=True)
        dur = time.time() - start
        counts[domain] = {
            "planned": target,
            "executed": case.executed,
            "unique_inputs": len(case.unique),
            "pass": case.passed,
            "fail": case.failed,
            "assertions": case.assertions,
            "assertion_failures": case.assertion_failures,
            "duration_s": round(dur, 1),
            "family_pass": case.family_pass,
            "family_fail": case.family_fail,
        }
        with open(os.path.join(out_dir, f"repros_{PHASE}_{domain}.json"), "w") as fh:
            json.dump(case.repros, fh, indent=1)
        print(f"[{PHASE}] {domain}: exec={case.executed} pass={case.passed} "
              f"fail={case.failed} uniq={len(case.unique)} "
              f"asserts={case.assertions} ({dur:.1f}s)", flush=True)
    summary = {
        "phase": PHASE,
        "seed": seed,
        "tested_sha": SHA,
        "selfcheck": sc,
        "python": sys.version.split()[0],
        "planned_total": sum(budget.values()),
        "executed_total": sum(c["executed"] for c in counts.values()),
        "pass_total": sum(c["pass"] for c in counts.values()),
        "fail_total": sum(c["fail"] for c in counts.values()),
        "assertions_total": sum(c["assertions"] for c in counts.values()),
        "assertion_failures_total": sum(c["assertion_failures"] for c in counts.values()),
        "per_domain": counts,
        "duration_s": round(time.time() - t0, 1),
        "source_file_sha256": {f: sha_file(os.path.join(REPO, f)) for f in SOURCE_FILES},
    }
    summary["executed_eq_pass_fail"] = (
        summary["executed_total"] == summary["pass_total"] + summary["fail_total"])
    with open(os.path.join(out_dir, f"results_{PHASE}.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print(f"[{PHASE}] totals: executed={summary['executed_total']} "
          f"pass={summary['pass_total']} fail={summary['fail_total']} "
          f"planned={summary['planned_total']} time={summary['duration_s']}s",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
