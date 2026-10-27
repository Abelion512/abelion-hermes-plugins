"""Credential masking: synthetic fixtures only (no real keys), positives AND negatives."""
import copy
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
pii = importlib.import_module("pii_mask_abelion.pii_middleware")
cred = importlib.import_module("pii_mask_abelion._credentials")

MASK = "[REDACTED]"
FAKE = "Zx9fake1234abcd5678"  # synthetic value, matches no vendor shape


def masked(text):
    return pii.mask_content(text)[0]


def test_generic_names_any_case_and_separator():
    for name in ("api_key", "API_KEY", "api-key", "Api-Key", "apiKey", "x-api-key", "apikey",
                 "OPENAI_API_KEY", "NINEROUTER_API_KEY", "HF_TOKEN", "MEM0_API_KEY", "N8N_API_KEY",
                 "HINDSIGHT_API_KEY", "WA_ACCESS_TOKEN", "TELE_TOKEN", "DC_TOKEN", "NPM_TOKEN",
                 "SUDO_PASS", "sudo_password", "LMS_PASSWORD", "lms_pass", "APPPASS_EMAIL",
                 "PASS_EMAIL", "WEBHOOK_SECRET", "client_secret", "clientSecret", "auth_token",
                 "ORACLE_WALLET_PASSWORD", "SUPABASE_SERVICE_ROLE_KEY", "INDODAX_SECRET_KEY",
                 "SOME_NEW_PROVIDER_API_KEY"):
        for line in (f"{name}={FAKE}", f"{name}: {FAKE}", f'"{name}": "{FAKE}"', f"export {name}='{FAKE}'"):
            out = masked(line)
            assert FAKE not in out, line
            assert name in out, line  # field name kept, only the value is masked


def test_identifiers_masked_when_labeled():
    for line in ("client_id=1234-abcdef.apps", "APP_ID=987654321", "public_key=pk_abcdef123456",
                 "lms_email=someone@example.org"):
        assert MASK in masked(line), line


def test_vendor_shapes():
    fixtures = [
        "hf_" + "a" * 34, "AIza" + "b" * 35, "GOCSPX-" + "c" * 24, "ghs_" + "d" * 30,
        "github_pat_" + "e" * 30, "npm_" + "f" * 36, "tvly-" + "g" * 20, "fc-" + "h" * 24,
        "pcsk_" + "i" * 24, "apify_api_" + "j" * 24, "sk-or-v1-" + "k" * 30, "sk-ant-" + "l" * 30,
        "ctx7sk-" + "m" * 20, "m0-" + "n" * 24, "xoxb-" + "1" * 12, "AKIA" + "A" * 16,
        "123456789:" + "T" * 35,
        "M" + "a" * 24 + "." + "b" * 6 + "." + "c" * 27,
        "eyJ" + "h" * 12 + "." + "p" * 12 + "." + "s" * 12,
    ]
    for tok in fixtures:
        out = masked(f"use {tok} now")
        assert tok not in out, tok
        assert "use " in out and " now" in out


def test_url_query_path_and_irregular_syntax():
    assert FAKE not in masked(f"https://example.test/page?api_key={FAKE}&b=1")
    assert masked(f"https://example.test/page?api_key={FAKE}&b=1").endswith("&b=1")
    assert "sk-notion" not in masked("notion.com/apikey?=sk-notion")
    assert "notion.com/apikey?=" in masked("notion.com/apikey?=sk-notion")
    assert FAKE not in masked(f"notion.com/apikey?={FAKE}")
    assert FAKE not in masked(f"curl -H 'X-API-Key: {FAKE}' https://example.test/x")
    assert FAKE not in masked(f"tool --password {FAKE}")


def test_false_positives_stay_intact():
    keep = [
        "https://wiki.example.com/Token_Setup", "https://www.notion.so/help/api-key-guide",
        "see docs at https://docs.example.com/guides/api-keys",
        "secret_key_path=/etc/app/secret.key", "token_file=./tokens/a.json",
        "path: /home/me/.config/token.txt", "api_key_name=my-key-name", "max_tokens=100000",
        "prompt_tokens: 123456", "token_count=1234567", "sort_key=created_at_desc",
        "primary_key=id_column", "password=your_password_here", "token=${TOKEN}",
        "API_KEY=<your-api-key>", "OPENAI_API_KEY=[REDACTED]_SECRET_FIELD", "monkey=banana123",
        "bypass=true_enough", "tokenizer=cl100k_base_x", "author: Someone Else", "key=value_here",
        "api_key_header=Authorization", "password_policy=min_length_12",
        "def f(x):\n    return x + 1  # nothing here",
    ]
    for text in keep:
        assert masked(text) == text, text


def test_transport_covers_every_request_shape():
    call_args = json.dumps({"command": f"export API_KEY={FAKE}", "n": 1})
    req = {
        "model": "gpt-x", "stream": True,
        "system": f"owner password: {FAKE}",
        "instructions": f"HF_TOKEN={FAKE}",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": f"API_KEY={FAKE}"}]}],
        "messages": [
            {"role": "user", "content": f"api-key: {FAKE}"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "terminal", "arguments": call_args}}]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": f"TOKEN={FAKE}"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA1234567890123456"}}]},
        ],
        "tools": [{"type": "function", "function": {"name": "terminal",
                                                    "description": f"example API_KEY={FAKE}"}}],
    }
    snap = copy.deepcopy(req)
    out = pii.pii_middleware(req)["request"]
    assert req == snap  # caller never mutated
    text = json.dumps(out)
    assert FAKE not in json.dumps({k: v for k, v in out.items() if k != "tools"})
    # structure intact
    assert out["model"] == "gpt-x" and out["stream"] is True
    assert out["messages"][1]["tool_calls"][0]["id"] == "c1"
    args = json.loads(out["messages"][1]["tool_calls"][0]["function"]["arguments"])  # still valid JSON
    assert args["n"] == 1 and FAKE not in args["command"] and "API_KEY" in args["command"]
    assert out["messages"][2]["content"][1] == req["messages"][2]["content"][1]  # image untouched
    assert out["tools"] is req["tools"]  # tool schemas are not rewritten
    assert "role" in text


def test_unchanged_request_returns_none():
    assert pii.pii_middleware({"model": "m", "messages": [{"role": "user", "content": "hello"}]}) is None


def test_performance_stays_linear_on_plain_text():
    msg = {"role": "user", "content": ("def foo(x):\n    y = x + 1  # paths /home/u/p/file.py a=b\n" * 40)}
    req = {"model": "m", "messages": [dict(msg) for _ in range(100)]}  # ~300 KB
    t = time.perf_counter()
    for _ in range(3):
        assert pii.pii_middleware(req) is None
    per_call = (time.perf_counter() - t) / 3
    assert per_call < 1.0, per_call  # generous CI bound; local is far lower
