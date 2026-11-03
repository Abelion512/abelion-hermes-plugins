---
name: TODO
description: TODO
version: TODO
platforms: [linux, macos, windows]
---

# TODO plugin skill coverage

This is the skill surface for this plugin. Each skill here should be usable by
an agent when relevant and visible only when the plugin is loaded.

## What this skill set covers

This plugin's skills should answer these questions:

- How to create this plugin (from template, manifest, dependencies, registry).
- How to use it (enable, config, disabled behavior, rollback).
- How to debug it (log points, replay, common denials, failed policy behavior).
- How to reproduce issues (disposable profile, synthetic inputs, loopback
  provider, E2E when applicable, enough to repeat a bug without live data).
- How to test it (unit tests, integration/E2E, validation matrix, fixtures,
  known skipped paths).
- Any internal ops skill for this plugin (for example: mask handling, held
  output handling, session-map behavior, restore boundaries).

If a skill would only be useful when another plugin or part of the repo is
involved, consider whether it belongs here or at the platform layer.

## Skill authoring standard

Follow the repo's plugin skill standard. A skill is not a README. It should be:

- Short and actionable.
- Clear about when to use it and when not to use it.
- Grounded in real commands/tools for this plugin, not generic advice.
- Honest about limits and what is not covered.

One plugin may have more than one skill. Avoid one huge skill that tries to be
everything.

## Maintenance rule

Every meaningful plugin behavior or operational concern should have an owner in
`docs/` or `skills/`. If a behavior is important enough to document in chat or
in a PR description, it should live in the plugin's own docs/skills.

## Link from plugin docs

`docs/USAGE.md` must point at this skill set and explain which skill covers
which concern. Do not leave skill coverage as implicit.
