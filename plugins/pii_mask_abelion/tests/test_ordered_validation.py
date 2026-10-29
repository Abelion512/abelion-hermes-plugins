"""Hermes-host-specific edge cases; skipped without the matching Hermes runtime."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

pytest.importorskip(
    "hermes_constants",
    reason="Requires the pinned Hermes runtime; standalone contracts are tested beside this plugin",
)

PLUGINS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGINS_ROOT))
from pii_mask_abelion.guard import Guard
from pii_mask_abelion.output_redact import redact_output


@pytest.mark.parametrize("kw", [
    {"ttl": float("nan")}, {"ttl": 0}, {"max_sessions": True},
    {"max_entries": -1}, {"max_bytes": "2"},
])
def test_guard_wrong_requirement(kw):
    with pytest.raises(ValueError):
        Guard(**kw)


@pytest.mark.parametrize("req", [
    None, [], {}, {"model": "", "messages": [{}]}, {"model": "ok", "messages": "wrong"},
])
def test_guard_wrong_values_no_state(req):
    guard = Guard()
    result = guard.required_policy("request", request=req, session_id="s")
    assert result["allow"] is False
    assert not guard.sessions


@pytest.mark.parametrize("args", [None, [], 42])
def test_tool_args_wrong_type(args):
    assert Guard().pre_tool(args)["action"] == "block"


def test_guard_valid():
    result = Guard().required_policy(
        "request",
        request={"model": "test", "messages": [{"role": "user", "content": "email=a@example.com"}]},
        session_id="s",
    )
    assert result["allow"]
    assert "a@example.com" not in json.dumps(result["request"])


@pytest.mark.parametrize("value", [{}, [], 12])
def test_output_invalid(value):
    assert redact_output(value) == "[OUTPUT_WITHHELD:invalid_text]"


def test_output_native_failure():
    with patch("agent.redact.redact_sensitive_text", side_effect=RuntimeError("private")):
        assert redact_output("plain") == "[OUTPUT_WITHHELD:redactor_failed]"
