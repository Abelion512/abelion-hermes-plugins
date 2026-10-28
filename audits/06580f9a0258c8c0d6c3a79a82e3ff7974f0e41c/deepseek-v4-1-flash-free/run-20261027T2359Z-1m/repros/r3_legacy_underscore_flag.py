#!/usr/bin/env python3
"""R3: legacy pii_middleware.mask_credentials misses --snake_case flag values.

Expectation basis: _credentials.py docstring says field names are normalised over
case and `_`/`-`/`.`, and only the value is masked. `--api_key VALUE` is that shape.
Actual: `--api-key VALUE` is masked, `--api_key VALUE` is forwarded unchanged.
Note: pii_middleware is NOT registered by __init__.register(); impact is limited to
direct users of scan_message/mask_credentials.
"""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion._credentials import mask_credentials

CANARY = "SyntheticCanaryFlagZ3x7C1v5"
for text in (f"--api-key {CANARY}", f"--api_key {CANARY}", f"--client_secret {CANARY}"):
    out, changes = mask_credentials(text)
    print(f"expected=masked actual=forwarded={CANARY in out and out == text} verbatim={out!r}")

# second gap in the same function: colon+space values with more than one word are
# classified as "prose annotation" by _looks_like_code and skipped.
for text in (f"api_key: {CANARY}", f"api_key: {CANARY} tail"):
    out, _ = mask_credentials(text)
    print(f"colon expected=masked actual=forwarded={CANARY in out} verbatim={out!r}")
