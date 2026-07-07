"""Circuit breaker — blocks failing tool calls after consecutive errors.

Integrated with Hermes tool error feedback via check_fn and pre_tool_call.
Monitors failure rate from post_tool_call events and self-resets after timeout.

Used for: delegation, terminal, web_search — any tool that can cascade-fail.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Per-tool circuit breaker with sliding-window failure tracking."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = State.CLOSED
        self.failures = 0
        self.last_failure_time = 0.0

    def allow_request(self) -> bool:
        if self.state == State.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = State.HALF_OPEN
                logger.info("[protect] Circuit breaker half-open — allowing trial request")
                return True
            return False
        return True

    def record_success(self) -> None:
        self.failures = 0
        if self.state != State.CLOSED:
            self.state = State.CLOSED
            logger.info("[protect] Circuit breaker closed — failures reset")

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            if self.state != State.OPEN:
                self.state = State.OPEN
                logger.warning(
                    "[protect] Circuit breaker OPENED for tool after %d failures",
                    self.failures,
                )


# Per-tool breakers
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker()
    return _breakers[name]


# ── post_tool_call integration ─────────────────────────────────────────

def on_tool_result(tool_name: str, status: str, **kwargs) -> None:
    """post_tool_call hook: feed tool result to circuit breaker.

    Call from post_tool_call_hook or pre_tool_call block check.
    status: "success", "error", or empty.
    """
    breaker = get_breaker(tool_name)
    if status == "error":
        breaker.record_failure()
    elif status == "success":
        breaker.record_success()


def snapshot() -> dict:
    """Dump circuit breaker states to JSON file. Returns snapshot dict."""
    data = {
        "timestamp": time.time(),
        "breakers": {
            name: {
                "state": cb.state.value,
                "failures": cb.failures,
                "threshold": cb.failure_threshold,
                "recovery_timeout": cb.recovery_timeout,
            }
            for name, cb in _breakers.items()
        },
    }
    dest = _snapshot_path()
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)
    return data


def _snapshot_path() -> str:
    base = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    p = os.path.join(base, "shield", "protect")
    os.makedirs(p, exist_ok=True)
    return os.path.join(p, "circuit_breaker.json")


def check_and_block(tool_name: str, args: dict) -> dict | None:
    """pre_tool_call hook: block if breaker is OPEN.

    Returns block directive if circuit is open, None otherwise.
    """
    breaker = get_breaker(tool_name)
    if not breaker.allow_request():
        remaining = max(0, breaker.recovery_timeout - (time.time() - breaker.last_failure_time))
        logger.warning("[protect] Circuit breaker blocking %s (%.0fs remaining)", tool_name, remaining)
        return {
            "action": "block",
            "message": (
                f"⛔ Tool `{tool_name}` is temporarily unavailable "
                f"(circuit breaker open, ~{remaining:.0f}s remaining). "
                f"Try again later or use an alternative approach."
            ),
        }
    return None
