# tool-context-abelion

Injects a short `[Context: ...]` block after the first turn: current UTC
datetime and a reminder to use actual session tools and check their required
values. It grants no account access or blanket execution permission.

## Install

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/tool_context_abelion
```

## Verify

```bash
hermes plugins list                      # tool-context-abelion shows enabled
hermes plugins doctor tool_context_abelion
```

Second turn onward, the model's received message starts with
`[Context: <day> <date> <time> UTC ...]`. `skills_list` shows
`tool-context-abelion:turn-context`.

## Limits

- Only a valid explicit `available_tools` list is named. Native calls without
  that inventory say to use the host session tool list; no tool names are invented.
- The first turn of a session gets no injection (the system prompt already
  has the date and full tool list).
- The datetime is UTC. Local-time answers still need conversion.

## Disable / rollback

```bash
hermes plugins disable tool-context-abelion
hermes plugins remove tool-context-abelion
```

## Bundled agent skill

`turn-context` - how the agent should read the injected block. Registered
automatically while enabled on hosts with `ctx.register_skill` (API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); older hosts load the plugin without the skill.
See [docs/USAGE.md](docs/USAGE.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
