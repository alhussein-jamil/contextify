#!/usr/bin/env python3
"""Generate contextify.ico from assets/Contextify.png for Windows executables."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "assets" / "Contextify.png"
ICO = ROOT / "assets" / "contextify.ico"


def main() -> int:
    if not PNG.is_file():
        print(f"Missing {PNG}", file=sys.stderr)
        return 1

    try:
        from PIL import Image
    except ImportError:
        print("Install Pillow first: uv pip install pillow", file=sys.stderr)
        return 1

    img = Image.open(PNG).convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    ICO.parent.mkdir(parents=True, exist_ok=True)
    img.save(ICO, format="ICO", sizes=sizes)
    print(f"Wrote {ICO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
