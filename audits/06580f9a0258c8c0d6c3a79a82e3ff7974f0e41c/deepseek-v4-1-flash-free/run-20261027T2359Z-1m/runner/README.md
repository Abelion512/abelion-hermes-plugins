# Runner: Privacy Guard audit corpus

Target: `Abelion512/abelion-hermes-plugins` @ `06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c`
(tested SHA pinned; nothing here reads another branch).

## Requirements

- Python 3.12 (stdlib only). No pip install, no network, no Hermes core, no provider.
- A clean checkout of the pinned SHA. `pii_mask_abelion/` is imported read-only.
- 4 CPU cores recommended; otherwise pass `--workers N`.

## Commands

```bash
SHA=06580f9a0258c8c0d6c3a79a82e3ff7974f0e41c
git clone https://github.com/Abelion512/abelion-hermes-plugins.git /tmp/pg-audit
cd /tmp/pg-audit
git checkout --detach "$SHA"
git rev-parse HEAD                      # must print the SHA above
cd audits/$SHA/deepseek-v4-1-flash-free/run-20261027T2359Z-1m
python3 runner/run_audit.py \
  --repo /tmp/pg-audit \
  --parent runner/parent_credentials_49e1fe4.py \
  --out results.json --workers 4        # exit 0
sha256sum -c SHA256SUMS                 # after the run
```

`--scale 0.001` runs a 1,000-execution smoke slice with the same index→case mapping.
`--out -` is not supported; always write a file.

## What one execution means

One execution = one case index `i`, decoded deterministically into input parameters,
evaluated once against the pinned source with at least one assertion. `executed =
passed + failed`. `skipped` (ambiguous by pre-declared rule) and `not run` (needs a
real Hermes/provider path) are reported separately and are not counted as executed.

`unique_inputs` counts distinct blake2b-64 fingerprints of the *input* per domain.
For D2-D5 the synthetic canary/value is part of the fingerprint, so two cases with
the same field name but different secret values count as two unique inputs. D1/D6
fingerprint the field name only.

## Files

- `run_audit.py` — corpus, oracle, runner (this file is the whole harness).
- `parent_credentials_49e1fe4.py` — frozen copy of
  `pii_mask_abelion/_credentials.py` at `49e1fe4` (pre-case-fix parent of the tested
  commit), used only by D6 for regression comparison.
- `../results.json` — aggregate counts, failure families, up to 6 samples per rule.
- `../repros/` — minimal standalone reproductions of each reported root cause.
- `../logs/` — stdout/stderr, exit code, integrity checks (sanitized: synthetic
  canaries only; no credentials, env dump, or private file content).

## Test double, explicitly

`agent` / `agent.redact` is **not** installed in the audit host. D5 first exercises
the real "native redactor unavailable" path, then installs an in-memory
`agent.redact` module (`sys.modules`) to exercise the plugin's surrounding logic
(parenthetical masking, restore ordering, failure modes). That module is a test
double, not Hermes. No end-to-end Hermes run is claimed.
