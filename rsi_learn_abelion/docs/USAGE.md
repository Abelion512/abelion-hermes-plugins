# rsi-learn-abelion - mechanism reference

## Registered callbacks

| Registration | Callback | Source |
|---|---|---|
| `pre_llm_call` hook | `pre_llm_hook` - first-turn lesson recall | `callback_hooks.py` |
| `post_tool_call` hook | `post_tool_call_hook` - outcome capture | `callback_hooks.py` |
| `pre_llm_call` hook | `realtime_decision_hook` - per-turn decisions | `decision_hook.py` |
| skill | `experience-lessons` via `ctx.register_skill` | `skills/` |

Other modules (`rsl_injector.py`, `reflection.py`, `rsl_validator.py`,
`lesson_extractor.py`, `compressor.py`) are library code used by the hooks or
kept for the roadmap; they are not registered callbacks on their own.

## Behavior details

- **Lesson recall** (first turn): dedups the store
  (`LessonCompressor.deduplicate`), compresses it, and returns it as
  `{"context": ...}`. Also snapshots the previous session's metrics before
  resetting.
- **Outcome capture** (`post_tool_call`): accumulates per-session tool events
  and metrics (totals, failures, error types) for extraction into lessons.
- **Realtime decision** (every turn with a non-empty user message):
  1. `_is_time_sensitive` matches `_TIME_KEYWORDS` (latest/recent/update/
     news/current/today/price/release/announce/cutoff/…) or known model-name
     patterns (`claude|gpt|gemini|llama|…` + digit). On match it calls
     `web_search_tool(query, limit=3)` directly and injects up to 3 results
     (truncated to ~2000 chars) under a "REALTIME DATA AVAILABLE" banner,
     or a "no results / knowledge may be outdated" fallback.
  2. It filters stored lessons by keyword overlap with the message
     (`_filter_relevant`) and injects the top 3 by confidence/frequency as
     `[Experience Lessons]` with `[HIGH]` (≥ 0.75) / `[MED]` tags.

## Lesson store

`$HERMES_HOME/shield/lessons/RSI_LESSONS.md` via `LessonStore`
(`lesson_store.py`). Lessons are `Lesson` records (`compressor.py`):
pattern, action, confidence, frequency, error_type, tags. Upserts merge by
pattern fingerprint (frequency increments, highest confidence kept). The
store is Markdown for hand review and pruning.

## Configuration

None. Trigger keywords, confidence thresholds (0.75 HIGH, 0.8 boost,
0.9 inject-now), result caps (3 lessons, 3 search results, ~2000 chars) are
constants in `decision_hook.py` / `rsl_injector.py`.
