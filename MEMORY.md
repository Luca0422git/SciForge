# SciForge memory and progress log

This file is the project's memory across work sessions. **Read it first, every session**, then
`docs/sciforge/feature-outline.md` (the spec). Update it at the end of every session: what was
done, what was learned, what is next. Newest session goes at the top of the log.

---

## Where things live

| What | Where |
|---|---|
| The spec (source of truth for scope) | `docs/sciforge/feature-outline.md` |
| This memory / progress log | `MEMORY.md` |
| SciForge's own module (workbench, timeline, search, ...) | `src/Mod/SciForge/` |
| Golden-model benchmark suite (step lists + runner) | `src/Mod/SciForge/SciForgeTests/golden/` |
| Every change to FreeCAD's own code (tagged `SCIFORGE:`) | `docs/sciforge/core-patches.md` |
| CI workflows (SciForge's own) | `.github/workflows/sciforge-*.yml` |
| Tooling scripts for CI / local runs | `tools/sciforge/` |
| Original "Forge" v0.1 prototype, kept verbatim for history | `prototype/forge-freecad/` |
| Upstream FreeCAD source | everything else (the fork base is tag `1.1.4`) |

## Fixed facts

- **Fork base:** FreeCAD tag `1.1.4` (commit `4fd3bf320d`), full upstream history kept so future
  FreeCAD releases can be merged (`git remote add upstream https://github.com/FreeCAD/FreeCAD.git`,
  then `git fetch upstream refs/tags/1.1.X:refs/tags/1.1.X` and merge the tag).
- **Repo:** `github.com/Luca0422git/SciForge`, **public** since 2026-10-10 (was private). Standard
  GitHub Actions runners are free for public repos, so pushing and full builds cost nothing; full
  C++ builds still take hours, so they run when started by hand (Actions tab → "SciForge build" →
  Run workflow) or by a `sciforge-v*` tag. Tests run on every push (~20 min).
- **History is 2.4 GB**: GitHub rejects a single push over 2 GB, so the initial import was
  pushed in 5 fast-forward stages. Normal pushes are small and unaffected.
- **License:** LGPL-2.1-or-later (inherited from FreeCAD). Keep FreeCAD copyright notices.
- **Owner:** Luca, a beginner at software engineering who tests, not codes. Explain plainly. Primary
  platform Windows 10/11, then Linux. No macOS.
- **Sandbox can run real FreeCAD**: the official FreeCAD 1.1.4 Linux AppImage downloads and runs
  headless (`freecadcmd`) *and* with a GUI on a virtual screen (`xvfb-run`). Use
  `tools/sciforge/get_freecad.sh` to fetch it. The 3D view renders blank under xvfb (no GPU),
  but widgets, toolbars, commands and geometry all work, and screenshots of the window work.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-09 | Fork at 1.1.4 with full history (not a flat copy) | Makes merging future FreeCAD releases a normal `git merge` |
| 2026-10-09 | Removed FreeCAD-org automation workflows (translations, stale bot, backport, labeler, CodeQL, scorecards, Fedora nightly, weekly release, dependabot); `CI_master.yml` made manual-only | They serve FreeCAD's organization, fail or waste minutes here; a weekly release cron would have run on our default branch |
| 2026-10-09 | SciForge module lives at `src/Mod/SciForge` and is installed by the normal CMake build | Ships inside every SciForge build; no separate add-on install step |
| 2026-10-09 | Golden models are JSON step lists run by a small interpreter in real FreeCAD | Same file runs in CI (headless) and can later be compared with Fusion reference metrics |
| 2026-10-09 | No SHEET METAL, PLASTIC or MANAGE tabs (Luca: "not for now") | Not used; out of scope |
| 2026-10-09 | Until the branding pass lands, CI's Windows build ships the portable 7z only, no installer | The FreeCAD NSIS installer would install over / clash with a real FreeCAD install |
| 2026-10-10 | Repository made public by Luca | Free GitHub Actions minutes for tests and full builds (was the open question on cost) |

## Status by phase (outline section 10)

### Phase 0: Foundations (in progress)

- [x] Fork FreeCAD 1.1.4 into the SciForge repo (full history)
- [x] Commit outline + Forge prototype
- [x] Disable upstream automation that does not apply
- [x] First real run of the prototype in FreeCAD 1.1.4 (GUI, under xvfb): found and fixed 2 bugs
- [x] SciForge module seeded from the prototype at `src/Mod/SciForge` (renamed, `[SciForge]` logs),
      built by CMake (`BUILD_SCIFORGE`, core patch #3)
- [x] Golden-model harness + 32 models with hand-derived expectations (31 pass on stock 1.1.4,
      1 = upstream bug fixed by core patch #4)
- [x] GUI smoke test in real FreeCAD under xvfb (14 checks, screenshot)
- [x] `tools/sciforge/run_tests.sh` runs all of it with one command
- [x] CI `sciforge-tests.yml`: unit + golden + GUI smoke on every push (against stock FreeCAD)
- [x] First `sciforge-tests.yml` run on GitHub is green (2026-10-09)
- [x] CI `sciforge-build.yml` written (manual): Windows portable 7z + Linux AppImage, then
      golden models run on the built SciForge
- [ ] First `sciforge-build.yml` run succeeds (never run yet: expect fixes; it is hours long)
- [ ] First CI build downloaded and launched by Luca on Windows
- [ ] Branding pass: app name, icons, user-data folder, installer (side by side with FreeCAD)
- [ ] Parity capture: Luca records Fusion workflows; behavior specs written + signed off
- [ ] Spike 9.1: Press/Pull feasibility report (OCC offset / local ops), with benchmark
- [ ] Spike 9.2: Fillet robustness benchmark + feasibility report
- [ ] Answers to the open questions in outline section 12

### Phase 1: The modeling core (started)

- [x] Interface shell, first pass (7.1): Fusion-style ribbon (tabs, groups, menus in Fusion's order,
      unavailable items greyed), dark theme with measured colours, 131 original icons in Fusion's
      visual style, quick-access bar, navigation bar, Fusion-style timeline with playback,
      contextual SKETCH tab, Fusion shortcut keys with clash handling, Revit mouse style (=Fusion).
      Spec + known gaps: `docs/sciforge/parity/ui-shell.md`. Not yet signed off by Luca.
- [x] Press/Pull v1 (7.0): faces push/pull (planar + cylindrical exact), edges -> fillet, fillet face ->
      radius; parametric feature in the timeline; dialog + drag arrow + live preview; 13 golden
      models (2 documented gaps: sloped neighbours, shared corners -> need C++ per-face offset, 9.1)
- [x] Fusion-style Extrude (E): join/cut/new body, one side/two sides/symmetric, distance/all,
      taper, drag arrow, auto-switch to Cut when dragged into material
- [x] Right-click marking menu (8 slots + list, Repeat last command). **Slot order unconfirmed.**
- [x] Browser panel with Fusion's structure (7.2), eye toggles, rename, activate
- [x] Change Parameters (7.4): user params (App::VarSet "Parameters"), model params, bare names
- [x] Construct presets (19 Fusion entries -> attacher modes; Offset Plane/Midplane computed)
- [x] Timeline marker drag + playback; ViewCube colours; 3D Print (3MF/STL) export
- [ ] Unified Revolve / Hole / Fillet dialogs Fusion-style (FreeCAD's dialogs used meanwhile)
- [ ] ViewCube shape, doc tabs in the app bar, floating command dialogs (Sketch Palette: done)
- [ ] Timeline: reorder by drag, suppress, groups (7.3)
- [ ] Sketcher parity (7.5): inference, glyphs, Fusion dimension tool feel (needs captures)
- [x] Sketch workspace, first parity pass (branch `sf/sketch`): Fusion keys in sketches (L R C D T
      X O P E, Esc / Esc), on-screen dimension box (type the value, Enter; double-click a
      dimension to change it), Finish Sketch always works (also with a tool running), Look At on
      entry + camera restored, SKETCH PALETTE (grid, snap, slice, profile, points, dimensions,
      constraints, projected geometry, construction, Look At), light-blue profile shading,
      Circumscribed/Inscribed Polygon without the sides pop-up, Offset/Trim like Fusion, Project /
      Include 3D Geometry, Mirror / patterns / scale / move starting with nothing selected,
      Rectangular Pattern panel, double-click a sketch in browser/timeline to edit it.
      7 scenarios (`sketch_*.py`), 3 golden models (`sketch_*`), core patch #7 (trim)
- [x] Hole (H) and Thread, Fusion-style (branch `sf/hole`): Single Hole where you click a face
      (flat or curved; hidden helper sketch "Hole N Sketch", X/Y fields, two edge references with
      distances, draggable blue centre dot), From Sketch points/circle centres (auto-flip into
      the part), Extents Distance/To/All, Simple/Counterbore/Countersink, Tap Type Simple/
      Clearance (ISO 273 / ASME B18.2.8 fits)/Tapped (ISO metric, UNC/UNF/UNEF, class, hand,
      Modeled, tap depth), Flat/Angle drill point, blue depth + diameter arrows. Thread on shaft
      or hole faces: size from the diameter, full/partial length (+ blue length arrow), cosmetic
      (dashed helix overlay, also for tapped holes) or modeled (own ISO 68-1 groove sweep,
      `thread_core.py`). 6 scenarios (`hole*.py`), 16 golden models (`hole_*`, `thread_*`).

## Known issues / findings

- **Lesson (2026-10-10): green tests, unusable product.** Luca's first real session: Create Sketch
  opened FreeCAD pop-ups, dragging the Extrude arrow crashed, Extrude ignored clicks on profiles
  and faces, a stuck dialog made E/Q/Create Sketch silently do nothing. The smoke test called
  SciForge code directly and never clicked. Rule now: **every interactive feature gets a step in
  `SciForgeTests/gui/journey_gui.py` driven by real mouse clicks/drags on the 3D view**, and a
  feature is not "done" until that passes. Click one step *after* the key that opens a task panel
  (the panel narrows the 3D view).
- CI quirks (GitHub runner, xvfb + software GL): a click on an outline edge can land on the face
  next to it (use `harness.click_edge`), and synthesized Ctrl+clicks lose their Ctrl there (use
  `harness.ensure_also_selected` after a Ctrl+click that must add to the selection). Both work on
  a desktop and in the local xvfb. A CI round takes ~20 minutes (free: the repo is public).
- **Trap: never keep a pivy handle to a FreeCAD-owned Coin node across time** (between timer
  ticks, until a dialog closes). FreeCAD deletes view-provider/edit nodes when it rebuilds a
  display or leaves sketch edit; writing to the stale handle segfaults (sketch_mode polygon
  preview, 2026-10-10; faulthandler showed pivy `__setattr__` -> `getField`). Look nodes up
  fresh (`sketch_mode.find_node`) each time, or hold a Coin reference (`node.ref()` /
  `node.unref()`, see `fillet_ui._Looks`). Debug crashes with Python's faulthandler (prints the
  Python stack on SIGSEGV) or gdb (`bt`).
- **Trap: pivy dragger callbacks crash FreeCAD** (`addMotionCallback`/`addFinishCallback`): pivy
  calls Python without the GIL (gdb: SIGSEGV in `SoDraggerPythonCB` -> `PyDict_New`), and doing a
  recompute or Pad<->Pocket swap inside Coin's event traversal is unsafe anyway. `ArrowDragger`
  polls the dragger with a QTimer instead. Use FreeCAD's `view.addEventCallback` (GIL-safe) for
  mouse events; defer real work from selection observers/event callbacks with
  `QTimer.singleShot`.
- FreeCAD 1.1 draws origin planes small and fixed-size: SciForge draws its own big squares while
  Create Sketch waits (`sketch_ui.PlanePicker`) and picks them by ray maths. From the isometric
  view (camera +x -y +z) the XZ square is in front of XY for y > 0, as in Fusion.
- Extrude profiles: sketches (click inside a shaded closed region, `profile_pick.py`) or a planar
  body face `(feature, "FaceN")` as Pad/Pocket `Profile` (FreeCAD supports face profiles).
  Distances are signed along the outward normal, so a cut into the part is negative (`flip`).

- Prototype bug (fixed in `src/Mod/SciForge`): `package.xml` lacked `<subdirectory>./</subdirectory>`,
  so FreeCAD 1.1 looked for `Forge/InitGui.py` and silently skipped the add-on. It would never have
  appeared on Luca's machine.
- Prototype bug (fixed): `Sketcher_External` no longer exists in 1.1. It is now
  `Sketcher_Projection` + `Sketcher_Intersection` (matches Fusion's Project / Intersect split).
- **Upstream bug (core patch #4):** `LinearPattern.Spacings2` defaults to `[0.0]`, so 2-direction
  linear patterns in Spacing mode stack row 2 on row 1. Fixed in C++ but **not yet compiled**:
  the first `sciforge-build.yml` run verifies it (golden `plate_hole_grid` must PASS there).
  Worth reporting upstream.
- FreeCAD API: `body.newObject()` does not move `Body.Tip` for pattern/mirror features (the GUI
  commands do it separately). The golden builder sets Tip explicitly. Anything SciForge builds
  from Python must do the same.
- Parity item: FreeCAD leaves split seam faces unless `Refine = True`; Fusion never shows them.
  SciForge features should default to refined. Golden models assume refined face counts.
- Sketch on XZ extrudes toward -Y in FreeCAD. Fusion's plane orientation differs (Y-up vs Z-up
  setting): needs a parity decision during the sketch behavior spec.
- OCC results matched the hand formulas for corner fillets (two fillets meeting a sharp edge),
  vertex blends (all-edge rounded box), chamfer corners, countersinks and shells: a good sign
  for 9.2, but these are easy cases. The real fillet benchmark (100+ hard cases) is still to do.
- **Editing a sketch switches FreeCAD to the Sketcher workbench** (and back after). So the
  SciForge interface is a "shell" (`shell.py`) that follows workbench changes instead of living in
  the workbench's Activated/Deactivated.
- **Trap:** FreeCAD's `ToolBarManager::saveState()` saves every toolbar's visibility on workbench
  switches. Hiding toolbars naively would hide them in plain FreeCAD forever. SciForge hides the
  toolbar's toggle action first (saveState skips those). Menu-bar visibility is not persisted.
- FreeCAD's Sketcher binds single letters (L, S, E, P, I, C, H, V, T...) to constraints. Fusion's
  keys win while SciForge is on; clashing FreeCAD keys are parked and restored (`shortcuts.py`).
- FreeCAD's "Revit" navigation style is exactly Fusion's default mouse mapping.
- The 3D view does render under xvfb in the GUI smoke test (screenshots show the part), the
  earlier blank view was just timing.
- **Quick updates**: SciForge is pure Python, so the CI artifact `SciForge-quick-update-<sha>`
  (made on every green `SciForge tests` run) + `install_update.ps1` replaces Mod\SciForge in
  Luca's portable build. Full builds only for C++ changes (core patches). Tell Luca when one is due.
- Installer lessons (Luca's Windows): a plain `.ps1` double-click closes at once, so start it via
  `install_update.cmd` (Bypass + pause). Renaming `Mod\SciForge` failed with "Access to the path
  is denied" (an open Explorer window/antivirus/OneDrive blocks folder renames), so the installer
  now copies files over the old ones, removes leftovers, backs up to `<SciForge>\SciForge-backups`
  (never inside `Mod`: FreeCAD loads every folder there) and self-elevates if the folder is not
  writable. Tested with pwsh as an unprivileged user (locked file, read-only folder).
- FreeCAD only honours a command's shortcut if the command is in a visible menu/toolbar. SciForge
  binds keys with QShortcut on the main window instead (`shortcuts.py`); GUI test presses real keys.
- FreeCAD saves dock visibility and toolbar state on exit: SciForge turns itself off on the main
  window's Close event (and back on if the close is cancelled). The browser lives *inside* the
  "Model" dock (its widget swapped), never hiding the dock.
- Preferences: SciForge records whether each preference existed and removes it again on exit
  (writing back GetBool's False default would have turned off FreeCAD's gradient for good).
- PartDesign::FeaturePython works as a timeline feature (Press Pull); its proxy class path is
  stored in files: keep `sciforge.presspull.PressPullFeature` stable.
- OCC's generic offset ("fill") gives BSpline end caps that do not merge with planar neighbours;
  build exact slabs for planes (prism) and cylinders (revolved ring).
- Sketch constraint expressions: path `.Constraints[i]` works; names with dots (base.width) do not.
- Attacher: AxisOfCurvature/CenterOfCurvature need a circular *edge*; SciForge maps a round face
  to its edge (Fusion lets you click the face).
- Fusion semantics still unknown (need parity capture before adding golden models): taper
  angle sign, chamfer two-distance side assignment, "intersect" and "new body" behavior.
- **Sketch mode architecture (sf/sketch)**: `sketch_mode.py` starts a `SketchSession` whenever a
  sketch goes into edit (Gui document observer) and ends it on reset: event filter on the 3D
  view (Esc, Enter, dimension double-click, ShortcutOverride so typed digits never reach view
  shortcuts), dimension box, profile shading (`sketch_regions.py`, generalFuse of the curves),
  palette (`sketch_palette.py`), polygon preview. Sketcher preferences it needs (Esc does not
  leave the sketch, no datum pop-up, Fusion colours, collapsed panel widgets) are set on enable
  and restored on disable. Settled work runs off the document's commit/abort/undo/redo signals.
- **Trap: FreeCAD notification balloons are not in the Report view.** Sketcher errors (malformed
  constraints, solver failures) go to `Gui::NotificationArea`; scenarios watch it
  (`sketch_input.watched`) and fail on any new message.
- **Trap: Sketcher creates constraint actions with single-letter shortcuts (C, T, E, P...) the
  first time a sketch opens**, after SciForge parked the clashing keys, so C/T/E/P went dead in
  sketches. `sketch_mode.repark_keys()` re-parks them on every sketch session.
- Ctrl+Z / Ctrl+Y did nothing (FreeCAD only honours shortcuts of visible menus and the menu bar
  is hidden): `config.SHORTCUTS` now binds Std_Undo/Std_Redo. Other Ctrl shortcuts (Ctrl+S,
  Ctrl+O...) are probably dead for the same reason: not checked yet.
- **Upstream bug (core patch #7):** trimming a line where it crosses a full circle at 0 degrees
  makes a Coincident with the circle's non-existent start point: malformed constraint, invalid
  sketch, error balloons. Python repair `sketch_fix.py` runs after every sketch commit.
- FreeCAD's polygon constraints (equal + tangent) can lean into a rhombus for even n; SciForge's
  polygons use equal sides + corners on a construction circle (`sketch_polygon.py`), checked
  for n = 3..12 at many rotations, 4 DoF like Fusion.
- FreeCAD topological naming: a sketch's projected *vertical* edge of a part loses its reference
  after the base sketch's dimension changes (horizontal/top-face edges survive). Not fixable in
  SciForge Python; known gap.
- `addRectangularArray(ids, vec, clone, rows, cols, constr, perpscale)`: rows go along `vec`,
  columns along `vec` turned -90 degrees and scaled, so a +Y second direction needs a negative
  `perpscale`.
- QTest quirks: `mouseDClick` on item views does not emit `itemDoubleClicked` (send press,
  release, DblClick, release by hand: `sketch_input.double_click_widget`); clicks in fast
  succession on the 3D view merge (one click per scenario step); a Coin search path dies with
  its action (keep node + parent, never the path: SIGSEGV otherwise).
- **Trap: a Gui document observer (`Gui.addDocumentObserver`) crashes FreeCAD** when its
  `slotChangedObject(vp, prop)` reads `vp.Object` while FreeCAD is still building that view
  provider (SIGSEGV in `ViewProviderDocumentObjectPy::getObject`). Use an App observer
  (`App.addDocumentObserver`, gets the document object; `Visibility` mirrors the eye).
- **Trap: long recomputes run other Qt timers.** While a recompute takes more than about a
  second (modeled threads), FreeCAD's progress bar processes events and swallows keys/clicks;
  timers (a scenario's next step, a dialog's preview timer) fire *inside* the recompute.
  Dialogs check `doc.Recomputing` and retry later; scenario steps after a slow recompute set
  `wait_ms`, like a person waiting for the busy cursor.
- QCheckBox only toggles when the click is on its box or text: `hole_steps.click_checkbox`
  clicks the box (a centre click on a wide form row does nothing).
- A click on a curved face reports a point on the drawn facets, up to ~0.1 mm inside the true
  surface: look faces up with a tolerance (`hole.base_face_at`) and snap the point onto the
  face (`hole.snap_to_face`); use the clicked face's own name when it is the base feature's.
- OpenCASCADE `makePipeShell`'s default tolerance (1e-4) makes a swept thread ~0.02 % off in
  volume; `thread._sweep` uses `Part.BRepOffsetAPI.MakePipeShell` with tolerance 1e-6 (same
  speed) and matches the hand formula to ~1e-8.
- FreeCAD Hole quirk: `updateDiameterParam` skips thread size index 0 (`threadSize > 0`), so
  `ThreadDiameter` is stale for M1x0.25 / #1 / #0 ... (the hole itself is right). Worth
  reporting upstream.
- Timeline Delete shows a deleted feature's profile sketch again (`timeline_ops._show_profile_
  again`). For a Single Hole that is its hidden helper sketch: `hole_ui._HelperGuard` hides it
  again; the next Single Hole removes such orphan sketches inside its own undo step.
- Single Hole helper sketches are listed in the browser's Sketches folder as "Hole N Sketch"
  (hidden); double-clicking one, or timeline "Edit Profile Sketch" on the hole, opens the Hole
  dialog (`SciForgeType = "HoleSketch"` + `hole_ui.EDITORS`).
- **Extrude/Press Pull QA findings (branch `sf/extrude_presspull-qa`)**, rules for every dialog:
  - FreeCAD's selection takes the left-button *release* and stops it there
    (`SoFCUnifiedSelection` sets handled): a `view.addEventCallback` never sees the release of
    a click that selected something. Pick on the press, and skip presses on a drag handle
    (`profile_pick.handle_at`, a Coin ray pick that finds an `SoDragger`), or a press on an
    arrow drops the sketch area behind it.
  - FreeCAD draws a body through its Tip, and a new feature hides the one before it. Code that
    removes a feature (not FreeCAD's Delete) must show the new Tip again
    (`extrude.show_tip`), or the whole part vanishes from the view.
  - Ctrl+Z with a dialog open made FreeCAD commit the preview and undo it under the dialog;
    Ctrl+S saved the half-made preview; closing the design left a dialog on a deleted document
    that blocked every later command. `preview.UndoCancels(panel)` handles all of these (and
    other designs' clicks are filtered out of picks). Use it in every feature dialog.
  - FreeCAD's Pad/Pocket silently ignore a taper up to a face and a Pad's up-to-last: the
    SciForge extrude feature (`ExtrudeFeature`, property `Operation`) builds those.
  - OpenCASCADE cannot offset a whole sphere ("no closed bounds"): Press Pull builds the shell.
  - `doc.commitTransaction()`/`abortTransaction()` leave the step name opened by
    `doc.openTransaction(name)` pending when nothing changed: the next change anywhere (even
    right after an Undo) opens a step under that name and the Redo list is lost. Close it
    with `App.closeActiveTransaction()` (`preview.end_transaction`). **`taskui.Panel` (shared)
    still has this for every other dialog.**
  - FreeCAD's Pad "up to shape" with a whole body fails ("please select faces") and an empty
    face list silently extrudes nothing: hand over the faces facing the extrusion
    (`extrude.facing_faces`).
  - FreeCAD's number field (QuantitySpinBox) silently drops a parameter name; formulas typed
    in Extrude/Press Pull fields go through `preview.FormulaInput` (expression on the feature).
    FreeCAD's own ExpressionBinding made a field read-only once it had a formula.
  - Not fixed (other owners): rolling the timeline marker (`timeline_ops._set_tips`) does
    not hide/show features, so the 3D view shows the wrong step after a roll; a sketch made
    on a face of another body goes into the active body (`sketch_ui.create_sketch`); the
    marking menu has no OK/Cancel while a command is open (Fusion has).
  - Scenario traps: in the iso view a point behind a wall or right behind an arrow is not
    clickable (compute what is in front); the disc at the bottom of a hole is only visible
    from the top.

## Questions waiting for Luca


(See outline section 12. Also:)

## Session log

### 2026-10-09: Session 1
- Forked FreeCAD 1.1.4 (latest stable) into the repo with full history, pushed in stages.
- Added outline and prototype verbatim; removed FreeCAD-org automation workflows.
- Got real FreeCAD 1.1.4 running in the sandbox (headless + GUI via xvfb).
- Ran the prototype for the first time in real FreeCAD; fixed 2 bugs (see Known issues).
- Created `src/Mod/SciForge` from the prototype (renamed), wired into CMake.
- Built the golden-model harness (schema, selectors, builder, runner) and 32 models;
  found and patched an upstream FreeCAD bug with it.
- Added GUI smoke test, `tools/sciforge/*.sh`, CI workflows, docs (`docs/sciforge/`).

### 2026-10-09: Session 1, part 2 (UI shell)
- Luca sent 5 screenshots of stock Fusion. Built the Fusion-style shell from them: `ribbon_config.py`
  (data), `ribbon_ui.py`, `theme.py`, `shell.py`, `navbar_ui.py`, new `timeline_ui.py`, icon
  generator `tools/sciforge/make_icons.py` (131 icons). GUI smoke test now 29 checks incl. sketch
  mode and clean switch-off; unit tests 53 (ribbon data checked against a snapshot of FreeCAD
  1.1.4's command list).
- Luca was compiling the first Windows build during this; result still unknown.

### 2026-10-09: Session 1, part 3 (big features)
- Luca asked for the big Fusion features and no more 4-hour waits. Added the quick-update path,
  then Press/Pull, Extrude, marking menu, Browser, Change Parameters, Construct presets, marker
  drag, ViewCube colours, 3D Print. Tests: 77 unit, 43 golden (+3 xfail), 70 GUI checks.
- Quick-update installer fixes after Luca's reports (closed at once; then "access denied" when
  renaming the old folder). See Known issues.
- Luca installed manually. Keeping `SciForge.old` inside Mod gave "'SciForgeWorkbench' already
  exists" (FreeCAD loads every Mod folder); told him to move it out. Then: "the icons are awesome,
  it really does feel like fusion". Asked him for the feedback list in Next steps 1.

### 2026-10-10: Session 1, part 4 (Luca's first real use: "pretty but nothing works")
- Reproduced in a real GUI with real mouse input: sketch pop-ups, arrow-drag crash (gdb), Extrude
  not taking clicks, silent commands. Fixed: Fusion-style Create Sketch (`sketch_ui.py`, big
  origin squares, click plane/face, no pop-ups), Extrude profile picking (`profile_pick.py`, click
  inside the shaded profile) and face extrude, crash-free `ArrowDragger` (QTimer), blue arrow,
  commands finish the open dialog instead of going silent (`commands.finish_open_dialog`),
  `find_body` (reopened files), deferred selection handling, copyable Diagnostics with the last
  200 SciForge messages. New GUI journey test (25 checks, real clicks/drags) + 2 golden models
  (face extrude join/cut). Tests: 77 unit, 45 golden (+3 xfail), 70 smoke, 25 journey.

### 2026-10-10: Sketch workspace parity (branch `sf/sketch`)
- Luca: "sketching on a shape works until I click finish sketch. I get errors EVERYWHERE."
  Rebuilt the sketch environment Fusion-style (see Phase 1 checkbox and Known issues):
  new `sketch_mode.py`, `sketch_palette.py`, `sketch_tools_ui.py`, `sketch_pick_ui.py`,
  `sketch_regions.py`, `sketch_polygon.py`, `sketch_fix.py`; core patch #7 (trim, not compiled).
- Every SKETCH command is now swept from its menu with curves present (`sketch_sweep.py`): no
  pop-up, no notification, no error, Esc keeps the sketch. 7 sketch scenarios with real input.
- Gaps left: Include 3D Geometry is a flat projection, greyed tools (Edge Polygon, 3-Point
  Rectangle, 2-Point/Tangent circles, Tangent Arc, Midpoint Line, Overall/Center Point Slot,
  Conic, Text, Project to Surface, 3D Sketch), M in a sketch still runs the part Move.

### 2026-10-10: Session 1, part 5 ("make it all work"; parallel feature agents)
- Luca's 2nd report: second extrude made the part disappear (leftover selection re-used the
  first sketch -> auto Cut; fixed: dialogs clear the selection, used+hidden sketches never taken
  from a stale selection), Finish Sketch crash (resetEdit with a sketch tool active -> FreeCAD
  segfault; fixed in Python via `commands.leave_edit` + core patch #6), face normals flipped
  twice (fixed), Ctrl+Z/Y/S/N/O/Del dead because the menu bar is hidden (now bound in
  `config.SHORTCUTS`).
- Test infrastructure: `SciForgeTests/gui/harness.py` (real clicks/keys/ribbon buttons; ANY
  Report-view error fails), scenarios in `SciForgeTests/gui/scenarios/` (luca_session,
  ribbon_sweep = every SOLID/SKETCH command, keys), `run_tests.sh --only scenarios /
  --scenario NAME`. Rules for feature work: `docs/sciforge/dev/feature-guide.md`.
- Parallel feature workflow (12 features, each in its own git worktree, branch `sf/<key>`):
  built and merged: extrude_presspull, sketch, timeline_browser, fillet. The full suite after the
  fillet merge found a reproducible FreeCAD crash (stale Coin node in sketch_mode, see Known
  issues) and a unit failure (one bad import disabled all commands); both fixed. CI green again
  at run #28 (commit 4313045a): that quick update has all four features. Then the org's monthly agent spend limit stopped all other agents.
  NOT built yet: hole (WIP, untested, on branch `sf/hole`), revolve, patterns, shell_draft,
  bodies, inspect, primitives, sweep_loft. The QA ("break and fix") stage ran for none of them.
  The workflow script and its feature list are in `tools/sciforge/workflows/fusion_features.js`
  and `fusion_features_args.json` (set "scratch"; drop the features already merged). In the same
  session it can resume with resumeFromRunId "wf_4a2277cc-81f". (The fillet build agent never
  returned a report; its committed branch was merged as is.)
- ribbon_sweep KNOWN list: only "Shell" left (shell_draft fixes it); remove when fixed.

### 2026-10-10: Hole and Thread (branch `sf/hole`)
- Continued the parked WIP patch (applied, reviewed, mostly rewritten; patch removed). New:
  `hole.py` / `hole_ui.py` (Fusion Hole), `thread.py` / `thread_ui.py` / `thread_core.py`
  (Thread, cosmetic overlay), `thread_tables.py` (ISO / ANSI sizes, checked row by row against
  FreeCAD 1.1.4's Hole), `hole_common.py` (selection boxes, selection gate, undo watch).
  Ribbon: Thread now runs `SciForge_Thread` (was greyed).
- Tests: scenarios `hole`, `hole_sketch`, `hole_tapped`, `hole_thread`, `hole_thread_inside`, `hole_edges`
  (only real input; volumes hand-derived, incl. a slab check of FreeCAD's own modeled tapped
  thread), 16 golden models (`golden/hole_ops.py`: ops hole_at, hole_points, thread), unit
  tests `test_thread_core.py`. Full suite on the branch: unit 134 OK, golden 99 pass + 1 xfail
  (plate_hole_grid, core patch #4 not compiled), smoke 70/70, journey 25/25, 26 scenarios PASS.
- Gaps (honest list): no Taper Tapped (NPT) tap type; "To" works out the depth when the dialog
  applies (does not re-measure if that face moves later); clearance holes by thread size only
  (no fastener types); thread class is recorded, the modeled thread uses the basic profile;
  cosmetic threads are a dashed helix, not a texture; a hole on a curved face keeps its spot
  (helper sketch placed in the body, not attached to the face); depth is measured to the
  drill point's shoulder (Fusion's default to confirm with Luca).
### 2026-10-10: QA of Extrude and Press Pull (branch `sf/extrude_presspull-qa`)
- 7 new scenarios `extrude_presspull_qa*.py` (28 paths, real input only) found and fixed:
  a press on the drag arrow dropped the sketch area behind it; after a New Body switch or
  dropping the only pick the whole part vanished (hidden Tip); Ctrl+Z in a dialog left it
  working on deleted objects; Ctrl+S saved a half-made preview; closing a design under a
  dialog blocked every later command; clicks in another open design were taken as picks;
  To Object a body extruded nothing; an unchanged dialog threw away the Redo list; a
  double-click on the timeline icon of the step being made printed a ReferenceError
  (one-line guard in `taskui.edit_object`); Press Pull only worked on the active body; a
  ball's face could not be Press Pulled; "To Object" showed a warning while waiting.
- New Fusion behaviour: taper with To Object / join through All (SciForge's
  `ExtrudeFeature`, property `Operation`); parameters and formulas typed in Extrude and
  Press Pull fields; Enter is OK over the 3D view; clicking the end of a preview drops the
  profile it came from; Symmetric no longer offers To Object. 3 golden models (tapers).

## Next steps (in order)

1. Finish the feature workflow (see session log, part 5): revolve, patterns, shell_draft, bodies,
   inspect, primitives, sweep_loft (hole: done on `sf/hole`, merge after its full-suite run);
   then the QA stage for all 12 (including the 4 already merged). Merge each only after the full
   suite passes locally.
2. Luca installs the newest green quick update and redoes his session; ask for the copyable
   SciForge > Diagnostics text whenever something misbehaves, and the Fusion right-click menu
   screenshot (slot order).
3. Full Windows build to get core patches #4, #6, #7 compiled (CI `sciforge-build.yml`); check
   golden `plate_hole_grid` PASS there.
4. Get answers to outline section 12 + parity captures of Luca's Fusion workflows (2.4).
5. Spike 9.2 (Fillets): 100+ case benchmark from real part workflows, success-rate metric.
6. Branding pass (app name, icons, user-data folder, installer) so CI can ship an installer.
7. Grow golden models toward 100 (gear, bottle loft+shell, sweep pipe, snap-fit, hinge, threads).
