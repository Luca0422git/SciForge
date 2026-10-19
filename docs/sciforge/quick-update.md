# SciForge quick update

Most SciForge changes (interface, icons, Press/Pull, dialogs, ...) are Python. They do not need
the multi-hour build: you only swap the SciForge module inside the SciForge you already have.
A full **SciForge build** is only needed when FreeCAD's C++ core changes (rare; MEMORY.md says so
when it happens).

The update works on every SciForge layout:

- the **installed** SciForge (`C:\Program Files\SciForge`, from the installer): found by itself;
- the **portable** build unzipped anywhere (the folder with `bin\SciForge.exe`);
- a build or a FreeCAD 1.1.4 from before the branding pass (the folder with `bin\FreeCAD.exe`).

## Get it

1. GitHub > **Actions** > **SciForge tests** > the newest run with a green tick.
2. Scroll to **Artifacts**, download `SciForge-quick-update-...` (a few MB).

## Install it (about a minute)

1. Close SciForge.
2. Unzip the download: right-click the .zip > **Extract All** (running it from inside the
   .zip does not work).
3. In the unzipped folder, double-click **`install_update.cmd`**.
4. If SciForge was installed with the installer, the window says where it found it: press
   **Enter** to update that one. Otherwise (or after typing `n`) a folder picker opens: pick
   your SciForge folder (the one with `bin` and `Mod` inside).
5. Read the result in the window, press a key to close it, and start SciForge.
   **SciForge > Diagnostics** shows the build number, the program and the settings folder.

If anything goes wrong, the window stays open with the reason, and everything is also written to
`install_update.log` in the unzipped folder: send that file.

An installed SciForge lives under `C:\Program Files`, so Windows asks for administrator
permission: click **Yes**. A second window does the update and shows the result. The portable
build in a normal folder (for example `C:\SciForge`) needs no permission.

Your previous version is copied to `<your SciForge>\SciForge-backups\<date>` (outside `Mod`,
because FreeCAD loads every folder inside `Mod`). To go back: delete `Mod\SciForge` and copy the
backup folder there under the name `SciForge`. Old backups can be deleted any time; the
uninstaller removes them with the program.

**"SciForge's AI connector is running (python)"**: an AI app you set up (Claude Desktop, Gemini
CLI, Claude Code) started SciForge's AI connector, which runs while that app runs, even with
SciForge closed. Press **Enter** and the installer stops it (harmless: the AI app starts it again
next time), or quit the AI app first (Claude Desktop: right-click its icon by the clock > Quit).

**"Access to the path is denied"**: Windows would not let the files be changed. Close SciForge
(also look in Task Manager for `SciForge` or `FreeCAD`), close every File Explorer window showing
the SciForge folder, and run `install_update.cmd` again (right-click > **Run as administrator**
if it still fails).

Without the installer: close SciForge, delete `<your SciForge>\Mod\SciForge` and copy the
`SciForge` folder from the download into `Mod`.

The .cmd already starts PowerShell with permission to run the script. The manual equivalent:

```
powershell -ExecutionPolicy Bypass -File .\install_update.ps1
```
