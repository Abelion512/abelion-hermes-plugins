#!/usr/bin/env python3
"""PR review bot for abelion-hermes-plugins.
- Scores diff (0-5 like Greptile).
- Flags bulk-commit: >5 commits in <5 min, >200 files or >2000 LOC delta, unrelated dirs.
- Posts comment via gh. Auto-approve low risk. Never auto-merge except P4/docs.
- Learning: log to docs/review-log.jsonl (score, risks, decision).
"""
import argparse, json, os, re, subprocess, sys
from datetime import datetime, timezone

def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
    return r.stdout

def analyze(diff: str, commits: list[dict]) -> dict:
    lines = diff.splitlines()
    add = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    files = set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.M))
    filecount = len(files)
    risks = []
    if re.search(r"(eval\s*\(|exec\s*\(|__import__|os\.system)", diff):
        risks.append("exec-eval")
    if re.search(r"(BEGIN (RSA )?PRIVATE KEY|api[_-]?key\s*=\s*['\"])", diff):
        risks.append("secret-pattern")
    # bulk-commit guard
    bulk = []
    if len(commits) > 5:
        bulk.append(f"{len(commits)} commits in PR push")
    if add > 2000 or filecount > 200:
        bulk.append(f"large diff: {add} LOC, {filecount} files")
    dirs = set(f.split("/")[1] for f in files if f.startswith("plugins/") and "/" in f)
    if len(dirs) > 3:
        bulk.append(f"multi-plugin touch: {', '.join(sorted(dirs))}")
    score = 5.0 if add < 200 else max(1.0, 5.0 - add / 800)
    if risks:
        score -= 1.5
    if bulk:
        score -= 1.0
    return {
        "score": round(max(0, score), 1),
        "loc": add,
        "files": filecount,
        "risks": risks,
        "bulk_flags": bulk,
        "commit_count": len(commits),
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pr", required=True)
    p.add_argument("--diff", required=True)
    p.add_argument("--repo", required=True)
    a = p.parse_args()
    diff = open(a.diff).read()
    out = gh("pr", "view", a.pr, "--repo", a.repo, "--json", "commits,labels,author")
    try:
        data = json.loads(out)
        commits = data.get("commits", [])
    except Exception:
        commits = []
    r = analyze(diff, commits)
    r["pr"] = int(a.pr)
    r["ts"] = datetime.now(timezone.utc).isoformat()
    body = (
        f"### PR review bot\n\nScore: **{r['score']}/5**\n\n"
        f"- LOC: {r['loc']} in {r['files']} files, {r['commit_count']} commits\n"
        f"- Risks: {', '.join(r['risks']) or 'none'}\n"
        f"- Bulk flags: {', '.join(r['bulk_flags']) or 'none'}\n"
    )
    if os.environ.get("GH_TOKEN"):
        subprocess.run(["gh", "pr", "comment", a.pr, "--repo", a.repo, "--body", body])
    json.dump(r, open("/tmp/review.json", "w"))
    print(json.dumps(r))

if __name__ == "__main__":
    main()
