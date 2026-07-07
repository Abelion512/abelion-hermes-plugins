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
from copy import deepcopy
from typing import Any, Optional

from ._patterns import PAREN_CRED_RE

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
    # Environment variable patterns (KEY=value)
    (re.compile(r'(?i)(api[_-]?key|apikey|secret|token|password)\s*[:=]\s*["\']?[a-z0-9_\-]{8,}["\']?'), "SECRET_CRED"),
    # Bare secret values (long alphanumeric preceded by "secret", "token", "password" or similar)
    (re.compile(r'(?i)\bsecret[a-z0-9_\-]{8,}\b|GITHUB_TOKEN|SUPER_SECRET|supersecret'), "BARE_SECRET"),
    # .env style (whole line)
    (re.compile(r'^\s*(?:export\s+)?(?:\w+)_(?:API_KEY|TOKEN|PASSWORD|SECRET)\s*[:=].+', re.MULTILINE), "ENV_ENTRY"),
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
    changes = 0
    result = text

    for pattern, label in SECRET_PATTERNS:
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

def pii_middleware(
    request: dict[str, Any],
    original_request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """LLM request middleware: mask PII in messages before provider.

    Register via ctx.register_middleware("llm_request", pii_middleware).
    Returns {"request": new_request} if changes made, None otherwise.
    """
    messages = request.get("messages", [])
    if not messages:
        return None

    changed = False
    new_request = deepcopy(request)
    new_messages = new_request.get("messages", [])

    total_masked = 0
    sensitivity = PUBLIC

    for msg in new_messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            # Multi-part content (tool results, images, etc.)
            for part in content:
                if part.get("type") == "text":
                    text = part.get("text", "")
                    masked, count = mask_content(text)
                    if count > 0:
                        part["text"] = masked
                        total_masked += count
                        changed = True
        elif isinstance(content, str):
            masked, count = mask_content(content)
            if count > 0:
                msg["content"] = masked
                total_masked += count
                changed = True

        # Track highest sensitivity found
        level = classify_content(str(content))
        if level == CONFIDENTIAL:
            sensitivity = CONFIDENTIAL
        elif level == INTERNAL and sensitivity != CONFIDENTIAL:
            sensitivity = INTERNAL

    if changed:
        logger.info(
            "[PII] Masked %d items in request (level=%s)",
            total_masked, sensitivity,
        )
        return {"request": new_request}

    return None


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
