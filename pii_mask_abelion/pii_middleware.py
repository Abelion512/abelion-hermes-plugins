"""PII Layering — 3-level sensitivity detection + masking.

Intercepts LLM request payload via llm_request middleware.
Masks sensitive content BEFORE it reaches the provider.

Levels (from research briefs):
  PUBLIC      → no mask, route any provider
  INTERNAL    → mask internal keywords (company, proprietary)
  CONFIDENTIAL → mask secrets, PII, API keys

Detection: regex + keyword heuristics (zero LLM cost).
Masking: replace matched text with [REDACTED_<type>] tags.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from ._credentials import classify_field, mask_credentials, mask_value_for_key
from ._patterns import PAREN_CRED_RE, PAREN_LABEL_RE

logger = logging.getLogger(__name__)

# ── Sensitivity levels ────────────────────────────────────────────────

PUBLIC = "PUBLIC"
INTERNAL = "INTERNAL"
CONFIDENTIAL = "CONFIDENTIAL"

SENSITIVITY_LEVELS = (PUBLIC, INTERNAL, CONFIDENTIAL)


# ── Secrets patterns (CONFIDENTIAL) ────────────────────────────────────

SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    # API keys & tokens (standalone prefixes)
    (re.compile(r'(?i)(?:sk|pk)-[a-z0-9]{4,}'), "OPENAI_KEY"),
    # GitHub tokens
    (re.compile(r'(?i)ghp_[a-z0-9]{8,}|gho_[a-z0-9]{8,}|ghu_[a-z0-9]{8,}'), "GITHUB_TOKEN"),
    # KEY=value assignments are handled by mask_credentials (value only, field name kept)
    # Bare secret values (long alphanumeric preceded by "secret", "token", "password" or similar)
    (re.compile(r'(?i)\bsecret(?=[a-z_\-]*\d)[a-z0-9_\-]{8,}\b|supersecret'), "BARE_SECRET"),
    # .env style lines are handled by mask_credentials (value only, field name kept)
    # Prose credential annotations: ``value (password)``, ``user (username)``
    # Catches credentials labeled in free-form prose before reaching provider.
    # Pattern imported from _patterns.py (shared with output_redact_abelion).
    (PAREN_CRED_RE, "PAREN_CRED"),
    # Connection strings
    (re.compile(r'(?i)(postgres|mysql|mongodb|redis)://[^@\s]+@'), "DB_CONNECTION"),
    (re.compile(r'(?i)https?://[^@\s]+:[^@\s]+@'), "URL_WITH_CREDS"),
    # Private keys
    (re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----'), "PRIVATE_KEY"),
    # PII patterns (Indonesia-specific KTP/NIK/NPWP)
    (re.compile(r'\b\d{16,19}\b'), "LONG_NUMBER"),
    (re.compile(r'(?i)\b(email|phone|address|ssn|kks|nik|ktp|npwp)\s*[:=]\s*["\']?\w+'), "PII_FIELD"),
    # Bearer tokens (JWT format)
    (re.compile(r'(?i)bearer\s+[a-z0-9_\-\.]{12,}', re.MULTILINE), "BEARER_TOKEN"),
]

# ── Internal markers (INTERNAL) ────────────────────────────────────────

INTERNAL_KEYWORDS = [
    "internal", "company", "proprietary", "confidential", "private",
    "rahasia", "internal only", "do not share", "embargo",
]

INTERNAL_PATTERN = re.compile(
    r'(?i)\b(' + "|".join(re.escape(kw) for kw in INTERNAL_KEYWORDS) + r')\b'
)


# ── Classification ─────────────────────────────────────────────────────

def classify_content(text: str) -> str:
    """Classify text sensitivity level.

    Returns one of PUBLIC, INTERNAL, CONFIDENTIAL.
    Uses rule-based heuristics only — zero LLM cost.
    """
    if not text:
        return PUBLIC

    # Check CONFIDENTIAL first (highest priority)
    for pattern, _ in SECRET_PATTERNS:
        if pattern is PAREN_CRED_RE and not PAREN_LABEL_RE.search(text):
            continue
        if pattern.search(text):
            return CONFIDENTIAL

    # Check INTERNAL
    if INTERNAL_PATTERN.search(text):
        return INTERNAL

    return PUBLIC


# ── Masking ────────────────────────────────────────────────────────────

def mask_content(text: str, mask_char: str = "[REDACTED]") -> str:
    """Mask all sensitive content in text.

    Returns (masked_text, changes) where changes is a count of replacements.
    """
    # Credential names/values first: keeps the field name and masks only the value.
    result, changes = mask_credentials(text)

    for pattern, label in SECRET_PATTERNS:
        if pattern is PAREN_CRED_RE and not PAREN_LABEL_RE.search(result):
            continue
        new_result, count = pattern.subn(
            lambda m: _mask_match(m, label, mask_char), result
        )
        if count > 0:
            changes += count
            result = new_result

    return result, changes


def _mask_match(match: re.Match, label: str, mask_char: str) -> str:
    """Replace matched text with labeled redaction marker."""
    return f"{mask_char}_{label}"


# ── Middleware ─────────────────────────────────────────────────────────

# String values under these keys are structure, not content: never rewritten.
_SKIP_KEYS = frozenset({
    "role", "type", "id", "name", "model", "tool_call_id", "call_id", "tool_use_id", "mime_type",
    "media_type", "finish_reason", "tool_choice",
})
# Binary payloads: opaque, left alone (a known gap: secrets inside images/audio are not inspected).
_BINARY_KEYS = frozenset({"data", "b64_json", "file_data", "audio", "bytes", "signature", "encrypted_content"})
_VALUE_KEYS = frozenset({"default", "example", "examples", "const", "value"})
_B64 = re.compile(r"[A-Za-z0-9+/=_\-]{128,}")


def _mask_json_string(text: str):
    """Tool-call ``arguments`` are JSON text: mask the string leaves so the JSON stays valid."""
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, (dict, list)):
        return None
    new, count = _mask_obj(parsed)
    if count == 0:
        return text, 0
    return json.dumps(new, ensure_ascii=False), count


def _mask_obj(value: Any, key: str = ""):
    """Copy-on-write walk: returns (value, masked_count); unchanged objects are returned as is."""
    if isinstance(value, str):
        if not value or key in _SKIP_KEYS or value.startswith("data:"):
            return value, 0
        if key in _BINARY_KEYS and _B64.fullmatch(value):
            return value, 0
        if key == "arguments" and value[:1] in "{[":
            res = _mask_json_string(value)
            if res is not None:
                return res
        if key:
            new, count = mask_value_for_key(key, value)
            if count:
                return new, count
        try:
            masked, count = mask_content(value)
        except Exception:  # never let one string abort masking, and never pass it on unmasked
            logger.warning("[PII] masking failed for a string; replaced it", exc_info=True)
            return "[REDACTED]_MASK_ERROR", 1
        return (masked, count) if count else (value, 0)
    if isinstance(value, dict):
        out = None
        total = 0
        pair = value.get("name") if isinstance(value.get("name"), str) else None
        for k, v in value.items():
            if not isinstance(k, str):
                continue
            # {"name": "HF_TOKEN", "value": "..."} style entries: classify by the name.
            if pair is not None and k == "value" and isinstance(v, str) and classify_field(pair):
                new, count = mask_value_for_key(pair, v)
            else:
                # {"api_key": {"default": "..."}}: the value inherits the credential field name.
                new, count = _mask_obj(v, key if k in _VALUE_KEYS and key and classify_field(key) else k)
            if count:
                if out is None:
                    out = dict(value)
                out[k] = new
                total += count
        return (out, total) if out is not None else (value, 0)
    if isinstance(value, (list, tuple)):
        out = None
        total = 0
        for i, v in enumerate(value):
            new, count = _mask_obj(v, key)
            if count:
                if out is None:
                    out = list(value)
                out[i] = new
                total += count
        if out is None:
            return value, 0
        return (tuple(out) if isinstance(value, tuple) else out), total
    return value, 0


def pii_middleware(
    request: dict[str, Any],
    original_request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """LLM request middleware: mask PII and credentials in the outgoing request.

    Walks the WHOLE request (messages, tool-call arguments, system/instructions/input and
    other provider-specific fields), not just ``messages[].content``. Tool schemas are walked too (descriptions, defaults, examples) but only string values change. Ids,
    roles, model names and opaque base64 payloads are left alone. Copy-on-write: the caller's
    request is never mutated.

    Register via ctx.register_middleware("llm_request", pii_middleware).
    Returns {"request": new_request} if changes made, None otherwise.
    """
    if not isinstance(request, dict) or not request:
        return None
    try:
        new_request, total_masked = _mask_obj(request)
    except Exception:
        # Unsupported structure (cyclic, absurdly deep, ...). The host cannot be told to block the
        # call from here: it would send the original, so say so loudly instead of failing silently.
        logger.error("[PII] could not walk the request; it will be sent UNMASKED", exc_info=True)
        return None
    if total_masked == 0:
        return None
    logger.info("[PII] Masked %d items in request (level=%s)", total_masked, CONFIDENTIAL)
    return {"request": new_request}


# ── Standalone scan (stateless, for testing) ───────────────────────────

def scan_message(text: str) -> dict[str, Any]:
    """Scan a message for PII. Returns scan result.

    Result keys:
      sensitivity: PUBLIC | INTERNAL | CONFIDENTIAL
      has_secrets: bool
      masked_count: int
      masked_text: str (redacted version if secrets found)
    """
    sensitivity = classify_content(text)
    masked, count = mask_content(text)
    return {
        "sensitivity": sensitivity,
        "has_secrets": count > 0,
        "masked_count": count,
        "masked_text": masked if count > 0 else text,
    }
