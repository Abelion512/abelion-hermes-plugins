---
name: nebula-plugin-setup
description: Set up, enable, roll back, and disable the nebula plugin.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [privacy, setup, onboarding, rollback, required-policy]
---

# Nebula Plugin Setup Skill

Install, enable, configure, and roll back the nebula Privacy Guard plugin.
Turn this into a repeatable, reversible workflow — nothing here should touch
the running process's plugin folders directly.

## When to Use

- First-time install or re-install of nebula on a profile.
- Switching between optional masking (Tahap A) and required mode (Tahap B).
- Rolling back an enable or config change without deleting the plugin.

Don't use for: understanding what the guard masks (read USAGE.md), or
debugging a live failure — that is the `nebula-plugin-debug` skill.

## Install

The profile keeps the plugin fed by `update-plugins.sh`. It expects the repo
cloned at `$HOME/.hermes/abelion-hermes-plugins`, then syncs
`plugins/nebula/` into `~/.hermes/plugins/` (it does not migrate profiles or
delete anything else).

```bash
./update-plugins.sh
```

Restart the Hermes process so a fresh load picks up plugin code. Do not
replace folders of a live-process-loaded plugin — stop the process first.

## Enable (Tahap A: optional masking)

Add `nebula` to the enabled plugin list in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - nebula
```

Masking and held-output handling start with the process; nothing is denied,
no behavior is mandatory. This is safe to flip on for daily hosts even
before a pinned commit.

## Require (Tahap B: required policy)

Required mode refuses the request before egress when a policy cannot
sanitize it — it is a denial surface, not a best-effort mask. Only anchor
this after the host is at the pinned core commit
(`9a85916c87d56c2ca00b02fad8918f93ef1816e9`, matching CI):

```yaml
security:
  require_privacy_guard: true
  privacy_guard_plugin: nebula
```

Older hosts without the pinned core raise at startup instead of silently
masking — read the error, do not disable the guard to hide a migration or
test failure. Keep `nebula` as the owner guard (the rolling config may
still contain legacy `pii-mask-abelion` names; verify which ID owns the
required policy before restart).

## Disable and Roll Back

- Remove `nebula` from `enabled` (or flip `require_privacy_guard: false`),
  then restart. Holder entries and per-session restoration maps end with
  the process — nothing persists, so there is nothing to clean on disk.
- Do not delete `~/.hermes/plugins/nebula/` from a live profile: stop the
  process first, then remove or quarantine the folder (see the monorepo
  policies docs).
- To reinstall, rewrite the config entry and re-run `update-plugins.sh`.
  The plugin catalog card in `hermes.json` is updated by repo PRs, not by
  hand on profile side.

## Verification

- Plugin loads: check the plugin list / start logs for `nebula` binding, and
  the registered skill `nebula:privacy-mask-placeholders` appearing via
  `skills_list` plus `nebula:redacted-output-handling`.
- Do one masking smoke test: send known synthetic content, e.g.
  `abelion`, a `.env`-like file path, once. A restorable PII/path token in
  the final message plus intact credentials prove the guard is talking.
- Run the unit suite from a repo checkout: `pytest plugins/nebula/tests -q`
  — green means the installed source matches the repo standard. There is no
  hermes core dependency for this suite (standalone).

## Limits

- Setup covers THIS repo's plugin. Hermes core installation or version
  management is not made or covered here.
- Nothing in this skill should ever be entered as real secrets for config —
  the plugin never needs your credentials in config; all detection is
  pattern-based.
