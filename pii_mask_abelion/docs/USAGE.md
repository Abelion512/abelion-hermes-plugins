# Redact usage for Hermes agents

This is documentation for the local v6-derived test candidate, not an already-published release. The exact accepted v6 laptop trial does not include this later skill-registration change.

The short session prompt note is registered with `register_system_prompt_section`. The separate bundled skill is registered through native `ctx.register_skill`, and resolves as `pii-mask-abelion:privacy-mask-placeholders` in `skills_list`, `skill_view`, and the new session's `<available_skills>` index while this plugin is enabled. These are native Hermes tools, not new tools implemented here. Older hosts without `register_skill` skip this skill; without the prompt-section API they also skip that note. README alone is not automatically read. Disabled/unloaded plugins do not advertise their registered skill.

Follow [README](../README.md) for the matching local core patch, disposable-profile config, tests, rollback and limits. The model uses exact opaque tokens, not original secrets. Only the documented local path tool slots restore PATH. A capacity denial can need a fresh session or smaller local input; media, foreign-token or unsupported-route denials need the input/route corrected. Never bypass denial by switching to an unguarded provider.

Do not infer a live login cookie from any generic process session ID. Cookie protection is limited to recognized structural/header forms. The skill is advice; mandatory core enforcement is separate. No passwords, cookies, map values or real account identifiers belong in documentation or skills.

## Status: desired, implemented, proven

Draft for review. Proof means an E2E in [`e2e/test_privacy_wire.py`](../../e2e/test_privacy_wire.py) on real Hermes upstream main 8acb7f65 (see [`e2e/README.md`](../../e2e/README.md) to run it).

| Desired behavior | Implemented | Proven by E2E |
|---|---|---|
| The model API never receives an original private value (credentials, usernames, PII), in any call | Main chat request only, through `llm_request`/`llm_execution` | Main request: yes. Auxiliary calls (session title): **no, they leak** (Hermes has no hook that can change an auxiliary request, a core limit) |
| Mask what was missed; block what cannot be made safe | Masking yes. Blocking needs the required mode | Required mode: **no**, `llm_privacy` is an unknown middleware on this Hermes, so requests are still sent |
| Tool results are masked before they reach the model | Yes | Yes (replay of a tool result) |
| Placeholders are restored only to authorized local destinations, never sent back to the cloud | Documented local path slots only | **Not covered by an E2E** (UNRUN) |
| Public text without a private value stays unchanged | Yes | Yes (benign text) |
| Keep case, typo, session-bound and destination limits | Per README | Not covered by an E2E |

Build or change this feature: edit the code, update this table, and change or add the matching test in the same commit. A behavior moves to "Proven" only when its E2E passes; a failing E2E stays failing and is listed here.
