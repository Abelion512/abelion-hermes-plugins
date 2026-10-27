"""Generic credential detection for outbound LLM requests.

Two ideas, both bounded (no nested unbounded quantifiers, linear scans):

1. Vendor token shapes with a fixed public prefix (``hf_``, ``AIza``, ``npm_`` ...).
2. Field names: ``<anything>_API_KEY``, ``api-key``, ``apiKey``, ``clientSecret``,
   ``SOME_PROVIDER_TOKEN`` and so on. The name is normalised (case, ``_``/``-``/``.``,
   camelCase) and only the VALUE is masked; the field name and the surrounding text stay.

No provider list is needed for (2). Names are split into segments, and a name is a
credential when a segment (or segment pair such as ``api`` + ``key``) says so.
"""

from __future__ import annotations

import re

# ── 1. Fixed-prefix token shapes (public formats) ────────────────────────
# Prefix is literal, the body length floor keeps prose like "hf_x" from matching.
TOKEN_SHAPES = re.compile(
    r"\b(?:"
    r"sk-or-v1-[A-Za-z0-9]{20,}"            # OpenRouter
    r"|sk-ant-[A-Za-z0-9_\-]{20,}"          # Anthropic
    r"|sk-proj-[A-Za-z0-9_\-]{20,}"         # OpenAI project keys
    r"|[sp]k-lf-[A-Za-z0-9\-]{16,}"         # Langfuse secret/public key
    r"|hf_[A-Za-z0-9]{30,}"                 # Hugging Face
    r"|AIza[0-9A-Za-z_\-]{35}"              # Google API key
    r"|GOCSPX-[A-Za-z0-9_\-]{20,}"          # Google OAuth client secret
    r"|ya29\.[A-Za-z0-9_\-]{20,}"           # Google OAuth access token
    r"|gh[pousr]_[A-Za-z0-9]{20,}"          # GitHub tokens
    r"|github_pat_[A-Za-z0-9_]{20,}"        # GitHub fine-grained token
    r"|ntn_[A-Za-z0-9]{30,}"                # Notion
    r"|npm_[A-Za-z0-9]{36}"                 # npm
    r"|tvly-[A-Za-z0-9_\-]{16,}"            # Tavily
    r"|fc-[A-Za-z0-9]{20,}"                 # Firecrawl
    r"|pcsk_[A-Za-z0-9_]{20,}"              # Pinecone
    r"|apify_api_[A-Za-z0-9]{20,}"          # Apify
    r"|ctx7sk-[A-Za-z0-9_\-]{10,}"          # Context7
    r"|m0-[A-Za-z0-9]{20,}"                 # Mem0
    r"|sb_(?:secret|publishable)_[A-Za-z0-9_\-]{16,}"  # Supabase
    r"|xox[abprs]-[A-Za-z0-9\-]{10,}"       # Slack
    r"|AKIA[0-9A-Z]{16}"                    # AWS access key id
    r"|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"  # JWT (Supabase keys etc.)
    r")(?![A-Za-z0-9])"
)
# Telegram bot token: 8-10 digits, colon, 35 chars. Discord bot token: three dot parts.
TELEGRAM_TOKEN = re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")
DISCORD_TOKEN = re.compile(r"\b[MNO][A-Za-z0-9_\-]{23,25}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b")

# ── 2. Field-name driven masking ─────────────────────────────────────────
# name, separator (quotes allowed so JSON/headers/query/env/CLI all fit), value.
# Name is bounded to 64 chars; the value excludes whitespace and delimiters.
_ASSIGN = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9_.\-]{1,63})"
    r"(?P<sep>[\"']?\??[ \t]*[:=][ \t]*[\"']?)"
    r"(?P<value>[^\s\"',;&<>{}\[\]()/][^\s\"',;&<>{}\[\]()]{5,})"
)
# CLI flags: --password hunter2, --api-key=abc, -H "x-api-key: abc" is covered by _ASSIGN.
_FLAG = re.compile(
    r"(?P<name>--[A-Za-z][A-Za-z0-9\-]{1,40})(?P<sep>[ =])(?P<value>[^\s\"',;&<>{}\[\]()-][^\s\"',;&<>{}\[\]()]{5,})"
)

_SPLIT = re.compile(r"[_.\-]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Segments that mean "secret value" on their own (after lowercasing).
_SECRET_SEG = re.compile(
    r"^(?:\w*(?:pass|passw|passwd|password|passwords|pwd|passphrase)|\w*token|\w*secrets?|"
    r"credential|credentials|apikey|accesskey|privatekey|secretkey|authkey|bearer|sudo)$"
)
_NOT_SECRET = {"bypass", "compass", "surpass", "trespass", "overpass", "underpass", "tokenizer",
               "tokenize", "secretary", "mypass"}
# "key" alone is too common (dict keys), so it needs one of these before it.
_KEY_PREFIX = {"api", "secret", "private", "access", "service", "role", "auth", "encryption", "signing",
               "license", "master", "ssh", "webhook"}
# Identifier-like fields the user asked to mask too (not secrets by themselves).
_ID_PAIRS = {("client", "id"), ("app", "id"), ("public", "key"), ("account", "sid")}
# Plural/measure forms that are counters or limits, not credentials.
_COUNTER_PREV = {"max", "min", "num", "total", "input", "output", "completion", "prompt", "cache",
                 "reasoning", "n"}

# Names that describe a location, size or kind, not the credential itself
# (``token_path``, ``secret_file``, ``api_key_name``, ``token_count``, ``password_policy``).
_NOT_VALUE_LAST = {"path", "file", "filename", "dir", "folder", "name", "label", "type", "env", "var",
                   "header", "field", "prefix", "location", "policy", "mode", "format", "kind",
                   "length", "len", "count", "limit", "usage", "ttl", "expires", "expiry", "required",
                   "enabled", "hint", "manager", "field", "page", "wiki", "docs", "doc"}
_NOT_VALUE_ANY = {"count", "limit", "usage", "ttl", "expires", "expiry", "path", "file"}

_PATH_VALUE = re.compile(r"^(?:\.{0,2}/|~/|[A-Za-z]:\\)[\w./\\ -]+$")

_PLACEHOLDER_START = ("[REDACTED", "${", "$(", "{{", "%(", "<", "***", "xxx", "your_", "your-", "changeme")


def _segments(name: str) -> list[str]:
    parts: list[str] = []
    for chunk in _SPLIT.split(name):
        parts.extend(p.lower() for p in _CAMEL.split(chunk) if p)
    return parts


def classify_field(name: str) -> str | None:
    """Return "SECRET", "IDENTIFIER" or None for a field/variable name."""
    segs = _segments(name)
    if not segs or segs[-1] in _NOT_VALUE_LAST or _NOT_VALUE_ANY.intersection(segs):
        return None
    for i, seg in enumerate(segs):
        if seg in _NOT_SECRET:
            continue
        if _SECRET_SEG.match(seg) and not (i and segs[i - 1] in _COUNTER_PREV and seg == "token"):
            return "SECRET"
        if seg == "key" and i and _KEY_PREFIX.intersection(segs[:i]):
            return "SECRET"
        if i and (segs[i - 1], seg) in _ID_PAIRS:
            return "IDENTIFIER"
        if seg == "email" and len(segs) > 1:  # pass_email, lms_email, apppass_email ...
            return "IDENTIFIER"
    # glued forms: apikey, clientid, appid, publickey
    joined = "".join(segs)
    if joined in ("clientid", "appid", "publickey"):
        return "IDENTIFIER"
    return None


def _plain_url(value: str) -> bool:
    """A public-looking URL (no query, userinfo, fragment, and a short path) is not a secret."""
    if not value.startswith(("http://", "https://")):
        return False
    if any(c in value for c in "?@#"):
        return False
    return value.split("://", 1)[1].count("/") <= 3


def _looks_like_reference(value: str) -> bool:
    low = value.lower()
    return low.startswith(_PLACEHOLDER_START) or bool(_PATH_VALUE.match(value)) or _plain_url(value)


def _sub_assign(m: re.Match) -> str:
    kind = classify_field(m.group("name"))
    value = m.group("value")
    if kind is None or _looks_like_reference(value):
        return m.group(0)
    label = "SECRET_FIELD" if kind == "SECRET" else "ID_FIELD"
    return f"{m.group('name')}{m.group('sep')}[REDACTED]_{label}"


def _sub_flag(m: re.Match) -> str:
    if classify_field(m.group("name").lstrip("-")) != "SECRET" or _looks_like_reference(m.group("value")):
        return m.group(0)
    return f"{m.group('name')}{m.group('sep')}[REDACTED]_SECRET_FIELD"


def mask_credentials(text: str) -> tuple[str, int]:
    """Mask vendor token shapes and credential field VALUES. Returns (text, changes)."""
    changes = 0
    for pattern, label in ((TOKEN_SHAPES, "TOKEN"), (TELEGRAM_TOKEN, "TELEGRAM_TOKEN"),
                           (DISCORD_TOKEN, "DISCORD_TOKEN")):
        text, n = pattern.subn(f"[REDACTED]_{label}", text)
        changes += n
    if ":" in text or "=" in text:
        text, n = _ASSIGN.subn(_sub_assign, text)
        changes += _count_new(n, text)
    if "--" in text:
        text, n = _FLAG.subn(_sub_flag, text)
        changes += _count_new(n, text)
    return text, changes


def _count_new(subn_count: int, text: str) -> int:
    # subn counts every regex match (including unchanged ones); count real masks instead.
    return text.count("[REDACTED]_SECRET_FIELD") + text.count("[REDACTED]_ID_FIELD") if subn_count else 0
