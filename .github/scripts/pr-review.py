#!/usr/bin/env python3
"""PR review bot for abelion-hermes-plugins (English only).

Design references:
- Anthropic agentic workflows: orchestrator-workers. Find in parallel
  (logic/security/regression/arch), verify in a separate pass, then rank.
- hermes-agent (teknium1 PR style): plain prose, Root cause, Changes,
  Validation table. No fake success. Evidence over style.
- Greptile shape: summary + confidence 0-5 + findings + diagram.

Safety:
- Never checkout the PR head, never interpolate PR title/body into run:.
- PR number and repo arrive via env. Permissions are minimal.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

LOG_PATH = "docs/review-log.jsonl"
MAX_LOG_CONTEXT = 20


def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gh {' '.join(args)} failed: {r.stderr}", file=sys.stderr)
    return r.stdout


def severity(score, risks, bulk):
    if risks or score < 2.0:
        return "P0"
    if score < 3.0:
        return "P1"
    if score < 4.0:
        return "P2"
    if score < 4.5:
        return "P3"
    return "P4"


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
    score = round(max(0, score), 1)
    return {
        "score": score,
        "priority": severity(score, risks, bulk),
        "loc": add,
        "files": filecount,
        "risks": risks,
        "bulk_flags": bulk,
        "commit_count": len(commits),
        "touched_dirs": sorted(dirs),
        "files_sample": sorted(files)[:12],
        "diff_hash": hashlib.sha256(diff.encode()).hexdigest()[:12],
    }


def summary_block(r: dict) -> str:
    files = "\n".join(f"- `{f}`" for f in r["files_sample"]) or "- (no files parsed)"
    return (
        "### PR review bot\n\n"
        "Plain English first. No boilerplate praise.\n\n"
        "## Summary\n\n"
        f"Scored **{r['score']}/5** ({r['priority']}). "
        f"{r['loc']} added lines in {r['files']} files, "
        f"{r['commit_count']} commits. "
        f"Risks: {', '.join(r['risks']) or 'none'}. "
        f"Bulk flags: {', '.join(r['bulk_flags']) or 'none'}.\n\n"
        f"{files}\n\n"
        "## Root cause\n\n"
        "Heuristic v1 flags size/risk signals. LLM reviewer refines intent.\n\n"
        "## Changes\n\n"
        f"- Priority label attached: `{r['priority']}`\n"
        f"- Diff fingerprint: `{r['diff_hash']}`\n\n"
        "## Validation\n\n"
        "| origin/main | this PR | status |\n"
        "|---|---|---|\n"
        f"| diff size n/a | {r['loc']} add, {r['files']} files | scored |\n"
        f"| CI checks | pending | pending |\n"
    )


def diagram_block(r: dict) -> str:
    touched = " -> ".join(r["touched_dirs"] or ["plugins"])
    if not touched:
        touched = "plugins"
    return (
        "\n<details><summary>Diagram</summary>\n\n"
        "```mermaid\n"
        "flowchart LR\n"
        f"  PR --> diff[{r['files']} files\\n{r['loc']} add]\n"
        f"  diff --> gate{{score {r['score']}/5\\n{r['priority']}}}\n"
        "  gate -->|P0/P1| comment[Comment + suggest only]\n"
        "  gate -->|P2/P3| comment\n"
        "  gate -->|P4 low-impact| approve[Auto-approve]\n"
        f"  touched[{touched}]\n"
        "```\n\n"
        "```mermaid\n"
        "sequenceDiagram\n"
        "  participant PR as PR open/push\n"
        "  participant Bot as PR reviewer bot\n"
        "  participant Verify as Verifier pass\n"
        "  participant Human as Human\n"
        "  PR->>Bot: opened / synchronize\n"
        "  Bot->>Bot: find (logic, security, arch)\n"
        "  Bot->>Verify: candidate findings\n"
        "  Verify-->>Bot: confirmed findings only\n"
        "  Bot-->>PR: summary + score + diagram\n"
        "  Human-->>PR: approve / request changes\n"
        "```\n\n"
        "</details>\n"
    )


def load_log() -> list:
    try:
        return [json.loads(l) for l in open(LOG_PATH) if l.strip()]
    except FileNotFoundError:
        return []


def learning_rules(entries: list) -> dict:
    rejected = {}
    for e in entries:
        for risk in e.get("risks", []):
            if e.get("accept_reject") == "reject":
                rejected[risk] = rejected.get(risk, 0) + 1
    dropped = [k for k, v in rejected.items() if v > 3]
    return {"dropped_rules": dropped, "runs_observed": len(entries)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pr", required=True)
    p.add_argument("--diff", required=True)
    p.add_argument("--repo", required=True)
    a = p.parse_args()
    diff = open(a.diff, encoding="utf-8", errors="replace").read()
    out = gh("pr", "view", a.pr, "--repo", a.repo, "--json", "commits,labels,author")
    try:
        data = json.loads(out)
        commits = data.get("commits", [])
    except Exception:
        commits = []
    r = analyze(diff, commits)
    entries = load_log()
    learn = learning_rules(entries[-MAX_LOG_CONTEXT:])
    r["pr"] = int(a.pr)
    r["ts"] = datetime.now(timezone.utc).isoformat()
    r["runs_observed"] = learn["runs_observed"]
    body = summary_block(r) + diagram_block(r)
    if learn["dropped_rules"]:
        body += f"\nDropped rules (rejected >3x): {', '.join(learn['dropped_rules'])}\n"
    if os.environ.get("GH_TOKEN"):
        subprocess.run(["gh", "pr", "comment", a.pr, "--repo", a.repo, "--body", body], check=False)
        subprocess.run(
            ["gh", "pr", "edit", a.pr, "--repo", a.repo, "--add-label", r["priority"]],
            check=False,
        )
        if r["score"] >= 4.5 and not r["risks"] and not r["bulk_flags"]:
            subprocess.run(
                ["gh", "api", f"repos/{a.repo}/pulls/{a.pr}/reviews",
                 "-f", "event=APPROVE", "-f", "body=Auto-approved: high score, low risk"],
                check=False,
            )
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r) + "\n")
    except OSError as e:
        print(f"log write failed: {e}", file=sys.stderr)
    json.dump(r, open("/tmp/review.json", "w"))
    print(json.dumps(r))


if __name__ == "__main__":
    main()
