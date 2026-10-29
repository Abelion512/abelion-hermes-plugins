# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Invalid capacity/TTL values raise before state exists. Wrong request, model or tool argument types are denied; values are not coerced. Partial middleware requests remain supported. Existing exact session/path/secret rules are unchanged.

Tested in isolated development fixtures. This is not proof of the installed laptop source/runtime or a deployment.

## Test layers and automation

- Unit/regression layer: `python -m pytest plugins/pii_mask_abelion/tests -q`. This includes the seeded mutation matrix and should stay fast, deterministic, and model-free.
- Required-host E2E layer: CI checks out the exact core SHA configured in `.github/workflows/ci.yml`, verifies the imported source commit, and runs `plugins/pii_mask_abelion/e2e` against a synthetic loopback provider and disposable profiles. Missing host prerequisites fail the required CI run.
- Inspect recorded egress request bodies and user-visible output. A test that only inspects the plugin's in-memory return value is not a provider-boundary test.
- Keep imported/historical corpora separate from the current automated regression suite. Retired-target cases and known expectation mismatches must remain labelled as such, never counted as passes.
- CI is model-agnostic and does not call a live 2.8T-parameter model. The model size does not change the boundary contract: a canary must not cross the guarded provider edge or appear in delivered output. Live endpoint compatibility requires a separate opt-in test with synthetic data and explicit endpoint/budget configuration.

