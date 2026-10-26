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
        "token: ghp_abcdefghij12",
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
