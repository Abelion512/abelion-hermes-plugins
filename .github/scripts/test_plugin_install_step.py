"""Run the plugin job's 'install test deps and pip-audit' step with a fake python, the way Actions runs it (bash -e)."""
import os, pathlib, stat, subprocess, tempfile, unittest
import yaml

WORKFLOW = pathlib.Path(os.environ.get("CI_WORKFLOW", pathlib.Path(__file__).resolve().parents[1] / "workflows" / "ci.yml"))
STEP = "install test deps and pip-audit"

def script():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in wf["jobs"]["plugin"]["steps"]:
        if step.get("name") == STEP:
            return step["run"]
    raise AssertionError("install step not found")

class InstallStep(unittest.TestCase):
    def run_step(self, requirements):
        """requirements: {filename: content} placed in <plugin>/tests/. A fake python logs its args and fails on 'FAIL' files."""
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            tests = root / "plugins" / "p" / "tests"
            tests.mkdir(parents=True)
            for name, content in requirements.items():
                (tests / name).write_text(content)
            bindir = root / "bin"
            bindir.mkdir()
            fake = bindir / "python"
            fake.write_text('#!/bin/sh\necho "$@" >> "$FAKE_LOG"\nfor a in "$@"; do\n'
                            '  if [ -f "$a" ] && grep -q FAIL "$a"; then exit 1; fi\ndone\nexit 0\n')
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", P="plugins/p", FAKE_LOG=str(root / "log"))
            r = subprocess.run(["bash", "-e", "-c", script()], cwd=d, env=env, capture_output=True, text=True, timeout=60)
            log = (root / "log").read_text() if (root / "log").exists() else ""
            return r, log

    def test_no_requirements_file_succeeds(self):
        r, log = self.run_step({})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pip-audit", log)

    def test_valid_requirements_file_is_installed(self):
        r, log = self.run_step({"requirements-test.txt": "ok\n"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("-r plugins/p/tests/requirements-test.txt", log)

    def test_failing_requirements_install_still_fails(self):
        r, log = self.run_step({"requirements.txt": "FAIL\n"})
        self.assertNotEqual(r.returncode, 0)

    def test_failing_first_of_two_files_fails(self):
        r, log = self.run_step({"requirements-a.txt": "FAIL\n", "requirements-b.txt": "ok\n"})
        self.assertNotEqual(r.returncode, 0)

if __name__ == "__main__":
    unittest.main()
