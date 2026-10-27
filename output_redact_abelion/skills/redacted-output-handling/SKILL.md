---
name: redacted-output-handling
description: Handle responses passed through output credential redaction.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [output, redact, credentials]
---

# Redacted Output Handling Skill

The output-redact-abelion plugin redacts credential-shaped material from the
AI final response through transform_llm_output with hold_stream requested.
When the mapping guard is loaded, this plugin yields to that guard. The
mandatory core output policy is owned by pii-mask-abelion, not this plugin. This skill is how to treat redacted replies and denials.

## When to Use

- A reply contains redaction placeholders where a secret-like value was, or
  the response was withheld by the output policy.
- Don't use for: recovering the original secret. Redaction is one-way by
  design; never try to reconstruct it.

## How to Apply

1. When a value you needed was redacted, ask the user to handle that step
   locally, or use a tool slot that receives the value without printing it.
2. Keep redacted tokens verbatim when referencing them; do not paraphrase
   into something that looks like a real credential.

## Pitfalls

- Coverage is pattern-based: unknown secret encodings can pass, and ordinary
  text that matches a credential shape can be redacted.
- The redactor is not a firewall; direct tool/service traffic is outside its
  boundary.

## Verification

Use synthetic credential-shaped canaries to check the final output for the
specific pattern being tested. Preserve placeholders exactly. A clean canary
test is not proof that every live credential format is detected.

## Wrong requirement or value

Non-text output is withheld. A missing or failed native redactor withholds output rather than returning an unverified success. An active privacy Guard still owns final session mapping.
Do not claim a rejected operation succeeded or silently replace the requested value.
