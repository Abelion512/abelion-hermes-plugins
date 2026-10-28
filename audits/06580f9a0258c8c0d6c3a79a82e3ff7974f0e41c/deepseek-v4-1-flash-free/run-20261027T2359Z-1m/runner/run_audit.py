#!/usr/bin/env python3
"""Independent Privacy Guard audit corpus: 1,000,000 deterministic executions.

Pinned source: abelion-hermes-plugins @ 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c
Source is read-only here: this runner imports pii_mask_abelion as shipped at that SHA.

Design notes
------------
* Every case index i maps deterministically to (parameters) -> input. No shared
  mutable state between cases except the per-domain counters, so cases are
  independent and the split across worker processes cannot change results.
* Expectations come from the documented contract at that SHA:
    - pii_mask_abelion/_credentials.py module docstring (name normalisation,
      "a segment (or segment pair such as api + key) says so", value-only masking)
    - the _NOT_SECRET / _NOT_VALUE_LAST / _NOT_VALUE_ANY / _COUNTER_PREV /
      _KEY_PREFIX / _ID_PAIRS vocabulary documented in that file
    - pii_mask_abelion/README.md (required mode masks whole request; credentials
      never restore; CLI may restore known exact PII/path tokens; media/binary
      denied; JSON tool arguments walked)
    - pii_mask_abelion/docs/VALIDATION.md (invalid input denies, never coerced)
    - pii_mask_abelion/guard.py comments for placeholder/session rules
  The oracle in this file was written from those statements BEFORE the full run.
  It is not derived by calling the implementation. Where the documentation does
  not decide an outcome, the case is skipped as AMBIGUOUS (counted separately).
* No network, no provider, no real secret. Every value is a synthetic canary.
* agent.redact is NOT installed in the audit environment. Domain D5 therefore
  (a) exercises the documented "redactor unavailable" path against the real
  environment first, and (b) exercises the surrounding logic with an in-memory
  test double installed in sys.modules. The double is never native Hermes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import platform
import random
import re
import sys
import time
import types
from pathlib import Path

SEED = 20261028
SHA = "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c"
DOMAIN_PLAN = {
    "D1_field_classification": 250_000,
    "D2_benign_name_false_positive": 150_000,
    "D3_request_nested_masking": 250_000,
    "D4_placeholder_session_boundary": 150_000,
    "D5_output_redaction": 100_000,
    "D6_case_fix_regression": 100_000,
}

REPO = ""
_INIT = False
_C = _Guard = _MARKER = _TOKEN = _OR = _PM = _PARENT = None


# ─────────────────────────── helpers ────────────────────────────
def fp(*parts) -> int:
    h = hashlib.blake2b(digest_size=8)
    for p in parts:
        h.update(repr(p).encode("utf-8", "surrogatepass"))
        h.update(b"\x1f")
    return int.from_bytes(h.digest(), "big")


class Agg:
    def __init__(self, domain: str):
        self.domain = domain
        self.executed = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.assertions = 0
        self.fps = set()
        self.rules: dict[str, int] = {}
        self.samples: dict[str, list] = {}

    def skip(self, reason: str, sample=None):
        self.skipped += 1
        self.rules["skip:" + reason] = self.rules.get("skip:" + reason, 0) + 1
        if sample is not None and len(self.samples.setdefault("skip:" + reason, [])) < 3:
            self.samples["skip:" + reason].append(sample)

    def case(self, checks: list, fpv: int):
        """checks: list of (ok: bool, rule: str, detail). One case = one execution."""
        self.fps.add(fpv)
        self.executed += 1
        self.assertions += len(checks)
        failed = False
        for ok, rule, detail in checks:
            if not ok:
                failed = True
                self.rules[rule] = self.rules.get(rule, 0) + 1
                if len(self.samples.setdefault(rule, [])) < 6:
                    self.samples[rule].append(detail)
        if failed:
            self.failed += 1
        else:
            self.passed += 1

    def pack(self):
        return {
            "domain": self.domain,
            "executed": self.executed,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "assertions": self.assertions,
            "unique_inputs": len(self.fps),
            "rules": self.rules,
            "samples": self.samples,
            "_fps": list(self.fps),
        }


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=repr)


# ─────────────────── contract vocabulary (oracle) ───────────────────
SECRET_WORDS = {
    "pass", "passw", "passwd", "password", "passwords", "pwd", "passphrase",
    "token", "secret", "secrets", "credential", "credentials",
    "apikey", "accesskey", "privatekey", "secretkey", "authkey", "bearer",
}
NOT_SECRET = {"bypass", "compass", "surpass", "trespass", "overpass",
              "underpass", "tokenizer", "tokenize", "secretary", "mypass"}
KEY_PREFIX = {"api", "secret", "private", "access", "service", "role", "auth",
              "encryption", "signing", "license", "master", "ssh", "webhook"}
ID_PAIRS = {("client", "id"), ("app", "id"), ("public", "key"), ("account", "sid")}
NOT_VALUE_LAST = {"path", "file", "filename", "dir", "folder", "name", "label",
                  "type", "env", "var", "header", "field", "prefix", "location",
                  "policy", "mode", "format", "kind", "length", "len", "count",
                  "limit", "usage", "ttl", "expires", "expiry", "required",
                  "enabled", "hint", "manager", "page", "wiki", "docs", "doc"}
NOT_VALUE_ANY = {"count", "limit", "usage", "ttl", "expires", "expiry", "path", "file"}
COUNTER_PREV = {"max", "min", "num", "total", "input", "output", "completion",
                "prompt", "cache", "reasoning", "n"}
TAIL_OK = {"key", "value", "val", "str", "string", "text", "hex", "raw", "plain",
           "v1", "v2", "primary", "secondary"}
LABEL_WORDS = {"username", "user_name", "email", "phone", "address", "alamat",
               "nik", "ktp", "npwp"}


def expect_kind(parts: list[str]) -> str | None:
    """Documented classification for an unambiguous part sequence."""
    if not parts:
        return None
    if parts[-1] not in NOT_VALUE_LAST and not (set(parts) & NOT_VALUE_ANY):
        if any(a == "api" and b == "key" for a, b in zip(parts, parts[1:])):
            return "SECRET"
    if parts[-1] in NOT_VALUE_LAST or (set(parts) & NOT_VALUE_ANY):
        return None
    for i, seg in enumerate(parts):
        if seg in NOT_SECRET:
            continue
        if seg in SECRET_WORDS:
            if i and parts[i - 1] in COUNTER_PREV and seg == "token":
                continue
            if all(t in TAIL_OK or t.isdigit() for t in parts[i + 1:]):
                return "SECRET"
        if seg == "key" and i and (set(parts[:i]) & KEY_PREFIX):
            return "SECRET"
        if i and (parts[i - 1], seg) in ID_PAIRS:
            return "IDENTIFIER"
        if seg == "email" and len(parts) > 1:
            return "IDENTIFIER"
    return None


# ─────────────────────────── domain D1 ───────────────────────────
# Compound cores are kept as *semantic parts* so the oracle never re-parses text.
D1_CORES = [
    ("password",), ("passwd",), ("pwd",), ("passphrase",), ("pass",),
    ("secret",), ("credential",), ("api", "key"), ("apikey",), ("access", "key"),
    ("private", "key"), ("secret", "key"), ("auth", "key"), ("bearer",), ("token",),
    ("client", "secret"), ("db", "password"), ("user", "token"),
    ("client", "id"), ("app", "id"), ("public", "key"), ("account", "sid"),
    ("lms", "email"),
    ("compass",), ("bypass",), ("tokenizer",), ("secretary",), ("mypass",),
    ("key",), ("email",), ("model",),
]
D1_PREFIX = ["db", "app", "user", "myco", "acme", "svc", "web", "prod", "edge",
             "core", "demo", "team", "org", "net", "ops", "lab", "qa", "eu"]
D1_SUFFIX = ["", "value", "val", "str", "text", "hex", "raw", "plain", "primary",
             "secondary", "key", "v1", "v2", "string",
             "name", "path", "file", "filename", "dir", "folder", "label", "type",
             "env", "var", "header", "field", "prefix", "location", "policy",
             "mode", "format", "kind", "length", "count", "limit", "usage", "ttl",
             "expiry", "required", "enabled", "hint", "manager", "page", "wiki",
             "docs", "doc"]
D1_TAIL2 = ["", "v1", "raw", "primary", "hex"]
CASE_STYLES = ["lower", "upper", "capital", "swap", "alt"]
SEP_STYLES = ["_", "-", "."]


def restyle(s: str, style: str) -> str:
    if style == "lower":
        return s.lower()
    if style == "upper":
        return s.upper()
    if style == "capital":
        return s.capitalize()
    if style == "swap":
        return s.swapcase()
    return "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(s))


def build_name(parts: list[str], sep: str, style: str) -> str:
    if sep == "camel":
        joined = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    else:
        joined = sep.join(parts)
    return restyle(joined, style)


def d1(i: int, agg: Agg):
    idx = i
    core = D1_CORES[i % len(D1_CORES)]
    i //= len(D1_CORES)
    pre = D1_PREFIX[i % len(D1_PREFIX)]
    i //= len(D1_PREFIX)
    suf = D1_SUFFIX[i % len(D1_SUFFIX)]
    i //= len(D1_SUFFIX)
    tail2 = D1_TAIL2[i % len(D1_TAIL2)]
    i //= len(D1_TAIL2)
    style = CASE_STYLES[i % len(CASE_STYLES)]
    i //= len(CASE_STYLES)
    sep = SEP_STYLES[i % len(SEP_STYLES)]
    i //= len(SEP_STYLES)
    variant = i  # extra variation axis, keeps indices injective for the planned range

    parts = [pre, *core]
    if suf:
        parts.append(suf)
    if tail2:
        parts.append(tail2)
    if variant % 3 == 1 and core not in (("compass",), ("bypass",),):
        parts = core[:]  # prefix-less form
    name = build_name(parts, sep, style)
    expected = expect_kind(parts)
    if expected is None and any(p in LABEL_WORDS for p in parts):
        agg.skip("label_word_out_of_scope", name)
        return
    got = _C.classify_field(name)
    agg.case(
        [(got == expected, "classify_mismatch", {"name": name, "parts": parts,
                                                 "expected": expected, "actual": got})],
        fp("D1", name),
    )


# ─────────────────────────── domain D2 ───────────────────────────
D2_WORDS = ["compass", "bypass", "surpass", "trespass", "overpass", "underpass",
            "tokenizer", "tokenize", "secretary", "mypass", "keyboard", "monkey",
            "turkey", "hockey", "jockey", "keynote", "donkey", "passenger",
            "passport", "passage", "key", "model", "content", "project", "region",
            "topic", "summary", "city", "note", "title", "unit", "channel", "vendor",
            "version", "build", "image", "runtime", "backend", "endpoint"]
D2_SUFFIX = ["name", "path", "file", "type", "count", "limit", "usage", "ttl",
             "policy", "mode", "format", "kind"]
D2_FORMS = ["assign_eq", "assign_colon", "json", "flag", "header"]


def d2(i: int, agg: Agg):
    idx = i
    word = D2_WORDS[i % len(D2_WORDS)]
    i //= len(D2_WORDS)
    pre = D1_PREFIX[i % len(D1_PREFIX)]
    i //= len(D1_PREFIX)
    suf = D2_SUFFIX[i % len(D2_SUFFIX)]
    i //= len(D2_SUFFIX)
    style = CASE_STYLES[i % len(CASE_STYLES)]
    i //= len(CASE_STYLES)
    form = D2_FORMS[i % len(D2_FORMS)]
    i //= len(D2_FORMS)
    variant = i

    parts = [pre, word] + ([suf] if suf else [])
    if variant % 4 == 0:
        parts = [word] + ([suf] if suf else [])
    name = build_name(parts, ["_", "-", "camel"][variant % 3], style)
    if expect_kind(parts) is not None:
        agg.skip("ambiguous_for_negative_domain", name)
        return
    if any(p in LABEL_WORDS for p in parts):
        agg.skip("label_word_out_of_scope", name)
        return
    canary = f"SyntheticBenign{idx:05d}Qq"
    texts = {
        "assign_eq": f"{name}={canary}",
        "assign_colon": f"{name}: {canary}",
        "json": json.dumps({name: canary}),
        "flag": f"--{name} {canary}",
        "header": f"{name}: {canary}\n",
    }
    text = texts[form]
    kind = _C.classify_field(name)
    masked_cred, _ = _C.mask_credentials(text)
    g = _Guard()
    guarded = g.text(text, g.session("d2"))
    checks = [
        (kind is None, "benign_classified_sensitive",
         {"name": name, "actual": kind}),
        (canary in masked_cred and masked_cred == text, "benign_value_masked_by_mask_credentials",
         {"name": name, "text": text, "out": masked_cred}),
        (canary in guarded, "benign_value_masked_by_guard_text",
         {"name": name, "text": text, "out": guarded}),
    ]
    agg.case(checks, fp("D2", name, form, canary))


# ─────────────────────────── domain D3 ───────────────────────────
D3_SENS_KEYS = ["api_key", "password", "db_password", "clientSecret", "access_token",
                "HF_TOKEN", "refreshToken", "secretKeyValue", "account_sid",
                "clientId", "user_email", "PAYMENT_TOKEN", "Authorization"]
D3_BENIGN_KEYS = ["project", "region", "topic", "summary", "city", "note",
                  "title", "unit", "channel", "vendor"]
D3_DEPTHS = [1, 2, 3, 5, 8, 30, 70]
D3_FORMS = ["meta_dict", "tool_arguments", "content_text", "tool_result_json", "headers"]


def nest(key: str, value: str, depth: int):
    node = {key: value}
    for d in range(depth - 1):
        node = {"level": [node]} if d % 2 else {"nest": node}
    return node


def d3_key(key0: str, sep: str, style: str) -> str:
    parts = key0.split("_")
    if sep == "camel":
        s = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    elif sep == "-":
        s = "-".join(parts)
    else:
        s = "_".join(parts)
    return restyle(s, style)


def d3(i: int, agg: Agg):
    idx = i
    depth = D3_DEPTHS[i % len(D3_DEPTHS)]
    i //= len(D3_DEPTHS)
    form = D3_FORMS[i % len(D3_FORMS)]
    i //= len(D3_FORMS)
    sens = (i % 3) != 0
    keys = D3_SENS_KEYS if sens else D3_BENIGN_KEYS
    key0 = keys[i % len(keys)]
    i //= len(keys)
    style = CASE_STYLES[i % len(CASE_STYLES)]
    i //= len(CASE_STYLES)
    sep = ["_", "-", "camel"][i % 3]
    i //= 3
    engine = ["guard", "legacy"][i % 2]
    i //= 2
    variant = i

    key = d3_key(key0, sep, style)

    canary = f"SynCanary{idx:06d}Zq"
    benign = f"SyntheticBenign{idx:06d}Qq"
    value = canary if sens else benign

    if form == "meta_dict":
        request = {"model": "audit-model", "messages": [{"role": "user", "content": "hello"}],
                   "meta": nest(key, value, depth)}
    elif form == "tool_arguments":
        request = {"model": "audit-model", "messages": [{"role": "assistant", "content": None,
                   "tool_calls": [{"id": "call_1", "type": "function",
                                   "function": {"name": "lookup", "arguments": json.dumps(nest(key, value, depth))}}]}]}
    elif form == "content_text":
        request = {"model": "audit-model",
                   "messages": [{"role": "user", "content": f"{key}: {value} tail"}]}
    elif form == "tool_result_json":
        request = {"model": "audit-model",
                   "messages": [{"role": "tool", "tool_call_id": "c1",
                                 "content": json.dumps({"name": key, "value": value})}]}
    else:
        request = {"model": "audit-model", "messages": [{"role": "user", "content": "hello"}],
                   "headers": {key: value}}

    before = json.loads(json.dumps(request))
    denied = False
    if engine == "guard":
        res = _Guard().required_policy("request", request=request, session_id=f"d3-{idx}")
        out = json.dumps(res.get("request", res), ensure_ascii=False)
        denied = not res.get("allow")
    else:
        res = _PM.pii_middleware(request)
        out = json.dumps(res, ensure_ascii=False) if res is not None else json.dumps(request)
        denied = False

    checks = [
        (denied or (canary not in out), "sensitive_value_forwarded",
         {"engine": engine, "form": form, "key": key, "depth": depth}),
        (request == before, "input_mutated", {"engine": engine, "form": form}),
        (_is_json(out), "output_not_json", {"form": form}),
    ]
    if not sens and not denied:
        checks.append((benign in out, "benign_value_overmasked",
                       {"engine": engine, "form": form, "key": key}))
    if engine == "guard" and not denied:
        parsed = json.loads(out) if _is_json(out) else {}
        checks.append((parsed.get("model") == "audit-model", "control_field_changed",
                       {"form": form, "out_model": parsed.get("model")}))
    agg.case(checks, fp("D3", engine, form, key, depth, value))


def _is_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except Exception:
        return False


# ─────────────────────────── domain D4 ───────────────────────────
D4_KINDS = ["SECRET", "PII", "PATH", "IDENTIFIER"]
D4_PLATFORMS = ["cli", "api", "", "gateway"]
D4_RELATIONS = ["same", "foreign", "closed", "same_after_other"]
D4_ACTIONS = ["output", "required_policy", "tool_request", "text_reoccurrence"]
D4_MUT_BY_ACTION = {
    "output": ["exact", "upper", "one_char"],
    "required_policy": ["exact", "upper", "one_char"],
    "tool_request": ["exact", "wrapped_word", "one_char"],
    "text_reoccurrence": ["exact"],
}
TOOLS = ["read_file", "write_file", "patch", "search_files", "terminal", "http_fetch"]


def d4(i: int, agg: Agg):
    idx = i
    kind = D4_KINDS[i % len(D4_KINDS)]
    i //= len(D4_KINDS)
    plat = D4_PLATFORMS[i % len(D4_PLATFORMS)]
    i //= len(D4_PLATFORMS)
    rel = D4_RELATIONS[i % len(D4_RELATIONS)]
    i //= len(D4_RELATIONS)
    action = D4_ACTIONS[i % len(D4_ACTIONS)]
    i //= len(D4_ACTIONS)
    muts = D4_MUT_BY_ACTION[action]
    mut = muts[i % len(muts)]
    i //= len(muts)
    tool = TOOLS[i % len(TOOLS)]
    i //= len(TOOLS)
    variant = i

    value = {
        "SECRET": f"SyntheticSecret{idx:07d}Xq",
        "PII": f"user{idx:05d}@example.test",
        "PATH": f"/srv/synthetic{idx:05d}/project",
        "IDENTIFIER": f"acct_{idx:07d}",
    }[kind] + ("" if variant % 5 else "/extra")
    g = _Guard()
    sid = f"s{idx}"
    s = g.session(sid)
    tok = g.remember(s, value, kind)

    if mut == "upper":
        token = tok.upper()
    elif mut == "one_char":
        c = "a" if tok[-2] != "a" else "b"
        token = tok[:-2] + c + ">"
    elif mut == "wrapped_word":
        token = "pre" + tok + "post"
    else:
        token = tok

    foreign = None
    if rel in ("foreign", "same_after_other"):
        fg = _Guard()
        fs = fg.session("other")
        foreign = fg.remember(fs, value, kind)

    if action == "output":
        # The audit host has no native agent.redact. Identity double isolates the
        # plugin's own restore/mask ordering; it is NOT native Hermes behaviour.
        _install_mock("identity")
        if rel == "closed":
            g.close(sid)
        use = token if rel != "foreign" else foreign
        got = g.output(use, session_id=sid, platform=plat)
        if kind == "SECRET":
            ok = value not in got
            rule = "secret_restored"
        elif rel in ("foreign", "closed") or mut != "exact" or plat != "cli":
            ok = value not in got
            rule = "non_restorable_value_present"
        else:
            ok = value in got
            rule = "pii_not_restored_on_cli"
        agg.case([(ok, rule, {"kind": kind, "plat": plat, "rel": rel, "mut": mut,
                              "got": got[:80]})],
                 fp("D4o", kind, plat, rel, mut, action, variant, value))
        return

    if action == "required_policy":
        use = foreign if rel == "foreign" else token
        request = {"model": "m", "messages": [{"role": "user", "content": f"note {use} end"}]}
        res = g.required_policy("request", request=request, session_id=sid)
        if rel == "foreign":
            ok = res.get("allow") is False and res.get("reason") == "unknown_placeholder"
            rule = "foreign_token_not_denied"
        elif mut != "exact" or rel == "closed":
            ok = res.get("allow") is False or value not in json.dumps(res)
            rule = "mutated_token_not_rejected"
        else:
            ok = res.get("allow") is True and tok in json.dumps(res)
            rule = "known_token_not_preserved"
        agg.case([(ok, rule, {"rel": rel, "mut": mut, "res": str(res)[:120]})],
                 fp("D4p", rel, mut, action, variant, value))
        return

    if action == "tool_request":
        args = {"path": token}
        out = g.tool_request(tool, args, session_id=sid)
        got = out.get("args", {}).get("path")
        restorable_tool = tool in {"read_file", "write_file", "patch", "search_files"}
        if kind == "PATH" and mut == "exact" and restorable_tool:
            ok = got == value
            rule = "known_path_not_restored"
        else:
            ok = got == token and value not in json.dumps(out)
            rule = "unexpected_restore"
        agg.case([(ok, rule, {"kind": kind, "tool": tool, "mut": mut, "got": str(got)[:90]})],
                 fp("D4t", kind, tool, mut, action, variant, value))
        return

    # text_reoccurrence: a known literal is masked when it reappears without a label
    g2 = _Guard()
    s2 = g2.session("t")
    tok2 = g2.remember(s2, value, kind)
    text = f"before {value} after"
    out = g2.text(text, s2)
    if len(value) < 4:
        ok = value in out
        rule = "short_literal_masked"
    else:
        ok = value not in out
        rule = "known_literal_forwarded"
    agg.case([(ok, rule, {"kind": kind, "len": len(value), "out": out[:90]})],
             fp("D4r", kind, action, variant, value))


# ─────────────────────────── domain D5 ───────────────────────────
D5_LABELS = ["password", "pass", "pw", "secret", "secrets", "credential",
             "credentials", "token", "apikey", "email", "user", "username",
             "app email", "app-password", "pass email", "client id",
             "client secret", "api key", "api-secret", "auth", "auth token",
             "webhook secret", "sudo password", "apppass"]
D5_WORD_COUNTS = [1, 2, 3, 4, 5, 6]
D5_SPACING = ["({})", "( {} )", "(  {}  )"]
D5_SUBS = ["unavailable", "paren", "non_paren_label", "restore", "error"]


def _install_mock(mode: str):
    mod = types.ModuleType("agent")
    mod.__path__ = []
    rmod = types.ModuleType("agent.redact")
    if mode == "identity":
        rmod.redact_sensitive_text = lambda t: t
    elif mode == "raise":
        def _boom(t):
            raise RuntimeError("synthetic redactor failure")
        rmod.redact_sensitive_text = _boom
    elif mode == "none":
        rmod.redact_sensitive_text = lambda t: None
    elif mode == "int":
        rmod.redact_sensitive_text = lambda t: 7
    elif mode == "strip":
        rmod.redact_sensitive_text = lambda t: re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[REDACTED_EMAIL]", t)
    rmod._PREFIX_RE = re.compile(r"(?!x)x")
    mod.redact = rmod
    sys.modules["agent"] = mod
    sys.modules["agent.redact"] = rmod


def _remove_mock():
    sys.modules.pop("agent.redact", None)
    sys.modules.pop("agent", None)


def d5(i: int, agg: Agg):
    idx = i
    sub = D5_SUBS[i % len(D5_SUBS)]
    i //= len(D5_SUBS)
    label = D5_LABELS[i % len(D5_LABELS)]
    i //= len(D5_LABELS)
    wc = D5_WORD_COUNTS[i % len(D5_WORD_COUNTS)]
    i //= len(D5_WORD_COUNTS)
    spacing = D5_SPACING[i % len(D5_SPACING)]
    i //= len(D5_SPACING)
    style = CASE_STYLES[i % len(CASE_STYLES)]
    i //= len(CASE_STYLES)
    variant = i
    canary = f"SyntheticProse{idx:06d}Zq"
    words = " ".join(f"w{k}" for k in range(wc))
    lb = restyle(label, style)

    if sub == "unavailable":
        _remove_mock()
        text = f"{words} {canary} {spacing.format(lb)} tail"
        direct = _OR.redact_output(text)
        g = _Guard()
        got = g.output(text, session_id=f"u{i}", platform="cli")
        agg.case([
            (direct == "[OUTPUT_WITHHELD:redactor_unavailable]", "unavailable_not_withheld",
             {"direct": direct}),
            (got == _MARKER, "guard_output_not_withheld_when_redactor_missing", {"got": got[:80]}),
        ], fp("D5a", text, variant))
        return

    if sub == "paren":
        _install_mock("identity")
        text = f"{words} {canary} {spacing.format(lb)} tail"
        got = _OR.redact_output(text)
        ok = got is not None and canary not in got and "***" in got and lb in got
        agg.case([(ok, "paren_credential_not_masked",
                   {"text": text, "out": None if got is None else got[:100]})],
                 fp("D5b", text))
        return

    if sub == "non_paren_label":
        _install_mock("identity")
        other = ["note", "info", "version", "summary", "owner"][variant % 5]
        text = f"{words} {canary} ({restyle(other, style)}) tail"
        got = _OR.redact_output(text)
        agg.case([(got is None, "benign_parenthetical_masked",
                   {"text": text, "out": got})], fp("D5c", text))
        return

    if sub == "restore":
        _install_mock("identity")
        g = _Guard()
        s = g.session(f"r{i}")
        kind = ["PII", "SECRET", "PATH"][variant % 3]
        raw = {"PII": f"user{idx:05d}@example.test", "SECRET": f"SyntheticSecret{i:06d}Xq",
               "PATH": f"/srv/synthetic{i:05d}/dir"}[kind]
        tok = g.remember(s, raw, kind)
        text = f"{spacing.format(lb)} {tok} tail"
        got = g.output(text, session_id=f"r{i}", platform="cli")
        if kind == "SECRET":
            ok = raw not in got
            rule = "secret_restored_in_output"
        else:
            ok = raw in got
            rule = "cli_pii_not_restored_after_redaction"
        agg.case([(ok, rule, {"kind": kind, "got": got[:100]})],
                 fp("D5d", kind, text, raw))
        return

    # error modes
    mode = ["raise", "none", "int", "strip"][variant % 4]
    _install_mock(mode)
    text = f"{words} {canary} {spacing.format(lb)} tail"
    g = _Guard()
    got = g.output(text, session_id=f"e{i}", platform="cli")
    if mode == "strip":
        ok = canary in got
        rule = "good_redactor_output_dropped"
    else:
        ok = got == _MARKER
        rule = "redactor_error_not_withheld"
    agg.case([(ok, rule, {"mode": mode, "got": str(got)[:80]})],
             fp("D5e", mode, text, variant))
    _install_mock("identity")


# ─────────────────────────── domain D6 ───────────────────────────
D6_VARIANTS = ["lower", "upper", "swap", "alt"]


def d6(i: int, agg: Agg):
    idx = i
    pool = D1_CORES if i % 2 == 0 else [tuple([w]) for w in D2_WORDS]
    core = pool[(i // 2) % len(pool)]
    i //= 2 * len(pool)
    pre = D1_PREFIX[i % len(D1_PREFIX)]
    i //= len(D1_PREFIX)
    suf = D1_SUFFIX[i % len(D1_SUFFIX)]
    i //= len(D1_SUFFIX)
    sep = ["_", "-", "camel"][i % 3]
    i //= 3
    tail2 = D1_TAIL2[i % len(D1_TAIL2)]
    i //= len(D1_TAIL2)
    variant = i

    parts = [pre, *core] + ([suf] if suf else []) + ([tail2] if tail2 else [])
    if variant % 4 == 0:
        parts = list(core) + ([suf] if suf else []) + ([tail2] if tail2 else [])
    name = build_name(parts, sep, "lower")
    variants = [restyle(name, s) for s in D6_VARIANTS]
    parent_results = {_PARENT.classify_field(v) for v in variants}
    head_results = {_C.classify_field(v) for v in variants}
    if len(parent_results) == 1:
        expected = next(iter(parent_results))
        got = _C.classify_field(name)
        agg.case([(got == expected, "semantic_drift_after_case_fix",
                   {"name": name, "parent": expected, "head": got})],
                 fp("D6", "stable", name))
    else:
        agg.case([(len(head_results) == 1, "case_variance_remains",
                   {"name": name, "head": sorted(map(str, head_results))})],
                 fp("D6", "unstable", name))


# ─────────────────────────── runner plumbing ───────────────────────────
DOMAINS = {
    "D1_field_classification": d1,
    "D2_benign_name_false_positive": d2,
    "D3_request_nested_masking": d3,
    "D4_placeholder_session_boundary": d4,
    "D5_output_redaction": d5,
    "D6_case_fix_regression": d6,
}


def init_worker(repo: str, parent_path: str):
    global REPO, _INIT, _C, _Guard, _MARKER, _TOKEN, _OR, _PM, _PARENT
    if _INIT:
        return
    _INIT = True
    REPO = repo
    sys.path.insert(0, repo)
    from pii_mask_abelion import _credentials as C
    from pii_mask_abelion import guard as G
    from pii_mask_abelion import output_redact as OR
    from pii_mask_abelion import pii_middleware as PM
    _C, _Guard, _MARKER, _TOKEN, _OR, _PM = C, G.Guard, G.MARKER, G.TOKEN, OR, PM
    spec = importlib.util.spec_from_file_location("parent_credentials", parent_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _PARENT = mod


def run_slice(args):
    domain, start, end, repo, parent_path = args
    init_worker(repo, parent_path)
    fn = DOMAINS[domain]
    agg = Agg(domain)
    for i in range(start, end):
        try:
            fn(i, agg)
        except Exception as exc:  # harness-visible failure, never hidden
            agg.case([(False, "case_exception", {"index": i, "error": type(exc).__name__ + ": " + str(exc)[:160]})],
                     fp(domain, "exc", i))
    return agg.pack()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--parent", required=True, help="parent-commit _credentials.py for D6")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--scale", type=float, default=1.0, help="debug only: fraction of each domain")
    args = ap.parse_args()

    started = time.time()
    utc_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    plan = {k: int(v * args.scale) for k, v in DOMAIN_PLAN.items()}
    tasks = []
    for domain, n in plan.items():
        if n == 0:
            continue
        # contiguous slices preserve the deterministic index->case mapping
        chunk = max(1, n // (args.workers * 2))
        cur = 0
        while cur < n:
            end = min(n, cur + chunk)
            tasks.append((domain, cur, end, args.repo, args.parent))
            cur = end
    results = {}
    with mp.get_context("fork").Pool(args.workers, initializer=init_worker,
                                     initargs=(args.repo, args.parent)) as pool:
        for packed in pool.imap_unordered(run_slice, tasks):
            d = packed["domain"]
            r = results.setdefault(d, {"executed": 0, "passed": 0, "failed": 0, "skipped": 0,
                                       "assertions": 0, "rules": {}, "samples": {}, "_fps": set()})
            for k in ("executed", "passed", "failed", "skipped", "assertions"):
                r[k] += packed[k]
            for rule, count in packed["rules"].items():
                r["rules"][rule] = r["rules"].get(rule, 0) + count
            for rule, samples in packed["samples"].items():
                bucket = r["samples"].setdefault(rule, [])
                for smp in samples:
                    if len(bucket) < 6:
                        bucket.append(smp)
            r["_fps"].update(packed["_fps"])

    duration = time.time() - started
    out = {
        "schema": "privacy-guard-audit/1",
        "tested_sha": SHA,
        "generated_at_utc": utc_start,
        "duration_seconds": round(duration, 3),
        "seed": SEED,
        "scale": args.scale,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "domains": {},
        "totals": {},
        "expectation_oracle": "documented contract at tested SHA (see runner docstring)",
        "test_double": "agent.redact mocked in-memory for non-native D5 cases; absent in audit host",
    }
    totals = {"planned": sum(plan.values()), "executed": 0, "unique_inputs": 0, "passed": 0,
              "failed": 0, "skipped": 0, "assertions": 0}
    for domain in DOMAIN_PLAN:
        if domain not in results:
            continue
        r = results[domain]
        fps = r.pop("_fps")
        entry = {
            "planned": plan[domain],
            "executed": r["executed"],
            "unique_inputs": len(fps),
            "passed": r["passed"],
            "failed": r["failed"],
            "skipped": r["skipped"],
            "assertions": r["assertions"],
            "fail_rate_of_executed": round(r["failed"] / r["executed"], 6) if r["executed"] else None,
            "rules": dict(sorted(r["rules"].items(), key=lambda kv: -kv[1])),
            "samples": r["samples"],
        }
        out["domains"][domain] = entry
        for k in totals:
            if k == "planned":
                continue
            totals[k] += entry[k]
    out["totals"] = totals
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    print(f"sha={SHA} scale={args.scale} duration={duration:.1f}s")
    for domain, e in out["domains"].items():
        print(f"{domain}: executed={e['executed']} pass={e['passed']} fail={e['failed']} "
              f"skip={e['skipped']} unique={e['unique_inputs']} assertions={e['assertions']}")
    print(f"TOTAL: executed={totals['executed']} pass={totals['passed']} fail={totals['failed']} "
          f"skip={totals['skipped']} unique={totals['unique_inputs']} assertions={totals['assertions']}")


if __name__ == "__main__":
    main()
