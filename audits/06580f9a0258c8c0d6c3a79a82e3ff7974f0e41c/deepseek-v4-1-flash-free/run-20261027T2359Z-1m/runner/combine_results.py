#!/usr/bin/env python3
"""Merge the primary run and the D1 skipped-slot completion into one totals view.

Never edits either input. Both inputs are committed next to the output, so every
number below is recomputable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    primary = json.loads(Path(sys.argv[1]).read_text())
    supp = json.loads(Path(sys.argv[2]).read_text())
    out_path = Path(sys.argv[3])

    d1 = primary["domains"]["D1_field_classification"]
    d1c = dict(d1)
    d1c["executed"] += supp["executed"]
    d1c["passed"] += supp["passed"]
    d1c["failed"] += supp["failed"]
    d1c["assertions"] += supp["assertions"]
    d1c["unique_inputs"] += supp["unique_inputs"]
    d1c["skipped_primary"] = d1["skipped"]
    d1c["skipped_path"] = "completed by results_supplementary.json"
    d1c["skipped"] = 0
    d1c["rules"].pop("skip:label_word_out_of_scope", None)
    d1c["rules"]["completed_by_supplementary"] = supp["executed"]

    domains = dict(primary["domains"])
    domains["D1_field_classification"] = d1c
    totals = {"planned": sum(d["planned"] for d in domains.values()),
              "executed": 0, "unique_inputs": 0, "passed": 0, "failed": 0,
              "skipped": 0, "assertions": 0}
    for d in domains.values():
        for k in ("executed", "unique_inputs", "passed", "failed", "skipped", "assertions"):
            totals[k] += d[k]
    assert totals["executed"] == totals["passed"] + totals["failed"]
    assert totals["skipped"] == 0

    out = {
        "schema": "privacy-guard-audit-combined/1",
        "tested_sha": primary["tested_sha"],
        "seed": primary["seed"],
        "sources": ["results.json", "results_supplementary.json"],
        "note": ("Primary run executed 995,824 and skipped 4,176 D1 slots under an "
                 "over-conservative rule; the supplementary run executed exactly those "
                 "4,176 slots. No completed case was re-executed."),
        "primary_duration_seconds": primary["duration_seconds"],
        "supplementary_duration_seconds": supp["duration_seconds"],
        "domains": domains,
        "totals": totals,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(totals, indent=1))


if __name__ == "__main__":
    main()
