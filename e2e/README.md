# End-to-end tests

These tests start a real Hermes, load the real plugins from this repo and check the final outcome
(what a loopback provider received, what the dashboard did). Unit tests stay in each plugin's `tests/`.
They are not run by CI yet.

## Layout

| Feature | Spec (contract) | Agent skill | E2E test |
|---|---|---|---|
| Privacy Guard (`pii_mask_abelion`) | `pii_mask_abelion/docs/USAGE.md` | `pii_mask_abelion/skills/` | `test_privacy_wire.py` |
| Screen (`screen`) | `screen/docs/USAGE.md` | `screen/skills/bot-screen-control/` | `test_screen_dashboard.py` |
| 9router adapter (disabled) | `README.md` row | - | `test_nine_router_disabled.py` |

`support/` holds shared helpers: `fake_provider.py` (loopback OpenAI-compatible server that records requests),
`host.py` (isolated profile, real Hermes process), `screen_driver.js` (real Chrome driving the Screen tab).

## Run

```
HERMES_PYTHON=/path/to/hermes/venv/bin/python python -m pytest e2e -v -rs
```

Screen also needs `Xvnc`, `xdotool`, `xfce4-terminal`, `node` with `puppeteer-core` (`NODE_PATH`) and Chrome
(`SCREEN_E2E_CHROME`). Bot Desktop refuses to start on low free memory; `SCREEN_E2E_MIN_FREE_MB` lowers that
guard for a constrained test host only.

A missing requirement is reported as skipped with `NOT RUN: <what is missing>`. A skip is not a pass.

## Safety

Providers are loopback fakes, keys are fake, the profile is a temp directory and the environment is stripped of
real keys and tokens. Private values in the tests are synthetic.

## 9router adapter (disabled)

Desired: not listed in `hermes.json`, not installed by `update-plugins.sh`; code kept; the user's 9Router service is untouched.
Proven by `test_nine_router_disabled.py`. On Hermes, `plugins disable` on an installed copy leaves it registered; only `plugins remove` unregisters it.

## Known results (Hermes upstream main 8acb7f65, repo head 6fd0584 plus the 9router commit)

- `test_auxiliary_requests_have_no_original_private_values` FAILS: the session-title request carries the originals.
  Hermes has no request-mutating hook for auxiliary calls, so this is a core limit the plugin cannot close.
- `test_required_mode_on_unsupported_host_sends_nothing` FAILS: `llm_privacy` is an unknown middleware on this Hermes,
  so required (fail-closed) mode is unavailable and requests are sent.
- Privacy covers the model request wire and tool-result replay. Restoring placeholders only to local destinations is
  not covered by an E2E here.
- Screen: view-only under the agent lease, input under the human lease, reconnect and hand back are covered.
  Model-driven `computer_use`, phone/Tailscale and abrupt tab close are not covered.
