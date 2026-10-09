# SciForge quick update

Most SciForge changes (interface, icons, Press/Pull, dialogs, ...) are Python. They do not need
the multi-hour build: you only swap the SciForge module inside the SciForge you already have.
A full **SciForge build** is only needed when FreeCAD's C++ core changes (rare; MEMORY.md says so
when it happens).

## Get it

1. GitHub > **Actions** > **SciForge tests** > the newest run with a green tick.
2. Scroll to **Artifacts**, download `SciForge-quick-update-...` (a few MB).

## Install it (about a minute)

1. Close SciForge.
2. Unzip the download: right-click the .zip > **Extract All** (running it from inside the
   .zip does not work).
3. In the unzipped folder, double-click **`install_update.cmd`**.
4. A folder picker opens: pick your SciForge folder (the one with `bin` and `Mod` inside).
5. Read the result in the window, press a key to close it, and start SciForge.
   **SciForge > Diagnostics** shows the build number.

If anything goes wrong, the window stays open with the reason, and everything is also written to
`install_update.log` in the unzipped folder: send that file.

Your previous version is kept as `Mod\SciForge.backup-<date>`. To go back: delete `Mod\SciForge`
and rename the backup to `SciForge`.

Without the installer: rename `<your SciForge>\Mod\SciForge` to `SciForge.old` and copy the
`SciForge` folder from the download into `Mod`.

The .cmd already starts PowerShell with permission to run the script. The manual equivalent:

```
powershell -ExecutionPolicy Bypass -File .\install_update.ps1
```
