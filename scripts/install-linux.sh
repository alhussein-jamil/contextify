#!/usr/bin/env bash
# Install contextify standalone binary to ~/.local/bin (no Python required).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$DIR/contextify"
DEST="${INSTALL_DIR:-$HOME/.local/bin}/contextify"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: run this script from the unzipped release folder (contextify binary missing)" >&2
    exit 1
fi

mkdir -p "$(dirname "$DEST")"
cp "$SRC" "$DEST"
chmod 755 "$DEST"

echo "Installed: $DEST"
echo "Ensure ~/.local/bin is on your PATH, then run: contextify --help"
