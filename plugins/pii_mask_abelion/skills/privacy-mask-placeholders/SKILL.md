---
name: privacy-mask-placeholders
description: Work with masked PII, credential and path placeholders.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [privacy, masking, placeholders, redact]
---

# Privacy Mask Placeholders Skill

The pii-mask-abelion plugin (required-mode candidate) masks PII, credentials
and local paths before requests leave for the provider, using per-session
random tokens, and restores known tokens locally where supported. This skill
is how to work inside that mapping. The plugin also adds its own short
system-prompt note via register_system_prompt_section; keep both consistent.

## When to Use

- A tool result or message contains mask tokens from this plugin, or a
  request was denied by the privacy policy.
- Don't use for: unmasked profiles — none of this applies when the plugin is
  disabled.

## How to Apply

1. Treat tokens as opaque stand-ins; never invent the original value.
2. Credentials never restore — do not build flows that need the real secret
   back from the model side.
3. Only PATH tokens in read_file / write_file / patch / search_files path
   slots restore for local execution. Shell/terminal, URLs, outbound
   messages and delegate goals are blocked rather than interpolated — plan
   coding work around that.
4. On a policy denial, change the input (remove media/unsupported objects or
   session material), not just retry.

## Pitfalls

- Mapping lives in process memory per session; restart or expiry loses
  restoration. No map on disk.
- Cookie/session detection is structural: JSON {"sessionid":"abc"}, prose
  user_session=abc, and bare name=value pairs can pass unflagged.
- CLI final may restore known exact tokens; API/gateway output does not.

## Verification

Masked values stay tokens on the provider side, and supported path slots
restore to the real local paths on execution.

## Wrong requirement or value

Invalid capacity/TTL values raise before state exists. Wrong request, model or tool argument types are denied; values are not coerced. Partial middleware requests remain supported. Existing exact session/path/secret rules are unchanged.
Do not claim a rejected operation succeeded or silently replace the requested value.
