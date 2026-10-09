# Installs Forge into FreeCAD's user Mod folder on Windows.
#
# Default: makes a junction (a folder link), so edits to this repo show up in
# FreeCAD after a restart. No admin rights needed. Use -Copy for a plain copy.
#
#   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
#   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1 -ModDir "C:\path\to\Mod"
#
# FreeCAD 1.1+ keeps user data in a version-specific folder under
# %APPDATA%\FreeCAD, so launch FreeCAD once first so that folder exists.
param(
    [string]$ModDir = "",
    [switch]$Copy
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ModDir -eq "") {
    $base = Join-Path $env:APPDATA "FreeCAD"
    if (-not (Test-Path $base)) {
        throw "Could not find $base. Install FreeCAD, launch it once, then re-run (or pass -ModDir)."
    }
    $versioned = Get-ChildItem $base -Directory | Where-Object { $_.Name -match '^v\d' } | Sort-Object Name
    if ($versioned.Count -ge 1) {
        $pick = $versioned[-1]
        if ($versioned.Count -gt 1) {
            Write-Host "Several FreeCAD data folders found; using the newest: $($pick.Name)"
        }
        $ModDir = Join-Path $pick.FullName "Mod"
    } elseif (Test-Path (Join-Path $base "Mod")) {
        $ModDir = Join-Path $base "Mod"
    } else {
        throw "No versioned data folder under $base. Launch FreeCAD once, then re-run (or pass -ModDir)."
    }
}

New-Item -ItemType Directory -Force -Path $ModDir | Out-Null
$target = Join-Path $ModDir "Forge"

if (Test-Path $target) {
    $item = Get-Item $target -Force
    if ($item.LinkType -eq "Junction") { $item.Delete() } else { Remove-Item $target -Recurse -Force }
}

if ($Copy) {
    New-Item -ItemType Directory -Path $target | Out-Null
    foreach ($name in @("package.xml", "Init.py", "InitGui.py", "forgecad")) {
        Copy-Item (Join-Path $repo $name) -Destination $target -Recurse -Force
    }
    Write-Host "Copied Forge to $target"
} else {
    New-Item -ItemType Junction -Path $target -Target $repo | Out-Null
    Write-Host "Linked $target -> $repo"
}

Write-Host "Done. Restart FreeCAD and pick 'Forge' in the workbench dropdown."
