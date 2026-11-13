# Bot Screen end-to-end tests

These tests exercise the dashboard and agent virtual desktop through a real Hermes process, disposable profile, XFCE/Xvnc desktop, and real Chrome. They do not use the user's personal display.

## CI contract

CI runs this suite against `Abelion512/hermes-4gent` pinned to `9a85916c87d56c2ca00b02fad8918f93ef1816e9`. Screen prerequisites are mandatory in CI; missing dependencies fail the run.

## Layout

- `test_screen_dashboard.py`: real browser flow, view mode, take over, hand back, reconnect, and page errors.
- `support/screen_driver.js`: Chrome/Puppeteer driver.
- `../docs/USAGE.md`: feature and compatibility contract.
- `../tests/`: isolated API, lease, websocket, installer, and frontend regression tests.

The shared Hermes process/profile harness lives under `.github/e2e_support/`. This E2E only covers the agent's virtual desktop. Model-driven `computer_use`, phone/Tailscale, abrupt tab closure, and a user's own desktop remain outside coverage. A desktop takeover does not pause the agent's other tools, so this is not general HITL.
