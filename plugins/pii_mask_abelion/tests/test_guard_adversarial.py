"""Deterministic adversarial privacy regressions for the required Guard boundary.

All values are synthetic. The generated matrix tests name/case/separator mutations
against the actual pre-egress policy, not just the legacy masking helper.
"""
import json
import random

import pytest

from pii_mask_abelion.guard import Guard, MARKER

CANARY = "SyntheticPrivacyCanaryZ9x7Q5v3"
EMAIL = "privacy.user@example.test"
PHONE = "0812-3456-7890"
NIK = "3174051203990001"
PRIVATE_PATH = "/home/e2e-user/private-fixture.txt"


def request_for(content):
    return {"model": "synthetic-privacy-model", "messages": [{"role": "user", "content": content}]}


def decision_json(result):
    if result.get("allow") is True:
        return json.dumps(result["request"], ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False)


def generated_mutations():
    """Yield a repeatable matrix of casing, separators, encoding, and payload syntax."""
    rng = random.Random(0x2800)
    names = (
        "api_key",
        "openai_api_key",
        "client_secret",
        "provider_token",
        "database_password",
        "thirdparty_api_key",
        "authorization",
        "HF_TOKEN",
    )
    for index in range(256):
        name = rng.choice(names)
        name = "".join(
            ch.upper() if ch.isalpha() and rng.getrandbits(1) else ch.lower()
            for ch in name
        )
        if rng.random() < 0.20:
            name = name.replace("_", "%5F")
        style = rng.randrange(6)
        if style == 0:
            text = f"{name}={CANARY}"
        elif style == 1:
            text = f"{name}: {CANARY}"
        elif style == 2:
            text = f'"{name}": "{CANARY}"'
        elif style == 3:
            text = f"export {name}='{CANARY}'"
        elif style == 4:
            text = f"--{name.replace('_', '-')} {CANARY}"
        else:
            text = f"{name}%3D{CANARY}"
        yield f"mutation-{index:03d}", text


@pytest.mark.parametrize(
    ("case_id", "text"),
    list(generated_mutations()),
    ids=lambda value: value if isinstance(value, str) and value.startswith("mutation-") else None,
)
def test_generated_field_mutations_are_masked_before_egress(case_id, text):
    result = Guard().required_policy(
        "request", request=request_for(text), session_id=case_id
    )
    assert result.get("allow") is True, (case_id, result)
    wire = decision_json(result)
    assert CANARY not in wire, (case_id, text, wire)


@pytest.mark.parametrize(
    "text",
    [
        f"email {EMAIL}",
        f"phone {PHONE}",
        f"NIK {NIK}",
        f"path {PRIVATE_PATH}",
        f"API_KEY={CANARY}\nlogin value {CANARY}",
        f"Authorization: Bearer {CANARY}",
        f"https://synthetic-user:{CANARY}@db.example.test/private",
        "-----BEGIN PRIVATE KEY-----\nSyntheticPrivateKeyMaterialZ9x7Q5v3\n-----END PRIVATE KEY-----",
        json.dumps({"name": "HF_TOKEN", "value": CANARY, "note": "benign-retained"}),
        json.dumps({"nested": json.dumps({"api_key": CANARY})}),
    ],
)
def test_supported_sensitive_shapes_never_appear_in_policy_result(text):
    values = (CANARY, EMAIL, PHONE, NIK, PRIVATE_PATH, "SyntheticPrivateKeyMaterialZ9x7Q5v3")
    result = Guard().required_policy(
        "request", request=request_for(text), session_id="shape-" + str(abs(hash(text)))
    )
    wire = decision_json(result)
    assert all(value not in wire for value in values), (text, result)
    if result.get("allow") is True:
        assert MARKER not in wire


@pytest.mark.parametrize(
    "obfuscated_name",
    [
        "api_\u200bkey",
        "API\u202e_KEY",
        "pass\u2063word",
        "client_se\u200bcret",
        "author\u2066ization",
    ],
)
def test_invisible_unicode_inside_sensitive_assignment_fails_closed(obfuscated_name):
    result = Guard().required_policy(
        "request", request=request_for(f"{obfuscated_name}={CANARY}"), session_id="unicode"
    )
    assert result.get("allow") is False, result
    assert "request" not in result
    assert CANARY not in json.dumps(result, ensure_ascii=False)


def test_invisible_unicode_sensitive_dictionary_key_fails_closed():
    payload = request_for({"api_\u200bkey": CANARY})
    result = Guard().required_policy("request", request=payload, session_id="unicode-key")
    assert result.get("allow") is False, result
    assert CANARY not in json.dumps(result, ensure_ascii=False)


def test_benign_invisible_unicode_without_sensitive_label_is_preserved():
    benign = "A zero-width separator: left\u200bright"
    result = Guard().required_policy(
        "request", request=request_for(benign), session_id="benign-unicode"
    )
    assert result == {"allow": True, "request": request_for(benign)}


def test_structural_auth_material_is_denied_without_echoing_it():
    payload = {
        "model": "synthetic-privacy-model",
        "messages": [{"role": "user", "content": "please summarize this"}],
        "headers": {"Authorization": "Bearer " + CANARY},
    }
    result = Guard().required_policy("request", request=payload, session_id="auth-structure")
    assert result.get("allow") is False, result
    assert "request" not in result
    assert CANARY not in json.dumps(result, ensure_ascii=False)


def test_benign_docs_and_public_urls_remain_unchanged():
    benign = (
        "See https://docs.example.test/guides/api-key-setup. "
        "max_tokens=4096 token_count=1200; this is documentation, not a credential."
    )
    result = Guard().required_policy(
        "request", request=request_for(benign), session_id="benign-docs"
    )
    assert result == {"allow": True, "request": request_for(benign)}
