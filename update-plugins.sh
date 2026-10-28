#!/bin/bash
# update-plugins — git pull + rsync all Abelion plugins
set -euo pipefail

REPO="$HOME/.hermes/abelion-hermes-plugins"
PLUGIN_DIR="$HOME/.hermes/plugins"

if [ ! -d "$REPO/.git" ]; then
  echo "❌ Repo not found at $REPO"
  echo "   Clone first: git clone git@github.com:Abelion512/abelion-hermes-plugins.git $REPO"
  exit 1
fi

echo "⟳ Pulling latest plugins..."
cd "$REPO"
git pull --ff-only

echo "⟳ Syncing to $PLUGIN_DIR..."
for d in pii_mask_abelion screen; do
  rsync -a --delete "$d/" "$PLUGIN_DIR/$d/"
  echo "  ✅ $d"
done

# 9Router Catalog is disabled: not synced. Code stays in model-providers/9router.
# An already installed copy is left untouched; remove it yourself if wanted.

echo ""
echo "✅ Plugins updated. Restart gateway:"
echo "   hermes gateway restart"
echo "   # or: sudo systemctl restart hermes-gateway"
