# Privacy Guard — independent audit report

- **Agent:** DeepSeek V4.1 Flash Free (`deepseek-v4-1-flash-free`), run `run-20261027T2359Z-1m`.
- **Domain:** `pii_mask_abelion` (Privacy Guard plugin) — credential/PII classification, request masking, placeholder/session handling, output redaction, case-fix regression.
- **Tested SHA:** `06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c` (`HEAD` verified before and after; base branch head identical).
- **Repository:** `Abelion512/abelion-hermes-plugins`. Plugin source was imported read-only and is unchanged.
- **Generated:** 2026-10-28T00:04:33Z. **Seed:** 20261028. **Host:** Linux-7.0.0-38-generic-x86_64, Python 3.12.3, 4 cores, no network.

## Headline

- **Planned case slots:** 1,000,000 across 6 domains.
- **Executed:** 1,000,000 (primary 995,824 + supplementary 4,176).
- **Unique inputs:** 900,398 (blake2b-64 fingerprints; D1/D6 hash the name, D2–D5 hash name+value).
- **Passed:** 935,332. **Failed:** 64,668. **Skipped (final):** 0. **Assertions:** 2,004,809.
- **Primary run only:** executed 995,824, passed 931,156, failed 64,668, skipped 4,176 (see H3).
- **Upstream test suite at the same SHA:** 67 passed, 6 skipped, 3 failed under CPU load; idle re-run of the three: 2 passed, 1 failed (finding S4).
- The failure rate below is a **corpus** rate, not a production leak rate: the corpus deliberately over-samples risky shapes.

## Results per domain

- **D1 field classification — 250,000 planned, 250,000 executed, 245,356 unique, 246,544 pass, 3,456 fail, 0 skip, 250,000 assertions.** Names over prefixes, semantic cores, disqualifier suffixes, secondary tails, case styles and `_`/`-`/`.`/camel separators. All 3,456 fails are one family (H1).
- **D2 benign-name false positives — 150,000 planned/executed/unique, 150,000 pass, 0 fail, 450,000 assertions.** Benign values, control fields and request identity unchanged.
- **D3 request/nested masking — 250,000 planned/executed/unique, 197,988 pass, 52,012 fail, 934,809 assertions.** Guard and legacy middleware; `meta` dict, tool-call arguments, message content text, tool-result JSON string, and headers; nesting depth 1–70; 13 sensitive and 10 benign keys; separators and case styles. Fail family `sensitive_value_forwarded`; three verified sub-causes (S1–S3).
- **D4 placeholder/session boundary — 150,000 planned/executed/unique, 150,000 pass, 0 fail, 150,000 assertions.** SECRET/PII/PATH/IDENTIFIER values, `cli`/`api`/empty/`gateway` platforms, same/foreign/closed/same-after-other sessions, output/required-policy/tool-request/text-reoccurrence actions.
- **D5 output redaction — 100,000 planned/executed/unique, 90,800 pass, 9,200 fail, 120,000 assertions.** Unavailable-native path against the real host, parenthetical masking, restore ordering and failure modes. The two fail families are one harness assertion bug (H2) and one dependency-robustness gap (S5).
- **D6 case-fix regression — 100,000 planned/executed, 5,042 unique, 100,000 pass, 0 fail, 100,000 assertions.** Parent `49e1fe4` vs tested SHA across case/separator styles. No regression found; low uniqueness is a design limit (H5).

## Method

- One execution = one case index `i` decoded deterministically into parameters, evaluated once against the pinned source with at least one assertion. `executed = passed + failed`. Skipped and not-run categories are separate.
- Expectations were written from the documented contract at the tested SHA before the run: module docstrings, `_NOT_SECRET`/`_NOT_VALUE_LAST`/`_NOT_VALUE_ANY`/`_KEY_PREFIX`/`_ID_PAIRS` vocabulary comments, `README.md`, `docs/VALIDATION.md`, and placeholder/session comments in `guard.py`. The oracle never calls the implementation to derive an expectation.
- 4 worker processes; each case is independent of worker assignment. No shared mutable state between cases except counters. Deterministic index→case mapping, so the run is reproducible with the same SHA and seed.
- Every value is a synthetic canary. No real secret, no provider call, no install, no plugin activation.
- `agent`/`agent.redact` is **not** installed in the audit host. D5 first exercises the real "native redactor unavailable" path, then installs an in-memory `agent.redact` test double in `sys.modules` to exercise the surrounding logic. The double is not Hermes.
- Corpus shaping (not results) was fixed before the run: 250k/150k/250k/150k/100k/100k. The 4,176 D1 slots skipped by an over-conservative pre-run rule were executed afterwards by a separate supplementary pass; no completed case was re-executed. Both raw result files are committed and the combined view is generated from them.

## Findings

### Source bugs

- **S1 — `Authorization` / `Proxy-Authorization` header value forwarded (Medium).** Required mode allows the request and forwards the raw token when the header value has no `Bearer`/`Basic` scheme; prose `Authorization: <raw>` behaves the same. Affected: `pii_mask_abelion/guard.py` `Guard.spans` (line 85; the auth regex at line 137 only consumes scheme-prefixed tokens) and `Guard.session_material` (line 288; the sensitive-key set omits `authorization`). Expectation basis: README required-mode "mask the whole request", credentials never restored, headers are request data. Parity evidence: the legacy structured path *does* mask these keys via `_credentials.mask_value_for_key` (`_AUTH_KEYS`, `_credentials.py:329`), so the guard/legacy behaviour disagrees. Repro `repros/r1_authorization_header_leak.py`: all six variants `allow=True`, canary forwarded. Corpus evidence: `results.json`, `D3_request_nested_masking.rules.sensitive_value_forwarded` (52,012 aggregate; see limitation L3).
- **S2 — Name/value indirection inside JSON strings is forwarded (Medium).** `{"name":"HF_TOKEN","value":"<canary>"}` is masked when it is a real dict, but forwarded when the same object arrives as a JSON string — the normal shape for tool results and message content. Affected: `guard.py` `Guard.walk` (line 205, pair handling only for dicts) and `Guard.text` (line 171); `pii_mask_abelion/pii_middleware.py` `mask_content` (line 105) and `_mask_obj` (line 176). Expectation basis: README says JSON tool arguments and tool-result replay are walked; `walk` masks the identical pair as a dict. Repro `repros/r2_tool_result_json_indirection.py`: guard `allow=True` + canary forwarded, legacy forwarded, real-dict control masked.
- **S3 — Legacy middleware colon+space and underscore-flag gaps (Low).** `mask_credentials("api_key: <value> tail")` is skipped because `_looks_like_code` (`_credentials.py:236`) treats a colon+space+word as prose/annotation; `--api_key` / `--client_secret` are not matched by `_FLAG` (`_credentials.py:67`, kebab-only) and no dictionary key exists, so `mask_value_for_key` cannot help. Expectation basis: module docstring says `<anything>_API_KEY`/`api-key`/`apiKey` names mask the value; legacy CLI forms are documented. Repro `repros/r3_legacy_underscore_flag.py`: kebab flags masked, underscore flags and the two-word colon form forwarded. Impact is limited: `register()` wires only the guard hooks, so this path is reachable only by direct `pii_middleware` callers.
- **S4 — 200 KB field value takes 3.63 s in legacy masking (Low, latency/DoS).** `mask_credentials("api_key=" + "x"*200000)` measured 3.63 s on an idle host (single run); `pii_mask_abelion/tests/test_credentials.py::test_pathological_inputs_do_not_blow_up` asserts `<2.0 s` and still fails on an idle host (`logs/pytest_upstream_rerun_idle.log`). The guard path is bounded separately (`test_bounded_redos` passes idle; guard caps text at 128 KiB), so this affects direct legacy users, not the registered hook path.
- **S5 — A native redactor returning `None` discards the layer-1 mask (Low, dependency-dependent).** `output_redact.redact_output` (`output_redact.py:21–63`) sets `changed=True` after parenthetical masking, then `return None` if the dependency returns `None`; `Guard.output` (`guard.py:350`) treats `None` as "nothing redacted" and forwards the pre-redaction text, so the already-computed layer-1 mask is lost. Repro `repros/r7_none_redactor_discards_layer1.py`: canary forwarded with only the parenthetical label untouched. The documented Hermes `redact_sensitive_text` returns `str`, so this needs a non-conforming dependency; demonstrated with an in-memory double only.

### Policy disagreements and documented limits (not counted as source bugs)

- **P1 — Over-masking of glued `apikey` names (3,456 D1 cases).** The source decomposes `apikey` into `api`+`key` and the pair rule has no tail guard, so `db_apikey_label_raw` and 1,799 other names classify `SECRET`. The audit oracle applied the tail-disqualifier rule to the glued word and expected `None`. The source is consistent with its docstring ("a segment pair such as api + key"); the effect is fail-closed over-masking. Counted as a fail under H1, not as a bug.
- **P2 — `password_hash` / `token_hash` classify as `None`, while `apikey_help`/`api_key_help` classify as `SECRET` (Low).** Suffix policy is inconsistent for human-equivalent names. `repros/r5_false_positive_api_help.py`. Masking is a utility/over-masking decision, not a leak; recorded as a policy gap.
- **P3 — Remembered 1–3 character literals are not re-masked without a label (Low).** `guard.py` says exact registered literals are masked without the label, but the re-occurrence loop skips values shorter than 4 bytes. `repros/r6_short_literal_reoccurrence.py`: first labelled occurrence masked, bare second occurrence forwarded. Masking every 1–3 character substring would damage ordinary text, so this is reported as a documented-limit gap.
- **P4 — Optional `llm_request` forwards a `Cookie` header while required mode denies it (Low, documented).** `repros/r4_optional_cookie_header.py`: optional `canary_forwarded=True`, required `allow=False, reason=session_material`. This matches "optional is not a boundary", but callers must not treat optional as protection.
- **P5 — Parenthetical layer masks up to six words before the label (Informational).** `"I met a user (email)"` becomes `"*** (email)"`. Fail-closed over-masking; D5 parenthetical cases pass against the documented behaviour. Utility note only.

### Harness issues (not source bugs)

- **H1 — 3,456 D1 fails are an oracle-model limitation.** The oracle treats `apikey` as one secret word and applies the tail rule; the source splits it into `api`+`key` and applies the pair rule with no tail guard. Generation-only analysis (no engine call) counts exactly 3,456 such cases over 1,800 distinct names, matching the recorded fail count and every recorded sample. `logs/failure_family_analysis.txt`.
- **H2 — 4,320 D5 fails are a wrong assertion.** The `strip` test double returns `"*** (password) tail"`, i.e. layer 1 legitimately masked the canary before the label; the assertion nevertheless required the canary to remain visible. No source defect.
- **H3 — 4,176 D1 slots were skipped by an over-conservative pre-run LABEL rule.** `classify_field` has no LABEL rule (that lives in `Guard.spans`), so those expectations were decidable. `runner/run_topup.py` re-derived exactly those indices, executed only them (4,176 pass, 0 fail, 3.1 s) and wrote `results_supplementary.json`; no completed case was re-executed.
- **H4 — Two upstream perf tests failed only under CPU contention.** Another audit process shared the 4 cores during the primary run; on the idle re-run `test_performance_stays_linear_on_plain_text` and `test_bounded_redos` passed, `test_pathological_inputs_do_not_blow_up` still failed (S4).
- **H5 — D6 has 100,000 executions but only 5,042 distinct names.** The case-style axes replay a small name space, so D6 independence is lower than the execution count suggests; it is a regression check, not a broad classifier sample.

## NOT RUN

- **Real Hermes core end-to-end (0 executions):** `agent` / `agent.redact` are absent in the audit host; the real Hermes SHA `9b904dcc22c23fe8b82834339bbdd96495072e59` is not present. No orchestrator, agent tool dispatch, provider transport, CLI/API/gateway path or plugin activation was exercised.
- **Real native redactor (layer 2):** not installed; exercised only through the in-memory test double described above.
- **Provider/network calls, real credentials, destructive actions, installation:** none, by design.
- The 1,000,000 suite is plugin-level and in-process. It does not measure production leak rates, provider behaviour or framework integration.

## Commands, exit codes, durations

Run from `audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/deepseek-v4-1-flash-free/run-20261027T2359Z-1m`:

```
python3 runner/run_audit.py --repo /tmp/opencode/audit-pg/repo \
  --parent runner/parent_credentials_49e1fe4.py --out results.json --workers 4
# EXIT=0, 1261.1 s

python3 runner/run_topup.py --repo /tmp/opencode/audit-pg/repo \
  --parent runner/parent_credentials_49e1fe4.py --primary results.json \
  --out results_supplementary.json
# EXIT=0, 3.1 s, selected=4176, passed=4176

python3 runner/combine_results.py results.json results_supplementary.json results_combined.json
# EXIT=0

python3 -m pytest pii_mask_abelion/tests -q      # upstream suite, under CPU load
# EXIT=1, 3 failed, 67 passed, 6 skipped, 78.80 s

python3 -m pytest -q \
  pii_mask_abelion/tests/test_credentials.py::test_performance_stays_linear_on_plain_text \
  pii_mask_abelion/tests/test_credentials.py::test_pathological_inputs_do_not_blow_up \
  pii_mask_abelion/tests/test_guard.py::test_bounded_redos   # idle re-run
# EXIT=1, 1 failed, 2 passed, 6.37 s

sh repros/run_all.sh /tmp/opencode/audit-pg/repo
# EXIT=0; output in logs/repros_output.log
```

## Source integrity

- `HEAD = 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c`; tree `cb7a95c4d2f64717e3a2a3e6b6d332ed1213f04d`; tracked worktree clean.
- Key source hashes (full list in `logs/source_integrity.txt`):
  - `_credentials.py c14eb89279e0328fc642bf3eb986564f16d8bd8f602a71d3e2068be104977279`
  - `guard.py 75c8d35b007d66dd1a53c41fb8a35f6784a0cb20a7d234fa6949a7da2e93b2fa`
  - `output_redact.py bc10be4f9bbc5e8bfafbb82db5a5d97d30c5607293cc683ee0fb55f432a7c601`
  - `pii_middleware.py c2d53776f27a6f262f6b33e9e04aaca69b67ad2d8fbf487bf685d05562ecbbae`
  - `_patterns.py d107da26c30f9c96760037375ccc68202fcaf94c426bd41176dfbcb1ebf62816`
  - `plugin.yaml dd0e91ee327ee15ba01706d9c0314c19c8b14f334277d29c86d7b94a2acda408`
- Evidence is committed only under `audits/06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c/deepseek-v4-1-flash-free/run-20261027T2359Z-1m/`.

## Evidence map

- `results.json` — primary run: totals, per-domain rules, fail samples, environment.
- `results_supplementary.json` — the 4,176 previously skipped D1 slots.
- `results_combined.json` — canonical 1,000,000 view generated from the two files above.
- `runner/run_audit.py` — corpus, oracle and runner. `runner/run_topup.py` — skipped-slot completion. `runner/combine_results.py` — merge. `runner/README.md` — dependencies and counting rules.
- `repros/r1..r7` — minimal independent reproductions; `repros/run_all.sh` runs all.
- `logs/source_integrity.txt`, `logs/run_stdout.log`, `logs/run_stderr.log` (6,480 identical synthetic test-double warnings, no real data), `logs/exit_code.txt`, `logs/pytest_upstream*.log`, `logs/failure_family_analysis.txt`, `logs/repros_output.log`.
- `SHA256SUMS` — hashes for every evidence file; `sha256sum -c SHA256SUMS` is clean.

## Limitations

- **L1:** No real Hermes core, native redactor, provider or transport was available (see NOT RUN); the suite is plugin-level and in-process.
- **L2:** D6 has 5,042 distinct names over 100,000 executions (H5).
- **L3:** The D3 52,012 fails are reported as one family. The split by sub-cause was not instrumented; samples are dominated by legacy `content_text` and `tool_result_json`, with `Authorization` a smaller subset. S1–S3 are each verified by a standalone repro, but their exact shares of 52,012 are not claimed.
- **L4:** Another audit process shared the 4 CPU cores during the primary run; wall-clock timings are pessimistic. Case results are deterministic and unaffected.
- **L5:** The 4,176-slot supplementary pass corrected a harness skip rule, not an expectation; it is reported separately and merged transparently.
- **L6:** Corpus failure rate is not a production leak rate. The corpus intentionally over-samples risky names, depths and formats.
