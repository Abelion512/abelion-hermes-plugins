# Minimal classifier and boundary reproductions

All reproductions below are NOT RUN. Expected results are sourced from the pinned regression test; no actual values are inferred.

Source test: pii_mask_abelion/tests/test_classifier_case_invariance.py, Git blob SHA-1 07b46bf216c7f76afca7051df05d3d676e5018e1.

## Positive classification

Input field names: password, paSsWOrD, service-password, SerViCE-PasSWord, clientSecret, githubToken, accountSid, lmsEmail.
Expected: first six password/token credential names are SECRET; accountSid and lmsEmail are IDENTIFIER. Actual: NOT RUN because a fresh pinned checkout was blocked by DNS.

## Benign-name controls

Input field names: compass, CoMPASs, api_key_name, API_key_nAme, passwordPolicy, tokenCount, secretFile, tokenizer.
Expected from pinned tests: each is None. Actual: NOT RUN. Do not generalize this expectation to every name containing token, key, pass, or secret.

## Request and session boundaries

The runner generates nested JSON requests with unique SYNTHETIC_AUDIT_CANARY values, foreign-session placeholders, altered/forged placeholders, malformed payloads and oversized content. Expected decisions and canary-absence checks derive from the pinned Guard.required_policy, Guard.walk, Guard.text and README session-map contract. Actual: NOT RUN.

## Root-cause status

No source bug is confirmed by execution. The only confirmed issue is the host-level checkout blocker, not a Privacy Guard source bug.
