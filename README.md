# abelion-hermes-plugins

Abelion security, context, and provider plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Plugins

| ID | Directory | Hooks | Purpose | Docs | Agent skill |
|---|---|---|---|---|---|
| `shield-abelion` | `shield_abelion/` | pre_tool_call, post_tool_call, on_session_end | Read-before-edit, safety guard, loop detector, circuit breaker | [README](shield_abelion/README.md) · [usage](shield_abelion/docs/USAGE.md) | `shield-abelion:blocked-tool-recovery` |
| `pii-mask-abelion` | `pii_mask_abelion/` | required privacy + request/tool hooks + held output | Session-local PII/secret/path masking with required host patch | [README](pii_mask_abelion/README.md) · [usage](pii_mask_abelion/docs/USAGE.md) | `pii-mask-abelion:privacy-mask-placeholders` |
| `output-redact-abelion` | `output_redact_abelion/` | transform_llm_output | Redact credentials from AI response | [README](output_redact_abelion/README.md) · [usage](output_redact_abelion/docs/USAGE.md) | `output-redact-abelion:redacted-output-handling` |
| `tool-context-abelion` | `tool_context_abelion/` | pre_llm_call | Inject UTC datetime and session-tool context | [README](tool_context_abelion/README.md) · [usage](tool_context_abelion/docs/USAGE.md) | `tool-context-abelion:turn-context` |
| `rsi-learn-abelion` | `rsi_learn_abelion/` | pre_llm_call, post_tool_call | RSI lesson extraction and decision layer | [README](rsi_learn_abelion/README.md) · [usage](rsi_learn_abelion/docs/USAGE.md) | `rsi-learn-abelion:experience-lessons` |
| `screen` | `screen/` | dashboard plugin | Live Bot Screen view + Take over / Hand back (noVNC) | [README](screen/README.md) · [usage](screen/docs/USAGE.md) | `screen:bot-screen-control` |
| `9router` | `model-providers/9router/` | provider profile | 9Router model provider with validated model discovery | [README](model-providers/9router/README.md) · [usage](model-providers/9router/docs/USAGE.md) | `9router:model-picker` |

> **Status: reviewed PR candidate, not merged or installed.** Seven-plugin input
> validation, documentation and native skills are included. Required outbound
> privacy needs the matching core change in `Abelion512/hermes-4gent`, based on
> `9b904dcc22c23fe8b82834339bbdd96495072e59`. Without that change, optional
> middleware is not mandatory protection. Output redactor errors withhold final
> text, but do not make this a network firewall. Installed laptop compatibility
> has not been verified. See [delivery and compatibility](docs/DELIVERY.md).

## Install

This is a multi-plugin repo - install the folder you want, not the whole repo:

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/<folder>
```

Example: `hermes plugins install --enable Abelion512/abelion-hermes-plugins/shield_abelion`.
Pin a commit with `--ref <sha>`; skip auto-enable with `--no-enable`.
Or via Dashboard → :9119/plugins → Add from GitHub (private repo: needs the
GitHub access already on the machine).

## Docs and agent skills

Every plugin carries three layers, per [docs/plugin-docs-standard.md](docs/plugin-docs-standard.md):

- `README.md` - human quickstart: install, verify, limits, rollback.
- `docs/USAGE.md` - mechanism reference: exact hooks, behavior, config, state files.
- `skills/<name>/SKILL.md` - agent-facing skill, published through
  `ctx.register_skill` while the plugin is enabled. It shows up in the
  session's skill index as `<plugin>:<skill>` and loads with
  `skill_view("<plugin>:<skill>")` - this is how the agent learns the plugin
  exists and how to work with it. Hosts without `ctx.register_skill` skip the skills. Other plugin requirements still apply.

Validate any plugin folder locally with `hermes plugins doctor <folder>`.

## Requirements

- A host supporting `ctx.register_skill` for bundled skills. Discovery here was verified on fork base `9b904dcc22c2` plus the local privacy patch; this is not proof for every released version. The two redact candidates also require held-output support, and required mode needs the matching local core patch.
- `NINEROUTER_API_KEY` env var (for 9Router provider)
- `aiohttp` (for the screen dashboard plugin; offered at install)

## Native route candidate

The matching core now checks final native Anthropic Messages and Gemini payloads,
plus the identified Jev compaction-evaluation Decisions request. This is local
review-pending code, not a published/installed release. Other direct HTTP and
service calls are not a process-wide privacy boundary. Unknown/unsupported
transports still deny at the guarded dispatch seam. No laptop/provider proof.
