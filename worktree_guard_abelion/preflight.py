#!/usr/bin/env python3
"""Pre-enable check for worktree-guard-abelion. Safe: temp HERMES_HOME + temp git repos, no model, no network.

Loads this plugin into a throwaway Hermes home through Hermes' real plugin loader and tool dispatch, then
proves (or disproves) that this Hermes honours the hooks the guard depends on. Exit 0 = PASS, enable it.
Anything else = do NOT enable: on an unsupported Hermes the guard could silently let main-checkout writes through.

    python3 preflight.py          # finds Hermes' Python itself; or run it with Hermes' own python
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _find_hermes_python():
    try:
        import hermes_cli  # noqa: F401
        return None
    except ImportError:
        pass
    cands = []
    exe = shutil.which("hermes")
    if exe:
        first = Path(exe).resolve().read_text(errors="ignore").splitlines()[:1] if Path(exe).resolve().is_file() else []
        if first and first[0].startswith("#!") and "env" not in first[0]:
            cands.append(first[0][2:].split()[0])
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    for sub in ("hermes-agent/venv/bin/python", "hermes-agent/.venv/bin/python"):
        cands.append(str(home / sub))
    for c in cands:
        if Path(c).exists() and subprocess.run([c, "-c", "import hermes_cli"], capture_output=True).returncode == 0:
            return c
    return "none"


def main() -> int:
    py = _find_hermes_python()
    if py == "none":
        print("FAIL: cannot find a Python that can import hermes_cli. Run this file with Hermes' own Python.")
        return 2
    if py:
        return subprocess.call([py, str(Path(__file__).resolve())])

    tmp = Path(tempfile.mkdtemp(prefix="wg-preflight-")).resolve()
    home = tmp / "home"
    (home / "plugins").mkdir(parents=True)
    shutil.copytree(HERE, home / "plugins" / "worktree_guard_abelion",
                    ignore=shutil.ignore_patterns("__pycache__", "preflight.py"))
    (home / "config.yaml").write_text("plugins:\n  enabled: [worktree-guard-abelion]\n")
    os.environ.update(HERMES_HOME=str(home), TERMINAL_ENV="local")
    for k in ("HERMES_WORKTREE_GUARD", "HERMES_WORKTREE_GUARD_ALLOW", "HERMES_WORKTREE_GUARD_EXECUTE_CODE"):
        os.environ.pop(k, None)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def g(cwd, *a):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env=env).stdout.strip()

    def mkrepo(name):
        r = tmp / name
        r.mkdir()
        g(r, "init", "-q", "-b", "main")
        (r / "a.txt").write_text("orig\n")
        g(r, "add", ".")
        g(r, "commit", "-qm", "i")
        return r

    results = []

    def check(label, ok):
        results.append(ok)
        print(("PASS  " if ok else "FAIL  ") + label)

    try:
        from hermes_cli import plugins as P
        P.discover_plugins()
        import model_tools
        H = model_tools.handle_function_call
        gm = sys.modules.get("worktree_guard_abelion") or next(
            (m for n, m in sys.modules.items() if n.endswith("worktree_guard_abelion") and hasattr(m, "_MODIFY_OK")), None)
        check("plugin loaded by Hermes' loader", gm is not None)
        check("host applies modified tool args (modify supported)", bool(gm and gm._MODIFY_OK))

        repo = mkrepo("repo")
        os.environ["TERMINAL_CWD"] = str(repo)
        wt = Path(f"{repo}-worktrees/task-pf000001")
        T = dict(task_id="pf000001")
        H("write_file", {"path": str(repo / "a.txt"), "content": "changed\n"}, tool_call_id="1", **T)
        check("write in main checkout creates a session worktree and leaves main unchanged",
              (wt / "a.txt").exists() and g(repo, "status", "--porcelain") == "" and (repo / "a.txt").read_text() == "orig\n")
        H("patch", {"path": str(repo / "a.txt"), "old_string": "orig", "new_string": "patched"}, tool_call_id="2", **T)
        check("patch re-routed; main file untouched", (repo / "a.txt").read_text() == "orig\n" and g(repo, "status", "--porcelain") == "")
        H("terminal", {"command": "git commit -qam agent"}, tool_call_id="3", **T)
        check("git commit from main cwd lands on the session branch only",
              "agent" in g(wt, "log", "--oneline") and "agent" not in g(repo, "log", "--oneline"))
        H("terminal", {"command": f"rm {repo}/a.txt", "workdir": str(wt)}, tool_call_id="4", **T)
        check("absolute-path delete of a main file is blocked", (repo / "a.txt").exists())
        out = H("execute_code", {"code": f"open({str(repo / 'x.txt')!r},'w').write('x')"}, tool_call_id="5", **T)
        check("execute_code is blocked while cwd is a main checkout", not (repo / "x.txt").exists() and "worktree-guard" in out)
        out = H("terminal", {"command": "git status -s && echo ro-ok"}, tool_call_id="6", **T)
        check("read-only terminal command still works", "ro-ok" in out)
        msg = P.get_pre_verify_continue_message(session_id="pf000001", coding=True, attempt=0,
                                                changed_paths=[str(wt / "a.txt")])
        check("pre_verify nudge fires for edits in the session worktree (a nudge, not enforcement)", bool(msg and "diff --stat" in msg))

        dirty = mkrepo("dirty")
        (dirty / "a.txt").write_text("user work\n")
        os.environ["TERMINAL_CWD"] = str(dirty)
        out = H("write_file", {"path": str(dirty / "a.txt"), "content": "z"}, tool_call_id="7", task_id="pf000002")
        check("dirty main checkout: refused, nothing created or changed",
              "uncommitted" in out and (dirty / "a.txt").read_text() == "user work\n"
              and not Path(f"{dirty}-worktrees/task-pf000002").exists())
    except Exception as exc:  # any surprise is a failure, never a silent pass
        print(f"FAIL  preflight crashed: {type(exc).__name__}: {exc}")
        results.append(False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = bool(results) and all(results)
    print("\nPREFLIGHT " + ("PASS: safe to enable on this Hermes." if ok else "FAILED: do NOT enable the plugin."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
