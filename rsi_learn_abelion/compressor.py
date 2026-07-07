"""Compress RSI lessons before injection into ephemeral_system_prompt.

Rule-based, zero LLM calls. Goal: minimal text, maximum signal.

Design:
- MAX 8 lessons per injection (ephemeral prompt harus pendek)
- Dedup by pattern fingerprint
- Sort by (confidence * 0.6 + normalized_frequency * 0.4)
- High-confidence lessons get [HIGH] tag
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Lesson:
    """A single RSI lesson."""
    id: str
    pattern: str           # Trigger condition (e.g. "thread lock error")
    action: str            # What to do (e.g. "use threading.Lock with context manager")
    confidence: float      # 0.0 - 1.0
    frequency: int         # How many times observed
    error_type: str = ""
    tags: list[str] = field(default_factory=list)


class LessonCompressor:
    """Rule-based compressor — no LLM."""

    MAX_LESSONS = 12
    MIN_CONFIDENCE = 0.30  # lowered from 0.55 — v4 showed C underperform due to over-filtering
    HIGH_CONFIDENCE = 0.75

    def compress(self, lessons: list[Lesson]) -> str:
        """Compress lessons into a text block for ephemeral_system_prompt.

        Output format:
        [RSI Lessons]
        • [HIGH] IF <pattern> → <action> (seen Nx)
        • [MED] IF <pattern> → <action>
        [/RSI Lessons]
        """
        if not lessons:
            return ""

        # Filter by confidence
        filtered = [l for l in lessons if l.confidence >= self.MIN_CONFIDENCE]
        if not filtered:
            return ""

        # Deduplicate
        deduped = self.deduplicate(filtered)

        # Sort: high confidence + frequent first
        max_freq = max(l.frequency for l in deduped) if deduped else 1
        sorted_lessons = sorted(
            deduped,
            key=lambda l: (l.confidence * 0.6 + min(l.frequency, max_freq) / max_freq * 0.4),
            reverse=True,
        )[:self.MAX_LESSONS]

        # Build text
        lines = ["[RSI Lessons]"]
        for lesson in sorted_lessons:
            tag = "HIGH" if lesson.confidence >= self.HIGH_CONFIDENCE else "MED"
            freq_tag = f" (seen {lesson.frequency}x)" if lesson.frequency > 3 else ""
            lines.append(
                f"• [{tag}] IF {lesson.pattern} → {lesson.action}{freq_tag}"
            )
        lines.append("[/RSI Lessons]")

        return "\n".join(lines)

    @staticmethod
    def deduplicate(lessons: list[Lesson]) -> list[Lesson]:
        """Remove near-duplicates by fingerprint of pattern+action."""
        seen: set[str] = set()
        result: list[Lesson] = []
        for l in lessons:
            fp = hashlib.md5(f"{l.pattern[:50]}|{l.action[:50]}".encode()).hexdigest()[:8]
            if fp not in seen:
                seen.add(fp)
                result.append(l)
        return result
