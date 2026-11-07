# Plugin platform rules

This repo is a platform for standalone Hermes Agent plugins. Treat every new
plugin as a product, not a loose folder: one plugin = one discovery entry, one
catalog metadata file, one docs trio, one test/E2E surface, one skills surface.

Ownership stays per-plugin. Shared concerns live at repo root or `.github/`.
Never drift plugin convention sideways by copy-pasting nebula and editing the
plugin name only.

## Non-negotiables for every plugin

1. **Discovered through `plugin.yaml` / `plugin.json`.** If a folder does not
   have the repo's plugin manifest, it is not a plugin.
2. **One catalog entry in `hermes.json`.** The catalog is the authority for what
   is installed and enabled; folder presence alone is not enough.
3. **Docs trio per plugin:**
   - `README.md` — human quickstart
   - `docs/USAGE.md` — behavior contract and current status
   - `skills/<name>/SKILL.md` — agent-facing skill(s)
4. **Tests and E2E.** Every plugin needs `tests/` and, when host behavior
   matters, `e2e/`. A plugin with only syntax checks is incomplete, not broken.
5. **Reproducible ops.** Each plugin should make it easy to create, enable,
   debug, reproduce, test, and disable in a disposable profile. That guidance
   belongs in the plugin's own docs/skills, not only in repo-level notes.
6. **Owned status.** Ideas, features, gaps, known failures, and skipped paths
   must be recorded in that plugin's docs, not only in chat or PRs.

## Platform goals

- Easy to add a new plugin without inventing new policy.
- Hard to ship a plugin with missing tests, missing docs, hidden secrets, or
  undocumented behavior.
- Easy for an agent to do the boring repeatable work: scaffold, update skills,
  update docs, add E2E, update labels, run validation.
- Stable enough that plugins can appear and disappear without the repo rules
  getting messy.

## What lives where

- `hermes.json` — catalog entry.
- `update-plugins.sh` — profile sync script for the repo's plugin(s).
- `AGENTS.md` — repo onboarding and rules for humans and agents working here.
- `.github/plugin-docs-standard.md` — docs trio standard and validation before
  merge.
- `.github/templates/` — reusable templates for repeatable agent and maintainer
  tasks.
- `.github/workflows/`, `.github/labeler.yml`, and plugin-local label config —
  CI and labeling rules.
- `plugins/<id>/` — one plugin, fully self-contained in its behavior,
  tests, docs, and skills.

## How to add a plugin

Use the existing scaffold template first. A new plugin should be able to come
from a template plus its catalog entry, not from rewriting repo policy every
time.

First:
1. Add `plugins/<id>/` via the template.
2. Add its catalog entry.
3. Fill the docs trio and skills.
4. Add tests and E2E.
5. Run the repo checks: syntax, tests, dependency audit, secret scan, doc lint,
   and E2E where applicable.

Edit this file when the platform model changes, not when one plugin needs a
temporary exception.

## Guiding rule

If a rule exists to make multiple future plugins easier, put it in the platform
layer and apply it by convention/template/CI. If a concern is only about one
plugin today, keep it inside that plugin's docs/tests/skills.
