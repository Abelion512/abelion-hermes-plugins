# No-model end-to-end: real Hermes plugin loader + tool dispatch (handle_function_call) on a temp git repo.
# Run: HERMES_SRC=/path/to/hermes-agent python tests/e2e_dispatch.py   (needs Hermes deps installed)
import os, sys, json, subprocess, tempfile, shutil
t = tempfile.mkdtemp(); repo = os.path.join(t, "repo"); home = os.path.join(t, "home")
os.makedirs(repo); os.makedirs(home + "/plugins")
shutil.copytree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worktree_guard_abelion"), home + "/plugins/worktree_guard_abelion", ignore=shutil.ignore_patterns("__pycache__"))
open(home + "/config.yaml", "w").write("plugins:\n  enabled: [worktree-guard-abelion]\n")
os.environ.update(HERMES_HOME=home, TERMINAL_CWD=repo, TERMINAL_ENV="local")
def g(*a, cwd=repo): return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env={**os.environ, "GIT_AUTHOR_NAME":"t","GIT_AUTHOR_EMAIL":"t@t","GIT_COMMITTER_NAME":"t","GIT_COMMITTER_EMAIL":"t@t"}).stdout.strip()
g("init", "-q", "-b", "main"); open(repo + "/a.txt", "w").write("orig\n"); g("add", "."); g("commit", "-qm", "i")
sys.path.insert(0, os.environ["HERMES_SRC"])
import model_tools
from hermes_cli.plugins import discover_plugins
discover_plugins()
H = model_tools.handle_function_call
TID = "sess9876abc"
def show(label, r): print(f"--- {label}\n{str(r)[:700]}")
show("patch in main", H("patch", {"path": repo + "/a.txt", "old_string": "orig", "new_string": "changed"}, task_id=TID, tool_call_id="t1"))
print("main a.txt:", repr(open(repo + "/a.txt").read()), "| main status:", repr(g("status", "--porcelain")))
wt = f"{repo}-worktrees/task-sess9876"
print("wt a.txt:", repr(open(wt + "/a.txt").read()))
show("read main path after wt exists", H("read_file", {"path": repo + "/a.txt"}, task_id=TID, tool_call_id="t1b"))
show("write_file main path after read", H("write_file", {"path": repo + "/a.txt", "content": "again\n"}, task_id=TID, tool_call_id="t1c"))
print("wt a.txt:", repr(open(wt + "/a.txt").read()), "| main:", repr(open(repo + "/a.txt").read()))
show("terminal commit in main cwd", H("terminal", {"command": "git commit -qam 'agent change' && git log --oneline -2 && pwd"}, task_id=TID, tool_call_id="t2"))
print("main log:", g("log", "--oneline"), "| wt branch log:", g("log", "--oneline", cwd=wt))
show("terminal rm abs main path", H("terminal", {"command": f"rm {repo}/a.txt", "workdir": wt}, task_id=TID, tool_call_id="t3"))
print("main a.txt still exists:", os.path.exists(repo + "/a.txt"))
show("read-only git status", H("terminal", {"command": "git status -s && echo ro-ok"}, task_id=TID, tool_call_id="t4"))
show("write .git", H("write_file", {"path": repo + "/.git/hooks/pre-commit", "content": "x"}, task_id=TID, tool_call_id="t5"))
show("write non-repo", H("write_file", {"path": t + "/free.txt", "content": "x"}, task_id=TID, tool_call_id="t6"))
