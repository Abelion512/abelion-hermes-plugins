# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Invalid capacity/TTL values raise before state exists. Wrong request, model or tool argument types are denied; values are not coerced. Partial middleware requests remain supported. Existing exact session/path/secret rules are unchanged.

## Test matrix

| Test file | What it validates | Command |
|---|---|---|
| `tests/test_guard.py` | Session map, mask/restore round trip, PATH tool slot, capacity, cookies, session material | `pytest plugins/nebula/tests/test_guard.py -q --tb=short` |
| `tests/test_credentials.py` | Credential field classification, vendor shapes, URL/query/JSON arguments, false positives | `pytest plugins/nebula/tests/test_credentials.py -q --tb=short` |
| `tests/test_pii_middleware.py` | PII middleware request walk, schema defaults, headers/extra_body, private key blocks | `pytest plugins/nebula/tests/test_pii_middleware.py -q --tb=short` |
| `tests/test_consolidated_privacy.py` | Exactly one active plugin manifest, native output redaction + CLI restore | `pytest plugins/nebula/tests/test_consolidated_privacy.py -q --tb=short` |
| `tests/test_guard_runtime.py` | Runtime placeholder round trip, required oversize denial, cookie boundary | `pytest plugins/nebula/tests/test_guard_runtime.py -q --tb=short` |
| `tests/test_robustness.py` | Missing native detector symbols, missing payload fields, unhashable session ids, skill registration failures, fail-closed middleware fallback, non-string structured values | `pytest plugins/nebula/tests/test_robustness.py -q --tb=short` |
| `e2e/test_privacy_wire.py` | Real Hermes process + loopback provider egress (requires Hermes runtime) | `pytest plugins/nebula/e2e/test_privacy_wire.py -q --tb=short` |

## Known skipped paths

- `test_pathological_inputs_do_not_blow_up` is hardware-bound. On slow hosts the 2.0s threshold may fail; deselect rather than relax.
- E2E tests are skipped when `HERMES_PYTHON` does not point to an importable Hermes install. They are not run in this environment.
- Native `agent.redact` is unavailable outside Hermes; tests that assert on final-output behavior monkeypatch or mark unavailable.

## Failure taxonomy

| Failure mode | Branch | Recovery |
|---|---|---|
| Unknown placeholder | `required_policy` / `output` | Fresh session; do not reuse old `<HG:...>` tokens across restarts |
| Capacity / oversize | `required_policy` request size bound | Reduce input size or start new session |
| Media / unsupported | `walk` / `required_policy` | Change input/route; do not retry same payload |
| Cookie / session material | `session_material` | Remove live auth material from prompt/schema |
| Native redactor missing | `output` | Withhold output or run inside Hermes; do not claim redaction from standalone tests |
