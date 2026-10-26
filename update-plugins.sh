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
for d in shield_abelion pii_mask_abelion output_redact_abelion tool_context_abelion rsi_learn_abelion worktree_guard_abelion; do
  rsync -a --delete "$d/" "$PLUGIN_DIR/$d/"
  echo "  ✅ $d"
done

mkdir -p "$PLUGIN_DIR/model-providers"
rsync -a --delete model-providers/9router/ "$PLUGIN_DIR/model-providers/9router/"
echo "  ✅ model-providers/9router"

echo ""
echo "✅ Plugins updated. Restart gateway:"
echo "   hermes gateway restart"
echo "   # or: sudo systemctl restart hermes-gateway"
