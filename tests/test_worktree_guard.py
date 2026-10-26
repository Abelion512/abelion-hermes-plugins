import logging
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worktree_guard_abelion as wg  # noqa: E402

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True,
                          env={**os.environ, **ENV}).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = Path(self.tmp.name).resolve()
        self.repo = t / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "sub").mkdir()
        (self.repo / "a.txt").write_text("x")
        (self.repo / "sub" / "b.txt").write_text("y")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        self.plain = t / "plain"
        self.plain.mkdir()
        self.manual = t / "manual-wt"
        git(self.repo, "worktree", "add", "-q", "-b", "manual", str(self.manual))
        for k in ("HERMES_WORKTREE_GUARD", "HERMES_WORKTREE_GUARD_ALLOW"):
            os.environ.pop(k, None)
        os.environ["TERMINAL_CWD"] = str(self.repo)
        wg._created.clear()
        wg._pending.clear()

    def hook(self, tool, args, task="abc123xyz", cid="c1"):
        return wg._pre_tool_call(tool, args, task_id=task, tool_call_id=cid)

    def wt(self, task="abc123xyz"):
        return Path(f"{self.repo}-worktrees/task-{task[:8]}")

    def assertMainClean(self):
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")


class FileTools(Base):
    def test_write_in_main_is_rerouted_into_new_worktree(self):
        r = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": "y"})
        self.assertEqual(r, {"action": "modify", "args": {"path": str(self.wt() / "a.txt")}})
        self.assertTrue((self.wt() / "a.txt").exists())
        self.assertEqual(git(self.wt(), "branch", "--show-current"), "hermes/task-abc123xy")
        self.assertMainClean()

    def test_nested_new_file_and_reuse(self):
        r1 = self.hook("patch", {"path": "sub/new/n.py", "old_string": "", "new_string": ""})
        self.assertEqual(r1["args"]["path"], str(self.wt() / "sub/new/n.py"))
        r2 = self.hook("write_file", {"path": str(self.repo / "sub" / "b.txt"), "content": ""})
        self.assertEqual(r2["args"]["path"], str(self.wt() / "sub/b.txt"))
        self.assertEqual(git(self.repo, "worktree", "list").count("\n"), 2)  # main, manual, one session worktree

    def test_separate_sessions_get_separate_worktrees(self):
        a = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}, task="aaaaaaaa1")
        b = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}, task="bbbbbbbb2")
        self.assertNotEqual(a["args"]["path"], b["args"]["path"])

    def test_notice_reaches_the_model_once(self):
        self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}, cid="k1")
        out = wg._transform_tool_result("write_file", {}, "ok", task_id="abc123xyz", tool_call_id="k1")
        self.assertIn("re-routed", out)
        self.assertIsNone(wg._transform_tool_result("write_file", {}, "ok", task_id="abc123xyz", tool_call_id="k1"))

    def test_absolute_path_into_main_from_worktree_cwd_still_rerouted(self):
        os.environ["TERMINAL_CWD"] = str(self.manual)
        r = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        self.assertEqual(r["action"], "modify")

    def test_linked_worktrees_allowed(self):
        self.assertIsNone(self.hook("write_file", {"path": str(self.manual / "a.txt"), "content": ""}))

    def test_nested_linked_worktree_inside_main_dir_allowed(self):
        inner = self.repo / ".worktrees" / "i"
        git(self.repo, "worktree", "add", "-q", "-b", "inner", str(inner))
        self.assertIsNone(self.hook("write_file", {"path": str(inner / "a.txt"), "content": ""}))

    def test_non_repo_allowed_by_policy(self):
        self.assertIsNone(self.hook("write_file", {"path": str(self.plain / "f"), "content": ""}))

    def test_symlink_and_traversal_into_main_are_caught(self):
        link = self.plain / "ln"
        link.symlink_to(self.repo)
        self.assertEqual(self.hook("write_file", {"path": str(link / "a.txt"), "content": ""})["action"], "modify")
        p = str(self.manual / ".." / "repo" / "a.txt")
        self.assertEqual(self.hook("write_file", {"path": p, "content": ""})["action"], "modify")
        self.assertMainClean()

    def test_git_dir_and_v4a_are_blocked_with_worktree_path(self):
        r = self.hook("write_file", {"path": str(self.repo / ".git" / "config"), "content": ""})
        self.assertEqual(r["action"], "block")
        body = "*** Begin Patch\n*** Update File: %s\n@@\n-x\n+y\n*** End Patch" % (self.repo / "a.txt")
        r = self.hook("patch", {"mode": "patch", "patch": body})
        self.assertEqual(r["action"], "block")
        self.assertIn(str(self.wt()), r["message"])
        self.assertMainClean()

    def test_plugin_own_files_protected(self):
        r = self.hook("write_file", {"path": os.path.join(wg._PLUGIN_DIR, "__init__.py"), "content": ""})
        self.assertEqual(r["action"], "block")

    def test_read_file_untouched_until_worktree_exists_then_follows_it(self):
        self.assertIsNone(self.hook("read_file", {"path": str(self.repo / "a.txt")}))
        self.assertFalse(self.wt().exists())
        self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        r = self.hook("read_file", {"path": str(self.repo / "a.txt")})
        self.assertEqual(r["args"]["path"], str(self.wt() / "a.txt"))
        self.assertIsNone(self.hook("read_file", {"path": str(self.plain / "x")}))


class Terminal(Base):
    def test_commit_in_main_rerouted_by_workdir(self):
        r = self.hook("terminal", {"command": "git commit -am x"})
        self.assertEqual(r, {"action": "modify", "args": {"workdir": str(self.wt())}})

    def test_git_add_dot_and_subdir_cwd(self):
        r = self.hook("terminal", {"command": "git add .", "workdir": str(self.repo / "sub")})
        self.assertEqual(r["args"]["workdir"], str(self.wt() / "sub"))

    def test_absolute_main_path_from_worktree_cwd_blocked(self):
        r = self.hook("terminal", {"command": f"rm {self.repo}/a.txt", "workdir": str(self.manual)})
        self.assertEqual(r["action"], "block")
        self.assertTrue((self.repo / "a.txt").exists())

    def test_cd_into_main_then_mutate_blocked(self):
        os.environ["TERMINAL_CWD"] = str(self.manual)
        self.assertEqual(self.hook("terminal", {"command": f"cd {self.repo} && git add -A"})["action"], "block")
        self.assertEqual(self.hook("terminal", {"command": "echo hi > ../repo/o.txt"})["action"], "block")

    def test_git_dash_C_main_blocked(self):
        os.environ["TERMINAL_CWD"] = str(self.plain)
        self.assertEqual(self.hook("terminal", {"command": f"git -C {self.repo} commit -am x"})["action"], "block")

    def test_read_only_and_other_cwds_allowed(self):
        for c in ["git status", "git diff", "git log -3", "ls -la", "cat a.txt | wc -l", "FOO=1 git status",
                  "git worktree add -b z ../z", "ls 2>&1", "make 2>/dev/null"]:
            self.assertIsNone(self.hook("terminal", {"command": c}), c)
        self.assertIsNone(self.hook("terminal", {"command": "git commit -am x", "workdir": str(self.manual)}))
        self.assertIsNone(self.hook("terminal", {"command": "rm f", "workdir": str(self.plain)}))
        self.assertMainClean()

    def test_redirect_and_sed_in_main_rerouted(self):
        self.assertEqual(self.hook("terminal", {"command": "echo hi > out.txt"})["action"], "modify")
        self.assertEqual(self.hook("terminal", {"command": "sed -i s/x/y/ a.txt"})["action"], "modify")


class FailSafe(Base):
    def test_creation_failure_blocks_and_leaves_main_untouched(self):
        orig = wg._git
        wg._git = lambda cwd, *a, **k: None if a[:2] == ("worktree", "add") else orig(cwd, *a, **k)
        self.addCleanup(setattr, wg, "_git", orig)
        r = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        self.assertEqual(r["action"], "block")
        self.assertMainClean()

    def test_squatter_directory_blocks(self):
        self.wt().mkdir(parents=True)
        r = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        self.assertEqual(r["action"], "block")

    def test_git_timeout_fails_closed(self):
        orig = wg._git

        def boom(*a, **k):
            raise subprocess.TimeoutExpired("git", 3)
        wg._git = boom
        self.addCleanup(setattr, wg, "_git", orig)
        self.assertEqual(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})["action"], "block")


class DirtyMain(Base):
    def _assert_refused_clean(self, r):
        self.assertEqual(r["action"], "block")
        self.assertIn("uncommitted or untracked", r["message"])
        self.assertFalse(self.wt().exists())

    def test_tracked_change_blocks_creation_and_changes_nothing(self):
        (self.repo / "a.txt").write_text("user work")
        self._assert_refused_clean(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": "z"}))
        self._assert_refused_clean(self.hook("terminal", {"command": "git add -A"}))
        self.assertEqual((self.repo / "a.txt").read_text(), "user work")

    def test_staged_and_untracked_block_too(self):
        (self.repo / "new.py").write_text("1")
        self._assert_refused_clean(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": "z"}))
        git(self.repo, "add", "new.py")
        self._assert_refused_clean(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": "z"}))

    def test_existing_session_worktree_is_not_rechecked(self):
        self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        (self.repo / "later.txt").write_text("late")
        self.assertEqual(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})["action"], "modify")


class ExecuteCode(Base):
    def test_blocked_when_session_cwd_is_main(self):
        r = self.hook("execute_code", {"code": "open('a.txt','w').write('x')"})
        self.assertEqual(r["action"], "block")
        self.assertIn("execute_code", r["message"])

    def test_allowed_in_worktree_non_repo_and_with_explicit_opt_in(self):
        os.environ["TERMINAL_CWD"] = str(self.manual)
        self.assertIsNone(self.hook("execute_code", {"code": "1"}))
        os.environ["TERMINAL_CWD"] = str(self.plain)
        self.assertIsNone(self.hook("execute_code", {"code": "1"}))
        os.environ["TERMINAL_CWD"] = str(self.repo)
        os.environ["HERMES_WORKTREE_GUARD_EXECUTE_CODE"] = "allow"
        self.addCleanup(os.environ.pop, "HERMES_WORKTREE_GUARD_EXECUTE_CODE", None)
        self.assertIsNone(self.hook("execute_code", {"code": "1"}))


class Capability(Base):
    def test_block_only_mode_when_host_cannot_modify(self):
        wg._MODIFY_OK = False
        self.addCleanup(setattr, wg, "_MODIFY_OK", True)
        r = self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        self.assertEqual(r["action"], "block")
        self.assertIn(str(self.wt()), r["message"])
        self.assertEqual(self.hook("terminal", {"command": "git add -A"})["action"], "block")

    def test_load_refused_without_pre_tool_call_hook(self):
        import types
        fake = types.ModuleType("hermes_cli.plugins")
        fake.VALID_HOOKS = {"post_tool_call"}
        saved = sys.modules.get("hermes_cli.plugins")
        sys.modules["hermes_cli.plugins"] = fake
        try:
            with self.assertRaises(RuntimeError):
                wg.register(type("C", (), {"register_hook": lambda *a: None})())
        finally:
            if saved is None:
                sys.modules.pop("hermes_cli.plugins")
            else:
                sys.modules["hermes_cli.plugins"] = saved


class Switches(Base):
    def test_off_and_allow(self):
        os.environ["HERMES_WORKTREE_GUARD"] = "off"
        self.assertIsNone(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}))
        os.environ.pop("HERMES_WORKTREE_GUARD")
        os.environ["HERMES_WORKTREE_GUARD_ALLOW"] = str(self.repo)
        self.assertIsNone(self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""}))

    def test_weakening_is_logged_at_start(self):
        class Ctx:
            def register_hook(self, *a): pass
        os.environ["HERMES_WORKTREE_GUARD"] = "off"
        with self.assertLogs(wg.logger, level=logging.WARNING) as cm:
            wg.register(Ctx())
        self.assertIn("DISABLED", cm.output[0])

    def test_registers_three_hooks(self):
        names = []

        class Ctx:
            def register_hook(self, n, f): names.append(n)
        wg.register(Ctx())
        self.assertEqual(names, ["pre_tool_call", "transform_tool_result", "pre_verify"])


class Handoff(Base):
    def test_pre_verify_nudges_once_for_session_worktree_edits(self):
        self.hook("write_file", {"path": str(self.repo / "a.txt"), "content": ""})
        changed = [str(self.wt() / "a.txt")]
        r = wg._pre_verify(coding=True, attempt=0, changed_paths=changed)
        self.assertEqual(r["action"], "continue")
        self.assertIn("diff --stat", r["message"])
        self.assertIsNone(wg._pre_verify(coding=True, attempt=1, changed_paths=changed))
        self.assertIsNone(wg._pre_verify(coding=True, attempt=0, changed_paths=[str(self.plain / "x")]))


if __name__ == "__main__":
    unittest.main()
