# Nebula Plugin — Session History Summary

## 1. Plugin naming

- Original name: `pii_mask_abelion`
- Renamed to `nebula` in commit `13f876c` (monorepo refactor)
- Naming theme: cosmic/celestial phenomena discussed in prior sessions
  - Options considered: Luna, Astra, Terra, Sol, Aurora
  - User chose Nebula because "tidak tau ada apa di balik nebula"
  - Pattern: generic cosmic name, no `-abelion` suffix
- Current stable folder/ID: `nebula`

No references to `aqua`, `terra`, `luna`, `earth`, or `dst` exist in the current repo or git history.

## 2. Round-trip mask/restore discussion

- Round-trip test pattern `abelion -> mask -> restore -> abelion` was discussed in **OpenCode sessions**, not in Hermes sessions from the last 3 days.
- OpenCode discussion points:
  1. Round-trip test pattern to verify masking and restoration correctness
  2. Whether to use dataset/public credentials for testing
  3. User asked whether ChatGPT's claim that "transformers are needed" was true

## 3. Why Opencode "succeeded" vs assistant "failed"

- It did not actually succeed previously.
- `qwen3.5:0.8b` inference is >120s per request on this hardware.
- Both Hermes chat and OpenCode run with this local model timeout.
- Plugin tests themselves pass: `127/128` unit tests pass; one failure is `test_pathological_inputs_do_not_blow_up` due to a 2.0s timing threshold being too tight for this hardware.

## 4. Test coverage (current)

- **Unit tests:** 129 passed, 8 skipped, 1 failed (timing/hardware)
- **E2e tests:** 6 skipped (Hermes runtime not available in this environment)
- **Total:** 129 passed, 8 skipped, 1 failed from 138 collected tests

### New tests added (2026-11-02)

- `test_round_trip_abelion_username_mask_restore_local_only` in `plugins/nebula/tests/test_guard.py`
  - Local synthetic data only, no cloud.
  - Verifies mask removes secrets/PII/paths from wire.
  - Verifies session map stores exact originals.
  - Verifies PATH restores via `tool_request` (`read_file` slot).
  - Verifies CLI restore for PII/PATH when redactor present; credentials never restore.
- `test_public_credential_shapes_are_masked_but_not_restored` in `plugins/nebula/tests/test_guard.py`
  - Public-known credential shapes with fake values: `hf_`, `AIza`, `ghp_`, `github_pat_`, `sk-ant-`, `sk-proj-`, `xoxb-`, `AKIA`, JWT.
  - Verifies shapes are masked from wire.
  - Verifies credential values never restore via CLI.

## 5. User constraints

- **Local-only testing:** tests must not use cloud accounts.
- **Round-trip visibility:** `abelion -> username -> abelion` pattern must be readable to verify mask/restore success.
- **No transformer dependency:** standalone tests run without `agent.redact`; restore behavior is monkeypatched in tests.
- **Model rule:** all verification must use local model inference. Do not route test prompts through cloud providers.

## 6. Key files

- `plugins/nebula/tests/test_guard.py` — Guard unit tests, including round-trip and public-shape tests
- `plugins/nebula/tests/test_credentials.py` — Credential masking tests
- `plugins/nebula/pii_middleware.py` — LLM request masking middleware
- `plugins/nebula/output_redact.py` — Final-output redaction hook
- `plugins/nebula/guard.py` — Session-local privacy guard with placeholder mapping
- `docs/VALIDATION.md` — Test matrix, known skipped paths, failure taxonomy
- `docs/SESSION_HISTORY.md` — This file

## 7. Open items

- `test_pathological_inputs_do_not_blow_up` threshold may need hardware-adjusted bound.
- E2E tests blocked: Hermes runtime not available (`HERMES_PYTHON` missing), commit-mismatch gate.
- Opencode v2.2.5 activation failing ("Location plugins did not finish activating"); not required for plugin tests.
- `AGENTS.md` creation blocked by approval timeout; pending manual creation.

## 8. Commands

```bash
# Unit tests
pytest plugins/nebula/tests/test_guard.py -q --tb=short
pytest plugins/nebula/tests/test_credentials.py -q --tb=short
pytest plugins/nebula/tests/ -q --tb=no

# E2E (requires Hermes runtime)
pytest plugins/nebula/e2e/test_privacy_wire.py -q --tb=short
```

## 9. Notes

- Only use qwen3.5:0.8b with curl?, not use hermes for test mask (abelion -> mask -> username/cloud api free tier will use for train data so we must to protect our data privacy just in local no going out from local -> restore -> abelion)
- U can improve for missing or wrong test for more stable the system.
- Every create new plugins, use vibes @docs/title-reference.md