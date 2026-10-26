"""Active loop detector — blocks infinite tool loops.

pre_tool_call hook → return {"action": "block", "message": "..."}
Blocks when same tool + same args appears 3+ times consecutively.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import OrderedDict, deque

logger = logging.getLogger(__name__)


class ActiveLoopDetector:
    def __init__(self, max_similar_actions: int = 3, window_size: int = 10):
        self.max_similar_actions = max_similar_actions
        self.window_size = window_size
        self.action_history: deque[dict] = deque(maxlen=window_size)

    def add_action(self, tool_name: str, args: dict) -> None:
        self.action_history.append({"tool": tool_name, "args": str(args)})

    def is_looping(self) -> bool:
        if len(self.action_history) < self.max_similar_actions:
            return False
        recent = list(self.action_history)
        last = recent[-1]
        count = 0
        for action in reversed(recent):
            if action["tool"] == last["tool"] and action["args"] == last["args"]:
                count += 1
            else:
                break
        return count >= self.max_similar_actions

    def reset(self) -> None:
        self.action_history.clear()


# One detector per session so parallel sessions don't trip each other's loop check.
# Bounded (oldest session dropped) so a long-running gateway can't grow it forever.
_MAX_SESSIONS = 64
_detectors: "OrderedDict[str, ActiveLoopDetector]" = OrderedDict()
_lock = threading.Lock()
_detector = ActiveLoopDetector()  # fallback when the hook gives no session id


def _get_detector(session_id: str = "") -> ActiveLoopDetector:
    if not session_id:
        return _detector
    with _lock:
        det = _detectors.get(session_id)
        if det is None:
            det = _detectors[session_id] = ActiveLoopDetector()
            while len(_detectors) > _MAX_SESSIONS:
                _detectors.popitem(last=False)
        else:
            _detectors.move_to_end(session_id)
        return det


def reset_detector() -> None:
    _detector.reset()
    with _lock:
        _detectors.clear()


def snapshot() -> dict:
    """Dump loop detector state to JSON. Returns snapshot dict."""
    data = {
        "timestamp": time.time(),
        "max_similar_actions": _detector.max_similar_actions,
        "window_size": _detector.window_size,
        "history_size": len(_detector.action_history),
        "recent": list(_detector.action_history)[-5:],
    }
    base = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    dest = os.path.join(base, "shield", "protect", "loop_detector.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)
    return data


def check_and_block(tool_name: str, args: dict, session_id: str = "") -> dict | None:
    """pre_tool_call hook. Returns block directive if loop detected."""
    det = _get_detector(session_id)
    det.add_action(tool_name, args)
    if det.is_looping():
        logger.warning(
            "[protect] Blocking loop: %s called %d+ times with identical args",
            tool_name, det.max_similar_actions,
        )
        return {
            "action": "block",
            "message": (
                f"🛑 Infinite loop detected: `{tool_name}` called "
                f"{det.max_similar_actions}+ times with same arguments. "
                f"Try a different approach."
            ),
        }
    return None
