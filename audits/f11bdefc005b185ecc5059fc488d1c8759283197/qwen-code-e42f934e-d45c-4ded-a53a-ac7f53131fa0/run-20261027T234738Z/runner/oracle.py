"""Independent semantic oracle for Privacy Guard (pii_mask_abelion + output_redact_abelion).

Written from the SOURCE CONTRACT of commit f11bdef (read, not copied from any prior suite):
  pii_middleware.py: SECRET_PATTERNS list order L38-63; mask_content sequential subn
  with replacement "[REDACTED]_<LABEL>" (L102-118); classify_content CONFIDENTIAL >
  INTERNAL > PUBLIC (L79-97); pii_middleware deepcopy, masks ONLY parts with
  type=="text", returns {"request":...} iff changed else None (L128-182).
  _patterns.py PAREN_CRED_RE: group(1)= up to 6 words before annotation, group(2)= label.
  output_redact.py redact_output: layer1 replaces match with "*** " + group(2)
  (label KEPT), layer2 delegates to agent.redact (absent -> ImportError -> skip),
  returns None when unchanged.

The oracle re-implements these semantics independently (own regex construction where
the contract is unambiguous, documented pass-through where it is not) so that test
expectations are grounded in the contract, not in the implementation's incidental bugs.
Where the contract itself is ambiguous or buggy, we record the CONTRACT-LITERAL result
and flag policy divergence separately.
"""
from __future__ import annotations

import re

# ── Contract-literal pattern set (mirrors the documented ORDER and LABELS) ──
# Order matters: mask_content applies patterns sequentially over evolving text.
ORACLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?i)(?:sk|pk)-[a-z0-9]{4,}'), "OPENAI_KEY"),
    (re.compile(r'(?i)ghp_[a-z0-9]{8,}|gho_[a-z0-9]{8,}|ghu_[a-z0-9]{8,}'), "GITHUB_TOKEN"),
    (re.compile(r'(?i)(api[_-]?key|apikey|secret|token|password)\s*[:=]\s*["\']?[a-z0-9_\-]{8,}["\']?'), "SECRET_CRED"),
    (re.compile(r'(?i)\bsecret[a-z0-9_\-]{8,}\b|GITHUB_TOKEN|SUPER_SECRET|supersecret'), "BARE_SECRET"),
    (re.compile(r'^\s*(?:export\s+)?(?:\w+)_(?:API_KEY|TOKEN|PASSWORD|SECRET)\s*[:=].+', re.MULTILINE), "ENV_ENTRY"),
    # PAREN_CRED reproduced from contract (shared _patterns.py)
    (re.compile(
        r"(\S+(?:\s+\S+){0,5}?)\s*"
        r"(\(\s*(?:"
        r"  app[ _-]?(?:email|pass(?:word)?)"
        r"|pass[ _-]?email"
        r"|client[ _-]?(?:id|secret)"
        r"|api[ _-]?(?:key|secret)"
        r"|auth[ _-]?(?:token|key)?"
        r"|webhook[ _-]?secret"
        r"|sudo[ _-]?password"
        r"|password\s+nya"
        r"|password|pass|pw"
        r"|secret(?:s)?"
        r"|credentials?"
        r"|token"
        r"|apikey"
        r"|email"
        r"|user\s?name"
        r"|user"
        r"|apppass"
        r")\s*\))",
        re.IGNORECASE | re.VERBOSE), "PAREN_CRED"),
    (re.compile(r'(?i)(postgres|mysql|mongodb|redis)://[^@\s]+@'), "DB_CONNECTION"),
    (re.compile(r'(?i)https?://[^@\s]+:[^@\s]+@'), "URL_WITH_CREDS"),
    (re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----'), "PRIVATE_KEY"),
    (re.compile(r'\b\d{16,19}\b'), "LONG_NUMBER"),
    (re.compile(r"(?i)\b(email|phone|address|ssn|kks|nik|ktp|npwp)\s*[:=]\s*[\"']?\w+"), "PII_FIELD"),
    (re.compile(r'(?i)bearer\s+[a-z0-9_\-\.]{12,}', re.MULTILINE), "BEARER_TOKEN"),
]

INTERNAL_KEYWORDS = [
    "internal", "company", "proprietary", "confidential", "private",
    "rahasia", "internal only", "do not share", "embargo",
]
INTERNAL_PATTERN = re.compile(r'(?i)\b(' + "|".join(re.escape(k) for k in INTERNAL_KEYWORDS) + r')\b')

PUBLIC, INTERNAL, CONFIDENTIAL = "PUBLIC", "INTERNAL", "CONFIDENTIAL"


def oracle_classify(text: str) -> str:
    if not text:
        return PUBLIC
    for pat, _ in ORACLE_PATTERNS:
        if pat.search(text):
            return CONFIDENTIAL
    if INTERNAL_PATTERN.search(text):
        return INTERNAL
    return PUBLIC


def oracle_mask(text: str) -> tuple[str, int]:
    changes = 0
    result = text
    for pat, label in ORACLE_PATTERNS:
        result, count = pat.subn(lambda m, _l=label: f"[REDACTED]_{_l}", result)
        changes += count
    return result, changes


def oracle_middleware(request: dict) -> dict | None:
    """Contract-literal middleware semantics on plain dicts (mock transport)."""
    messages = request.get("messages", [])
    if not messages:
        return None
    import copy as _copy
    new_request = _copy.deepcopy(request)
    changed = False
    for msg in new_request.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    masked, count = oracle_mask(part.get("text", ""))
                    if count > 0:
                        part["text"] = masked
                        changed = True
        elif isinstance(content, str):
            masked, count = oracle_mask(content)
            if count > 0:
                msg["content"] = masked
                changed = True
    return {"request": new_request} if changed else None


def oracle_output_redact(response_text: str) -> str | None:
    """Layer-1 contract: replace group(1) value, KEEP group(2) label. Layer-2 absent."""
    if not response_text:
        return None
    text = response_text
    changed = False
    if "(" in text and ")" in text:
        pat = ORACLE_PATTERNS[5][0]
        new_text, n = pat.subn(lambda m: "*** " + m.group(2), text)
        if n > 0:
            text = new_text
            changed = True
    return text if changed else None
