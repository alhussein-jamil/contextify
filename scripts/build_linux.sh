#!/usr/bin/env bash
# Build contextify as a standalone Linux executable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="$HOME/.local/bin:$PATH"

if [[ ! -d .venv ]]; then
    uv venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing build dependencies"
# Bundle rich for progress UI; skip tiktoken (encoding assets break in PyInstaller).
uv pip install -e ".[build]"
uv pip uninstall -y tiktoken 2>/dev/null || true
if [[ "${INSTALL_DEV:-0}" == "1" ]]; then
    uv pip install -e ".[dev,all]"
fi

if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
    echo "==> Running tests"
    pytest tests/ -q --tb=short
fi

echo "==> Building executable with PyInstaller"
pyinstaller contextify.spec --noconfirm --clean

EXE="$ROOT/dist/contextify"
if [[ -f "$EXE" ]]; then
    chmod +x "$EXE"
    echo ""
    echo "============================================"
    echo "  Build complete!"
    echo "  Run:  $EXE --help"
    echo "  Size: $(du -h "$EXE" | cut -f1)"
    echo "============================================"
else
    echo "ERROR: Executable not found at $EXE" >&2
    exit 1
fi
