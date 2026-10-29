#!/usr/bin/env bash
# Remove Screen safely. Restore the latest install backup when available.
set -euo pipefail

if [[ -n "${HERMES_HOME:-}" ]]; then
  HERMES_HOME_DIR="$HERMES_HOME"
elif [[ -n "${HOME:-}" ]]; then
  HERMES_HOME_DIR="$HOME/.hermes"
else
  echo "!! HOME or HERMES_HOME must be set."
  exit 1
fi
if [[ -z "$HERMES_HOME_DIR" || "$HERMES_HOME_DIR" == "/" || "$HERMES_HOME_DIR" != /* ]]; then
  echo "!! refusing unsafe Hermes home: $HERMES_HOME_DIR"
  exit 1
fi

DEST="$HERMES_HOME_DIR/plugins"
CFG="$HERMES_HOME_DIR/config.yaml"
TS="$(date -u +%Y%m%d-%H%M%S)-$$"
TMP_NAMES=""
TMP_SORTED=""
cleanup() {
  [[ -z "$TMP_NAMES" ]] || rm -f -- "$TMP_NAMES"
  [[ -z "$TMP_SORTED" ]] || rm -f -- "$TMP_SORTED"
}
trap cleanup EXIT

cfg_bak="$(ls -1t -- "$CFG".bak-screen-* 2>/dev/null | head -1 || true)"
folder_bak="$(ls -1dt -- "$DEST"/screen.bak-* 2>/dev/null | head -1 || true)"

# Never recursively delete an unknown directory, and never restore an unknown backup.
if [[ -e "$DEST/screen" || -L "$DEST/screen" ]]; then
  if [[ ! -f "$DEST/screen/plugin.yaml" ]] || ! grep -qE '^name:[[:space:]]*screen[[:space:]]*$' "$DEST/screen/plugin.yaml"; then
    echo "!! refusing to delete $DEST/screen: no recognized Screen plugin.yaml"
    exit 1
  fi
fi
if [[ -n "$folder_bak" ]]; then
  if [[ ! -f "$folder_bak/plugin.yaml" ]] || ! grep -qE '^name:[[:space:]]*screen[[:space:]]*$' "$folder_bak/plugin.yaml"; then
    echo "!! refusing to restore $folder_bak: no recognized Screen plugin.yaml"
    exit 1
  fi
fi

# Preflight config changes before touching plugin files. Restoring a config backup
# preserves the explicit rollback behavior; without one, remove only Screen and
# preserve all other enabled plugin IDs instead of unsetting the entire list.
CONFIG_ACTION="none"
CONFIG_JSON=""
if [[ -n "$cfg_bak" ]]; then
  CONFIG_ACTION="restore"
else
  command -v hermes >/dev/null 2>&1 || {
    echo "!! 'hermes' is required to safely update plugins.enabled (no config backup exists)."
    exit 1
  }
  RAW="$(hermes config get plugins.enabled 2>&1 || true)"
  NORMALIZED="$(printf '%s' "$RAW" | tr -d '[:space:]')"
  if grep -qi "not set" <<< "$RAW" || [[ -z "$NORMALIZED" || "$NORMALIZED" == "[]" || "$NORMALIZED" == "null" ]]; then
    CONFIG_ACTION="none"
  else
    TMP_NAMES="$(mktemp "${TMPDIR:-/tmp}/hermes-screen-uninstall-names.XXXXXX")"
    TMP_SORTED="$(mktemp "${TMPDIR:-/tmp}/hermes-screen-uninstall-sorted.XXXXXX")"
    screen_enabled=0
    while IFS= read -r line; do
      [[ "$line" =~ ^[[:space:]]*$ ]] && continue
      if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*([A-Za-z0-9._-]+)[[:space:]]*$ ]]; then
        n="${BASH_REMATCH[1]}"
      else
        echo "!! plugins.enabled is not a supported YAML list:"
        printf '%s\n' "$RAW"
        echo "!! refusing to change files or config."
        exit 1
      fi
      if [[ "$n" == "screen" ]]; then
        screen_enabled=1
      else
        printf '%s\n' "$n" >> "$TMP_NAMES"
      fi
    done <<< "$RAW"
    if [[ "$screen_enabled" == "1" ]]; then
      sort -u "$TMP_NAMES" > "$TMP_SORTED"
      json="["
      first=1
      while IFS= read -r n; do
        [[ -z "$n" ]] && continue
        if [[ ! "$n" =~ ^[A-Za-z0-9._-]+$ ]]; then
          echo "!! invalid plugin ID refused while serializing plugins.enabled: $n"
          exit 1
        fi
        if [[ "$first" == "1" ]]; then
          json="${json}\"${n}\""
          first=0
        else
          json="${json}, \"${n}\""
        fi
      done < "$TMP_SORTED"
      CONFIG_JSON="${json}]"
      CONFIG_ACTION="set"
    fi
  fi
fi

if [[ "$CONFIG_ACTION" == "restore" ]]; then
  cp -p -- "$cfg_bak" "$CFG"
  echo ">> config restored from $cfg_bak"
elif [[ "$CONFIG_ACTION" == "set" ]]; then
  if [[ -f "$CFG" ]]; then
    cp -p -- "$CFG" "$CFG.bak-uninstall-$TS"
    echo ">> current config backed up to $CFG.bak-uninstall-$TS"
  fi
  hermes config set plugins.enabled "$CONFIG_JSON"
  echo ">> plugins.enabled = $CONFIG_JSON"
else
  echo ">> plugins.enabled did not contain screen; leaving the setting unchanged"
fi

if [[ -e "$DEST/screen" || -L "$DEST/screen" ]]; then
  rm -rf -- "$DEST/screen"
  echo ">> removed $DEST/screen"
fi
if [[ -n "$folder_bak" ]]; then
  mkdir -p "$DEST"
  mv -- "$folder_bak" "$DEST/screen"
  echo ">> previous plugin restored from $folder_bak"
fi

echo ">> done. Restart the dashboard manually if it is running."
