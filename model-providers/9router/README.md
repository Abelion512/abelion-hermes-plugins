# 9router

Registers the local [9Router](http://localhost:20128) gateway as a Hermes
model provider. Its models appear in the `/model` picker under the 9Router
provider - from validated gateway `/v1/models` IDs, including configured combos. No wildcard
model IDs are invented. An unavailable catalog uses an explicitly unverified
curated fallback, not a claim of current availability.

## Requirements

- 9Router running on `http://localhost:20128`.
- `NINEROUTER_API_KEY` in the environment (asked at install; calls fail at
  request time without it).

## Install

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/model-providers/9router
```

## Verify

```bash
hermes plugins list            # 9router shows enabled
hermes plugins doctor model-providers/9router
```

`/model` lists 9Router entries. `skills_list` shows `9router:model-picker`.

## Limits

- The provider target is hardcoded to `http://localhost:20128/v1` - the
  `base_url` in `plugin.yaml` metadata is informational only.
- Discovery is cached for 60 seconds. The host provider picker may keep its own
  registered fallback snapshot until refreshed/restarted.
- When the gateway is unreachable at load time, the picker falls back to the
  built-in curated list, which can be stale: a listed model may not exist and
  a new route may be missing. Check the live `/v1/models` when it matters.

## Disable / rollback

```bash
hermes plugins disable 9router
hermes plugins remove 9router
```

## Bundled agent skill

`model-picker` - how the agent should pick and troubleshoot 9Router models.
Registered automatically while enabled on hosts with `ctx.register_skill`
(API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); older hosts load the provider without the skill.
See [docs/USAGE.md](docs/USAGE.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
