"""Large-amount masking variant: "2.8 triliun" (Indonesian trillion).

Behavior verified against the current configured patterns — recorded as a
variant test, not as a proposed new policy:

- Prose amounts in everyday separator forms (``Rp2,8 triliun``,
  ``Rp 2.800.000.000.000``) are benign text and stay unchanged.
- A bare 16+-digit numeric run is masked by the stateless mask helper
  (``[REDACTED]_LONG_NUMBER``) and by the active session Guard's placeholder
  on the outgoing request wire. The caller's request is never mutated.
"""

import json

import pytest

from pii_mask_abelion.pii_middleware import mask_content, pii_middleware
from pii_mask_abelion.guard import Guard

# 2.8 triliun written without separators becomes a long numeric run that the
# 16-19 digit LONG_NUMBER/NUMBER detectors treat as PII. Synthetic value, not
# a real budget figure.
TRILLIUN_DIGITS = "2800000000000000"  # gitleaks:allow (synthetic masking variant)

BENIGN_AMOUNT_TEXTS = [
    "Anggaran Rp2,8 triliun telah dipakai.",
    "Anggaran Rp 2.800.000.000.000 telah dipakai.",
    "Amount Rp2.8 triliun spent.",
]

NUMERIC_RUN_TEXTS = [
    TRILLIUN_DIGITS,
    f"Anggaran {TRILLIUN_DIGITS} rupiah",
]


@pytest.mark.parametrize("text", BENIGN_AMOUNT_TEXTS)
def test_benign_2_8_trilliun_amounts_stay_unchanged(text):
    masked, count = mask_content(text)
    assert count == 0
    assert masked == text

    request = {"messages": [{"role": "user", "content": text}]}
    assert pii_middleware(request) is None
    assert request["messages"][0]["content"] == text


@pytest.mark.parametrize("text", NUMERIC_RUN_TEXTS)
def test_numeric_2_8_trilliun_run_masked_by_stateless_helper(text):
    masked, count = mask_content(text)
    assert count > 0
    assert TRILLIUN_DIGITS not in masked
    assert "[REDACTED]_LONG_NUMBER" in masked


@pytest.mark.parametrize("text", NUMERIC_RUN_TEXTS)
def test_numeric_2_8_trilliun_run_masked_in_middleware_request(text):
    request = {"model": "synthetic", "messages": [{"role": "user", "content": text}]}
    result = pii_middleware(request)
    assert result is not None
    assert TRILLIUN_DIGITS not in json.dumps(result["request"], ensure_ascii=False)
    assert request["model"] == "synthetic"
    assert request["messages"][0]["content"] == text
    assert "[REDACTED]_LONG_NUMBER" in json.dumps(result["request"], ensure_ascii=False)


@pytest.mark.parametrize("text", NUMERIC_RUN_TEXTS)
def test_numeric_2_8_trilliun_run_masked_on_active_guard_wire(text):
    result = Guard().required_policy(
        "request",
        request={"model": "synthetic", "messages": [{"role": "user", "content": text}]},
        session_id="trilliun-variant",
    )
    assert result["allow"] is True
    wire = json.dumps(result["request"], ensure_ascii=False)
    assert TRILLIUN_DIGITS not in wire
    assert "<HG:" in wire
