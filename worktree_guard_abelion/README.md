# worktree-guard-abelion

Keeps Hermes out of a repo's main checkout. When the agent tries to edit a file
or run a mutating git/file command there, the tool call is blocked and the
message tells it the exact `git worktree add` command to run, then to work in
that worktree and review `git diff` before handing over. Nothing is merged.

Blocked in a main checkout: `write_file`, `patch` (including V4A bodies), and
`terminal` commands that look like writes (`git add/commit/checkout/reset/...`,
`rm/mv/cp/touch/mkdir/tee`, `sed -i`, `>` redirects).
Allowed: linked worktrees, paths outside any git repo, read-only commands.

## Install and enable

    hermes plugins install --enable Abelion512/abelion-hermes-plugins/worktree_guard_abelion

(or copy the folder to `~/.hermes/plugins/` and add `worktree-guard-abelion`
to `plugins.enabled`). Restart Hermes.

## Switches

- `HERMES_WORKTREE_GUARD=off` disables it.
- `HERMES_WORKTREE_GUARD_ALLOW=/path/a:/path/b` lets those repo roots be edited directly.

## Limits

This is a policy hook, not an OS sandbox. The terminal check is a pattern
match, so a creative shell command can still write elsewhere. A git timeout
(3s) blocks the call (fail closed). Enforcement covers CLI, gateway and
dashboard sessions alike because it hooks `pre_tool_call`.

## Test

    python3 -m unittest discover -s tests -v
