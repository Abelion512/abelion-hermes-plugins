#!/usr/bin/env bash
# screen plugin installer (repo layout) - dashboard plugin untuk Hermes.
# - menyalin dashboard/ ke ~/.hermes/plugins/screen/ (salinan lama DIPINDAH ke
#   backup bertimestamp, tidak ditimpa)
# - backup config.yaml sebelum disentuh; memverifikasi schema plugins.enabled
#   saat ini (lewat `hermes config get` resmi) dan BERHENTI tanpa mengubah apa
#   pun bila nilainya bukan daftar yang bisa digabung dengan aman
# - menggabungkan "screen" ke plugins.enabled lewat `hermes config set` resmi
# - tidak pernah start/stop/restart gateway atau dashboard; hanya mencetak
#   instruksi restart di akhir
set -euo pipefail
cd "$(dirname "$0")"
[ -d dashboard ] || { echo "!! jalankan dari folder screen (dashboard/ tidak ditemukan)"; exit 1; }

HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME_DIR/plugins"
CFG="$HERMES_HOME_DIR/config.yaml"
TS="$(date -u +%Y%m%d-%H%M%S)"

command -v hermes >/dev/null 2>&1 || {
  echo "!! perintah 'hermes' tidak ditemukan di PATH terminal ini."; exit 1; }

# --- 1) verify the CURRENT schema of plugins.enabled before any write -------
RAW="$(hermes config get plugins.enabled 2>&1 || true)"
CURRENT=""
if printf '%s\n' "$RAW" | grep -qi "not set"; then
  CURRENT=""
elif printf '%s\n' "$RAW" | grep -qE '^\s*- '; then
  CURRENT="$(printf '%s\n' "$RAW" | grep -E '^\s*- ' | sed 's/^\s*- *//; s/\s*$//')"
elif [ -n "$RAW" ]; then
  echo "!! plugins.enabled saat ini BUKAN daftar (isi: $RAW)."
  echo "!! Installer berhenti tanpa mengubah apa pun. Perbaiki config.yaml dulu."
  exit 1
fi

# --- 2) backups --------------------------------------------------------------
if [ -f "$CFG" ]; then
  cp -p "$CFG" "$CFG.bak-screen-$TS"
  echo ">> backup config: $CFG.bak-screen-$TS"
fi
if [ -e "$DEST/screen" ]; then
  mv "$DEST/screen" "$DEST/screen.bak-$TS"
  echo ">> versi lama dipindah ke $DEST/screen.bak-$TS (tidak ditimpa)"
fi

# --- 3) install + official enable (merge, sorted-unique) ---------------------
mkdir -p "$DEST/screen"
cp -r dashboard "$DEST/screen/dashboard"
cp -f plugin.yaml "$DEST/screen/plugin.yaml" 2>/dev/null || true
cp -f __init__.py "$DEST/screen/__init__.py" 2>/dev/null || true
if [ -d skills ]; then
  cp -r skills "$DEST/screen/skills"
  echo ">> skills agent tersalin ke $DEST/screen/skills"
fi
if [ -f README.md ]; then
  cp -f README.md "$DEST/screen/README.md" 2>/dev/null || true
fi
echo ">> plugin tersalin ke $DEST/screen"

json="["; first=1
{ echo "screen"; if [ -n "$CURRENT" ]; then printf '%s\n' "$CURRENT"; fi; } \
  | sort -u > /tmp/.sv-names.$$.txt
while IFS= read -r n; do
  n="${n//\"/}"; [ -z "$n" ] && continue
  if [ "$first" = "1" ]; then json="$json\"$n\""; first=0; else json="$json, \"$n\""; fi
done < /tmp/.sv-names.$$.txt
rm -f /tmp/.sv-names.$$.txt
json="$json]"

hermes config set plugins.enabled "$json"
echo ">> plugins.enabled = $json"

echo ">> Selesai. Restart dashboard manual: Ctrl+C lalu 'hermes dashboard'."
echo ">> Buka http://127.0.0.1:9119 - menu SCREEN ada di sidebar bagian Plugins."
echo ">> Rollback: bash uninstall.sh (mengembalikan backup $TS)."
