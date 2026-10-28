# End-to-end tests

These tests start a real Hermes process, load the real plugins from this repo and assert the final outcome:
what the loopback provider actually received, how provider lifecycle behaves, and what Bot Screen does in a
real virtual desktop/browser. Keys and private-looking values are synthetic; profiles are temporary.

## CI contract

The required `e2e` job runs `python -m pytest e2e -q -rs` against Hermes source pinned to
`9a85916c87d56c2ca00b02fad8918f93ef1816e9` from `Abelion512/hermes-4gent`. `e2e/conftest.py` verifies the imported source's full
`git HEAD` equals that SHA before test collection proceeds. Missing Hermes, a wrong revision, or missing
Screen prerequisites fails the job; the CI run cannot pass by skipping all host tests.

This is compatibility evidence for that exact forked core commit. That core commit remains separate from
upstream adoption; these tests do not mean stock Hermes has mandatory request/auxiliary/output enforcement.
The plugin must not be described as providing mandatory privacy on an unsupported host.

## Layout

| Feature | Spec | E2E test |
|---|---|---|
| Privacy Guard | `pii_mask_abelion/docs/USAGE.md` | `test_privacy_wire.py` |
| 9Router Catalog lifecycle (disabled from repo install) | `model-providers/9router/README.md` | `test_nine_router_disabled.py` |
| Bot Screen dashboard and human/agent input lease | `screen/docs/USAGE.md` | `test_screen_dashboard.py` |

`support/fake_provider.py` is an OpenAI-compatible loopback server that records every request;
`support/host.py` creates an isolated Hermes profile; `support/screen_driver.js` drives real Chrome.
No external provider is called. Real API credentials are stripped from the subprocess environment.

## Run locally

For the same strict CI contract:

```bash
HERMES_PYTHON=/path/to/pinned/hermes/venv/bin/python \
HERMES_EXPECTED_COMMIT=9a85916c87d56c2ca00b02fad8918f93ef1816e9 \
REQUIRE_HERMES_E2E=1 REQUIRE_SCREEN_E2E=1 \
SCREEN_E2E_CHROME=/path/to/chrome \
python -m pytest e2e -v -rs
```

Requirements for Screen: `Xvnc`, `xdotool`, `xfce4-terminal`, Node.js with `puppeteer-core`
resolvable, and a Chrome-compatible executable in `SCREEN_E2E_CHROME`. On hosts where the dependencies
are intentionally absent, Screen reports an explicit skip locally. CI sets `REQUIRE_SCREEN_E2E=1`, which
converts a missing prerequisite into a failure.

## Safety and coverage limits

- Synthetic canaries only, temporary profile, loopback-only model endpoint, no real keys.
- Privacy tests verify the exact request bodies observed by the fake provider. This is not proof that every
  possible secret format is detectable or that every Hermes transport is intercepted.
- Required-mode behavior is tested only against the pinned core contract. A stock/unsupported host is not
  certified by this run.
- 9Router tests verify repo omission and that native `plugins remove` unregisters an already-installed
  provider copy; native `plugins disable` alone does not unregister that provider.
- Screen checks live view, agent lease, human takeover, reconnect, hand-back and page errors. Model-driven
  `computer_use`, phone/Tailscale access, abrupt tab close and a user's own desktop remain outside coverage.
