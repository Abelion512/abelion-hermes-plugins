"""Realtime decision hook — pre_llm_call.

Every turn, before model generates:
1. Classify if query is time-sensitive → auto web_search
2. Check if RSI lessons are relevant → inject top matches

Priority: realtime > experience > training data.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .compressor import Lesson, LessonCompressor
from .lesson_store import LessonStore

logger = logging.getLogger(__name__)

# ── Time-sensitivity keywords ───────────────────────────────────────
# These trigger web_search before any generation.
_TIME_KEYWORDS = re.compile(
    r"\b(latest|recent|update|news|current|now|today|"
    r"price|release|announce|new (model|tool|api|version)|"
    r"what.{0,20}new|what.{0,20}happened|"
    r"cutoff|training data|outdated)\b",
    re.IGNORECASE,
)

# Model/release names that indicate time-sensitivity
_TIME_MODEL_NAMES = re.compile(
    r"\b(claude|gpt|gemini|llama|fable|opus|sonnet|haiku|"
    r"nemotron|nuevo|deepseek|qwen|mistral|phi)\s*[0-9]",
    re.IGNORECASE,
)

# Relevance: keywords that map to existing lesson patterns
_LESSON_MAP = {
    "file": {"write", "read", "file", "edit", "patch", "save", "directory"},
    "shell": {"bash", "terminal", "shell", "command", "run", "exec", "script", "install"},
    "browser": {"web", "browser", "navigate", "url", "page", "search"},
    "patch": {"patch", "diff", "change", "modify", "update", "replace"},
}

_LESSON_STORE: LessonStore | None = None


def _ensure_store() -> LessonStore:
    global _LESSON_STORE
    if _LESSON_STORE is None:
        _LESSON_STORE = LessonStore()
    return _LESSON_STORE


def realtime_decision_hook(**kwargs) -> dict | None:
    """pre_llm_call hook: decide what to inject before generation.

    Returns {"context": "..."} or None (nothing to inject).
    """
    user_msg: str = kwargs.get("user_message", "")
    if not user_msg:
        return None

    ctx_parts: list[str] = []

    # ── 1. Time-sensitivity check → web search ──
    if _is_time_sensitive(user_msg):
        try:
            # Lazy import — don't block plugin load
            from tools.web_tools import web_search_tool
            raw = web_search_tool(user_msg, limit=3)
            parsed = json.loads(raw)
            if parsed.get("success"):
                results = parsed.get("data", {}).get("web", [])
                if results:
                    lines = [
                        "╔══════════════════════════════════════════════╗",
                        "║  SYSTEM OVERRIDE: REALTIME DATA AVAILABLE  ║",
                        "╚══════════════════════════════════════════════╝",
                        "",
                        "The user's question below is TIME-SENSITIVE.",
                        "You have TWO sources of information:",
                        "  A) Your training data (OUTDATED — do not use)",
                        "  B) Web search results below (CURRENT — use this)",
                        "",
                        "RULES:",
                        "1. Answer using ONLY the web search results below.",
                        "2. Do NOT add information from your training data.",
                        "3. If results don't answer the question fully, say so.",
                        "4. If asked about a model/version/price/release, start with",
                        "   the exact name and date from search results.",
                        "",
                        "--- WEB SEARCH RESULTS ---",
                    ]
                    for r in results[:3]:
                        title = r.get("title", "")
                        url = r.get("url", "")
                        desc = r.get("description", "")
                        lines.append(f"• {title}: {desc[:200]}")
                        lines.append(f"  {url}")
                    lines.append("[/Web Search Results]")
                    block = "\n".join(lines)
                    # Truncate to ~2000 chars
                    if len(block) > 2000:
                        block = block[:1997] + "..."
                    ctx_parts.append(block)
                    logger.info(
                        "[abelion_decision] Web search triggered for: %.60s (results=%d)",
                        user_msg, len(results),
                    )
            else:
                # Web search triggered tapi gak ada hasil — inject fallback warning
                ctx_parts.append(
                    "[Web Search Results]\n"
                    "⚠️ Web search returned no results for this query.\n"
                    f"Query: {user_msg[:100]}\n"
                    "Your training data cutoff may not include the latest information.\n"
                    "If the user asked about current models/prices/releases, "
                    "explicitly state that your knowledge may be outdated.\n"
                    "[/Web Search Results]"
                )
        except Exception as e:
            logger.warning("[abelion_decision] Web search failed: %s", e)

    # ── 2. High-confidence RSI lesson check ──
    try:
        store = _ensure_store()
        lessons = store._read_all()
        if lessons:
            # Filter by relevance to current message
            relevant = _filter_relevant(lessons, user_msg)
            if relevant:
                sorted_lessons = sorted(
                    relevant, key=lambda l: (-l.confidence, -l.frequency)
                )[:3]
                lesson_lines = ["[Experience Lessons]"]
                for l in sorted_lessons:
                    tag = "HIGH" if l.confidence >= 0.75 else "MED"
                    freq = f" (seen {l.frequency}x)" if l.frequency > 1 else ""
                    lesson_lines.append(
                        f"• [{tag}] {l.pattern} → {l.action}{freq}"
                    )
                lesson_lines.append("[/Experience Lessons]")
                ctx_parts.append("\n".join(lesson_lines))
                logger.info(
                    "[abelion_decision] Lessons injected: %d (total stored: %d)",
                    len(sorted_lessons), len(lessons),
                )
    except Exception as e:
        logger.warning("[abelion_decision] Lesson check failed: %s", e)

    if not ctx_parts:
        return None

    return {"context": "\n\n".join(ctx_parts)}


# ── Helpers ─────────────────────────────────────────────────────────

def _is_time_sensitive(text: str) -> bool:
    """Heuristic: does query need realtime info?"""
    if _TIME_KEYWORDS.search(text):
        return True
    if _TIME_MODEL_NAMES.search(text):
        return True
    return False


def _filter_relevant(lessons: list[Lesson], user_msg: str) -> list[Lesson]:
    """Return lessons whose pattern keywords overlap with user message."""
    msg_lower = user_msg.lower()
    msg_words = set(msg_lower.split())

    # Score each lesson by keyword overlap
    scored: list[tuple[Lesson, float]] = []
    for l in lessons:
        # Extract keywords from pattern
        pattern_keywords = set()
        for cat, words in _LESSON_MAP.items():
            if any(w in l.pattern.lower() for w in words):
                pattern_keywords |= words

        # Also grab individual words from pattern
        pattern_words = set(re.findall(r"\w+", l.pattern.lower()))
        pattern_keywords |= pattern_words

        overlap = len(pattern_keywords & msg_words) / max(len(pattern_keywords), 1)
        if overlap > 0 or l.confidence >= 0.8:
            # Boost confidence by overlap
            scored.append((l, min(1.0, l.confidence + overlap * 0.2)))

    scored.sort(key=lambda x: -x[1])
    return [l for l, _ in scored]
