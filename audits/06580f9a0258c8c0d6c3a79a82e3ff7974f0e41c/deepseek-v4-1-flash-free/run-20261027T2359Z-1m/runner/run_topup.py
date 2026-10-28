#!/usr/bin/env python3
"""Supplementary run: execute ONLY the case slots the primary D1 pass skipped.

The primary run skipped 4,176 D1 slots because the runner's pre-run filter treated
"expected None + a LABEL word in the parts" as ambiguous. That was over-conservative:
classify_field (unlike Guard.spans) has no LABEL rule, so those expectations are
decidable by the same oracle used everywhere else. The filter is not changed here;
this script re-derives the exact skipped indices and executes just them.

It does not re-run any completed case. The primary results.json is untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import run_audit as ra


def d1_parts(i: int):
    """Exact mirror of run_audit.d1()'s index decode, without executing the case."""
    core = ra.D1_CORES[i % len(ra.D1_CORES)]
    i //= len(ra.D1_CORES)
    pre = ra.D1_PREFIX[i % len(ra.D1_PREFIX)]
    i //= len(ra.D1_PREFIX)
    suf = ra.D1_SUFFIX[i % len(ra.D1_SUFFIX)]
    i //= len(ra.D1_SUFFIX)
    tail2 = ra.D1_TAIL2[i % len(ra.D1_TAIL2)]
    i //= len(ra.D1_TAIL2)
    style = ra.CASE_STYLES[i % len(ra.CASE_STYLES)]
    i //= len(ra.CASE_STYLES)
    sep = ra.SEP_STYLES[i % len(ra.SEP_STYLES)]
    i //= len(ra.SEP_STYLES)
    variant = i
    parts = [pre, *core]
    if suf:
        parts.append(suf)
    if tail2:
        parts.append(tail2)
    if variant % 3 == 1 and core not in (("compass",), ("bypass",)):
        parts = core[:]
    name = ra.build_name(parts, sep, style)
    return parts, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--parent", required=True)
    ap.add_argument("--primary", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ra.init_worker(args.repo, args.parent)
    primary = json.loads(Path(args.primary).read_text())
    recorded = primary["domains"]["D1_field_classification"]["skipped"]

    t0 = time.time()
    cases = []
    for i in range(ra.DOMAIN_PLAN["D1_field_classification"]):
        parts, name = d1_parts(i)
        expected = ra.expect_kind(parts)
        if expected is None and any(p in ra.LABEL_WORDS for p in parts):
            cases.append((i, name, expected))
    assert len(cases) == recorded, (len(cases), recorded)

    passed = failed = assertions = 0
    fps = set()
    fails = []
    for i, name, expected in cases:
        got = ra._C.classify_field(name)
        assertions += 1
        fps.add(ra.fp("D1topup", name))
        if got == expected:
            passed += 1
        else:
            failed += 1
            if len(fails) < 6:
                fails.append({"index": i, "name": name, "expected": expected, "actual": got})

    out = {
        "schema": "privacy-guard-audit-supplementary/1",
        "tested_sha": ra.SHA,
        "seed": ra.SEED,
        "kind": "D1 skipped-slot completion",
        "selection": "primary D1 indices where expected is None and a LABEL word is present",
        "recorded_primary_skips": recorded,
        "selected": len(cases),
        "executed": len(cases),
        "unique_inputs": len(fps),
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "assertions": assertions,
        "fail_samples": fails,
        "duration_seconds": round(time.time() - t0, 3),
        "note": "No completed case from the primary run was re-executed.",
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("selected", "executed", "passed", "failed",
                                         "unique_inputs", "assertions", "duration_seconds")}))


if __name__ == "__main__":
    main()
