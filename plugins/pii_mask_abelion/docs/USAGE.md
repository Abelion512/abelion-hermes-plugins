# Redact usage for Hermes agents

This documents the current repository implementation, not a published release or a verified installation on a user's laptop. Do not silently replace a separately packaged trial with this revision.

The short session prompt note is registered with `register_system_prompt_section`. The separate bundled skill is registered through native `ctx.register_skill`, and resolves as `pii-mask-abelion:privacy-mask-placeholders` in `skills_list`, `skill_view`, and the new session's `<available_skills>` index while this plugin is enabled. These are native Hermes tools, not new tools implemented here. Older hosts without `register_skill` skip this skill; without the prompt-section API they also skip that note. README alone is not automatically read. Disabled/unloaded plugins do not advertise their registered skill.

Follow [README](../README.md) for the matching local core patch, disposable-profile config, tests, rollback and limits. The model uses exact opaque tokens, not original secrets. Only the documented local path tool slots restore PATH. A capacity denial can need a fresh session or smaller local input; media, foreign-token or unsupported-route denials need the input/route corrected. Never bypass denial by switching to an unguarded provider.

Do not infer a live login cookie from any generic process session ID. Cookie protection is limited to recognized structural/header forms. The skill is advice; mandatory core enforcement is separate. No passwords, cookies, map values or real account identifiers belong in documentation or skills.

## Status: desired, implemented, proven

The pinned-core E2E is [`../e2e/test_privacy_wire.py`](../e2e/test_privacy_wire.py). CI runs it against the exact fork SHA in the repository workflow; it does not certify unmodified stock Hermes. Local instructions are in [`../e2e/README.md`](../e2e/README.md).

| Desired behavior | Implemented | Proven by E2E |
|---|---|---|
| Mask recognized private values in ordinary main-chat requests | Optional `llm_request`/`llm_execution` plugin middleware | Main request: yes; E2E only certifies the synthetic cases listed below |
| Enforce the required local policy before supported provider egress | Requires the matching `agent.privacy_guard` contract in the pinned Hermes core; unsupported stock hosts must reject this guarantee | Required-mode E2E records the actual loopback provider bodies, including auxiliary title requests; see current CI run before describing this as passing |
| Optional mode protects auxiliary/title traffic | Not guaranteed by optional request middleware | No; enable required mode with the matching core if auxiliary egress must be guarded |
| Tool results are masked before they reach the model | Yes | Yes (replay of a tool result) |
| Placeholders are restored only to authorized local destinations, never sent back to the cloud | Documented local path slots only | **Not covered by an E2E** (UNRUN) |
| Public text without a private value stays unchanged | Yes | Yes (benign text) |
| Keep case, typo, session-bound and destination limits | Per README | Not covered by an E2E |

Build or change this feature: edit the code, update this table, and change or add the matching test in the same commit. A behavior moves to "Proven" only when its E2E passes; a failing E2E stays failing and is listed here.
