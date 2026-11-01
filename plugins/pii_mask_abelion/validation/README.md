# Historical imported adversarial matrix

> This is a legacy offline evaluation record, not the source of truth for current CI. The live regression suite is `../tests/`; pinned-host egress evidence is under `../e2e/`. Keep historical failures visible rather than folding them into the current passing-test count.


Original JSONL: 278 unique IDs, SHA256 a6305f45e1a55f9e0305dae9d4e51eada4fe17e4ea7d0e7f7ef885653ace8722. Source: user-uploaded ZIP, 28 October 2026. Inputs and expectations are unchanged.

The supplied security_stress.py generates a different corpus; it does not read this JSONL and requires retired plugin paths. Unchanged execution exits before testing on the three-package layout. A compatibility runner exercises 93 mask helper/request cases and 87 held-output cases. The 98 Shield cases are retained-target mismatches, not native passes.

Current result: 170 pass, 10 fail, 98 retired-target not run. Of the 10 failures, eight ask for broad INTERNAL prose masking, which is not a current configured policy. One fake JWT lacks the supported JWT shape; one synthetic AWS access ID is 22 characters, not the 20-character AKIA shape. These inputs remain reported failing against their original expectations; they are not silently fixed or excluded.

Confirmed legacy exported helper defects (partial email and missed phone/unlabeled PII) were fixed with full-value patterns and permanent regressions. The active Guard already removed those canaries. Shape-correct synthetic credential controls are tested separately. This is not an all-green 278-suite claim, a native Shield-equivalence claim or end-to-end provider certification.

Uploaded corpus and detailed outputs are kept outside the repository revision so synthetic key fixtures are not accidentally published. Run `python plugins/pii_mask_abelion/validation/run_matrix.py /path/to/abelion_security_test_cases.jsonl` with the matched Hermes environment.
