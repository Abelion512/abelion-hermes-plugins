# Abelion Hermes Plugins

A monorepo for standalone Hermes Agent plugins. Each plugin owns its implementation, documentation, unit tests, skills, and feature-specific end-to-end tests. Shared CI and the pinned-core E2E harness live under `.github/`.

## Active plugins

| Plugin | Runtime ID | Source | Responsibility |
|---|---|---|---|
| Privacy Guard | `nebula` | [`plugins/nebula/`](plugins/nebula/) | Session-local PII/credential masking, permitted placeholder restoration, and held output redaction. |

Each plugin folder contains its own `README.md`, `docs/`, `tests/`, `e2e/`, and `skills/` as applicable. The repository root retains only shared metadata and entry points such as `hermes.json`, `update-plugins.sh`, this README, and GitHub configuration.

## Plugin vs. core

Feature policy and UI stay in the plugin repository. Host-wide enforcement, authorization, lifecycle, and execution guarantees belong in the Hermes core fork. Do not duplicate the same security boundary in both places.

- **Privacy Guard plugin:** credential/PII/path classification, session-local token mapping, bounded restoration, policy configuration, skills, and regression tests.
- **Hermes core:** provider/tool interception, mandatory fail-closed policy gates, session lifecycle, held-stream semantics, and stable native redaction contracts.

The standalone `decolua/9router` project owns its router implementation. This repository does not vendor or maintain a duplicate adapter.

## Security and compatibility

Mandatory Privacy Guard behavior requires the exact Hermes fork commit `9a85916c87d56c2ca00b02fad8918f93ef1816e9` from [`Abelion512/hermes-4gent`](https://github.com/Abelion512/hermes-4gent). CI checks out that commit for real-host tests. This does not certify stock Hermes, prove upstream adoption, or provide a process-wide network firewall. Detection remains heuristic, and unsupported transports are not universally covered.

## Validation

CI runs each plugin's own tests and dependency checks, plus a real-host E2E suite with a synthetic loopback provider, disposable profiles, and the exact core commit above. No real provider or production credentials are used. A green CI run is evidence for its tested commit and paths only.

### Privacy regression strategy

Keep both test layers. Unit tests exercise classifiers, boundaries, capacity, session isolation, and adversarial mutations quickly; E2E tests exercise the pinned Hermes host and inspect recorded provider requests plus delivered output. E2E does not replace unit coverage, and a green unit run alone is not proof of a secure provider boundary.

The privacy suite includes a deterministic 256-case field-name mutation matrix and fail-closed checks for invisible Unicode in sensitive assignments. CI prints test counts in the run summary and continues to run the full real-host suite against a synthetic loopback provider.

The “2.8T” target is not treated as a count of test cases or as a privacy guarantee. CI does **not** call a live 2.8-trillion-parameter model or send real PII/secrets to a remote endpoint. The current evidence is model-agnostic boundary testing: sensitive canaries must not appear in requests observed at the provider or in final user-visible output. Any live-model compatibility claim requires a separate explicitly configured evaluation and recorded evidence.

## Installation and migration

`update-plugins.sh` syncs the active plugin folders into `~/.hermes/plugins/`. It now stops before pulling or syncing if it detects the retired `pii_mask_abelion`, `screen`, or `output-redact-abelion` directories. It does not guess the active profile, edit Hermes configuration, or delete plugin state. Complete the backed-up native migration and quarantine procedure in [`docs/PLUGIN_MIGRATION.md`](docs/PLUGIN_MIGRATION.md) first. Never delete plugin directories from a live profile, and never disable required Privacy Guard merely to hide a migration failure.

Retired source can be recovered from Git history as documented in [`.github/retired-source-recovery.md`](.github/retired-source-recovery.md). An old installed copy is separate state and is not deleted merely because its source was removed from this repository.
