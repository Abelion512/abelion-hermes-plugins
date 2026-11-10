# Plugin docs — repeating update template

Use this when updating a plugin's docs, whether for a new feature, a bug fix, a limit change, or a cleanup.

## The three layers to keep in sync

1. `<plugin>/README.md`
2. `<plugin>/docs/USAGE.md`
3. `<plugin>/docs/VALIDATION.md`

Optional plugin-scoped file:

4. `<plugin>/docs/IDEAS.md`

Do not let one layer drift from the others. If a behavior changes, all three that are affected change in the same commit.

## README update checklist

- [ ] What the plugin does is still accurate
- [ ] Required host/version is stated only when it truly matters
- [ ] Install, verify, disable/rollback steps still match the current code
- [ ] Limits are honest, including what is *not* covered
- [ ] Bundled skill pointer is correct

## USAGE update checklist

- [ ] Every registered hook/middleware/skill is listed with its source file
- [ ] Behavior details, state files, config (or "None") are current
- [ ] Known limits and the status table match the code and tests
- [ ] Any "UNRUN" or "Not covered" item is still accurate, not silently upgraded to "proven"

## VALIDATION update checklist

- [ ] The ordered validation still matches the current code paths
- [ ] Unit vs real-host E2E split is clear
- [ ] What each layer proves and what it does not is still accurate
- [ ] Historical/corpus files are labelled as historical, not as current passes

## IDEAS update checklist

- [ ] New ideas land as their own block before implementation
- [ ] Implemented ideas move to USAGE and the status table
- [ ] Abandoned ideas are marked abandoned, not deleted silently

## Do not

- Do not write docs that imply coverage the tests do not support.
- Do not replace a real limit with a softer sentence to make the plugin sound broader.
- Do not let an IDEAS idea become "supported" without a test and a doc update.
