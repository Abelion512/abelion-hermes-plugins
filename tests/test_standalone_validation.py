"""Standalone contracts. Host-dependent cross-plugin tests live separately."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pii_mask_abelion.guard import Guard


@pytest.mark.parametrize("value", [None, [], {}, {"model": "x", "messages": "wrong"}])
def test_invalid_request_has_no_policy_state(value):
    policy = Guard()
    assert policy.required_policy("request", request=value, session_id="test")["allow"] is False
    assert not policy.sessions


def test_standalone_request_masks_synthetic_email():
    policy = Guard()
    result = policy.required_policy("request", request={"model": "test", "messages": [{"role": "user", "content": "sample@example.com"}]}, session_id="test")
    assert result["allow"] is True
    assert "sample@example.com" not in json.dumps(result["request"])
