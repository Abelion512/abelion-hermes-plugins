#!/usr/bin/env bash
# Rollback/removal untuk screenview-abelion (dashboard plugin).
# Mengembalikan backup install terbaru (config + salinan plugin sebelumnya)
# bila ada, kalau tidak ada cukup menghapus plugin dan unset. Tidak pernah
# start/stop gateway atau dashboard; restart sendiri setelahnya.
set -euo pipefail
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME_DIR/plugins"
CFG="$HERMES_HOME_DIR/config.yaml"

cfg_bak="$(ls -1t "$CFG".bak-screen-* 2>/dev/null | head -1 || true)"
folder_bak="$(ls -1dt "$DEST"/screenview_abelion.bak-* 2>/dev/null | head -1 || true)"
legacy_bak="$(ls -1dt "$DEST"/screen.bak-* 2>/dev/null | head -1 || true)"

rm -rf "$DEST/screenview_abelion"
echo ">> plugin dihapus dari $DEST/screenview_abelion"

if [ -n "$folder_bak" ]; then
  mv "$folder_bak" "$DEST/screenview_abelion"
  echo ">> versi sebelumnya dikembalikan dari $folder_bak"
fi
if [ -n "$legacy_bak" ]; then
  mv "$legacy_bak" "$DEST/screen"
  echo ">> instalasi era-zip dikembalikan ke $DEST/screen"
fi

if [ -n "$cfg_bak" ]; then
  cp -p "$cfg_bak" "$CFG"
  echo ">> config dikembalikan dari $cfg_bak"
else
  command -v hermes >/dev/null 2>&1 && hermes config unset plugins.enabled || true
  echo ">> tidak ada backup config; plugins.enabled di-unset"
fi
echo ">> Selesai. Restart dashboard manual kalau sedang jalan."
