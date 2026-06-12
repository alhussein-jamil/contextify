#!/usr/bin/env bash
# Verify the PyInstaller binary runs with no Python/uv on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="${1:-$ROOT/dist/contextify}"
FIXTURE="${2:-$ROOT/tests/fixtures/sample_repo}"
OUT="$(mktemp -d)"

cleanup() { rm -rf "$OUT"; }
trap cleanup EXIT

if [[ ! -x "$EXE" ]]; then
    echo "ERROR: missing executable: $EXE" >&2
    exit 1
fi

# Minimal environment — mimics a user with only the release binary, no venv/uv.
env -i \
    HOME="${HOME:-/tmp}" \
    USER="${USER:-test}" \
    PATH=/usr/bin:/bin \
    TERM="${TERM:-xterm-256color}" \
    "$EXE" "$FIXTURE" -o "$OUT" -q
test -f "$OUT/context.txt"
test -f "$OUT/statistics.json"

echo "OK: standalone smoke passed ($EXE)"
