#!/usr/bin/env python3
"""R2: {'name': sensitive_field, 'value': secret} inside a JSON *string* is forwarded.

Expectation basis: guard.Guard.walk masks that exact pair when it is a real dict
(`pair = obj.get('name')`), and README says required mode checks JSON tool arguments
and tool-result replay. Tool results / message content arrive as JSON text strings,
so the same pair must not survive as text.
Actual: both engines forward the canary.
"""
import json, sys
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from pii_mask_abelion.guard import Guard
from pii_mask_abelion.pii_middleware import pii_middleware

CANARY = "SyntheticCanaryNV9k2T5r8W1"
blob = json.dumps({"name": "HF_TOKEN", "value": CANARY})
request = {"model": "m", "messages": [{"role": "tool", "tool_call_id": "c1", "content": blob}]}
res = Guard().required_policy("request", request=request, session_id="repro-r2")
print("guard  expected=masked-or-denied actual="
      f"allow={res.get('allow')} canary_forwarded={CANARY in json.dumps(res)}")
legacy = pii_middleware(request)
print("legacy expected=masked actual="
      f"canary_forwarded={CANARY in json.dumps(legacy if legacy is not None else request)}")
structured = {"model": "m", "messages": [{"role": "tool", "content": {"name": "HF_TOKEN", "value": CANARY}}]}
res2 = Guard().required_policy("request", request=structured, session_id="repro-r2b")
print("control (real dict) expected=masked actual="
      f"canary_forwarded={CANARY in json.dumps(res2)}")
