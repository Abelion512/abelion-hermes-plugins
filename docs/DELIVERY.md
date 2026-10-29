# Delivery and compatibility

## Current status

PR #4 is a source-review candidate, not a merged or installed release. No daily-profile installation, activation, Pages deployment, or laptop migration has been performed.

**Merge gate:** the required checks must pass on the exact current PR HEAD, including the pinned-core E2E job. A green unit suite alone is not sufficient. The current result is shown in [PR #4](https://github.com/Abelion512/abelion-hermes-plugins/pull/4) and its [Actions runs](https://github.com/Abelion512/abelion-hermes-plugins/actions).

## Package boundaries

| Package | Runtime ID | Current contract |
|---|---|---|
| Privacy Guard | `pii-mask-abelion` | Session-local request/tool masking and held-output redaction. Mandatory policy enforcement depends on the pinned forked core described below. |
| Bot Screen | `screen` | Dashboard-only view of the agent's virtual desktop, with a capability-gated input lease. It does not expose a user's personal display or pause other agent tools. |
| 9Router Catalog | `9router` | Disabled in this repository's install manifest. The service itself is not modified. The adapter advertises validated IDs from the live local catalog only. |

## Plugin vs. core ownership

Keep feature policy and UI in this repository; keep enforcement primitives and host-wide lifecycle guarantees in `Abelion512/hermes-4gent`. The two repositories must not grow duplicate implementations of the same security boundary.

| Concern | Owner | Keep in this repository | Core-owned contract / improvement |
|---|---|---|---|
| Privacy Guard | Plugin policy | Credential/PII/path classifiers, session-local token map, bounded restoration rules, policy configuration, skills and regression fixtures. | Provider/tool execution interception, session lifecycle guarantees, held-stream semantics, fail-closed required-policy gate, and the stable native redaction API. Core must enforce that every supported path crosses the policy; plugin regexes alone cannot establish that guarantee. |
| Bot Screen | Plugin feature | Screen tab/assets, noVNC presentation, allowlisted display RPCs, view/input lease UX, RFB splice and Screen-specific installer. | Generic dashboard-plugin discovery and API mount, authenticated HTTP/WebSocket handling, capability/consent checks, profile scoping, isolation/host routing, and the underlying virtual-desktop/lease authority. Do not reimplement generic auth or plugin mounting inside Screen. |
| 9Router Catalog | Optional adapter | Provider-specific `/v1/models` parsing, model-ID validation, catalog docs and selection skill. | Generic provider registration, credential storage, provider transport and lifecycle. This PR intentionally leaves 9Router out of the active install catalog. |
| Repository operations | Plugin repository | `hermes.json`, `update-plugins.sh`, plugin-specific CI, migration and rollback documentation. | No core change needed unless the native plugin install/update contract itself is defective. |

The Privacy Guard's import of Hermes' private `agent.redact._PREFIX_RE` is a coupling point, not a reason to move the classifier into core. Prefer a stable, documented core helper for shared native detection, introduced in a separate core PR; until then the pinned-core compatibility test must make this dependency explicit. Core-required enforcement changes must be reviewed and merged in the core repository separately, then pinned here by exact commit SHA.

## Security boundaries and repairs

### Privacy Guard

Mandatory request/tool/output behavior is tied to the exact Hermes fork commit `9a85916c87d56c2ca00b02fad8918f93ef1816e9`. The plugin CI checks out that source and verifies the imported source's full Git HEAD. This does **not** certify stock Hermes or imply that the separate core patch has been merged/adopted upstream. Do not advertise universal privacy coverage: detection is heuristic, and this is not a process-wide network firewall.

The loopback E2E suite records request bodies that actually reach its local test provider, including auxiliary requests. Canary values are synthetic; no real API provider or real credentials are used.

### Bot Screen

- The browser WebSocket uses Hermes's canonical `_ws_auth_ok` check. Missing, non-callable, or failing auth code denies the upgrade.
- `HERMES_SCREEN_UPSTREAM` is ignored unless explicit test mode is enabled, and test mode accepts loopback `ws://` addresses only.
- A one-time display ticket stays server-side and is consumed once. Message size is bounded at 16 MiB.
- Installer plugin IDs are validated before any backup/move/config mutation, and temporary name lists use `mktemp` rather than a predictable path under `/tmp`.
- Uninstall refuses to recursively delete a `plugins/screen` directory without a recognized `plugin.yaml`.

The dashboard/browser E2E uses a disposable virtual desktop. It does not cover model-driven `computer_use`, phone/Tailscale connectivity, abrupt tab closure, or a user's own desktop. Test stubs do not prove runtime behavior beyond the tested code paths.

### 9Router Catalog

The static curated inventory was removed because the IDs could not be verified as currently available. Discovery now enforces a 1 MiB response cap, validates IDs and removes duplicates. When `/v1/models` is unreachable or malformed, the advertised list is empty instead of falling back to guessed/stale names. The adapter remains disabled from this repository's install/update manifest.

## Test-data policy

- `e2e/support/loopback_provider.py` is a synthetic OpenAI-compatible provider used only to record local test traffic.
- `screen/tests/mock_upstream.py` is an in-process fixture for the pinned display/lease protocol. It is a test double, not a live Hermes gateway.
- Canary credentials, names, email addresses, phone numbers, NIK-like values, file paths, model IDs and session tokens are synthetic. They must not be copied into production configuration or treated as real inventory.
- No external model API is contacted by these tests, and the test harness strips inherited provider credentials from child processes.

Removing these test fixtures would reduce security coverage, so they remain in test-only paths and are named/documented as such. There is no mock or curated fallback model catalogue in production code.

## CI and verification contract

The `e2e` job checks out the exact fork commit above, verifies source identity, builds the matching Hermes dashboard assets, installs a compatible browser, and runs the host tests with skips converted to failures for mandatory prerequisites. The plugin CI also runs unit tests, syntax checks, secret scanning and dependency audits.

The exact final run status must be checked after the last commit. Historical run counts from earlier candidates are deliberately not copied here as if they were current evidence.

## Known limits

- No installed-laptop/runtime evidence is claimed.
- Loopback provider-wire tests are not tests against an external provider.
- Stock Hermes is not certified for required-policy enforcement without the matching core support.
- Native `plugins disable` does not unregister an already-installed 9Router provider; the lifecycle test covers native `plugins remove` as the verified removal path.
- Secret scanning and regex masking do not prove detection of every possible secret format.

## Deployment and migration

No deployment or user-profile change is part of this PR. Keep installation separate until current CI is green and the exact host/profile compatibility is reviewed. Do not run `update-plugins.sh` to fetch an unmerged candidate. Follow [migration guidance](MIGRATION.md) for stopped-profile changes and rollback.
