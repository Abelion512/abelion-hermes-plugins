"""Standalone Privacy Guard contracts, independent of a Hermes runtime install."""
import json
from pathlib import Path
import sys

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = PLUGIN_ROOT.parent
REPO_ROOT = PLUGINS_ROOT.parent
sys.path.insert(0, str(PLUGINS_ROOT))

from pii_mask_abelion.guard import Guard


@pytest.mark.parametrize("value", [None, [], {}, {"model": "x", "messages": "wrong"}])
def test_invalid_request_has_no_policy_state(value):
    policy = Guard()
    assert policy.required_policy("request", request=value, session_id="test")["allow"] is False
    assert not policy.sessions


def test_standalone_request_masks_synthetic_email():
    policy = Guard()
    result = policy.required_policy(
        "request",
        request={"model": "test", "messages": [{"role": "user", "content": "sample@example.com"}]},
        session_id="test",
    )
    assert result["allow"] is True
    assert "sample@example.com" not in json.dumps(result["request"])


def test_audit_label_has_evidence_only_path():
    config = (REPO_ROOT / ".github" / "labeler.yml").read_text(encoding="utf-8")
    assert 'audit:\n  - changed-files:\n      - any-glob-to-any-file: "plugins/pii_mask_abelion/validation/**"' in config
