# Plugin tests — repeating authoring template

Use this when adding or updating `<plugin>/tests/` or `<plugin>/e2e/`.

## Two layers, both required over time

- Unit/regression: `<plugin>/tests/` — fast, deterministic, no real provider, no real credentials.
- Real-host E2E: `<plugin>/e2e/` — real Hermes process, disposable profile, synthetic only.

A plugin that only has unit tests is incomplete for behavior that touches the host boundary. A plugin that only has E2E is incomplete for fast feedback and adversarial coverage.

## Unit test template

```python
"""One-line scope of what this file proves."""
import pytest

def test_<behavior>_<case>():
    # Arrange
    # Act
    # Assert: one clear concern
```

- One file per behavior area.
- Shared fixtures go in `<plugin>/tests/conftest.py`.
- Keep tests deterministic. Avoid "maybe passes on my machine" fixtures.

## E2E test template

```python
"""One-line scope. Synthetic only; no real provider or credentials."""
import pytest

# Mark/skip rules must be explicit: NOT RUN is not the same as PASS.
```

E2E files must say:

- What the suite proves
- What it does not prove
- The CI contract (which Hermes commit, which env, which prerequisites)
- The run command

## Dependency pins: plugin deps vs host deps

Two different things live in a plugin's requirements files, and mixing them up makes
CI prove behavior on a runtime the plugin never runs on.

- Plugin dependency: declared in `plugin.yaml` `python_dependencies`, mirrored exactly in
  `plugin-requirements.txt`. CI enforces that mirror (`plugin dependency mirror` step).
  Bump it in both files in the same change.
- Host dependency: the web framework versions the pinned Hermes managed env actually
  ships (`fastapi` / `starlette` / `uvicorn` / `websockets` today). These are pinned in
  `<plugin>/tests/requirements-test.txt` so the suite runs against the real host runtime.
  Never bump them on their own; re-pin only after the pinned Hermes core moves, and
  record the new versions in the plugin's `docs/VALIDATION.md`.

Dependabot cannot see the host pins, so it will try to bump them. They are listed under
`ignore:` in `.github/dependabot.yml`. If you need a different runtime, change the
managed env first, not the test file.

A floor is a security claim: `aiohttp>=3.10,<4` says 3.10 is acceptable, and pip resolves
to the newest allowed version, so a plain `pip-audit -r` never sees that the floor is
vulnerable. CI's `dependency floor audit` step pins each declared floor and audits that
oldest version, on every push and weekly. If it fails, raise the floor in `plugin.yaml`
and the mirror together; do not lower it to silence the check.

## Synthetic-only rule

- No real provider keys, tokens, cookies, or session IDs in test data.
- If the test needs a secret-shaped value, use a synthetic canary that cannot be a real credential.
- If a test touches a subprocess, do not let it inherit the full host environment; use an allowlist.

## Status discipline

Every feature claim needs a home:

- Unit test for in-plugin logic
- E2E test for host-boundary behavior
- Doc row that says "Proven by E2E" or "Not covered" honestly

A feature is not "proven" because CI is green in general. It is proven because there is a test for it and the doc says so.

## What to avoid

- Mega-tests that assert five unrelated behaviors
- E2E that silently skips when prerequisites are missing, unless the skip reason is named and intentional
- Tests that assert against the plugin's in-memory return value when the real question is what the provider or user actually saw
- New test data that looks like a real credential

## Maintenance

- When the plugin changes, update the matching tests in the same change.
- When a test is retired, say why in the code or docs; do not just delete it and hope the next person reconstructs the intent.
