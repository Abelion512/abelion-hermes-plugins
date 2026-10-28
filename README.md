# Abelion Hermes plugins

Three focused packages for Hermes Agent. This is a local review candidate, not a merged or installed release.

| Human name | Stable ID | Folder | Purpose |
|---|---|---|---|
| Privacy Guard | `pii-mask-abelion` | `pii_mask_abelion` | Session masking and held native output redaction |
| Bot Screen | `screen` | `screen` | Dashboard virtual-desktop view and input takeover |
| 9Router Catalog (disabled) | `9router` | `model-providers/9router` | Disabled: not listed in hermes.json or installed by update-plugins.sh. Uses live-validated model IDs only; offline catalog is empty. |

Names clarify scope; runtime IDs and skill namespaces stay stable. 9Router Catalog does not implement the router. Bot Screen does not show the user's personal display or pause other tools during takeover. Loopback/mock data exists only in test fixtures and is never a production model inventory.

## Native first

Shield, tool-context and custom RSI are no longer active install targets in this candidate. Prefer Hermes native command approvals, loop/failure guards, file-write baseline checks, skill self-improvement and `/learn`. These are overlapping functions, not identical policy settings. No native configuration has been changed and the installed host version has not been verified. Current native guidance/tool queries handle context and exact time; automatic per-turn UTC injection is not retained.

Retired source and its earlier cross-plugin tests are preserved in [rollback](rollback/README.md). Existing lesson files and metrics are untouched. This source cleanup does not uninstall existing plugins from any profile.

## Privacy boundary

Privacy Guard requires held-output support. Mandatory request/tool/output protection needs the matching, unadopted core change. Stock Hermes plus this plugin is not equivalent mandatory protection. Unsupported or missing required policy denies; it is not a process-wide network firewall. See [Privacy Guard](pii_mask_abelion/README.md).

## Installation is separate

No daily-profile install is authorized or performed by this candidate. After host compatibility, reviewed revision and profile are confirmed, use native plugin management with the selected folder and pinned revision. Do not use `update-plugins.sh` to fetch an unmerged candidate. Existing retired plugins must be disabled/removed separately while stopped, following [migration](docs/MIGRATION.md), never silently through source deletion.

- [Bot Screen](screen/README.md)
- [9Router Catalog](model-providers/9router/README.md)
- [Compatibility and local evidence](docs/DELIVERY.md)
- [GitHub Pages preparation](docs/PAGES.md)

GitHub Pages documentation is prepared locally only. No site or public URL is published yet.
