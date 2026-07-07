"""RSI Lesson Injector — Spec 02 Phase 1 & Spec 04.

Decision tree for lesson injection timing:
- defer → next session boundary (cache-safe, preferred)
- compress → summarize before injection
- inject-now → immediate (high urgency or near-expired cache)

Also handles formatting lessons as structured injection messages.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Queue for deferred lessons (session-boundary injection)
_session_boundary_queue: List[dict] = []


def format_lesson_injection(lessons: List[dict]) -> str:
    """Format lessons as injectable context block.

    Token budget: max 3 lessons, ~500 tokens total.
    """
    if not lessons:
        return ""

    parts = [
        "<lessons>",
        "Berikut adalah pelajaran dari sesi sebelumnya yang relevan dengan task ini:",
        "",
    ]

    count = 0
    for lesson in lessons[:3]:
        trigger = lesson.get("trigger_value", lesson.get("trigger_type", "general"))
        body = lesson.get("action_body", "")

        # Truncate long lessons
        if len(body) > 400:
            body = body[:400] + "..."

        parts.append(f"  [{trigger}]")
        parts.append(f"  {body}")
        parts.append("")
        count += 1

    if count == 0:
        return ""

    parts.append("</lessons>")
    return "\n".join(parts)


def decide_injection_timing(lesson: dict, cache_age_seconds: float = 0) -> str:
    """Decide injection timing: 'defer' | 'compress' | 'inject-now'.

    Rules:
    - confidence > 0.9 AND exact task match → inject-now
    - cache_age > 900 (15 min, near expiry) → inject-now
    - action_body > 500 tokens → compress first
    - Default → defer to next session boundary
    """
    confidence = lesson.get("confidence", 0.5)
    body = lesson.get("action_body", "")
    is_exact = lesson.get("trigger_type") == "task_type"

    if confidence >= 0.9 and is_exact:
        return "inject-now"

    if cache_age_seconds > 900:
        return "inject-now"  # cache almost expired anyway

    if len(body) > 500:
        return "compress"

    return "defer"


def compress_lesson(lesson: dict, max_len: int = 300) -> dict:
    """Compress a lesson by keeping only essential info.

    Extractive: keep trigger, first sentence of action_body, remove condition_context.
    """
    compressed = dict(lesson)
    body = lesson.get("action_body", "")

    if len(body) > max_len:
        # Keep first max_len chars + "..."
        compressed["action_body"] = body[:max_len] + "..."

    # Drop verbose condition context
    compressed.pop("condition_context", None)
    compressed.pop("tags", None)

    return compressed


def inject_lesson_cached(lesson: dict, messages: List[dict],
                         cache_tokens: int = 0, persona_id: str = "default") -> bool:
    """Smart injection that tries to preserve cache.

    Args:
        lesson: Lesson dict to inject
        messages: Current conversation message list (mutated in-place)
        cache_tokens: Estimated cache size (0 = unknown/small)
        persona_id: Persona for tracking

    Returns:
        True if injected, False if deferred.
    """
    # Method 1: Defer to next session (safest) if cache is significant
    if cache_tokens > 5000:
        _session_boundary_queue.append((lesson, persona_id))
        logger.debug(f"[RSI Injector] Deferred lesson to session boundary (cache={cache_tokens}tok)")
        return False

    # Method 2: Ensure lesson is compressed if long
    lesson_to_inject = lesson
    if len(lesson.get("action_body", "")) > 300:
        lesson_to_inject = compress_lesson(lesson)

    # Method 3: Inject as last user message (before final user turn)
    # This preserves system prompt + early history cache
    formatted = format_lesson_injection([lesson_to_inject])
    if not formatted:
        return False

    injection_msg = {"role": "user", "content": formatted}
    messages.insert(-1, injection_msg)  # before last user message
    logger.info(f"[RSI Injector] Injected lesson mid-conversation")
    return True


def clear_deferred_queue():
    """Clear the deferred queue (e.g., at session boundary after injection)."""
    _session_boundary_queue.clear()


def get_deferred_lessons() -> List[tuple]:
    """Return all deferred (lesson, persona_id) pairs."""
    return list(_session_boundary_queue)


def inject_deferred_at_session_start(persona_id: str,
                                      messages: List[dict]) -> bool:
    """Inject ALL deferred lessons for this persona at session boundary.

    This is the preferred timing — cache is fresh anyway since it's a new session.
    """
    relevant = [(l, p) for l, p in _session_boundary_queue if p == persona_id]
    if not relevant:
        return False

    lessons = [l for l, _ in relevant]
    formatted = format_lesson_injection(lessons)
    if formatted:
        # Inject at start of conversation (after system prompt)
        content_msg = {"role": "user", "content": formatted}
        messages.insert(1, content_msg)  # after system, before first user
        logger.info(f"[RSI Injector] Injected {len(lessons)} deferred lessons at session start")

    # Remove injected items from queue
    _session_boundary_queue[:] = [(l, p) for l, p in _session_boundary_queue
                                   if p != persona_id]
    return True
