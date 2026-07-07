"""Persistent lesson store for RSI.

Stores lessons in RSI_LESSONS.md with full metadata persistence.
Format preserves: pattern, action, confidence, frequency, error_type, tags.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home

from .compressor import Lesson

logger = logging.getLogger(__name__)

RSI_TAG = "[rsi]"


class LessonStore:
    """Lesson store backed by RSI_LESSONS.md with full metadata."""

    def __init__(self):
        self._mem_path: Path | None = None
        self._in_memory_lessons: dict[str, Lesson] = {}

    @property
    def mem_path(self) -> Path:
        if self._mem_path is None:
            self._mem_path = get_hermes_home() / "shield" / "lessons" / "RSI_LESSONS.md"
            self._mem_path.parent.mkdir(parents=True, exist_ok=True)
        return self._mem_path

    async def get_relevant_lessons(
        self,
        task_description: str = "",
        tags: list[str] | None = None,
        limit: int = 20,
        min_confidence: float = 0.0,
    ) -> list[Lesson]:
        """Get all RSI lessons sorted by confidence."""
        lessons = self._read_all()
        filtered = [l for l in lessons if l.confidence >= min_confidence]
        filtered.sort(key=lambda l: -l.confidence)
        return filtered[:limit]

    async def upsert_lesson(self, lesson: Lesson) -> None:
        """Store a lesson — dedup by pattern fingerprint, merge metadata."""
        existing = self._read_all()

        # Look for matching lesson by pattern fingerprint
        fp = self._fingerprint(lesson)
        for ex in existing:
            if self._fingerprint(ex) == fp:
                # Merge: update frequency, keep highest confidence + tags
                ex.frequency += 1
                ex.confidence = max(ex.confidence, lesson.confidence)
                if lesson.error_type and lesson.error_type not in ex.error_type:
                    ex.error_type = lesson.error_type
                for t in lesson.tags:
                    if t not in ex.tags:
                        ex.tags.append(t)
                self._write_all(existing)
                logger.debug(
                    "[RSI] Updated lesson: %s (freq=%d, conf=%.2f)",
                    lesson.pattern[:40], ex.frequency, ex.confidence,
                )
                return

        # New lesson
        existing.append(lesson)
        self._write_all(existing)
        logger.info("[RSI] New lesson: %s → %s (conf=%.2f)",
                     lesson.pattern[:40], lesson.action[:40], lesson.confidence)

    async def save_session_metrics(self, metrics: dict) -> None:
        """Save session metrics for FASR/entropy analysis."""
        metrics_path = self.mem_path.parent / "rsi_session_metrics.jsonl"
        serializable = {
            k: list(v) if isinstance(v, set) else v
            for k, v in metrics.items()
        }
        with open(metrics_path, "a") as f:
            f.write(json.dumps(serializable) + "\n")

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _fingerprint(lesson: Lesson) -> str:
        """Deterministic fingerprint from pattern+action for dedup.
        Normalizes whitespace so 'shared state  accessed' == 'shared state accessed'.
        """
        import re as _re
        norm = lambda s: _re.sub(r'\s+', ' ', s.strip().lower())[:60]
        raw = f"{norm(lesson.pattern)}|{norm(lesson.action)}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _read_all(self) -> list[Lesson]:
        """Parse all [rsi]-tagged entries with full metadata."""
        if not self.mem_path.exists():
            return list(self._in_memory_lessons.values())

        lessons: list[Lesson] = []
        try:
            text = self.mem_path.read_text(encoding="utf-8")
            for entry in text.split("§"):
                entry = entry.strip()
                if not entry or not entry.startswith(RSI_TAG):
                    continue
                body = entry[len(RSI_TAG):].strip()
                lesson = self._parse_entry(body)
                if lesson:
                    lessons.append(lesson)
        except (OSError, IOError) as e:
            logger.warning("[RSI] Failed to read RSI_LESSONS.md: %s", e)
            return list(self._in_memory_lessons.values())

        # Merge with in-memory cache (new lessons not yet flushed)
        seen_fps = {self._fingerprint(l) for l in lessons}
        for ml in self._in_memory_lessons.values():
            if self._fingerprint(ml) not in seen_fps:
                lessons.append(ml)

        return lessons

    def _write_all(self, lessons: list[Lesson]) -> None:
        """Write lessons with full metadata — no field loss."""
        try:
            # Dedup before write
            seen: set[str] = set()
            deduped: list[Lesson] = []
            for l in lessons:
                fp = self._fingerprint(l)
                if fp not in seen:
                    seen.add(fp)
                    deduped.append(l)

            rsi_entries = []
            for l in deduped:
                lines = [
                    f"§",
                    f"{RSI_TAG} IF {l.pattern} → {l.action}",
                ]
                # Only write metadata if non-default
                if l.confidence != 0.65:
                    lines.append(f"  conf: {l.confidence:.2f}")
                if l.frequency > 1:
                    lines.append(f"  freq: {l.frequency}")
                if l.error_type:
                    lines.append(f"  error: {l.error_type}")
                if l.tags:
                    lines.append(f"  tags: {','.join(l.tags)}")
                rsi_entries.append("\n".join(lines))

            content = "\n".join(rsi_entries) if rsi_entries else ""
            self.mem_path.write_text(content.strip() + "\n", encoding="utf-8")

            # Update in-memory cache
            self._in_memory_lessons = {l.id: l for l in deduped}

        except (OSError, IOError) as e:
            logger.error("[RSI] Failed to write RSI_LESSONS.md: %s", e)
            for l in lessons:
                self._in_memory_lessons[l.id] = l

    @staticmethod
    def _parse_entry(body: str) -> Lesson | None:
        """Parse a single [rsi] entry body with optional metadata lines."""
        lines = body.strip().split("\n")
        if not lines:
            return None

        first = lines[0].strip()
        if "→" not in first:
            return None

        parts = first.split("→", 1)
        pattern = parts[0].replace("IF", "", 1).strip()
        action = parts[1].strip()

        # Defaults
        confidence = 0.65
        frequency = 1
        error_type = ""
        tags: list[str] = []

        # Parse optional metadata lines
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("conf:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("freq:"):
                try:
                    frequency = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("error:"):
                error_type = line.split(":", 1)[1].strip()
            elif line.startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                if raw:
                    tags = [t.strip() for t in raw.split(",") if t.strip()]

        return Lesson(
            id=f"rsi_{hash(pattern) & 0xFFFFFFFF}",
            pattern=pattern,
            action=action,
            confidence=confidence,
            frequency=frequency,
            error_type=error_type,
            tags=tags,
        )
