#!/usr/bin/env python3
"""R1: structured Authorization / Proxy-Authorization header is forwarded unmasked.

Expectation basis: pii_mask_abelion/README.md says required mode checks the whole
model payload; _credentials.mask_value_for_key treats 'authorization' and
'proxy-authorization' as secret keys, and guard.py masks 'authorization: bearer X'.
So a bare Authorization header value must be masked or the request denied.
Actual: allow=True and the synthetic canary is still on the wire.
"""
import json, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion.guard import Guard

CANARY = "SyntheticCanaryAuthZ9p4X6v8Q2"
for key in ("Authorization", "Proxy-Authorization", "authorization"):
    for where, request in (
        ("dict", {"model": "m", "messages": [{"role": "user", "content": "hi"}],
                  "headers": {key: CANARY}}),
        ("prose", {"model": "m", "messages": [{"role": "user",
                                               "content": f"{key}: {CANARY}"}]}),
    ):
        res = Guard().required_policy("request", request=request, session_id="repro-r1")
        forwarded = CANARY in json.dumps(res)
        print(f"{where:5s} {key:20s} expected=masked-or-denied actual="
              f"allow={res.get('allow')} canary_forwarded={forwarded}")
