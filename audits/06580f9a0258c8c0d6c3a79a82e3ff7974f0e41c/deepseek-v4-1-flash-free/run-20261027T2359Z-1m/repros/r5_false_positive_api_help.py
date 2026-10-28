#!/usr/bin/env python3
"""R5: policy over-masking of 'help/message/hash' suffixes after a credential word.

Expectation basis: none of these suffixes are in the documented _NOT_VALUE_LAST list,
so the source is free to classify them as sensitive. Recorded as a POLICY difference,
not a source bug: the value is masked (fail-closed) but utility is lost.
Actual: password_help -> None, apikey_help -> SECRET (same human meaning).
"""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion._credentials import classify_field

for name in ("password_help", "apikey_help", "api_key_help", "secret_menu",
             "password_message", "password_hash", "token_hash"):
    print(f"{name:20s} actual={classify_field(name)}")
