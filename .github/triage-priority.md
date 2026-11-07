# Triage and priority labels

Plugin ownership labels are driven by each active plugin's
`plugins/<id>/.github/labels.yml`. The repo-level labeler handles shared
paths such as CI, dependencies, documentation, and task templates.

## Ownership labels

- `nebula`: the active Privacy Guard plugin under `plugins/nebula/`.
- `plugins`: generic ownership for newly added plugin folders before a
  plugin-specific label is defined.
- `repo-tools`: shared workflow material under `.github/task-templates/`,
  `.github/labeler.yml`, `.github/dependabot.yml`, and `.plugins/`.

Retired plugin IDs (`pii_mask_abelion`, `screen`, and
`output-redact-abelion`) are migration identifiers, not active ownership
labels. Do not add new files or task routing rules under those paths.

## Priority labels

- `P0`: active breakage of the required privacy contract, a critical CI gate,
  or confirmed credential exposure.
- `P1`: high-impact behavior regression or a serious test/coverage gap.
- `P2`: normal plugin feature, documentation, skill, or test work.
- `P3`: low-urgency cleanup, polish, or future ideas.

Priority reflects impact, not folder name. A green CI run is evidence only for
the exact checks and commit tested. Do not describe skipped or untested behavior
as proven.

## Triage sequence

1. Identify the active plugin and the affected contract.
2. Separate runtime code, docs, skills, tests, and shared infrastructure.
3. Assign priority from impact, not from the path label.
4. Update the plugin's usage/validation documentation when the actual contract
   or proof status changes.
