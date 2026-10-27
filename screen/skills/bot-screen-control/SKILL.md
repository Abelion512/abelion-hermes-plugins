---
name: bot-screen-control
description: "Work with the Screen dashboard: view, Take over, Hand back."
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [screen, dashboard, computer-use, takeover]
---

# Bot Screen Control Skill

The screen plugin adds a SCREEN tab to the Hermes web dashboard where the
user watches your Bot Screen (the virtual desktop your computer-use runs on)
live, can Take over to drive it themselves, and Hand back to return control
to you. This skill is your side of that handshake.

## When to Use

- The user mentions Screen, watching your desktop, Take over, or Hand back.
- You are about to do long computer-use work the user may want to observe.
- Don't use for: the user's own desktop. Screen shows only the agent's Bot
  Screen, never the user's personal display.

## How to Apply

1. Bot Screen must be running for Screen to show anything. If the user says
   the tab is blank, ask them to start it with
   `terminal(command="hermes computer-use screen start")` - it auto-stops
   after 30 idle minutes.
2. When the user takes over, stop issuing mouse/keyboard actions immediately.
   Input is theirs until they hand back; racing them corrupts both inputs.
3. After a hand back, re-orient before acting: capture a fresh screenshot,
   because the user may have changed windows, pages, or files.
4. Before long unattended computer-use runs, remind the user they can watch
   from the dashboard (http://127.0.0.1:9119, SCREEN menu) or their phone.

## Pitfalls

- On a phone in landscape fullscreen the header buttons hide; rotating to
  portrait brings back Take over / Hand back (v0.6.3).
- Screen is view + input only. It does not pause your other tools - only
  computer-use input is contested during a takeover.

## Verification

During a takeover you send no computer-use input; after hand back your next
action is based on a fresh screenshot.

## Wrong requirement or value

Lease requests reject malformed JSON, unknown fields, non-boolean force and force on acquire with HTTP422 before upstream RPC. Only an explicit boolean true on release may request forced release. Existing auth and viewer capability checks remain.
Do not claim a rejected operation succeeded or silently replace the requested value.
