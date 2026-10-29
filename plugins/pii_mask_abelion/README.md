# Privacy Guard for Hermes Agent

This plugin combines Hermes's native secret redactor with session-local masking for PII, credentials and paths. The repository merge is not a release, an installed-profile migration, or verification on a user's laptop. Do not enable it for daily use based only on unit-test counts.

## Required host

Mandatory mode requires the exact Hermes fork commit `9a85916c87d56c2ca00b02fad8918f93ef1816e9` from `Abelion512/hermes-4gent`. CI pins and verifies that source for real-host E2E tests. Stock Hermes plus this plugin is not equivalent mandatory protection. A version number alone does not prove the required core contract exists. The user's installed host and profile remain unverified.

## Try without changing your normal profile

Use the plugin-local E2E harness in `e2e/` with a pinned Hermes environment. It creates a temporary profile, uses synthetic inputs and a loopback fake provider, and does not use real credentials. Missing required test support fails the CI gate rather than silently converting the run to a pass.

For a separate disposable profile with the matching core already present, put this plugin directory under that profile's `plugins/`, and use this YAML alongside its existing model settings:

```yaml
plugins:
  enabled:
    - pii-mask-abelion
security:
  require_privacy_guard: true
  privacy_guard_plugin: pii-mask-abelion
```

Restart the test process and begin a new session. The profile must contain exactly one required privacy callback owned by that plugin name. Missing, failed, duplicate or unsupported policy denies the request. Provider credentials belong in the normal SDK authentication setup, never in model messages or plugin mapping.

## How the agent learns it is installed

The plugin uses Hermes's supported `register_system_prompt_section` API to add a short usage note to each new session's frozen prompt. It teaches exact placeholder handling and supported file destinations. README by itself is not automatic discovery. Older hosts without this registration API do not get the awareness note. Existing sessions retain their cached prompt; use a new session after loading the plugin. The note is guidance, not the enforcement mechanism.

## Behavior

- Mapping stays in local process memory, per session, with random tokens. Restart/expiry loses restoration. No map is saved to disk.
- Credentials never restore. CLI final may restore known exact PII/path tokens. API/gateway output does not restore them.
- Only known PATH tokens in `read_file`, `write_file`, `patch`, `search_files` path slots can restore for local execution. Shell/terminal, URLs, outbound messages and masked delegate goals are blocked rather than interpolated. This can limit coding workflows; it is not transparent shell support.
- Required mode checks main/aux model payloads, schemas, JSON tool arguments and tool-result replay. Main text/reasoning/interim replies are held until the final transform.
- Recognized authentication-session material (header/storage cookie values, standalone JSESSIONID/sessionid assignments, JWT-shaped data) is denied before model delivery. Generic process session_id values are not proof of credentials. Tool definitions are documentation, not live cookie containers; recognized values are still redacted. Normal documentation mentioning cookies is allowed. Coverage is structural/header detection, not full cookie detection. JSON {"sessionid":"abc"}, prose user_session=abc logged_in=yes, bare name=value and unknown unlabelled opaque values can pass detection.
- Images/audio/binary/unsupported objects are denied, not inspected by OCR. Unsupported provider transports deny in required mode. Current supported route is OpenAI SDK Chat Completions, not Responses/Codex, Anthropic/Bedrock/Gemini adapters or MoA.

## Limits and recovery

The required JSON payload ceiling is 2 MiB, with a 10-second bounded policy call. One string over 128 KiB or dense/expensive content can be withheld and cause denial. Mapping is capped at 4096 entries and 2 MB per session, 64 sessions, one-hour idle expiry. There is no silent eviction to make old tokens point somewhere else. For a true capacity refusal, start a fresh session or reduce the input locally. A media/unsupported/foreign-token refusal needs the relevant input changed, not merely retrying or switching providers.

## Disable / rollback

Stop the test process. In that disposable profile, set `security.require_privacy_guard: false`, remove `pii-mask-abelion` from `plugins.enabled`, and start a new process/session. This explicitly returns to native Hermes behavior, not equivalent protection. Do not remove the required plugin while leaving mandatory mode true; it will intentionally deny. No merge or deploy is needed to discard the local test worktree.

## Not covered

Not a firewall or prompt-injection solution. Direct tool/service traffic (curl, browser uploads, MCP, TTS/STT, media generation and provider-specific memory calls), persisted user prompts, all progress UI/logs and unknown secret encodings are not universally protected. Native Hermes still has its own redaction at several of these sinks; that is not the same as this reversible PII policy.

## Bundled Hermes skill

The plugin registers `pii-mask-abelion:privacy-mask-placeholders` through native `ctx.register_skill`, exposed in `skills_list`, `skill_view` and the `<available_skills>` index while enabled. Older hosts without that API skip it. See [usage](docs/USAGE.md) and [skill](skills/privacy-mask-placeholders/SKILL.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.

## Native route boundary

The matching core checks final native Anthropic Messages and Gemini payloads,
plus the identified Jev compaction-evaluation Decisions request. This repository
change is not a published release or installed-profile verification. Other direct
HTTP and service calls are not a process-wide privacy boundary. Unknown/unsupported
transports still deny at the guarded dispatch seam. No laptop/provider proof.

## Consolidated Privacy Guard

This revision combines the two earlier privacy plugins into one installable plugin.
The stable folder `pii_mask_abelion` and ID `pii-mask-abelion` are intentional: the
required core owner setting and imports used by its integration harness stay valid.
There is one held-output hook. It masks using the session map, applies native output
redaction, then restores only permitted local-CLI PII/path tokens. Credentials never
restore. Native redactor errors or unavailability withhold the output.

### Existing installations

No automatic migration is performed. Do not overwrite a running daily profile.
For a reviewed migration in a disposable profile, stop its Hermes process first;
keep the existing `pii-mask-abelion` install/owner ID, update that folder to the
reviewed consolidated commit, and disable/remove the separate `output-redact-abelion`
through Hermes' native plugin management. Restart and begin a new session, then
verify that only `pii-mask-abelion` owns the required policy and only one privacy
output hook is registered. Removing a callback while required mode is running
intentionally denies. Do not disable required mode to bypass an error.

A fresh install uses only `pii_mask_abelion`; the removed folder is not a second
install target. Existing old plugin copies do not disappear merely because a repo
folder was removed. Uninstalling them is a separate profile operation. Session maps
are memory-only and are lost across restart; never reuse old placeholders in a new
session. To roll back a disposable test, stop it and restore the previous pinned
plugin/config versions together, then restart with a fresh session. The laptop and
daily profile have not been migrated or activated.
