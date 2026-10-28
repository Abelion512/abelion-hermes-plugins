"""Measure-only policy probes against the native SUT at pinned SHA.

These do NOT assert PASS/FAIL; they quantify where the source contract diverges
from a reasonable privacy policy (findings evidence). Synthetic canaries only.
"""
import sys, json
sys.path.insert(0, "/workspace")
from pii_mask_abelion.pii_middleware import mask_content, classify_content, pii_middleware
from output_redact_abelion.output_redact import redact_output

P = {}

# F1 PAREN_CRED swallows up to 6 preceding words of ordinary prose
P["F1_paren_swallow"] = mask_content("Contact John Smith today (email)")

# F2 double-mask artifact: GITHUB_TOKEN label literal re-hit by BARE_SECRET
P["F2_double_mask"] = mask_content("ghp_aaaaaaaa")

# F3 SECRET_CRED charset excludes symbols -> partial value survives
P["F3_partial_value"] = mask_content("password=P@ssw0rd!xyz")

# F4 non-text parts never scanned/masked
req = {"messages":[{"role":"user","content":[
    {"type":"input_audio","input_audio":{"url":"sk-SecretKeyMaterial99"}}]}]}
P["F4_nontext_passthrough"] = pii_middleware(req)

# F5 PII_FIELD masks only first word of multi-word value
P["F5_address_residue"] = mask_content("address: Jl. Merdeka No 5 Jakarta")

# F6 LONG_NUMBER fails for >19-digit runs
P["F6_20digit"] = mask_content("id 12345678901234567890 end"), classify_content("12345678901234567890")

# F7 ENV_ENTRY shadowing / short env values unmatched
P["F7_short_env"] = mask_content("my_api_key=short"), classify_content("my_api_key=short")

# F8 output layer keeps annotation label + identity context
P["F8_output_label_kept"] = redact_output("Login as Budi Santoso (username) with s3cr3tvalue (password)")

# F9 camelCase key: only substring of key masked, value survives if <8 or split
P["F9_camel_split"] = mask_content("userApiKey=abcdefgh1234")

# F10 bare secret without delimiter/context -> PUBLIC
P["F10_bare_nocontext"] = classify_content("Xk9mP2wQ7rT4yZ8nB5vC1dF6gH3j"), mask_content("Xk9mP2wQ7rT4yZ8nB5vC1dF6gH3j")

def enc(o):
    try: json.dumps(o); return o
    except Exception: return repr(o)

out = {k: enc(v) for k, v in P.items()}
print(json.dumps(out, indent=2, default=str))
open("/workspace/audits/f11bdefc005b185ecc5059fc488d1c8759283197/qwen-code-e42f934e-d45c-4ded-a53a-ac7f53131fa0/run-20261027T234738Z/results/policy_probe.json","w").write(json.dumps(out, indent=2, default=str))
