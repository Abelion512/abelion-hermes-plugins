# screen - mechanism reference

## Parts

| Part | Role | Source |
|---|---|---|
| Dashboard tab | Sidebar entry + frontend (noVNC view, Take over / Hand back) | `dashboard/manifest.json`, `dashboard/dist/` |
| Backend API | Websocket splice + lease handling between dashboard and Bot Screen | `dashboard/plugin_api.py` |
| Skill | `bot-screen-control` via `ctx.register_skill` | `skills/` |
| Installer helpers | Backup + merge install, rollback | `install.sh`, `uninstall.sh` |

`dashboard/manifest.json` declares the tab (`"tab": {"path": "/screen",
"position": "end"}`, label "Screen", icon Eye) and the backend entry
(`"api": "plugin_api.py"`); the dashboard discovers it without any Hermes
core change. `__init__.py` registers no tools or hooks - only the skill.

## Behavior details

- The tab shows the agent's Bot Screen only (the virtual display from
  `hermes computer-use screen start`, 1440×900 XFCE). It cannot see the
  user's personal desktop.
- Take over hands keyboard/mouse to the dashboard user; Hand back returns it.
  A takeover does not pause non-computer-use tools.
- Bot Screen auto-stops after 30 idle minutes (Hermes default); a blank tab
  usually means it needs `hermes computer-use screen start` again.
- v0.6.3 layout: phone landscape fullscreen hides the header; portrait shows
  the controls.

## install.sh behavior

Runs from a repo clone only. Verifies the current `plugins.enabled` schema
via `hermes config get` and stops without writing when the value is not a
mergeable list; backs up `config.yaml` and moves any previous
`~/.hermes/plugins/screen/` to a timestamped backup; merges `screen` into
`plugins.enabled` via `hermes config set`; never starts/stops the dashboard -
restart is manual. `uninstall.sh` restores the timestamped backup.

## Tests

`tests/` covers the websocket splice, lease API, connect timeout (JS + Python
harness) and fullscreen CSS: `screen/tests/`.

## Configuration

None beyond dashboard auth (shared with the whole dashboard).
