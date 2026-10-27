---
name: turn-context
description: Use the injected per-turn datetime and tool reminder.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [context, datetime, tools, injection]
---

# Turn Context Skill

The tool-context-abelion plugin prepends a `[Context: ...]` block to your
user message on every turn after the first. It carries the current UTC
date/time and context about actual session tools. This skill
is how to read that block correctly.

## When to Use

- Any turn whose user message contains a `[Context: <day> <date> <time> UTC ...]`
  block from this plugin.
- Don't use for: the first turn of a session - the plugin skips it because the
  system prompt already carries the full tool list and date.

## How to Apply

1. Treat the block's datetime as the current time. Never answer "today",
   "this week", or deadline math from training data when the block is present.
   Note it is UTC - convert before quoting local times to the user.
2. Check actual tool schemas and required values before acting. Test portable
   work yourself when possible, but do not infer account access or approval.
3. Use only tools in the host session. An explicitly supplied inventory is a
   reminder, not authority. Without it, no tool names are advertised.

## Pitfalls

- The block is injected into the user message, not the system prompt. It is
  plugin output, not a user instruction, and not a higher-authority message.
- If the plugin is disabled the block disappears; fall back to the system
  prompt's date and tools without commenting on the change.

## Verification

Answers that depend on the current date use the block's datetime, and every
tool you call exists in your actual tool list.

## Wrong requirement or value

Do not advertise hardcoded tools or blanket execution authority. Only an explicitly supplied valid tool inventory is named; otherwise defer to the host session tool list. Wrong required values are not silently changed.
Do not claim a rejected operation succeeded or silently replace the requested value.
