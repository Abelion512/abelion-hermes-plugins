#!/usr/bin/env python3
"""Finding #001: Output redaction falls back to [GUARD_WITHHELD] when native agent.redact is unavailable.

When the native Hermes `agent.redact` module is not importable, `Guard.output()`
returns `[GUARD_WITHHELD]` for ALL outputs (including valid PII tokens that would
normally be restored for the CLI platform). No data leak — output is over-redacted.

Reproduce:
  python3 audits/06580f9.../hermes-audit/repros/finding001_repro.py
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from pii_mask_abelion.guard import Guard, MARKER

g = Guard()
s = g.session("repro-findings001")
token = g.remember(s, "CANARY@example.invalid", "PII")

# Check if agent.redact is available
try:
    import agent.redact  # noqa: F401
    native_available = True
except ImportError:
    native_available = False

out = g.output(token, session_id="repro-findings001", platform="cli")

print(f"agent.redact available: {native_available}")
print(f"Token: {token}")
print(f"Output: {out!r}")

if not native_available:
    # Expected actual behavior: ImportError path → MARKER
    assert out == MARKER, f"Expected MARKER, got {out!r}"
    print("PASS: Output is [GUARD_WITHHELD] (redactor_unavailable path)")
    print("NOTE: CLI PII restoration is BLOCKED because redact_output returns")
    print("      [OUTPUT_WITHHELD:redactor_unavailable] which output() treats as")
    print("      [OUTPUT_WITHHELD:...] → returns MARKER before CLI restore.")
else:
    # If native redactor IS available: PII should be restored for CLI
    assert out == "CANARY@example.invalid", f"Expected PII restored, got {out!r}"
    print("PASS: PII restored for CLI (native redactor available)")
