"""Standalone Privacy Guard contracts, independent of a Hermes runtime install."""
import json
from pathlib import Path
import sys

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_ROOT = PLUGIN_ROOT.parent
REPO_ROOT = PLUGINS_ROOT.parent
sys.path.insert(0, str(PLUGINS_ROOT))

from nebula.guard import Guard


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


def test_validation_label_exists_for_validation_path():
    import yaml

    plugin = yaml.safe_load((PLUGIN_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
    assert "validation" in plugin
    assert any(
        "validation" in str(v)
        for v in plugin["validation"]
    ), plugin["validation"]


def test_priority_labels_are_not_auto_path_labels():
    """Repo-wide and plugin-local labelers should not pretend priority comes
    from changed files. This is a structural stance check, not a snapshot of
    every label ever."""
    import yaml

    repo = yaml.safe_load((REPO_ROOT / ".github" / "labeler.yml").read_text(encoding="utf-8"))
    plugin = yaml.safe_load((PLUGIN_ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
    priority_like = {"p0", "p1", "p2", "p3", "priority", "severity"}
    for source, payload in [("repo", repo), ("plugin", plugin)]:
        if not isinstance(payload, dict):
            raise AssertionError(f"{source} labels payload is not a mapping: {payload!r}")
        for key, rule in payload.items():
            if str(key).lower() in priority_like:
                raise AssertionError(
                    f"{source} labeler should not define priority-as-path label {key!r}: {rule!r}"
                )
