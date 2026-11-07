#!/usr/bin/env bash
# update-plugins: sync active monorepo plugin packages to Hermes' plugin directory.
set -euo pipefail

REPO="$HOME/.hermes/abelion-hermes-plugins"
PLUGIN_DIR="$HOME/.hermes/plugins"

if [ ! -d "$REPO/.git" ]; then
  echo "Repo not found at $REPO" >&2
  echo "Clone first: git clone git@github.com:Abelion512/abelion-hermes-plugins.git $REPO" >&2
  exit 1
fi

# A source rename does not uninstall an older copy from a user's Hermes profile.
# Never delete, overwrite, or silently leave a retired plugin discoverable beside
# the consolidated plugin. Require an explicit, backed-up native migration first.
LEGACY_PLUGIN_IDS=(pii_mask_abelion screen output-redact-abelion)
found_legacy=()
for id in "${LEGACY_PLUGIN_IDS[@]}"; do
  if [ -d "$PLUGIN_DIR/$id" ]; then
    found_legacy+=("$id")
  fi
done

if [ "${#found_legacy[@]}" -gt 0 ]; then
  printf 'Legacy Hermes plugin installation detected under %s:\\n' "$PLUGIN_DIR" >&2
  printf '  - %s\\n' "${found_legacy[@]}" >&2
  cat >&2 <<'MESSAGE'

Update stopped before pulling or syncing anything. This script will not guess
which Hermes profile/config is active and will not edit config or delete plugin
state automatically.

Migration required:
  1. Stop the Hermes gateway/process.
  2. Back up the active Hermes profile configuration and the nebula plus listed
     legacy plugin directories.
  3. Use the installed Hermes version's native plugin management to disable the
     listed legacy plugin IDs. Confirm that only `nebula` owns Privacy Guard.
  4. Move the disabled legacy directories outside ~/.hermes/plugins/ (for
     example, into ~/.hermes/plugin-quarantine/<timestamp>/). Keep them for
     rollback; do not permanently delete them yet.
  5. Re-run this updater, then verify the active plugin list and start a new
     session. Follow docs/PLUGIN_MIGRATION.md for the full procedure.

If native plugin management cannot disable an ID, do not move its directory:
stop and resolve the profile/configuration mismatch first.
MESSAGE
  exit 2
fi

echo "Pulling latest plugins..."
cd "$REPO"
git pull --ff-only

echo "Syncing active plugins to $PLUGIN_DIR..."
for d in nebula; do
  rsync -a --delete "$REPO/plugins/$d/" "$PLUGIN_DIR/$d/"
  echo "  synced $d"
done

echo
echo "Plugins updated. Restart the gateway and start a new session:"
echo "  hermes gateway restart"
echo "  # or: sudo systemctl restart hermes-gateway"
