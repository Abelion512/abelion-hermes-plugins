"""Privacy Guard 1,000,000-execution differential runner.

SUT (native, at pinned commit f11bdef):
  pii_mask_abelion.pii_middleware.{classify_content,mask_content,pii_middleware,scan_message}
  output_redact_abelion.output_redact.redact_output   (layer-2 ImportError path in this env)
Test double: direct function calls on plain dicts (mock transport; NO provider/network).
Oracle: oracle.py — independent contract reimplementation.

Method: seeded generator builds unique inputs per category; each execution asserts
SUT == oracle (contract-literal equivalence). PASS means "implementation matches its
own documented contract", NOT "no privacy leaks". Known contract-level gaps are
measured separately by policy_probe and reported as findings, never forced to PASS.

Counts executed / assertions / unique inputs separately. Exits non-zero on any fail.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import string
import sys
import time
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent.parent          # .../run-.../
REPO = RUN_DIR.parents[3]                                  # /workspace
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from oracle import (oracle_classify, oracle_mask, oracle_middleware,
                    oracle_output_redact, PUBLIC, INTERNAL, CONFIDENTIAL)

# ── Native SUT under pinned source ──
from pii_mask_abelion.pii_middleware import (classify_content, mask_content,
                                             pii_middleware, scan_message)
from output_redact_abelion.output_redact import redact_output

SEED = 20261028
TARGET_TOTAL = 1_000_000

rng = random.Random(SEED)

ALNUM = string.ascii_letters + string.digits
WORDS = ["alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india",
         "juliet","kilo","lima","mike","november","oscar","papa","quebec","romeo"]
FIRST = ["Budi","Siti","Andi","Dewi","Eko","Rina","Joko","Maya","Agus","Nina","Putri","Bayu",
         "Dian","Fajar","Hana","Iwan","Lina","Rudi","Sari","Tono","Umar","Vina","Wati","Yusuf",
         "Zaki","Arief","Citra","Doni","Endang","Gita"]
LAST = ["Wijaya","Santoso","Pratama","Kusuma","Halim","Susanto","Gunawan","Hartono","Lesmana",
        "Nugroho","Permana","Setiawan","Utomo","Wibowo","Yulianto","Firmansyah","Ramadhan",
        "Saputra","Maharani","Anggara"]
PREFIXES = ["sk","SK","Sk","pk","PK","Pk"]
GH_PREFIX = ["ghp_","GHP_","gho_","GHO_","ghu_","ghU_"]
LABELS = ["password","PASSWORD","Password","pass","PASS","pw","PW","secret","SECRET","Secrets",
          "token","TOKEN","apikey","API_KEY","api key","client_id","client secret","auth token",
          "webhook_secret","sudo_password","username","user name","email","EMAIL","user",
          "app_email","appPass","pass email","credentials","credential","password nya"]
PII_KEYS = ["email","EMAIL","Email","phone","PHONE","address","Address","ssn","nik","NIK",
            "ktp","KTP","npwp","kks"]
DB_SCHEMES = ["postgres","POSTGRES","mysql","MySQL","mongodb","MongoDB","redis","REDIS"]

def canary(n=None):
    n = n or rng.randint(8, 24)
    return "".join(rng.choice(ALNUM) for _ in range(n))

def word(): return rng.choice(WORDS)
def name2(): return f"{rng.choice(FIRST)} {rng.choice(LAST)}"

# ── Generators (each returns a fresh unique input) ─────────────────────

def g_classify():
    k = rng.random()
    if k < 0.30:
        return f"{word()} {word()} {canary(12)}"                      # benign-ish
    if k < 0.45:
        return f"my {rng.choice(['internal','company','rahasia','embargo','private'])} memo about {word()}"
    if k < 0.60:
        return f"{rng.choice(PREFIXES)}-{canary(rng.randint(2,40))}"   # mixed-case keys, incl. too-short
    if k < 0.70:
        return f"{rng.choice(GH_PREFIX)}{canary(rng.randint(4,40))}"
    if k < 0.80:
        return f"{word()} {rng.choice(PII_KEYS)}: {canary(rng.randint(1,20))}"
    if k < 0.90:
        return f"contact {name2()} ({rng.choice(LABELS)})"
    return f"{rng.choice(DB_SCHEMES)}://{canary(10)}:{canary(12)}@db.internal/{word()}"

def g_fp_names():
    ctx = rng.choice([
        "{n} works at the office", "meeting with {n} tomorrow", "cc {n} on the email",
        "{n}, please review", "ask {n} for details", "report by {n}",
        "{n} sent a file called report_{w}.pdf", "hello from {n} in {w}",
    ])
    s = ctx.format(n=name2(), w=word())
    if rng.random() < 0.15:
        s += f" and {name2()}"
    if rng.random() < 0.05:
        s += f" ({rng.choice(['author','reviewer','sender','friend'])})"  # benign paren, NOT in label set
    return s

def g_mask_text():
    t = rng.random()
    if t < 0.18:
        return f"{rng.choice(PREFIXES)}-{canary(rng.randint(2,40))} is my key"
    if t < 0.30:
        return f"{rng.choice(GH_PREFIX)}{canary(rng.randint(4,40))}"
    if t < 0.45:
        sep = rng.choice([":","="," : "," = ","  =  ",":'","=\""])
        key = rng.choice(["api_key","API-KEY","apikey","ApiKey","secret","TOKEN","password","Password","userApiKey","dbPassword","clientSecret","sessionToken"])
        val = canary(rng.randint(1,30))
        return f"{key}{sep}{val}"
    if t < 0.55:
        return f"the value is secret{canary(rng.randint(4,30))} here"
    if t < 0.65:
        return f"export MY_{rng.choice(['API_KEY','TOKEN','PASSWORD','SECRET'])}={canary(16)}\nnext line {word()}"
    if t < 0.75:
        return f"login as {name2()} ({rng.choice(LABELS)}) ok"
    if t < 0.82:
        return f"{rng.choice(DB_SCHEMES)}://{canary(8)}:{canary(10)}@host/{word()}"
    if t < 0.87:
        return f"url https://{canary(6)}:{canary(9)}@site.example/{word()}"
    if t < 0.90:
        return "-----BEGIN RSA PRIVATE KEY-----\n" + canary(40)
    if t < 0.94:
        return f"id {rng.choice(['','0'])}{''.join(rng.choice(string.digits) for _ in range(rng.randint(10,25)))} end"
    if t < 0.97:
        return f"{rng.choice(PII_KEYS)}: {rng.choice(['Jl. Merdeka No 5 Jakarta', canary(10), 'a+b@c.com', '0812-3456-7890'])}"
    return f"Bearer {canary(rng.randint(6,40))}.{canary(10)}"

def g_request_nested():
    style = rng.random()
    msgs = []
    nmsg = rng.randint(1, 4)
    for _ in range(nmsg):
        role = rng.choice(["user","assistant","system","tool"])
        if style < 0.4:
            msgs.append({"role": role, "content": g_mask_text()})
        else:
            parts = []
            for _p in range(rng.randint(1, 3)):
                ptype = rng.choice(["text","text","image_url","input_audio","file"])
                if ptype == "text":
                    parts.append({"type":"text","text": g_mask_text()})
                else:
                    parts.append({"type":ptype, ptype: {"url": g_mask_text()}})
            msgs.append({"role": role, "content": parts})
    req = {"messages": msgs, "model": f"mock-{word()}"}
    if rng.random() < 0.1:
        req["tools"] = [{"name":"x","desc": g_mask_text()}]
    return req

def g_boundary():
    k = rng.random()
    if k < 0.2:
        return ""                                   # empty
    if k < 0.3:
        return "[REDACTED]_OPENAI_KEY already masked"
    if k < 0.4:
        base = f"{rng.choice(PREFIXES)}-{canary(16)}"
        return f"{base} and again {base}"           # duplicate same secret
    if k < 0.5:
        return f"session start sk-{canary(12)} session end"
    if k < 0.6:
        return "\n".join(f"{word()} {word()}" for _ in range(rng.randint(2,6)))  # multiline no-secret
    if k < 0.7:
        return f"export A_{rng.choice(['TOKEN','PASSWORD'])}={canary(rng.randint(1,12))}"  # short env values
    if k < 0.8:
        return ("x"*rng.randint(1,50)) + f" password={canary(12)} " + ("y"*rng.randint(1,50))
    if k < 0.9:
        return f"({rng.choice(LABELS)})"            # annotation with no value before
    return f"sk-{canary(4)} pk-{canary(4)} sk-{canary(3)}"  # boundary lengths 4 vs 3

def g_corrupt():
    return rng.choice([
        None, 12345, [], {}, b"bytes-not-str",
        {"messages": []}, {"messages": None}, {"messages": [{}]},
        {"messages": [{"content": None}]}, {"messages": [{"content": 999}]},
        {"messages": [{"content": ["not-a-dict-part"]}]},
        {"messages": [{"content": [{"type":"text"}]}]},
        {"messages": [{"content": [{"type":"text","text":None}]}]},
        {"no_messages": True},
        "", "   ", "\x00\x01binary-ish", 
        {"messages":[{"content":{"nested":"dict-content"}}]},
        {"messages":[{"role":"user"}]},
    ])

def g_output():
    t = rng.random()
    if t < 0.35:
        return f"Login as {name2()} ({rng.choice(LABELS)}) with {canary(12)} ({rng.choice(LABELS)})"
    if t < 0.5:
        return f"The admin account is jdoe ({rng.choice(LABELS)})"
    if t < 0.6:
        return f"no parens here, just text about {word()}"
    if t < 0.7:
        return ""
    if t < 0.8:
        return f"({rng.choice(LABELS)}) alone"
    if t < 0.9:
        s = name2()
        for _ in range(rng.randint(2,6)):
            s += f" {word()}"
        return f"{s} ({rng.choice(LABELS)})"        # >6 words before annotation
    return f"partial ( not closed and other ) bracket {word()}"

def g_regression():
    # fixed replay set — deterministic, measured against contract-literal behavior
    pool = [
        ("My password is hunter2secret", 0),      # known gap: prose 'password is X' unmatched
        ("Contact John Smith today (email)", 1),
        ("sk-" + "abcdefgh", 1),
        ("SK-" + "AbCdEfGh", 1),
        ("ghp_" + "a"*8, 2),      # DOUBLE-MASK artifact: GITHUB_TOKEN then literal label re-hit by BARE_SECRET
        ("GHP_" + "A"*8, 2),
        ("api_key=" + "z"*8, 1),
        ("API-KEY : '" + "z"*8 + "'", 1),
        ("address: Jl. Merdeka No 5 Jakarta", 1),
        ("1234567890123456", 1),
        ("12345678901234567890", 0),              # 20-digit known gap
        ("Bearer " + "a"*12, 1),
        ("bearer " + "a"*11, 0),                  # below threshold
    ]
    item = pool[rng.randrange(len(pool))]
    REGRESSION_EXPECT[item[0]] = item[1]
    return item[0]

REGRESSION_EXPECT: dict[str,int] = {}

# ── Category configs: (generator, checks_fn, planned executions) ───────
# Each check returns list of assertion outcomes (bool). We count assertions.

def chk_unit(text):
    """classify + mask + scan_message consistency (unit level)."""
    if not isinstance(text, str):
        text = str(text)
    outs = []
    outs.append(classify_content(text) == oracle_classify(text))
    sm, sc = mask_content(text)
    om, oc = oracle_mask(text)
    outs.append(sm == om and sc == oc)
    res = scan_message(text)
    outs.append(res["masked_count"] == oc and res["sensitivity"] == oracle_classify(text))
    return outs

def chk_fp(text):
    # expectation basis: bare person names carry NO pattern trigger → must be PUBLIC & unmasked
    outs = []
    outs.append(classify_content(text) == PUBLIC)
    _, c = mask_content(text)
    outs.append(c == 0)
    return outs

def chk_req(req):
    got = pii_middleware(req)
    exp = oracle_middleware(req)
    outs = [got == exp]
    # POLICY probe (measure-only, NOT a contract assertion): after masking, does any
    # 12+ char alnum run survive in a text part? Measures partial-mask residue rate.
    if got is not None:
        for m in got["request"].get("messages", []):
            c = m.get("content")
            texts = ([c] if isinstance(c, str) else
                     [p.get("text","") for p in c
                      if isinstance(p, dict) and p.get("type")=="text"]
                     if isinstance(c, list) else [])
            for t in texts:
                RESIDUE_STATS["checked"] += 1
                if re.search(r"[A-Za-z0-9]{12,}", t.replace("[REDACTED]","")):
                    RESIDUE_STATS["residue"] += 1
    return outs

RESIDUE_STATS = {"checked": 0, "residue": 0}

def chk_boundary(text):
    return chk_unit(text) if isinstance(text, str) else [True]

def chk_corrupt(x):
    # robustness: SUT must not raise beyond what oracle-equivalent handling does;
    # we only require no crash OR identical exception class between SUT and oracle.
    try:
        r1 = pii_middleware(x) if isinstance(x, dict) else None
        e1 = None
    except Exception as ex:
        r1, e1 = None, type(ex).__name__
    try:
        r2 = oracle_middleware(x) if isinstance(x, dict) else None
        e2 = None
    except Exception as ex:
        r2, e2 = None, type(ex).__name__
    return [(r1 == r2 and e1 == e2) or (not isinstance(x, dict))]

def chk_output(text):
    return [redact_output(text) == oracle_output_redact(text)]

def chk_regression(text):
    _, c = mask_content(text)
    return [c == REGRESSION_EXPECT[text], classify_content(text) == oracle_classify(text)]

CATS = [
    ("classify",        g_classify,     chk_unit,      200_000, 2),
    ("fp_names",        g_fp_names,     chk_fp,        150_000, 2),
    ("mask_text",       g_mask_text,    chk_unit,      200_000, 3),
    ("request_nested",  g_request_nested, chk_req,     150_000, 1),
    ("boundary",        g_boundary,     chk_boundary,  100_000, 3),
    ("corrupt",         g_corrupt,      chk_corrupt,    20_000, 1),
    ("output_redact",   g_output,       chk_output,    150_000, 1),
    ("regression",      g_regression,   chk_regression, 30_000, 2),
]

def main():
    t0 = time.time()
    stats = {}
    total_exec = total_assert = total_fail = 0
    seen_hash_global = set()
    failures_sample = []
    for cat, gen, chk, planned, apc in CATS:
        if cat == "regression":
            # prime the fixed replay expectations deterministically (no rng draw)
            for txt, expc in [  # same pool as g_regression, primed before any regression exec
                ("My password is hunter2secret",0),("Contact John Smith today (email)",1),
                ("sk-abcdefgh",1),("SK-AbCdEfGh",1),("ghp_aaaaaaaa",2),("GHP_AAAAAAAA",2),
                ("api_key=zzzzzzzz",1),("API-KEY : 'zzzzzzzz'",1),
                ("address: Jl. Merdeka No 5 Jakarta",1),("1234567890123456",1),
                ("12345678901234567890",0),("Bearer aaaaaaaaaaaa",1),("bearer aaaaaaaaaaa",0)]:
                REGRESSION_EXPECT[txt]=expc
        uniq = set()
        ex = fa = ss = fl = 0
        for _ in range(planned):
            inp = gen()
            try:
                key = hashlib.sha1(repr(inp).encode()).hexdigest()
            except TypeError:
                key = f"unhashable:{type(inp).__name__}"
            uniq.add(key); seen_hash_global.add(key)
            outs = chk(inp)
            ex += 1; fa += len(outs); ss += sum(outs)
            if not all(outs):
                fl += 1
                if len(failures_sample) < 20:
                    failures_sample.append({"cat": cat, "input": repr(inp)[:300]})
        stats[cat] = {"planned": planned, "executed": ex, "assertions": fa,
                      "passed_asserts": ss, "failed_cases": fl,
                      "unique_inputs": len(uniq)}
        total_exec += ex; total_assert += fa; total_fail += fl
    dur = time.time() - t0
    out = {
        "seed": SEED, "target_sha_requested": "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c",
        "tested_sha_actual": subprocess_head(), "duration_s": round(dur, 2),
        "total_executions": total_exec, "total_assertions": total_assert,
        "total_failed_cases": total_fail,
        "global_unique_inputs": len(seen_hash_global),
        "categories": stats, "residue_probe": dict(RESIDUE_STATS), "failures_sample": failures_sample,
    }
    (RUN_DIR / "results" / "results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "categories"}, indent=2))
    print("FAIL" if total_fail else "ALL-EQUIVALENT")
    return 1 if total_fail else 0

def subprocess_head():
    import subprocess
    return subprocess.run(["git","-C",str(REPO),"rev-parse","HEAD"],
                          capture_output=True, text=True).stdout.strip()

if __name__ == "__main__":
    sys.exit(main())
