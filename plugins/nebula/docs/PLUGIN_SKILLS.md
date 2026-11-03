# Nebula skills coverage

This plugin ships skills for agent-facing operations. The main skill today is
`nebula:privacy-mask-placeholders`, registered through native `ctx.register_skill`
and visible in `skills_list` and `skill_view` while the plugin is enabled. The
plugin also adds a short session prompt note through
`register_system_prompt_section`.

## What this plugin's skills should cover

- How to create the plugin from the repo template and catalog entry.
- How to use it locally: enable, config, rollback, disable, and disposable-profile
  workflow.
- How to debug it: where to look when masking fails, when policy denies, and how
  to tell whether the issue is the plugin, the host, or missing required-core
  behavior.
- How to reproduce issues: disposable profile, synthetic inputs, loopback
  provider, and E2E when host behavior is involved.
- How to test it: unit tests, the validation matrix, known skipped paths, and E2E
  gaps.
- Internal operational skill coverage: placeholder handling, held-output handling,
  restore boundaries, and what is intentionally not restored.

## Current skill surface

- `skills/privacy-mask-placeholders/SKILL.md`
- `skills/redacted-output-handling/SKILL.md`

If a future capability needs its own skill, add it under `skills/<name>/SKILL.md`
and register it in the plugin init path. Do not expand a skill until the
behavior is real, grounded, and discoverable.

## Rule

If a behavior is important enough to explain in chat, it should also exist as a
skill or docs entry owned by this plugin.
