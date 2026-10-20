# SciForge quick update (Windows).
#
# Replaces the SciForge module inside an existing SciForge with the version from this
# download, so you do not have to wait for a full rebuild. It works on every layout:
# the installed SciForge (C:\Program Files\SciForge, found through the registry key the
# installer writes), the portable build unzipped anywhere (bin\SciForge.exe), and a build
# or FreeCAD from before the branding pass (bin\FreeCAD.exe): the folder only needs
# 'bin' and 'Mod' inside.
# A copy of your old version is kept in <SciForge>\SciForge-backups\<date> (outside Mod,
# because FreeCAD loads every folder inside Mod).
#
# Easiest: double-click install_update.cmd (it starts this script and keeps the
# window open). Everything that happens is also written to install_update.log.
#
# The update copies files over the old ones instead of renaming the SciForge folder:
# Windows refuses to rename a folder while anything (an Explorer window, antivirus,
# OneDrive) is looking inside it, but overwriting the files still works then.
#
# "Update now" inside SciForge (sciforge/update_ui.py) starts this script by itself, after
# SciForge quit, with:  -Target <SciForge folder> -WaitPid <SciForge's process id> -Restart -Quiet
#   -WaitPid N      wait (up to 15 minutes) until process N has ended before touching anything
#   -Restart        start SciForge again when the update is in
#   -Quiet          never ask anything (no folder picker, no Enter); a failure puts the old version
#                   back and shows one message box with the log's path; implies -NoPause
#   -RunInstaller X after -WaitPid, start the installer X (a full-installer update) and stop
#   -NoDialog       with -Quiet: no message box (the Windows check job of sciforge-tests.yml)
# Without these the script behaves exactly as before (the interactive quick update).
param([string]$Target = "", [switch]$NoPause, [switch]$Elevated,
    [int]$WaitPid = 0, [switch]$Restart, [switch]$Quiet, [string]$RunInstaller = "", [switch]$NoDialog)

$ErrorActionPreference = "Stop"
if ($Quiet) { $NoPause = $true }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "install_update.log"
try { Start-Transcript -Path $log -Force -Append:$Elevated | Out-Null } catch { }

function Finish($ok, $msg) {
    Write-Host ""
    if ($ok) { Write-Host "[SciForge] $msg" -ForegroundColor Green }
    else { Write-Host "[SciForge] $msg" -ForegroundColor Red; Write-Host "[SciForge] Details: $log" }
    try { Stop-Transcript | Out-Null } catch { }
    # Quiet: nobody is looking at this window, so a failure is told in a message box (the
    # elevated copy leaves that to the one that started it).
    if ((-not $ok) -and $Quiet -and (-not $NoDialog) -and (-not $Elevated)) { Show-Failure $msg }
    if (-not $NoPause) { Read-Host "Press Enter to close" | Out-Null }
    if ($ok) { exit 0 } else { exit 1 }
}

function Show-Failure($msg) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(
            "SciForge could not be updated. Your old version was put back.`n`n$msg`n`nDetails: $log",
            "SciForge update", "OK", "Warning")
    } catch { }
}

function Wait-ForProcess($id) {
    # Until process $id has ended (SciForge quitting after "Update now"), at most 15 minutes.
    $deadline = (Get-Date).AddSeconds(900)
    while ((Get-Process -Id $id -ErrorAction SilentlyContinue) -and ((Get-Date) -lt $deadline)) {
        Start-Sleep -Milliseconds 500
    }
    if (Get-Process -Id $id -ErrorAction SilentlyContinue) { return $false }
    Start-Sleep -Seconds 1  # let Windows let go of the files
    return $true
}

function Start-Program($folder, $name) {
    $bin = Join-Path $folder "bin"
    Start-Process -FilePath (Join-Path $bin $name) -WorkingDirectory $bin
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

function Find-Installed {
    # The SciForge installer writes HKLM (all users) or HKCU (current user)
    # \SOFTWARE\SciForge<version> with the install folder as its default value
    # (package/WindowsInstaller/include/declarations.nsh, APP_REGKEY). Returns the folders
    # that still exist. A FreeCAD installation uses SOFTWARE\FreeCAD<version>: not matched.
    $found = @()
    foreach ($hive in @("HKLM:\SOFTWARE", "HKCU:\SOFTWARE")) {
        try {
            $keys = @(Get-ChildItem -Path $hive -ErrorAction SilentlyContinue |
                Where-Object { $_.PSChildName -match '^SciForge\d*$' })
            foreach ($key in $keys) {
                $dir = (Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue).'(default)'
                if ($dir -and (Test-Path (Join-Path $dir "bin")) -and (Test-Path (Join-Path $dir "Mod")) -and
                    ($found -notcontains $dir)) {
                    $found += $dir
                }
            }
        } catch { }
    }
    return $found
}

function Program-Name($folder) {
    # The program inside: SciForge.exe since the branding pass, FreeCAD.exe before it.
    foreach ($name in @("SciForge.exe", "FreeCAD.exe", "freecad.exe")) {
        if (Test-Path (Join-Path (Join-Path $folder "bin") $name)) { return $name }
    }
    return ""
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

function Copy-Tree($from, $to, [switch]$Tolerant) {
    # Copies every file from $from into $to, overwriting (also read-only files). Tolerant (the
    # put-back after a failed update): a file that cannot be written is told and skipped.
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
            if ($Tolerant) { Write-Host "[SciForge] could not put back $dest ($($_.Exception.Message))"; continue }
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
    "(also check Task Manager for 'SciForge' or 'FreeCAD'), (2) close every File Explorer window " +
    "showing the SciForge folder, (3) right-click install_update.cmd > 'Run as administrator'. " +
    "An installed SciForge (C:\Program Files\SciForge) always needs the administrator step; " +
    "the portable build in a normal folder such as C:\SciForge does not.")

$script:backup = ""  # the copy of the old version, once made (Quiet puts it back on a failure)
$script:current = ""
try {
    Write-Host "[SciForge] quick update, PowerShell $($PSVersionTable.PSVersion)"
    if ($WaitPid -gt 0) {
        Write-Host "[SciForge] waiting for SciForge (process $WaitPid) to close..."
        if (-not (Wait-ForProcess $WaitPid)) {
            Finish $false "SciForge did not close (process $WaitPid is still running), so nothing was changed."
        }
        Write-Host "[SciForge] SciForge has closed"
    }
    if ($RunInstaller -ne "") {
        # A full-installer update: SciForge has quit, the person sees the normal installer.
        if (-not (Test-Path -LiteralPath $RunInstaller)) { Finish $false "The installer is not there: $RunInstaller" }
        Write-Host "[SciForge] starting the installer $RunInstaller"
        Start-Process -FilePath $RunInstaller
        Finish $true "The installer was started."
    }
    $source = Join-Path $here "SciForge"
    if (-not (Test-Path (Join-Path $source "InitGui.py"))) {
        Finish $false ("The 'SciForge' folder is not next to this script. Unzip the whole download first " +
            "(right-click the .zip > Extract All), then run install_update.cmd from the unzipped folder.")
    }

    if ($Target -eq "" -and $Quiet) { Finish $false "No -Target given; nothing changed." }
    if ($Target -eq "") {
        # An installed SciForge is found by itself; the picker is for the portable build.
        $installed = @(Find-Installed)
        if ($installed.Count -eq 1) {
            Write-Host "[SciForge] found the installed SciForge in $($installed[0])"
            $answer = Read-Host "Update it? (Enter = yes, n = pick another folder)"
            if ($answer -notmatch '^[nN]') { $Target = $installed[0] }
        } elseif ($installed.Count -gt 1) {
            Write-Host "[SciForge] several SciForge installations found; pick the one to update:"
            $installed | ForEach-Object { Write-Host "    $_" }
        }
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
    $program = Program-Name $Target
    if ($program -eq "") {
        Finish $false ("No SciForge.exe or FreeCAD.exe in $Target\bin. Pick the SciForge folder " +
            "(installed: C:\Program Files\SciForge; portable: the unzipped folder).")
    }
    Write-Host "[SciForge] program: bin\$program"

    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($Target, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
    # SciForge's own python.exe running alone is the AI connector (sciforge_mcp.py): Claude
    # Desktop, Gemini CLI or Claude Code start it and keep it while they run, SciForge closed
    # or not. Stopping it is harmless: the AI app starts it again when it is opened again.
    $helpers = @($running | Where-Object { $_.ProcessName -like "python*" })
    if ($running.Count -gt 0 -and $helpers.Count -eq $running.Count) {
        Write-Host ("[SciForge] SciForge's AI connector is running ($($helpers.Count) python): an AI " +
            "app you set up (Claude Desktop, Gemini CLI, Claude Code) started it.")
        $answer = "y"
        if (-not $NoPause) {
            $answer = Read-Host "Stop it now? The AI app starts it again next time. (Enter = yes, n = no)"
        }
        if ($answer.Trim().ToLower() -ne "n") {
            foreach ($p in $helpers) {
                try { Stop-Process -Id $p.Id -Force -ErrorAction Stop } catch { }
            }
            Start-Sleep -Seconds 1
            $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
                try { $_.Path -and $_.Path.StartsWith($Target, [System.StringComparison]::OrdinalIgnoreCase) } catch { $false }
            })
        }
    }
    if ($running.Count -gt 0) {
        $what = $running[0].ProcessName
        if ($what -like "python*") {
            Finish $false ("SciForge's AI connector is still running (python): quit Claude Desktop " +
                "(right-click its icon by the clock > Quit), Gemini CLI or Claude Code, then run this again.")
        }
        Finish $false ("SciForge is still running ($what). Close it, then run this again.")
    }

    # Folders such as C:\Program Files need administrator rights: ask Windows for them once.
    if (-not ((Can-Write $mod) -and (Can-Write $Target))) {
        if (-not $Elevated -and -not (Is-Admin)) {
            Write-Host "[SciForge] this folder needs administrator rights; Windows will ask for permission..."
            try { Stop-Transcript | Out-Null } catch { }
            $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$($MyInvocation.MyCommand.Path)`"",
                "-Target", "`"$Target`"", "-Elevated")
            if ($Quiet) {
                # The elevated copy does the work and tells its result by its exit code; this one
                # (not an administrator) starts SciForge again, so SciForge does not run elevated.
                $argList += @("-Quiet", "-NoDialog")
                try {
                    $child = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs -Wait -PassThru -WindowStyle Hidden
                } catch {
                    try { Start-Transcript -Path $log -Append | Out-Null } catch { }
                    Finish $false ("Administrator permission was not given. " + $accessHelp)
                }
                try { Start-Transcript -Path $log -Append | Out-Null } catch { }
                if ($child.ExitCode -ne 0) {
                    Finish $false "The update could not be installed (see the log); the old version was put back."
                }
                if ($Restart) { Start-Program $Target $program; Write-Host "[SciForge] SciForge started again" }
                Finish $true "Update installed."
            }
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
        if ($Quiet) {
            # The put-back after a failure trusts this copy: it must be complete (a partly made
            # one would make it delete files that were never saved).
            $have = @(Get-ChildItem -LiteralPath $current -Recurse -Force -File).Count
            $kept = @(Get-ChildItem -LiteralPath $backup -Recurse -Force -File).Count
            if ($have -ne $kept) {
                throw "The copy of the old version is not complete ($kept of $have files), so nothing was changed."
            }
        }
        $script:backup = $backup
        $script:current = $current
    } else {
        New-Item -ItemType Directory -Path $current -Force | Out-Null
    }

    $copied = Copy-Tree $source $current
    $removed = Remove-Leftovers $source $current
    Write-Host "[SciForge] $copied files installed, $removed old files removed"

    $info = Join-Path $current "sciforge\build_info.py"
    if (Test-Path $info) { Get-Content $info | Select-String "COMMIT|DATE" | ForEach-Object { Write-Host "[SciForge] $_" } }
    if ($Restart -and -not $Elevated) {
        try {
            Start-Program $Target $program
            Write-Host "[SciForge] SciForge started again"
        } catch { Write-Host "[SciForge] could not start SciForge again: $($_.Exception.Message)" }
        Finish $true "Update installed. SciForge is starting again."
    }
    Finish $true "Update installed. Start SciForge again."
} catch {
    $msg = $_.Exception.Message
    $line = $_.InvocationInfo.ScriptLineNumber
    if ($Quiet -and $script:backup -ne "") {
        # Nobody is watching: put the old version back before telling what went wrong.
        try {
            Write-Host "[SciForge] putting the old version back from $($script:backup) ..."
            $back = Copy-Tree $script:backup $script:current -Tolerant
            $gone = Remove-Leftovers $script:backup $script:current
            Write-Host "[SciForge] old version back: $back files restored, $gone new files removed"
        } catch { Write-Host "[SciForge] could not put the old version back: $($_.Exception.Message)" }
    }
    if ($_.Exception -is [UnauthorizedAccessException] -or $msg -match "denied|being used by another process") {
        Finish $false ("Something went wrong: $msg (line $line). " + $accessHelp)
    }
    Finish $false ("Something went wrong: $msg (line $line)")
}
