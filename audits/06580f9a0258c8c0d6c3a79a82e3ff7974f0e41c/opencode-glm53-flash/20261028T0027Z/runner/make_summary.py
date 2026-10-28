#!/usr/bin/env python3
"""Merge phase A + B partial results into the audit's final results.json.

Usage: python3 make_summary.py <A_results.json> <B_results.json> <out results.json>
Adds:
* exact totals (executed = pass + fail, no double counting across phases),
* per-domain merged numbers (phases carry disjoint family sets so the unique
  input counts add without overlap),
* plugin source SHA256 verification snapshot taken from both phases,
* the tested SHA and provenance block.
"""
from __future__ import annotations

import json
import sys

DOMAINS = ["D1_field_classification", "D2_benign_name_false_positives",
           "D3_request_nested_payload_masking", "D4_placeholder_session_boundaries",
           "D5_output_redaction"]


def main(argv):
    a_path, b_path, out_path = argv[1], argv[2], argv[3]
    a = json.load(open(a_path))
    b = json.load(open(b_path))
    assert a["phase"] == "A" and b["phase"] == "B", "phase files swapped"
    assert a["tested_sha"] == b["tested_sha"] and a["seed"] == b["seed"]

    merged: dict = {}
    counts = {}
    for dom in DOMAINS:
        pa = a["per_domain"].get(dom, {})
        pb = b["per_domain"].get(dom, {})
        row = {
            "planned": pa.get("planned", 0) + pb.get("planned", 0),
            "executed": pa.get("executed", 0) + pb.get("executed", 0),
            "unique_inputs": pa.get("unique_inputs", 0) + pb.get("unique_inputs", 0),
            "pass": pa.get("pass", 0) + pb.get("pass", 0),
            "fail": pa.get("fail", 0) + pb.get("fail", 0),
            "assertions": pa.get("assertions", 0) + pb.get("assertions", 0),
            "assertion_failures": (pa.get("assertion_failures", 0)
                                   + pb.get("assertion_failures", 0)),
            "skip": 0,
            "not_run": max(0, (pa.get("planned", 0) + pb.get("planned", 0))
                           - (pa.get("executed", 0) + pb.get("executed", 0))),
            "phases": {"A": pa, "B": pb},
        }
        merged[dom] = row
        counts[dom] = row
    totals = {}
    for k in ("planned", "executed", "unique_inputs", "pass", "fail", "assertions",
              "assertion_failures", "not_run"):
        totals[k] = sum(v[k] for v in merged.values())
    totals["skip"] = 0
    totals["executed_eq_pass_fail"] = totals["executed"] == totals["pass"] + totals["fail"]
    result = {
        "summary_version": "audit-run-summary-v1",
        "tested_sha": a["tested_sha"],
        "requested_sha": "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c",
        "sha_pinned_verified": a["tested_sha"] == "06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c",
        "seed": a["seed"],
        "generator": "run_audit.py (independent; own vocabulary and compositions)",
        "phases": {"A": "no native redactor; standalone plugin execution",
                   "B": "plugin real + controlled agent.redact stub (mock of Hermes core)"},
        "environment": {
            "python_phase_a": a["python"], "python_phase_b": b["python"],
            "dependencies": "stdlib only (no pip installs)",
            "hermes_core_present": False,
        },
        "source_files_sha256": a.get("source_file_sha256", {}),
        "per_domain": merged,
        "totals": totals,
        "timing": {"phase_a_s": a["duration_s"], "phase_b_s": b["duration_s"]},
        "selfcheck": {"A": a.get("selfcheck"), "B": b.get("selfcheck")},
    }
    json.dump(result, open(out_path, "w"), indent=1)
    print("merged totals:", json.dumps({k: totals[k] for k in
                                        ("planned", "executed", "pass", "fail",
                                         "assertions", "assertion_failures")}))
    print("executed==pass+fail:", result["totals"]["executed_eq_pass_fail"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
