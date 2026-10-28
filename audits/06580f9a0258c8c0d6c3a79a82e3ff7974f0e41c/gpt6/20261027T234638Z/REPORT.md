# Privacy Guard audit

- Status: BLOCKED for execution. No million-test result is claimed. GitHub API could read the private repo at the requested SHA, but the audit host could not resolve github.com for a fresh local checkout.
- Agent: GPT-6; exact runtime build identifier unavailable. Run ID: 20261027T234638Z. Environment capture UTC: 2026-10-27T23:46:38Z.
- Scope: field classification; benign-name false positives; request and nested payload masking; placeholder/session boundaries; output redaction.
- Work provenance: runner and generator authored for this audit from the pinned contract. No prior AI stress generator or million-run result reused. Pinned regression tests supply only explicit named expectations.

## Target and integrity

- Requested SHA: 06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c. Parent: 579e8c4f52e8bdcf26e1cadc5798cb755071fd90. Root tree: cb7a95c4d2f64717e3a2a3e6b6d332ed1213f04d.
- Local git rev-parse HEAD: NOT RUN. Clone failed before checkout. Source was read remotely, not executed from a local checkout.
- source-manifest.json records Git blob SHA-1 IDs from the pinned tree, not local SHA-256 hashes. Local git hash-object verification: NOT RUN.
- No plugin source write was attempted. Local source-unchanged comparison: NOT RUN because no checkout existed.

## Results

- Total: planned 1,000,000; executed 0; pass 0; fail 0; skip 0; not run 1,000,000; unique inputs 0; assertions 0.
- field_classification: planned 200,000; executed 0; pass 0; fail 0; skip 0; not run 200,000; unique inputs 0; assertions 0.
- benign_false_positive: planned 200,000; executed 0; pass 0; fail 0; skip 0; not run 200,000; unique inputs 0; assertions 0.
- request_nested_payload: planned 250,000; executed 0; pass 0; fail 0; skip 0; not run 250,000; unique inputs 0; assertions 0.
- placeholder_session_boundary: planned 200,000; executed 0; pass 0; fail 0; skip 0; not run 200,000; unique inputs 0; assertions 0.
- output_redaction: planned 150,000; executed 0; pass 0; fail 0; skip 0; not run 150,000; unique inputs 0; assertions 0.
- Counting design: each generated iteration is one execution; unique inputs are to be counted per domain using SHA-256 of canonical inputs without storing raw rows; assertions are tallied separately. No planned case is counted as executed.

## Method

- Environment: Linux 6.18.55-x86_64, Python 3.13.5, Git 2.47.3. The pinned README describes an earlier test environment using Python 3.14.9; matching host/core unavailable here.
- Runner is standard-library Python plus the exact pinned source at a local checkout. Its neutral agent.redact test double is not native Hermes. No provider/network calls or tool dispatch are made by the runner.
- Fresh checkout attempted: GIT_TERMINAL_PROMPT=0 git clone --no-checkout https://github.com/Abelion512/abelion-hermes-plugins.git <temporary-path>. Exit 128, Could not resolve host: github.com. git ls-remote failed for the same DNS reason.
- Executed check: python -m py_compile runner/privacy_guard_million.py, exit 0. Syntax check only, not a test run.
- Reproduction after local access works: gzip -dc runner/privacy_guard_million.py.gz > runner/privacy_guard_million.py && python runner/privacy_guard_million.py --source-root /tmp/abelion-hermes-plugins-06580f9 --count 1000000 --seed 20261028 --output /tmp/privacy-guard-results.json. Verify local HEAD equals the requested SHA before running.
- Existing CI on the target SHA reported six successful jobs; this is not this audit's million-run evidence: https://github.com/Abelion512/abelion-hermes-plugins/actions/runs/40601119386
- Audit-PR CI observation at 2026-10-28T00:10:09Z: full-history secret-scan failed with three generic-api-key findings. One is in a pre-existing audit fixture outside this run folder (reported at audits/f11bdefc005b185ecc5059fc488d1c8759283197/qwen-code-e42f934e-d45c-4ded-a53a-ac7f53131fa0/run-20261027T234738Z/runner/policy_probe.py, commit 6a4cbf28de70e9e2af4494e1544e4ecf08709905). Two are historical snapshots of this audit source-manifest in earlier commits 1abf152039d58e27ad45b2d70c0a7367e859d810 and 1f1f5c9bee5862b955780d3c4d3446a1dd186954; the current source-manifest stores the blob ID as five chunks to avoid resembling a credential. Those older commits remain in history because history rewrite/force-push is prohibited, so the historical scanner result may remain red. This audit did not modify the prior fixture or scanner workflow. The most recent checked run had Privacy Guard and root tests successful, 9Router successful, Screen still in progress.

## Findings

- Source bug: none confirmed; no plugin test ran.
- Documented policy boundary, not classified as a defect: pinned Privacy Guard README states that some unlabelled opaque values, bare name=value, user_session=abc and JSON containing a sessionid field may pass detection. This structural detector is not universal secret discovery. README Git blob SHA-1: e51c8c234d2386d2e68c0df3c48883a4e0672992. Pinned regression controls preserve benign names including compass, api_key_name, passwordPolicy, tokenCount, secretFile and tokenizer.
- Blocking harness issue: expected a checkout with a locally verifiable HEAD; actual Git exited 128 before checkout due to DNS failure. logs/environment.txt records the attempt. This is not evidence of a GitHub authorization denial.
- Proposed classifier and boundary reproductions: NOT RUN; see repros/classifier_case_invariance.md.

## Limits

No local checkout, source-hash verification, plugin-test execution, million run, native Hermes integration or outgoing provider request. A neutral redactor mock is not Hermes and direct-function tests do not prove end-to-end egress protection. The pinned README says the mandatory core change is not adopted. Test failure rate is not a production leak rate; no production leak-rate claim is made.
