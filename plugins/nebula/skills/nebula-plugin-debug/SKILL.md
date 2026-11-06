---
name: nebula-plugin-debug
description: Debug and reproduce nebula Privacy Guard failures with a repeatable workflow.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [privacy, debugging, reproduction, policy, e2e]
---

# Nebula Plugin Debug Skill

Systematic debugging for the nebula plugin: figure out which layer breaks
(plugin, host, or model behavior), find the root cause, then fix and prove
it — never patch on a guess and never move on without a failing-state
reproduction first. This is the systematic-debugging workflow applied to
nebula's own surfaces.

## When to Use

- A guarded value (name, email, phone, NIK, credential, path, cookie)
  appears unmasked anywhere it should not.
- A required-mode request is denied and the denial seems wrong, or an
  optional-mode request ships something it should not.
- Mask/restore round trips behave badly, held output stalls, or restore
  slots (read_file / write_file / patch / search_files) restore or block
  when they should not.
- Plugin tests, E2E, or validation matrix disagree about a pattern.

Don't use for: debugging a different community plugin's internals — that is
platform-standard territory. host-level Hermes bugs without a guard angle
belong to the core fork, not here.

## Workflow

1. **Reproduce first, understand later.** Build one deterministic
   reproduction on a disposable profile with synthetic inputs — never the
   daily profile. Keep prompts synthetic ("abelion"), and never place any
   real cookie, map value, account identifier or secret into a repro.
2. **Locate the layer.** Check three suspects in order:
   - host support: is the running core at the pinned commit
     (`HERMES_EXPECTED_COMMIT` / `gh api` pin `9a85916c…`) and does it
     support `hold_stream`, `register_skill`, `register_system_prompt_section`
     at the plugin registration site? (Legacy hosts are refused by design.)
   - plugin guard: which middleware/hook saw the payload —
     `required_policy` (llm_privacy), `optional_request` (llm_request),
     `llm_execution`, `tool_request`, `pre_tool`, `on_session_end`,
     `transform_llm_output` (hold_stream). Use the denial reason, the held
     token list, and the session map (in-process only) as maps.
   - model behavior: does the model copy token text verbatim? If it invents
     literals, the prompt section or token paste is missing, not the guard.
3. **Root cause before patch.** Diff the expectation vs the observed wire
   (loopback provider) or user-visible output. Do not add code to suppress
   a symptom you cannot explain.
4. **Fix where the contract breaks** — usually matching/patterns in
   `_credentials.py` / `_patterns.py`, policy verbs in `guard.py`, or
   redaction behavior in `output_redact.py`.
5. **Prove with a failing-then-passing test.** Add a minimal unit test
   mirroring the repro pattern first (red), then the fix (green). A fix
   without a regression test does not leave the branch.
6. **Verify the whole layer cheaply:** `pytest plugins/nebula/tests -q
   --tb=short` (unit, no live model), add E2E coverage with the loopback
   provider whenever the host's guarantee matters, and update the status
   table in this repo's docs. Do not silently restore credentials.

## Special Notes

- If it reproduces only with real data, construct an equivalent
  synthetic replication instead — the repro log itself must not leak.
- Required-mode denial = user-visible refusal, never a silent leak path;
  diagnose denials as intended behavior first, before labelling them bugs.
- Report only verified denials to the run matrix in `validation/`; that
  area is a historical record — do not rewrite outcomes there.

## Limits

- This handles what nebula can notice. Network transports not covered by
  native Hermes middleware (e.g., direct tool/service traffic, MCP, media
  generation, unknown secret encodings) are not debuggable here.
- Timing-sensitive tests: `test_pathological_inputs_do_not_blow_up` deselect
  on slow hardware; do not loosen the bound to fix a watchdog error.
