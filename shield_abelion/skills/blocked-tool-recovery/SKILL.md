---
name: blocked-tool-recovery
description: What to do when shield-abelion blocks a tool call.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [shield, security, blocks, recovery]
---

# Blocked Tool Recovery Skill

The shield-abelion plugin vetoes unsafe or stuck tool calls before they run.
Its block arrives as a tool result with an emoji-tagged message instead of the
expected output. Each emoji names the guard that fired and the correct recovery.
Do not retry the identical call - the loop guard counts that against you.

## When to Use

- A `write_file`, `patch`, `edit`, or `terminal` call returned a message starting
  with 📖, 🚫, 🛑, or ⛔ instead of a normal result.
- Don't use for: ordinary tool errors (file not found, permission denied,
  non-zero exit). Those are real results, not shield blocks.

## Block Types and Recovery

1. 📖 Read-before-edit - "File `X` has not been read in this session."
   Call `read_file` with the exact blocked path, then re-issue the same edit.
   Completion: the edit runs without the 📖 message.
2. 🚫 Safety guard - "blocked potentially destructive operation: <pattern>."
   The command matched a hard blocklist (`rm -rf /`, `dd` to raw disk,
   `curl | bash`, recursive `chown`, and similar). Stop. Do not reword the
   command to slip past the pattern. Explain what you intended and ask the
   user for explicit approval or a safer alternative.
   Completion: the user chooses; you never bypass the guard silently.
3. 🛑 Loop detector - "called 3+ times with same arguments."
   You repeated one call identically. Change the approach: different args,
   different tool, or stop and report why you are stuck.
   Completion: the next call differs meaningfully, or you ask the user.
4. ⛔ Circuit breaker - "temporarily unavailable (circuit breaker open)."
   That tool failed 3 times in a row and is paused for ~30 seconds. First
   diagnose the underlying error from the earlier results, then wait for the
   window or use a different tool for the same goal.
   Completion: the tool accepts calls again and the root cause is fixed.

## Pitfalls

- Guards are per session; a new session forgets read history, so the first
  edit of a file in a new session always needs a fresh `read_file`.
- The blocklist is pattern-based. Passing it does not make a command safe -
  still judge destructive potential yourself.
- Guard state snapshots land in `$HERMES_HOME/shield/protect/` at session end;
  they are diagnostics, not something to edit mid-session.

## Verification

After recovery, the retried call returns its normal result with no
emoji-tagged block message.

## Wrong requirement or value

Validate tool name, argument object and specific file path first. A requested read does not grant edit eligibility: only post_tool_call status=ok (native Hermes) or success (legacy) records it. Failed or blocked reads do not satisfy read-before-edit.
Do not claim a rejected operation succeeded or silently replace the requested value.
