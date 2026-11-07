# E2E standard for a plugin

Every plugin that depends on host behavior should have an E2E surface. The point
is to prove what the real host actually does with the plugin, using a repeatable
setup that does not depend on a live provider or real credentials.

## What E2E should cover

- The normal happy path for the plugin's main behavior.
- The failure/denial paths that matter, if the host behavior is relevant.
- Edge cases that are important enough to assert in a real run.
- Enough to reproduce a bug without using private inputs.

## What E2E must not depend on

- Real provider credentials.
- Real user data.
- Manual interactive steps that cannot be scripted.
- A specific laptop, display, or network path unless that is the actual test
  subject.

## Synthetic controls

Use synthetic inputs and synthetic canaries for any credential-like or PII-like
value. Keep those fixtures inside the repo's test surface or clearly marked
sample data. Do not store real secrets as fixtures.

## When E2E is optional

A plugin that is purely local and does not depend on host dispatch behavior may
have a lighter E2E story. If there is no host-dependent surface, say so plainly
and keep the claim limited.

## Repo expectation

If a plugin has host-dependent behavior, the repo should be able to run its E2E
in a defined environment and know when that run cannot happen. An E2E surface
that silently passes when it could not run is worse than an honest skipped state.
