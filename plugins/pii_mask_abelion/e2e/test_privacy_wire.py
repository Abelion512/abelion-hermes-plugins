"""Privacy Guard (pii-mask-abelion): what the model API actually receives from a real Hermes process.

Every assertion reads the requests the loopback provider recorded. Main and auxiliary (title etc.)
requests are judged separately: a request without `tools` is auxiliary.
Synthetic values only. A FAIL here is a real gap, not a skip.
"""
import json
import pytest
from support.loopback_provider import LoopbackProvider
from abelion_e2e_support.host import make_profile, run_hermes, wire_text, requires_hermes

pytestmark = requires_hermes
PLUGIN = [("pii-mask-abelion", "pii_mask_abelion")]
CRED = "sk-proj-SyntheticE2eCanary7Xk29QmZ41AbCdEf"  # synthetic canary, not a real key
PRIVATE = {"username": "private_user_canary_7mQ2", "email": "test.person@example.test", "phone": "+62 800-0000-0000",
           "nik": "9999999900012345", "credential": CRED,
           "home_path": "/home/e2e-user/private-fixture.txt"}
REQUIRED_CONFIG = "security:\n  require_privacy_guard: true\n  privacy_guard_plugin: pii-mask-abelion\n"
PROMPT = ("username: private_user_canary_7mQ2\nlogin as private_user_canary_7mQ2\nemail: test.person@example.test\nHP +62 800-0000-0000\n"
          "NIK 9999999900012345\nOPENAI_API_KEY=" + CRED + "\n"
          "file /home/e2e-user/private-fixture.txt\nsay hi")


def leaked(req):
    s = wire_text(req)
    return sorted(k for k, v in PRIVATE.items() if v in s)


def chat(tmp_path, prompt, replies=None, argv_extra=(), plugins=PLUGIN, extra_config="", cwd=None):
    with LoopbackProvider(replies) as srv:
        home = make_profile(tmp_path, srv.base_url, plugins, extra_config)
        run_hermes(home, ["chat", "-q", prompt, *argv_extra], cwd=cwd)
        return srv


def test_baseline_without_plugin_sends_originals(tmp_path):
    """Control: proves the probe can see a leak at all."""
    srv = chat(tmp_path, PROMPT, plugins=())
    assert srv.main_requests() and set(leaked(srv.main_requests()[0])) == set(PRIVATE)


def test_main_request_has_no_original_private_values(tmp_path):
    srv = chat(tmp_path, PROMPT)
    assert srv.main_requests(), "no main request reached the provider"
    assert leaked(srv.main_requests()[0]) == []


def test_auxiliary_requests_have_no_original_private_values(tmp_path):
    """Auxiliary traffic is guarded only when the matching host required-policy contract is enabled."""
    srv = chat(tmp_path, PROMPT, extra_config=REQUIRED_CONFIG)
    assert srv.aux_requests(), "no auxiliary request observed (title generation)"
    assert [leaked(r) for r in srv.aux_requests()] == [[]] * len(srv.aux_requests())


def test_tool_result_replay_masks_secrets(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text(f"OPENAI_API_KEY={PRIVATE['credential']}\nowner {PRIVATE['email']}\n")
    srv = chat(tmp_path / "run", "read the file and summarize", [{"tool": "read_file", "args": {"path": str(secret)}}, "done"],
               argv_extra=("-t", "file"), cwd=tmp_path)
    mains = srv.main_requests()
    assert len(mains) >= 2, "tool round trip did not happen"
    for r in mains:
        s = wire_text(r)
        assert PRIVATE["credential"] not in s and PRIVATE["email"] not in s


def test_benign_public_text_is_unchanged(tmp_path):
    text = "what is github.com/example-org/example-project and who is Example Maintainer"
    srv = chat(tmp_path, text)
    assert text in wire_text(srv.main_requests()[0]).replace("\\n", "\n")


def test_required_mode_masks_requests_before_provider_egress(tmp_path):
    """With the required-policy core pinned by CI, every observed egress request must be sanitized."""
    srv = chat(tmp_path, PROMPT,
               extra_config="security:\n  require_privacy_guard: true\n  privacy_guard_plugin: pii-mask-abelion\n")
    assert srv.main_requests(), "required mode neither sent a sanitized request nor reported a provider request"
    assert srv.requests, "expected requests at the loopback provider"
    assert [leaked(r) for r in srv.requests] == [[]] * len(srv.requests)



def test_adversarial_mixed_input_forms_are_absent_from_every_provider_request(tmp_path):
    """Exercise the whole host path with varied synthetic values and serializations."""
    opaque = "SyntheticWireCanaryOmegaZ9x7Q5v3"
    json_value = "SyntheticJsonCanaryR8m6N4p2"
    auth_value = "SyntheticHeaderCanaryW4c8K2m6"  # gitleaks:allow (synthetic privacy test canary)
    url_secret = "SyntheticUrlSecretV4n8Q2"  # gitleaks:allow (synthetic privacy test canary)
    prompt = "\n".join([
        f"OPENAI_API_KEY={PRIVATE['credential']}",
        f"api%5Fkey={opaque}",
        f"Authorization: Bearer {auth_value}",
        json.dumps({"name": "HF_TOKEN", "value": json_value, "note": "benign-retained"}),
        f"email {PRIVATE['email']} phone {PRIVATE['phone']} NIK {PRIVATE['nik']}",
        f"database https://synthetic-user:{url_secret}@db.example.test/private",
        f"local file {PRIVATE['home_path']}",
        "public reference https://docs.example.test/guides/api-key-setup",
    ])
    srv = chat(tmp_path, prompt, extra_config=REQUIRED_CONFIG)
    assert srv.requests, "required mode produced no observable provider interaction"
    wire = json.dumps([item["body"] for item in srv.requests], ensure_ascii=False)
    canaries = [
        PRIVATE["credential"], PRIVATE["username"], PRIVATE["email"], PRIVATE["phone"],
        PRIVATE["nik"], PRIVATE["home_path"], opaque, json_value, auth_value, url_secret,
    ]
    assert all(value not in wire for value in canaries), {
        "leaked": [value for value in canaries if value in wire],
        "request_count": len(srv.requests),
    }
    assert "public reference" in wire
    assert "docs.example.test/guides/api-key-setup" in wire


def test_obfuscated_sensitive_label_never_reaches_provider(tmp_path):
    """Invisible-format bypass attempts must be blocked rather than partially rewritten."""
    opaque = "SyntheticUnicodeCanaryY7d3P9"
    prompt = f"api_\u200bkey={opaque}"
    srv = chat(tmp_path, prompt, extra_config=REQUIRED_CONFIG)
    wire = json.dumps([item["body"] for item in srv.requests], ensure_ascii=False)
    assert opaque not in wire


def test_final_model_output_redacts_synthetic_credentials_and_pii(tmp_path):
    secret = "SyntheticOutputCanaryK8m4Q2"
    email = "output.private@example.test"
    reply = f"OPENAI_API_KEY={secret}; contact {email}"
    with LoopbackProvider([reply]) as srv:
        home = make_profile(tmp_path, srv.base_url, PLUGIN, REQUIRED_CONFIG)
        result = run_hermes(home, ["chat", "-q", "return the synthetic sample"], cwd=tmp_path)
    combined = result.stdout + "\n" + result.stderr
    assert result.returncode == 0, combined[-2000:]
    assert srv.main_requests(), "no main request reached the synthetic provider"
    assert secret not in combined
    assert email not in combined
