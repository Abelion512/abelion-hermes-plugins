# PR review prompt (copy-ready)

Review the PR diff. Output JSON: {score 0-5, priority P0-P4, findings[], suggestion}.

Rules:
- Logic/security/architecture first, not style nitpicks.
- Score: 5 production-ready, 4 minor polish, 3 fix first, 2 rework, 0-1 rethink.
- P0 = critical/blocking (security, data loss, crash). P1 = high bug. P2 = medium.
  P3 = low nit. P4 = docs/chore low-impact (only case that may auto-merge).
- Cite top-star best practices from docs/pr-review-knowledge/.
- Every finding needs proof: file:line + repro.

## Top-star rules
- Input validation at boundary, no silent failures.
- No eval/exec with untrusted input.
- Error handling: explicit, no empty catch.
- Types: prefer strict, no any without justification.

## Agentic workflow (Anthropic orchestrator-workers)
1. find: logic/security/regression/arch workers in parallel.
2. verify: separate pass drops false positives.
3. rank: severity P0-P4, proof required.
4. post: summary + score + diagram + findings.

## PR diff:
{pr.diff}
