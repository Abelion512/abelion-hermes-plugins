# abelion-hermes-plugins

Abelion security, context, and provider plugins for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Plugins

| ID | Directory | Hooks | Purpose |
|---|---|---|---|
| `shield-abelion` | `shield_abelion/` | pre_tool_call, post_tool_call, on_session_end | Read-before-edit, safety guard, loop detector, circuit breaker |
| `pii-mask-abelion` | `pii_mask_abelion/` | llm_request middleware | Mask PII/secrets before sending to provider |
| `output-redact-abelion` | `output_redact_abelion/` | transform_llm_output | Redact credentials from AI response |
| `tool-context-abelion` | `tool_context_abelion/` | pre_llm_call | Inject datetime + tool reminder + execution mandate |
| `rsi-learn-abelion` | `rsi_learn_abelion/` | pre_llm_call, post_tool_call | RSI lesson extraction and decision layer |
| `screenview-abelion` | `screenview_abelion/` | dashboard plugin | Live Bot Screen view + Take over / Hand back (noVNC) |
| `9router` | `model-providers/9router/` | provider profile | 9Router multi-model gateway (110+ models) |

## Install

```bash
hermes plugin install https://github.com/Abelion512/abelion-hermes-plugins
```

Or via Dashboard → :9119/plugins → Add from GitHub.

## Requirements

- Hermes Agent ≥ 0.1.0
- `NINEROUTER_API_KEY` env var (for 9Router provider)
