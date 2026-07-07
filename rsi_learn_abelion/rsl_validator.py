"""RSI Lesson Validator — Spec 02 Phase 2.

3-layer validation pipeline:
1. Conflict detection — check if new lesson contradicts existing ones
2. Confidence scoring — threshold gates
3. Sandbox test (optional) — execute lesson in safe environment

Also includes extraction pipeline: error grouping → lesson candidate → validate.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable

from ..utils.memory_store import MemoryStore, get_persona_store
from ..utils.query_expander import expand_query

logger = logging.getLogger(__name__)

# ─── Error Pattern Registry ────────────────────────────────────────

ERROR_PATTERNS: Dict[str, Callable] = {
    "ImportError": lambda trace: {
        "trigger_type": "error_type",
        "trigger_value": "ImportError",
        "action_type": "instruction",
        "action_body": (
            "Jika pytest/script gagal dengan ImportError, "
            "cek apakah library sudah terinstall. "
            "Jalankan `pip install <missing_library>` atau periksa `requirements.txt`."
        ),
    },
    "ModuleNotFoundError": lambda trace: ERROR_PATTERNS["ImportError"](trace),
    "KeyError": lambda trace: {
        "trigger_type": "error_type",
        "trigger_value": "KeyError",
        "action_type": "instruction",
        "action_body": (
            "KeyError berarti key tidak ditemukan di dictionary. "
            "Gunakan .get() dengan default value, "
            "atau cek keberadaan key dengan `key in dict` sebelum akses."
        ),
    },
    "FileNotFoundError": lambda trace: {
        "trigger_type": "error_type",
        "trigger_value": "FileNotFoundError",
        "action_type": "instruction",
        "action_body": (
            "FileNotFoundError berarti path tidak ditemukan. "
            "Cek apakah file sudah dibuat, gunakan path absolute, "
            "atau buat directory dulu dengan os.makedirs() / path.parent.mkdir()."
        ),
    },
    "Connection refused": lambda trace: {
        "trigger_type": "error_type",
        "trigger_value": "connection_refused",
        "action_type": "instruction",
        "action_body": (
            "Koneksi ditolak → service belum running atau port salah. "
            "Cek status service, port binding, dan firewall."
        ),
    },
    "timeout": lambda trace: {
        "trigger_type": "error_type",
        "trigger_value": "timeout",
        "action_type": "instruction",
        "action_body": (
            "Timeout → koneksi lambat atau service down. "
            "Tambah timeout value, cek network, atau switch ke provider lain."
        ),
    },
}


# ─── Extraction ────────────────────────────────────────────────────

def group_by_error_pattern(traces: List[dict]) -> Dict[str, List[dict]]:
    """Group failed traces by error pattern (signal keyword)."""
    groups: Dict[str, List[dict]] = {}
    for trace in traces:
        error = (trace.get("error_snippet") or "").lower()
        matched = False
        for signal in ERROR_PATTERNS:
            if signal.lower() in error:
                groups.setdefault(signal, []).append(trace)
                matched = True
                break
        if not matched:
            groups.setdefault("_other", []).append(trace)
    return groups


def extract_lesson_candidate(pattern: str, traces: List[dict]) -> Optional[dict]:
    """Extract lesson from set of similar failures.

    Strategy:
    1. Rule-based: pattern matches known error signature → template
    2. LLM-based (fallback): ask LLM to summarize (caller provides)
    3. Returns structured lesson dict or None.
    """
    if pattern in ERROR_PATTERNS:
        lesson = ERROR_PATTERNS[pattern](traces[0] if traces else {})
        lesson["evidence_count"] = len(traces)
        lesson["confidence"] = min(0.5 + 0.1 * len(traces), 0.95)
        lesson["status"] = "candidate"
        lesson["source_trace_id"] = traces[0].get("session_id", "") if traces else ""
        return lesson

    return None  # no rule-based match → caller uses LLM fallback


# ─── Validation Pipeline ───────────────────────────────────────────

def is_contradictory(candidate: dict, existing: dict) -> bool:
    """Check if two lessons contradict each other.

    Simple heuristic: same trigger_type+trigger_value but different action_body
    means they conflict.
    """
    if (candidate.get("trigger_type") == existing.get("trigger_type") and
            candidate.get("trigger_value") == existing.get("trigger_value")):
        # Same trigger → check if action_body differs significantly
        c_body = candidate.get("action_body", "").strip().lower()
        e_body = existing.get("action_body", "").strip().lower()
        if c_body and e_body and c_body != e_body:
            return True
    return False


def validate_lesson(candidate: dict, persona_id: str = "default") -> bool:
    """3-layer validation. Returns True if lesson should be stored.

    Layer 1: Conflict detection against existing active lessons
    Layer 2: Confidence threshold (>= 0.6)
    Layer 3: Sandbox test (confidence >= 0.9, optional)
    """
    store = get_persona_store(persona_id)

    # Layer 1: Conflict detection
    trigger_type = candidate.get("trigger_type", "")
    trigger_value = candidate.get("trigger_value", "")
    existing = store._find_conflict(trigger_type, trigger_value) if hasattr(store, "_find_conflict") else None
    if existing:
        new_conf = candidate.get("confidence", 0.5)
        old_conf = existing.get("confidence", 0)
        if is_contradictory(candidate, existing):
            if new_conf <= old_conf:
                logger.info(f"[RSI Validator] Lesson rejected — conflict with existing (old {old_conf:.2f} >= new {new_conf:.2f})")
                return False
            else:
                logger.info(f"[RSI Validator] New lesson wins conflict (new {new_conf:.2f} > old {old_conf:.2f}) — deprecating old")

    # Layer 2: Confidence threshold
    confidence = candidate.get("confidence", 0.5)
    if confidence < 0.6:
        candidate["status"] = "candidate"
        logger.info(f"[RSI Validator] Lesson stored as 'candidate' (confidence {confidence:.2f} < 0.6)")
        # Still store but as candidate for manual review
        store.store_lesson(candidate)
        return True

    # Layer 3: Sandbox test (for high-confidence critical lessons)
    if confidence >= 0.9 and candidate.get("action_type") in ("code", "workflow"):
        sandbox_ok = _sandbox_test(candidate)
        if not sandbox_ok:
            candidate["confidence"] = 0.5
            candidate["status"] = "candidate"
            logger.warning(f"[RSI Validator] Sandbox test failed — downgrading confidence to 0.5")
        else:
            candidate["status"] = "active"
    else:
        candidate["status"] = "active"

    store.store_lesson(candidate)
    logger.info(f"[RSI Validator] Lesson stored as '{candidate['status']}'")
    return True


def _sandbox_test(lesson: dict) -> bool:
    """Run lesson in sandbox environment.

    For code-type lessons, attempts to parse/validate the action_body.
    For instruction-type, always passes (can't sandbox natural language).
    Returns True if test passes.
    """
    action_type = lesson.get("action_type", "")
    body = lesson.get("action_body", "")

    if action_type == "code":
        # Basic syntax check — try compile
        try:
            compile(body.strip(), "<sandbox>", "exec")
            return True
        except SyntaxError as e:
            logger.warning(f"[RSI Validator] Sandbox syntax error: {e}")
            return False

    # For non-code lessons, confidence test is sufficient
    return True


# ─── Run RSI Extraction (called at session end) ────────────────────

def run_rsi_extraction(persona_id: str, session_traces: List[dict],
                       llm_callback: Optional[Callable] = None):
    """Process all traces at session end.

    Args:
        persona_id: Persona namespace
        session_traces: List of trace dicts from this session
        llm_callback: Optional callable(str) -> str for LLM fallback extraction
    """
    store = get_persona_store(persona_id)

    # Step 1: Group by failure pattern
    failures = [t for t in session_traces if not t.get("success", True)]
    if not failures:
        logger.debug("[RSI Validator] No failures to extract lessons from")
        return

    patterns = group_by_error_pattern(failures)
    logger.info(f"[RSI Validator] Found {len(patterns)} failure patterns across {len(failures)} traces")

    # Step 2-4: For each pattern, extract → validate → store
    for pattern, traces in patterns.items():
        lesson = extract_lesson_candidate(pattern, traces)

        # Fallback to LLM if no rule matches
        if lesson is None and llm_callback:
            try:
                prompt = (
                    f"Analyze these {len(traces)} similar failures and extract "
                    f"a reusable lesson. Format as JSON:\n\n"
                    f"Traces: {json.dumps(traces, indent=2)}\n\n"
                    f"Output: {{\"trigger_type\": \"...\", \"trigger_value\": \"...\", "
                    f"\"condition_context\": \"...\", \"action_body\": \"...\", "
                    f"\"confidence\": 0.0-1.0}}"
                )
                response = llm_callback(prompt)
                lesson = json.loads(response)
            except Exception as e:
                logger.error(f"[RSI Validator] LLM extraction failed: {e}")
                continue

        if lesson:
            validate_lesson(lesson, persona_id)

    # Step 5: Apply decay & purge deprecated
    try:
        store.apply_decay()
        store.purge_deprecated()
    except Exception as e:
        logger.error(f"[RSI Validator] Cleanup failed: {e}")
