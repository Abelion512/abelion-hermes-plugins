# output-redact-abelion

A Hermes plugin for pattern-based final-text credential redaction. The plugin registers `transform_llm_output` with `hold_stream=True`; older hosts lacking that parameter are refused. It adds a parenthetical prose detector and delegates to Hermes's native `redact_sensitive_text`.

This is not a replacement for required outbound privacy. When pii-mask-abelion is loaded, this plugin yields to its session-local final transform rather than destroying reversible tokens. It does not own the required core callback, inspect all network traffic or restore credentials. Non-text output, a missing native redactor or a redactor exception returns an OUTPUT_WITHHELD marker. This local failure branch does not make the optional host hook a mandatory network boundary.

## Use in a disposable profile

Use a compatible Hermes host and place this directory under the temporary profile's `plugins/`. Add `output-redact-abelion` to that profile's `plugins.enabled`, restart the test process and start a new session. Do not alter a daily profile based on a synthetic test. There is no additional API key or dependency.

To disable, stop the test process, remove the plugin from `plugins.enabled`, then restart. If required local redact is also enabled, keep its own policy plugin/config intact; removing this optional output plugin does not disable that core contract.

## Agent skill

`ctx.register_skill` exposes `output-redact-abelion:redacted-output-handling` through native Hermes `skills_list`, `skill_view` and the `<available_skills>` index while enabled. Older hosts without that API skip the skill. See [usage](docs/USAGE.md) and [skill](skills/redacted-output-handling/SKILL.md).

## Verification and limits

Use synthetic values only. Confirm known patterns are redacted, ordinary text remains, and the two-plugin case yields to the mapping guard. Redaction can miss unknown encodings and can change innocent text that resembles credentials. This does not verify every transport, progress UI, log, real provider or laptop.

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
