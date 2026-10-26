"""worktree_guard_abelion - keep the agent out of a repo's main checkout.

``pre_tool_call`` blocks, with a fix-it message, any write_file/patch on a path
inside a git *main* checkout and any terminal command that obviously mutates
files or git state while its working directory is in one. Linked worktrees
(``git worktree add``), non-repo paths and repos listed in the allow env var
pass through.

Limits (by design, stdlib-only): this is a policy hook, not an OS sandbox. The
terminal check is a best-effort pattern match, so an arbitrary shell command can
still write outside a worktree. File tools are checked by resolved real path.

Env: HERMES_WORKTREE_GUARD=off disables; HERMES_WORKTREE_GUARD_ALLOW=/a:/b
lists repo roots that may be edited directly.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
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
_REDIRECT = re.compile(r"(?<![0-9&<])>>?\s*(?!&|/dev/null)\S")
_GIT_TIMEOUT = 3


def _disabled() -> bool:
    return os.environ.get("HERMES_WORKTREE_GUARD", "").strip().lower() in {"off", "0", "false"}


def _allowed_roots() -> set[str]:
    raw = os.environ.get("HERMES_WORKTREE_GUARD_ALLOW", "")
    return {os.path.realpath(p) for p in raw.split(os.pathsep) if p.strip()}


def _git(cwd: str, *args: str) -> Optional[str]:
    """stdout of git, None when git says no (not a repo) or is missing; raises on timeout."""
    try:
        res = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
    except FileNotFoundError:
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def main_checkout_root(path: str) -> Optional[str]:
    """Repo root when *path* lies in a git main checkout, else None (linked worktree, bare, no repo)."""
    p = Path(path)
    while not p.is_dir():
        if p.parent == p:
            return None
        p = p.parent
    out = _git(str(p), "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if not out:
        return None
    parts = out.splitlines()
    if len(parts) != 3:
        return None
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


def _is_mutating_command(cmd: str) -> bool:
    if _REDIRECT.search(cmd):
        return True
    for seg in _SEGMENT_SPLIT.split(cmd):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        while words and ("=" in words[0] and not words[0].startswith("-")):
            words = words[1:]  # VAR=value prefix
        if words and words[0] in {"sudo", "env", "command", "time"}:
            words = words[1:]
        if not words:
            continue
        if words[0] == "git":
            sub = next((w for w in words[1:] if not w.startswith("-")), "")
            if sub in _GIT_MUTATORS:
                return True
        elif words[0] in _FILE_MUTATORS:
            return True
        elif words[0] == "sed" and any(w.startswith("-i") or w == "--in-place" for w in words[1:]):
            return True
    return False


def _message(root: str, task_id: str) -> str:
    slug = "task-" + (re.sub(r"[^A-Za-z0-9]", "", task_id or "")[:6] or "task")
    wt = f"{root}-worktrees/{slug}"
    return (
        f"Blocked by worktree-guard: {root} is the main checkout. Do not edit or run git "
        f"mutations there. Create an isolated worktree first: "
        f"`git -C {root} worktree add -b hermes/{slug} {wt}` then use absolute paths under "
        f"{wt} for write_file/patch and set terminal workdir to {wt}. "
        f"Run tests and review `git diff` there; do not merge into the main checkout."
    )


def _paths_for(tool_name: str, args: dict[str, Any], base: str) -> list[str]:
    if tool_name in _FILE_TOOLS:
        p = args.get("path") or args.get("file_path")
        paths = [p] if isinstance(p, str) and p else []
        patch = args.get("patch")
        if isinstance(patch, str):  # V4A mode names files inside the patch body
            paths += re.findall(r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$", patch, re.M)
            paths += re.findall(r"^\*\*\* Move to:\s*(.+)$", patch, re.M)
        return [_resolve(x.strip(), base) for x in paths]
    return []


def check(tool_name: str, args: dict[str, Any], task_id: str = "") -> Optional[str]:
    """Block message, or None to allow. Raises nothing the caller must handle except git timeouts."""
    if _disabled():
        return None
    args = args or {}
    base = _base_cwd(task_id)
    if tool_name in _FILE_TOOLS:
        for path in _paths_for(tool_name, args, base):
            root = main_checkout_root(path)
            if root:
                return _message(root, task_id)
        return None
    if tool_name == "terminal":
        cmd = args.get("command") or ""
        if not isinstance(cmd, str) or not _is_mutating_command(cmd):
            return None
        workdir = args.get("workdir")
        cwd = _resolve(workdir, base) if isinstance(workdir, str) and workdir else base
        root = main_checkout_root(cwd)
        if root:
            return _message(root, task_id)
    return None


def _hook(tool_name, args, task_id="", **kwargs):
    try:
        msg = check(tool_name, args, task_id)
    except subprocess.TimeoutExpired:
        return {"action": "block", "message": "worktree-guard: git timed out while checking the target; failing closed."}
    return {"action": "block", "message": msg} if msg else None


def register(ctx):
    ctx.register_hook("pre_tool_call", _hook)
    logger.info("[worktree_guard_abelion] registered pre_tool_call guard")
