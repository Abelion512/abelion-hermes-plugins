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
from urllib.parse import unquote

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
_NAME = r"[A-Za-z](?:[A-Za-z0-9_.\-]|%(?:25)?(?:5[Ff]|2[DdEe])){1,63}"  # %5F / %2D / %2E: URL-encoded _ - .
_VALUE = (r"(?:\"[^\"\n]{1,512}\"|'[^'\n]{1,512}'"  # quoted scalar: whole, spaces included
          r"|[^\s\"',;&<>{}\[\]()/$=][^\s\"',;&<>{}\[\]()]*)")
_ASSIGN = re.compile(
    rf"(?P<name>{_NAME})"
    r"(?P<sep>[\"']?\??[ \t]*(?:[:=]|%3[DdAa])[ \t]*)"
    rf"(?P<value>{_VALUE})"
)
# Line-start "NAME: several words" / "NAME=several words" (.env, YAML, prose notes): whole rest of the line.
_LINE = re.compile(
    rf"(?m)^(?P<name>[ \t]*(?:export[ \t]+|-[ \t]+)?(?P<n>{_NAME})[ \t]*[:=][ \t]*)(?P<value>[^\n\"']{{1,200}})$"
)
# CLI flags: --password hunter2, --api-key=abc, --password "my pass phrase".
_FLAG = re.compile(
    rf"(?P<name>--[A-Za-z][A-Za-z0-9\-]{{1,40}})(?P<sep>[ =])(?P<value>\"[^\"\n]{{1,512}}\"|'[^'\n]{{1,512}}'"
    r"|[^\s\"',;&<>{}\[\]()-][^\s\"',;&<>{}\[\]()]*)"
)

_SPLIT = re.compile(r"[_.\-]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Segments that mean "secret value" on their own (after lowercasing).
_SECRET_SEG = re.compile(
    r"^(?:\w*(?:pass|passw|passwd|password|passwords|pwd|passphrase)|\w*token|\w*secrets?|"
    r"credential|credentials|apikey|accesskey|privatekey|secretkey|authkey|bearer)$"
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

# Words that may follow the secret segment and still name the secret itself (secret_key, token_value, ...).
_TAIL_OK = {"key", "value", "val", "str", "string", "text", "hex", "raw", "plain", "v1", "v2", "primary", "secondary"}
_CODE_WORDS = {"none", "str", "bool", "int", "float", "dict", "list", "bytes", "any", "optional", "callable",
               "self", "cls", "true", "false", "null", "undefined", "nil"}
_SNAKE = re.compile(r"^_*[a-z]+(?:_[a-z]+)+_*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_PASS_FAMILY = re.compile(r"(?:pass|passw|passwd|password|passwords|pwd|passphrase)$")
_PATH_VALUE = re.compile(r"^(?:\.{0,2}/|~/|[A-Za-z]:\\)[\w./\\ -]+$")

_TYPE_WORDS = frozenset({"string", "number", "integer", "boolean", "object", "array", "null", "none", "true",
                         "false", "secret", "required", "yes", "no", "on", "off", "n/a", "unset", "empty", "optional", "str", "bool", "int"})
_PEM = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)")
_PLACEHOLDER_START = ("[REDACTED", "${", "$(", "{{", "%(", "<", "***", "xxx", "your_", "your-", "changeme")


def _segments(name: str) -> list[str]:
    parts: list[str] = []
    for chunk in _SPLIT.split(name):
        parts.extend(p.lower() for p in _CAMEL.split(chunk) if p)
    return parts


def classify_field(name: str) -> str | None:
    """Return "SECRET", "IDENTIFIER" or None for a field/variable name."""
    # Case-insensitive delimited field vocabulary before camel-case expansion.
    literal = [p.lower() for p in _SPLIT.split(name) if p]
    if literal and literal[-1] not in _NOT_VALUE_LAST and not _NOT_VALUE_ANY.intersection(literal):
        if any(a == "api" and b == "key" for a,b in zip(literal,literal[1:])):
            return "SECRET"
    segs = _segments(name)
    if not segs or segs[-1] in _NOT_VALUE_LAST or _NOT_VALUE_ANY.intersection(segs):
        return None
    for i, seg in enumerate(segs):
        if seg in _NOT_SECRET:
            continue
        if (_SECRET_SEG.match(seg) and not (i and segs[i - 1] in _COUNTER_PREV and seg == "token")
                and not (i and segs[i - 1] == "per")
                and all(t in _TAIL_OK or t.isdigit() for t in segs[i + 1:])):
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
    return low in _TYPE_WORDS or low.startswith(_PLACEHOLDER_START) or bool(_PATH_VALUE.match(value)) or _plain_url(value)


def _label(kind: str) -> str:
    return "[REDACTED]_SECRET_FIELD" if kind == "SECRET" else "[REDACTED]_ID_FIELD"


def _mask_scalar(name: str, value: str) -> str | None:
    """Replacement for a credential field's value (quotes kept), or None to leave it alone."""
    kind = classify_field(unquote(unquote(name)))
    if kind is None:
        return None
    quote = value[0] if value[0] in "\"'" else ""
    inner = value[1:-1] if quote else value
    if not inner or _looks_like_reference(inner) or inner.startswith("[REDACTED"):
        return None
    if kind != "SECRET" and len(inner) < 4:
        return None
    return f"{quote}{_label(kind)}{quote}"


def _looks_like_code(m: re.Match) -> bool:
    """Unquoted values that are code, not data: ``x = self.key``, ``token = get()``, ``key: str | None``."""
    value = m.group("value")
    if value[0] in "\"'":
        return False
    nxt = m.string[m.end():m.end() + 2]
    value = value.rstrip("`*.…,")  # prose punctuation hugging the value
    if not value or value[0] == "…":
        return True
    low = value.lower()
    if low == m.group("name").lower().split("%")[0] or low in _CODE_WORDS or _DOTTED.match(value):
        return True
    if value[:1] == "=" or nxt[:1] in ("(", ")", "[") or value in ("0", "1"):
        return True
    if nxt[:1] and nxt[:1] in ",}" and _IDENT.match(value) and not any(c.isdigit() for c in value):
        return True  # {"access_token": token}, f(api_key=token)
    if _SNAKE.match(value):  # my_var_name: a variable reference, not a value
        return True
    if "=" in m.group("sep") and m.group("sep")[:1] == " " and _IDENT.match(value) and not any(c.isdigit() for c in value):
        return True  # ``api_key = label``: spaced assignment of a plain word is code
    if ":" in m.group("sep") and nxt[:1] == " " and nxt[1:2].isalpha():  # prose / annotation: "token: foo bar"
        return True
    return False


def _sub_assign(m: re.Match) -> str:
    if _looks_like_code(m):
        return m.group(0)
    new = _mask_scalar(m.group("name"), m.group("value"))
    return m.group(0) if new is None else f"{m.group('name')}{m.group('sep')}{new}"


def _sub_line(m: re.Match) -> str:
    value = m.group("value").rstrip()
    if not _PASS_FAMILY.search(unquote(m.group("n")).lower()) or " " not in value.strip():  # single token: _ASSIGN already decided
        return m.group(0)
    new = _mask_scalar(m.group("n"), value.strip())
    return m.group(0) if new is None else f"{m.group('name')}{new}"


def _sub_flag(m: re.Match) -> str:
    if classify_field(m.group("name").lstrip("-")) != "SECRET":
        return m.group(0)
    new = _mask_scalar(m.group("name").lstrip("-"), m.group("value"))
    return m.group(0) if new is None else f"{m.group('name')}{m.group('sep')}{new}"


def _scan_assign(text: str) -> str:
    """Like ``_ASSIGN.sub`` but a rejected match does not swallow its value: ``out: password: x`` still
    reaches the inner ``password: x`` (non-overlapping matching would skip it)."""
    out: list[str] = []
    pos = last = 0
    while True:
        m = _ASSIGN.search(text, pos)
        if m is None:
            break
        new = _sub_assign(m)
        if new == m.group(0):
            pos = max(m.start("value"), m.start() + 1)
            continue
        out.append(text[last:m.start()])
        out.append(new)
        pos = last = m.end()
    out.append(text[last:])
    return "".join(out)


def mask_credentials(text: str) -> tuple[str, int]:
    """Mask vendor token shapes and credential field VALUES. Returns (text, changes)."""
    changes = 0
    for pattern, label in ((TOKEN_SHAPES, "TOKEN"), (TELEGRAM_TOKEN, "TELEGRAM_TOKEN"),
                           (DISCORD_TOKEN, "DISCORD_TOKEN")):
        text, n = pattern.subn(f"[REDACTED]_{label}", text)
        changes += n
    if "-----BEGIN" in text:
        text, n = _PEM.subn("[REDACTED]_PRIVATE_KEY", text)
        changes += n
    if ":" in text or "=" in text or "%3" in text:
        text, n = _LINE.subn(_sub_line, text)  # multi-word line values first
        changes += _count_new(n, text)
        text = _scan_assign(text)
        changes += _count_new(1, text)
    if "--" in text:
        text, n = _FLAG.subn(_sub_flag, text)
        changes += _count_new(n, text)
    return text, changes


def _count_new(subn_count: int, text: str) -> int:
    # subn counts every regex match (including unchanged ones); count real masks instead.
    return text.count("[REDACTED]_SECRET_FIELD") + text.count("[REDACTED]_ID_FIELD") if subn_count else 0


_AUTH_KEYS = frozenset({"authorization", "proxy-authorization"})


def mask_value_for_key(key: str, value: str) -> tuple[str, int]:
    """Structured data: the field name is a separate dict key, so decide by key. (value, changes)."""
    if not value or _looks_like_reference(value):
        return value, 0
    low = key.lower()
    if low in _AUTH_KEYS:
        scheme, _, rest = value.partition(" ")
        if rest and not rest.startswith("[REDACTED"):
            return f"{scheme} [REDACTED]_SECRET_FIELD", 1
        return (value, 0) if rest else ("[REDACTED]_SECRET_FIELD", 1)
    kind = classify_field(key)
    if kind is None:
        return value, 0
    return ("[REDACTED]_SECRET_FIELD" if kind == "SECRET" else "[REDACTED]_ID_FIELD"), 1
