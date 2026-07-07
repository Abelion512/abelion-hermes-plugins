"""Output redaction plugin — transform_llm_output hook.

Menambal celah pipeline: ``final_response`` dari LLM tidak melalui
``redact_sensitive_text()`` (redaksi hanya di ``messages[]`` untuk
persistence, bukan return value). Ditambah pattern baru untuk credential
dalam prosa seperti ``admin (username) / password (password nya)``.

Ini hook modular via ``transform_llm_output`` — tidak patch file core Hermes.
"""

from __future__ import annotations

import logging
import re

from ._patterns import PAREN_CRED_RE

logger = logging.getLogger(__name__)


def redact_output(response_text: str) -> str | None:
    """Redact credentials from LLM final response.

    Returns redacted string if changes made, ``None`` if nothing to redact
    (so next hook in chain can run).

    Layers:
    1. Prose parenthetical credential annotation pattern (custom)
    2. Delegates to Hermes' builtin ``redact_sensitive_text`` (catches env
       vars, API keys, JWTs, auth headers, DB connstrings, etc.)
    """
    if not response_text:
        return None

    text = response_text
    changed = False
    n = 0  # count of parenthetical pattern substitutions

    # Layer 1: prose parenthetical credentials
    if "(" in text and ")" in text:
        new_text, n = PAREN_CRED_RE.subn(
            lambda m: "*** " + m.group(2), text
        )
        if n > 0:
            text = new_text
            changed = True

    # Layer 2: Hermes builtin redaction
    try:
        from agent.redact import redact_sensitive_text
        redacted = redact_sensitive_text(text)
        if redacted != text:
            text = redacted
            changed = True
    except ImportError:
        # Running outside Hermes (tests, standalone) — skip builtin
        pass
    except Exception as exc:
        logger.warning("[output_redact] redact_sensitive_text failed: %s", exc)

    if changed:
        logger.info("[output_redact] Redacted %d pattern(s) in LLM response (%d parenthetical)", n, n > 0)
        return text

    return None
