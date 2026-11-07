# PR review knowledge (project rules)

These rules apply to every PR in abelion-hermes-plugins. Changes to this
file change review standards, so they land only through owner review.

- Validate input at the boundary. Never silently swallow failures.
- No eval/exec with untrusted input. No leaked secrets in diffs.
- Privacy guard precedence: PII/credential masking before egress.
- Tests must be synthetic only. No cloud accounts, no real credentials.
- Explicit error handling. No empty catch blocks.
- Strict typing preferred. Justify any dynamic escape.
- Bulk-commit signal (reported, not auto-scored): >5 commits/push,
  >2000 LOC, >200 files, >3 plugin dirs.
- Priority labels are bare: P0, P1, P2, P3, P4. Never prefix them.
- The bot never approves and never merges. Human review decides.

## Staged targets (not implemented yet)

Per the approved spec: summary/diagram/infographic output trio,
feedback-approved learning loop, and big-codebase reference patterns land
after the seeded-PR trial proves the free models. P4 auto-approval is a
later stage and only takes effect if the owner agrees the conditions.
