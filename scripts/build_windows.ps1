# Build contextify as a standalone Windows executable.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".venv")) { uv venv }
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Installing build dependencies"
uv pip install -e ".[build]"
uv pip uninstall tiktoken 2>$null
if ($env:INSTALL_DEV -eq "1") { uv pip install -e ".[dev,all]" }

if ($env:SKIP_TESTS -ne "1") {
    Write-Host "==> Running tests"
    pytest tests/ -q --tb=short
}

Write-Host "==> Generating Windows icon"
uv pip install pillow -q
python scripts/generate_icons.py

Write-Host "==> Building executable with PyInstaller"
pyinstaller contextify.spec --noconfirm --clean

$Exe = Join-Path $Root "dist\contextify.exe"
if (Test-Path $Exe) {
    Write-Host ""
    Write-Host "============================================"
    Write-Host "  Build complete!"
    Write-Host "  Run:  $Exe --help"
    Write-Host "============================================"
} else {
    Write-Error "Executable not found at $Exe"
}
