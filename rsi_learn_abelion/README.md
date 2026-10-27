# rsi-learn-abelion

Experience learning for Hermes. Watches tool outcomes, extracts lessons
(`pattern → action` with confidence and frequency), stores them in
`$HERMES_HOME/shield/lessons/RSI_LESSONS.md`, and injects the relevant ones
before generation. Also detects time-sensitive questions by keyword and runs
`web_search` itself, injecting the results so answers use current data.

| Piece | Hook | What it does |
|---|---|---|
| Lesson recall | `pre_llm_call` (first turn) | Injects compressed, deduped lessons from the store |
| Outcome capture | `post_tool_call` | Records tool errors/successes for lesson extraction |
| Realtime decision | `pre_llm_call` (every turn) | Time-sensitive query → injected `web_search` results; relevant lessons → top 3 injected |

## Install

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/rsi_learn_abelion
```

## Verify

```bash
hermes plugins list                    # rsi-learn-abelion shows enabled
hermes plugins doctor rsi_learn_abelion
```

Ask a time-sensitive question ("what is the latest Claude model?"): the turn
receives injected web results. `skills_list` shows
`rsi-learn-abelion:experience-lessons`. After sessions with tool errors,
`$HERMES_HOME/shield/lessons/RSI_LESSONS.md` gains entries.

## Limits

- Time-sensitivity is a keyword/regex heuristic - it misses some current-event
  questions and fires on some that are not. Each trigger runs a real web
  search before generation (adds latency; needs working search config).
- The injected "SYSTEM OVERRIDE: REALTIME DATA AVAILABLE" banner is
  plugin-generated context, not a system message. It tells the model to
  prefer the injected results over training data; it has no authority beyond
  that turn's context.
- Lessons are heuristic and confidence-tagged; a stale or wrong lesson can be
  injected. They advise the model, they do not constrain it.
- The lesson store grows with use; review or prune RSI_LESSONS.md by hand if
  it accumulates noise.

## Disable / rollback

```bash
hermes plugins disable rsi-learn-abelion
hermes plugins remove rsi-learn-abelion
```

The lesson store is left on disk; delete
`$HERMES_HOME/shield/lessons/RSI_LESSONS.md` to forget everything.

## Bundled agent skill

`experience-lessons` - how the agent should apply injected lessons and search
context. Registered automatically while enabled on hosts with
`ctx.register_skill` (API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); older hosts load the plugin
without the skill. See [docs/USAGE.md](docs/USAGE.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
