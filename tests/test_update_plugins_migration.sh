#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME/.hermes/abelion-hermes-plugins/.git" "$HOME/.hermes/plugins" "$TMP/bin"
export CALL_LOG="$TMP/calls.log"
: > "$CALL_LOG"

cat > "$TMP/bin/git" <<'MOCK'
#!/usr/bin/env bash
printf 'git %s\n' "$*" >> "$CALL_LOG"
MOCK
cat > "$TMP/bin/rsync" <<'MOCK'
#!/usr/bin/env bash
printf 'rsync %s\n' "$*" >> "$CALL_LOG"
MOCK
chmod +x "$TMP/bin/git" "$TMP/bin/rsync"
export PATH="$TMP/bin:$PATH"

# Each retired plugin ID must block before git pull or rsync can mutate a profile.
for id in pii_mask_abelion screen output-redact-abelion; do
  mkdir -p "$HOME/.hermes/plugins/$id"
  set +e
  output="$(bash "$ROOT/update-plugins.sh" 2>&1)"
  status=$?
  set -e
  if [ "$status" -ne 2 ]; then
    printf 'expected exit 2 for %s, got %s\n%s\n' "$id" "$status" "$output" >&2
    exit 1
  fi
  grep -Fq "$id" <<< "$output"
  if [ -s "$CALL_LOG" ]; then
    echo "updater called git/rsync before blocking on $id" >&2
    cat "$CALL_LOG" >&2
    exit 1
  fi
  rm -rf -- "$HOME/.hermes/plugins/$id"
done

# A clean profile proceeds with the normal fast-forward pull and nebula sync.
bash "$ROOT/update-plugins.sh" >/dev/null
grep -Fq 'git pull --ff-only' "$CALL_LOG"
grep -Fq 'rsync -a --delete' "$CALL_LOG"
echo "update-plugins migration guard tests passed"
