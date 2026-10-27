import copy
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pii = importlib.import_module("pii_mask_abelion.pii_middleware")
out = importlib.import_module("output_redact_abelion.output_redact")


def test_secrets_still_masked():
    for text in (
        "key sk-abcdef1234",
        "API_KEY=abc123def",
        "token: " + "ghp_" + "abcdefghij12",
        "postgres://u:p@h/db",
        "order 1234567890123456",  # LONG_NUMBER protection is kept
        "admin (username) / hunter2 (password nya)",
    ):
        masked, n = pii.mask_content(text)
        assert n > 0 and masked != text, text


def test_plain_text_untouched():
    text = "def f(x): return x + 1  # nothing sensitive (really)"
    assert pii.mask_content(text) == (text, 0)
    assert pii.classify_content(text) == pii.PUBLIC


def test_paren_label_prefilter_matches_full_pattern():
    from pii_mask_abelion._patterns import PAREN_CRED_RE, PAREN_LABEL_RE

    for label in ("app email", "pass email", "client id", "api key", "auth", "auth token",
                  "webhook secret", "sudo password", "password nya", "pw", "secrets",
                  "credentials", "token", "apikey", "email", "user name", "user", "apppass"):
        text = f"value one two ({label})"
        assert PAREN_CRED_RE.search(text), label
        assert PAREN_LABEL_RE.search(text), label


def test_request_not_mutated_and_untouched_messages_shared():
    req = {
        "model": "m",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "user", "content": [{"type": "text", "text": "key sk-abcdef1234"}, {"type": "image"}]},
        ],
    }
    snap = copy.deepcopy(req)
    res = pii.pii_middleware(req)
    assert req == snap
    new = res["request"]
    assert "sk-abcdef1234" not in str(new)
    assert new["messages"][0] is req["messages"][0]
    assert new["messages"][1]["content"][1] == {"type": "image"}


def test_no_change_returns_none():
    assert pii.pii_middleware({"messages": [{"role": "user", "content": "hi"}]}) is None


def test_output_redact_paren_and_plain():
    assert "hunter2" not in out.redact_output("admin (username) / hunter2 (password nya)")
    assert out.redact_output("just a normal answer (see above)") is None


# ── Equivalence against an unfiltered reference (the pre-filter must never change results) ──

import random


def _ref_mask(text):
    """Reference: every pattern applied with no pre-filter (the old behavior)."""
    n = 0
    for pattern, label in pii.SECRET_PATTERNS:
        text, c = pattern.subn(lambda m, label=label: f"[REDACTED]_{label}", text)
        n += c
    return text, n


_LABELS = ["app email", "app_pass", "apppassword", "pass email", "pass-email", "client id",
           "client_secret", "api key", "api_secret", "apikey", "auth", "auth token", "auth_key",
           "webhook secret", "sudo password", "password nya", "password", "pass", "pw", "secret",
           "secrets", "credential", "credentials", "token", "email", "user name", "username",
           "user", "apppass", "AUTH", "Password", "TOKEN", "pwd", "users", "authx"]
_FRAGS = ["hello", "a b c d e f g h", "sk-abcdef1234", "API_KEY=abc123def", "1234567890123456",
          "email: bob@x.com", "Bearer abcdefghijklmnop", "postgres://u:p@h/db", "\n", "\r\n",
          "\t", "é", "日本語", "😀", "(", ")", "()", "f(a,b)", "\x00", "a" * 50,
          "admin (username) / x (password nya)"]


def test_label_matrix_matches_reference():
    for label in _LABELS:
        for pre in ("", "word ", "a b c d e f g h ", "x\n"):
            for post in (")", ") tail", "", "  )"):
                for text in (f"{pre}({label}{post}", f"{pre}( {label} {post}"):
                    assert pii.mask_content(text) == _ref_mask(text), text


def test_random_inputs_match_reference():
    rng = random.Random(11)
    alpha = "()  \n\tabcdefghijklmnopqrstuvwxyz_-ASEKT:=0123456789@/."
    for _ in range(3000):
        t = "".join(rng.choice(alpha) for _ in range(rng.randint(0, 80)))
        assert pii.mask_content(t) == _ref_mask(t), t
    for _ in range(1500):
        parts = []
        for _ in range(rng.randint(1, 14)):
            if rng.random() < 0.3:
                parts.append("(" + rng.choice(_LABELS) + rng.choice(["", ")", " )"]))
            else:
                parts.append(rng.choice(_FRAGS))
        t = rng.choice([" ", "", "\n"]).join(parts)
        assert pii.mask_content(t) == _ref_mask(t), t


def test_long_text_and_malformed_content():
    text = " ".join(["word (not a label)"] * 5000 + ["key sk-abcdef1234"])
    masked, n = pii.mask_content(text)
    assert n == 1 and "sk-abcdef1234" not in masked
    req = {"messages": [{"role": "user", "content": [{"type": "text"}, "stray", {"text": "x"}]},
                        {"role": "assistant", "content": None, "tool_calls": []}]}
    assert pii.pii_middleware(req) is None


def test_malformed_part_is_skipped_but_valid_parts_still_masked():
    req = {"messages": [{"role": "user", "content": [
        "stray", {"type": "text", "text": "key sk-abcdef1234"}]}]}
    res = pii.pii_middleware(req)
    assert "sk-abcdef1234" not in str(res["request"])
    assert req["messages"][0]["content"][1]["text"] == "key sk-abcdef1234"  # caller untouched


def test_shared_objects_are_only_the_unchanged_ones():
    # Hermes deep-copies the request before and after middleware, so sharing unchanged
    # objects is safe there; this pins which objects are shared vs fresh.
    keep = {"role": "user", "content": "hello"}
    req = {"messages": [keep, {"role": "user", "content": "key sk-abcdef1234"}], "tools": [{"a": 1}]}
    new = pii.pii_middleware(req)["request"]
    assert new["messages"][0] is keep and new["tools"] is req["tools"]
    assert new["messages"][1] is not req["messages"][1]
