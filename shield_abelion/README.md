# shield-abelion

Pre-execution guard for Hermes tool calls. Four checks run before a tool fires,
and a circuit breaker watches tool health after each call.

| Guard | Trigger | Effect |
|---|---|---|
| Read-before-edit | `write_file` / `edit` / `patch` / `write` on a path not yet read this session | Blocks with 📖 until you `read_file` it |
| Safety guard | Hard blocklist (`rm -rf /`, `dd` to raw disk, `curl\|bash`, recursive `chown`, …) in `terminal` / `bash` / `execute_code` / `write_file` / `patch` | Blocks with 🚫, asks for explicit user approval |
| Loop detector | Same tool + identical args 3 times in a row | Blocks with 🛑 |
| Circuit breaker | A tool errors 3 times consecutively | Opens for ~30 s, blocks with ⛔ |

Blocked calls never execute; the agent gets the block message as the tool
result and recovers (see the bundled skill below).

## Install

From a clone of this repo, or straight from GitHub (private repo - needs the
GitHub access already on the machine):

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/shield_abelion
```

## Verify

```bash
hermes plugins list                 # shield-abelion shows enabled
hermes plugins doctor shield_abelion
```

In a chat, ask the agent to edit a file it has not read yet: the 📖 block
should fire. `skills_list` shows `shield-abelion:blocked-tool-recovery`, and
`skill_view("shield-abelion:blocked-tool-recovery")` loads the agent guide.

## Limits

- Pattern-based, not a sandbox. The blocklist catches known catastrophic
  shapes; a command that does not match is not reviewed. It is one layer, not
  proof a command is safe.
- The loop detector only counts *consecutive identical* calls; a loop that
  varies its args is invisible to it.
- The circuit breaker counts errors per tool name, per process; restarting
  Hermes resets it.
- Guard state snapshots are written at session end under
  `$HERMES_HOME/shield/protect/` (diagnostics only).

## Disable / rollback

```bash
hermes plugins disable shield-abelion   # keep installed, turn off
hermes plugins remove shield-abelion    # uninstall
```

## Bundled agent skill

`blocked-tool-recovery` - tells the agent how to answer each block type.
Registered automatically while the plugin is enabled, on Hermes builds with
`ctx.register_skill` (API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); older hosts load the plugin
without the skill. See [docs/USAGE.md](docs/USAGE.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
