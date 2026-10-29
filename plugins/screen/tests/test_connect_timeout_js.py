"""Tab-side regression: a stalled RFB connect must not lock the Screen tab on
"menyambung..." forever (real dist/index.js, dependency-free node harness)."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_stalled_connect_does_not_lock_tab():
    script = Path(__file__).parent / "js" / "connect_timeout.test.mjs"
    r = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
