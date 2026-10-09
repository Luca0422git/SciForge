# Forge

A Fusion-style workflow layer for FreeCAD. FreeCAD stays the engine; Forge is the new face on it.

**Status: v0.1, first slice. Written but not yet run inside real FreeCAD** (see "What is tested").

## What v0.1 gives you

- **One "Forge" workbench** with Fusion-style toolbars: *Design* (New Design, Create Sketch, Create / Cut / Modify / Construct drop-downs, Search), *Sketch* (Draw / Modify drop-downs, Dimension, Construction toggle, Finish Sketch) and *View*.
- **A timeline along the bottom.** Every feature of the active body in order. Click = select, double-click = edit, right-click = roll back / roll forward.
- **Fusion shortcut map** (applied while Forge is active, restored when you leave): `S` search, `E` extrude, `F` fillet, `H` hole, `D` dimension, `L` line, `C` circle, `R` rectangle, `T` trim, `X` construction, `F6` fit.
- **Command search** (press `S`): type a few letters of any FreeCAD command and hit Enter.
- **Auto-body.** *Create Sketch* makes a document and a body for you if you have none, so you never think about "Bodies" first.
- **Forge > Diagnostics** lists any command names Forge could not find in your FreeCAD, so a wrong name never silently breaks the toolbar.

## Install on Windows

1. Install FreeCAD from the official site (freecad.org, or the GitHub releases page). Use the stable **1.1.x** release.
2. **Launch FreeCAD once**, then close it. This creates your version-specific user folder under `%APPDATA%\FreeCAD`.
3. Unzip this project somewhere permanent, for example `C:\dev\forge-freecad`.
4. Open PowerShell in that folder and run:
   ```
   powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
   ```
   This links the project into FreeCAD's `Mod` folder, so when I change the code and you pull the update, FreeCAD sees it after a restart. Add `-Copy` for a plain copy instead.
5. Start FreeCAD and choose **Forge** in the workbench dropdown at the top.

If the script cannot find your folder: in FreeCAD open **View > Panels > Python console** and run `FreeCAD.getUserAppDataDir()`. Pass that path plus `Mod` as `-ModDir`.

## If something breaks

1. Open **View > Panels > Report view**. Every Forge problem prints there, prefixed `[Forge]`.
2. Run **Forge > Diagnostics** and copy the text.
3. Send me both, plus a screenshot if it is visual. That is all I need.

If the drop-down buttons act weird, set `USE_DROPDOWNS = False` in `forgecad/config.py` and restart FreeCAD for flat buttons.

## Customizing

Everything about layout lives in `forgecad/config.py`: toolbars, drop-down contents, shortcut keys. No GUI code to touch. Per-machine shortcut overrides go in `<FreeCAD user data>\Forge\shortcuts.json` as `{"Command_Name": "Key"}`.

## What is tested

- Unit tests for the search ranking and the timeline model (rollback rules, state labels).
- A smoke test that runs the whole workbench lifecycle (load, build, activate, deactivate) against a **fake** FreeCAD and Qt. It catches typos, bad wiring and crashes.
- Run them anywhere: `python -m unittest discover -s tests`

**Not tested yet:** anything that needs the real FreeCAD, such as how the toolbars look, whether every command name exists in 1.1.x, and the drop-down behavior. That is the point of the first real run.

## Layout

```
InitGui.py           workbench registration (FreeCAD runs this at startup)
forgecad/config.py   toolbars, groups, shortcuts (edit this one)
forgecad/*_core.py   pure-Python logic (unit tested)
forgecad/*_ui.py     Qt widgets (timeline, search)
tests/               unit + smoke tests
```

License: intended LGPL-2.1-or-later to match FreeCAD. Add a LICENSE file before publishing.
