# Redact usage for Hermes agents

This is documentation for the local v6-derived test candidate, not an already-published release. The exact accepted v6 laptop trial does not include this later skill-registration change.

The short session prompt note is registered with `register_system_prompt_section`. The separate bundled skill is registered through native `ctx.register_skill`, and resolves as `pii-mask-abelion:privacy-mask-placeholders` in `skills_list`, `skill_view`, and the new session's `<available_skills>` index while this plugin is enabled. These are native Hermes tools, not new tools implemented here. Older hosts without `register_skill` skip this skill; without the prompt-section API they also skip that note. README alone is not automatically read. Disabled/unloaded plugins do not advertise their registered skill.

Follow [README](../README.md) for the matching local core patch, disposable-profile config, tests, rollback and limits. The model uses exact opaque tokens, not original secrets. Only the documented local path tool slots restore PATH. A capacity denial can need a fresh session or smaller local input; media, foreign-token or unsupported-route denials need the input/route corrected. Never bypass denial by switching to an unguarded provider.

Do not infer a live login cookie from any generic process session ID. Cookie protection is limited to recognized structural/header forms. The skill is advice; mandatory core enforcement is separate. No passwords, cookies, map values or real account identifiers belong in documentation or skills.
