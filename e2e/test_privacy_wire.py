"""Privacy Guard (pii-mask-abelion): what the model API actually receives from a real Hermes process.

Every assertion reads the requests the loopback provider recorded. Main and auxiliary (title etc.)
requests are judged separately: a request without `tools` is auxiliary.
Synthetic values only. A FAIL here is a real gap, not a skip.
"""
import pytest
from support.fake_provider import FakeProvider
from support.host import make_profile, run_hermes, wire_text, requires_hermes

pytestmark = requires_hermes
PLUGIN = [("pii-mask-abelion", "pii_mask_abelion")]
CRED = "sk-proj-" + "SyntheticE2eCanary" + "7Xk29QmZ41AbCdEf"  # split so secret scanners ignore the synthetic canary
PRIVATE = {"username": "abelion", "email": "bob.santoso@example.com", "phone": "+62 812-3456-7890",
           "nik": "3175091201900001", "credential": CRED,
           "home_path": "/home/abelion/Documents/rahasia.txt"}
PROMPT = ("username: abelion\nlogin as abelion\nemail: bob.santoso@example.com\nHP +62 812-3456-7890\n"
          "NIK 3175091201900001\nOPENAI_API_KEY=" + CRED + "\n"
          "file /home/abelion/Documents/rahasia.txt\nsay hi")


def leaked(req):
    s = wire_text(req)
    return sorted(k for k, v in PRIVATE.items() if v in s)


def chat(tmp_path, prompt, replies=None, argv_extra=(), plugins=PLUGIN, extra_config="", cwd=None):
    with FakeProvider(replies) as srv:
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
    srv = chat(tmp_path, PROMPT)
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
    text = "what is github.com/Abelion512/abelion-hermes-plugins and who is Abelion"
    srv = chat(tmp_path, text)
    assert text in wire_text(srv.main_requests()[0]).replace("\\n", "\n")


def test_required_mode_on_unsupported_host_sends_nothing(tmp_path):
    """security.require_privacy_guard needs a Hermes with the required-policy contract. A host without it
    must stop before any provider request."""
    srv = chat(tmp_path, PROMPT, extra_config="security:\n  require_privacy_guard: true\n  privacy_guard_plugin: pii-mask-abelion\n")
    assert srv.requests == []
