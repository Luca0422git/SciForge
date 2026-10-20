# SciForge: checks install_update.ps1's -Quiet mode (what "Update now" runs after SciForge
# quits) on Windows PowerShell 5.1, against a fake SciForge folder. Run by the "update script"
# job of .github/workflows/sciforge-tests.yml; it can also be run by hand:
#   powershell -ExecutionPolicy Bypass -File tools\sciforge\test_update_script.ps1
#
# The fake SciForge has bin\SciForge.exe (a tiny program that writes bin\restarted.txt when it
# is started), Mod\SciForge with an old version, and the "download" is a folder with the new
# one next to a copy of the script, as the quick-update zip unpacks.
# Checked: it waits for the process it is told to wait for, replaces Mod\SciForge, removes
# files the new version does not have, keeps a backup, starts SciForge again; a file that cannot
# be written puts the old version back and starts nothing; -Quiet never asks; -RunInstaller
# waits and starts the installer.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$updateScript = Join-Path $repo "tools\sciforge\install_update.ps1"
$work = Join-Path ([IO.Path]::GetTempPath()) ("sciforge-update-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $work | Out-Null
$failures = @()

function Check($ok, $what) {
    if ($ok) { Write-Host "ok   $what" } else { Write-Host "FAIL $what"; $script:failures += $what }
}

function Write-File($path, $text) {
    $dir = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [IO.File]::WriteAllText($path, $text)
}

function Read-File($path) { return ([IO.File]::ReadAllText($path)).Trim() }

# The fake program: writes restarted.txt next to itself and ends.
$source = @"
using System;
using System.IO;
public static class FakeSciForge {
    public static void Main(string[] args) {
        File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "restarted.txt"),
            "started " + string.Join(" ", args));
    }
}
"@
$dummy = Join-Path $work "dummy.exe"
Add-Type -TypeDefinition $source -OutputAssembly $dummy -OutputType ConsoleApplication

function New-Fake($name) {
    # A fake install and a fake download; returns the paths.
    $root = Join-Path $work $name
    $fake = Join-Path $root "fake"
    $payload = Join-Path $root "payload"
    New-Item -ItemType Directory -Path (Join-Path $fake "bin") -Force | Out-Null
    Copy-Item $dummy (Join-Path $fake "bin\SciForge.exe")
    Write-File (Join-Path $fake "Mod\SciForge\InitGui.py") "old init"
    Write-File (Join-Path $fake "Mod\SciForge\sciforge\a_first.py") "OLD"
    Write-File (Join-Path $fake "Mod\SciForge\sciforge\old_only.py") "only in the old version"
    Write-File (Join-Path $payload "SciForge\InitGui.py") "new init"
    Write-File (Join-Path $payload "SciForge\sciforge\a_first.py") "NEW"
    Write-File (Join-Path $payload "SciForge\sciforge\zz_last.py") "brand new"
    Copy-Item $updateScript (Join-Path $payload "install_update.ps1")
    return @{ Root = $root; Fake = $fake; Payload = $payload; Mod = (Join-Path $fake "Mod\SciForge") }
}

function Run-Script($payload, $extra) {
    # Windows PowerShell 5.1 as install_update.cmd starts it; returns the exit code and the time.
    $started = Get-Date
    # (Windows PowerShell 5.1 turns a native program's stderr into a terminating error under "Stop")
    $before = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $payload "install_update.ps1") @extra 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $before
    $seconds = ((Get-Date) - $started).TotalSeconds
    $output | ForEach-Object { Write-Host "    | $_" }
    return @{ Code = $code; Seconds = $seconds }
}

function Wait-ForFile($path) {
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path -LiteralPath $path) { return $true }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

try {
    # 1. the normal update: waits for a process, replaces, backs up, restarts
    Write-Host "== update, waiting for SciForge to close"
    $t = New-Fake "one"
    $closing = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-Command", "Start-Sleep -Seconds 6" -PassThru -WindowStyle Hidden
    $r = Run-Script $t.Payload @("-Target", $t.Fake, "-WaitPid", $closing.Id, "-Restart", "-Quiet", "-NoDialog")
    Check ($r.Code -eq 0) "the update ends with exit code 0"
    Check ($r.Seconds -ge 3) "it waited for the process to end ($([int]$r.Seconds) s)"
    Check ((Read-File (Join-Path $t.Mod "InitGui.py")) -eq "new init") "InitGui.py is the new one"
    Check ((Read-File (Join-Path $t.Mod "sciforge\a_first.py")) -eq "NEW") "a changed file is the new one"
    Check (Test-Path (Join-Path $t.Mod "sciforge\zz_last.py")) "a new file is there"
    Check (-not (Test-Path (Join-Path $t.Mod "sciforge\old_only.py"))) "a file the new version lacks is gone"
    $backups = @(Get-ChildItem (Join-Path $t.Fake "SciForge-backups") -Directory)
    Check ($backups.Count -eq 1) "one backup folder was made"
    if ($backups.Count -eq 1) {
        Check ((Read-File (Join-Path $backups[0].FullName "sciforge\a_first.py")) -eq "OLD") "the backup holds the old version"
        Check (Test-Path (Join-Path $backups[0].FullName "sciforge\old_only.py")) "the backup holds the old-only file"
    }
    Check (Wait-ForFile (Join-Path $t.Fake "bin\restarted.txt")) "SciForge.exe was started again"
    Check (Test-Path (Join-Path $t.Payload "install_update.log")) "the log was written"

    # 2. no restart without -Restart
    Write-Host "== update without -Restart"
    $t = New-Fake "two"
    $r = Run-Script $t.Payload @("-Target", $t.Fake, "-Quiet", "-NoDialog")
    Check ($r.Code -eq 0) "exit code 0"
    Start-Sleep -Milliseconds 800
    Check (-not (Test-Path (Join-Path $t.Fake "bin\restarted.txt"))) "SciForge was not started"

    # 3. a file that cannot be written: the old version comes back, nothing is started
    Write-Host "== a file that cannot be replaced"
    $t = New-Fake "three"
    $locked = Join-Path $t.Mod "sciforge\zz_last.py"
    Write-File $locked "OLD LAST"
    Write-File (Join-Path $t.Payload "SciForge\sciforge\zz_last.py") "NEW LAST"
    $hold = [IO.File]::Open($locked, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $r = Run-Script $t.Payload @("-Target", $t.Fake, "-Restart", "-Quiet", "-NoDialog")
    } finally { $hold.Close() }
    Check ($r.Code -eq 1) "a failed update ends with exit code 1"
    Check ((Read-File (Join-Path $t.Mod "sciforge\a_first.py")) -eq "OLD") "the file replaced before the failure is the old one again"
    Check ((Read-File (Join-Path $t.Mod "InitGui.py")) -eq "old init") "InitGui.py is the old one again"
    Check (Test-Path (Join-Path $t.Mod "sciforge\old_only.py")) "the old-only file is still there"
    Check ((Read-File $locked) -eq "OLD LAST") "the file that was locked is untouched"
    Check ((Get-Content (Join-Path $t.Payload "install_update.log") -Raw) -match "old version back") "the log says the old version was put back"
    Start-Sleep -Milliseconds 800
    Check (-not (Test-Path (Join-Path $t.Fake "bin\restarted.txt"))) "a failed update does not start SciForge"

    # 4. -Quiet never asks: no target is an error, not a folder picker
    Write-Host "== -Quiet without a target"
    $t = New-Fake "four"
    $r = Run-Script $t.Payload @("-Quiet", "-NoDialog")
    Check ($r.Code -eq 1) "no -Target: exit code 1 (and no window to answer)"
    Check ((Read-File (Join-Path $t.Mod "InitGui.py")) -eq "old init") "nothing changed"

    # 5. -RunInstaller waits for the process, then starts the installer
    Write-Host "== -RunInstaller"
    $t = New-Fake "five"
    $installerDir = Join-Path $t.Root "installer"
    New-Item -ItemType Directory -Path $installerDir | Out-Null
    $installer = Join-Path $installerDir "SciForge-installer.exe"
    Copy-Item $dummy $installer
    $closing = Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-Command", "Start-Sleep -Seconds 5" -PassThru -WindowStyle Hidden
    $r = Run-Script $t.Payload @("-RunInstaller", $installer, "-WaitPid", $closing.Id, "-Quiet", "-NoDialog")
    Check ($r.Code -eq 0) "exit code 0"
    Check ($r.Seconds -ge 2) "it waited for the process to end"
    Check (Wait-ForFile (Join-Path $installerDir "restarted.txt")) "the installer was started"
    Check ((Read-File (Join-Path $t.Mod "InitGui.py")) -eq "old init") "the module was not touched"
    $r = Run-Script $t.Payload @("-RunInstaller", (Join-Path $installerDir "missing.exe"), "-Quiet", "-NoDialog")
    Check ($r.Code -eq 1) "a missing installer is an error"
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "$($failures.Count) check(s) failed:"
    $failures | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host ""
Write-Host "all checks passed"
