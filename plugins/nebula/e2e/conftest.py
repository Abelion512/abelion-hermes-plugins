import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / ".github" / "e2e_support"))
sys.path.insert(0, str(REPO_ROOT / "plugins"))


def pytest_sessionstart(session):
    """CI must not silently skip host tests or run against an unreviewed Hermes build."""
    if os.environ.get("REQUIRE_HERMES_E2E") != "1":
        return

    from abelion_e2e_support.host import HERMES_COMMIT, OFFER

    expected = os.environ.get("HERMES_EXPECTED_COMMIT", "").strip().lower()
    if len(expected) != 40:
        pytest.exit("REQUIRE_HERMES_E2E=1 but HERMES_EXPECTED_COMMIT is not a full 40-character SHA", returncode=4)
    if OFFER is None or not HERMES_COMMIT:
        pytest.exit("Required Hermes source is not importable; E2E must not pass as skips", returncode=4)
    if HERMES_COMMIT.lower() != expected:
        pytest.exit(
            f"Wrong Hermes source: imported HEAD={HERMES_COMMIT}, required={expected}",
            returncode=4,
        )


def pytest_report_header(config):
    if os.environ.get("REQUIRE_HERMES_E2E") == "1":
        from abelion_e2e_support.host import HERMES_COMMIT
        return f"Verified Hermes core HEAD: {HERMES_COMMIT}"
    return None
