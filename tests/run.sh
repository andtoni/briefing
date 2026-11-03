#!/bin/sh
# Run every check. Each test file is a plain script that exits non-zero on the first failed assertion.
set -eu
cd "$(dirname "$0")/.."
log=$(mktemp)
trap 'rm -f "$log"' EXIT
for t in tests/test_*.py; do
  printf '== %s\n' "$t"
  python3 "$t" > "$log" 2>&1 || { cat "$log"; exit 1; }
  tail -n 1 "$log"
done
