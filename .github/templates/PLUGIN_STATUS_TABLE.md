# Status table template

Use this when a plugin needs a visible short summary of what is desired,
implemented, and proven.

| Desired behavior | Implemented | Proven by E2E |
|---|---|---|
| behavior 1 | yes / no | yes / no / not covered |
| behavior 2 | yes / no | yes / no / not covered |

Rules:

- Be honest about "Proven by E2E" — a failing or missing E2E is not the same as
  proven.
- If a behavior is only partially implemented, say so in the note column or in
  the plugin docs.
- Update this table when the code, tests, or E2E change.
- If something is not yet proven, do not imply otherwise in README or skills.
