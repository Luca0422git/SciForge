# 2026-10-16: Import and export, part 2 (branch `sf/exchange-2`, wave 5)

Brief: `docs/sciforge/dev/briefs/exchange-2.md`. Spec, sources and gaps:
`docs/sciforge/parity/insert-export.md`, "Part 2" (also notes in `parity/versions.md` and
`parity/components.md`). No FreeCAD core change (no full build needed).

## What was built

- **STEP / IGES with structure** (`step_import.py`, rules in `exchange_core.py`): FreeCAD's
  own reader (`Import.insert(..., useLinkGroup=True, merge=False, mode=0)`) runs in a hidden
  throw-away document; its tree (App::LinkGroup = assembly, Part::Feature = part, App::Link =
  a repeated occurrence) becomes plain nodes with the solids in the file's coordinates and
  the colours Import.insert returns; then SciForge makes a component per product (named
  after it, nested, its placement), a body per solid (Body1, Body2 ...; its base
  Part::Feature inside the component for FreeCAD's link scope) and, for a repeated part,
  a linked instance (`instances.make_instance`, "Wheel:2"). An assembly holding a part of
  its own name keeps that part's solids as its own bodies (how FreeCAD and SciForge write a
  component's bodies). IGES (no structure) gives bodies; a faces-only IGES is sewn into
  solids (open shells become surface bodies). SAT / SMT / F3D are refused with the reason.
- **File > Open** (`SciForge_Open`, Ctrl+O through `config.PREFERRED`, the application menu
  and quick-access Open): designs as before (`versions_ui.open_design`), a STEP / IGES file
  as a new unsaved design named after the file, the file's top product being the design.
- **Insert STEP** (`exchange_ui.insert_cad_file`, INSERT > Insert STEP, also IGES): the file
  as one component named after it in the active component, one undo step, then the Move
  dialog opens on it (Fusion's Initial Position).
- **Data Panel**: Upload (copies a STEP / IGES file into the folder shown), the file listed
  with its name, double-click opens it, right-click Insert into Current Design / Delete
  (`versions.list_folder` lists `.step/.stp/.iges/.igs`, `versions_ui`).
- **Export** (`exchange.py`, `export_ui.ExportDialog`): Type STEP / IGES / STL / 3MF / OBJ /
  DXF / DWG; Export Whole design / Selected bodies / A component. STEP is written from a
  hidden document mirroring the components (a component with bodies only = a part of its
  name; with components = an assembly + a part of its name for its bodies; an instance = an
  App::Link, i.e. a second occurrence of the same product; colours on the view providers so
  `ImportGui.export` writes them). IGES with solids (`Part.setStaticValue("write.iges.brep.
  mode", 1)`, put back after). A component's meshes / STEP / IGES in its own coordinates
  (Fusion: "the selected component defines the coordinate system"). DXF of a sketch (its
  own 2D coordinates) or a flat face (its frame, centred) through `importDXF.export`; DWG
  only through `importDWG.convertToDwg` with a converter found the way FreeCAD finds them
  (none here: refused with the names of LibreDWG / ODA / QCAD).
- **Browser**: sketch > Save As DXF; body / component > Save As Mesh (the Export dialog on
  it, 3MF); linked component > Break Link (`browser_core.MENUS`, `browser_ui`).
- **Insert into Current Design / Insert Component** (`design_insert.py`, called by
  `versions_ui.insert_design`): one component named after the other design ("Wheel (2)" for
  a second one), each body a copy body whose first step `LinkedCopy` (Part::FeaturePython,
  `App::PropertyXLink` to the other design's body, relative path) copies its solid; then
  the Move dialog. Opening a design recomputes linked copies whose source changed since.
  **Break Link** copies the other design's bodies with every feature in
  (`Document.copyObject(body, True)` across documents), one undo step; refused when the
  other design is missing.
- **Manipulators** (`insert_ui._PlaneHandles`, used by Insert SVG / DXF and Canvas / Edit
  Canvas): two arrows (X / Y Distance), a curved handle (Z Angle), a scale arrow just
  outside the right edge, each with a value box; the handles are rebuilt when the camera
  changes (they keep their screen size). SVG is now centred on the sketch origin and its Z
  Angle is positive clockwise (Autodesk help); DXF keeps its origin at the sketch origin.

## FreeCAD facts and traps found

- `Import.insert` with `useLinkGroup=True` keeps assemblies (App::LinkGroup) and makes a
  repeated part an App::Link to the first occurrence; without it (the default headless
  setting) every occurrence is a separate copy. It returns `[(Part::Feature, colours)]`, so
  colours work headless and in the GUI alike. `getSubObject(sub, retType=2)` gives
  `(obj, Matrix, None)`: the occurrence's placement in the file.
- The IGES writer writes loose faces unless OpenCASCADE's static `write.iges.brep.mode` is
  1; the `Mod/Part/IGES/BrepMode` parameter alone does not change it after start-up
  (`Part.setStaticValue` does).
- `FreeCADGui.open` is for macros / Inventor files: it silently does not open an FCStd.
  Use `App.openDocument`.
- A Data Panel tool button's `clicked(bool)` passes `False` into a slot with a `path=None`
  argument: connect through a lambda.
- Coin drag handles made before a camera change (fit, zoom) stopped taking drags over a
  transparent canvas in Edit Canvas (the press reached Coin and the ray pick hit the
  dragger, but the dragger never activated); rebuilding the handles after the camera
  change cured it every time. Rebuilding on a camera change is also Fusion's look
  (constant screen size), so it was kept as the behaviour.
- Enter in an `ArrowValueBox` takes the value and then reaches the 3D view, where
  `EnterFinishes` presses OK: Fusion's Enter in a value box finishes the command too.
- A scale arrow lying on the picture's edge took presses for the picture / sketch under
  it; it now sits just outside the edge.
- Black on `sciforge/*.py` reformats dozens of other areas' files: run it on your own files
  only.

## Tests (real FreeCAD 1.1.4, one at a time, final runs on 7969ba9bf6)

- New scenarios: `exchange2_step_open` 80 checks (Ctrl+O of a 3-part STEP assembly with a
  repeated wheel: names, nesting, copies, volumes, places, colours, browser, timeline; the
  copy follows its original; save + Ctrl+O reopen; File menu > Open of two free parts;
  IGES; SAT refused; broken STEP refused; Data Panel Upload / double-click / Insert),
  `exchange2_step_insert` 75 (Insert STEP into a design, the Move dialog, X 100, Ctrl+Z
  twice / Ctrl+Y twice, insert into an active component, Esc, a second insert, cancelled
  file dialog, broken file), `exchange2_export` 89 (STEP round trip with components and
  colours, IGES round trip, a component as 3MF in its frame, Save As DXF of a sketch on XZ
  read back, DXF of a clicked face, DWG refused, DXF with nothing picked refused, Save As
  Mesh), `exchange2_manip` 43 (SVG: X arrow, turn, scale, value box + Enter, undo / redo;
  Canvas: turn and Y in the insert, scale in Edit Canvas, Esc; DXF: X arrow, Cancel),
  `exchange2_link` 42 (Data Panel Insert into Current Design, Move X 30, undo / redo, Break
  Link and its undo / redo, a second linked insert, the design taken away: message,
  refused Break Link, menus): all PASS.
- Updated for the new behaviour: `insert_step` 30, `insert_svg` 38, `versions_link` 25: PASS.
- Also run: `insert_dxf` 35, `insert_canvas` 48, `insert_reopen` 24, `export_formats` 53,
  `export_print` 41, `export_everything` 27, `mesh_print` 33, `misc_decal` 54,
  `versions_data_panel` 30, `versions_save` 69, `ribbon_sweep` 214, `components_basic` 251,
  `timeline_browser` 92: all PASS. Unit `test_exchange_core` 17.
- `--only base`: unit 1138 OK, golden 403 pass + the known XFAIL `plate_hole_grid`, smoke
  71, journey 25: all pass.

## Gaps (also in the parity doc, Part 2)

- STEP keeps no body names inside a component (FreeCAD's writer has no names for a
  product's solids): they come back Body1, Body2.
- An inserted design's own components come in flat; a linked copy can be edited in place;
  no out-of-date icon or Get Latest (copies follow the saved design when this one opens).
- DWG untested (no converter in the sandbox); SAT / SMT / F3D / FBX / USD not read or
  written; McMaster-Carr not built (online catalogue; a downloaded STEP uses Insert STEP).
- DXF Z Angle direction and canvas Z Angle direction are guesses (counter-clockwise).
- The decal keeps its own manipulator (its scale arrow has no value box); not touched, so
  `fixdecal_*` stay as they are.
- `docs/sciforge/dev/remaining-gaps.md` still lists the insert-export gaps fixed here (not
  edited: a shared survey).
