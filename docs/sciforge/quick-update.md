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

If the SciForge folder is somewhere protected (for example `C:\Program Files`), Windows asks
for administrator permission: click **Yes**. A second window does the update and shows the result.

Your previous version is copied to `<your SciForge>\SciForge-backups\<date>` (outside `Mod`,
because FreeCAD loads every folder inside `Mod`). To go back: delete `Mod\SciForge` and copy the
backup folder there under the name `SciForge`. Old backups can be deleted any time.

**"Access to the path is denied"**: Windows would not let the files be changed. Close SciForge
(also look in Task Manager for `FreeCAD`), close every File Explorer window showing the SciForge
folder, and run `install_update.cmd` again (right-click > **Run as administrator** if it still
fails). Keeping SciForge in a normal folder such as `C:\SciForge` avoids this.

Without the installer: close SciForge, delete `<your SciForge>\Mod\SciForge` and copy the
`SciForge` folder from the download into `Mod`.

The .cmd already starts PowerShell with permission to run the script. The manual equivalent:

```
powershell -ExecutionPolicy Bypass -File .\install_update.ps1
```
