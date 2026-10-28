# Minimal repro sheet — classifier case invariance regression set

These are the fixed regression pairs exercised by runner domain
`D1_field_classification`, family `regression` (weight 0.05 of the 200,000
execution budget ≈ 10,000 executions). Phase A executed 200,000/200,000 of this
domain with 0 failures, so every pair below held at the tested SHA during the
audited run — no rerun needed to see this sheet; it documents exactly what
passed. All values are synthetic; no real secrets.

Source of pairs: `runner/run_audit.py`, constant `REGRESSIONS_D1`.

Quick manual check (stdlib only, run in a checkout at 06580f9):

```bash
python3 - <<'EOF'
from pii_mask_abelion import _credentials as C
checks = [
    ("password", "SECRET"), ("paSsWOrD", "SECRET"),
    ("service-password", "SECRET"), ("SerViCE-PasSWord", "SECRET"),
    ("client_id", "IDENTIFIER"), ("aCcoUNT_SiD", "IDENTIFIER"),
    ("compass", None), ("CoMPASs", None),
    ("api_key_name", None), ("API_key_nAme", None),
    ("apikey", "SECRET"), ("ApIkEy", "SECRET"),
    ("maxTokens", None), ("tokenCount", None),
    ("secretFile", None), ("tokenizer", None), ("model", None),
    ("bearertoken", "SECRET"), ("MyApiKey3", "SECRET"),
    ("publickey", "IDENTIFIER"),
]
bad = [(n, e, C.classify_field(n)) for n, e in checks if C.classify_field(n) != e]
print("MISMATCH:", bad) if bad else print("all case-invariance pairs hold")
EOF
```

Expectation semantics: `"SECRET"` / `"IDENTIFIER"` = required-masking classes;
`None` = benign name must not be masked (no false positive).

Result at the audited SHA across the full 200k-execution D1 sweep: 0 mismatches
(see `logs/run_A.log`, D1 summary line).
