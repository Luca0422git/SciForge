# SciForge quick update (Windows).
#
# Replaces the SciForge module inside an existing SciForge portable build with the
# version from this download, so you do not have to wait for a full rebuild.
# A copy of your old version is kept in <SciForge>\SciForge-backups\<date> (outside Mod,
# because FreeCAD loads every folder inside Mod).
#
# Easiest: double-click install_update.cmd (it starts this script and keeps the
# window open). Everything that happens is also written to install_update.log.
#
# The update copies files over the old ones instead of renaming the SciForge folder:
# Windows refuses to rename a folder while anything (an Explorer window, antivirus,
# OneDrive) is looking inside it, but overwriting the files still works then.
param([string]$Target = "", [switch]$NoPause, [switch]$Elevated)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "install_update.log"
try { Start-Transcript -Path $log -Force -Append:$Elevated | Out-Null } catch { }

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

function Is-Admin {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        return (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
            [Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

function Can-Write($folder) {
    $probe = Join-Path $folder (".sciforge-write-test-" + [guid]::NewGuid().ToString("N"))
    try {
        [IO.File]::WriteAllText($probe, "x")
        Remove-Item -LiteralPath $probe -Force
        return $true
    } catch { return $false }
}

function Copy-Tree($from, $to) {
    # Copies every file from $from into $to, overwriting (also read-only files).
    $count = 0
    $fromFull = (Resolve-Path -LiteralPath $from).Path.TrimEnd('\', '/')
    foreach ($item in Get-ChildItem -LiteralPath $fromFull -Recurse -Force) {
        $rel = $item.FullName.Substring($fromFull.Length).TrimStart('\', '/')
        $dest = Join-Path $to $rel
        if ($item.PSIsContainer) {
            if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
            continue
        }
        $parent = Split-Path -Parent $dest
        if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        if (Test-Path -LiteralPath $dest) {
            $old = Get-Item -LiteralPath $dest -Force
            if ($old.IsReadOnly) { $old.IsReadOnly = $false }
        }
        try {
            Copy-Item -LiteralPath $item.FullName -Destination $dest -Force
        } catch {
            throw "Could not write $dest. $($_.Exception.Message)"
        }
        $count++
    }
    return $count
}

function Remove-Leftovers($newRoot, $installed) {
    # Deletes files that the new version no longer has (old .py files, __pycache__).
    $installedFull = (Resolve-Path -LiteralPath $installed).Path.TrimEnd('\', '/')
    $removed = 0
    $files = @(Get-ChildItem -LiteralPath $installedFull -Recurse -Force -File)
    foreach ($file in $files) {
        $rel = $file.FullName.Substring($installedFull.Length).TrimStart('\', '/')
        if (-not (Test-Path -LiteralPath (Join-Path $newRoot $rel))) {
            try {
                if ($file.IsReadOnly) { $file.IsReadOnly = $false }
                Remove-Item -LiteralPath $file.FullName -Force
                $removed++
            } catch { Write-Host "[SciForge] could not remove old file $($file.FullName) (harmless)" }
        }
    }
    # Empty folders left behind, deepest first.
    $dirs = @(Get-ChildItem -LiteralPath $installedFull -Recurse -Force -Directory |
        Sort-Object { $_.FullName.Length } -Descending)
    foreach ($dir in $dirs) {
        if (@(Get-ChildItem -LiteralPath $dir.FullName -Force).Count -eq 0) {
            try { Remove-Item -LiteralPath $dir.FullName -Force } catch { }
        }
    }
    return $removed
}

$accessHelp = ("Windows did not allow SciForge's files to be changed. Try this: (1) close SciForge " +
    "(also check Task Manager for 'FreeCAD'), (2) close every File Explorer window showing the " +
    "SciForge folder, (3) right-click install_update.cmd > 'Run as administrator'. " +
    "If SciForge is under 'C:\Program Files', moving it to e.g. C:\SciForge avoids this for good.")

try {
    Write-Host "[SciForge] quick update, PowerShell $($PSVersionTable.PSVersion)"
    $source = Join-Path $here "SciForge"
    if (-not (Test-Path (Join-Path $source "InitGui.py"))) {
        Finish $false ("The 'SciForge' folder is not next to this script. Unzip the whole download first " +
            "(right-click the .zip > Extract All), then run install_update.cmd from the unzipped folder.")
    }

    if ($Target -eq "") { $Target = Pick-Folder }
    if ($Target -eq "") { Finish $false "No folder picked; nothing changed." }
    # Accept the Mod folder, the bin folder or Mod\SciForge too, and go up to the SciForge folder.
    $Target = $Target.TrimEnd('\', '/')
    $leaf = Split-Path -Leaf $Target
    if ($leaf -eq "SciForge" -and (Split-Path -Leaf (Split-Path -Parent $Target)) -eq "Mod") {
        $Target = Split-Path -Parent $Target
        $leaf = "Mod"
    }
    if ($leaf -eq "Mod" -or $leaf -eq "bin") { $Target = Split-Path -Parent $Target }
    Write-Host "[SciForge] SciForge folder: $Target"

    $mod = Join-Path $Target "Mod"
    $current = Join-Path $mod "SciForge"
    if (-not (Test-Path (Join-Path $Target "bin"))) {
        Finish $false "No 'bin' folder in $Target. Pick the SciForge folder itself (it contains 'bin' and 'Mod')."
    }
    if (-not (Test-Path $mod)) { Finish $false "No 'Mod' folder in $Target." }

    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($Target, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
    if ($running.Count -gt 0) {
        Finish $false ("SciForge is still running ($($running[0].ProcessName)). Close it, then run this again.")
    }

    # Folders such as C:\Program Files need administrator rights: ask Windows for them once.
    if (-not ((Can-Write $mod) -and (Can-Write $Target))) {
        if (-not $Elevated -and -not (Is-Admin)) {
            Write-Host "[SciForge] this folder needs administrator rights; Windows will ask for permission..."
            try { Stop-Transcript | Out-Null } catch { }
            $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$($MyInvocation.MyCommand.Path)`"",
                "-Target", "`"$Target`"", "-Elevated")
            try {
                Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs -Wait
                Write-Host "[SciForge] the administrator window has finished; its result is in $log"
                if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
                exit 0
            } catch {
                try { Start-Transcript -Path $log -Append | Out-Null } catch { }
                Finish $false ("Administrator permission was not given. " + $accessHelp)
            }
        }
        Finish $false $accessHelp
    }

    if (Test-Path $current) {
        # Keep a copy of the old version (copying works even when renaming the folder is blocked).
        $backups = Join-Path $Target "SciForge-backups"
        if (-not (Test-Path -LiteralPath $backups)) { New-Item -ItemType Directory -Path $backups -Force | Out-Null }
        $backup = Join-Path $backups (Get-Date -Format "yyyyMMdd-HHmmss")
        Write-Host "[SciForge] keeping a copy of the old version in $backup ..."
        Copy-Item -LiteralPath $current -Destination $backup -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $current -Force | Out-Null
    }

    $copied = Copy-Tree $source $current
    $removed = Remove-Leftovers $source $current
    Write-Host "[SciForge] $copied files installed, $removed old files removed"

    $info = Join-Path $current "sciforge\build_info.py"
    if (Test-Path $info) { Get-Content $info | Select-String "COMMIT|DATE" | ForEach-Object { Write-Host "[SciForge] $_" } }
    Finish $true "Update installed. Start SciForge again."
} catch {
    $msg = $_.Exception.Message
    $line = $_.InvocationInfo.ScriptLineNumber
    if ($_.Exception -is [UnauthorizedAccessException] -or $msg -match "denied|being used by another process") {
        Finish $false ("Something went wrong: $msg (line $line). " + $accessHelp)
    }
    Finish $false ("Something went wrong: $msg (line $line)")
}
