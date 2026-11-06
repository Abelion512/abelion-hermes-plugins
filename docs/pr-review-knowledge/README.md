# PR review knowledge (top-star best practices)

FF rules apply to every PR in abelion-hermes-plugins.

- Validate input at the boundary. Never silently swallow failures.
- No eval/exec with untrusted input. No leaked secrets in diffs.
- Privacy guard precedence: PII/credential masking before egress.
- Tests must be synthetic only. No cloud accounts, no real credentials.
- Explicit error handling. No empty catch blocks.
- Strict typing preferred. Justify any dynamic escape.
- Bulk-commit guard: >5 commits/push, >2000 LOC, >200 files, >3 plugin dirs.
- Auto-approve at score >= 4.5 with no risks and no bulk flags.
- Auto-merge only P4 docs/chore low-impact. Everything else is comment only.
- Priority labels are bare: P0, P1, P2, P3, P4. Never prefix them.
