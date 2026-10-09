# SciForge quick update (Windows).
#
# Replaces the SciForge module inside an existing SciForge portable build with the
# version from this download, so you do not have to wait for a full rebuild.
# Your old version is kept as Mod\SciForge.backup-<date> next to it.
#
# Easiest: double-click install_update.cmd (it starts this script and keeps the
# window open). Everything that happens is also written to install_update.log.
param([string]$Target = "", [switch]$NoPause)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "install_update.log"
try { Start-Transcript -Path $log -Force | Out-Null } catch { }

function Finish($ok, $msg) {
    Write-Host ""
    if ($ok) { Write-Host "[SciForge] $msg" -ForegroundColor Green }
    else { Write-Host "[SciForge] $msg" -ForegroundColor Red; Write-Host "[SciForge] Details: $log" }
    try { Stop-Transcript | Out-Null } catch { }
    if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
    if ($ok) { exit 0 } else { exit 1 }
}

function Pick-Folder {
    # A normal Windows folder picker; falls back to typing/dragging the path.
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Pick your SciForge folder (the one with 'bin' and 'Mod' inside)"
        $dialog.ShowNewFolderButton = $false
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { return $dialog.SelectedPath }
        return ""
    } catch {
        Write-Host "Drag your SciForge folder (the one with 'bin' and 'Mod' inside) here, then press Enter:"
        return (Read-Host).Trim().Trim('"')
    }
}

try {
    Write-Host "[SciForge] quick update, PowerShell $($PSVersionTable.PSVersion)"
    $source = Join-Path $here "SciForge"
    if (-not (Test-Path (Join-Path $source "InitGui.py"))) {
        Finish $false ("The 'SciForge' folder is not next to this script. Unzip the whole download first " +
            "(right-click the .zip > Extract All), then run install_update.cmd from the unzipped folder.")
    }

    if ($Target -eq "") { $Target = Pick-Folder }
    if ($Target -eq "") { Finish $false "No folder picked; nothing changed." }
    # Accept the Mod folder or the bin folder too, and go up to the SciForge folder.
    $leaf = Split-Path -Leaf $Target
    if ($leaf -eq "Mod" -or $leaf -eq "bin") { $Target = Split-Path -Parent $Target }

    $mod = Join-Path $Target "Mod"
    $current = Join-Path $mod "SciForge"
    if (-not (Test-Path (Join-Path $Target "bin"))) {
        Finish $false "No 'bin' folder in $Target. Pick the SciForge folder itself (it contains 'bin' and 'Mod')."
    }
    if (-not (Test-Path $mod)) { Finish $false "No 'Mod' folder in $Target." }

    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($Target, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
    if ($running.Count -gt 0) { Finish $false "SciForge is still running. Close it, then run this again." }

    if (Test-Path $current) {
        $backup = Join-Path $mod ("SciForge.backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        Move-Item -LiteralPath $current -Destination $backup
        Write-Host "[SciForge] old version kept in $backup"
    }
    Copy-Item -LiteralPath $source -Destination $current -Recurse
    $info = Join-Path $current "sciforge\build_info.py"
    if (Test-Path $info) { Get-Content $info | Select-String "COMMIT|DATE" | ForEach-Object { Write-Host "[SciForge] $_" } }
    Finish $true "Update installed. Start SciForge again."
} catch {
    Finish $false ("Something went wrong: " + $_.Exception.Message + " (line " + $_.InvocationInfo.ScriptLineNumber + ")")
}
