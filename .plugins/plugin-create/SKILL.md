---
name: plugin-create
description: Create a new plugin scaffold and wire it into this monorepo.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [plugin, create, scaffold, monorepo, hermes-plugins]
---

# Plugin Create Skill

This repo is a monorepo for standalone Hermes Agent plugins. Every plugin owns its implementation, docs, unit tests, skills, and feature-specific E2E. This skill is how you add a new plugin folder and wire it into the shared metadata, CI, labeler, and README without leaving the repo half-updated.

Use this when the user asks to add a plugin, or when a feature clearly belongs in a new plugin rather than bolting onto an unrelated existing plugin.

## When to Use

- Starting a new plugin that will live under `plugins/<id>/`.
- Adding the first doc layer, skill, test, or E2E for a plugin that already has code.
- Updating `hermes.json`, `update-plugins.sh`, CI, labeler, and root README for a new plugin.

Do not use for routine edits inside an existing plugin; use the plugin's own skill or docs instead. Do not use to copy a plugin into a live profile; this repo is source, not an installer for a running Hermes home.

## How to Apply

1. Pick a stable plugin identity first.
   - Folder: `plugins/<stable-id>/`
   - Installed plugin name in `plugin.yaml`
   - Monorepo public ID used by `hermes.json`, `update-plugins.sh`, README, and labeler
   - Reuse the same public ID everywhere. Do not let the folder name, installed name, and labeler name drift apart.

2. Create the minimal scaffold before the plugin counts as "in the repo":
   - `plugin.yaml`
   - `__init__.py`
   - `README.md`
   - `docs/USAGE.md`
   - `docs/VALIDATION.md`
   - `skills/<name>/SKILL.md`
   - `tests/conftest.py`
   - `tests/<first area>.py`
   - `e2e/README.md`
   - `e2e/conftest.py`
   - `e2e/<first real-host behavior>.py`

   A plugin folder without the doc trio plus at least one test layer is incomplete, even if the code runs.

3. Write `plugin.yaml` honestly and minimally:
   - `name`, `description`, `version`, `author`, `kind`
   - `python_dependencies` only if the plugin actually imports the dep
   - `metadata.hermes.category` and `tags` that help triage, not spam

4. Write `__init__.py` guarded by host capability:
   - Use `getattr(ctx, "register_skill", None)` before registering skills.
   - Guard hooks/middleware/prompt sections by the host API they need.
   - If the plugin refuses legacy hosts, say so explicitly and do not silently degrade into a leaking mode.

5. Wire the plugin into shared metadata in the same change:
   - `hermes.json` → `plugins[]`
   - `update-plugins.sh` → sync list
   - Root `README.md` → active plugin table row
   - `.github/labeler.yml` → plugin label(s)
   - `.github/workflows/ci.yml` only if detection, labeler, or shared behavior changes

6. Write the doc trio first if it is missing:
   - `README.md`: human quickstart, required host only when it truly matters, install, verify, disable/rollback, honest limits, bundled skill pointer.
   - `docs/USAGE.md`: every registered hook/middleware/skill with source file, behavior, state, config or "None", known limits, and a status table.
   - `docs/VALIDATION.md`: ordered validation and the unit vs real-host E2E split, with what each layer proves and what it does not.

7. Add the first tests in both layers when the behavior warrants it:
   - Unit/regression in `tests/` for in-plugin logic.
   - Real-host E2E in `e2e/` for host-boundary behavior, synthetic only.
   - `e2e/README.md` with the CI contract, layout, run command, and what it does not prove.

8. If the plugin bundles third-party viewer/runtime code, add `docs/VENDOR.md` with source, license, and provenance.

9. Before calling the job done, run the review-before-merge checklist in `.github/task-templates/review-before-merge.md`.

## Pitfalls

- Creating the folder and code but skipping the doc trio and tests. That is not "plugin done"; that is "plugin started."
- Letting the folder name, installed plugin name, monorepo public ID, and labeler name diverge.
- Adding `python_dependencies` that the plugin does not actually import.
- Registering a skill that lives on disk but is not wired through `ctx.register_skill`.
- Editing `hermes.json` or the sync list and then forgetting the labeler, or vice versa.
- Claiming a feature is proven because CI ran, when no test was written for that feature.
- Adding priority labels without a rule or doc explaining them.

## Verification

- The new plugin folder exists under `plugins/<id>/` with the doc trio and at least one test layer.
- `hermes.json`, `update-plugins.sh`, root README, and labeler all mention the plugin consistently.
- `python -m compileall -q plugins/<id>` and any shell scripts pass.
- `pip-audit` can run against the plugin's declared requirements files if present.
- The diff does not introduce new credentials, tokens, keys, cookies, session IDs, or secret-shaped test data.

## Wrong requirement or value

If the requested plugin identity is unstable, ask for the stable public ID before creating folders and wiring shared metadata. If the user wants a feature but the plugin shape is not yet clear, prefer the smallest honest scaffold and record the open decisions in `docs/IDEAS.md` rather than inventing a broad plugin spec.
