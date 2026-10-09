# SciForge quick update (Windows).
#
# Replaces the SciForge module inside an existing SciForge portable build with the
# version from this download, so you do not have to wait for a full rebuild.
# Your old version is kept as Mod\SciForge.backup-<date> next to it.
#
# How to use:
#   1. Unzip the "SciForge-quick-update" download anywhere.
#   2. Right-click this file > "Run with PowerShell".
#   3. When asked, drag your SciForge folder (the one that contains "bin" and "Mod")
#      into the window and press Enter.
#   4. Start SciForge again.
param([string]$Target = "")

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $here "SciForge"

function Fail($msg) {
    Write-Host ""
    Write-Host "[SciForge] $msg" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path (Join-Path $source "InitGui.py"))) {
    Fail "This script must stay next to the 'SciForge' folder from the download."
}

if ($Target -eq "") {
    Write-Host "Drag your SciForge folder (the one with 'bin' and 'Mod' inside) here, then press Enter:"
    $Target = (Read-Host).Trim().Trim('"')
}
$mod = Join-Path $Target "Mod"
$current = Join-Path $mod "SciForge"
if (-not (Test-Path (Join-Path $Target "bin"))) { Fail "No 'bin' folder in $Target. Pick the SciForge folder itself." }
if (-not (Test-Path $mod)) { Fail "No 'Mod' folder in $Target." }

$running = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$Target*" }
if ($running) { Fail "SciForge is still running. Close it first, then run this again." }

if (Test-Path $current) {
    $backup = Join-Path $mod ("SciForge.backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    Move-Item $current $backup
    Write-Host "[SciForge] old version kept in $backup"
}
Copy-Item $source $current -Recurse
$info = Join-Path $current "sciforge\build_info.py"
if (Test-Path $info) { Get-Content $info | Select-String "COMMIT|DATE" | ForEach-Object { Write-Host "[SciForge] $_" } }
Write-Host ""
Write-Host "[SciForge] Update installed. Start SciForge again." -ForegroundColor Green
Read-Host "Press Enter to close"
