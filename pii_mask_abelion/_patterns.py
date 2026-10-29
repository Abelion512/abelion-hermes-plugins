"""Shared credential detection patterns — single source of truth.

Digunakan oleh:
- pii_mask_abelion.output_redact (held final-output stage)
- pii_mask_abelion (llm_request middleware)

This consolidated plugin uses this one local pattern module.
"""

from __future__ import annotations

import re

# ── Prose credential annotation pattern ────────────────────────────────
# Catches parenthetical credential labels in free-form AI prose.
# Value is bounded to 6 words before the annotation.
# Labels derived from common patterns in ~/.hermes/.env:
#   password, pass, pw, secret, token, apikey, credentials,
#   apppass, app_email, pass_email, auth, client_id, client_secret,
#   webhook_secret, sudo_password, username, email.
PAREN_CRED_RE = re.compile(
    r"(\S+(?:\s+\S+){0,5}?)\s*"
    r"(\(\s*"
    r"(?:"
    r"  app[ _-]?(?:email|pass(?:word)?)"
    r"  |pass[ _-]?email"
    r"  |client[ _-]?(?:id|secret)"
    r"  |api[ _-]?(?:key|secret)"
    r"  |auth[ _-]?(?:token|key)?"
    r"  |webhook[ _-]?secret"
    r"  |sudo[ _-]?password"
    r"  |password\s+nya"
    r"  |password|pass|pw"
    r"  |secret(?:s)?"
    r"  |credentials?"
    r"  |token"
    r"  |apikey"
    r"  |email"
    r"  |user\s?name"
    r"  |user"
    r"  |apppass"
    r")\s*"
    r"\))",
    re.IGNORECASE | re.VERBOSE,
)


# Cheap pre-filter: PAREN_CRED_RE can only match when a "(label)" annotation exists.
# Running this first avoids the leading \S+(?:\s+\S+){0,5}? backtracking on text without one.
PAREN_LABEL_RE = re.compile(
    r"\(\s*(?:app[ _-]?(?:email|pass)|pass[ _-]?email|client[ _-]?(?:id|secret)"
    r"|api[ _-]?(?:key|secret)|auth|webhook[ _-]?secret|sudo[ _-]?password"
    r"|password|pass|pw|secret|credential|token|apikey|email|user|apppass)",
    re.IGNORECASE,
)
