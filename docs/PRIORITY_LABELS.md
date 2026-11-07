# Priority labels

Repo labeler does two different jobs, and priority is not one of them.

1. **Path ownership** — which part of the repo a change touches. That can be
   inferred from changed files, and repo-wide + plugin-local `labels.yml` files
   handle that.
2. **Intent / seriousness** — how important or urgent a change is. That is a
   human judgment, not a filename pattern. Priority labels should not be
   auto-applied from globs.

So: do not use P0/P1/P2/P3 as automatic path labels. A plugin folder can change
because of a doc typo, a failing test, a feature, or a security fix, and the
same path cannot reliably mean the same priority.

## Preferred places for priority

- **Triage.** Humans or a triage job apply priority labels after looking at the
  actual change.
- **CI gating.** If priority should affect merge rules, that should be an explicit
  policy check, not label inference.
- **Purpose-built manual labels.** A small shared set of priority labels can exist
  as a triage aid, but only if they are applied deliberately.

## What this repo does

- Repo-wide `labeler.yml` deliberately does **not** define priority labels.
- Plugin-local `labels.yml` files are for path-owned labels only. They should not
  define priority labels either, unless there is a very specific plugin-level
  reason, and even then it should be intentional, not glob-based.
- If priority matters for a change, label it by triage, not by where the files
  live.

## Rule

If a label answers “where did this change happen?”, path rules are fine. If a
label answers “how important is this?”, keep it manual and explicit.
