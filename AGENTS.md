# AGENTS.md — Abelion Hermes Plugins

This is a monorepo for standalone Hermes Agent plugins. It is built to grow beyond a single plugin, so the repo has a [plugin platform standard](docs/PLUGIN_PLATFORM.md) plus reusable templates for docs, skills, tests, E2E, labels, and repeat maintenance work.

Right now there is one active plugin, **Privacy Guard (nebula)**: session-local PII/credential/path masking, held-output redaction, and optional-mode request middleware.

## Repo map

- `hermes.json` — plugin catalog. Currently one entry: `nebula`.
- `plugins/nebula/` — Privacy Guard plugin.
  - `guard.py` — session-local guard: `<HG:...>` mapping, request walk, `required_policy`, `tool_request`, `output`.
  - `pii_middleware.py` — optional `llm_request` middleware: sensitivity levels, copy-on-write masking.
  - `output_redact.py` — `transform_llm_output` hook: parenthetical credential pattern + native Hermes redactor.
  - `_credentials.py` — field-name + vendor-prefix secret detection.
  - `_patterns.py` — shared prose parenthetical credential patterns.
  - `skills/` — two registered skills: `privacy-mask-placeholders`, `redacted-output-handling`.
  - `docs/` — `USAGE.md`, `VALIDATION.md`.
  - `tests/` — standalone plugin tests.
  - `e2e/` — real-host E2E with loopback provider.
- `docs/SESSION_HISTORY.md` — plugin session notes (mask/restore discussion, test status, open items).
- `docs/title-reference.md` — internal naming tiers; cosmic/Latin names only, no external model labels.
- `update-plugins.sh` — syncs `plugins/nebula/` into `~/.hermes/plugins/`. Does not migrate profiles.
- `.github/workflows/ci.yml` — syntax, unit tests, dependency audit, real-host E2E, gitleaks.
- `.github/e2e_support/abelion_e2e_support/` — shared Hermes+E2E harness used by plugin E2E suites.
- `.github/retired-source-recovery.md` — how to recover old Shield/tool-context/RSI source from a pinned commit.

## The plugin

### What it does

- Detects secrets, PII, paths, cookies/session material, media/unsupported payloads.
- Masks them with per-session `<HG:nonce:hex24>` tokens in process memory only.
- Required mode denies before egress when policy can't sanitize; optional mode masks but does not deny.
- Credentials never restore. CLI final may restore exact known PII/path tokens into documented local path tool slots (`read_file`, `write_file`, `patch`, `search_files`). Shell, URLs, messages and delegate goals are blocked, not interpolated.
- Native Hermes output redaction runs before allowed CLI restoration.

### What it does not do

- It is not a process-wide network firewall.
- It does not cover direct tool/service traffic, MCP, TTS/STT, media generation, unknown secret encodings, persisted prompts, UI/logs, or unsupported provider transports.
- Stock Hermes is not equivalent mandatory protection. Required mode needs the pinned core.

## Required host

Mandatory privacy requires Hermes fork commit `9a85916c87d56c2ca00b02fad8918f93ef1816e9` from `Abelion512/hermes-4gent`. CI checks out that exact commit for the E2E job and verifies the imported source matches.

## Local dev

### Unit tests

```bash
pytest plugins/nebula/tests -q
```

Known issue: `test_pathological_inputs_do_not_blow_up` can fail on slow hardware because its 2.0s bound is tight. Deselect it rather than loosening it.

### E2E tests

```bash
HERMES_PYTHON=/path/to/pinned/hermes/venv/bin/python \
HERMES_EXPECTED_COMMIT=9a85916c87d56c2ca00b02fad8918f93ef1816e9 \
REQUIRE_HERMES_E2E=1 \
pytest plugins/nebula/e2e -v -rs
```

E2E is skipped when `HERMES_PYTHON` does not point at an importable Hermes install. When the harness is enabled, it exits as a failure rather than silently skipping if Hermes is not importable or the imported HEAD does not match `HERMES_EXPECTED_COMMIT`. It uses a synthetic loopback provider and disposable profiles only; no real provider or credentials are involved.

### Install into a Hermes profile

Use `update-plugins.sh`. It expects the repo cloned at `$HOME/.hermes/abelion-hermes-plugins` and syncs `plugins/nebula/` into `~/.hermes/plugins/`. It does not migrate profiles, change privacy settings, or remove old installed plugins.

For a disposable test profile with required mode:

```yaml
plugins:
  enabled:
    - nebula
security:
  require_privacy_guard: true
  privacy_guard_plugin: nebula
```

Restart the process and start a new session.

## Conventions

- Plugin folder and runtime ID are both `nebula`. That is intentional; the core owner setting and E2E harness expect it.
- One active plugin, one output hook, one required-policy owner. Consolidated plugin replaced the earlier separate `output-redact-abelion` plugin; stale copies do not disappear automatically.
- Skills are registered through native `ctx.register_skill` and `register_system_prompt_section`. Older hosts without those APIs skip them; README alone is not automatic discovery.
- Naming theme is cosmic/Latin (`nebula`, `nova`, `aurora`, ...). No `-abelion` suffixes, no external model-tier labels.
- Test data is synthetic/local-only. No cloud accounts, no real credentials in tests. Public-known credential shapes are tested with fake bodies and must stay masked and non-restorable.
- Every behavior change: edit the code, update the plugin's `docs/USAGE.md` status table and/or ideas docs, and add/change the matching test and/or E2E in the same commit. A behavior is "Proven" only when its E2E passes.

## Security and privacy rules for agents working here

- Do not paste real secrets, cookies, map values, or account identifiers into code, docs, skills, or prompts.
- Do not claim this plugin makes stock Hermes or any laptop/provider "safe" or "protected". It is evidence for one pinned commit and the tested paths.
- Do not disable required Privacy Guard just to hide a migration or test failure.
- Do not delete plugin directories from a live profile. Stop the process first.

## Decisions already made

- Plugin renamed from `pii_mask_abelion` to `nebula` during the monorepo refactor.
- Round-trip test pattern `abelion -> username -> abelion` is readable by design so mask/restore success is verifiable.
- All verification uses local model inference; test prompts do not go to cloud providers.
- No transformer dependency; standalone tests run without `agent.redact`, and restore behavior is monkeypatched in tests.
- Title reference doc defines internal tiers; do not reuse external model names as capability labels.

## Open items from session history

- `test_pathological_inputs_do_not_blow_up` threshold may need a hardware-adjusted bound.
- E2E blocked when `HERMES_PYTHON` is missing or the commit does not match.
- Opencode activation issues are not required for plugin tests.
- `AGENTS.md` was pending manual creation; this file covers that.

## If you are adding another plugin

- Follow the plugin platform standard in [docs/PLUGIN_PLATFORM.md](docs/PLUGIN_PLATFORM.md) and the docs trio standard in [.github/plugin-docs-standard.md](.github/plugin-docs-standard.md).
- Start from the repo templates under [.github/templates/](.github/templates/) so repeated work stays repeatable: plugin docs, skills, ideas/feature docs, tests, E2E, and status tables.
- Add it under `plugins/<id>/` with its own README, docs, tests, e2e, skills, plugin-local labels if useful, and a catalog entry in `hermes.json`.
- Keep feature policy/UI in the plugin repo; host enforcement, lifecycle, and execution guarantees belong in the Hermes core fork.
- Do not vendor or duplicate the `decolua/9router` router here.
