# 2026-10-14: Derive, Decal, Preferences, Scripts and Add-Ins, Manage Materials, Compute All, Capture Image (branch `sf/misc`)

Outline 7.1, 7.6, 7.12, 7.17. Spec, sources (each row marked Autodesk / Forum / Guess) and gaps:
`docs/sciforge/parity/misc.md`. No change to FreeCAD's own code (no core patch, no full build
needed).

## What was built

- **Derive / Insert Derive** (`derive_core.py`, `derive.py`, `derive_ui.py`): INSERT > Insert
  Derive (a saved design's bodies, sketches, construction planes/axes/points and user
  parameters, ticked in a tree of its browser; Place Objects At Origin), CREATE > Derive (from
  the open design into a New or an Existing design). One Derive step in the timeline; derived
  bodies are ordinary bodies whose first (hidden) step holds the solid, so later steps follow
  an update; derived sketches are fixed curves; derived parameters live in the Parameters
  VarSet's group "Derived" (greyed in Change Parameters, usable as bare names in every field).
  The source is read from a throw-away copy of its saved file (never opened). Out of date
  (the source saved again: mtime/size, then sha1 to tell a copied folder from a new version):
  the step turns yellow and a note says so; right-click > Update Derive / Break Link (new
  generic hook `taskui.MENU_EXTRAS`, collected like EDITORS, shown by the timeline's menu);
  Edit (tick/untick, origin, Update, Break Link). Source by relative path first, kept up to
  date at every save (`slotStartSaveDocument`). Loops refused. Delete of the step takes its
  objects and parameters (delete.py).
- **Decal** (`decal_core.py`, `decal.py`, `decal_ui.py`): a picture on a flat face, wrapped
  round a cylinder, or laid onto other curved faces; Opacity, X/Y Distance, Z Angle, Scale
  X/Y/Plane XY, flips, Chain Faces; move arrows, a turn handle and a scale arrow with value
  boxes; a timeline step; a Decals folder in the body's component; follows the body (found
  again by where it sits; a flat face moved along its normal takes it along). The mesh is the
  face's triangles cut to the picture (Sutherland-Hodgman in picture space), drawn with a Coin
  texture just above the face.
- **Preferences** (`prefs_core.py`, `preferences_ui.py`): Fusion's window (pages, Restore
  Defaults, OK / Cancel / Apply). Honoured: language (restart), Fusion / SolidWorks mouse
  presets, reverse zoom, orbit type, recovery interval and SciForge's file settings, design
  history of new designs, sketch guides, scripts / add-ins folders and editor, default physical
  material, anti-aliasing / transparency / frame rate, precision, default units of new designs,
  the Add-on Manager's proxy. Greyed with the reason: Inventor / Tinkercad / Alias / PowerMill
  mouse, Y up, automatic version on close, default appearance, graphics driver, angular
  precision. `harness.run`'s prepare() resets the ones that change clicks, views and new designs
  (`preferences_ui.reset_for_tests`).
- **Scripts and Add-Ins** (`scripts_core.py`, `scripts_ui.py`, Shift+S): one list, Run / Stop,
  Create (templates), Edit (the chosen editor or FreeCAD's), + (copy a script in), Open File
  Location, Run on Startup (at SciForge's start), Get Add-Ons (FreeCAD's Add-on Manager).
- **Compute All** (`compute_core.py`, `compute_ui.py`, Ctrl+B): everything recomputed quietly,
  a status-bar message, a summary window listing the steps that failed / warn with Find in
  Timeline (a note when all computed).
- **Manage Materials** (`materials_ui.py`, `material.py`): the Material Browser (Physical and
  Appearance tabs: In This Design, Favorites, Library, My Materials / My Appearances, search,
  properties, Assign to Selection, New Material in FreeCAD's User library, New Appearance,
  Delete). Bodies keep their own material's definition; a design opened where it is missing
  gets it made again.
- **Capture Image** (`capture_ui.py`, File menu): Fusion's Image Options (view size / presets /
  custom with lock, transparent background).
- Ribbon: Derive, Insert Derive, Decal, Manage Materials, Compute All, Scripts and Add-Ins,
  Preferences, File > Capture Image wired (only those lines changed); `ribbon_sweep` knows the
  new dialogs' titles.

## Tests

Scenarios: `misc_derive` (76 checks), `misc_decal` (54), `misc_preferences` (84),
`misc_scripts` (49), `misc_materials` (44), `misc_compute` (14), `misc_capture` (25): all pass.
Unit: `test_misc_cores.py` (39). Other areas run after the change: see the report.

## FreeCAD facts and traps found

- A wheel event *sent* to the 3D view's QOpenGLWidget does nothing: a real one goes on to the
  `Gui::View3DInventorViewer` parent, so a test must send it there.
- The harness fails on any Report line with "error", "failed", "invalid"... including
  SciForge's own *informational* lines: Compute All's summary says "could not be computed",
  a script's own failure is logged as "stopped (see Scripts and Add-Ins)" with the details in
  Diagnostics (an exception name like ZeroDivisionError contains "error").
- PartDesign's base feature drops its base shape's Placement: bake it into the geometry
  (`transformShape(placement.toMatrix(), True)`).
- `App.openDocument(copy, True)` on a copy of a design that is open works (same Uid accepted).
- `addProperty` inside a transaction is undone with it; `setGroupOfProperty` exists;
  `setPropertyStatus(name, ["NoModify"])` keeps a note from starring the design; properties set
  in `slotStartSaveDocument` are saved in that file.
- Materials: `inheritMaterial(uuid)` + `addPhysicalModel(<Density model>)` +
  `setPhysicalValue("Density", "1.27 g/cm^3")` + `save("User", mat, "SciForge/<name>.FCMat",
  saveAsCopy=True)` makes a user material; the MaterialManager keeps deleted ones in its cache
  (refresh() does not drop them); a design whose user material is missing loads FreeCAD's
  Default and prints "Material not found".
- A Coin texture from a picture: QImage -> RGBA8888 -> mirrored vertically ->
  `SoSFImage.setValue(SbVec2s(w, h), 4, bytes)`; the 3D view does render under xvfb now (the
  screenshots show the decals).
- The quick-access Menu has SciForge's "File" first and FreeCAD's "&File" later: a test must
  take the first match.
- A plain QDialog that closes leaves no active window without a window manager: every key was
  dead until `versions_ui._refocus_main()` ran (all new windows call it when they close).
- FreeCAD's `Gui::SolidWorksNavigationStyle` gives the SolidWorks preset; `orbit_ui._plan`
  steps aside for any preset that is not Fusion's.

## Gaps (what Fusion does that was not built, why)

See the parity doc's last table: whole components / flat patterns / "From Components"
parameters in Derive; choosing the source version; the application bar's out-of-date icon;
decals on free-form faces without stretching and corner manipulators; Inventor / Tinkercad /
Alias / PowerMill mouse presets, Y up, automatic version on close; Fusion's add-in API.
CONSTRUCT > User Coordinate System still runs FreeCAD's dialog (no Fusion source found for it).
