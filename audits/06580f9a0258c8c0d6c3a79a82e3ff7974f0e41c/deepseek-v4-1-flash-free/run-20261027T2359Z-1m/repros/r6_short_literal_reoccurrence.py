#!/usr/bin/env python3
"""R6: a remembered 1-3 character credential is not masked when it reappears bare.

Expectation basis: guard.py comment says "Exact registered literals are masked even
when the surrounding label is absent", with no length caveat. The re-occurrence loop
skips entry.value shorter than 4 bytes. Recorded as a documented-limit gap (masking
every 1-3 char substring would destroy ordinary text), not an exploitable leak.
Actual: first labelled occurrence is masked; the bare second occurrence is forwarded.
"""
import sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion.guard import Guard

g = Guard(); s = g.session("repro-r6")
g.remember(s, "ab", "SECRET")
first = g.text("password=ab", s)
second = g.text("ab", s)
print(f"first  expected=masked actual={first}")
print(f"second expected=masked actual={second!r} forwarded={'ab' in second}")
