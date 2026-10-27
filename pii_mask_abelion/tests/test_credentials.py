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
    assert FAKE not in text  # including the tool schema description
    # structure intact
    assert out["model"] == "gpt-x" and out["stream"] is True
    assert out["messages"][1]["tool_calls"][0]["id"] == "c1"
    args = json.loads(out["messages"][1]["tool_calls"][0]["function"]["arguments"])  # still valid JSON
    assert args["n"] == 1 and FAKE not in args["command"] and "API_KEY" in args["command"]
    assert out["messages"][2]["content"][1] == req["messages"][2]["content"][1]  # image untouched
    assert out["tools"][0]["function"]["name"] == "terminal"  # schema structure intact
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


def test_tool_schema_defaults_examples_and_schema_style_keys():
    tool = {"type": "function", "function": {"name": "login", "parameters": {
        "type": "object", "required": ["api_key"],
        "properties": {
            "api_key": {"type": "string", "description": "the key", "default": FAKE, "examples": [FAKE]},
            "password": "string", "token": {"type": "string"}, "source": {"type": "string"}}}}}
    out = pii.pii_middleware({"model": "m", "tools": [tool]})["request"]["tools"][0]
    props = out["function"]["parameters"]["properties"]
    assert FAKE not in json.dumps(out)
    assert props["password"] == "string" and props["token"] == {"type": "string"}  # no corruption
    assert out["function"]["parameters"]["required"] == ["api_key"]
    assert tool["function"]["parameters"]["properties"]["api_key"]["default"] == FAKE  # input untouched


def test_headers_extra_keys_and_name_value_pairs():
    req = {"model": "m", "messages": [], "extra_headers": {"x-api-key": FAKE, "Authorization": f"Basic {FAKE}",
                                                          "Content-Type": "application/json"},
           "extra_body": {"client_secret": FAKE, "client_id": "id-123456", "temperature": 0.2,
                          "env": [{"name": "HF_TOKEN", "value": FAKE}, {"name": "LOG_LEVEL", "value": "debug-mode"}]}}
    out = pii.pii_middleware(req)["request"]
    assert FAKE not in json.dumps(out)
    assert out["extra_headers"]["Authorization"].startswith("Basic ")
    assert out["extra_headers"]["Content-Type"] == "application/json"
    assert out["extra_body"]["temperature"] == 0.2
    assert out["extra_body"]["env"][1] == {"name": "LOG_LEVEL", "value": "debug-mode"}
    assert out["extra_body"]["env"][0]["name"] == "HF_TOKEN"


def test_multiline_private_key_and_wallet_context():
    begin, end = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"  # built at runtime: keeps scanners quiet
    pem = begin + "\n" + "\n".join(["Zx9fakeBody" + str(i) * 20 for i in range(4)]) + "\n" + end
    out = masked(f"key file:\n{pem}\nafter")
    assert "Zx9fakeBody" not in out and out.startswith("key file:") and out.endswith("after")
    assert "Zx9fakeBody" not in masked(begin + "\nZx9fakeBody1111111111")  # truncated block
    assert FAKE not in masked(f"ORACLE_WALLET_PASSWORD={FAKE}")
    assert FAKE not in masked(f"wallet_password: {FAKE}\nOCI_AUTH_TOKEN = {FAKE}")


def test_url_encoded_and_json_valid_arguments():
    assert FAKE not in masked(f"https://example.test/cb?x=1&api_key%3D{FAKE}")
    args = json.dumps({"url": f"https://example.test/a?token={FAKE}", "body": 'say "hi"\nline2', "n": [1, 2]})
    req = {"messages": [{"role": "assistant", "tool_calls": [{"id": "c", "type": "function",
                                                              "function": {"name": "f", "arguments": args}}]}]}
    out = pii.pii_middleware(req)["request"]
    parsed = json.loads(out["messages"][0]["tool_calls"][0]["function"]["arguments"])
    assert FAKE not in json.dumps(parsed) and parsed["body"] == 'say "hi"\nline2' and parsed["n"] == [1, 2]
    assert parsed["url"].startswith("https://example.test/a?token=")


def test_binary_payload_untouched():
    blob = "A" * 300
    req = {"messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": blob}},
        {"type": "text", "text": f"password: {FAKE}"}]}]}
    out = pii.pii_middleware(req)["request"]
    assert out["messages"][0]["content"][0]["source"]["data"] == blob
    assert FAKE not in json.dumps(out)


def test_pathological_inputs_do_not_blow_up():
    cases = ["a" * 200000, "api_key=" + "x" * 200000, "-----BEGIN " + "PRIVATE KEY-----" + "y" * 200000,
             "k=" * 100000, ":" * 200000, ("token " * 50000), "%3D" * 100000, "_-." * 60000 + "=v" * 5]
    for text in cases:
        t = time.perf_counter()
        masked(text)
        assert time.perf_counter() - t < 2.0, text[:20]


def test_clear_credential_fields_mask_short_and_spaced_values():
    for text in ("sudo_pass: abc", "SUDO_PASS=x1", "password=12", "lms_pass = 'a b'", 'x-api-key: z',
                 '{"password": "ab c d"}', "export DB_PASSWORD='two words here'", 'tool --password "my pass phrase" go',
                 "password: my secret phrase here", "- password: two words", "Lms_Pass = ke ke 12"):
        out = masked(text)
        assert MASK in out, text
        for leak in ("abc", "x1", "12", "a b", "ab c d", "two words", "my pass phrase", "secret phrase", "ke ke"):
            assert leak not in out.replace("[REDACTED]_SECRET_FIELD", ""), (text, out)
    out = masked('tool --password "my pass phrase" go')
    assert out.endswith(' go') and out.startswith('tool --password "')
    req = {"headers": {"x-api-key": "z"}, "env": {"SUDO_PASS": "ab"}, "messages": [
        {"role": "assistant", "tool_calls": [{"id": "c", "type": "function", "function": {
            "name": "f", "arguments": json.dumps({"password": "a b", "note": "hi"})}}]}]}
    out = pii.pii_middleware(req)["request"]
    assert out["headers"]["x-api-key"] != "z" and out["env"]["SUDO_PASS"] != "ab"
    a = json.loads(out["messages"][0]["tool_calls"][0]["function"]["arguments"])
    assert a["password"] != "a b" and a["note"] == "hi"


def test_urlencoded_names_and_ordinary_urls():
    assert FAKE not in masked(f"https://example.test/cb?api%5Fkey={FAKE}&b=1")
    assert FAKE not in masked(f"https://example.test/cb?api%255Fkey={FAKE}&b=1")  # double encoded
    assert masked(f"https://example.test/cb?api%5Fkey={FAKE}&b=1").endswith("&b=1")
    for ok in ("https://example.test/a%2Fb%255Fc?x=1&q=hello%20world", "https://example.test/search?q=api%5Fkey"):
        assert masked(ok) == ok


def test_source_code_is_not_corrupted():
    for line in ("api_key: str | None = None,", "worker_api_key = self.api_key", "api_key=api_key,",
                 "token = uuid.uuid4().hex", "token = get_token()", "self._token_queue: deque = deque()",
                 "pass_session_id: bool = False,", "set_sudo_password_callback = shim('a', 'b')",
                 "_TOKEN_QUERY = 0x0008", "sudo_user = os.environ.get('SUDO_USER')",
                 "if sudo_user == 'root':", "def f(token: Token) -> None:", "_PER_PASS = 1000, 500, 4",
                 "agent.api_key = effective_key", "client(api_key=token, base_url=u)"):
        assert masked(line) == line, line


def test_nested_label_before_credential_is_not_swallowed():
    for text in (f"out: password: {FAKE}", f"result: token = {FAKE}", f"line1 a: b: api_key={FAKE}"):
        assert FAKE not in masked(text), text


def test_failure_modes_are_loud_and_never_pass_raw_values(monkeypatch, caplog):
    # a string that makes the masker fail is replaced, not forwarded
    def boom(text):
        raise RuntimeError("x")
    monkeypatch.setattr(pii, "mask_content", boom)
    out = pii.pii_middleware({"messages": [{"role": "user", "content": f"password: {FAKE}"}]})["request"]
    assert FAKE not in json.dumps(out) and "MASK_ERROR" in json.dumps(out)
    monkeypatch.undo()
    # cyclic subtree: replaced with a marker, the rest of the request is still masked
    cyc = {"a": 1}
    cyc["self"] = cyc
    out = pii.pii_middleware({"messages": [{"role": "user", "content": f"api_key: {FAKE}"}], "extra": cyc})["request"]
    assert FAKE not in json.dumps(out) and "UNSUPPORTED_STRUCTURE" in json.dumps(out)
    assert pii.pii_middleware("not a dict") is None and pii.pii_middleware({}) is None


def test_tuples_are_walked():
    out = pii.pii_middleware({"messages": ({"role": "user", "content": f"api_key: {FAKE}"},)})["request"]
    assert isinstance(out["messages"], tuple) and FAKE not in json.dumps(out)


def _nest(levels):
    deep = {"leaf": f"password: {FAKE}", "n": 1}
    for _ in range(levels):
        deep = {"x": deep}
    return deep


def test_deep_nesting_is_masked_not_skipped():
    out = pii.pii_middleware({"messages": [], "extra_body": _nest(300)})["request"]  # beyond the walk depth
    node = out["extra_body"]
    while "leaf" not in node:
        node = node["x"]
    assert node["n"] == 1 and "[REDACTED]" in node["leaf"] and FAKE not in node["leaf"]


def test_unserialisable_depth_is_replaced_not_forwarded():
    out = pii.pii_middleware({"messages": [], "extra_body": _nest(5000)})["request"]
    node = out["extra_body"]
    for _ in range(100):
        if not isinstance(node, dict):
            break
        node = node["x"]
    assert node == "[REDACTED]_UNSUPPORTED_STRUCTURE"


def test_walk_failure_falls_back_to_round_trip(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("walk")
    monkeypatch.setattr(pii, "_mask_obj", boom)
    out = pii.pii_middleware({"messages": [{"role": "user", "content": f"api_key: {FAKE}"}]})["request"]
    assert FAKE not in json.dumps(out) and out["messages"][0]["role"] == "user"
