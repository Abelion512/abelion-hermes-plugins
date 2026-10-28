# Delivery and compatibility

Three-package review candidate, published in existing PR #4. Main is not merged; no install, activation, Pages deployment or daily-profile change has been made. The closed privacy core remains unmerged and unadopted.

Privacy Guard needs held-output registration. Mandatory protection needs the matching required-privacy core, verified locally at 9a85916c87d56c2ca00b02fad8918f93ef1816e9. Version labels alone do not prove compatibility. Current-upstream native features were compared in documentation/source, not verified on the laptop.

The previous six-plugin candidate had 145 passed plus one expected boundary xfail; minimal standalone had 65 passed and six integration skips; its actual-core boundary run had 59 passed in one complete canonical run. Those counts are historical and must not be presented as a fresh three-package result.

Earlier three-package evidence (historical, before the classifier/auth/JSON fixes):
- Configured privacy suite: 72 passed, 1 expected boundary xfail (not a pass).
- Combined active suite without host test helpers resolving: 125 passed, 3 explicit integration skips. Do not add this count to the privacy count: they overlap. Minimal standalone: 70 passed, 6 explicit integration skips.
- Actual closed core 9a85916: one complete direct canonical per-file-runner execution, 59 passed, 0 failed in 104.8s, clean environment. The shell wrapper had previously exceeded the outer time limit, so only the completed direct run supports this claim.
- Disposable seven-to-three native removal/restart and pinned snapshot rollback passed, retaining mandatory privacy owner and one output hook.
- Uploaded 278-case matrix: 170 pass, 10 fail, 98 retired Shield targets not run. Original expectations preserved. See validation/README.md. Not all green.

Remaining limitations: E2E provider traffic is loopback-only, not a real external-provider run; Screen coverage is limited to dashboard lease/input flows and does not cover model-driven computer_use, phone/Tailscale, abrupt tab close or a user's own desktop. Daily-profile migration is not performed or verified. Offline 9Router curated models are not verified inventory. Scanner success is not proof every secret format is detectable.

Run retained tests with the matched host importable, or the minimal standalone environment. Retired tests remain in pinned Git history (see rollback/README.md) and are excluded from the active test suite; fewer tests do not mean regressions were fixed. See MIGRATION.md for stopped disposable-profile migration and pinned rollback order.

## Current CI contract and historical maintenance evidence

The current source of truth is the exact HEAD shown on [PR #4](https://github.com/Abelion512/abelion-hermes-plugins/pull/4), not a SHA copied into this document. Current E2E CI checks out Hermes core `9a85916c87d56c2ca00b02fad8918f93ef1816e9`, verifies that the imported code comes from that exact commit, and runs the real-provider-wire, 9Router lifecycle and Bot Screen tests. A missing or mismatched host is a hard failure rather than a skipped pass.

This evidence is specific to the pinned `Abelion512/hermes-4gent` commit. That commit remains unmerged/unadopted separately; a passing plugin CI run does not make mandatory privacy enforcement available on stock Hermes. Do not enable or describe mandatory protection on an unsupported host.

The measurements below are historical. Snapshot used for those measurements: `0fa17829691bcab8db7e7a6a29e88e6604860f46` (traceability only, **not the current head**):
- [PR #4](https://github.com/Abelion512/abelion-hermes-plugins/pull/4), not merged. Push and PR CI each passed all six jobs.
- Auth/JSON fix: 49 new unit regressions passed; privacy suite with official Hermes `7ee6d99c4f16df08cd6ca0b2c34abb81014db2ba`: 128 passed, one strict expected auxiliary-title failure. These counts overlap.
- CLI-to-loopback provider checks cover auth/JSON prompt and tool replay. This is real local transport evidence, not an external-provider or installed-laptop test.
- Historical scanner behavior and results are recorded here for traceability only. The current end-to-end job independently pins and verifies the Hermes host revision; a green result does not establish compatibility with stock Hermes or universal secret detection.

Maintenance review prepared on the same candidate (publication status is recorded by the PR revision):
- Complete active tests with official Hermes `7ee6d99`: 189 passed, one known strict auxiliary-title expected failure. Minimal environment: 127 passed, eight explicit host integration skips. These are overlapping runs, not additive counts.
- Classifier vocabulary indexing: 10,000 repeated field classifications, five trials, median 1.508 s before and 0.153 s after. Same workload and interpreter; 13,000 differential inputs preserved outputs. This is a classifier microbenchmark, not overall application speed.
- PR #2 disposable tests: 34 passed; PR #5 disposable tests: nine passed. Neither plugin was installed or reactivated.
- Native custom-provider discovery against a local synthetic OpenAI `/v1/models` server returned exact route/combo IDs and sent the configured Bearer header. This supports replacing the 9Router catalog adapter, not proof the installed picker/config or real gateway is migrated.
- noVNC RFB/display entry files and pako license match upstream v1.7.0. Restored missing noVNC license/authors notices locally; not every vendor file has been certified unchanged.

No installed-laptop evidence is available. The auxiliary-title upgrade can be disabled with native `auxiliary.title_generation.model_upgrade_enabled: false`, but that is a separate reviewed configuration choice, not a general privacy fix or a change made here.
