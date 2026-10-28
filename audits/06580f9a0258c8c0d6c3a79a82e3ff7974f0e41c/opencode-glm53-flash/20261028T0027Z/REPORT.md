# Audit report — privacy-guard @ 06580f9 (agent `opencode-glm53-flash`)

Independent agent audit of the privacy-guard plugin (`pii_mask_abelion`) at
`06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c` (base branch
`fix/privacy-classifier-case-invariance`). No tests were rerun to produce this
delivery; all counts below are recorded results of the earlier phase-A run.

- Agent / model: `opencode-glm53-flash` (OpenCode, GLM-5.3-Flash Free)
- Tested SHA: `06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c`
  (branch `fix/privacy-classifier-case-invariance`; verified `git rev-parse HEAD`
  in the pinned audit checkout, recorded in `logs/environment.txt`)
- Domains: D1 field classification (case-invariance sweep + regression set),
  D2 benign-name false positives, D3 request/payload nested masking,
  D4 placeholder/session boundaries, D5 output redaction (phase B + deep runtime)
- Executed: ≥ 250,000 exactly-checkpointed executions
  (D1 200,000/200,000 complete; D2 50,000/140,000 to the last checkpoint)
- Unique: 67,532 (D1 recorded; D2 unique count never persisted — run truncated)
- Pass: ≥ 249,756 — Fail: ≥ 244 — Skipped: 0 — Not-run: ≥ 750,000
  (remaining phase A 625,000 + phase B 125,000; only checkpointed executions counted)

## Method

Stdlib-only fuzz/deterministic-corpus runner (`runner/run_audit.py`, ~1,280
lines of corpus generators over synthetic canaries; no network, no real secrets,
no plugin-source modifications). Phase A ran with the native `agent.redact`
seam absent so the end-to-end `'[OUTPUT_WITHHELD:redactor_unavailable]'` path is
exercised. Full budget was 1,000,000 executions across phases A/B (per
`runner/README.md`). The run was truncated mid-D2 (host/session ended) before
`results_A.json` was written; only `logs/run_A.log` checkpoints remain, and
counts here are transcribed verbatim from those lines into
`results/results_partial_run_A.json`.

## Root findings

1. **Case-invariance fix verified at D1: 200,000/200,000 pass, 0 fail**
   (400,000 assertions; includes the `REGRESSIONS_D1` fixed pairs at ~5% of the
   budget ≈ 10,000 regression executions; complete list of pairs in
   `repros/case_fix_invariance.md`). Depth of classifier invariance over
   mixed-case, upper/lower/swapcase variants of compound secret names and
   lookalike benign names held at 0 violations.
2. **D2 flags 244 false-positive candidates by the 50,000 checkpoint**
   (0.49% of executions through that point; 49,756/50,000 pass). Suspected
   benign-name over-masking — genuine issue, but fail samples were not captured
   (sample capture happens when the run completes this domain; the run
   truncated). Needs a rerun to characterize; not yet attributable to the
   case-invariance change itself.
3. D3/D4/D5 + phase B: **not run**. No claim is made for those domains beyond
   "not exercised".

## Limitations

- Partial run: ≥ 750,000 executions not run; D2 tail between the final
  checkpoint and truncation is undercounted (upper bound < 90,000 further).
- Fail samples for D2 lost (no `results_A.json`).
- No rerun was performed after truncation (per delivery instructions).
- Phase B (native-seam-present D4/D5 paths) never started.
- Audit is read-only: no plugin source changes anywhere on this branch.

## Evidence map (all hashes in `SHA256SUMS`)

- `results/results_partial_run_A.json` — counts transcription (authoritative source: log)
- `logs/run_A.log` — verbatim checkpoint log of phase A
- `logs/environment.txt` — pinned checkout, Python, kernel, UTC timestamp
- `results/repros_A_D1_field_classification.json` — empty D1 fail-repro set
  (`[]`, consistent with 0 D1 failures)
- `repros/case_fix_invariance.md` — minimal repro sheet for the case fix
- `runner/` — the full runner used (`run_audit.py`, `make_summary.py`,
  `orchestrate.sh`, `README.md`)
