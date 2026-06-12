# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for contextify standalone CLI binary."""

from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = [(str(root / "src/contextify/contextify.ignore"), "contextify")]

a = Analysis(
    [str(root / "src/contextify/__main__.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "contextify",
        "contextify.cli",
        "contextify.exporter",
        "rich",
        "rich.console",
        "rich.logging",
        "rich.progress",
        "rich.table",
        "rich.text",
        "pygments",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="contextify",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
