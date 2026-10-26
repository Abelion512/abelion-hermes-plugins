import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worktree_guard_abelion as wg  # noqa: E402


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name, "repo").resolve()
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("x")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        self.wt = Path(self.tmp.name, "repo-worktrees", "t1").resolve()
        git(self.repo, "worktree", "add", "-q", "-b", "hermes/t1", str(self.wt))
        self.plain = Path(self.tmp.name, "plain").resolve()
        self.plain.mkdir()
        os.environ.pop("HERMES_WORKTREE_GUARD", None)
        os.environ.pop("HERMES_WORKTREE_GUARD_ALLOW", None)
        os.environ["TERMINAL_CWD"] = str(self.repo)

    def run_hook(self, tool, args, task="abc123xyz"):
        return wg._hook(tool, args, task_id=task)


class FileTools(Base):
    def test_write_in_main_blocked_with_fix(self):
        r = self.run_hook("write_file", {"path": str(self.repo / "a.txt"), "content": "y"})
        self.assertEqual(r["action"], "block")
        self.assertIn("git -C", r["message"])
        self.assertIn("worktree add", r["message"])
        self.assertIn("task-abc123", r["message"])

    def test_new_file_in_new_subdir_of_main_blocked(self):
        self.assertTrue(self.run_hook("write_file", {"path": str(self.repo / "n/x.py"), "content": ""}))

    def test_relative_path_uses_session_cwd(self):
        self.assertTrue(self.run_hook("patch", {"path": "a.txt", "old_string": "x", "new_string": "y"}))

    def test_linked_worktree_allowed(self):
        self.assertIsNone(self.run_hook("write_file", {"path": str(self.wt / "a.txt"), "content": "y"}))

    def test_worktree_inside_main_tree_allowed(self):
        inner = self.repo / ".worktrees" / "i"
        git(self.repo, "worktree", "add", "-q", "-b", "hermes/i", str(inner))
        self.assertIsNone(self.run_hook("write_file", {"path": str(inner / "a.txt"), "content": "y"}))

    def test_non_repo_allowed(self):
        self.assertIsNone(self.run_hook("write_file", {"path": str(self.plain / "f"), "content": ""}))

    def test_symlink_into_main_blocked(self):
        link = self.plain / "ln"
        link.symlink_to(self.repo)
        self.assertTrue(self.run_hook("write_file", {"path": str(link / "a.txt"), "content": ""}))

    def test_traversal_into_main_blocked(self):
        p = str(self.wt / ".." / ".." / "repo" / "a.txt")
        self.assertTrue(self.run_hook("write_file", {"path": p, "content": ""}))

    def test_v4a_patch_body_checked(self):
        body = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch" % (self.repo / "a.txt")
        self.assertTrue(self.run_hook("patch", {"mode": "patch", "patch": body}))

    def test_read_file_never_blocked(self):
        self.assertIsNone(self.run_hook("read_file", {"path": str(self.repo / "a.txt")}))


class Terminal(Base):
    def test_git_commit_in_main_blocked(self):
        self.assertTrue(self.run_hook("terminal", {"command": "git commit -am x"}))

    def test_git_commit_with_workdir_in_worktree_allowed(self):
        self.assertIsNone(self.run_hook("terminal", {"command": "git commit -am x", "workdir": str(self.wt)}))

    def test_workdir_in_main_overrides_safe_default(self):
        os.environ["TERMINAL_CWD"] = str(self.wt)
        self.assertTrue(self.run_hook("terminal", {"command": "rm a.txt", "workdir": str(self.repo)}))

    def test_redirect_blocked_but_devnull_and_stderr_merge_ok(self):
        self.assertTrue(self.run_hook("terminal", {"command": "echo hi > out.txt"}))
        self.assertIsNone(self.run_hook("terminal", {"command": "ls 2>&1"}))
        self.assertIsNone(self.run_hook("terminal", {"command": "make 2>/dev/null"}))

    def test_sed_inplace_and_chain_blocked(self):
        self.assertTrue(self.run_hook("terminal", {"command": "sed -i s/x/y/ a.txt"}))
        self.assertTrue(self.run_hook("terminal", {"command": "cd /tmp && git add -A"}))

    def test_read_only_commands_allowed(self):
        for c in ["git status", "git diff", "git log -3", "pytest -q", "ls -la", "cat a.txt | wc -l",
                  "git worktree add -b hermes/z ../z", "FOO=1 git status"]:
            self.assertIsNone(self.run_hook("terminal", {"command": c}), c)

    def test_non_repo_cwd_allowed(self):
        self.assertIsNone(self.run_hook("terminal", {"command": "rm f", "workdir": str(self.plain)}))


class Switches(Base):
    def test_off(self):
        os.environ["HERMES_WORKTREE_GUARD"] = "off"
        self.assertIsNone(self.run_hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}))

    def test_allowlist(self):
        os.environ["HERMES_WORKTREE_GUARD_ALLOW"] = str(self.repo)
        self.assertIsNone(self.run_hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}))

    def test_git_timeout_fails_closed(self):
        orig = wg._git
        def boom(*a, **k):
            raise subprocess.TimeoutExpired("git", 3)
        wg._git = boom
        self.addCleanup(setattr, wg, "_git", orig)
        r = self.run_hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        self.assertEqual(r["action"], "block")

    def test_register(self):
        calls = []
        class Ctx:
            def register_hook(self, name, fn): calls.append(name)
        wg.register(Ctx())
        self.assertEqual(calls, ["pre_tool_call"])


if __name__ == "__main__":
    unittest.main()
