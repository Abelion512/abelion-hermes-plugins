# Test standard for a plugin

A plugin is not complete without a test surface. The tests should make the plugin
regressions visible, not just satisfy a checklist.

## Required test surfaces

- Unit tests for the plugin's own code.
- Integration-style tests for the plugin's runtime contracts, where relevant.
- E2E tests for host-dependent behavior, where relevant.

## Good test habits

- Tests should be deterministic where possible.
- Tests should use synthetic or local-only data.
- Tests should not depend on real credentials or external accounts unless the
  plugin is explicitly about that, and even then only in clearly separated test
  code.
- Tests should assert the important behavior, not just that something runs.

## Known skips and flaky tests

If a test is hardware-bound, environment-bound, or intentionally skipped, record
that in the plugin's docs and in the test code where appropriate. A skipped test
must not quietly hide a real bug.

## Coverage rule

If a behavior matters enough to claim in docs, it should have a test that fails
when it is broken. If it cannot be tested reasonably, say so in the docs and
do not imply it is proven.

## Repetition

If the plugin has recurring tasks like adding a skill, updating docs, or adding
an E2E case, those tasks should have templates or scripts that make them
repeatable without hand-editing blind.
