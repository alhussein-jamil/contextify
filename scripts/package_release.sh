#!/usr/bin/env bash
# Bundle dist/contextify into a versioned zip for GitHub Releases.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EXE="$ROOT/dist/contextify"
if [[ ! -f "$EXE" ]]; then
    echo "ERROR: Run scripts/build_linux.sh first (missing dist/contextify)" >&2
    exit 1
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
VERSION="${RELEASE_VERSION:-$(uv run python -c "from contextify import __version__; print(__version__)")}"
PKG="contextify-${VERSION}-linux-x86_64"
STAGING="$ROOT/dist/$PKG"

rm -rf "$STAGING"
mkdir -p "$STAGING"

cp "$EXE" "$STAGING/contextify"
chmod 755 "$STAGING/contextify"
cp "$ROOT/README.md" "$STAGING/README.md"
cp "$ROOT/src/contextify/contextify.ignore" "$STAGING/contextify.ignore"
cp "$ROOT/scripts/RELEASE_INSTALL.txt" "$STAGING/INSTALL.txt"
cp "$ROOT/scripts/install-linux.sh" "$STAGING/install.sh"
chmod 755 "$STAGING/install.sh"

ZIP="$ROOT/dist/${PKG}.zip"
rm -f "$ZIP"
(
    cd "$ROOT/dist"
    zip -rq "${PKG}.zip" "$PKG"
)

(
    cd "$ROOT/dist"
    sha256sum "${PKG}.zip" > SHA256SUMS
)

echo "Created $ZIP"
cat "$ROOT/dist/SHA256SUMS"
