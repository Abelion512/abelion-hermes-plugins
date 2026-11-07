# Plugin skill — repeating authoring template

Use this when adding a skill under `<plugin>/skills/<name>/SKILL.md` or updating an existing one.

## Frontmatter rules (non-negotiable)

```yaml
---
name: <snake_case>
description: <one sentence, <= 60 chars, ends with a period.>
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [<plugin>, <tag>, <tag>]
---
```

- `name` must match `[a-zA-Z0-9_-]+`.
- `description` must be one sentence, 60 characters or fewer, ending with a period.
- No unquoted `:` inside YAML scalars.
- `---` must start at byte 0 of the file.

## Body template

```markdown
# <Readable skill title>

One short paragraph: what this skill is for and which plugin it belongs to. Keep it readable; this is guidance, not a contract dump.

## When to Use

- ...
- Don't use for: ...

## How to Apply

1. ...
2. ...

Use Hermes tools (`read_file`, `terminal`, `skill_view`) to describe steps; do not hardcode machine-local paths.

## Pitfalls

- ...
- ...

## Verification

...

## Wrong requirement or value

Say what happens on a bad input, and that the agent must not claim success or silently swap in a different value. If the plugin has an ordered-validation doc, point at it.
```

## Registration reminder

The skill must also be registered in `<plugin>/__init__.py` through `ctx.register_skill(...)`, guarded by `getattr(ctx, "register_skill", None)`. A skill that lives on disk but is not registered is not discovered by Hermes; that is a bug, not a feature.

## One skill, one job

If you are tempted to write a second "overview" skill that duplicates the first, stop and merge the guidance into the skill the agent will actually load. Multiple near-duplicate skills are worse than one clear one.

## Update discipline

When the plugin behavior changes, update the skill in the same change. A skill that says one thing and the plugin does another is worse than no skill.
