---
name: model-picker
description: Pick and use 9Router provider models in Hermes.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [9router, provider, models, gateway]
---

# 9Router Model Picker Skill

The 9router plugin registers the local 9Router gateway (http://localhost:20128)
as a Hermes provider, so its models show up in the `/model` picker under the
9Router provider without manual config edits.

## When to Use

- The user asks which models are available, or asks you to switch models.
- A model call fails and you need to tell a gateway problem from a model problem.
- Don't use for: providers other than 9Router - this skill covers only the
  9router plugin's model list.

## How to Apply

1. Pick models through the normal `/model` picker; 9Router entries need no
   extra setup once the plugin is enabled and `NINEROUTER_API_KEY` is set.
2. Use exact live IDs from `/v1/models`, including combos. Do not invent a
   wildcard route or assume a curated entry is available.
3. On a failure, distinguish auth, connection and model errors. A 401 is not
   proof the service is down. Never print the configured API key to diagnose it.
4. When the gateway is unreachable the plugin falls back to a built-in curated
   list. That list can be stale - a listed model may not exist, and a new
   route may be missing. Verify against the live endpoint when it matters.

## Pitfalls

- Discovery has a 60-second cache; the host can separately retain its
  registered provider snapshot until refreshed/restarted.
- `NINEROUTER_API_KEY` missing does not block loading; calls fail at request
  time instead. Check the env var before debugging anything else.

## Verification

`/model` shows 9Router entries, and a call to a picked model returns a
completion rather than a connection or auth error.

## Wrong requirement or value

Model discovery bounds response size, requires an object/list payload and nonempty string IDs with the supported identifier alphabet. Invalid IDs are excluded, duplicates removed; malformed/unavailable responses retain the existing curated fallback, not proof of live availability.
Do not claim a rejected operation succeeded or silently replace the requested value.

## Catalog freshness

Only validated live model/combination IDs are advertised on successful discovery.
No oc/* or mmf/* wildcard is a verified model. Discovery uses configured Bearer
auth and a 60-second cache. The host may cache its own registration snapshot.
An unavailable catalog's curated fallback is unverified, not proof of a free or
working route. Native /v1/messages and Chat Completions are distinct protocols.
