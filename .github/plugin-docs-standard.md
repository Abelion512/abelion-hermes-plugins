# Plugin docs standard

Every plugin in this repo ships three layers. The goal: a human can install
it in minutes, and an agent (Hermes or another one reading the repo) can
discover and use it correctly without guessing.

## The trio

```
<plugin>/
├── README.md            # human quickstart
├── docs/USAGE.md        # mechanism reference
└── skills/<name>/SKILL.md   # agent-facing skill (one or more)
```

- **README.md** - what it does, requirements, exact install/verify/disable
  commands, honest limits. Style follows the official plugins
  (e.g. NousResearch/hermes-official-plugins/advanced-delegation): state the
  minimum Hermes version only when a feature truly needs it, and name
  unsupported routes instead of implying coverage.
- **docs/USAGE.md** - the contract for maintainers and reviewing agents:
  every registered hook/middleware/skill with its source file, behavior
  details, state files, config (or "None"), and known limits.
- **skills/\*/SKILL.md** - loaded by the agent when relevant. Follow the
  upstream authoring rules (hermes-agent `skills/software-development/
  hermes-agent-skill-authoring`): frontmatter starts at byte 0 with `---`;
  `name` matches `[a-zA-Z0-9_-]+`; `description` ≤ 60 chars, one sentence,
  ends with a period; body has When to Use (+ counter-triggers), actionable
  steps, Pitfalls, Verification. Reference Hermes tools (`read_file`,
  `terminal`, `skill_view`), not raw shell. No machine-local paths.

## How skills reach the agent

`__init__.py` registers each `skills/*/SKILL.md` through
`ctx.register_skill(name, path, description=...)` inside `register(ctx)`,
guarded with `getattr(ctx, "register_skill", None)` so older hosts load the
plugin without skills. While the plugin is enabled, Hermes lists the skill as
`<plugin>:<name>` in `skills_list` and in the session `<available_skills>`
index (API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); the agent loads it
with `skill_view("<plugin>:<name>")`. Plugin skills are read-only and never
copied into `~/.hermes/skills/`. A README alone is not discovery - without
the registered skill the agent never sees the plugin's guidance.

## Validation before merging

- `hermes plugins doctor <folder>` - runs Hermes's real discovery, manifest
  parse, `register(ctx)` and registries against the folder.
- Frontmatter: name + description present, description ≤ 60 chars ending in
  a period, no `:` unquoted in YAML scalars.
- Every documented command exists in the Hermes version claimed; every
  relative link resolves; every limit named honestly (what passes, what is
  blocked, what is not covered).
