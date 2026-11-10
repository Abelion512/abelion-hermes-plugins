# Repeating agent tasks — templates

These templates describe the *shape* every repeating agent task in this repo should follow. Use them as the starting structure, not as copy-paste filler: fill in the plugin-specific facts, keep the honest limits, and update the existing docs/tests/status tables in the same change.

## When to use these

- Adding or changing a plugin feature
- Adding or changing a plugin skill
- Adding or changing plugin docs
- Adding or changing plugin tests / E2E
- Updating `hermes.json`, `update-plugins.sh`, CI, or the labeler for a new plugin

Do not start a plugin change until the affected plugin already has the three doc layers (README → docs/USAGE.md → skills) and at least one test layer. If a plugin folder is missing one, that is the first fix, not a follow-up.

## 1. New plugin feature / idea

File: `<plugin>/docs/IDEAS.md` (new feature candidates and decisions, plugin-scoped)
Every implemented feature also gets a row in `<plugin>/docs/USAGE.md` and, where relevant, a status row in `<plugin>/docs/VALIDATION.md` or the USAGE status table.

Template:

```markdown
# <plugin id> — feature ideas and decisions

Keep feature candidates here before they are implemented, and keep the decision after they land. One block per idea. Delete a block only when the idea is abandoned, not when it ships; shipped ideas move into USAGE.md and the relevant status table.

## <short name>

- **What:** one sentence.
- **Why:** one or two sentences.
- **Scope:** plugin / core / shared. If core, say which contract and which repo owns the enforcement.
- **Status:** idea / underway / done / abandoned
- **Landed in:** commit / none yet
- **Tests added:** unit yes/no, E2E yes/no, which files
- **Docs updated:** README, USAGE, skill, VALIDATION — list the files touched
- **Limits / what is still not covered:** be explicit
```

Rule: a feature is not "proven" until its test row says so. A green test run that was not written for the feature does not count.

## 2. New plugin skill

Template (Skill.md frontmatter + body):

```yaml
---
name: <snake_case skill name>
description: <one sentence, <= 60 chars, ends with a period.>
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [<plugin>, <tag>, <tag>]
---
```

Body skeleton:

```markdown
# <Skill title>

One short paragraph: what this skill is for and which plugin it belongs to.

## When to Use

- ...
- Don't use for: ...

## How to Apply

1. ...
2. ...

## Pitfalls

- ...

## Verification

...

## Wrong requirement or value

... say what happens on a bad input, and that the agent must not claim success or silently swap in a different value.
```

Register the skill in `<plugin>/__init__.py` through `ctx.register_skill(...)`, guarded by `getattr(ctx, "register_skill", None)`.

## 3. New plugin docs

Every plugin keeps three layers. Do not add a fourth "meta" doc layer per plugin; keep the standard trio plus, where useful, `docs/IDEAS.md` and `docs/VENDOR.md` (provenance only).

Template for the trio:

- `README.md` — human quickstart: what it does, required host/version only when it truly matters, install, verify, disable/rollback, honest limits, bundled skill pointer.
- `docs/USAGE.md` — mechanism reference for maintainers and reviewing agents: every hook/middleware/skill with source file, behavior, state, config (or "None"), known limits, and a status table.
- `docs/VALIDATION.md` — ordered validation: input → type/shape → requirement/value → effect → confirmed outcome, plus the test-layer split (unit vs real-host E2E) and what each layer proves.

## 4. New plugin tests

Unit/regression:

- `<plugin>/tests/` — fast, deterministic, no real provider, no real credentials.
- `conftest.py` at plugin level for shared fixtures.
- One test file per behavior area.
- Prefer one assertion per logical concern; avoid mega-tests that assert five unrelated things.

E2E:

- `<plugin>/e2e/` — real Hermes process, disposable profile, synthetic only.
- `e2e/README.md` — what the suite proves, CI contract, layout, run command, what it does *not* prove.
- Shared host/profile harness lives under `.github/e2e_support/` so multiple plugins can reuse one canonical implementation.
- E2E is additive, not a replacement for unit tests.

Test template header:

```python
"""One-line scope. Synthetic only; no real provider or credentials."""
import pytest
```

## 5. New plugin update (shared infra)

When a plugin is added or removed from the active set, update in one change:

- `hermes.json` → `plugins[]`
- `update-plugins.sh` → `for d in ...`
- `.github/workflows/ci.yml` → only if the change touches detection/labeler/shared behavior
- `.github/labeler.yml` → plugin labels, and any new priority/label taxonomy if needed
- Root `README.md` → plugin table
- This template doc, if the new plugin changes the repeating-task shape

## 6. "Did this change actually land?" checklist

Before marking the task complete, confirm:

- [ ] Plugin code updated
- [ ] `docs/USAGE.md` updated (behavior/hooks/limits)
- [ ] Status table / VALIDATION updated to reflect the real proof
- [ ] Skill updated or added and registered
- [ ] Test added or updated in the right layer (unit or E2E)
- [ ] `hermes.json` and `update-plugins.sh` synced if plugin set changed
- [ ] No new hardcoded credentials, tokens, keys, cookies, or session IDs in the diff
- [ ] CI still makes sense for the new shape (detection, labeler, audit, secret scan)

A change that touches the plugin but not its docs/tests is incomplete by default.
