#!/usr/bin/env bash
# Install the Screen dashboard plugin without mutating an installed profile implicitly.
set -euo pipefail

if [[ -n "${HERMES_HOME:-}" ]]; then
  HERMES_HOME_DIR="$HERMES_HOME"
elif [[ -n "${HOME:-}" ]]; then
  HERMES_HOME_DIR="$HOME/.hermes"
else
  echo "!! HOME or HERMES_HOME must be set."
  exit 1
fi
if [[ -z "$HERMES_HOME_DIR" || "$HERMES_HOME_DIR" != /* ]]; then
  echo "!! refusing unsafe Hermes home: $HERMES_HOME_DIR"
  exit 1
fi
HERMES_HOME_DIR="$(realpath -m -- "$HERMES_HOME_DIR")"
if [[ "$HERMES_HOME_DIR" == "/" ]]; then
  echo "!! refusing unsafe Hermes home: /"
  exit 1
fi

cd "$(dirname "$0")"
[[ -d dashboard ]] || { echo "!! run from the Screen plugin folder (dashboard/ missing)"; exit 1; }

DEST="$HERMES_HOME_DIR/plugins"
CFG="$HERMES_HOME_DIR/config.yaml"
TS="$(date -u +%Y%m%d-%H%M%S)-$$"

command -v hermes >/dev/null 2>&1 || {
  echo "!! 'hermes' was not found in this shell's PATH."
  exit 1
}

# Read and validate plugins.enabled before any backup, move, install or config mutation.
RAW="$(hermes config get plugins.enabled 2>&1 || true)"
CURRENT=""
NORMALIZED="$(printf '%s' "$RAW" | tr -d '[:space:]')"
if grep -qi "not set" <<< "$RAW" || [[ -z "$NORMALIZED" || "$NORMALIZED" == "[]" || "$NORMALIZED" == "null" ]]; then
  CURRENT=""
else
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*([A-Za-z0-9._-]+)[[:space:]]*$ ]]; then
      CURRENT+="${BASH_REMATCH[1]}"$'\n'
    else
      echo "!! plugins.enabled is not a supported YAML list:"
      printf '%s\n' "$RAW"
      echo "!! installer stopped without changing files or config."
      exit 1
    fi
  done <<< "$RAW"
fi
if [[ -n "$CURRENT" ]]; then
  while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    if [[ ! "$n" =~ ^[A-Za-z0-9._-]+$ ]]; then
      echo "!! unsupported plugin ID: $n"
      echo "!! installer stopped without changing files or config."
      exit 1
    fi
  done <<< "$CURRENT"
fi

mkdir -p "$DEST"
if [[ -f "$CFG" ]]; then
  cp -p "$CFG" "$CFG.bak-screen-$TS"
  echo ">> config backup: $CFG.bak-screen-$TS"
fi
if [[ -e "$DEST/screen" || -L "$DEST/screen" ]]; then
  mv -- "$DEST/screen" "$DEST/screen.bak-$TS"
  echo ">> previous plugin moved to $DEST/screen.bak-$TS"
fi

# Stage the package before exposing it at the final install path.
STAGE="$(mktemp -d "$DEST/.screen-install.XXXXXX")"
TMP_NAMES="$(mktemp "${TMPDIR:-/tmp}/hermes-screen-plugin-names.XXXXXX")"
trap 'rm -f -- "$TMP_NAMES"; rm -rf -- "$STAGE"' EXIT
cp -r dashboard "$STAGE/dashboard"
cp -f plugin.yaml "$STAGE/plugin.yaml"
cp -f __init__.py "$STAGE/__init__.py"
if [[ -d skills ]]; then
  cp -r skills "$STAGE/skills"
fi
if [[ -f README.md ]]; then
  cp -f README.md "$STAGE/README.md"
fi
mv -- "$STAGE" "$DEST/screen"

# Serialize only validated IDs, deduplicate and sort them, then use Hermes' CLI.
{
  printf '%s\n' "screen"
  if [[ -n "$CURRENT" ]]; then printf '%s\n' "$CURRENT"; fi
} | sort -u > "$TMP_NAMES"
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
done < "$TMP_NAMES"
json="${json}]"

hermes config set plugins.enabled "$json"
echo ">> plugins.enabled = $json"
echo ">> done. Restart the dashboard manually: Ctrl+C, then 'hermes dashboard'."
echo ">> open http://127.0.0.1:9119 and select SCREEN in the Plugins sidebar."
echo ">> rollback: bash uninstall.sh (restores the newest available backup)."
