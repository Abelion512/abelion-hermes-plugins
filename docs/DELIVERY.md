# Delivery and compatibility

This branch is a reviewed candidate, not a merged release. Do not use the old
`update-plugins.sh` to obtain an unmerged branch: it pulls its current checkout.

## Install the chosen plugin

Use the existing Hermes launcher so its own environment and profile are selected.
Do not run a detached system Python or copy another environment into it.

```sh
hermes plugins install --ref perf-pii-redact-abelion --enable Abelion512/abelion-hermes-plugins/shield_abelion
```

Replace `shield_abelion` with the requested folder from the root table. This
private repository needs existing GitHub access on the machine. Installation
and enable change the selected profile; review its prompts and dependencies.
A seven-plugin install is not required to use one plugin. Do not overwrite a
working installation with rsync or enable required privacy without its core.

## Required privacy is a separate host capability

The pii-mask candidate requires held-output hooks. Mandatory request/tool/output
checks additionally need the matching core PR in Abelion512/hermes-4gent, based
on `9b904dcc22c23fe8b82834339bbdd96495072e59`. A stock host or a version number
alone is not evidence that this contract exists. Missing held-output capability
refuses plugin registration. Required mode without a working policy denies.
Use the core developer guide and pii-mask README for disposable-profile setup;
there is no verified daily-install migration yet. Keep daily config unchanged
until host/source compatibility is established.

## Evidence and limits

The repository behavior tests exercise wrong type/value branches and their
absence of effects. Run with the selected Hermes environment importable:

```sh
python -m pytest -q tests/test_ordered_validation.py
# Privacy integration also imports the matching Hermes test helpers:
PYTHONPATH=/path/to/reviewed/hermes:$PWD python -m pytest --import-mode=importlib -q pii_mask_abelion/tests
```

The tested fork passed 48 behavior cases, 63 privacy cases with 1 expected
boundary xfail, native discovery/read/index for seven skills and controlled
synthetic CLI probes. These results are development evidence, not an actual
provider, full Screen feature suite, all Hermes releases or installed laptop
proof. The unknown installed laptop source/runtime remains unresolved; no
additional diagnostic-relay loop or portable user test is requested here.

Rollback through the native plugin disable/remove flow. For required privacy,
stop the process and follow the core rollback order before removing its policy.
No merge, gateway restart, deployment or daily-profile change is done by this PR.
