"""RSI callback hooks — learn from tool errors."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .compressor import Lesson, LessonCompressor
from .lesson_store import LessonStore
from .lesson_extractor import LessonExtractor

logger = logging.getLogger(__name__)

_store: LessonStore | None = None
_compressor = LessonCompressor()
_extractor = LessonExtractor()
_session_id: str = ""
_session_tool_events: list[dict] = []
_session_metrics: dict = {}
_session_start_time: float = 0.0


def _reset_session():
    global _session_id, _session_tool_events, _session_metrics, _session_start_time
    _session_id = ""; _session_tool_events = []; _session_start_time = 0.0
    _session_metrics = {
        "tool_calls_total": 0, "tool_calls_failed": 0, "first_attempt_success": None,
        "error_types_seen": [], "lessons_injected": 0, "session_id": "",
        "outcome": "unknown", "duration_seconds": 0.0, "error_type_count": 0,
    }

def _ensure_store() -> LessonStore:
    global _store
    if _store is None:
        _store = LessonStore()
    return _store

def pre_llm_hook(**kwargs: Any) -> dict | None:
    global _session_id, _session_metrics
    if not kwargs.get("is_first_turn", False):
        return None

    # Save previous session's metrics before resetting
    _save_metrics_snapshot()

    _session_id = kwargs.get("session_id", "")
    _reset_session()
    _session_id = kwargs.get("session_id", "")
    _session_start_time = datetime.now(timezone.utc).timestamp()
    store = _ensure_store()
    deduped = LessonCompressor.deduplicate(store._read_all())
    compressed = _compressor.compress(deduped)
    if not compressed:
        return None
    _session_metrics["lessons_injected"] = len(deduped)
    return {"context": compressed}

def post_tool_call_hook(**kwargs: Any) -> None:
    global _session_id, _session_metrics
    if kwargs.get("status") not in {"ok","success","error"}:return
    if not isinstance(kwargs.get("tool_name"),str) or not kwargs["tool_name"].strip():return
    if not _session_metrics:
        _reset_session()
    _session_metrics["tool_calls_total"] += 1
    tool_name = kwargs.get("tool_name", "unknown")
    status = kwargs.get("status", "")
    error_type = kwargs.get("error_type", "")
    error_message = kwargs.get("error_message", "")
    sid = kwargs.get("session_id", "")
    if sid and not _session_id:
        _session_id = sid
    if _session_metrics["first_attempt_success"] is None:
        _session_metrics["first_attempt_success"] = (status != "error")
    if status == "error" or error_type:
        _session_metrics["tool_calls_failed"] += 1
        if error_type and error_type not in _session_metrics["error_types_seen"]:
            _session_metrics["error_types_seen"].append(error_type)
        event = {"type": "tool_failure", "tool": tool_name, "input": kwargs.get("args", {}),
                 "error": error_type or "unknown", "error_detail": error_message or "",
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        _session_tool_events.append(event)
        _extract_and_store([event], "running")
    else:
        _session_tool_events.append({"type": "tool_success", "tool": tool_name,
                                      "input": kwargs.get("args", {}),
                                      "timestamp": datetime.now(timezone.utc).isoformat()})
        # Extract success lessons every 3 successes
        success_count = sum(1 for e in _session_tool_events if e["type"] == "tool_success")
        if success_count > 0 and success_count % 3 == 0:
            _extract_and_store_success(_session_tool_events)

def _extract_and_store(events, session_outcome="running"):
    store = _ensure_store()
    import asyncio
    for lesson in _extractor.extract(tool_events=events, session_outcome=session_outcome):
        try:
            try:
                asyncio.get_running_loop()
                asyncio.ensure_future(store.upsert_lesson(lesson))
            except RuntimeError:
                asyncio.run(store.upsert_lesson(lesson))
        except Exception as e:
            logger.warning("[RSI] Failed to store lesson: %s", e)


def _extract_and_store_success(tool_events: list[dict]) -> None:
    """Extract success lessons and persist to store."""
    try:
        success_events = [e for e in tool_events if e.get("type") == "tool_success"]
        if not success_events:
            return

        lessons = _extractor.extract_success(success_events)
        if not lessons:
            return

        store = _ensure_store()
        import asyncio
        for lesson in lessons:
            try:
                try:
                    asyncio.get_running_loop()
                    asyncio.ensure_future(store.upsert_lesson(lesson))
                except RuntimeError:
                    asyncio.run(store.upsert_lesson(lesson))
            except Exception as e:
                logger.warning("[RSI] Failed to store success lesson: %s", e)
        logger.info("[RSI] Stored %d success lessons", len(lessons))
    except Exception as e:
        logger.warning("[RSI] Success extraction failed: %s", e)


def _save_metrics_snapshot() -> None:
    """Save current session metrics before reset for next session."""
    global _session_metrics
    if not _session_metrics.get("tool_calls_total", 0):
        return  # No activity this session, skip
    store = _ensure_store()
    import asyncio
    try:
        try:
            asyncio.get_running_loop()
            asyncio.ensure_future(store.save_session_metrics(_session_metrics))
        except RuntimeError:
            asyncio.run(store.save_session_metrics(_session_metrics))
    except Exception as e:
        logger.warning("[RSI] Failed to save session metrics: %s", e)