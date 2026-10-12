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
- [x] `sciforge-build.yml` runs: #1 (2026-10-09) green; #2 (2026-10-12) compiled and packaged on
      Windows and Linux (core patches #4, #6, #7 compile; golden `plate_hole_grid` PASS on the
      build) but its tests failed: the install rules listed 35 of 116 SciForge modules. Fixed
      (glob + `tools/sciforge/check_install.sh` on every push); a new run is needed.
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
- [x] Right-click marking menu (8 slots + list, Repeat last command; OK/Cancel while a command
      is open). **Slot order unconfirmed.**
- [x] Browser panel with Fusion's structure (7.2), eye toggles, rename, activate
- [x] Change Parameters (7.4): user params (App::VarSet "Parameters"), model params, bare names
- [x] Construct presets (19 Fusion entries -> attacher modes; Offset Plane/Midplane computed);
      replaced by the CONSTRUCT / INSPECT pass below (branch `sf/inspect`)
- [x] Timeline marker drag + playback; ViewCube colours; 3D Print (3MF/STL) export
- [ ] Unified Revolve / Hole / Fillet dialogs Fusion-style (FreeCAD's dialogs used meanwhile)
- [ ] ViewCube shape, doc tabs in the app bar, floating command dialogs (Sketch Palette: done)
- [x] Timeline: reorder by drag, suppress, groups (7.3); QA pass done (branch
      `sf/timeline_browser-qa`, 4 QA scenarios, spec `docs/sciforge/parity/timeline-browser.md`)
- [ ] Sketcher parity (7.5): inference, glyphs, Fusion dimension tool feel (needs captures)
- [x] Sketch inference in Python (plan C1-C4, branch `worktree-agent-a27127a70299bdc90`,
      `sketch_infer.py` + `sketch_infer_core.py`): Ctrl = no snaps / no automatic
      constraints (all drawing tools); in Line (L) dashed alignment guides from the last 3
      hovered points + the tool's own points (Vertical/Horizontal point-to-point
      constraint on click, option), perpendicular from/onto a line with a right-angle
      mark, level/upright within 4 degrees, parallel (off by default). Feasibility answer:
      **works in Python** by rewriting the mouse position FreeCAD gets (no C++ needed).
      Scenario `sketch_infer` (222 checks), 33 unit tests. Tolerances, guide look and the
      constraint on click are **unconfirmed** against real Fusion (plan checks 3-6)
- [x] Sketch workspace, first parity pass (branch `sf/sketch`): Fusion keys in sketches (L R C D T
      X O P E, Esc / Esc), on-screen dimension box (type the value, Enter; double-click a
      dimension to change it), Finish Sketch always works (also with a tool running), Look At on
      entry + camera restored, SKETCH PALETTE (grid, snap, slice, profile, points, dimensions,
      constraints, projected geometry, construction, Look At), light-blue profile shading,
      Circumscribed/Inscribed Polygon without the sides pop-up, Offset/Trim like Fusion, Project /
      Include 3D Geometry, Mirror / patterns / scale / move starting with nothing selected,
      Rectangular Pattern panel, double-click a sketch in browser/timeline to edit it.
      7 scenarios (`sketch_*.py`), 3 golden models (`sketch_*`), core patch #7 (trim)
- [x] Sketch QA pass (branch `sf/sketch-qa`): L takes typed length/angle and chains lines
      (`sketch_line.py`), dimension box refuses 0/negative/text, redundant dimension -> driven,
      sketch fillet radius box, right-click sketch marking menu (`sketch_marking.py`), M / Del /
      Ctrl+C/X/V on sketch curves, construction mode shown in the palette, palette keeps no
      keyboard focus, one Ctrl+Z after Finish Sketch, curved faces refused by Create Sketch,
      typed circumscribed polygon size fixed, FreeCAD balloons off, one Enter after a typed
      value draws the line/rectangle/polygon, constraint tools with an unfitting selection
      start and wait for picks (`SciForge_Sketch<Constraint>` in the ribbon), sketch keys
      work with a real keyboard (in the view and in FreeCAD's value fields). Spec:
      `parity/sketch.md`. Scenarios `sketch_qa.py` (12 paths), `sketch_qa_part.py`,
      `sketch_qa_keys.py`
- [x] Hole (H) and Thread, Fusion-style (branch `sf/hole`): Single Hole where you click a face
      (flat or curved; hidden helper sketch "Hole N Sketch", X/Y fields, two edge references with
      distances, draggable blue centre dot), From Sketch points/circle centres (auto-flip into
      the part), Extents Distance/To/All, Simple/Counterbore/Countersink, Tap Type Simple/
      Clearance (ISO 273 / ASME B18.2.8 fits)/Tapped (ISO metric, UNC/UNF/UNEF, class, hand,
      Modeled, tap depth), Flat/Angle drill point, blue depth + diameter arrows. Thread on shaft
      or hole faces: size from the diameter, full/partial length (+ blue length arrow), cosmetic
      (dashed helix overlay, also for tapped holes) or modeled (own ISO 68-1 groove sweep,
      `thread_core.py`). 6 scenarios (`hole*.py`), 16 golden models (`hole_*`, `thread_*`).
- [x] Hole / Thread QA pass (branch `sf/hole-qa`): Enter over the view = OK, Ctrl+Z cancels
      / Ctrl+S finishes first (`preview.UndoCancels`), formulas and parameters in every value
      field, Redo list kept after an unchanged dialog, Extents To follows its face
      (`hole.HoleToDistance` helper), hole that misses the part refused, arrows stop at sane
      limits, timeline edits with a person's double-click, picks only from the dialog's own
      design, OK/Cancel/other keys wait for a running recompute, a thread's lost face found
      again by geometry. 4 QA scenarios (`hole_qa*.py`, 28 paths), golden
      `hole_to_face_follows`. Spec: `parity/hole-thread.md`.
- [x] Fusion-style Revolve (branch `sf/revolve`, `revolve.py` / `revolve_ui.py`): profile =
      sketch areas or flat faces; axis = origin axis (drawn as long X/Y/Z lines to click),
      sketch line, construction line (drawn dashed), straight part edge, construction axis;
      Type Angle / Full; One Side / Two Sides / Symmetric (per side, like Fusion's API); blue
      handle(s) dragged round the axis; Join / Cut / Intersect / New Body with auto Cut when
      the revolve goes mostly into material (Revolution <-> Groove swap); timeline edit;
      the interim "Revolve (Cut)" ribbon entry removed. 3 scenarios (`revolve_*.py`), 12
      golden models (`sf_revolve_*`, ops `sf_revolve` / `sf_revolve_edit`).
- [x] Revolve QA pass (branch `sf/revolve-qa`): Type **To** (origin planes drawn as squares
      to click, flat faces, edges, corners, construction planes/points; follows the object via
      the hidden `revolve.RevolveTo` helper; Join and Cut), Enter over the view = OK, Ctrl+Z
      cancels / Ctrl+S finishes first, formulas and parameters in the angle fields, Redo list
      kept, numbers typed over the 3D view go into the angle box, face profiles found again
      after earlier edits (`revolve.FaceLink`), Join <-> Cut keeps later steps' links, origin
      axes hidden behind the part, honest messages for cuts that miss / remove everything /
      have no solid. 5 QA scenarios (`revolve_qa*.py`, 25 paths), 5 new golden models
      (`sf_revolve_to_*`, `sf_revolve_face_profile_follows`). Spec: `parity/revolve.md`.
- [x] Rectangular Pattern, Circular Pattern, Pattern on Path, Mirror, Fusion-style (branch
      `sf/patterns`): Pattern Type Features (FreeCAD's LinearPattern/PolarPattern/Mirrored,
      dress-ups included; a face click takes the feature that made it) / Faces (SciForge's
      `PatternFeature` closes the faces into the hole or boss they bound) / Bodies (one new body
      per copy; Mirror: New Body or Join). Quantity, Distance, Extent/Spacing, One Direction/
      Symmetric per direction, Direction 2 offered at right angles, Full/Angle/Symmetric,
      Identical/Path Direction, Suppression (click the dot on a copy); origin axes and planes
      drawn to click; blue arrows and a curved angle handle; parameters/formulas; live preview;
      errors in the dialog; timeline edit.
      Spec + gaps: `docs/sciforge/parity/patterns.md`. 6 scenarios (`patterns*.py`), 16 golden
      models, unit tests `test_pattern_core.py`. Ribbon: Pattern on Path now runs
      `SciForge_PatternOnPath` (was greyed).
- [x] Fusion-style Shell, Draft, Scale (branch `sf/shell_draft`; spec + gaps in
      `docs/sciforge/parity/shell-draft-scale.md`). Shell (`shelling.py` / `shell_ui.py`):
      faces to take away or the body (hollow), Inside / Outside Thickness, Direction Inside /
      Outside / Both, Shell Type Sharp / Rounded, Tangent Chain, blue arrows, too-thick walls
      explained with the thickest that fits; FreeCAD's Thickness where it can, SciForge's
      `ShellFeature` for hollow/Both (swapped in place). Draft (`drafting.py` / `draft_ui.py`):
      Fixed Plane (origin squares or a flat face), pull arrow + Flip, faces, Tangent Chain,
      angle field + curved handle, on FreeCAD's Draft. Scale (`scale.py` / `scale_ui.py`):
      SciForge's `ScaleFeature` in the body, Uniform / Non Uniform about the origin or a
      corner, arrows that move with the part. Shared dialog base `pickpanel.py`. Ribbon: Scale
      now runs `SciForge_Scale` (was greyed). 6 scenarios (`shell_draft*.py`), 20 golden models
      (`sf_shell_*`, `sf_draft_*`, `sf_scale_*`), unit tests `test_shell_draft_core.py`.
- [x] Shell / Draft / Scale QA pass (branch `sf/shell_draft-qa`, 11 bugs fixed): later steps
      keep their faces when a shell/scale/draft is edited (`follow.py`), a 1 mm cup wall is no
      longer "too thick", arrows can always be grabbed, Draft's Pull Direction box and
      clickable pull arrow, Change Parameters lists Shell / Scale values. 4 QA scenarios
      (`shell_draft_qa_shell/_draft/_scale/_mix.py`, 25 paths), 4 golden models.
- [x] Body tools, Fusion-style (branch `sf/bodies`): Combine (Target / Tool Bodies, Join /
      Cut / Intersect, New Body, Keep Tools; used-up tools hidden while the step is part of
      the design), Split Body (origin/construction plane, face with Extend Splitting Tool,
      another body; every piece a body), Move/Copy M (Free Move with an on-top manipulator:
      3 arrows + 3 turn handles; Translate; Rotate about an axis with a blue handle; Point to
      Point snapping to corners; typed distances/angles; Create Copy), Delete Del (bodies,
      steps with dependants re-linked or flagged, faces -> "Delete Face" step, sketch curves),
      Appearance (library + custom colour, bodies or faces, drag a swatch onto the part),
      Physical Material (FreeCAD's library, mass shown; `bodies.mass()` for Inspect).
      Split Body also takes sketch lines/arcs; Move also Point to Position. Deleting keeps
      dependants working (fillets re-pointed at the step before, Combines/copies re-routed,
      a deleted tool body kept frozen in its Combine).
      `bodies.py` helpers for every multi-body tool. Spec + gaps: `docs/sciforge/parity/
      bodies.md`. 6 scenarios (`bodies_*.py`), 24 golden models (`bodies_*`), unit tests
      `test_bodies_schema.py`. Ribbon: Split Body runs `SciForge_SplitBody` (was greyed).
- [x] Fillet (F) and Chamfer, Fusion-style, plus a QA pass (branch `sf/fillet-qa`): picks of
      edges / faces / timeline features, Tangent Chain, blue arrows, live preview, errors in
      the dialog, timeline edit; QA added mm-safe value boxes with parameters/formulas,
      Ctrl+S/N/O finishing the dialog, later fillets kept on their edges after an insert or
      an edit (`blend.References`), two-solid bodies, angle limits. Spec + gaps:
      `docs/sciforge/parity/fillet.md`. Scenarios `fillet*.py` (8 files), 10 golden models
      `blend_*`, unit tests `test_blend_core.py`.
- [x] CONSTRUCT and INSPECT, Fusion-style (branch `sf/inspect`; spec + gaps in
      `docs/sciforge/parity/inspect.md`). CONSTRUCT (`construct.py` / `construct_ui.py`): all
      19 menu entries (8 planes, 5 axes, 6 points) in one dialog kind: boxes that wait blue,
      origin squares / axes / point drawn to click while a box waits, pre-selection used, live
      datum, blue arrow (Offset Plane), curved handle (Plane at Angle, Tangent Plane), sliding
      dot (Along Path), parameters/formulas, timeline edit, errors in the dialog. The
      "Perpendicular Plane" placeholder became Fusion's "Plane Tangent to Face at Point".
      Construction geometry works in Create Sketch, Extrude To Object, Revolve's axis and other
      constructs; editing a plane moves what is built on it. Measure (I, `measure.py` /
      `measure_ui.py`): one or two picks, minimum distance, angle, delta X/Y/Z, area, length,
      volume, position, radius; Selection Filter, Precision, Show Snap Points, click to copy,
      design units. Section Analysis (`section.py` / `section_ui.py`): face/plane, distance
      arrow, X/Y angle handles, Flip, colour + hatch, stored in the browser's Analysis folder
      (eye shows/hides). Center of Mass (`analysis.py` / `com_ui.py`) and Interference
      (`interference_ui.py`): stored in the Analysis folder, follow the design. 7 scenarios
      (`inspect*.py`), 6 golden models (`inspect_*`), unit tests `test_inspect_core.py`. Ribbon:
      Interference and Center of Mass now run SciForge commands (were greyed). QA pass
      (branch `sf/inspect-qa-2`, 5 scenarios `inspect_qa*.py`, 35 paths): Measure inside a
      sketch (I keeps the sketch open), Center of Mass weighted by Physical Material and
      measurable, one Enter after a sum, picks through what the box cannot take, held
      handles, deleted references (warnings, no errors), see the session log. Third QA round
      (branch `sf/inspect-qa-3`, `inspect_qa6..8`, 17 more paths, 52 in all): a handle let go
      over the part is never a pick, typos in value boxes keep the dialog open, Section
      takes parameters, the construction being edited never takes a click, golden
      `inspect_three_points_oblique_hole`.
- [x] Box, Cylinder, Sphere, Torus, Coil, Pipe, Fusion-style (branch `sf/primitives`; spec +
      gaps in `docs/sciforge/parity/primitives.md`). Pick an origin plane (squares) or a flat
      face, place with the mouse (Box: two corners with a rubber band; Cylinder / Torus /
      Coil: centre + a point on the circle; Sphere: centre), blue on-top arrows for the sizes,
      Operation Join / Cut / Intersect / New Body picked by itself from where the shape is.
      Clicks snap to the origin, corners, sketch points and circle centres on the plane.
      Coil: 4 types, rotation, angle, 4 sections x 3 positions. Pipe: sketch or model edges
      with Chain Selection, Distance handle, 3 sections, Hollow. Parameters typed in the fields
      keep driving the shape. On FreeCAD's PartDesign primitives / Helix / Pipe (+ SciForge
      FeaturePython steps for Intersect). Ribbon: Pipe runs `SciForge_Pipe` (was greyed).
      5 scenarios (`primitives_*.py`), 25 golden models (`sf_box_*`, `sf_cylinder_*`,
      `sf_sphere_*`, `sf_torus_*`, `sf_coil_*`, `sf_pipe_*`), unit tests
      `test_primitives_core.py`.

- [x] Sweep, Loft, Rib and Web, Fusion-style (branch `sf/sweep_loft`; spec + gaps in
      `docs/sciforge/parity/sweep-loft-rib.md`). Sweep (`sweep.py` / `sweep_ui.py`): Single
      Path / Path + Guide Rail, profile = sketch area or flat face, path/rail = sketch curves
      or part edges with Chain Selection, profile anywhere on the path (Distance / Distance
      One + Two, blue balls), Orientation, Taper, Twist, Profile Scaling, Join / Cut /
      Intersect / New Body with auto Cut. Loft (`loft.py` / `loft_ui.py`): ordered profiles
      (areas, faces, points; up / down / remove), Rails / Centerline, Closed, operations.
      Rib and Web (`rib.py` / `rib_ui.py`, FreeCAD has neither): Symmetric / One Side,
      Thickness and Depth arrows, To Next / Depth, Flip, Extend Curves. FreeCAD's own Pipe /
      Loft when they give Fusion's result, SciForge's FeaturePython otherwise (swapped in
      place on edit). Shared: `curves.py`, `curve_pick.py`. Ribbon: Rib and Web enabled (two
      lines). 7 scenarios (`sweep_loft_*.py`), 35 golden models (`sf_sweep_*`, `sf_loft_*`,
      `sf_rib_*`, `sf_web_*`). Gaps: Tangent Edges Merge, Path + Guide Surface, loft end
      conditions.
      `SciForge_PatternOnPath` (was greyed). QA pass done (branch `sf/patterns-qa`): 17 paths
      in 5 more scenarios (`patterns_qa_*.py`), 8 bugs fixed (see Known issues).
- [x] Sweep / Loft / Rib / Web QA pass (branch `sf/sweep_loft-qa`, 12 bugs fixed): editing a
      sweep / loft into the other kind of feature keeps the steps built on it (was refused),
      the Redo list survives a dialog opened and cancelled, a sweep / loft away from the part
      is a New Body, New Body shown from the start, a path clicked first leaves the Profile
      box waiting, a path in the profile's plane explained, web extensions stop at thin walls,
      Create Sketch on a construction plane in front of an origin square, loft sections no
      longer offered as unused profiles, the reason of a menu command shown, picked part
      edges / faces found again after FreeCAD loses their names (sweep, loft, Press Pull).
      5 QA scenarios (`sweep_loft_qa_sweep/_loft/_rib/_web/_part.py`, 21 paths), golden
      `sf_web_depth_thin_wall`.
- [x] Body tools QA pass (branch `sf/bodies-qa`): 12 problems fixed (used-up body left active,
      Combine edit hiding its tools, tool clicks swallowed by the Join preview, Move type
      chosen first eating the body click, browser/timeline Delete breaking Combines, New Body
      target deletion, reopened files activating a used-up body, round-edge snap to the
      circle seam, face looks lost on Move, lavender instead of grey, materials not
      draggable, a failed step showing its old result). Scenarios `bodies_qa.py` (8 paths) and
      `bodies_qa_2.py` (10 paths), golden
      `bodies_combine_new_body_target_deleted`.

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
  linear patterns in Spacing mode stack row 2 on row 1. Fixed in C++, compiled in build run #2
  (2026-10-12: `plate_hole_grid` PASS on the Windows build); earlier note:
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
- **Sketch inference in Python (2026-10-12, `sketch_infer.py`)**: FreeCAD snaps in C++ from
  the mouse pixel, but SciForge's filter on the 3D view's drawing area runs first: it can
  swallow a mouse event and `sendEvent` a copy with another position, and FreeCAD's own
  tool then lands exactly on that pixel (probe: created point = pixel's sketch point to
  1e-7 mm). Pixel -> sketch point the way FreeCAD does it: coin = (x * ratio,
  (height - y - 1) * ratio), then ray to the sketch plane (`_ViewMap`). Per-event
  switches are read live: `Mod/Sketcher/Snap/Snap` (master snap, also kills Ctrl's
  5-degree steps), `Snap/SnapToGrid`, the sketch's `ViewObject.Autoconstraints` (no undo
  entry), `view.getViewer().setPickRadius()`. Traps found:
  - **FreeCAD's click jumps to a point marker under the mouse before any snapping**
    (`ViewProviderSketch::mouseButtonPressed` uses the picked point): with Snap off a Ctrl
    click still landed on the end point; shrinking the pick radius for that click fixes it.
  - Autoconstraints off during a click that *finishes* a line also drops the constraints
    of its start (they are generated at the end): SciForge turns it back on in the
    synchronous commit signal of "Add sketch line" (before "Add Auto-Constraints").
  - FreeCAD 1.1 Python: `sketch.moveGeometry(geo, pos, Vector, False)` (no `movePoint`);
    `sketch.GeometryCount` is cheap (`len(sketch.Geometry)` copies every curve).
  - The line tool's preview is the Coin node `EditCurvesCoordinate` (2 points while the
    second point is sought, sketch-local); look it up fresh each time (find_node).
  - FreeCAD snaps to a line's middle within 5% of its length: inference must not fight it.
  - **Keep FreeCAD's grid snap on for the moved event whenever it cannot pull the point off
    the inference** (`sketch_infer_core.grid_off`): switching it off for every level line
    broke `sketch_modify`, `sketch_qa` K and `sketch_qa_keys` R2 (ends at 19.934 instead of
    20; with a typed length FreeCAD drops its own H/V, so the pixel's direction was used).
    When it must be off, the grid spacing is recomputed in Python (`_grid_size`) and the
    exact value is put in after the click (`exact_point`).
  - QTest's mouse *moves* drop keyboard modifiers in Qt 6.8 (send a QMouseEvent with
    `sendEvent` for Ctrl-held moves, `sketch_input.move_held`); under xvfb the real X
    pointer stays elsewhere and stray hover events land there: scenarios that read hover
    state move it too (`QCursor.setPos`, scenario `sketch_infer.move`).
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
    with `App.closeActiveTransaction()` (`preview.end_transaction`; `taskui._end_transaction`
    for every `taskui.Panel` dialog since c76d6ac7d2).
  - FreeCAD's Pad "up to shape" with a whole body fails ("please select faces") and an empty
    face list silently extrudes nothing: hand over the faces facing the extrusion
    (`extrude.facing_faces`).
  - FreeCAD's number field (QuantitySpinBox) silently drops a parameter name; formulas typed
    in Extrude/Press Pull fields go through `preview.FormulaInput` (expression on the feature).
    FreeCAD's own ExpressionBinding made a field read-only once it had a formula.
  - Fixed since (main branch): rolling the timeline marker shows exactly the step at the
    marker (`timeline_ops._show_only_tip`, scenario `timeline_roll_view`); a sketch on a face
    or plane of another body goes into that body and makes it active
    (`sketch_ui.create_sketch`, scenario `sketch_other_body`); the marking menu offers OK
    (top slot) and Cancel (first list row) while a dialog is open (`taskui.dialog_button`
    clicks FreeCAD's own panel button, scenario `marking_menu_command`); E pressed while a
    sketch is open extrudes that sketch even when an extrude already uses it (it took "the
    newest unused sketch" instead; `ExtrudePanel(sketch=...)`, scenario
    `extrude_from_edited_sketch`).
- **Marking-menu list rows never ran their command** (found 2026-10-11): `_list_clicked`
  closed the menu first (WA_DeleteOnClose deletes it and the row's QAction) and PySide
  silently drops a `QTimer.singleShot(0, action.trigger)` whose QObject is gone. The menu is
  now hidden, the action triggered, then closed. Trap for everything: a singleShot to a
  bound method of a Qt object is cancelled when that object is deleted.
- **A scenario that fails to import kept FreeCAD open for the runner's 15-minute timeout.**
  run_tests.sh now starts scenarios through `SciForgeTests/gui/scenario_launcher.py`, which
  writes a failed result ("the scenario file loads") and quits. Scenarios import QtTest
  from `PySide6` (FreeCAD's `PySide` shim has no QtTest).
- **FreeCAD 1.1 floats the Tasks panel over the 3D view (its "overlay") with title bars of
  its own**: an empty "Tasks" header with 3 buttons stayed over the view with no command
  open (FreeCAD auto-hides an overlay only when it holds 2+ panels) and a white strip sat
  above every dialog. `shell._hide_overlay_titles` keeps overlay title bars at zero height
  (FreeCAD re-shows them and builds new ones, so an event filter on the overlay containers
  flattens new ones). Docked panels use the same `Gui::OverlayTitleBar` class (the BROWSER
  header): only bars inside `Gui::OverlayTabWidget`/`OverlaySplitter` are flattened.
  Scenario `overlay_title` (fails without the fix, checked).
- **Failed preview vs. refused value (rule since the timeline QA merge)**: a step whose
  compute fails adds nothing, also inside its own dialog (`timeline_ops.settle` passes the
  step before it through; the dialog says why and OK waits), like Fusion. A value the
  dialog refuses before applying it (fillet radius, shell thickness, scale factor) keeps
  the last good preview. `patterns_path` expected the old FreeCAD behaviour (a failed step
  keeps its old shape) and was updated.
- **Value boxes: a plain number is mm (or degrees), always** (2026-10-11, all dialogs via
  `taskui.DistanceField`): FreeCAD's QuantitySpinBox reads a bare number in the unit it
  *shows*; after a value below 0.1 mm it showed µm and "4" became 4 µm. `autoNormalize`
  stays ON: switched off, the box re-read its own rounded text on focus-out ("12.57" for
  4*pi, caught by patterns_qa_paths), so the first Enter after a sum ("2*0.25") only
  evaluates it and a second Enter is OK (known small gap). Trap found while fixing it: leaving a box "finishes" it, also while its dialog closes, so anything
  connected to `editingFinished` must not report to a closed dialog (`Panel._recompute`
  now returns once closed). Scenario `value_box_units`.
- Timeline Delete of a body's last step hid the whole part: FreeCAD moves the Tip back by
  itself, so `_set_tips` saw nothing to do and the new Tip stayed hidden. `delete()` now
  shows each touched body's Tip (`fillet_qa_more` P19 checks it).
- Bodies used up by a Combine (no Keep Tools) are no longer listed in the browser, like
  Fusion (`browser_ui._used_up_bodies`, `bodies.consumed`); while a body-tool dialog is
  open (`bodies.PAUSED`) they stay listed so they can be picked. `bodies_combine` checks it.
- Browser: an analysis (Section, Center of Mass, Interference) is edited by double-click or
  right-click Edit Feature, like Fusion (found by the inspect agent; `inspect_section`).
- Create Sketch on a flat face attaches to the step that made the face (`hole.earliest_face`,
  `sketch_ui._earliest`), not to the last step (a hole drilled in it): suppressing an
  unrelated earlier hole no longer takes the sketch and what is built on it along.
  Scenario `sketch_earliest_face` (found by the hole QA). Dialog `_recompute` methods return
  once the dialog is closed (all but revolve_ui, which its QA pass owns).
- Open question for Luca: a Single Hole's hidden helper sketch is listed in the browser as
  "Hole 1 Sketch" (double-click opens the hole); Fusion lists no sketch for a single hole.
- `tools/sciforge/make_icons.py` empties the icon folder before writing: the hand-drawn
  `palette_check.svg` (check-box tick) would have been deleted; it is now in its `RAW` table.
  - Scenario traps: in the iso view a point behind a wall or right behind an arrow is not
    clickable (compute what is in front); the disc at the bottom of a hole is only visible
    from the top.
- **Coin draggers cannot be grabbed behind the part** (Coin gives a click to the nearest
  object only). The revolve handle sat behind the preview solid at 90 degrees and could not
  be dragged. `revolve_ui.AngleHandle` is drawn in an `SoAnnotation` (on top) and handles the
  mouse itself: FreeCAD's `view.addEventCallback` only records the mouse, a QTimer applies
  it (no pivy callbacks). Revit-style left drag does not move the camera, so this is safe.
- Revolve facts (FreeCAD 1.1.4): a positive Angle turns right-handed about the reference's
  own direction (origin axis = +X/+Y/+Z, edge = its curve direction, construction line =
  start -> end), Reversed flips it. `Midplane` splits the whole angle; `TwoAngles` turns
  Angle one way and Angle2 the other and **silently gives a wrong solid when the two add up
  to more than 360** (SciForge refuses that in the dialog). `Groove` with `UpToFace` returns
  an **empty solid without any error** (volume 0, both directions), so Fusion's Type "To"
  does not use UpToFace: the hidden `revolve.RevolveTo` helper measures the angle from the
  profile to the object on every recompute and the revolve's Angle / Reversed follow it by
  expressions (`abs(RevolveTo.Angle)`, `RevolveTo.Angle < 0 ? 1 : 0`; a ternary works on a
  PropertyBool). A disjoint Join is accepted (a body with two lumps, like Fusion's).
- Revolve QA findings (branch `sf/revolve-qa`):
  - FreeCAD 1.1.4 loses a face's name ("?Face7", "missing element reference") when an
    earlier step renumbers faces, and also loses vertex names after a sketch edit. A face
    profile goes through `revolve.FaceLink` and a To object through `revolve.RevolveTo`;
    both remember where the element is and find it again by place (then by name, then the
    nearest one). Store element memory, not only `PropertyLinkSub` names.
  - Swapping Revolution <-> Groove makes a new feature: later steps that link its faces or
    edges are moved to the new one by geometry (`revolve._relink_users`) before the old one
    is removed; only moving to a new body is still refused when something uses it.
  - A formula on a feature that reads a helper must not be read back as the user's formula
    (`revolve.formulas_of` skips them), and must be dropped before that helper is deleted:
    otherwise switching To -> Angle left "abs(RevolveTo.Angle)" pointing at nothing.
  - Typing a number with the mouse over the 3D view fired FreeCAD's view keys (0-6). The
    revolve dialog filters ShortcutOverride/KeyPress for digits over the view
    (`revolve_ui.TypeOverView`) and types them into the angle box, like Fusion. The same
    could serve Extrude/Hole (other owners).
  - Overlays drawn for picking (long axis lines, handles, To plane squares) go inside
    `SoSkipBoundingGroup` (`revolve_ui._skip_fit`): Fit then frames the part, not them.
  - Angle parameters: a user parameter in degrees is a PropertyAngle and refuses values
    beyond +-360 (a "720 deg" parameter cannot be made). Left for the parameters owner.
  - Drawing a construction line in the profile's sketch once raised FreeCAD's "Redundant
    constraint is not an autoconstraint ... Please report!" notification (revolve_qa_more
    P15, first version; the scenario now clicks the points). Left for the sketch owner.
  - `blend_steps.choose` (a drop-down picked with arrow keys) failed once in
    `revolve_qa_part` P9 while another full suite ran on the machine; it passed on the rerun
    and in every other run.
- A feature may only link inside its own body ("go out of the allowed scope" error).
  Profiles/edges from another body go through a hidden SubShapeBinder; a construction line,
  construction axis or sketch axis of another body (no shape to bind) through
  `revolve.AxisLink` (a hidden Part2DObjectPython with a global link that rebuilds the line
  every recompute, so the revolve follows edits). Helpers carry `SciForgeTimeline = False`.
- FreeCAD hides the previous tip when a feature is added and shows it again only when the
  feature is deleted with its own command: after removing/moving a preview feature from
  Python, show the body's Tip again (`revolve._show_tip`), or the body looks empty.
- Scenario step names must not contain "error"/"failed"/"invalid": the harness reads the
  step's own progress line in the Report view as an error.
- **Trap (sketch QA): the scenarios' FreeCAD-notification check never looked.**
  `Gui::NotificationArea` has no Q_OBJECT, so Qt calls it "QPushButton" (the class-name test
  never matched), its list is a widget the menu's action *creates* (not `defaultWidget()`), new
  messages sit aside until the menu opens (`aboutToShow`), and items compute their text per
  column. `sketch_input.notifications()` now handles all four; steps can declare expected
  messages (`step.notes_ok`), `QUIET` lists harmless ones ("Autoconstraints cause redundancy").
- FreeCAD's balloons are off while SciForge is on (`MaxOpenNotifications` 0). Messages still
  go to its list and the Report view; SciForge says what matters via `commands.tell`.
  **Trap: never set `NonIntrusiveNotificationsEnabled` to False**: FreeCAD then shows its user
  warnings ("Wrong selection"...) as *blocking message boxes* (`Gui/Notifications.h`); it hung
  sketch_qa. SciForge sets it True.
- **Trap (keys): a real keyboard sends keys to the focus widget, not to the GL drawing area.**
  That is `Gui::View3DInventorViewer` (the GL widget's parent; `h.press` sends to the GL widget
  and the key bubbles up to it), or, while a drawing tool runs, FreeCAD's on-screen value field
  (`Gui::QuantitySpinBox`, a child of the MDI view). FreeCAD's `DrawSketchKeyboardManager`
  keeps digits, Enter, Esc... in that field (for 2 s after a digit or Enter) and passes other
  keys to the viewer. SciForge's sketch keys sit on the viewer (`_KeyFilter`) and on each value
  field when it gets the focus (`SketchSession._focus_changed`): Enter there sends FreeCAD's own
  Ctrl+Enter (accept all fields), Esc stops the tool, a tool letter switches tools unless a
  value was typed into that field (then letters are a unit, "12 mm"). Tests that mean "the
  keyboard" use `si.key` / `si.type_text` (focus widget); `sketch_qa_keys.py` covers it.
- FreeCAD's sketch finds what is under the pointer when it redraws after a mouse move: a test
  press in the same instant as the move selected nothing on a busy machine. `si.click` rests
  80 ms on the spot first. A dimension-placing click on (or within a few pixels of) another
  curve or an axis picks that curve instead (made `sketch_draw` fail 1 run in 4).
- Sketcher_LeaveSketch records its recompute as a separate undo step ("Sketch recompute"):
  `sketch_mode._merge_recompute_step` undoes/redoes it together with the step before it.
- A dimension added on an already-set size stays *driving* in FreeCAD (sketch over-constrained,
  red). `RedundantConstraints`/`ConflictingConstraints` are 1-based; SciForge makes it driven.
- FreeCAD's polygon tool puts a typed size on the LAST curve as a Radius: SciForge's
  circumscribed polygon now ends with the circle touching the edges (`circle_indices()`).
- New-style Sketcher tools take typed values (on-screen fields) but the line tool draws one
  line per two clicks; `sketch_line.LineChain` clicks the end of each new line for the user
  (synthetic Qt mouse events on the GL widget, from a timer after FreeCAD's commit).
- Palette widgets must not take keyboard focus (Esc went to a check box and did nothing);
  Esc in the sketch's side panel is forwarded to `SketchSession.escape`.
- Construction mode (Toggle Construction with nothing selected) lives only in C++; it shows on
  the command's icon, so `sketch_mode.construction_mode()` compares that icon with
  `Gui.getIcon("Sketcher_ToggleConstruction_Constr")`. Every new sketch starts in normal mode.
- Unexplained: in one sketch_qa screenshot (path F) the task panel was drawn see-through (3D
  view visible behind the palette); not reproduced alone. Probably FreeCAD's overlay dock.
- **Patterns findings (branch `sf/patterns`)**:
  - FreeCAD's LinearPattern/PolarPattern read a spacing of exactly -1 as "use Offset"; a
    symmetric pattern is a walk of gaps (0, s, .. then a jump back) that must never contain -1
    (moved by a nanometre). List properties take a whole-list expression
    (`list(Offset.Value; ...)`), not per-element ones: that keeps symmetric copies following a
    parameter.
  - FreeCAD 1.1 bodies allow several solids (`Body.AllowCompound` is on by default), and its
    pattern features repeat dress-ups (fillets) too.
  - A PartDesign body takes its BaseFeature's shape without the shape's placement: bake the
    placement in (`shape.transformShape(matrix, True)`), or the copy lands on the original.
  - A top-level `Part::FeaturePython` linking into a body needs `App::PropertyLink(Sub)Global`,
    else "Link(s) ... go out of the allowed scope" is printed.
  - An overlay drawn over the part (origin axes/planes) gets the press, but FreeCAD still
    selects the part on the release: remember the overlay click and ignore that selection.
  - `sketch_ui.PlanePicker` leaves every click over the part to the part (fine for Create
    Sketch); pattern_ui subclasses it so a square in front of the part wins (Mirror Plane).
  - Harness trap: a scenario step whose name contains "error" fails the step (the harness
    reads its own "step: ..." log line in the Report view).
  - **To confirm with Luca:** Fusion's Symmetric (rectangular and circular) is implemented as
    "quantity and distance/angle per side, the original shared"; Direction 2 is offered at
    right angles after Direction 1; Mirror of a body defaults to New Body.
  - PartDesign features already own a `Suppressed` bool: a Python feature's own property of
    that name is silently not added (use another name: `SuppressedCopies`).
  - Quantity fields take parameters/formulas (`pattern_ui.CountBox`): FreeCAD's pattern
    features cannot change their copy count from an expression cleanly, so such a pattern is
    built by `PatternFeature` (expression `round(...)` on its `Quantity`). The spin arrows
    drop the formula (a plain number again). Bodies refuse a quantity formula.
  - A pattern has at most 2500 instances (`pattern_core.MAX_INSTANCES`, checked in
    `pattern.check` and when the copies are computed): measured here, a LinearPattern of
    50 x 40 holes took 14 s, 30 x 30 4 s; 5000 overlapping holes hung a scenario. The
    Quantity box has keyboard tracking off (typing 900 must not build 9 and 90 on the way).
  - The Total Angle handle counts on past 180 deg (`pattern_ui._TurnDragger` unwraps
    extrude_ui.AngleDragger's -180..180 reading against the last one); drag up to 360.
  - Theme (not patterns' file): an UNCHECKED QCheckBox indicator is practically invisible on
    the dark task panel (the tick shows once checked). Affects Suppression and every other
    dialog's check boxes: theme owner, give `QCheckBox::indicator` a visible border.
  - Not done (gaps, see the parity doc): Compute Option Optimized/Adjust,
    Components, face copies that heal into different
    surroundings, an explicit start point on a path. Pattern on Path now has its timeline
    kind (`pattern_path`: "Pattern on Path", pattern icon), added 2026-10-11.
- **Timeline/browser QA findings (branch `sf/timeline_browser-qa`)**, rules for everyone:
  - `Document.openTransaction` **commits the undo step that is open** (FreeCAD's
    `setActiveTransaction` commits every document's). Anything that opens an undo step while
    a command dialog is open (timeline/browser actions, playback) committed the dialog's
    preview, and Cancel could no longer remove it. End the open command first
    (`commands.finish_open_dialog()`), or do not change the document.
  - A step inserted before a fillet/chamfer/shell (marker rolled back) or the step before it
    deleted: FreeCAD re-links its `Base` to the new base with the old edge names ("Invalid
    edge link", or silently other edges). `timeline_ops.settle()` (after every recompute,
    via the timeline's document observer) finds the same edges again by place and size.
  - A failed PartDesign step keeps its old shape and FreeCAD skips the body, so the 3D view
    showed geometry that no longer existed after an edit in any dialog; `settle()` passes the
    base shape through (Fusion: a red step adds nothing).
  - Setting a sketch's `MapMode` attaches at once and prints "PositionBySupport: subshape not
    found" (Report view + balloon) when the face is not there yet; the harness's word list
    misses that line (`timeline_input.MORE_ERRORS` catches it).
  - A right-click on a timeline step/browser row selected it, and a command waiting for picks
    (Fillet takes whole features) used it. Right-clicks no longer pick while a command is open.
  - SciForge helpers (objects with `SciForgeRole`, or `SciForgeTimeline = False`) are not
    timeline steps; extrude.py's profile binders lacked the flag and showed as steps.
  - Test input: release a drag with `QTest.mouseRelease` (through the window); a release
    sent with `sendEvent` left the button "down" and the next click went to the dragged widget.
  - Fixed since: while rolled back before a fillet, Extrude could not switch to Cut ("... is
    used by Fillet"): `extrude.dependents()` now skips a dress-up's `Base` when it is its
    `BaseFeature` (the history chain; `settle()` re-finds the edges). Scenario
    `timeline_rolled_cut` (fails without the fix, checked).
- **Shell / Draft / Scale findings (branch `sf/shell_draft`)**:
  - FreeCAD's `PartDesign::Thickness` with no faces just copies the part (it cannot hollow a
    closed body) and has one thickness (no Both): SciForge's `ShellFeature` does those
    (offset inward + cut; two thick solids fused). Join "Intersection" = Fusion's sharp
    corners, "Arc" = rounded.
  - **OpenCASCADE's thick solid gives wrong parts without complaint** when the wall is too
    thick: the plain solid back (box 10 high, wall 16), or an invalid solid sticking out of
    the part (wall 20). `shelling._check` refuses those (valid, one solid, inside the part's
    box, something hollowed) and the dialog bisects for the thickest wall that fits.
  - `PartDesign::Draft` pulls along the neutral plane's own axis (a box's bottom face has axis
    +Z, not its outward -Z) and passes `Reversed` on as "retry": a face it cannot tilt is
    skipped with only a Report-view line, and many failures have an empty status string; a
    new Draft that fails has a null Shape (`isValid()` raises). `drafting.check` /
    `undrafted` catch these. Fusion's pull direction is out of a picked face.
  - `Shape.transformShape(matrix)` silently ignores a non-uniform scale; `transformGeometry`
    does it but turns faces into NURBS: exact (ellipse error 1e-15), yet FreeCAD's volume of
    curved NURBS faces is ~1 % off. A sketch still attaches to a flat NURBS face.
  - FreeCAD's naming loses a Pad's corner vertex when the Pad's length changes (the link
    becomes `?Vertex6`, "missing element reference" in the log); SciForge uses the same
    number then (`scale.plain_name`).
  - **A selection gate also filters `Gui.Selection.addSelection` from code**: a dialog that
    re-selects its own picks must allow them in its gate, or (pickpanel) read back what was
    really selected; otherwise the next click looked like "that pick was clicked away".
  - **FreeCAD's task box takes its height when it opens and does not grow** when a label's
    minimum height is raised later: a 3-line error was cut off. `pickpanel` reserves room
    for the message at layout time (the Fillet dialog has the same cut-off for its hint).
  - Draggers inside a see-through part cannot be grabbed (Coin gives the click to the part's
    face in front): the Draft handle sits on the face's continuation outside the part, the
    Scale arrow keeps a gap from the corner it sits on (the corner stays clickable).
    (QA pass: now solved differently, the arrows are screen-space handles; see below.)
- **Shell / Draft / Scale QA findings (2026-10-11, branch `sf/shell_draft-qa`)**:
  - **FreeCAD's element names are what keeps a later step on its face.** A sketch on a face,
    a Press Pull, a fillet name the faces of the step before them; FreeCAD 1.1 finds them
    again through "mapped" names built from each step's history. SciForge's Python features
    must keep those names stable or every later step breaks on an edit:
    - Two shapes made from the same solid and joined (Shell Both: inside and outside
      walls; hollow Both: two offsets) both have tag 0, so the fuse tells their faces apart
      with a `D<number>` that changes with the geometry: editing a thickness lost every
      later reference ("?Face6"). `shelling._tagged` gives the two walls their own tags
      (from the feature's ID: stable, saved with the design).
    - `transformGeometry` (non-uniform scale) returns a shape with no names, and the
      uniform `scale()` names them differently: switching or editing lost the faces.
      `scale._keep_names` copies the part's own `ElementMap` and `Tag` (same topology,
      same order) in both cases.
    - Swapping FreeCAD's Thickness for SciForge's shell (Inside to Both) makes new names
      anyway (the outside walls are new faces). Repointing the dependents must happen
      *after* the new feature has computed (else FreeCAD stores a stale shadow name:
      "subshape not found Shell001.Face11"), and with the same face found by geometry.
    - Whatever is still lost is found again by geometry (`follow.py`: `snapshot()` when
      the dialog opens, `repair()` after each preview recompute, a few rounds because a
      repaired step changes the ones after it): the same place and size, else the same
      kind of face facing the same way nearest to where it was. Golden ops `sf_*_edit` do
      the same. Press Pull stores short names only (`presspull.py`): without this its face
      was lost, or on the base code silently became another face (golden
      `sf_shell_swap_presspull_follows`: the wall pulled was the back one).
  - **`shape.BoundBox` comes from the display triangles once the part was drawn**: a
    cylinder of radius 10 measured 9.997 wide, so a shelled cup "stuck out" of the part and
    every wall of a round part was refused as too thick (headless tests never saw it:
    nothing is drawn). Use `shape.optimalBoundingBox(False, False)` for any geometric
    decision. The golden `sf_shell` step triangulates the part first, like the 3D view.
  - **Greedy selection (pickpanel's toggling clicks) keeps the left-button release from
    `view.addEventCallback` callbacks.** `handles3d` handles wait for that release, so in a
    PickPanel dialog a handle stayed "held" after the first drag and every later click was
    taken as the handle's. `pickpanel.Arrow` reads the release from Qt
    (`QApplication.mouseButtons()`). `construct_ui.py` (inspect) uses `handles3d` in a
    PickPanel dialog too and has the same problem (task suggested to its owner).
  - A handle drawn over the part takes the click (by screen distance), but FreeCAD still
    picks the face behind it: `PickPanel.handles_busy()` ignores picks while a handle is
    pressed or was pressed in the last 0.6 s (also when the handle was rebuilt meanwhile:
    a click on the Draft pull arrow flips it and makes a new arrow at once).
  - A handle over the part steals the clicks meant for faces: the Draft pull arrow now
    stands beside the part (at the outline corner seen furthest left), not through it.
  - The Shell arrow came from `thicknesses()`, which is 0 for a wrong or zero value: after
    "0" the arrow vanished and never came back. Arrows now follow the direction only.

  - FreeCAD's attacher cannot express most Fusion constructions (angle about an edge, tangent
    at a clicked spot, a fraction along a curve). SciForge attaches those datums to a hidden
    helper in the body (`construct.ConstructionFrame`, `SciForgeTimeline = False`,
    `SciForgeRole`) that works out the exact frame on every recompute; Offset Plane of a face
    of the same body stays FreeCAD's own FlatFace + offset (its distance is an expression).
  - `PropertyLinkSubList` groups consecutive picks on the same object into one entry with
    several sub-names: read it back with `construct.expand()` or picks get lost.
  - Clicking a cylinder in the view often hits its seam edge: construct turns a seam edge into
    the face (`construct.seam_face`).
  - Angles about an edge must not depend on which way OpenCASCADE runs the edge: they turn
    about the "upward" direction (`construct.upward`).
  - Datum planes are big and in front: a scenario that clicks a face behind one hides it with
    the browser eye first (that is what a person would do too). In CONSTRUCT dialogs the
    datums the blue box cannot take let clicks through (see Inspect QA findings).
  - Section Analysis cuts with a Coin clip plane (`SciForgeSectionClip`) inserted first in the
    view root of each solid step of a body (not the body's own root: that cut its sketches
    and construction planes too), found again on every refresh (never keep a pointer); cut
    faces are `shape.common(big face)`, drawn by the analysis' own view provider.
  - A Center of Mass with nothing picked links to no body, so FreeCAD never recomputes it: a
    document observer measures it again after recomputes, visibility changes and undo/redo
    (`analysis.follow`, values marked Output so writing them does not touch the object).
  - The browser's Analysis folder opens collapsed; scenarios open it with the keyboard
    (row click + Right).
  - **FreeCAD 1.1 label leak:** a Python view provider's attach() calls `Label.touch()`,
    which counts the object's label a second time in the document's unique-label registry
    (`DocumentObject::onChanged` with a stale `oldLabel`). After the object is deleted or
    its preview cancelled, the label stays "taken" and FreeCAD renames the next object
    (a cancelled Section1 made the next one "Section3"). SciForge's analyses answer
    `allowDuplicateLabel` with yes only while SciForge sets the label it worked out
    (`labels.set_exact`); datums take the next free number (`labels.set_free`). Other
    features with Python view providers (Press Pull, Shell, Scale ...) have the same leak.
  - Run `black` only on your own files: a reformatted shared file broke another agent's text
    replacements.
  - **Inspect QA findings (branch `sf/inspect-qa-2`)**:
    - FreeCAD's selection keeps the mouse release of a drag that ends over a face (it selects
      the face and marks the event handled): `handles3d` handles now also end their drag on
      any left-button release Qt sees (`handles3d.ReleaseWatch`, an application event
      filter installed only while the button is down on the handle; `angle_handle()` wraps
      revolve_ui's turning ball the same way).
    - FreeCAD's number box (autoNormalize, kept at integration) takes the first Enter after a
      sum ("70 + 5", and also "-15": the minus counts) only to rewrite the text. CONSTRUCT and
      Section Analysis install `construct_ui.EnterAfterSum` on their value boxes: after such
      an Enter the formula is taken and OK runs. Other dialogs still need two Enters (shared
      `taskui.DistanceField`; owner: taskui).
    - Fusion picks through what the active selection box cannot take. Origin squares / axes
      drawn by SciForge used to yield to anything under the mouse; they now yield only to
      something the box accepts (`_takes_under`), and construction planes / axes / points the
      box cannot take are made unpickable while it waits (`ConstructPanel._pick_through`, a
      `pickpanel.Looks` put back when the box changes or the dialog closes).
    - pattern_ui's Mirror plane picker counted only faces / edges / corners in front of an
      origin square: a construction plane in front lost the click (`_part_depth` counts
      "Plane" now; one line, found by `inspect_qa3` M).
    - Sketcher names its picks after the sketch's lists, not its shape: "Edge2" is the second
      curve counting construction lines (the shape leaves those out), "Vertex3" goes through
      `getGeoVertexIndex`, plus "RootPoint", "H_Axis", "V_Axis", "ExternalEdgeN" (ExternalGeo
      index N + 1). `measure.sketch_entity()` reads them.
    - Measure in a sketch cannot be a task dialog (the sketch's is open): it is a frame put at
      the top of the sketch's panel (`sketch_palette.sketch_panel()`), never
      `taskui.current()` (else other commands would close it and then refuse to start), no
      selection gate / greedy style (the sketch editor picks), Esc through an application key
      filter, ended by a timer when the sketch is no longer edited.
    - Center of Mass weighs each body with `material.effective(body)` (Steel while on
      FreeCAD's Default). Its marker stays unpickable (it would steal clicks on faces); Measure
      draws a clickable dot on it instead (`MeasurePanel._show_com_dots`).
    - The Measure / Interference result lists drew their items in a dark grey on the dark
      panel: they set light text themselves (`measure_ui.RESULTS_STYLE`).
  - **Inspect QA round 3 findings (branch `sf/inspect-qa-3`)**:
    - **A handle's release is also a pick, and dialogs remake their handles on release.**
      FreeCAD selects the face under the mouse when a drag ends over the part. A handle's
      own `busy()` memory dies with it, and Section Analysis builds new handles as soon as a
      drag ends, so the release's face became the new section plane (the bottom face, seen
      through the cut, after the arrow was dragged far down). `handles3d.just_used()`
      remembers the last press / drag / release of any handle; Section and CONSTRUCT ignore
      picks in that moment. Rule for every dialog with handles that are rebuilt: ask a
      module-level clock, not the handle object.
    - revolve_ui's turning ball and handles3d's arrow used separate "one press, one handle"
      guards, so a press where they meet moved both: `angle_handle()` now honours
      `handles3d.GRAB` too.
    - Coin's picking respects the section clip planes: what a section cuts away cannot be
      clicked (like Fusion); a click there picks what is seen behind it (e.g. the inside of
      the bottom face).
    - A value box that holds no value ("gap +") must keep the dialog open on Enter and OK
      (Revolve already did; CONSTRUCT closed with the old value, Section silently ignored
      "-gap"). Section's Distance / X / Y Angle now go through `preview.FormulaInput` and
      are stored as expressions on the analysis (`section_ui.FORMULA_PROPS`).
    - The construction being edited must be unpickable from the start of the edit, not only
      once it previews: a construction that lost its reference stood over the part and its
      click went to the origin square behind it.
    - FreeCAD stores a length expression on an angle property without complaint ("gap * 3"
      typed as an angle gives "45 mm" used as 45 deg); Fusion would refuse the units. Not
      fixed (rare).
    - Midplane of two faces meeting at an edge is the bisector through the part
      (`n1 - n2`); the QA first expected the outside one.
    - **A step's display is drawn inside its body's placement** (Coin path: body
      SoFCSelectionRoot > Switch > step root). A node put into a step's root works in the
      body's coordinates: the section clip plane is converted with the body's placement
      (`section_ui._parent_frame`); before, a body moved by its Placement was cut in the
      wrong place. Shapes (`obj.Shape` of a body) are global, a step's own Shape is not.
    - Lines drawn a hair above a face lose to the depth buffer on a face seen at a slant
      (bands of the Section hatch were missing on a horizontal cut): the cut face is drawn
      with an `SoPolygonOffset` (pushed back), the usual way to draw decals.

- **Body tools findings (branch `sf/bodies`)**:
  - FreeCAD's `PartDesign::Boolean` adopts its tool bodies as children (GeoFeatureGroup): they
    then move with the target body and their parent is no longer the document. SciForge's
    Combine is its own `PartDesign::FeaturePython` (`combine.CombineFeature`) that links each
    tool body's end step (`PropertyLinkListGlobal`), so the timeline, edits and undo work.
  - A step that "uses up" bodies (Combine without Keep Tools) registers in
    `bodies.CONSUMERS`; `bodies_gui.Watch` hides/shows bodies only on a *change* of that state
    (after recompute, undo/redo, delete), so a body the user shows on purpose stays shown.
    Body-tool dialogs pause it (`bodies.pause`) while they show the bodies they work on.
  - Deleting a step (SciForge's Delete): steps that used its edges/faces are re-pointed at the
    same edges/faces of the step before it (`delete._relink_to_base`, matched by geometry),
    so a fillet survives deleting the boss under it. The timeline's own Delete does not do
    this yet (timeline owner: `delete.delete_steps` can be called without a transaction).
  - A manipulator that follows the bodies while dragged must measure the drag from where it
    was grabbed (`move_ui.Triad._drag_center`), else every drag moves half the distance.
  - An origin `App::Line` runs along its own **X** (its placement's X), not Z
    (`pattern._line_of_datum` knew; `move.axis_of` does it too).
  - Enter in a QLineEdit of a task panel presses the panel's OK (dialog closes): a field that
    takes Enter itself needs an event filter that eats it (`appearance_ui._EnterTakes`).
  - `doc.addObject("PartDesign::Body")` before computing the next "BodyN" label counted the new
    body twice (Body3 for the second body): compute the label first (`bodies.new_body`).
  - FreeCAD materials: a body's `ShapeMaterial` propagates to its features; FreeCAD's Default
    material weighs 1 kg/m^3 (Fusion starts in Steel: `material.effective` counts Default as
    Steel); Brass and GrayCastIron have no density in FreeCAD's library (not offered).
    Setting `ViewObject.ShapeAppearance` on a body copies it to every feature, but a feature
    added later starts grey: SciForge stores looks on the body (JSON, undoable) and puts
    them on every step after each recompute (`appearance.sync`, cached by shape hash).
  - FreeCAD's `Document.openTransaction` commits any open transaction (no nesting): a command
    that must be one undo step cannot call `timeline_ops.delete` (it opens its own).
  - Requests for other owners: browser (show a body's physical material, hide used-up
    bodies), inspect (mass from `bodies.mass(body)`), timeline (a kind "delete_face" with
    the delete icon for `SciForge::DeleteFace`; steps outside bodies such as a Move copy never
    roll back with the marker).
    surroundings, an explicit start point on a path. The timeline module has no entry for
    `SciForge::PatternOnPath` (generic icon, title "Pattern On Path"): timeline owner, add a
    kind `"pattern_path": ("Pattern on Path", "pattern_rect")` to `KINDS` and map
    `"PatternOnPath"` to it in `KIND_BY_SCIFORGE_TYPE`.
- **Fillet / Chamfer QA findings (branch `sf/fillet-qa`)**:
  - **Trap: FreeCAD's number box reads a bare number in the unit it shows.** Below 0.1 mm
    `Gui::QuantitySpinBox` shows micrometres; after a drag down to 0.01 mm ("10.00 µm") a
    typed "1.5" became 1.5 µm and every later value was a thousand times too small. The
    Fillet/Chamfer boxes (`blend_field.ValueField`) read the text themselves (bare number =
    mm / degrees, "0.1 in" works, names and formulas become expressions). **The shared
    `taskui.DistanceField` (Extrude, Press Pull, every dialog) has the same trap**: owner of
    taskui, give it the same reading (or make drags stop at 0.1 mm). Its `autoNormalize`
    also swallows the first Enter after a sum ("2*0.25"): set the property False.
  - **Timeline Delete of the last step hides the whole part** (timeline owner,
    `timeline_ops.delete`): FreeCAD already moved `body.Tip` back when the step was removed,
    so `_set_tips()` sees no change and skips `_show_only_tip()`; the new Tip keeps
    Visibility False. Fix: call `_show_only_tip(body, body.Tip)` after the removal whatever
    the Tip was. Reported as KNOWN in `fillet_qa_more.py` (P19).
  - FreeCAD's element names do not survive an edge that an earlier change trims: a fillet
    inserted with the marker rolled back, or an earlier fillet edited to round one more
    edge, broke the later fillets ("Invalid edge link" in the Report view). Edits that keep
    the topology (sketch dimensions, extrude length, Press Pull distance, fillet radius)
    were fine. `blend.References` keeps later dress-ups' edges/faces as geometry and
    `recompute_keeping` puts them back on the same (possibly shorter) edge.
  - OpenCASCADE's tangent chain also runs through edges an *earlier* change made tangent:
    after a round is inserted, a later fillet's edge that now meets that round's end arc
    tangentially continues round the arc and down the next edge (Fusion's Tangent Chain does
    the same; volumes in the QA account for it).
  - A body may hold several solids (two profiles extruded apart); the old "would cut the part
    into pieces" check compared with 1 solid instead of the body's own count.
  - `QTest.mouseDClick` never releases the button: Qt then believes the left button is held
    (`QApplication.mouseButtons()`), and dialogs that ignore keys while a handle is dragged
    ignored Esc. `blend_steps.timeline_double_click` now sends the release, and with
    `click_first=True` (the fillet QA scenarios) the events of a person's double-click:
    press, release (the timeline selects the step), double-click, release.
  - **Hole (hole owner, `hole_ui.py`)**: with a person's double-click on "Hole 1" in the
    timeline (the first click selects the Hole step), the edit dialog then picks nothing
    when a reference edge is clicked. **Fixed on `sf/hole-qa`**: the Hole and Thread edit
    dialogs clear that whole-feature selection when they open; every hole scenario now
    uses `click_first=True`.
  - A selected timeline item is a whole-feature selection: F after a right-click on the
    timeline (Roll History Marker Here) rounded every edge that feature made. Whole features
    are no longer taken as picks when F starts (a timeline click *inside* the dialog still
    adds the feature's edges).
  - A Coin `SoSearchAction` / `Edge.Curve` on a degenerated edge (where three rounds meet)
    raises `TypeError: undefined curve type`: guard every `.Curve` read.
  - Display parity notes: FreeCAD draws a cylinder's seam as a line (Fusion does not), and the
    overlay title bar of the Tasks dock sometimes shows as a white strip in screenshots.
- **Primitives findings (branch `sf/primitives`)**:
  - **Upstream bug: undo + redo loses a formula's link.** Undo a step whose value carries a
    formula (an expression on a parameter), then redo it: the expression is back but the link
    to the Parameters object is not (`OutList` lacks it), so changing the parameter does
    nothing until the file is reopened. Pad, the PartDesign primitives and
    `Part::Part2DObjectPython` all do it (plain `App::FeaturePython` does not).
    `undo_links.py` (installed when the primitive commands load) sets the same expression
    again after every undo/redo where the link is missing, outside the undo history. It helps
    every feature; worth reporting upstream.
  - FreeCAD expressions refuse "mm minus a plain number" (`Parameters.d / 2 - 6 / 2`: Unit
    mismatch): composed expressions need units (`6 mm / 2`), a unitless parameter `* 1 mm`
    (`primitives.term`). Found by golden model `sf_torus_param_driven`.
  - A feature's frame before recompute: `Part.AttachEngine("Attacher::AttachEngine3D")` with
    the same support and mode. The XZ origin plane's normal is -Y; a box's top-face frame
    starts at that face's corner, not at the body origin.
  - Helper objects (coil section, pipe path and section) are `Part::Part2DObjectPython` in the
    body, marked `SciForgeRole` + `SciForgeTimeline = False` so the timeline skips them;
    `primitives.drop_orphans` removes helpers whose step was deleted (when a dialog opens).
  - Mouse placing on a plane: measure what one pixel is *on the plane* and round clicks to
    nice steps of about 6 pixels (`primitives_core.nice_floor`); within 10 px snap to the
    plane origin and to corners, line ends, sketch points and circle centres lying on the
    plane (`primitives.snap_points`, from `Part.getShape` of visible bodies and sketches).
    Screen-pixel rounding was too coarse or too fine depending on the view.
  - FreeCAD's Helix needs the profile and the axis from one object: the section helper gives
    both (its `V_Axis`). The helix sweeps the upright section, so Pappus (area x 2 pi r x
    turns) is its exact volume. Coil Intersect = `SubtractiveHelix` with `Outside` on.
  - Golden steps `sf_primitive`, `sf_coil`, `sf_path_sketch`, `sf_pipe`, `sf_primitive_edit`
    (`golden/primitive_ops.py`); the first three take `expressions` {field: formula}.
- **Primitives QA findings (branches `sf/primitives-qa2`, `sf/primitives-qa3`)**:
  - **FreeCAD's pipe fails on every sharp corner of its path** with its default
    `Transition = "Transformed"` ("A fatal error occurred when making the pipe"), and
    OpenCASCADE's `makePipeShell(..., 0)` (the same mode) **silently sweeps only the first
    leg** (40 pi instead of 70 pi round two block edges). Use "Right corner" / mode 1: a
    mitred corner, volume exactly area x path length (`pipe.CORNERS`).
  - **FreeCAD's pipe loses the hole of a hollow section swept round a closed path** (no
    message): it makes each wire of the section its own shell; on a closed path both shells
    are already closed, each becomes a solid and the inner one vanishes into the outer
    (`FeaturePipe.cpp`, "shells are already closed"). A hollow pipe round a closed path is
    SciForge's own `PipeFeature` (it now does Join / Cut / New Body as well as Intersect;
    property `Operation`), and a pipe that is one stays one (no step swaps).
  - **FreeCAD's helix always widens away from its section**: a negative `Angle` (or a
    negative `Growth`) gives exactly the mirror image, the same as `Reversed`. A coil that
    narrows as it rises is swept from its narrow end: the section stands at the far end
    (shifted along the axis, turned by the coil's own turns so it still starts where it was
    clicked) and FreeCAD sweeps it back to the plane (`coil.narrow_end`).
  - **FreeCAD's tapered helix (Angle not 0) is only right when its axis starts level with
    the body's origin** (`Helix::generateHelixPath`, the `startOffset` term): on a face 30
    above the origin a 20 mm coil ended 1.5 mm off, volume 0.8 % short. The coil section's
    own origin is moved down the axis to that level and its outline drawn where it is.
    Untapered coils were and are exact.
  - A Placement set inside a `Part2DObjectPython.execute()` is overwritten by its
    attachment right after (FreeCAD calls `positionBySupport` after the Python execute):
    put the offset into `AttachmentOffset` and keep the user's own offset in another
    property (`CoilSection.BaseOffset`).
  - The timeline's Delete removes a step's helpers only when nothing else uses them: a
    helper linked by another helper of the same step stayed behind (the pipe's path, read
    by its section). Link helpers from the step only (`PipeSection.Edges`).
  - The pipe's automatic section size (a twentieth of the path) was worked out again on
    every pick and overwrote a typed wall (0.5 became 0.2): it is chosen once.
  - A hollow pipe cut along an edge cuts its own core loose (a second solid): correct.
  - Hand-derived volumes for coils: Pappus with the mean radius of the section's centre
    (`primitives_core.coil_volume`) holds for tapered coils too (to ~1e-5, the helix is an
    approximation: golden rel_tol 1e-4).
  - From `sf/primitives-qa2` (that agent stopped before writing these down): sizes typed
    while placing are kept (the next mouse move overwrote them); a Length arrow dragged
    through the first corner flips the box over; arrows move in round steps; digits typed
    with the mouse over the 3D view go into the dialog's field (`TypeOverView`, FreeCAD's
    view keys 0-6 jumped the view); a diameter typed after the centre click wins; Enter
    after a negative number is OK at once (`EnterTakesNumber`); another command's key
    drops a shape not placed yet and keeps a placed one; the origin squares are sized to
    the whole design; a click on an edge never picks the plane hidden behind it; a box on
    a face hangs on the step that made the face; a Cut that misses, a Join leaving two
    pieces and an empty Intersect are said in the dialog; an edit opened from the timeline
    starts with nothing selected (`clear_selection_soon`), and a face or edge the step
    itself changed is found on the part before it (`base_face_holding`, `pipe_ui._holds`).
- **Hole / Thread QA findings (branch `sf/hole-qa`)**:
  - The Hole and Thread dialogs were built before main's shared dialog rules and missed
    them all: Enter over the 3D view (`preview.EnterFinishes`), Ctrl+Z / Ctrl+S / closing the
    design (`preview.UndoCancels`; the old `hole_common.DocumentWatch` committed the preview
    and undid it, so Ctrl+Y brought a "cancelled" hole back), `preview.end_transaction` (an
    unchanged dialog threw away the Redo list), `preview.FormulaInput` (a parameter typed in
    Depth was silently dropped), showing the Tip after removing a preview by code. **A new
    dialog should start from `pickpanel.py` or copy these five.**
  - `preview.FormulaInput` only sees the text when the field is left (Tab, Enter, a click
    elsewhere). A plain number typed over a formula must win at once (else the preview and
    OK still used the formula): the Hole / Thread fields watch `textEdited` and drop the
    formula as soon as the text is a plain number (`parameters.is_plain_number`).
    `QPushButton.click()` (the harness's `task_button`) does not move the keyboard focus, so
    in tests a field typed with `hole_steps.type_into` (no Tab) is never "left"; use
    `dialog_input.type_into` (types, then Tab) for formulas.
  - FreeCAD's Hole has no "up to face" depth. Extents To is now a hidden
    `Part::Part2DObjectPython` in the body just before the hole (`hole.HoleToDistance`,
    role `HoleTo`, `SciForgeTimeline = False`): it measures the depth from the hole's start
    to the target on every recompute and the hole's Depth is the expression
    `<helper>.Distance`. Removed with the hole (`hole.remove`, timeline Delete via
    `_helpers_of`); an orphan is dropped by the next hole. Typed formulas never touch Depth
    while Extents is To.
  - A long recompute (modeled thread / tapped hole) runs timers inside it; a test step that
    pressed H or OK then closed the dialog under the running recompute (traceback: "Internal
    C++ object (QLabel) already deleted"). Hole / Thread `_recompute` stop once closed, and
    OK / Cancel / another command wait while `doc.Recomputing`. Extrude has the same unguarded
    `_recompute` (extrude owner: add `if self._closed: return` after `preview.recompute` and
    guard the `setText` in its `except`); seen when OK followed a typed value within ~1 s on a
    part with a modeled thread.
  - In the iso view, a click point behind a taller feature hits that feature: compute the view
    ray (camera +x -y +z) before choosing click points next to a boss (hole_qa_more P18).
  - A thread's face link becomes `?FaceN` when an earlier step splits that face (a modeled
    thread before it): FreeCAD prints "missing element reference" and the thread failed.
    `ThreadFeature.execute` now finds the cylinder again from its last `Computed` record
    (same axis line and radius, most overlap: `thread.refind`) and points the link at it
    inside `execute()` (changes made there are purged, nothing new to undo), so the message
    comes once, not on every recompute.
  - A sketch attached to a face of the step just before it depends on that step: deleting the
    step turns the attachment off ("stays where it was") and the sketch no longer follows the
    part (a hole then sat frozen inside a plate made taller). `hole.earliest_face` /
    `earliest_edge` walk the BaseFeature chain back to the step that made the same flat face
    (same plane, holding the point) or the same edge, and attach there; a step that moved the
    face stops the walk. Create Sketch (sketch owner) attaches to the Tip's face and has the
    same weakness: suppressing Hole 1 also suppressed the holes of a sketch drawn after it
    (timeline suppress takes dependents along).
  - The browser lists Single Hole helper sketches ("Hole 1 Sketch", hidden; double-click opens
    the hole). Fusion shows no sketch for a single hole: to confirm with Luca whether they
    should leave the browser (browser owner + `hole.py` scenario's browser step).

- **Sweep / Loft / Rib / Web findings (branch `sf/sweep_loft`)**:
  - **Trap: OpenCASCADE's volume of a merged smooth B-spline side can be wrong.** A loft of
    a slot to the same slot with Tangent Edges Merge gave 7551 mm³ by `Shape.Volume`
    (GProp) instead of 8356 (the meshed shape and the formula agree on 8356). So the loft
    keeps one side face per profile curve, and the Merge box is greyed with the reason.
    Watch for this with any feature that makes B-spline faces (surface tools later).
  - For a big plane face centred on a point (to slice a part), use
    `Part.Plane(point, normal).toShape(-r, r, -r, r)`. The first way tried did not cover
    the point, and a rail then seemed not to touch the profile.
  - FreeCAD's Loft wants whole sketches in `Sections` as `(sketch, "")`; the first way
    tried failed with "At least one section is needed".
  - FreeCAD's AdditivePipe needs Transition "Right corner" to give Fusion's mitred corner
    on a path with a sharp bend, and Mode "Standard" for Perpendicular, "Fixed" for
    Parallel.
  - A native SubtractivePipe / SubtractiveLoft that misses the part silently changes
    nothing. The dialogs now say "does not touch the part" instead (`_misses()`).
  - OCC `MakePipeShell.setAuxiliarySpine(wire, True, 0)` with a helix-like guide gives the
    twist; for a curved path the guide comes from rotation-minimizing frames (double
    reflection), which keeps the profile from rolling.
  - Rib (gusset): thickening the band first and cutting it by the part left the rib
    unbounded wherever its thickness ran past the part's side. The outline is now found in
    the sketch plane (the band minus the plane's section of the part), then thickened.
  - A rib / web turned out of a side face (One Side) touches the part only along edges:
    `fuse` then gives two solids. Refused with the reason.
- **Sweep / Loft / Rib / Web QA findings (branch `sf/sweep_loft-qa`, break-and-fix pass)**:
  - **Trap: FreeCAD 1.1 re-hashes element names after a reopen.** A design saved and
    reopened, then the Extrude before a sweep edited: the Extrude's mapped names got new
    string-hasher ids (`#c:1;...` became `#4a:1;...`), a sweep along its top edge lost the
    edge ("?Edge3", "A curve picked from Extrude is gone") and a Press Pull on a face of the
    sweep lost its face (nested hashed names no longer match). Not reproducible headless
    without the GUI's own steps. Fix: `curves.remember(feature, props)` stores where each
    picked part element is after every good compute (hidden `SciForgeLinkMemory`, an
    output property) and `curves.refind` points a lost link at the element found again
    there (same curve / surface kind, facing the same way, nearest). Used by SciForge's
    sweep and loft and by Press Pull (two lines in `presspull.py`). Part edges / faces are
    therefore always built with SciForge's sweep / loft (FreeCAD's Pipe / Loft just fail).
    Other features that link part elements (Extrude To Object, fillets after an edit...)
    may need the same: worth checking in their QA.
  - Rebuilding a step as the other kind of feature (FreeCAD Pipe <-> SciForge sweep) used
    to be refused when a later step used it ("Sweep is used by Sketch002"). Now
    `curves.relink_users(old, new)` moves every link (each face / edge found again by
    `follow.find`) after the new step computed, before the old one is removed.
  - **Trap: a dialog's undo step is opened lazily by its first change.** `extrude.
    ensure_regions` recomputed a sketch with no closed area (a path, a rib line: its
    InternalShape stays null) every time areas were looked for, inside the dialog's step,
    so opening Sweep/Loft and pressing Esc threw away the Redo list. It now remembers such
    sketches (by shape hash); the Sweep / Loft dialogs also turn areas on before their step
    opens (`curve_pick.prepare_regions`).
  - Create Sketch (`sketch_ui.PlanePicker`) gave every click to the origin square behind a
    construction plane (a datum plane is picked as a whole object, not a "Face"): the
    loft's second profile was drawn on XZ instead of the Offset Plane. A datum plane in
    front of the squares now wins. (A face of the part under the mouse still always wins,
    even behind a square: by design for Create Sketch.)
  - `profile_pick.used_sketches` did not count FreeCAD Loft's `Sections`: Extrude / Sweep
    took a loft's second circle by itself as a new profile.
  - A command started from a ribbon menu (CREATE > Sweep / Loft / Rib / Web) that cannot
    start told why with a tooltip that the closing menu hid at once: `commands.tell` shows
    it again 250 ms later if it vanished.
  - Web Extend Curves added half the thickness (or all of it, One Side) past the wall: the
    web poked out of walls thinner than that (Depth mode; To Next was clipped). The band's
    two sides are now carried exactly to the wall.
  - Fusion makes a new body for a sweep / loft that does not touch the part: the automatic
    operation is now New Body there (SciForge's Extrude still says "separate solids").
  - Scenario traps: a Create Sketch click on an origin square with a face of the part
    behind it goes to the face (`sweep_loft_qa_part` clicks XZ left of the cylinder); in
    the XZ sketch of a cylinder a circle can be drawn inside the part (clicks land on the
    sketch plane); a sketch line lying on a preview's edge is picked as the sketch line.
- **Patterns QA findings (branch `sf/patterns-qa`, break-and-fix pass)**:
  - **Trap: rebuilding a step as a new object silently drops every link to it.** A pattern
    edit that needs the other kind of feature (Suppression, a Quantity formula, Faces, a
    fillet among the objects) replaced FreeCAD's LinearPattern with SciForge's feature; a
    sketch on its top face, a fillet on its edges or a Press Pull of its face lost their
    reference without a message. `pattern.relink_dependents(old, new)` moves every link first,
    each face/edge/vertex found again by place (`pattern.twin_element`). Any feature that
    swaps its object type needs the same.
  - **Upstream behaviour:** FreeCAD's Transformed features return without touching their shape
    when none of their originals is left (`FeatureTransformed.cpp`, `originals.empty()`): after
    the patterned hole was deleted the copies stayed and everything after the pattern froze.
    `pattern.OrphanWatch` (an App observer, `slotRecomputedObject`) passes the base shape
    through and sets the timeline warning (`SciForgeWarning`). Worth reporting upstream.
  - FreeCAD's pattern features repeat their originals in list (= click) order: a boss picked
    after the hole in it filled the copied hole. Originals are now sorted in timeline order.
  - Fusion has no active body: a pattern dialog started while a second body was active
    ignored the first body's features (clicks did nothing). `PatternPanel._adopt_body`.
  - **Trap: a flat drag handle is a sliver when its plane is seen nearly edge-on**, and a
    press that misses a handle selects the part behind it on release (the box's whole
    feature joined the pattern's objects). The pattern's curved handle got a second, standing
    band; pattern dialogs ignore the selection that follows a press on a handle. **Not fixed
    for other dialogs** (owners of `taskui.ArrowDragger` / `extrude_ui.AngleDragger`): the
    taper handle has the same flat band, and every dialog that picks faces should ignore the
    release after a press on a handle.
  - OpenCASCADE's Python exceptions print as "<unknown exception data>"; SciForge's pattern
    feature now raises sentences (`pattern.kernel_message`).
  - Not patterns' (seen during QA, sf/patterns base): an Extrude to a New Body from a sketch
    on another body's face shows a step "ExtrudeNNN profile" in the timeline (extrude /
    timeline owners).

- **Body tools QA findings (branch `sf/bodies-qa`)**:
  - **FreeCAD's Python document observers never get `slotFinishRestoreDocument`** (not in
    `App/DocumentObserverPython.cpp`; there is no "restore finished" slot at all). Use
    `slotCreatedDocument` plus a `QTimer` that waits while `doc.Restoring`
    (`bodies_gui._opened`). `thread_ui.py` (hole owner) still has a dead
    `slotFinishRestoreDocument`.
  - `slotDeletedObject` is emitted *before* FreeCAD breaks the links to the object
    (`Document::_removeObject`: signal, then `breakDependency`): an observer can still read
    the object and the objects linking to it, and property changes made there go into the
    same undo step. `doc.Transacting` is True while undo/redo/abort roll objects back (skip
    those). `bodies_gui.freeze_for` uses this so ANY Delete (browser, timeline) of a body a
    Combine uses keeps the Combine's result.
  - A used-up body must never stay the active body: sketches on origin planes and extrudes
    went into the hidden body (looked like "Extrude did nothing"). `bodies.leave_used_up`
    after every sync; a reopened file whose first body is used up activates a free one.
  - The Combine preview is drawn exactly where the see-through tools are (coplanar faces):
    a click on a tool lands on the preview. `combine_ui._really_clicked` resolves a click on
    the preview to the body really under the pointer (`solid.isInside(point, tol, True)`).
  - App.Material() is FreeCAD's built-in lavender (0.8, 0.8, 0.9), not the grey parts are
    drawn in: the default look comes from the Part colour preferences
    (`View/DefaultShapeColor`...), as `Materials::MaterialManager::defaultAppearance()`
    does (`appearance._default_material`).
  - OpenCASCADE gives a full circle one vertex (its seam) and a cylinder face a seam line:
    neither is a corner a person sees (`move_ui._corners`), a click there must snap to the
    centre.
  - FreeCAD 1.1 element maps survive SciForge's Python features: a sketch on a face of a
    Combine / Move / Split result stays on that face when an earlier step changes (tested
    headless: face index changed, the sketch followed). Limit: a face a Join merged
    (refine, ";RFI" in its name) is named differently once the Combine is switched to Cut;
    a Press Pull on it then fails with "select the face again" (FreeCAD's own Boolean
    loses it the same way). Fixing it would need SciForge's own face names for Combine
    results (faces lying on a target face named after it).

## Questions waiting for Luca


(See outline section 12. Also:)

- Primitives (`docs/sciforge/parity/primitives.md`): which defaults does your Fusion show for
  Torus Position, Coil Rotation (Clockwise?) and Section Position, and is Section Size of a
  square/triangle section the circle round it or its side?
- The 6 open Dependabot PRs (GitHub Actions version bumps): close them, or merge them?
- The browser lists a Single Hole's own sketch ("Hole 1 Sketch") under the body. Fusion
  shows nothing there; hiding it is easy, but double-clicking it is how the `hole` scenario
  edits the hole today. Hide it?
- Fusion checks for your copy: marking-menu slot order (screenshot), hole depth measured
  to the drill point or the shoulder, Polygon size (inscribed or circumscribed), Plane at
  Angle reference, how Symmetric counts pattern copies, pipe corners (mitred or rounded),
  Scale's default for profiles.

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
  (Done on `sf/shell_draft`: the list is empty.)

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
### 2026-10-10: Revolve (branch `sf/revolve`)
- Built Fusion's Revolve (see the Phase 1 checkbox): `sciforge/revolve.py` (Qt-free core, used
  by the dialog and the golden builder), `sciforge/revolve_ui.py` (dialog, clickable origin
  axes and construction lines, on-top angle handle, editors for Revolution / Groove /
  SciForge::Revolve). Ribbon: one line removed ("Revolve (Cut)").
- Tests: scenarios `revolve_basic` (nothing selected, Z axis click, Full/Angle, handle drag,
  Symmetric, Two Sides, OK, undo/redo, timeline edit, auto-Cut groove, Cancel, Esc),
  `revolve_axes` (sketch line axis, Join/Intersect/New Body, face + edge selected first,
  auto Cut by direction, edit, undo/redo, construction line, angle error kept in the
  dialog), `revolve_edit` (a FreeCAD-made revolve edited, side-two handle, Esc in an edit,
  two profiles toggled, axis cleared and re-picked). 12 golden models `sf_revolve_*`
  (cylinder, cone, torus, groove auto-cut, intersect, new body about a construction line,
  the same following the line when it is moved, two sides, symmetric, sketch line axis,
  face + edge, edit Groove <-> Revolution), schema unit tests `test_revolve_schema.py`.
- Gap: Fusion's Type "To" (FreeCAD's Groove up to a face gives an empty solid, see Known
  issues). Not checked by Luca yet.

### 2026-10-10: Sketch QA (branch `sf/sketch-qa`)
- Broke the merged sketch workspace on purpose with 3 new scenarios (only real input):
  `sketch_qa.py` (12 paths: typed lines, timeline edits, undo/redo, save/reopen, broken
  profile, bad values, Esc everywhere, tool switching, marking menu, Del/M/Ctrl+C/V,
  construction, fillet, polygon, constraint tools), `sketch_qa_part.py` (multi-feature part
  with Press Pull and sketch edits), `sketch_qa_keys.py` (keys sent where a real keyboard
  sends them). About 30 bugs fixed; the list with how each was found is in the branch's
  commits and `parity/sketch.md`.
- Biggest finds: every SciForge sketch key only worked in tests (keys went to the GL widget;
  a real keyboard sends them to the viewer or FreeCAD's value field, see Known issues);
  `NonIntrusiveNotificationsEnabled` False turned FreeCAD warnings into blocking boxes;
  Up/Down in the dimension box recursed ~1000 deep; the notification check never looked.
- Full suite on the branch (no --only): unit 134 OK, golden 99 pass + 1 xfail
  (plate_hole_grid, core patch #4 not compiled), smoke 70/70, journey 25/25, 29 scenarios
  PASS (2762 checks; sketch_qa 457, sketch_qa_keys 119, sketch_qa_part 104).
- Left open: Fusion's angle typed relative to the previous line, tangent arc by dragging from
  a line end, greyed sketch tools, Fusion's constraint glyph look; sketch_polygon failed once
  ("second use") and never again; one see-through task panel screenshot (path F).

### 2026-10-10: Patterns and Mirror (branch `sf/patterns`)
- New: `pattern_core.py` (where copies go, pure), `pattern.py` (document side: FreeCAD's
  pattern features with both spacing lists written, symmetric gap walks, SciForge's
  `PatternFeature` for faces / paths / anything FreeCAD cannot repeat, new-body copies for
  Bodies), `pattern_ui.py` (Rectangular / Circular / Pattern on Path dialogs, origin-axis and
  front-plane pickers, highlight overlay, arrows, angle handle, editors, delete watch for body
  patterns), `mirror_ui.py` (Mirror). Ribbon: Pattern on Path enabled (one line).
- Later the same day: Suppression (dots on the copies), Quantity from a parameter/formula,
  SciForge's own extrude / a pattern step as mirror and pattern objects.
- Tests: scenarios `patterns_rect`, `patterns_circ`, `patterns_mirror`, `patterns_path`,
  `patterns_suppress`, `patterns_params`, `patterns_qa` (real input only); golden ops
  `rectangular_pattern`, `circular_pattern`, `path_pattern`, `fusion_mirror`, `pattern_edit`
  (`golden/pattern_ops.py`) + 19 models;
  unit tests `test_pattern_core.py` (17).
- Parity doc `docs/sciforge/parity/patterns.md` (assumptions to confirm with Luca, gaps).
- Full suite at the end: unit 153 OK; golden 121 pass + 1 xfail (`plate_hole_grid`, needs
  core patch #4); smoke 70/70; journey 25/25; 39 of 40 scenarios PASS in the full run,
  `sketch_draw` failed 3 checks ("circle diameter typed: 8" got r 4.97) while another
  worktree's suite ran at the same time, and PASSES alone (86 checks): timing-sensitive,
  sketch owner to look at.
### 2026-10-11: QA of the timeline and browser (branch `sf/timeline_browser-qa`)
- 4 new scenarios `timeline_browser_qa*.py` (24 paths, real input only; balloons and the extra
  Report-view words watched) found and fixed: an edit that broke a later step left the old
  shape on screen; a step added at the rolled-back marker or deleted before a fillet broke the
  fillet; editing a step after the marker showed nothing (now rolls to it and back); Play kept
  rolling under an opened dialog (committed its preview); Unsuppress printed "subshape not
  found"; suppressed steps showed yellow; Suppress greyed for several steps; the marker could
  not stand before a sketch (now saved in the document) and sketches after it stayed drawn;
  step numbers changed when steps moved (now by creation order: FreeCAD's label numbers
  also count cancelled previews, so they are not usable); an extrude's binder showed as a step; a right-click
  during Fillet made a fillet; rename/activate/find opened undo steps inside a command; two
  origins after reopening; Esc did not drop a drag; long timelines hid the marker; "Hide
  Timeline" had no way back. New: hovering a step lights up the faces it made (Fusion).
  2 golden models (`tl_delete_before_fillet`,
  `tl_insert_before_fillet`), unit tests for the marker, numbering, origin, suppressed rows.
- Left for others: Extrude cannot switch to Cut while rolled back before a fillet (extrude),
  the floating empty "Tasks" header over the 3D view (shell), browser vs timeline names
  (shared smoke test).
- Trap: the timeline's height sets the 3D view's size; 8 px more moved where a scenario's
  click lands (sketch_polygon's snap) - keep the dock height.
### 2026-10-11: Shell, Draft, Scale (branch `sf/shell_draft`)
- Built Fusion's Shell, Draft and Scale (see the Phase 1 checkbox and Known issues). New
  modules: `shelling.py` / `shell_ui.py`, `drafting.py` / `draft_ui.py`, `scale.py` /
  `scale_ui.py`, shared dialog base `pickpanel.py` (picking with toggling clicks, see-through
  "before" part + solid preview, Esc/Enter/Ctrl+Z guards, Delete held). Shared edits: one
  ribbon line (Scale -> `SciForge_Scale`), ribbon_sweep `KNOWN` emptied (Shell fixed),
  append-only golden ops (`schema.py`, one import line in `builder.py`).
- Tests (only real input): `shell_draft` (nothing selected, picks/drops, typed value, arrow
  drag, Both / Outside / Rounded, too thick + hint, OK, undo/redo, timeline edit to Both,
  Cancel, Esc), `shell_draft_hollow` (body picked in the browser, preselected face + Enter,
  second shell on the result, Ctrl+Z inside, editing the first of two shells, a parameter
  formula, save/reopen), `shell_draft_draft` (origin square, faces, handle, flip, refused
  face, too steep, edit, Cancel, Esc, second draft with a preselected face),
  `shell_draft_scale` (body click, arrow drag, corner point, Non Uniform, factor 0, edit,
  Cancel, Esc, preselected body + Enter, save/reopen), `shell_draft_qa` (rounded block:
  tangent runs, a second body followed by Draft and Shell). 20 golden models, unit tests.
- Full suite on the branch (no --only): unit 149 OK, golden 134 pass + 1 xfail
  (plate_hole_grid, core patch #4 not compiled), smoke 70/70, journey 25/25, 45 scenarios
  PASS (3847 checks).
- Gaps: Draft Parting Line / Two Sides / Symmetric (greyed: FreeCAD's Draft cannot split
  faces), Scale of sketches/components, several bodies in one step, Change Parameters does
  not list SciForge's own Shell (hollow/Both) and Scale values (`parameters.py` knows only
  Press Pull among SciForge's features). Not checked by Luca yet.

### 2026-10-11: Body tools (branch `sf/bodies`)
- New: `bodies.py` (helpers any multi-body tool can call: `list_bodies`, `new_body`,
  `active_body`/`set_active_body`/`find_body`, `body_of`, `global_shape`/`to_local`,
  `mass`), `combine.py`/`combine_ui.py` (Combine), `split.py`/`split_ui.py` (Split Body,
  incl. sketch lines/arcs as tools), `move.py`/`move_ui.py` (Move/Copy: Free Move
  manipulator `Triad`, Translate, Rotate, Point to Point, Point to Position, Create Copy),
  `delete.py`/`delete_ui.py` (Delete, Delete Face step and its edit dialog),
  `appearance.py`/`appearance_ui.py`, `material.py`/`material_ui.py`, `bodies_panel.py`
  (shared dialog base), `bodies_gui.py` (step view provider + document watch).
  Ribbon: Split Body enabled (one line). No core patch.
- Tests: scenarios `bodies_combine`, `bodies_split`, `bodies_move`, `bodies_delete`,
  `bodies_look`, `bodies_timeline` (real input only; timeline roll/suppress/delete, Ctrl+Z
  in a dialog, save + reopen); golden ops in `golden/bodies_ops.py` (combine, split_body,
  move_bodies, delete_face, delete_bodies, body_tool_edit, measure_bodies) + 24 models
  `bodies_*`; unit tests `test_bodies_schema.py`.
- Spec and gaps: `docs/sciforge/parity/bodies.md`.
- Full suite at the end (no --only, 2026-10-11, 4 CPUs shared with another agent's GUI
  tests): unit 166 OK; golden 157 pass + 1 xfail (`plate_hole_grid`, needs core patch #4);
  smoke 70/70; journey 25/25; 56 of 56 scenarios PASS (4393 checks; bodies_combine 90,
  bodies_split 82, bodies_move 85, bodies_delete 63, bodies_look 58, bodies_timeline 64).
- Left for others (see findings): the browser to show a body's material and hide used-up
  bodies, Inspect to read `bodies.mass()`, the timeline a "delete_face" kind and roll-back
  of steps outside bodies (a Move copy).

### 2026-10-11: QA of Fillet and Chamfer (branch `sf/fillet-qa`)
- Broke the merged Fillet/Chamfer on purpose with 4 new scenarios, only real input, 22 paths:
  `fillet_qa.py` (beginner, wrong order, Esc mid-pick, fast typing, far/negative drags,
  three timeline edits + undo/redo, E/Q/F/Ctrl+S inside the dialog, save-close-reopen-edit),
  `fillet_qa_part.py` (a real part: sketch, extrude, boss fillet, Press Pull of the round, a
  pocket, a chamfer, then the first extrude made taller; history edits and an insert with the
  marker rolled back; a two-solid body; a radius from a parameter), `fillet_qa_chamfer.py`,
  `fillet_qa_more.py` (marking menu, two designs, two bodies, keys in the box, x button,
  timeline Delete, empty design, Press Pull edited under a fillet, design closed under the
  dialog). 2 golden models + ops `blend_insert` / `blend_edit` (`golden/blend_ops.py`).
- Bugs fixed (see Known issues "Fillet / Chamfer QA findings" and `parity/fillet.md`): µm
  reading of typed numbers after a drag, no parameters/formulas (and a FreeCAD pop-up on
  "="), Enter swallowed after a sum, Ctrl+S saving a half-made fillet, later fillets broken by
  an insert / an edit ("Invalid edge link"), two-solid bodies refused, 90° chamfer angle with
  a kernel message, F after a timeline right-click rounding a whole feature, F inside a
  dialog reusing its picks, a hidden fillet left in the body after dropping every pick,
  clicks in another design taken as picks, the drag arrow left behind the edge.
- Reported, not mine to fix: timeline Delete of the last step hides the whole part
  (`timeline_ops.delete`); `taskui.DistanceField` has the µm trap in every other dialog.
- Full suite at the end (no --only): unit 161 OK; golden 135 pass + 1 xfail
  (`plate_hole_grid`, needs core patch #4); smoke 70/70; journey 25/25; 54 of 54 scenarios
  PASS (4310 checks; fillet_qa 112, fillet_qa_part 96, fillet_qa_more 90,
  fillet_qa_chamfer 62; the teammate's fillet 67, fillet_chamfer 48, fillet_features 23,
  fillet_chain 14 unchanged).
### 2026-10-11: CONSTRUCT and INSPECT (branch `sf/inspect`)
- Reworked all 19 CONSTRUCT entries (see the Phase 1 checkbox) and built Fusion's Measure,
  Section Analysis, Center of Mass and Interference. New modules: `construct.py` (rewritten),
  `construct_ui.py` (rewritten), `handles3d.py` (arrow, path dot, clickable dots, overlay),
  `measure.py`, `measure_ui.py`, `section.py`, `section_ui.py`, `analysis.py`, `com_ui.py`,
  `interference_ui.py`, `bodypick.py`, `labels.py` (exact Fusion-style names, see Known
  issues). Shared edits: four ribbon lines (Plane Tangent to Face at Point, Axis
  Perpendicular to Face at Point, Interference, Center of Mass), append-only golden ops
  (`schema.py`, one import line in `builder.py`, ops in `golden/inspect_ops.py`).
- Tests (only real input): `inspect_construct` (Offset Plane: nothing selected, click, arrow
  drag, typed value, undo/redo, timeline edit, Cancel, Esc, preselected + Enter, origin
  square, sketch on the plane also over the part, extrude from it), `inspect_construct_planes`
  and `inspect_construct_axes` (every other entry), `inspect_construct_use` (Extrude To Object
  a construction plane, Revolve about a construction axis, editing the plane moves both),
  `inspect_measure`, `inspect_section` (also a second section started with a face
  selected), `inspect_com_interference` (an all-bodies Center of Mass following a hidden
  body and an edited extrude; a second Interference started with both bodies selected).
  6 golden models, unit tests `test_inspect_core.py`.
- Full suite on the branch (no --only): unit 192 OK, golden 161 pass + 1 xfail
  (plate_hole_grid, core patch #4 not compiled), smoke 70/70, journey 25/25, 68 scenarios
  PASS (5847 checks), ribbon_sweep included.
- Gaps (see `parity/inspect.md`): Tangent Plane reference plane, Along Path on a chain,
  Offset Plane To Object, browser double-click/right-click Edit for Analysis items (browser
  owner), one material for Center of Mass, Component filter, Interference "create bodies".
  Not checked by Luca yet.
### 2026-10-11: Box, Cylinder, Sphere, Torus, Coil, Pipe (branch `sf/primitives`)
- New: `primitives_core.py` (no FreeCAD: rounding and snapping, size checks, volumes, the
  automatic operation), `primitives.py` / `primitives_ui.py` (Box, Cylinder, Sphere, Torus;
  shared dialog base `PlacedPanel`, placing tool `Placer`, on-top arrow `LinearHandle`),
  `coil.py` / `coil_ui.py`, `pipe.py` / `pipe_ui.py`, `undo_links.py` (re-links formulas
  after undo/redo, see findings). Ribbon: Pipe enabled (one line). No core patch.
- Tests: scenarios `primitives_box`, `primitives_shapes`, `primitives_coil`,
  `primitives_pipe`, `primitives_qa` (real input only: nothing selected, a selection taken at
  once, Cancel, Esc, Enter, Ctrl+Z in a dialog, edit again, undo/redo, second use,
  parameters incl. the coil's Revolutions, snapping to a corner, re-pick plane, save +
  reopen + edit, timeline Delete); golden ops in `golden/primitive_ops.py` + 25 models
  `sf_box_*`, `sf_cylinder_*`, `sf_sphere_*`, `sf_torus_*`, `sf_coil_*`, `sf_pipe_*`
  (hand-derived; Pappus for coils/pipes); unit tests `test_primitives_core.py`.
- Spec and gaps: `docs/sciforge/parity/primitives.md`. Gaps: New Component, value boxes on
  the canvas, snapping along edges / midpoints, Fusion defaults to confirm with Luca.
- Full suite at the end (no --only, 2026-10-11, commit 168c2b7a48): unit 219 OK; golden
  204 pass + 1 xfail (`plate_hole_grid`, needs core patch #4); smoke 70/70; journey 25/25;
  72 of 72 scenarios PASS (6245 checks; primitives_box 78, primitives_shapes 99,
  primitives_coil 70, primitives_pipe 73, primitives_qa 107, ribbon_sweep 106).
- For every owner: `undo_links.py` is installed when the SciForge commands load and fixes
  formula links after undo/redo for all features, not only these (see findings).

### 2026-10-11: Integration of the feature agents (main branch)
- Merged into `claude/inspiring-cerf-ragp6j`, each after a full local suite: timeline/browser
  QA, shell_draft, bodies, fillet QA, inspect, primitives (MEMORY/builder/schema conflicts:
  schema blocks are appended whole from each branch's own diff, never a blind union, which
  once cut the tail off a check function).
- Fixed unowned leftovers, each with a scenario that fails without the fix (checked):
  sketch on another body's face goes into that body (`sketch_other_body`); marking menu OK /
  Cancel while a command is open and list rows that never ran (`marking_menu_command`); E
  in an already used sketch (`extrude_from_edited_sketch`); empty "Tasks" header and white
  strip over the 3D view (`overlay_title`); Extrude to Cut with a fillet after the marker
  (`timeline_rolled_cut`); timeline Delete of the last step hid the part (`fillet_qa_more`);
  bare numbers read in µm (`value_box_units`); Combine's used-up bodies in the browser
  (`bodies_combine`); analysis edit from the browser (`inspect_section`). Timeline kinds for
  Pattern on Path and Delete Face. `patterns_path` now expects a failed step to add nothing.
- Test runner: scenarios start through `scenario_launcher.py` (a scenario that does not load
  fails in seconds, not after the 15-minute timeout).
- CI green on 4263146a1d (run #45): the quick update for Luca has everything up to fillet QA.

### 2026-10-11: QA of Hole and Thread (branch `sf/hole-qa`)
- Branched from `sf/hole` and merged the current main into it first (the hole branch was
  older than every shared dialog rule), so the QA ran against today's product.
- 4 new scenarios with only real input (28 paths): `hole_qa.py` (8 paths), `hole_qa_part.py`
  (7), `hole_qa_thread.py` (7), `hole_qa_more.py` (6). Bugs found and fixed (details in
  Known issues and the commits): Enter over the view did nothing; an unchanged dialog threw
  away the Redo list; Ctrl+S saved a half-made hole/thread; Ctrl+Z in the dialog committed
  the preview; parameters/formulas typed in fields were dropped; the diameter arrow pulled
  through the centre grew the hole again; a hole dragged off the part was accepted; a
  person's timeline double-click left the edit dialog unable to pick edges; clearing a
  preview hid the part; clicks in another design were taken; Extents To did not follow its
  face (now a helper measures it); choosing To warned before the face was picked; a later
  hole's sketch hung on the hole before it and froze when that hole was deleted; OK / H
  during a modeled-thread recompute left a traceback; the thread length arrow ran past the
  face; a thread whose face lost its name failed (found again by geometry).
- Golden models `hole_to_face_follows`, `hole_second_survives_first` (fails with the old
  attachment: 9 faces, a closed pocket), `thread_second_after_modeled` (errors without the
  geometric re-find; golden `edit` can now set a thread's `modeled`).
- Teammate scenarios changed on purpose: `hole_edges` (Ctrl+Z in the dialog now cancels,
  Ctrl+Y brings nothing back; the hole is made again), `hole`, `hole_sketch`,
  `hole_tapped`, `hole_thread` use a person's double-click on the timeline.
- Full suite on the branch (no --only, at code commit 24314786f2, 75 minutes): unit 199 OK,
  golden 190 pass + 1 xfail (plate_hole_grid, core patch #4 not compiled), smoke 70/70,
  journey 25/25, 83 of 83 scenarios PASS (8146 checks; hole_qa 489, hole_qa_more 362,
  hole_qa_thread 375, hole_qa_part 257, ribbon_sweep 109).
- Left for other owners (Known issues): Extrude's `_recompute` has no closed-dialog guard;
  Create Sketch attaches to the Tip's face, so suppressing an unrelated earlier hole also
  suppresses that sketch's holes (see `hole.earliest_face`); helper sketches in the browser.

### 2026-10-11: Sweep, Loft, Rib and Web (branch `sf/sweep_loft`)
- New: `curves.py` (connected paths with a direction, tangent chains, rotation-minimizing
  frames, twist guides), `curve_pick.py` (sketch-area picker, curve highlight, the blue
  distance ball `PathHandle`, value box that takes a decimal comma), `sweep.py` /
  `sweep_ui.py` (Sweep), `loft.py` / `loft_ui.py` (Loft), `rib.py` / `rib_ui.py` (Rib and
  Web). Commands `SciForge_Sweep`, `SciForge_Loft`, `SciForge_Rib`, `SciForge_Web`. Ribbon:
  Rib and Web enabled (two lines in `ribbon_config.py`). No core patch.
- In plain words: Sweep moves a profile along a path (all of it or part of it, both ways
  when the profile sits inside the path), optionally guided by a rail, tapered or twisted;
  Loft blends profiles in the order you click them, optionally along rails or a
  centerline; Rib fills a corner with a plate drawn as one line; Web makes a grid of plates
  from several lines. FreeCAD's own Pipe / Loft are used when they give Fusion's result,
  SciForge's own feature otherwise.
- Tests: scenarios `sweep_loft_sweep`, `sweep_loft_sweep_cut`, `sweep_loft_sweep_rail`,
  `sweep_loft_loft`, `sweep_loft_loft_guides`, `sweep_loft_rib`, `sweep_loft_web` (real
  input only); golden ops in `golden/sweep_loft_ops.py` (`sf_curves`, `sf_sweep(_edit)`,
  `sf_loft(_edit)`, `sf_rib(_edit)`) + 35 analytic models; unit tests
  `test_sweep_loft_schema.py`.
- Spec and gaps: `docs/sciforge/parity/sweep-loft-rib.md` (main gaps: Tangent Edges Merge
  because of the B-spline volume trap, Path + Guide Surface, loft end conditions).
- Full suite at the end (no --only, 2026-10-11): unit 185 OK (194 with the new schema
  tests, run after); golden 216 pass + 1 xfail (`plate_hole_grid`, needs core patch #4);
  smoke 70/70; journey 25/25; 79 of 79 scenarios PASS (6594 checks).

### 2026-10-11: QA of Patterns and Mirror (branch `sf/patterns-qa`)
- 5 new scenarios `patterns_qa_paths/edit/part/more/features.py` (17 paths, real input
  only) found and fixed: a pattern rebuilt by an edit (Suppression, Quantity formula, Faces)
  dropped the faces / edges later steps hung on (sketch, fillet, Press Pull); a FreeCAD pattern
  whose holes were all deleted kept their copies and froze the timeline after it; the first
  body's steps could not be picked while a second body was active; steps picked in the
  "wrong" order were repeated in click order (the copied boss filled its copied hole); the
  curved Total Angle handle was a sliver seen edge-on and a missed press picked the part
  behind it; a typed Total Angle past 180 showed the handle at 180; a plain click on an arrow
  threw away a typed formula; "<unknown exception data>" for a fillet face as Faces; a Python
  AttributeError after the patterned body was deleted; an edit could pick the pattern's own
  copy body; picked steps were not shaded and were listed in click order.
- 2 golden models: `pattern_rect_features_any_order`, `pattern_edit_keeps_later_fillet`.
- No shared file changed. Findings for other owners: see "Patterns QA findings" above.
- Full suite at the end (no --only): unit 153 OK; golden 123 pass + 1 xfail
  (`plate_hole_grid`); smoke 70/70; journey 25/25; 44 of 45 scenarios PASS, all 12 pattern
  scenarios among them. `sketch_draw` failed the same 3 checks as on `sf/patterns` ("circle
  diameter typed: 8" got r 4.97) while another worktree's suite ran, and PASSES alone (86
  checks): the sketch timing flake fixed on the integration branch (`si.click` rests 80 ms).
- Trial merge into `claude/inspiring-cerf-ragp6j` (git merge-tree): only MEMORY.md conflicts.
  That branch hangs a sketch on the step that made the face (not on the pattern); the
  `patterns_qa_edit` check accepts both.
### 2026-10-11: QA of Revolve (branch `sf/revolve-qa`)
- Branched with the current main (which holds the merged revolve), so the QA ran against
  today's product. Luca had not opened issues: the bugs below were found by using Revolve
  the way a Fusion user does, with real clicks, keys and drags only.
- 5 new scenarios (25 paths): `revolve_qa.py` (P1-P5: beginner path, axis first, wrong
  order, Esc mid-pick, values while the preview runs, three timeline edits + undo/redo),
  `revolve_qa_part.py` (P6-P10: on a part, Press Pull / Extrude around it, save, close,
  reopen, edit, back face from the rear view), `revolve_qa_more.py` (P11-P16: Revolve from
  an open sketch, E/Q while open, a cut that misses, the first revolve as a cut, a
  construction line axis, clearing the axis), `revolve_qa_bodies.py` (P18-P22: New Body
  edited to Join, edge-on handle drag, Intersect after reopening, a formula through
  undo/redo, numbers typed over the view), `revolve_qa_to.py` (P23-P26: Type To an origin
  plane, To <-> Angle with undo/redo, To a corner that moves when the block's sketch is
  edited, wrong objects refused).
- Bugs found and fixed (commits on the branch): Enter over the view did nothing; Ctrl+Z
  in the dialog committed the preview; Ctrl+S could save a half-made revolve; an unchanged
  dialog threw away the Redo list; formulas typed in the angle fields were dropped;
  Revolve from an open sketch took another sketch; clicks in another design were taken; a
  part edge in front of a hidden origin axis picked the axis and Fit framed the long axis
  lines; silent cuts (miss / remove all / nothing to cut); the preview recompute ran after
  the dialog closed; a face profile was lost after an earlier edit; Join <-> Cut refused
  when a later step used the revolve; digits typed over the view moved the camera; Type
  To was missing (now built, with its own golden models); switching To back to Angle
  broke the revolve (helper formula left behind); To squares covered the part so its faces
  and corners could not be clicked; all squares stayed shown after a plane was picked.
- Teammate scenario changed on purpose: `revolve_basic` expects Type Angle / To / Full.
- Shared files touched: `SciForgeTests/golden/schema.py` (append-only block: sf_revolve
  takes "to"), `MEMORY.md`. New spec `docs/sciforge/parity/revolve.md`.
- Full suite on the branch (no --only, code of commit 52eb1d9d4b, 87 minutes): unit 236 OK,
  golden 219 pass + 1 xfail (plate_hole_grid, core patch #4 not compiled; the golden
  `sf_revolve_to_cut`, added after the run started, passed on its own), smoke 70/70,
  journey 25/25, 93 of 93 scenarios PASS (10064 checks; revolve_qa 342, revolve_qa_more
  353, revolve_qa_part 306, revolve_qa_to 255, revolve_qa_bodies 228).
### 2026-10-11: QA of Shell, Draft and Scale (branch `sf/shell_draft-qa`)
- `sf/shell_draft` was already merged into main: the QA branch starts from the current main
  (so it tests today's product). 4 new scenarios with only real input, 25 paths:
  `shell_draft_qa_shell` (8: OK with nothing picked, body/face/body/x picks, Esc while
  dragging the arrow, values typed fast / "abc" / 0 / Delete / the arrow dragged through
  the surface and far in, E and F with the dialog open, two timeline edits with undo/redo,
  a boss sketched on the shell's floor + Press Pull, save/reopen and the edit to Both),
  `shell_draft_qa_draft` (7: a face clicked first becomes the Pull Direction, OK without
  faces, Q with the dialog open, the handle dragged far and negative, the pull arrow
  clicked, save/reopen/edit, a drafted + shelled moulded part edited), `shell_draft_qa_scale`
  (7: OK with nothing picked, shrink by dragging and grab the arrow again inside the part,
  a boss on the scaled top while the scale is edited and made Non Uniform, E with the dialog
  open, a corner point followed through an Extrude edit, parameters + Change Parameters,
  save/reopen), `shell_draft_qa_mix` (7: Shell inserted at the rolled-back marker under a
  boss, edited, Scale from the browser, timeline Delete / Ctrl+Z, Suppress, Ctrl+S with a
  dialog open, a cup).
- Bugs found and fixed (details in Known issues): later steps lost their faces when a
  shell was edited (Both thickness, Inside to Both swap: sketch "subshape not found", Press
  Pull failed or silently took the back wall) or a scale went Non Uniform; a 1 mm cup wall
  refused as too thick; the Shell arrow vanished after a 0; arrows stayed "held" after a
  drag (every later click ignored) and could not be grabbed inside the see-through part;
  Draft's box was "Plane" (spec: Pull Direction) and its arrow could not be clicked to flip
  (Fusion can); the pull arrow covered faces to click; a flip click also picked the face
  behind it; dragged handles did not come back to their limits; Change Parameters did not
  list SciForge's Shell / Scale values (`parameters.py`, unowned: one dict + one branch).
- Golden models `sf_shell_both_edit_presspull`, `sf_shell_swap_presspull_follows`,
  `sf_scale_non_uniform_keeps_faces` (all three fail on the base code, checked) and
  `sf_shell_cup`.
- Full suite on the branch (no --only, at code commit d201082764, 92 minutes): unit 244 OK,
  golden 254 pass + 1 xfail (`plate_hole_grid`, core patch #4 not compiled), smoke 70/70,
  journey 25/25, scenarios 98 of 100 PASS (10418 checks; shell_draft_qa_shell 442,
  shell_draft_qa_scale 368, shell_draft_qa_draft 362, shell_draft_qa_mix 252, the five
  teammate shell_draft scenarios 365, ribbon_sweep 112). The 2 failures are the known
  baseline ones not owned here: `sweep_loft_loft` and `sweep_loft_loft_guides` use
  `p.field` of the old Offset Plane dialog (`ConstructPanel` has no `field` on main
  eefca10bc0 either).
- Left for other owners: `construct_ui.py` uses `handles3d` handles inside a PickPanel
  dialog (greedy selection): after a drag the handle stays "held" (task suggested);
  `presspull.py` stores short face names only (SciForge's dialogs now repair them).
### 2026-10-11: QA of the body tools (branch `sf/bodies-qa`)
- Used the six body tools like Luca would (wrong pick order, OK with nothing picked, Esc
  half way, values typed while the preview runs, handles dragged far and negative, edits
  from the timeline twice, undo/redo, save/close/reopen/edit, Create Sketch/Extrude/Press
  Pull before and after, a part of several features, another command's key while a dialog
  is open). Scenarios `bodies_qa.py` (paths A-H) and `bodies_qa_2.py` (paths I-R).
- Bugs fixed (all in the bodies files): (1) after a Combine the used-up tool body stayed the
  active body, so the next sketch/extrude went into a hidden body; (2) the same after
  reopening a file (the observer slot the teammate used never fires); (3) editing a Combine
  from the timeline did not show its tools; (4) a click on a picked tool under the Join
  preview landed on the preview and could not drop it; (5) Move: choosing Point to Point or
  Rotate before the body took the body click as the point/axis; (6) the browser's and the
  timeline's own Delete of a used-up tool body broke the Combine (now kept, same undo step);
  (7) deleting a New Body Combine's target body broke it (FrozenTarget), and such Combines
  can be edited; (8) Point to Point on a round edge snapped to the circle's seam point;
  (9) face looks were lost when the body was moved; (10) faces without a look (and bodies
  after Esc/undo of a look) turned lavender instead of the usual grey; (11) a failed
  Combine/Move/Delete Face kept showing its last result; plus Physical Material by drag and
  drop (Fusion's way).
- Known limit found: a Press Pull on a face a Join merged loses it when the Combine is
  switched to Cut (FreeCAD naming; FreeCAD's own Boolean does the same) and then keeps
  showing its last result (Press Pull owner).
- Full suite at the end (no --only, 4 CPUs shared with another agent's GUI tests): "all
  passed". Unit 166 OK; golden 158 pass + 1 xfail (`plate_hole_grid`, core patch #4);
  smoke 70/70; journey 25/25; 58 of 58 scenarios PASS, 4930 checks (bodies_qa 312,
  bodies_qa_2 225, the teammate's six unchanged: combine 90, split 82, move 85, delete 63,
  look 58, timeline 64; ribbon_sweep 104).
- For other owners: Press Pull (re-find a face like the sketch attacher does; a failed Press
  Pull should show the body without it), browser (material, hide used-up bodies), Inspect
  (mass via `bodies.mass`), timeline (roll back steps outside bodies), hole
  (`thread_ui.py`'s `slotFinishRestoreDocument` never fires).

### 2026-10-11: QA of CONSTRUCT and INSPECT (branch `sf/inspect-qa-2`)
- `sf/inspect` was already merged into main: the QA branch starts from the current main
  (6e2231074e). `sf/inspect-qa` was still checked out by an earlier, interrupted session's
  worktree, so the work is on `sf/inspect-qa-2` (that session's uncommitted work was carried
  over and finished here).
- Used the 19 CONSTRUCT entries, Measure, Section Analysis, Center of Mass and Interference
  like Luca would. 5 scenarios, only real input, 35 paths: `inspect_qa` (CONSTRUCT: OK with
  nothing picked, Esc after the first pick, picks the wrong way round, Plane at Angle typed /
  dragged far and negative / a formula, two timeline edits + undo/redo, Along Path dragged
  past the end, I with the dialog open, Ctrl+Z / Delete / Enter inside it, a drag that ends
  over the part, Press Pull before and after, a part of several features, save / reopen /
  edit), `inspect_qa2` (Measure: Delete, a third pick, a round face, inches, E with Measure
  open; Section on a construction plane that is edited and deleted, on a face dragged far
  both ways, features made after it, eyes, save / reopen / edit, undo / redo, delete),
  `inspect_qa3` (the boss deleted under an axis, a point and a section; Midplane + Mirror
  about it; Interference / Center of Mass across save / reopen and a deleted body; one body
  only), `inspect_qa4` (Measure inside a sketch; Measure from the Center of Mass sign;
  materials; Press Pull into another body + Interference; Esc while the arrow is held; a sum
  + one Enter; Point at Vertex through a construction plane; Section + Q), `inspect_qa5`
  (Plane Along Path on a sketch line + a sketch on that plane + edit; Measure with a sketch
  line picked first; E with Interference open; Q with Center of Mass open).
- Bugs fixed (details in Known issues, "Inspect QA findings"): (1) arrows / turning balls
  stayed held after a drag that ended over the part (every later pick was ignored, the
  known lead from the shell/draft QA); (2) Enter right after a sum or a minus ("70 + 5",
  "-15") only rewrote the box (regression since the integration kept FreeCAD's normalising);
  (3) the origin squares / axes lost clicks to an axis or a face the box cannot take, and
  construction geometry in front blocked picks behind it; (4) Create Sketch and (5) Mirror
  took the origin square behind a construction plane clicked in front of it (`pattern_ui`:
  one line); (6) a construction whose face/edge was deleted stopped its body from computing
  (the part vanished, errors after every change); (7) Section / (8) Interference / (9) Center
  of Mass whose plane or bodies were deleted printed errors after every change, and the
  Center of Mass silently switched to "all bodies"; (10) Measure counted a round face's seam
  in its perimeter; (11) Section Analysis cut sketches and construction planes too; (12) I in
  a sketch closed the sketch (Measure now runs inside it, Fusion's SKETCH tab has it);
  (13) Center of Mass ignored materials (now mass-weighted); (14) the Center of Mass sign
  could not be measured from; (15) Measure / Interference result lists were dark grey on
  the dark panel.
- Shared change: `pattern_ui._part_depth` (a construction plane in front of an origin square
  is a Mirror Plane). No core patch.
- Full suite at the end: not run (the session stopped on the spend limit); its scenarios
  were finished and checked by the third round below.
- For other owners: taskui (one Enter after a sum in every other dialog, see the finding).

### 2026-10-11: QA of CONSTRUCT and INSPECT, round 3 (branch `sf/inspect-qa-3`)
- Merged `sf/inspect-qa-2` (the round stopped by the spend limit) into the current main; only
  MEMORY.md conflicted (both sides kept; main had dropped the QA session logs, they are back
  in the Session log). All 12 inspect scenarios passed on the merged base as they were.
- In plain words: used CONSTRUCT and INSPECT like Luca would, with the mouse and keys only, in
  3 more scenarios (17 paths, 52 with the earlier rounds): `inspect_qa6` (a parameter typed
  into Offset Plane + one Enter, edited from the timeline; the arrow dragged up and down and
  the face picked again; an offset of an offset whose base is deleted, re-picked, undo/redo;
  two faces selected before Midplane; Plane at Angle on the origin Z axis; Delete in the
  browser + Undo; a typo in a formula; "-gap" in Section Analysis), `inspect_qa7` (a plane
  made with the timeline marker rolled back + Measure against it; a section made before a
  New Body, edited from the browser, the arrow let go over the part, another face, Flip,
  Esc; Interference of three bodies with an overlap and a touching pair, following an edit),
  `inspect_qa8` (the x of a selection box, OK refused in an edit, Ctrl+Z / Ctrl+Y after OK,
  Center of Mass x, a timeline double-click with a dialog open, the Along Path dot let go
  over the part, a section of a body moved by its Placement).
- Bugs fixed (details in Known issues, "Inspect QA round 3"): (1) letting go of the Section
  arrow over the part moved the section onto the face under the mouse; (2) one press could
  move the arrow and a turning ball together; (3) a typo in a CONSTRUCT value box + Enter
  closed the dialog with the old value; (4) Section Analysis ignored parameters/formulas;
  (5) editing a construction that lost its reference picked the origin square behind it
  instead of the face; (6) the CONSTRUCT dialog did not show that a value follows a
  parameter; (7) Section handles were sized from the last body only; (8) a body moved by its
  Placement was drawn cut in the wrong place; (9) bands of the Section hatch were missing on
  a cut seen at a slant (checked on the screenshot).
- New golden model `inspect_three_points_oblique_hole` (a construction point in Plane Through
  Three Points, a slanted hole cut from that plane: 12000 - 520 pi / 12).
- No shared file changed; no core patch.
- Full suite at the end (no --only, at d43207a93a): unit 245 OK, golden 264 pass + 1 xfail
  (plate_hole_grid, core patch #4 not compiled), smoke 70/70, journey 25/25, 120 of 120
  scenarios PASS (15447 checks; inspect_qa6 317, inspect_qa7 314, inspect_qa8 251).
### 2026-10-11: QA of Box, Cylinder, Sphere, Torus, Coil, Pipe, round 3 (branch `sf/primitives-qa3`)
- Merged the stopped agent's `sf/primitives-qa2` (three fix rounds + a WIP commit) and
  finished it: its coil, pipe and part scenarios now run and pass.
- Fixed (each found by a scenario or a headless probe, each with a golden model or a
  scenario step that fails on the old code): pipe round a sharp corner failed (FreeCAD's
  "Transformed" corner; now mitred) and SciForge's own sweep silently followed only the
  first leg; a typed pipe wall was overwritten when a curve was picked or dropped; a
  negative coil Angle built the mirror image below the plane instead of a coil narrowing
  as it rises; a tapered coil on a raised face drifted (FreeCAD's helix); a hollow pipe
  round a closed path came out solid (FreeCAD's pipe); a timeline Delete of a pipe left
  its hidden path helper behind. See "Primitives QA findings".
- New scenarios `primitives_qa_more` (conical spring with type change, a too-steep angle,
  edit, undo/redo, save / reopen / edit; torus groove with drag and edit; E with Pipe
  open) and `primitives_qa_ring` (hollow ring round a parameter-driven sketch circle, Esc
  mid-pick, Change Parameters, edit + Esc, save / reopen / edit, timeline Delete). Golden
  models `sf_pipe_corner_*` (3), `sf_pipe_ring_*` (2), `sf_coil_taper_*` (6).
- `primitives_qa` C clicked XY at a spot now behind the YZ square (the squares are as big
  as the design since qa2): it clicks where XY is in front.
- Full suite at the end (no --only, commit 7de7a3d8ae): unit 245 OK; golden 273 pass + 1
  xfail (`plate_hole_grid`, core patch #4); smoke 70/70; journey 25/25; 119 of 119
  scenarios PASS (13215 checks; primitives_qa 107, _qa_paths 81, _qa_keys 47, _qa_part 83,
  _qa_coil 61, _qa_pipe 54, _qa_more 80, _qa_ring 60). It took about 1 h 55: with 119
  scenarios the suite is close to a 2-hour limit on a busy machine.
### 2026-10-12: QA of Sweep, Loft, Rib and Web (branch `sf/sweep_loft-qa`)
- Break-and-fix pass with only real input (sketches drawn with the mouse, typed sizes,
  volumes hand-derived from what was drawn): 5 new scenarios, 21 paths:
  `sweep_loft_qa_sweep` (beginner / OK and Enter with nothing / boss on the sweep and edits
  with taper and distance / values and the ball dragged far and back / Esc mid-pick + Redo /
  wrong order + another command's key), `sweep_loft_qa_loft` (wrong order, Esc and Q
  mid-pick, centerline added under a boss, save-reopen-edit, used profiles not taken again),
  `sweep_loft_qa_rib` (rib before the part, gusset values, arrow dragged out and back, One
  Side / Flip Side / Depth, earlier Extrude edited, edit twice + Cancel, save-reopen-edit +
  Enter), `sweep_loft_qa_web` (Shell tray, pick / drop on the preview, Extend / Flip / One
  Side / Depth, Esc mid-pick, Ctrl+Z in an edit), `sweep_loft_qa_part` (sweep along the
  cylinder's top edge: Cut by itself, Intersect, Press Pull after it, save-reopen-edit, the
  Extrude edited). Golden `sf_web_depth_thin_wall`.
- 12 bugs fixed (see Known issues): edits refused when a later step used the sweep / loft;
  Redo list lost by just opening Sweep / Loft; New Body shown late and not chosen for a
  sweep away from the part; Profile box not lit after a path clicked first; empty sweep
  errors; web poking through thin walls; Create Sketch on a construction plane; loft
  sections offered again; menu-command tooltips hidden; picked part edges / faces lost
  after reopen + edit (sweep, loft, Press Pull).
- Shared files touched (minimal): `commands.py` (tell), `extrude.py` (ensure_regions),
  `profile_pick.py` (Sections), `sketch_ui.py` (datum plane in front), `presspull.py`
  (refind / remember), scenarios `sweep_loft_loft.py` (face profile now SciForge's loft)
  and `bodies_qa_2.py` (path R: the Press Pull now keeps its face, 13500).
- Full suite once at the end (no --only, 2026-10-12): unit 245 OK; golden 263 pass + 1
  xfail (`plate_hole_grid`, core patch #4); smoke 70/70; journey 25/25; scenarios 116 of
  117 PASS (13773 checks). The one failure, `bodies_qa_2` path R, expected the old Press
  Pull failure that the new face memory fixes; its expectation was updated (13500) and the
  scenario then passed alone (225 checks). No product code changed after the full run.

### 2026-10-12: Final integration of the QA rounds (main branch)
- Merged `sf/inspect-qa-3` (with qa-2), `sf/primitives-qa3` (with qa2) and `sf/sweep_loft-qa`
  after unit + golden runs; pushed (ebf14fd11f). The feature workflow is finished: every
  build stage and every QA round is on `claude/inspiring-cerf-ragp6j`.
- Fixed: deleting a pipe, sweep, loft or rib (timeline right-click, Delete key, browser)
  left the sketches it used hidden. They are read through helper objects (pipe path,
  sweep / loft binders), and only Profile / Sketch links were followed.
  `timeline_ops.used_sketches()` follows the step's helpers; `delete.py` uses it too.
  Scenario steps in `primitives_pipe` and `sweep_loft_sweep`, both failing without the fix
  (checked: the sweep's profile sketch stayed hidden as well).
- CI: every SciForge tests run since #52 was cancelled at the 90-minute limit (the suite
  needs ~2 h on one machine), so no quick update was built after #45. CI now runs 5 parts
  side by side: `--only base` (unit, golden, smoke, journey) and `--only scenarios --shard
  K/4` (`run_tests.sh`); the quick update is packaged by its own job once all pass.
- Full local suite (started 04:32 on 580bb54f50, ended 06:37): unit 245 OK; golden 276
  pass + 1 xfail (`plate_hole_grid`, core patch #4); smoke and journey PASS; 130 of 132
  scenarios PASS (16974 checks). The two failures re-ran PASS alone on fc1c19cc57:
  `inspect_qa4` broke because I edited the test helpers while the suite ran (the module is
  a symlink: one file loaded old, one new); `sweep_loft_qa_web` P2 checked the web's
  preview 0.7 s after typing on a busy machine (its wait is now 1.5 s).
- The first split CI runs (#58, #59) failed only on GitHub, in two scenarios:
  - `bodies_qa_2` P: GitHub's renderer picked the vertex where OpenCASCADE starts the boss's
    top circle, and Move took that point. Fusion has no such point: `move.seam_circle()`
    makes a click on it mean the round edge (centre). Path P now clicks it on purpose.
  - `inspect_qa8`: the command dialog is wider on GitHub's runner and covered the box
    corner (40, 30, 10); the clicks went to the dialog. Imitating GitHub's font locally did
    not reproduce it, so a click's note now says what was on top ("on top: TaskPanel"
    proved it). `h.click`, `h.click_edge` and the corner click pan the view first when the
    dialog covers the point (`h.uncover`); `harness_covered_click` checks that.
- CI green on d005d2d92a (run #61, all 5 parts, about 33 minutes): its quick update has
  everything up to this session.
- Full build run #2 (Luca, 2026-10-12, 4 hours): both platforms compiled and packaged, then
  its tests failed (Windows golden: 234 errors, 43 pass; Linux: golden and every scenario).
  Cause: `src/Mod/SciForge/CMakeLists.txt` listed SciForge's modules by hand and still had 35
  of 116 (`cannot import name 'blend' from 'sciforge'`); the quick update copies the whole
  folder, so only the full build lacked them. The 5 extrude "failed to compute" errors had
  the same cause (reproduced here: the installed copy of the old rules gives the same 234).
  Fix: the rules glob every module, icon and test file; `tools/sciforge/check_install.sh`
  (runs the real install rules with CMake into a scratch folder and compares) runs on every
  push and first in the build (fails in a minute, not after hours). On the installed copy
  of the new rules: unit OK, golden 276 + 1 xfail, smoke and journey PASS, 6 scenarios PASS.
  The build's Linux test now runs unit/golden/smoke/journey; the scenarios run on the built
  AppImage in a separate 4-part job that does not hold up the uploads.
- ViewCube (plan B, Python, merged 62cf7836c6): `viewcube.py` (geometry, views, turntable
  drag, arrows, hit-test, Home storage; no Qt) + `viewcube_ui.py` (QPainter widget over the
  view); FreeCAD's NaviCube hidden via `VIEWER_SETTINGS` (`ShowNaviCube`). Click a face /
  edge / corner (animated), drag = constrained orbit, face-on triangles (90 degrees) and
  roll arrows, Home in `doc.Meta["SciForgeHome"]` (saved), right-click menu (Go Home,
  Orthographic/Perspective, Set Home: Fit / Fixed Distance, Reset Home), Ctrl+Alt+V,
  X/Y/Z triad. Scenarios `viewcube_click/_drag/_arrows/_home/_menu` (each fails without the
  feature). Open: Fusion checks (arrow set, default Home corner, snap after a drag),
  Perspective with Ortho Faces, Go Home in one move. Also fixed `marking_menu._install`
  watching a view being deleted (traceback on close + open).
- CI run #70 (ViewCube merge): `viewcube_menu` failed only on GitHub ("FreeCAD's NaviCube is
  back"). Real bug, older than the cube: `theme` kept the user's viewer settings in memory,
  but FreeCAD saves its preferences on quit, so after quitting with SciForge on, the next
  session took SciForge's values for the user's and leaving SciForge kept them (no NaviCube,
  Revit navigation, dark background in Part Design). Each CI part shares one profile, so an
  earlier scenario had "quit with SciForge on". Fix: the user's values go to
  `Mod/SciForge/ViewerBackup` (kept until restored); `shell.startup()` (from InitGui) and
  `on_workbench` restore leftovers when SciForge is off. Scenario `viewer_settings_restart`
  (restart imitated by reloading `theme`) fails without the fix.
- CI run #72: `sketch_infer` path A failed only on GitHub (the Ctrl line came out level).
  Not the Ctrl code (the end landed exactly on the clicked pixel): the start was clicked
  without Ctrl, so FreeCAD's grid snap (a fifth of the 10 mm grid) put it on y = 20, and
  the test's pixel for y = 20.35 maps to 20.02 (GitHub) or 20.16 (here), so the angle
  passed here by luck (0.25 > 0.2). Path A now holds Ctrl for both clicks and checks both
  ends against the clicked pixels. Reproduced and checked with GitHub's font locally:
  `XDG_CONFIG_HOME=<dir with fontconfig/fonts.conf preferring DejaVu Sans>` (the AppImage
  forces FONTCONFIG_FILE, but its fonts.conf reads the user's XDG file).
- Lessons: do not edit files a running local suite uses (work in a `git worktree`); the
  agent proxy blocks downloading CI artifacts, so put diagnostics into the check details
  (they appear in the job log).
- Full build run #3 (31239bf4a0, started by Claude): both platforms compiled and packaged;
  Linux tests passed and the AppImage was uploaded. Windows golden: 275 pass, 2 errors
  (`sf_shell_both`, `sf_shell_both_edit_presspull`: "sh1 failed to compute"), so no .7z.
  Cause: Shell Both tags its two walls `1 << 40 + 2 * ID` (`shelling.TAG_BASE`), and FreeCAD
  keeps a shape's tag in a C `long`, which is 32 bits on Windows: "Python int too large to
  convert to C long", so every Shell Both failed on Windows (for Luca too, since the
  2026-10-11 Shell QA). Reproduced on Linux with a tag past 64 bits (same 2 errors, same 9
  passes). Fix: `TAG_BASE = 1 << 30`, tags above 2**31 - 1 skipped; unit test
  `test_wall_tags_fit_windows`. Lesson: any number handed to FreeCAD's C++ must fit 32 bits
  (Windows `long`).
- Build pipeline after run #3 (Luca: "one single item wasted hours"): (1) the golden models
  now also run on the official FreeCAD for Windows (`tools/sciforge/windows_golden.sh
  --stock`), in "SciForge tests" on every push (job "tests (Windows golden models)"; the
  quick update waits for it) and in the build as `check-windows` before compiling; (2) the
  build uploads the .7z / AppImage before testing it (a failed test no longer throws away
  the compile; the quick update fixes Python problems on top); (3) the build's concurrency
  group includes the platform choice, so a Windows-only build does not cancel a running
  build of both. Not done: a compile cache between builds (ccache is in the recipe but not
  kept between runs); a rebuild still takes the full 3 hours.
  Reviewed by 3 independent reviewers plus a refuting check (7 agents): nothing that touches
  run #4. Kept on purpose: `check-windows` also gates a Linux-only build (it is the only
  golden-model run before compiling; Linux-only builds are rare). Fixed after review:
  windows_golden.sh keeps FreeCAD's whole output (golden.log) and prints its end when no
  report came out; README no longer promises the quick update fixes a red built test.

### 2026-10-12: Sketch inference feasibility + prototype (branch `worktree-agent-a27127a70299bdc90`)
- Question (plan C1): can Fusion-like inference be done in Python on FreeCAD's own sketch
  tools? **Yes.** Probes in real FreeCAD 1.1.4: a filter that replaces a mouse event by a
  copy at another pixel moves FreeCAD's point exactly there; the Snap master switch and
  the sketch's Autoconstraints are read live; stock Ctrl drew a line at exactly 10.000
  degrees (5-degree steps), confirming the opposite-of-Fusion behaviour.
- Built `sketch_infer.py` (mouse filter, overlay, constraints after the click) and
  `sketch_infer_core.py` (pure maths, 26 unit tests), hooked into `SketchSession`
  (`_ViewFilter` gives it every mouse event first; commit/undo signals; Esc; close).
  Undo: "Inferred Constraints" is glued to the step before it (`sketch_mode.GLUED_STEPS`,
  the same mechanism as "Sketch recompute", now looping over several glued steps).
- Scenario `sketch_infer` (222 checks, real moves/clicks): Ctrl free point (also start
  coincident kept), guide snap + Vertical constraint (XY and XZ sketch), perpendicular
  from and onto a slanted line (exactly 90), level at 3.5 degrees / free at 6.8, parallel
  off/on, a typed length beating a guide, Ctrl+Z / Ctrl+Y. Parity:
  `docs/sciforge/parity/sketch.md` (new section). About 2 ms per mouse move on a
  400-curve sketch (box tests before distances; 7.6 ms without them).
- The first regression run caught 3 failures (grid snap, see Known issues); fixed.
- Not done / open: guides for rectangle corners, circle centres, arcs (Line only); the
  tolerances, the guide colour and whether Fusion adds a constraint on a guide click
  are unconfirmed (Luca's Fusion checks 3-6 in `plan.md`); Ctrl pressed without moving
  the mouse takes effect at the next move; FreeCAD's own line steps stay two undo steps.

## Next steps (in order)

0. **The current plan is `docs/sciforge/plan.md`** (2026-10-12, after the research report
   `reports/Fusion sketching ViewCube and navigation.md`). Done on 2026-10-12: stable orbit
   (A1), the Python ViewCube (B), sketch inference for Line (C1-C4, Ctrl in every tool), the
   full-build fix (install rules). Next: A2-A3 (orbit choice, mouse details), inference in
   the other sketch tools, glyphs beside the geometry, tangent-arc drag in L; then selection,
   components, joints, versions. Luca's Fusion checks (plan, last section) tune the details.
   The items below are older and partly superseded by it.
1. Done: all feature builds and QA rounds are merged (see the 2026-10-12 log). Open items
   left by the QA rounds, none blocking:
   - a length formula typed into an angle box is accepted (Fusion refuses it);
   - coils and pipes saved before the QA fixes keep their old shape until edited once;
   - Extrude Join with a profile away from the part says "separate solids", while Sweep and
     Loft switch to New Body (Fusion makes a new body);
   - other features than sweep / loft / Press Pull may lose picked edges / faces after
     save, reopen and edit (the "remember element" fix was made for those three);
   - the gaps listed at the end of each `docs/sciforge/parity/*.md`.
2. Luca installs the newest green quick update and redoes his session; ask for the copyable
   SciForge > Diagnostics text whenever something misbehaves, and the Fusion right-click menu
   screenshot (slot order).
3. Full Windows build: patches #4, #6, #7 compile (run #2/#3, `plate_hole_grid` PASS). Run #3's
   .7z was held back by the Shell Both tag bug (fixed 2026-10-12): a Windows-only build of
   the fix gives Luca the download.
4. Get answers to outline section 12 + parity captures of Luca's Fusion workflows (2.4).
5. Spike 9.2 (Fillets): 100+ case benchmark from real part workflows, success-rate metric.
6. Branding pass (app name, icons, user-data folder, installer) so CI can ship an installer.
7. Grow golden models toward 100 (gear, bottle loft+shell, sweep pipe, snap-fit, hinge, threads).
