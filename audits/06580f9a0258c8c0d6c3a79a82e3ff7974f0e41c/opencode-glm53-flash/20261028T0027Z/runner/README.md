# Independent audit runner (pass A/B) — how to reproduce

Environment: Python 3.12.3 (stdlib only). No third-party dependencies.
All inputs are synthetic canaries ("cnry..." values); no real secrets.
The plugin source is NOT modified by this runner. The only runtime instrumentation
is a pure memoization shim for two deterministic functions of the plugin
(`Guard.spans`, `_credentials.classify_field`) to make 1e6 executions tractable;
behavior is unchanged. Source file hashes are recorded in results files.

Pinned tested source: commit 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c (branch snapshot
under test privilege of `Abelion512/abelion-hermes-plugins`), plugin folder
`pii_mask_abelion` (plugin.yaml version 1.2.0-test).

## Commands

Run both phases and write results files (`results_A.json`, `results_B.json`):

```bash
# fresh checkout (Pin SHA, no other repo work)
git init -q /tmp/opencode/pg-audit-work
git -C /tmp/opencode/pg-audit-work remote add origin https://github.com/Abelion512/abelion-hermes-plugins.git
git -C /tmp/opencode/pg-audit-work fetch -q origin 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c
git -C /tmp/opencode/pg-audit-work checkout -q --force --detach FETCH_HEAD
git -C /tmp/opencode/pg-audit-work rev-parse HEAD  # expect 06580f9a...e41c

cd /<audit root>/audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/opencode-glm53-flash

AUDIT_REPO_ROOT=/tmp/opencode/pg-audit-work AUDIT_OUT=./results \
  AUDIT_PHASE=A AUDIT_SEED=2714620565 \
  python3 runner/run_audit.py

AUDIT_REPO_ROOT=/tmp/opencode/pg-audit-work AUDIT_OUT=./results \
  AUDIT_PHASE=B AUDIT_SEED=2714620565 \
  python3 runner/run_audit.py
```

Optionally precede either with `AUDIT_SMOKE=1` for a 400-exec/domain smoke run.

## Budget (executions, exact)

| phase | domain | planned |
|---|---|---|
| A | D1_field_classification | 200000 |
| A | D2_benign_name_false_positives | 140000 |
| A | D3_request_nested_payload_masking | 310000 |
| A | D4_placeholder_session_boundaries | 165000 |
| A | D5_output_redaction | 60000 |
| B | D4_placeholder_session_boundaries | 25000 |
| B | D5_output_redaction | 100000 |
| total | | 1000000 |

Phase B runs with `install_native_stub()` (documented in run_audit.py): the host
`agent.redact` seam is mocked with a controlled redactor so the plugin's real
output-hook code path exercises the same flow as on a Hermes host with the native
redactor present. Phase A runs with that seam absent → plugin's own
"[OUTPUT_WITHHELD:redactor_unavailable]" behavior exercises end-to-end.

## Counting rules

* executed = every single target invocation plus its own set of assertions.
  pass and fail sum to executed (assertion failures decrement exec PASS but not
  the assertion count).
* unique inputs = distinct (domain-qualified + canonical-input) strings per domain;
  phase A and B family sets are disjoint by construction — the union of unique
  counts across phases is exact with no double counting.
* assertions = checks that evaluated true within each execution.
* Not-run = planned budget never reached before a fatal stop; separately tracked
  in results.json per domain and total.

## Not part of the tested build

Nothing under runner/ is part of the plugin build. Everything in `runner/` is
pure measurement infrastructure.
