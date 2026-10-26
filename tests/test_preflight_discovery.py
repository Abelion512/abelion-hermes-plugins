"""Regression: preflight must never run a shell on preflight.py (reported on a device whose `hermes` launcher is a shell script)."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PRE = Path(__file__).resolve().parents[1] / "worktree_guard_abelion" / "preflight.py"


class Discovery(unittest.TestCase):
    def test_shell_launcher_is_never_used_as_interpreter(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d, "bin"); b.mkdir()
            h = b / "hermes"; h.write_text('#!/bin/sh\nexec /bin/true "$@"\n'); h.chmod(h.stat().st_mode | stat.S_IXUSR)
            i = b / "import"; i.write_text("#!/bin/sh\nexit 0\n"); i.chmod(0o755)  # ImageMagick-style `import` that 'succeeds'
            env = dict(os.environ, PATH=f"{b}:{os.environ['PATH']}", HOME=d, HERMES_HOME=d)
            env.pop("PYTHONPATH", None)
            r = subprocess.run([sys.executable, "-S", str(PRE)], env=env, capture_output=True, text=True, timeout=60)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("cannot find a Python", out)
        self.assertNotIn("Syntax error", out)
        self.assertNotIn("File name too long", out)


if __name__ == "__main__":
    unittest.main()
