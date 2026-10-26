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

## Install (check first, enable second)

Use a disposable repo for the first real run, not a project you care about.

    hermes plugins install --no-enable --ref <40-char commit SHA> Abelion512/abelion-hermes-plugins/worktree_guard_abelion
    python3 ~/.hermes/plugins/worktree-guard-abelion/preflight.py
    hermes plugins enable worktree-guard-abelion      # only if preflight printed PREFLIGHT PASS

`preflight.py` runs the plugin in a throwaway Hermes home and temp git repos
through Hermes' real plugin loader and tool dispatch (no model, no network). It
fails if this Hermes does not apply the hooks the guard relies on, because on
such a host the guard could silently let main-checkout writes through. If it
cannot find Hermes' Python, run it with Hermes' own Python.

`--ref` needs the full SHA. Add `--force` to move an installed copy. A private
repo is cloned with `GITHUB_TOKEN`, `gh auth`, or your git credential helper;
if that fails the install fails, nothing is enabled. Restart Hermes after
enabling.

## Switches (Hermes process env, logged at start-up when set)

- `HERMES_WORKTREE_GUARD=off` disables everything.
- `HERMES_WORKTREE_GUARD_ALLOW=/path/a:/path/b` exempts those repo roots.
- `HERMES_WORKTREE_GUARD_EXECUTE_CODE=allow` stops blocking `execute_code`.

## Limits

A policy hook, not an OS sandbox. Covered: `write_file`, `patch`, `read_file`,
`terminal`, `execute_code`. Not covered: other tools (e.g. browser or
computer-use input) and creative shell commands the pattern match misses
(`python -c`, `perl -i`, `dd`, ...). Running tests executes arbitrary code.
`execute_code` is blocked outright while the session cwd is a main checkout,
because arbitrary Python cannot be re-routed. The worktree starts from HEAD, so
a main checkout with uncommitted or untracked changes is refused (commit or
stash first). `pre_verify` is a nudge, not enforcement: it asks for checks and
a diff summary but cannot prove they ran. Without `modify` support the guard
falls back to blocking; without `pre_tool_call` it refuses to load.

## Tests

    python3 -m unittest discover -s tests -v     # 33 unit tests, real temp git repos
    python3 worktree_guard_abelion/preflight.py  # real loader + dispatch, temp home
