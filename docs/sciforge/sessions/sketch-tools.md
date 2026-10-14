# Session log: the remaining sketch tools and constraints (`sf/sketch-tools`)

Date: 2026-10-13. Feature outline 7.5. The behaviour spec with its sources is in
`docs/sciforge/parity/sketch.md`, section "The remaining sketch tools and constraints".
No FreeCAD core file was changed (nothing new in `core-patches.md`).

## What was built

All in `src/Mod/SciForge/sciforge/`:

- `sketch_draw.py`: SciForge's own sketch drawing handler (`DrawTool`). The open sketch's
  view and key filters (`sketch_mode`) hand it the mouse and keys first. It snaps like
  FreeCAD's tools and SciForge's inference (points, line middles, curves, guides, grid;
  Ctrl = free), draws its preview as Coin nodes of its own, shows value boxes beside the
  shape (digits go in, Tab moves on, Enter takes them; typed values become dimensions),
  shows its prompt beside the pointer (`Hint`), makes each shape one undo step and then
  repeats. A FreeCAD tool started meanwhile (its bitmap cursor) ends it.
- `sketch_draw_core.py` (no FreeCAD, no Qt; `SciForgeTests/unit/test_sketch_draw_core.py`,
  37 tests): the maths of every new tool.
- `sketch_build.py` (no Qt): the shapes with their constraints, and Trim / Extend / Break.
- `sketch_draw_tools.py`: Midpoint Line, 3-Point Rectangle, 2-Point Circle, 2-Tangent
  Circle, 3-Tangent Circle, Tangent Arc, Edge Polygon, Center to Center / Overall /
  Center Point Slot, Three Point Arc Slot, Conic Curve.
- `sketch_modify_tools.py`: Trim (T; click, or press and drag across several pieces),
  Extend (one click), Break.
- `sketch_constrain_tools.py`: Collinear, Concentric, Midpoint, Curvature (pick two;
  a selection made first applies at once; Esc ends).
- `sketch_project.py` / `sketch_project_tool.py`: Project to Surface (a "Projected
  Curves" object; Closest Point and Along Vector).
- `sketch_draw_ui.py`: the commands. `ribbon_config.py`: the menu entries (Trim / Extend /
  Break fall back to FreeCAD's if SciForge's are missing). `config.PREFERRED`: T runs
  SciForge's Trim, P SciForge's Project. `sketch_marking.py`: Trim in the right-click list.
- `sketch_mode.py`: the tool hooks; Fit Point / Control Point Spline: Enter and OK make
  the spline, Esc cancels it, the spline is one undo step.

Scenarios (`SciForgeTests/gui/scenarios/sketch_tools_*.py`, helpers in
`SciForgeTests/gui/sketch_tools_steps.py`): draw, circles, slots, modify, constraints,
audit, project, extrude. `sketch_infer_tools.py` (S: slot) now runs on SciForge's slot.

## FreeCAD facts and traps found

- FreeCAD's command runner (`Gui::Command::invoke`, its `AutoTransaction`) closes the undo
  step the B-spline tool opens in `activated()` as soon as the tool has started. The
  poles / knots clicked afterwards are in **no** undo step: Esc could not take them back,
  and a Ctrl+Z after a finished spline undid the step *before* it (in a test: a whole
  rectangle). SciForge calls `App.setActiveTransaction("Add Sketch B-Spline")` at the
  click (`SketchSession.open_spline_step`); the spline tool's own `commitCommand` then
  commits it.
- FreeCAD's spline tool makes the spline on **Esc** or its right click (`quit()` with 2+
  points); `Sketcher_StopOperation` only drops the handler. A right click sent with
  `QTest` never reached the handler; an Esc key event sent to the GL widget does (the key
  filter lets it through with `pass_escape`).
- FreeCAD 1.1's rectangle "3 corners" mode is a **parallelogram** through the third click
  (`DrawSketchHandlerRectangle.h`), not Fusion's 3-Point Rectangle.
- FreeCAD's slot tool asks for the end **radius** in its third box; Fusion asks for the
  width.
- In the sketch editor `EdgeN` counts construction curves (Edge3 = geometry 2); the
  sketch's `Shape` leaves construction curves out, so `Shape.getElement("Edge3")` can be
  another curve. `sketch_project.sketch_edge_name` maps by geometry. The shape is only
  current after a recompute (SciForge's tools, like FreeCAD's polygon, do not recompute).
- A Python `addGeometry` with no transaction open is in no undo step; Ctrl+Z then undoes
  the step before. Tests must open one (`doc.openTransaction`).
- `App.getActiveTransaction()` is the application-level step; `openTransaction` while
  one is active commits it.
- Qt 6 `QTest.mouseMove` without a button goes through `QCursor::setPos`: the window
  system delivers the move, so a tooltip under the pointer swallows it (the tools' prompt
  is a mouse-transparent label for that reason).
- An arc slot with a construction centre arc as well is over-constrained for FreeCAD's
  solver (redundant): SciForge's has none. Breaking a circle by splitting it twice leaves
  a half-redundant centre Coincident: replaced by a join at the seam.
- Collinear = Tangent between two lines; Concentric = Coincident between the centres
  (pos 3); a point at an arc's middle by Symmetric about a centre line can fall into a
  local minimum: the point is moved there first and the result checked.
- Curvature (G2): planegcs has no curvature constraint. Spline + line: tangent end to end
  plus the spline's third pole on the line gives curvature 0 at the joint (exact G2).
- The conic: a rational quadratic B-spline (poles start, apex, end; weights 1,
  rho/(1-rho), 1); `exposeInternalGeometry` adds Equal / Weight constraints on the pole
  circles that must be replaced by one Weight on the apex pole.
- In sketch edit mode a body face between the camera and the sketch hides the sketch's
  curves (no x-ray).
- Process trap: `black` run on a directory reformatted 76 unrelated files; only ever run
  it on named files.

## Gaps (what Fusion does that was not built)

- Text (another branch) and 3D Sketch.
- Chamfer's three types and a typed distance (FreeCAD's chamfer is used).
- Project to Surface: the curves are an object next to the sketch, not in it, and are not
  listed in SciForge's browser or timeline yet; sketch points cannot be picked (body
  vertices can).
- Conic: no rho handle on a finished curve; FreeCAD's Weight (rho / (1 - rho)) shows
  instead of rho; the pole circles show while the sketch is open.
- Curvature (G2) only between a spline and a line; with an arc, circle or spline: G1 and
  a note.
- 2-/3-Tangent Circle: lines only.
- No inference guides for the width clicks (slots, 3-Point Rectangle) or the conic's rho.
- Midpoint Line in empty space leaves a point at the middle (Guess, to be checked in
  Fusion).
