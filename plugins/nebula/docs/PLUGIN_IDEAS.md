# Nebula ideas and features

Use this file as the readable running list for ideas, supported behavior, and
known gaps. Keep it simple. If something is important enough to track, it should
live here or in the matching test/docs entry.

## Supported behavior

- Session-local masking of recognized PII, credential-shaped values, and local
  paths, using opaque per-session tokens.
- Held-output redaction path through the consolidated plugin output hook.
- Required-policy enforcement path when the matching required core is present.
- Only documented local path tool slots restore PATH tokens; credentials never
  restore.
- Recognized structural session/cookie material is treated as sensitive; generic
  process session IDs are not proof of credentials.

## Ideas being tracked

- Stronger INTERNAL prose-wide masking policy, if ever desired. This is not the
  current configured contract.
- Clearer restore/block matrix for delegate goals and shell-bound workflows.
- More explicit E2E coverage for restore boundaries where host behavior matters.

## Gaps and limits

- Optional request middleware does not guarantee auxiliary/title egress masking.
- Restore only targets documented PATH slots; other destinations are blocked.
- Unknown secret encodings can pass.
- Direct tool/service traffic, persisted prompts, UI/logs, and unsupported
  transports are not universally covered.
- E2E gaps remain for some documented restore behavior.

## Status source

For current status, see `docs/USAGE.md` and `docs/VALIDATION.md`. This file is
the readable summary; those files are the contract.
