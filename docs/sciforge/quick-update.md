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
2. Unzip the download anywhere.
3. Right-click `install_update.ps1` > **Run with PowerShell**.
4. Drag your SciForge folder (the one with `bin` and `Mod` inside) into the window, press Enter.
5. Start SciForge. **SciForge > Diagnostics** (or the Report view) shows the build number.

Your previous version is kept as `Mod\SciForge.backup-<date>`. To go back: delete `Mod\SciForge`
and rename the backup to `SciForge`.

Without the script: replace the folder `<your SciForge>\Mod\SciForge` with the `SciForge` folder
from the download.

If Windows blocks the script ("running scripts is disabled"), open PowerShell in the unzipped
folder and run:

```
powershell -ExecutionPolicy Bypass -File .\install_update.ps1
```
