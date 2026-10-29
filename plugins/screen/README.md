# Bot Screen

Adds a SCREEN tab to the Hermes web dashboard: a live view of the agent's
Bot Screen (its own virtual desktop + browser - never your personal display),
with Take over to drive it yourself and Hand back to return control to the
agent. NoVNC over the dashboard's existing server; no extra port.

## Requirements

- Hermes dashboard running (`hermes dashboard`, http://127.0.0.1:9119).
- Bot Screen running: `hermes computer-use screen start` (auto-stops after
  30 idle minutes - restart it when the tab goes blank).
- Python dep `aiohttp` (declared in `plugin.yaml`, offered at install).

## Install

Install the plugin from the monorepo:

```bash
hermes plugins install --enable Abelion512/abelion-hermes-plugins/plugins/screen
```

or from a clone: `bash plugins/screen/install.sh` (backs up config and any previous
copy before touching anything; never restarts the dashboard itself - restart
it manually after).

## Verify

```bash
hermes plugins list            # screen shows enabled
hermes plugins doctor screen
```

Open http://127.0.0.1:9119 - SCREEN sits at the end of the sidebar. Connect
shows the live Bot Screen; Take over / Hand back pass control both ways.
`skills_list` shows `screen:bot-screen-control`.

## Limits

- View + input only. A takeover does not pause the agent's other tools -
  only computer-use input is contested.
- Phone: in landscape fullscreen the header buttons hide; rotate to portrait
  to reach Take over / Hand back (v0.6.3).
- Remote access (phone) is expected through your existing private tunnel
  (Tailscale Serve), not a public port - nothing here exposes one.

## Disable / rollback

```bash
hermes plugins disable screen
hermes plugins remove screen           # or: bash plugins/screen/uninstall.sh
```

## Bundled agent skill

`bot-screen-control` - the agent's side of the takeover handshake. Registered
automatically while enabled on hosts with `ctx.register_skill` (API present in upstream source at 0.21.7, 0.22.0, 0.22.2 and 0.22.5; runtime verified only on fork base 9b904dcc plus the privacy patch); older hosts load the dashboard tab without the skill.
See [docs/USAGE.md](docs/USAGE.md).

## Input and requirement validation

See [ordered validation](docs/VALIDATION.md) for the runtime branches and failure outcomes.
