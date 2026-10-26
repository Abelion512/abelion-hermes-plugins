"""worktree_guard_abelion - route agent edits out of a repo's main checkout.

Hooks (stdlib only, no core changes):

* ``pre_tool_call``: when write_file/patch/terminal would modify a git *main*
  checkout, the plugin creates (once per session and repo) a linked worktree
  ``<repo>-worktrees/task-<id>`` on branch ``hermes/task-<id>`` and re-routes the
  call into it (``modify`` args). Calls that cannot be re-routed safely (V4A
  patch bodies, commands naming main-checkout paths, ``.git`` internals, this
  plugin's own files) are blocked with the worktree path in the message. If the
  worktree cannot be created the call is blocked (fail closed).
* ``transform_tool_result``: tells the model a call was re-routed.
* ``pre_verify``: once per turn, if the agent edited files in a worktree this
  plugin created, asks it to run the project's checks and summarise
  ``git diff --stat`` there before handing over. Never merges.

``execute_code`` (arbitrary Python, cannot be re-routed) is blocked while the
session cwd is a main checkout. A dirty main checkout (tracked changes or
untracked files) blocks worktree creation, so the agent never works on code
that silently lacks the user's uncommitted work.

Limits: a policy hook, not an OS sandbox. The terminal check is a pattern match,
so creative shell commands can still write anywhere; tools not named above
(for example browser/computer-use input) are not covered. Paths outside any git
repo are allowed by design. The ``pre_verify`` hook is a nudge, not enforcement.

Env (read from the Hermes process, logged at start-up when set):
HERMES_WORKTREE_GUARD=off disables everything;
HERMES_WORKTREE_GUARD_ALLOW=/a:/b exempts those repo roots;
HERMES_WORKTREE_GUARD_EXECUTE_CODE=allow stops blocking execute_code.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_FILE_TOOLS = {"write_file", "patch"}
_GIT_MUTATORS = {
    "add", "commit", "checkout", "switch", "reset", "restore", "merge", "rebase",
    "cherry-pick", "revert", "stash", "apply", "am", "clean", "rm", "mv", "pull",
    "tag", "branch", "push",
}
_FILE_MUTATORS = {"rm", "mv", "cp", "touch", "mkdir", "rmdir", "tee", "truncate", "patch", "install", "ln"}
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
_REDIRECT_TARGET = re.compile(r"(?<![0-9&<])>>?\s*(?!&|/dev/null)(\S+)")
_GIT_TIMEOUT = 3
_ADD_TIMEOUT = 25  # Hermes cancels pre_tool_call hooks at 30s (fail closed)
_PLUGIN_DIR = os.path.realpath(os.path.dirname(__file__))

_MODIFY_OK = True  # set by register(): False => host cannot apply `modify`, so re-routes become blocks

_lock = threading.RLock()
_created: dict[tuple[str, str], str] = {}   # (session key, repo root) -> worktree path
_pending: dict[str, str] = {}               # tool_call_id / "task:tool" -> notice


def _disabled() -> bool:
    return os.environ.get("HERMES_WORKTREE_GUARD", "").strip().lower() in {"off", "0", "false"}


def _allowed_roots() -> set[str]:
    raw = os.environ.get("HERMES_WORKTREE_GUARD_ALLOW", "")
    return {os.path.realpath(p) for p in raw.split(os.pathsep) if p.strip()}


def _git(cwd: str, *args: str, timeout: float = _GIT_TIMEOUT) -> Optional[str]:
    """stdout, or None when git fails (not a repo, bad ref) or is missing. Raises TimeoutExpired."""
    try:
        res = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def main_checkout_root(path: str) -> Optional[str]:
    """Repo root when *path* lies in a git main checkout, else None (linked worktree, no repo, allowed)."""
    p = Path(path)
    while not p.is_dir():
        if p.parent == p:
            return None
        p = p.parent
    out = _git(str(p), "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    parts = out.splitlines() if out else []
    if len(parts) != 3:
        # Inside a .git directory there is no work tree: treat the repo as the owner (blocks .git edits).
        out = _git(str(p), "rev-parse", "--path-format=absolute", "--git-common-dir")
        common = os.path.realpath(out) if out else ""
        root = os.path.dirname(common)
        return root if os.path.basename(common) == ".git" and root not in _allowed_roots() else None
    top, git_dir, common = (os.path.realpath(x) for x in parts)
    if git_dir != common:
        return None  # linked worktree
    return top if top not in _allowed_roots() else None


def _base_cwd(task_id: str) -> str:
    try:
        from tools.file_tools_paths import _authoritative_workspace_root

        root = _authoritative_workspace_root(task_id or "default")
        if root:
            return str(root)
    except Exception:
        pass
    env = os.environ.get("TERMINAL_CWD", "")
    return env if os.path.isabs(env) else os.getcwd()


def _resolve(path: str, base: str) -> str:
    return os.path.realpath(os.path.join(base, os.path.expanduser(path)))


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _slug(key: str) -> str:
    return "task-" + (re.sub(r"[^A-Za-z0-9]", "", key or "")[:8] or "x")


def _is_linked_worktree_of(wt: str, root: str) -> bool:
    out = _git(wt, "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir")
    parts = out.splitlines() if out else []
    return len(parts) == 2 and parts[0] != parts[1] and os.path.realpath(parts[1]) == os.path.realpath(os.path.join(root, ".git"))


def ensure_worktree(root: str, key: str) -> str:
    """Path of this session's worktree for *root*, creating it if needed. Raises RuntimeError on failure."""
    with _lock:
        known = _created.get((key, root))
        wt = known or f"{root}-worktrees/{_slug(key)}"
        if os.path.isdir(wt):
            if not _is_linked_worktree_of(wt, root):
                raise RuntimeError(f"{wt} exists but is not a worktree of {root}")
        else:
            dirty = _git(root, "status", "--porcelain")
            if dirty is None:
                raise RuntimeError("could not read git status of the main checkout")
            if dirty:
                raise RuntimeError(
                    f"the main checkout {root} has uncommitted or untracked changes that a worktree made from HEAD "
                    f"would not contain; commit or stash them, then retry")
            branch = f"hermes/{_slug(key)}"
            try:
                created = _git(root, "worktree", "add", "-b", branch, wt, timeout=_ADD_TIMEOUT) is not None
                if not created:  # branch already exists from an earlier run
                    created = _git(root, "worktree", "add", wt, branch, timeout=_ADD_TIMEOUT) is not None
            except subprocess.TimeoutExpired:
                raise RuntimeError("git worktree add timed out") from None
            if not created or not os.path.isdir(wt):
                raise RuntimeError("git worktree add failed")
        _created[(key, root)] = wt
        return wt


def _is_mutating_command(cmd: str) -> bool:
    if _REDIRECT_TARGET.search(cmd):
        return True
    for seg in _SEGMENT_SPLIT.split(cmd):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        while words and "=" in words[0] and not words[0].startswith("-"):
            words = words[1:]  # VAR=value prefix
        if words and words[0] in {"sudo", "env", "command", "time"}:
            words = words[1:]
        if not words:
            continue
        if words[0] == "git":
            sub = next((w for w in words[1:] if not w.startswith("-") and not os.path.isabs(w)), "")
            if sub in _GIT_MUTATORS:
                return True
        elif words[0] in _FILE_MUTATORS:
            return True
        elif words[0] == "sed" and any(w.startswith("-i") or w == "--in-place" for w in words[1:]):
            return True
    return False


def _command_paths(cmd: str, cwd: str) -> list[tuple[str, bool]]:
    """(resolved path, was absolute/~) for path-looking tokens and redirect targets of a command."""
    try:
        words = shlex.split(cmd, posix=True)
    except ValueError:
        words = cmd.split()
    words += _REDIRECT_TARGET.findall(cmd)
    out = []
    for w in words:
        w = w.split("=", 1)[1] if w.startswith("--") and "=" in w else w
        if "/" in w or w.startswith((".", "~")):
            out.append((_resolve(w, cwd), w.startswith(("/", "~"))))
    return out


def _reroute(new_args: dict, wt: str, root: str) -> dict:
    if _MODIFY_OK:
        return {"action": "modify", "args": new_args}
    return _unsafe(_blocked_in(root, wt) + " (this Hermes cannot rewrite tool arguments, so the call was blocked instead.)")


def _unsafe(msg: str) -> dict[str, str]:
    return {"action": "block", "message": msg}


def _blocked_in(root: str, wt: str) -> str:
    return (f"Blocked by worktree-guard: this call would modify the main checkout {root}. A worktree for this "
            f"session is ready at {wt} (branch hermes/{os.path.basename(wt)}). Redo the call using absolute paths "
            f"under {wt} and set terminal workdir to {wt}. Run the project's checks and review `git diff` there; "
            f"do not merge into the main checkout.")


def decide(tool_name: str, args: dict[str, Any], task_id: str = "", tool_call_id: str = "") -> Optional[dict]:
    """Directive dict for pre_tool_call, or None to allow. Raises nothing but TimeoutExpired/RuntimeError."""
    if _disabled():
        return None
    args = dict(args or {})
    base = _base_cwd(task_id)
    key = task_id or "default"

    if tool_name in _FILE_TOOLS:
        raw = args.get("path") or args.get("file_path")
        v4a = args.get("patch") if isinstance(args.get("patch"), str) else ""
        names = ([raw] if isinstance(raw, str) and raw else [])
        names += [n.strip() for n in re.findall(r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$", v4a, re.M)]
        names += [n.strip() for n in re.findall(r"^\*\*\* Move to:\s*(.+)$", v4a, re.M)]
        for name in names:
            real = _resolve(name, base)
            if _within(real, _PLUGIN_DIR):
                return _unsafe("Blocked by worktree-guard: this plugin's own files are not editable by the agent.")
            root = main_checkout_root(real)
            if not root:
                continue
            rel = os.path.relpath(real, root)
            wt = ensure_worktree(root, key)
            if rel == ".git" or rel.startswith(".git" + os.sep) or v4a:
                return _unsafe(_blocked_in(root, wt))
            new_path = os.path.join(wt, rel)
            _pending[tool_call_id or f"{key}:{tool_name}"] = (
                f"[worktree-guard] Edit re-routed from {real} to {new_path}. Work in {wt} from now on; "
                f"review `git diff` there before handing over. Never edit {root} directly.")
            return _reroute({"path": new_path}, wt, root)
        return None

    if tool_name == "execute_code":
        if os.environ.get("HERMES_WORKTREE_GUARD_EXECUTE_CODE", "").strip().lower() == "allow":
            return None
        root = main_checkout_root(base)
        if root:
            return _unsafe(
                f"Blocked by worktree-guard: execute_code runs arbitrary Python and cannot be confined to a worktree, "
                f"and this session's working directory is the main checkout {root}. Use write_file/patch/terminal "
                f"(they are routed into a session worktree automatically), or start the session inside a worktree.")
        return None

    if tool_name == "read_file":  # once a session worktree exists, show its content, not the stale main copy
        raw = args.get("path")
        if isinstance(raw, str) and raw:
            real = _resolve(raw, base)
            root = main_checkout_root(real)
            wt = _created.get((key, root)) if root else None
            rel = os.path.relpath(real, root) if root else ""
            if wt and not rel.startswith(".git"):
                _pending[tool_call_id or f"{key}:{tool_name}"] = (
                    f"[worktree-guard] Read from the session worktree: {os.path.join(wt, rel)} (not {real}).")
                return _reroute({"path": os.path.join(wt, rel)}, wt, root)
        return None

    if tool_name == "terminal":
        cmd = args.get("command")
        if not isinstance(cmd, str) or not _is_mutating_command(cmd):
            return None
        workdir = args.get("workdir")
        cwd = _resolve(workdir, base) if isinstance(workdir, str) and workdir else base
        cwd_root = main_checkout_root(cwd)
        touched = set()
        for path, absolute in _command_paths(cmd, cwd):
            r = main_checkout_root(path)
            if r and (absolute or r != cwd_root):
                touched.add(r)
        if not touched and not cwd_root:
            return None
        if touched:  # names main-checkout paths explicitly: cannot be rewritten safely
            root = sorted(touched)[0]
            return _unsafe(_blocked_in(root, ensure_worktree(root, key)))
        wt = ensure_worktree(cwd_root, key)
        new_cwd = os.path.normpath(os.path.join(wt, os.path.relpath(cwd, cwd_root)))
        _pending[tool_call_id or f"{key}:{tool_name}"] = (
            f"[worktree-guard] Command re-routed from {cwd} to {new_cwd}. Work in {wt} from now on; "
            f"review `git diff` there before handing over. Never modify {cwd_root} directly.")
        return _reroute({"workdir": new_cwd}, wt, cwd_root)
    return None


def _pre_tool_call(tool_name, args, task_id="", **kwargs):
    try:
        return decide(tool_name, args, task_id, kwargs.get("tool_call_id") or "")
    except subprocess.TimeoutExpired:
        return _unsafe("worktree-guard: git timed out while checking the target; failing closed.")
    except RuntimeError as exc:
        return _unsafe(f"worktree-guard: could not prepare an isolated worktree ({exc}); not editing the main checkout.")


def _transform_tool_result(tool_name, args, result, task_id="", **kwargs):
    key = kwargs.get("tool_call_id") or f"{task_id or 'default'}:{tool_name}"
    with _lock:
        note = _pending.pop(key, None)
    if note and isinstance(result, str):
        return f"{result}\n{note}"
    return None


def _pre_verify(coding=False, attempt=0, changed_paths=None, **kwargs):
    if attempt or _disabled():
        return None
    for (_key, root), wt in list(_created.items()):
        if any(_within(os.path.realpath(p), os.path.realpath(wt)) for p in (changed_paths or [])):
            return {"action": "continue", "message": (
                f"Before handing over: in {wt} run the project's tests/lint for what you changed, then show "
                f"`git -C {wt} diff --stat` and a short summary. Report any check you could not run. "
                f"Do not merge into {root} or push.")}
    return None


def _host_supports_modify() -> bool:
    """True when the host's pre_tool_call dispatch returns and applies modified args."""
    try:
        import inspect

        import hermes_cli.plugins as hp
        import model_tools

        return (hasattr(hp, "_dispatch_pre_tool_call_hooks")
                and "modified_args" in inspect.getsource(model_tools._pre_dispatch_guards))
    except Exception:
        return False


def register(ctx):
    global _MODIFY_OK
    try:
        from hermes_cli.plugins import VALID_HOOKS
        missing = {"pre_tool_call", "transform_tool_result", "pre_verify"} - set(VALID_HOOKS)
    except Exception:
        missing = set()  # not running inside Hermes (unit tests)
    if "pre_tool_call" in missing:
        raise RuntimeError("worktree-guard-abelion: this Hermes has no pre_tool_call hook; refusing to load a "
                           "guard that cannot guard. Upgrade Hermes or remove the plugin.")
    in_hermes = "hermes_cli.plugins" in __import__("sys").modules
    _MODIFY_OK = _host_supports_modify() if in_hermes else True
    if not _MODIFY_OK:
        logger.error("[worktree_guard_abelion] host cannot rewrite tool arguments: running in block-only mode")
    if missing:
        logger.warning("[worktree_guard_abelion] host lacks hooks %s: notices/handoff nudge unavailable", sorted(missing))
    if _disabled():
        logger.warning("[worktree_guard_abelion] DISABLED by HERMES_WORKTREE_GUARD")
    elif _allowed_roots():
        logger.warning("[worktree_guard_abelion] repo roots exempt from the guard: %s", sorted(_allowed_roots()))
    if os.environ.get("HERMES_WORKTREE_GUARD_EXECUTE_CODE", "").strip().lower() == "allow":
        logger.warning("[worktree_guard_abelion] execute_code is NOT blocked (HERMES_WORKTREE_GUARD_EXECUTE_CODE=allow)")
    for name, fn in (("pre_tool_call", _pre_tool_call), ("transform_tool_result", _transform_tool_result),
                     ("pre_verify", _pre_verify)):
        if name not in missing:
            ctx.register_hook(name, fn)
    logger.info("[worktree_guard_abelion] registered (modify=%s)", _MODIFY_OK)
