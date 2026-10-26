# worktree-guard-abelion

Keeps Hermes out of a repo's main checkout, automatically.

When a call would modify a git main checkout, the plugin creates a linked
worktree for the session (`<repo>-worktrees/task-<id>`, branch
`hermes/task-<id>`, from the main checkout's HEAD) and re-routes the call into
it. The model is told in the tool result. Nothing is merged or pushed.

| Call | In a main checkout |
|---|---|
| `write_file`, `patch` | path re-routed into the session worktree |
| `terminal` that writes (`git add/commit/checkout/reset/...`, `rm/mv/cp/touch/mkdir/tee`, `sed -i`, `>`) | `workdir` re-routed into the worktree |
| `read_file` | follows the worktree once it exists |
| V4A patch bodies, `.git` internals, commands naming absolute main-checkout paths, this plugin's own files | blocked, message names the worktree to use |
| worktree cannot be created (git error, 25s timeout, squatting directory) | blocked (fail closed) |

Allowed untouched: linked worktrees, paths outside any git repo (policy: only
git repos are protected), read-only commands.

Handoff: after a turn that edited files in the session worktree, `pre_verify`
asks the agent once to run the project's checks and show `git diff --stat`
before handing over.

## Install

    hermes plugins install --enable --ref <40-char commit SHA> Abelion512/abelion-hermes-plugins/worktree_guard_abelion

`--ref` needs the full SHA. Add `--force` to move an already installed copy.
Private repo: Hermes uses `GITHUB_TOKEN`, `gh auth`, or your git credential
helper. Restart Hermes afterwards.

## Switches (Hermes process env, logged at start-up when set)

- `HERMES_WORKTREE_GUARD=off` disables everything.
- `HERMES_WORKTREE_GUARD_ALLOW=/path/a:/path/b` exempts those repo roots.

## Limits

A policy hook, not an OS sandbox. The terminal check is a pattern match;
`execute_code` and creative shell commands can still write anywhere (and
running tests executes arbitrary code). The worktree starts from HEAD, so
uncommitted changes in the main checkout are not in it. Needs a Hermes with the
`pre_tool_call` `modify`/`block` directives, `transform_tool_result` and
`pre_verify` hooks (present in hermes-agent 67491b50).

## Tests

    python3 -m unittest discover -s tests -v
    HERMES_SRC=/path/to/hermes-agent python tests/e2e_dispatch.py
