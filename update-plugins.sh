#!/bin/bash
# update-plugins: sync the active monorepo plugin packages to Hermes' plugin directory.
set -euo pipefail

REPO="$HOME/.hermes/abelion-hermes-plugins"
PLUGIN_DIR="$HOME/.hermes/plugins"

if [ ! -d "$REPO/.git" ]; then
  echo "Repo not found at $REPO" >&2
  echo "Clone first: git clone git@github.com:Abelion512/abelion-hermes-plugins.git $REPO" >&2
  exit 1
fi

echo "Pulling latest plugins..."
cd "$REPO"
git pull --ff-only

echo "Syncing active plugins to $PLUGIN_DIR..."
for d in pii_mask_abelion screen; do
  rsync -a --delete "$REPO/plugins/$d/" "$PLUGIN_DIR/$d/"
  echo "  synced $d"
done

echo
echo "Plugins updated. Restart the gateway:"
echo "  hermes gateway restart"
echo "  # or: sudo systemctl restart hermes-gateway"
