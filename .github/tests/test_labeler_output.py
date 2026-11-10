"""Execute the actual labeler workflow shell step, without GitHub API access."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/labeler.yml"


class LabelerOutputTest(unittest.TestCase):
    def run_step(self, output_mode):
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        step = next(s for s in workflow["jobs"]["label"]["steps"]
                    if s.get("name") == "merge plugin-local labels")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github").mkdir()
            (root / ".github/labeler.yml").write_text("ci: []\n", encoding="utf-8")
            plugin = root / "plugins/example/.github"
            plugin.mkdir(parents=True)
            (plugin / "labels.yml").write_text(
                "tests:\n  - changed-files:\n      - any-glob-to-any-file: 'tests/**'\n",
                encoding="utf-8")
            output = root / "github-output"
            output.write_text("previous=value\n", encoding="utf-8")
            env = os.environ.copy()
            env.pop("GITHUB_OUTPUT", None)
            if output_mode == "file":
                env["GITHUB_OUTPUT"] = str(output)
            elif output_mode == "empty":
                env["GITHUB_OUTPUT"] = ""
            result = subprocess.run(["bash", "-e", "-c", step["run"]],
                                    cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = "merged_labeler_path=merged_labeler.yml\nlabels_count=2\n"
            if output_mode == "file":
                self.assertEqual(output.read_text(encoding="utf-8"), "previous=value\n" + expected)
                self.assertEqual(result.stdout, "")
            else:
                self.assertEqual(result.stdout, expected)
                self.assertEqual(output.read_text(encoding="utf-8"), "previous=value\n")
            merged = yaml.safe_load((root / "merged_labeler.yml").read_text(encoding="utf-8"))
            self.assertEqual(set(merged), {"ci", "tests"})
            self.assertEqual(merged["tests"][0]["changed-files"][0]["any-glob-to-any-file"],
                             ["plugins/example/tests/**"])

    def test_github_output_appends_both_outputs(self):
        self.run_step("file")

    def test_missing_github_output_uses_stdout(self):
        self.run_step("missing")

    def test_empty_github_output_uses_stdout(self):
        self.run_step("empty")


if __name__ == "__main__":
    unittest.main()
