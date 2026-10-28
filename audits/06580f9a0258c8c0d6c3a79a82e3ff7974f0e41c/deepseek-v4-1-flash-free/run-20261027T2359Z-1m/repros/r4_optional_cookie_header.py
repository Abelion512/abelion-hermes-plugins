#!/usr/bin/env python3
"""R4: optional (llm_request) path forwards a structured Cookie header; required denies.

Expectation basis: README says required mode, not stock optional middleware, is the
boundary, and session_material() denies cookie keys. This repro shows the difference
so the guarantee is not overstated.
Actual: Guard.request() forwards the cookie value; required_policy denies.
"""
import json, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion.guard import Guard

CANARY = "SyntheticSessionCookieQ8m2L4p6"
req = {"model": "m", "messages": [{"role": "user", "content": "hi"}],
       "headers": {"Cookie": f"sid={CANARY}"}}
opt = Guard().request(req, session_id="repro-r4a")["request"]
req2 = Guard().required_policy("request", request=req, session_id="repro-r4b")
print(f"optional expected=documented-not-guaranteed actual=canary_forwarded={CANARY in json.dumps(opt)}")
print(f"required expected=denied actual=allow={req2.get('allow')} reason={req2.get('reason')}")
