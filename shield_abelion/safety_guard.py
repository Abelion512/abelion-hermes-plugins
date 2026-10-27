"""Safety guard — boundary check before destructive tool calls.

pre_tool_call hook → return {"action": "block", "message": "..."}
Prevents operations that could damage the system:
  - rm -rf /, rm -rf ~, rm -rf /*
  - dd if=/dev/zero of=/dev/sda
  - mkfs, format, fdisk on system disks
  - chmod 000 on critical files
  - wget/curl piped to bash (if suspicious)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time

logger = logging.getLogger(__name__)

# ── Dangerous patterns ────────────────────────────────────────────────

# Commands that should never execute without explicit human confirmation
DANGEROUS_REGEXES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\brm\s+(-rf|--recursive)\s+/[ \t]'), "rm -rf / (system root)"),
    (re.compile(r'\brm\s+(-rf|--recursive)\s+/\s*$'), "rm -rf / (EOF, system root)"),
    (re.compile(r'\brm\s+(-rf|--recursive)\s+/var[/ \t]'), "rm -rf /var"),
    (re.compile(r'\brm\s+(-rf|--recursive)\s+/etc[/ \t]'), "rm -rf /etc"),
    (re.compile(r'\brm\s+(-rf|--recursive)\s+/boot[/ \t]'), "rm -rf /boot"),
    (re.compile(r'\bdd\s+if=/dev/zero\s+of=/dev/sd[a-z]\b'), "dd to raw disk"),
    (re.compile(r'\bdd\s+if=/dev/urandom\s+of=/dev/sd[a-z]\b'), "dd to raw disk"),
    (re.compile(r'\bmkfs\b.*/dev/sd[a-z]\b'), "mkfs on disk (not partition)"),
    (re.compile(r'\bmkfs\.\w+\b.*/dev/sd[a-z]\b'), "mkfs on disk (not partition)"),
    (re.compile(r'\bfdisk\b.*/dev/sd[a-z]\b'), "fdisk on raw disk"),
    (re.compile(r'\bchmod\s+000\s+/[ \t]'), "chmod 000 / (system root)"),
    (re.compile(r'\bchmod\s+000\s+/\s*$'), "chmod 000 / (EOF, system root)"),
    (re.compile(r'\bchmod\s+000\s+/etc[ /t]'), "chmod 000 /etc"),
    (re.compile(r'\bchmod\s+000\s+/etc\s*$'), "chmod 000 /etc (EOF)"),
    (re.compile(r'\bchown\s+-R\b'), "recursive chown (high risk)"),
    (re.compile(r'\b(wget|curl)\b.*\|\s*(bash|sh)\b'), "piped web to shell"),
    (re.compile(r'\bsudo\s+rm\s+(-rf|--recursive)\b'), "sudo rm -rf"),
    (re.compile(r'\b>\s+/dev/sd[a-z]\b'), "direct write to disk device"),
]


def check_and_block(tool_name: str, args: dict) -> dict | None:
    """pre_tool_call hook. Block destructive commands before execution.

    Checks terminal commands and file operations for dangerous patterns.
    """
    if tool_name not in ("terminal", "bash", "execute_code", "write_file", "patch"):
        return None

    # Extract command text from args
    cmd = (
        str(args.get("cmd", ""))
        or str(args.get("command", ""))
        or str(args.get("code", ""))
        or str(args.get("content", ""))
        or str(args.get("path", ""))
    )

    if not cmd:
        return None

    for pattern, desc in DANGEROUS_REGEXES:
        if pattern.search(cmd):
            logger.warning("[protect] Safety guard blocked: %s (tool=%s)", desc, tool_name)
            return {
                "action": "block",
                "message": (
                    f"🚫 Safety guard blocked potentially destructive operation: {desc}. "
                    f"If this is intentional, ask the user to approve explicitly."
                ),
            }

    return None


# ── Read-Before-Edit Guard ─────────────────────────────────────────────

_read_history: dict[str, set[str]] = {}
_read_lock = threading.Lock()

WRITE_TOOLS = {"write_file", "edit", "patch", "write"}


def snapshot() -> dict:
    """Dump read-before-edit state to JSON. Returns snapshot dict."""
    with _read_lock:
        data = {
            "timestamp": time.time(),
            "sessions": {
                sid: list(paths)
                for sid, paths in list(_read_history.items())
            },
        }
    base = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    dest = os.path.join(base, "shield", "protect", "read_history.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)
    return data


def record_read(session_id: str, path: str) -> None:
    """Record a file read for a session (call from pre_tool_call)."""
    if not session_id or not path:
        return
    with _read_lock:
        if session_id not in _read_history:
            _read_history[session_id] = set()
        _read_history[session_id].add(path)


def _get_read_key(tool_name: str, args: dict) -> str | None:
    """Extract the file path from tool args."""
    if tool_name == "read_file":
        return str(args.get("path", "") or args.get("file_path", ""))
    if tool_name in WRITE_TOOLS:
        return str(args.get("path", "") or args.get("file_path", "") or args.get("target", ""))
    return None


def check_and_block_read_before_edit(
    tool_name: str, args: dict, session_id: str = "", **kwargs
) -> dict | None:
    """pre_tool_call hook: block write/edit if file not read first."""
    if tool_name not in WRITE_TOOLS:
        return None

    target = _get_read_key(tool_name, args)
    if not target or target in (".", "/"):
        return None

    # Creating a brand-new file has nothing to read first. Only an absolute path that does
    # not exist yet (and is not a symlink) is exempt: a relative path can't be resolved reliably here (tool cwd
    # may differ), so it keeps the guard.
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded) and not os.path.lexists(expanded):  # lexists: any symlink (even dangling) keeps the guard
        return None

    with _read_lock:
        history = _read_history.get(session_id, set())

    if target not in history:
        logger.warning(
            "[protect] Read-before-edit blocked: %s -> '%s' not read in session %s",
            tool_name, target, session_id[:8] if session_id else "(none)",
        )
        return {
            "action": "block",
            "message": (
                f"📖 File `{target}` has not been read in this session. "
                f"Call `read_file` with path `{target}` first, then retry the edit."
            ),
        }

    return None
