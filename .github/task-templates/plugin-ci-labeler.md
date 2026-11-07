# CI and labeler — repeating update template

Use this when a plugin is added or removed, or when the repo's label/priority taxonomy changes.

## Plugin add/remove checklist

- [ ] `hermes.json` → plugins[]
- [ ] `update-plugins.sh` → sync list
- [ ] Root `README.md` → active plugin table
- [ ] `.github/labeler.yml` → plugin label(s)
- [ ] `.github/workflows/ci.yml` → only if detection/labeler/behavior changes
- [ ] `.github/task-templates/` → mention the new shape only if it changes the repeating task

## Labeler discipline

Labels should help triage, not just mirror folders. For every label rule, ask:

- Does this label help someone prioritize?
- Does it still make sense when the plugin is renamed, split, or removed?
- Is the rule broad enough to survive new files in the plugin, but narrow enough to avoid spamming unrelated work?

If the repo adopts a priority scheme, make the priority label rule separate from the plugin rule, and keep the mapping explicit in this doc.

## CI discipline

- Detection must keep working as plugins are added.
- Per-plugin test jobs must not depend on one plugin's special setup unless that setup is real and durable.
- Real-host E2E must keep failing loudly when prerequisites or the pinned core are wrong.
- Secret scanning must keep scanning the whole tree; do not weaken it per plugin.

## Do not

- Do not add a plugin without updating the labeler if the labeler is supposed to cover plugins.
- Do not add priority labels that no rule, policy, or docs explain.
- Do not let the labeler become a folder mirror with no triage value.
