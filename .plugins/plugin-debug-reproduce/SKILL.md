---
name: plugin-debug-reproduce
description: Debug and reproduce a plugin issue with tests.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [plugin, debug, reproduce, test, e2e, logs, synthetic]
---

# Plugin Debug and Reproduce Skill

When a plugin in this repo misbehaves, the first question is which layer the problem lives in: plugin code, host integration, install state, or docs/skills. Use this skill to reproduce the issue in the smallest honest way and to avoid claiming a fix before the right test layer says so.

Use this when the user reports a plugin bug, a strange behavior, a false positive/negative, a missing feature, or a failure they saw in CI or on a machine.

## When to Use

- A plugin behaves differently from its docs.
- CI fails and you need to know whether it is a real bug or a setup/prerequisite gap.
- A user reports a privacy/PII/credential leak, a missed redaction, an unexpected denial, a UI issue, an install failure, or a skill not being seen.
- You need to write a reproduction before changing code.

Do not use this skill to guess at a live provider's internal behavior beyond what the repo's tests and docs actually cover. Do not use it to fabricate a pass.

## How to Apply

1. State the scope before touching code.
   - Which plugin, which doc layer claimed the behavior, which test layer would prove it.
   - Whether the issue is in plugin logic, host integration, install state, or docs/skills.
   - Whether it is reproducible in unit tests, in the real-host E2E, or only on a specific machine/profile.

2. Start from the smallest reproducer that still exercises the claimed contract.
   - For in-plugin logic, prefer a unit/regression test first.
   - For host-boundary behavior, use the plugin's real-host E2E harness with a disposable profile and synthetic data.
   - Do not jump to a live provider or a real credential just because the failure sounds "production-like."

3. Use synthetic canaries, never real secrets.
   - If the issue involves a credential-shaped value, reproduce it with a synthetic canary that cannot be a real credential.
   - If the issue involves PII, use synthetic PII.
   - Do not paste real keys, tokens, cookies, or session IDs into tests, logs, docs, or skills.

4. Read the right evidence.
   - Plugin logs and error paths.
   - Test output, including skip reasons.
   - For E2E, the recorded provider/loopback traffic and the actual user-visible output, not only the plugin's in-memory return value.
   - For dashboard/API issues, the dashboard and plugin API behavior the E2E or tests exercise.

5. Separate "not run" from "failed" and "passed."
   - If a test was skipped because a prerequisite was missing, that is not a pass.
   - If a test was not written for the reported behavior, that is not evidence either way.
   - Say which one you have before drawing a conclusion.

6. Update the docs if the issue reveals a real gap.
   - If the plugin's docs implied coverage that did not exist, say so in the relevant doc layer.
   - If the behavior changed, update USAGE/VALIDATION and the status note in the same change.
   - If the issue is docs/skills only, fix the doc/skill and make sure the registration matches.

7. If the issue depends on host version, core commit, or environment, say so explicitly.
   - Do not claim a general fix when it only applies to one pinned host setup.
   - Do not claim a laptop/daily-profile fix from a disposable-profile test.

8. Before calling it fixed, run the layer that actually exercises the change.
   - Unit change → unit test.
   - Host-boundary change → relevant E2E or at least an explicit note that no E2E covers it yet.
   - Docs/skill change → confirm the doc/skill reads correctly and that registration still matches.

## Pitfalls

- Reproducing with real credentials because it feels more realistic.
- Treating a skipped test as evidence.
- Fixing the plugin and forgetting the doc/skill/status table.
- Claiming broad coverage from one synthetic case.
- Confusing a CI environment quirk with a plugin bug, or vice versa.
- Declaring a leak "fixed" because one value no longer appears, without checking the layer that actually proves the boundary.

## Verification

- There is a reproducer that exercises the reported behavior at the right layer.
- The reproducer uses synthetic data and does not embed real credentials.
- The failure mode is explained in terms the docs can match.
- Any code fix has a matching test and doc update where appropriate.
- Any scope limitation is stated honestly.

## Wrong requirement or value

If the report depends on a real credential, a real provider, or a real production profile, do not reproduce it with those things in the repo. If the user wants a claim that the repo cannot support, say what the repo can and cannot prove instead of widening the claim.
