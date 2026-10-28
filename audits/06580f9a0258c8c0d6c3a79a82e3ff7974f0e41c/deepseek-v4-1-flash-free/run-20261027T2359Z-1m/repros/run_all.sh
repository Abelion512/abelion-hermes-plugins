#!/bin/sh
# Usage: ./run_all.sh /path/to/pinned/checkout
set -u
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=${1:?usage: run_all.sh <pinned-checkout>}
for f in "$here"/r*.py; do
  echo "== $(basename "$f")"
  python3 "$f" "$repo" || echo "REPRO_EXIT=$?"
done
