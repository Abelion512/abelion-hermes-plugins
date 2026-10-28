#!/usr/bin/env python3
"""R7: a native redactor returning None discards the parenthetical layer-1 result.

Expectation basis: guard.output's documented policy is fail-closed ("Native redactor
errors or unavailability withhold the output"). output_redact sets changed=True and
then returns None when the dependency returns None; guard treats None as "nothing
redacted" and forwards the pre-redaction text, losing the layer-1 mask.
Severity low: the documented Hermes redact_sensitive_text returns str, so this needs
a non-conforming dependency. Demonstrated with an in-memory test double only.
Actual: canary survives.
"""
import sys, types
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
mod = types.ModuleType("agent"); mod.__path__ = []
rmod = types.ModuleType("agent.redact")
rmod.redact_sensitive_text = lambda t: None
rmod._PREFIX_RE = __import__("re").compile(r"(?!x)x")
mod.redact = rmod
sys.modules["agent"] = mod; sys.modules["agent.redact"] = rmod
from pii_mask_abelion.guard import Guard

CANARY = "SyntheticProseNoneZ1q3W5e7"
text = f"w0 w1 {CANARY} (password) tail"
got = Guard().output(text, session_id="repro-r7", platform="cli")
print(f"expected=withheld_or_masked actual={got!r} canary_forwarded={CANARY in got}")
