---
name: plugin-test
description: Write and run plugin tests in the right layer.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [plugin, test, e2e, pytest, synthetic, unit, regression]
---

# Plugin Test Skill

This repo keeps two test layers for each plugin: unit/regression in `tests/` and real-host E2E in `e2e/`. Use this skill when you are adding or updating tests, interpreting test output, or deciding whether a change is proven.

Use this when the user asks to add a test, fix a failing test, add E2E, or understand what the test suite proves.

## When to Use

- Adding a new unit test or regression test for plugin logic.
- Adding a real-host E2E test for a host-boundary behavior.
- Updating an existing test because the plugin behavior changed.
- Deciding whether a behavior is proven, not proven, or not covered.

Do not use this skill to bypass the synthetic-only rule or to turn a missing prerequisite into a silent pass.

## How to Apply

1. Pick the right layer.
   - In-plugin logic, classification, masking/replacement rules, state transitions, boundary caps, error handling: unit/regression in `tests/`.
   - What the host actually sends to a provider, what the user actually sees, or what a real dashboard flow does: real-host E2E in `e2e/`.
   - Do not use unit tests to claim a provider-boundary guarantee, and do not use E2E as the only fast feedback loop for plain logic.

2. Write the test for one clear concern.
   - One behavior per test where practical.
   - Arrange, act, assert in a readable order.
   - Share fixtures in `conftest.py` when multiple tests need the same setup.

3. Keep tests deterministic and fast.
   - Avoid "works on my machine" fixtures.
   - Avoid randomness unless the test is specifically about a randomized contract, and then control it.
   - Avoid test interdependence where possible.

4. Use synthetic data only.
   - No real provider keys, tokens, cookies, or session IDs in test data.
   - If a test needs a secret-shaped value, use a synthetic canary.
   - If a test needs PII, use synthetic PII.
   - Do not introduce test literals that look like real credentials.

5. Be explicit about skips.
   - If a test cannot run because a prerequisite is missing, name the missing prerequisite.
   - "Not run" is not "passed."
   - CI must not silently convert a missing-prerequisite case into a success.

6. For E2E, keep the contract honest.
   - State what the suite proves.
   - State what it does not prove.
   - State the CI contract: which Hermes commit, which env, which prerequisites, which run command.
   - Confirm the harness verifies the pinned core when the plugin requires it.

7. Update the doc layer when the test changes the proof status.
   - If a feature moves from "not covered" to "proven by E2E," update USAGE or VALIDATION.
   - If a test retreats to "not covered," keep the doc honest.
   - Do not let the code, the test, and the doc disagree.

8. Run the layer you changed.
   - Unit change: run `python -m pytest plugins/<plugin>/tests -q` from the repo root.
   - E2E change: run the plugin's E2E with the environment the plugin's `e2e/README.md` describes.
   - Do not assume a green full suite means the new behavior is covered.

## Pitfalls

- Writing one giant test that asserts unrelated behaviors.
- Using real credentials in test data.
- Silently skipping when a prerequisite is missing.
- Claiming E2E coverage for a behavior it does not touch.
- Updating code and tests but not the doc layer that says what is proven.
- Using an in-memory plugin return value as proof of a provider-boundary or user-visible outcome.

## Verification

- The test exercises the behavior it claims to exercise.
- The test uses synthetic data.
- The skip reason, if any, is named.
- The doc layer matches the current proof status.
- The test layer matches the kind of behavior under test.

## Wrong requirement or value

If the user wants a test that requires real credentials, a real provider, or a live production profile, say no to putting those into the repo and propose the synthetic equivalent instead. If the user wants a "proven" claim the existing tests cannot support, say what would actually prove it.
