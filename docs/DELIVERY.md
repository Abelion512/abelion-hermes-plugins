# Delivery and compatibility

Local three-package candidate. No commit, push, merge, install, activation, Pages deployment or daily-profile change has been made. The closed privacy core remains unmerged and unadopted.

Privacy Guard needs held-output registration. Mandatory protection needs the matching required-privacy core, verified locally at 9a85916c87d56c2ca00b02fad8918f93ef1816e9. Version labels alone do not prove compatibility. Current-upstream native features were compared in documentation/source, not verified on the laptop.

The previous six-plugin candidate had 145 passed plus one expected boundary xfail; minimal standalone had 65 passed and six integration skips; its actual-core boundary run had 59 passed in one complete canonical run. Those counts are historical and must not be presented as a fresh three-package result.

Fresh three-package evidence:
- Configured privacy suite: 72 passed, 1 expected boundary xfail (not a pass).
- Combined active suite without host test helpers resolving: 125 passed, 3 explicit integration skips. Do not add this count to the privacy count: they overlap. Minimal standalone: 70 passed, 6 explicit integration skips.
- Actual closed core 9a85916: one complete direct canonical per-file-runner execution, 59 passed, 0 failed in 104.8s, clean environment. The shell wrapper had previously exceeded the outer time limit, so only the completed direct run supports this claim.
- Disposable seven-to-three native removal/restart and pinned snapshot rollback passed, retaining mandatory privacy owner and one output hook.
- Uploaded 278-case matrix: 170 pass, 10 fail, 98 retired Shield targets not run. Original expectations preserved. See validation/README.md. Not all green.

 Remaining limitations: synthetic local requests, no actual provider proof, no complete Screen interaction suite and no daily-profile migration. Offline 9Router curated models are not verified inventory. Scanner success is not proof every secret format is detectable.

Run retained tests with the matched host importable, or the minimal standalone environment. Retired tests remain in the rollback archive and are excluded from the active test suite; fewer tests do not mean regressions were fixed. See MIGRATION.md for stopped disposable-profile migration and pinned rollback order.
