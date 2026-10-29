# Privacy Guard end-to-end tests

These tests start a real Hermes process with Privacy Guard enabled and assert what the synthetic loopback provider actually receives. Profiles are disposable and all PII/credential-like values are synthetic.

## CI contract

CI runs this suite against `Abelion512/hermes-4gent` pinned to `9a85916c87d56c2ca00b02fad8918f93ef1816e9`. The harness verifies the imported source's full Git HEAD. Missing Hermes or a different revision fails the required run rather than silently skipping it.

This is compatibility evidence for that exact fork commit. It does not certify stock Hermes, all secret formats, every outbound path, or a real provider.

## Layout

- `test_privacy_wire.py`: main and auxiliary provider requests and tool-result replay.
  It also tests mixed adversarial input forms across all observed provider requests, fail-closed handling of invisible Unicode labels, and final-output redaction.
- `test_loopback_provider.py`: the synthetic local OpenAI-compatible provider.
- `test_support_environment.py`: child-process environment allowlisting.
- `support/loopback_provider.py`: server fixture that records local test traffic.
- `../docs/USAGE.md`: behavior contract and limits.

The shared process/profile harness lives under `.github/e2e_support/` so both plugin E2E suites use one core-verification implementation.

## Run locally

```bash
HERMES_PYTHON=/path/to/pinned/hermes/venv/bin/python \
HERMES_EXPECTED_COMMIT=9a85916c87d56c2ca00b02fad8918f93ef1816e9 \
REQUIRE_HERMES_E2E=1 \
python -m pytest plugins/pii_mask_abelion/e2e -v -rs
```

Synthetic canaries only; no external model API is contacted and inherited provider credentials are stripped from test subprocesses. The loopback test verifies the host boundary, not compatibility with a particular remote model or a model-size class.
