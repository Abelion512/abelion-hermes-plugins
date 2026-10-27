# shield-abelion - mechanism reference

## Registered callbacks

| Registration | Callback | Source |
|---|---|---|
| `pre_tool_call` hook | `_hook` - runs the four guards in order | `__init__.py` |
| `post_tool_call` hook | `on_tool_result` - feeds success/error to the circuit breaker | `circuit_breaker.py` |
| `on_session_end`, `on_session_finalize` hooks | `_snapshot` - writes guard state JSON | `__init__.py` |
| skill | `blocked-tool-recovery` via `ctx.register_skill` | `skills/` |

Guard order inside `pre_tool_call`: read-before-edit → safety blocklist →
loop detector → circuit breaker. First block wins; a pass means `None` and
the tool runs.

## Behavior details

- **Read-before-edit** (`safety_guard.py`): tracks `read_file` paths per
  `session_id` in memory. Write tools are `write_file`, `edit`, `patch`,
  `write`. Targets `.` and `/` are exempt. Block message tells the agent to
  `read_file` the path first.
- **Safety guard** (`safety_guard.py` `DANGEROUS_REGEXES`): applies to
  `terminal`, `bash`, `execute_code`, `write_file`, `patch`. Reads the
  command from the first non-empty of `cmd`/`command`/`code`/`content`/`path`
  args. Patterns cover `rm -rf` on system roots, `dd`/`mkfs`/`fdisk` on raw
  disks, `chmod 000` on system paths, recursive `chown`, `wget|curl … | bash`,
  `sudo rm -rf`, direct writes to `/dev/sdX`.
- **Loop detector** (`loop_detector.py`): sliding window of the last 10
  calls; blocks when the newest call equals the previous 2 (3 identical in a
  row). Comparison is `tool_name` plus `str(args)`.
- **Circuit breaker** (`circuit_breaker.py`): per tool name; 3 consecutive
  `status == "error"` results open it for 30 s, then one half-open trial.
  Success resets the count.

## State files

Written by the session-end snapshots under `$HERMES_HOME/shield/protect/`:
`read_history.json`, `loop_detector.json`, `circuit_breaker.json`.
Diagnostics only - nothing reads them back at startup.

## Configuration

None. Thresholds (3 identical calls, 3 failures, 30 s recovery) are constants
in the modules listed above.
