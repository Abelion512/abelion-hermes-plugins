# Abelion Hermes Plugins

A monorepo for standalone Hermes Agent plugins. Each plugin owns its implementation, documentation, unit tests, skills, and feature-specific end-to-end tests. Shared CI and the pinned-core E2E harness live under `.github/`.

## Active plugins

| Plugin | Runtime ID | Source | Responsibility |
|---|---|---|---|
| Privacy Guard | `pii-mask-abelion` | [`plugins/pii_mask_abelion/`](plugins/pii_mask_abelion/) | Session-local PII/credential masking, permitted placeholder restoration, and held output redaction. |
| Bot Screen | `screen` | [`plugins/screen/`](plugins/screen/) | Dashboard for the agent's virtual desktop and a capability-gated human input lease. |

Each plugin folder contains its own `README.md`, `docs/`, `tests/`, `e2e/`, and `skills/` as applicable. The repository root retains only shared metadata and entry points such as `hermes.json`, `update-plugins.sh`, this README, and GitHub configuration.

## Plugin vs. core

Feature policy and UI stay in the plugin repository. Host-wide enforcement, authorization, lifecycle, and execution guarantees belong in the Hermes core fork. Do not duplicate the same security boundary in both places.

- **Privacy Guard plugin:** credential/PII/path classification, session-local token mapping, bounded restoration, policy configuration, skills, and regression tests.
- **Hermes core:** provider/tool interception, mandatory fail-closed policy gates, session lifecycle, held-stream semantics, and stable native redaction contracts.
- **Bot Screen plugin:** Screen tab, noVNC presentation, display RPC allowlist, and takeover/hand-back UX.
- **Hermes core:** plugin discovery/API mounting, dashboard HTTP/WebSocket authorization, capability and consent checks, profile isolation, and virtual-desktop/lease authority.

Bot Screen's lease governs virtual-desktop input only. **It is not general human-in-the-loop (HITL): it does not pause all agent tools or require human approval for arbitrary actions.** General HITL must be designed as a separate core-owned execution/approval gate, with any UI kept in a plugin.

The standalone `decolua/9router` project owns its router implementation. This repository does not vendor or maintain a duplicate adapter.

## Security and compatibility

Mandatory Privacy Guard behavior requires the exact Hermes fork commit `9a85916c87d56c2ca00b02fad8918f93ef1816e9` from [`Abelion512/hermes-4gent`](https://github.com/Abelion512/hermes-4gent). CI checks out that commit for real-host tests. This does not certify stock Hermes, prove upstream adoption, or provide a process-wide network firewall. Detection remains heuristic, and unsupported transports are not universally covered.

Bot Screen is for the agent's virtual desktop, not the user's personal display. Browser/display E2E tests do not certify model-driven computer use, phone/Tailscale access, abrupt-disconnect behavior, or an installed laptop.

## Validation

CI runs each plugin's own tests and dependency checks, plus a real-host E2E suite with a synthetic loopback provider, disposable profiles, and the exact core commit above. No real provider or production credentials are used. A green CI run is evidence for its tested commit and paths only.

### Privacy regression strategy

Keep both test layers. Unit tests exercise classifiers, boundaries, capacity, session isolation, and adversarial mutations quickly; E2E tests exercise the pinned Hermes host and inspect recorded provider requests plus delivered output. E2E does not replace unit coverage, and a green unit run alone is not proof of a secure provider boundary.

The privacy suite includes a deterministic 256-case field-name mutation matrix and fail-closed checks for invisible Unicode in sensitive assignments. CI prints test counts in the run summary and continues to run the full real-host suite against a synthetic loopback provider.

The “2.8T” target is not treated as a count of test cases or as a privacy guarantee. CI does **not** call a live 2.8-trillion-parameter model or send real PII/secrets to a remote endpoint. The current evidence is model-agnostic boundary testing: sensitive canaries must not appear in requests observed at the provider or in final user-visible output. Any live-model compatibility claim requires a separate explicitly configured evaluation and recorded evidence.

## Installation and migration

`update-plugins.sh` syncs the active plugin folders into `~/.hermes/plugins/`; it does not migrate an installed profile, change its privacy settings, or remove old installed plugins. Review the target profile, stop the running Hermes process, back up its config and plugin versions, then use native plugin management for removals. Never delete plugin directories from a live profile, and never disable required Privacy Guard merely to hide a migration failure.

Retired source can be recovered from Git history as documented in [`.github/retired-source-recovery.md`](.github/retired-source-recovery.md). An old installed copy is separate state and is not deleted merely because its source was removed from this repository.
