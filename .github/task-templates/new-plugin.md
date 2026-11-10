# New plugin — repeating setup template

Use this when adding a plugin folder that will live under `plugins/<id>/` and be shipped by this monorepo. Adapt the names; do not leave obvious placeholders like `<plugin>` in the final commit.

## 1. Decide the stable identifier first

- Folder: `plugins/<stable-id>/`
- Hermes plugin `name` in `plugin.yaml`: the installed plugin name
- Monorepo public ID used by `hermes.json`, `update-plugins.sh`, README, labeler: pick one stable token and reuse it everywhere

Do not rename a plugin's public identity later just because the internal folder layout changed.

## 2. Minimal skeleton a plugin must have before it counts as "in the repo"

```
plugins/<id>/
├── plugin.yaml
├── __init__.py
├── README.md
├── docs/
│   ├── USAGE.md
│   └── VALIDATION.md
├── skills/
│   └── <name>/
│       └── SKILL.md
├── tests/
│   ├── conftest.py
│   └── <first behavior area>.py
└── e2e/
    ├── README.md
    ├── conftest.py
    └── <first real-host behavior>.py
```

A plugin folder without the doc trio plus at least one test layer is incomplete, even if the code works.

## 3. plugin.yaml

Keep it honest and minimal. If the plugin has no Python deps, do not add an empty deps list just to look complete.

```yaml
name: <installed plugin name>
description: "<one line.>"
version: <sem-like release label>
author: Abelion
kind: standalone
python_dependencies:
  - "<dep>"   # only if the plugin actually imports it
metadata:
  hermes:
    category: <security | dashboard | ...>
    tags: [<tag>, <tag>]
    config:
      <key>: <value>   # only if the plugin owns a documented config knob
```

## 4. __init__.py

Guard everything that depends on a newer host API.

```python
def register(ctx):
    register_skill = getattr(ctx, "register_skill", None)
    if callable(register_skill):
        from pathlib import Path
        register_skill("<skill-name>", Path(__file__).parent / "skills" / "<name>" / "SKILL.md",
                       "<short description.>")
    # hooks / middleware / prompt sections only if the host supports them
```

If the plugin refuses legacy hosts, say so explicitly and raise/return in a way that matches the plugin's contract. Do not silently degrade into a leaking mode.

## 5. Wire it into shared metadata

Update in the same change:

- `hermes.json` → add to `plugins[]`
- `update-plugins.sh` → add to the sync list
- Root `README.md` → add a row to the active plugin table
- `.github/labeler.yml` → add the plugin label(s)
- `.github/task-templates/README.md` → mention the new plugin only if it changes the repeating-task shape

## 6. Doc trio first

Write `README.md`, `docs/USAGE.md`, `docs/VALIDATION.md` before the first feature is called "supported." USAGE must list every registered hook/middleware/skill with its source file and behavior; VALIDATION must say what each test layer proves and what it does not.

If the plugin bundles third-party viewer/runtime code, also add `docs/VENDOR.md` with source, license, and provenance.

## 7. First tests

- One unit/regression area in `tests/` that exercises the plugin's own logic without a real Hermes host.
- One real-host E2E area in `e2e/` with synthetic data and a disposable profile.
- `e2e/README.md` describing the CI contract and limits.

Do not claim an E2E proves something it only skips.

## 8. CI and release hygiene for the new plugin

- Syntax check: `python -m compileall -q plugins/<id>` and shell-check any `.sh`.
- Dependency audit: `pip-audit` on the plugin's `requirements*.txt` / `plugin-requirements.txt`.
- Dependency mirror: if `plugin.yaml` lists `python_dependencies`, ship a
  `plugin-requirements.txt` that mirrors it line for line. CI fails on drift.
- Host pins: any web-stack version in `tests/requirements-test.txt` must match the
  pinned Hermes managed env, and be listed under `ignore:` in `.github/dependabot.yml`
  so Dependabot does not move it.
- Secret scan: the repo-level `secret-scan` job already covers the whole tree; do not add per-plugin secret logic that weakens it.
- If the plugin needs extra CI shape, add that shape in the shared workflow, not as a one-off script that only the author remembers.

## 9. Default limits to state early

- What the plugin does not cover
- What "required" means, if anything, and which host contract it needs
- What state is memory-only, disk-backed, session-scoped, or shared
- What credentials/tokens/paths it does and does not handle

State limits before users rely on them.
