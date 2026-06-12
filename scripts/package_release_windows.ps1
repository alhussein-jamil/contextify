# Bundle dist/contextify.exe into a versioned zip for GitHub Releases.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Exe = Join-Path $Root "dist\contextify.exe"
if (-not (Test-Path $Exe)) {
    throw "Run scripts/build_windows.ps1 first (missing dist\contextify.exe)"
}

$Version = if ($env:RELEASE_VERSION) { $env:RELEASE_VERSION } else {
    uv run python -c "from contextify import __version__; print(__version__)"
}
$Pkg = "contextify-$Version-windows-x86_64"
$Staging = Join-Path $Root "dist\$Pkg"
$Zip = Join-Path $Root "dist\$Pkg.zip"

if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Path $Staging | Out-Null

Copy-Item $Exe (Join-Path $Staging "contextify.exe")
Copy-Item (Join-Path $Root "README.md") (Join-Path $Staging "README.md")
Copy-Item (Join-Path $Root "src\contextify\contextify.ignore") (Join-Path $Staging "contextify.ignore")
Copy-Item (Join-Path $Root "scripts\RELEASE_INSTALL_WINDOWS.txt") (Join-Path $Staging "INSTALL.txt")

if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path $Staging -DestinationPath $Zip

$Hash = Get-FileHash $Zip -Algorithm SHA256
Set-Content -Path (Join-Path $Root "dist\SHA256SUMS") -Value "$($Hash.Hash.ToLower())  $(Split-Path -Leaf $Zip)"
Write-Host "Created $Zip"
Get-Content (Join-Path $Root "dist\SHA256SUMS")
