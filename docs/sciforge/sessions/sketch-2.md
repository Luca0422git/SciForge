# Session log: sketch, part 2 (branch `sf/sketch-2`, wave 5, 2026-10-16)

Relaunch of the wave 5 sketch-2 builder (the first one stopped at the usage limit before it
committed anything). Started from 2273d4e0ab (Luca's four fixes merged). Spec, sources and
gaps: `docs/sciforge/parity/sketch.md`, section "Sketch, part 2" at the top and Known gaps;
`parity/selection.md` (sketch boxes, chains, planes); `parity/text-emboss.md` (T17). No
FreeCAD core file changed (no full build needed).

## What was built

- **Chain selection in a sketch** (`sketch_select.py`, rule `sketch_select_core.py`): a
  double-click on a curve (no tool running) selects the curves joined to it end to end, of
  its line type; a circle alone. FreeCAD's own double-click wire selection never fired under
  SciForge (checked with real double-clicks), so SciForge finds the curve itself and swallows
  the double-click and its release (FreeCAD toggled the clicked curve off).
- **Box selection in a sketch with Fusion's modifiers**: FreeCAD's sketch box already does
  window / crossing by direction but always added; a plain box now replaces (the selection is
  cleared before FreeCAD sees the release), Shift adds, Ctrl toggles (put aside, toggled
  after FreeCAD's box).
- **Sketch Fillet** (`sketch_fillet_tool.py`, `sketch_fillet_core.py`, `sketch_fillet_ui.py`):
  SciForge's own tool on the sketch handler for lines, arcs and circles in any pair (a corner
  point or two curves), pointer or typed radius, FreeCAD's `SketchObject.fillet` makes it, a
  Radius dimension, refusals with the reason. SKETCH > MODIFY > Fillet runs it; FreeCAD's
  fillet tool (which never saw a click on CI, #123-#126) stays the fallback.
  `modeling2_sketch` now uses it (its CI fallback is gone).
- **Chamfer between a line and an arc** (`sketch_chamfer_core.line_arc_*`,
  `sketch_chamfer_tool._build_arc`): corner point or the two curves, all three types; SciForge
  goes further than Fusion (Autodesk documents line-line only).
- **Text frame resized by a corner drag** (`text_ui.TextLayer`, `text_core.resized_frame`).
- **Box selection of planes, axes and points** (`selection_ui._work_elements`,
  `selection_core.box_kinds`).
- **A sketch's curves outside the sketch belong to it** (`sketch_companions.py`): Project to
  Surface's "Projected Curves" and the new "3D Curves": listed under the sketch in the
  browser, shown / hidden with it, no timeline step of their own, deleted with it; hidden by
  Show Projected Geometries while the sketch is open.
- **3D Sketch** (`sketch3d.py`, `sketch3d_core.py`, `sketch3d_ui.py`): the palette's 3D Sketch
  box; L and Fit Point Spline draw 3D lines and splines with the manipulator (XY / YZ / ZX
  planes at the last point); snapping to 3D points, sketch points (tied), corners and edges
  of the design, the grid; the triad moves a 3D point (drag an arrow, or type a distance +
  Enter). Sweep takes the 3D curves as its path. **Built as a separate 3D-curve feature**
  (a companion object of the sketch, sketch coordinates), because FreeCAD's Sketcher cannot
  hold a curve off its plane. A line whose ends both lie on the sketch plane is an ordinary
  sketch line (joined to the points at its ends; it makes profiles, as in Fusion).

## FreeCAD facts and traps found

- `QTest.mouseDClick` (Qt 6) sends press, release, double-click and **no release** after the
  double-click; a real mouse sends one. Scenarios add the release (`sketch2_select.dclick_at`);
  without it FreeCAD's sketch stays in its rubber-band state and the next tool's clicks were
  lost. SciForge also resets its "swallow the release" flag on the next press.
- FreeCAD 1.1.4's sketch box (`ViewProviderSketch::doBoxSelection`) is window from left to
  right and touch (crossing) from right to left, and only adds to the selection.
- FreeCAD draws an origin plane as a square in the plane's first quadrant, set off from the
  origin (`ViewProviderPlane::updatePlaneSize`: corners at 8 and DatumPlaneSize 62, scaled), and
  as the whole square round the origin while it is hovered or selected: a box drag that passes
  over it changes its bounding box. `ViewObject.getBoundingBox()` gives what is drawn.
- `obj.Parents` gives the selection path of an origin plane, `[(Body, "Origin.XY_Plane.")]`;
  `Gui.Selection.addSelection(doc, "Body", "Origin.XY_Plane.")` selects it as a click does.
- The Sketcher's slice (`TempoVis.sketchClipPlane`) keeps the half behind the sketch as seen
  (SoClipPlane normal away from the eye); checked from above and below.
- `Part.ArcOfCircle.setParameterRange(u0, u1)` trims an arc in place and keeps its sketch
  extension (construction flag, geometry id); assigning `sketch.Geometry` back keeps it.
- A sketch point's construction flag is not kept in the file (after reopening
  `getConstruction` is False for a point that was construction).
- `Sketch.ExternalGeometry` is read-only from Python; there is no call to re-point one
  external reference in place.
- **TNP limit (stock FreeCAD 1.1.4, reproduced headless without SciForge)**: a pad of a
  rectangle whose width dimension changes loses the external references to its vertical
  edges and corners on the moved side ("missing element reference ... ?Edge2", "Failed to
  project external geometry"); the projected curve stays where it was. Its top and bottom
  edges follow. (2 of 12 edges, 4 of 8 vertices lost; Refine on or off.)
- `sweep_ui` mapped every non-sketch edge to the body's base feature (`curve_pick.base_element`)
  and refused edges of other objects: a sketch's 3D curves are now taken as they are.
- An object that links a sketch twice (Projected Curves: its curves and its owner) appears
  twice in `sketch.InList`.

## Tests

New scenarios (real FreeCAD 1.1.4, real input, one at a time): `sketch2_select` (82 checks),
`sketch2_fillet`, `sketch2_text_frame`, `sketch2_box_planes` (43), `sketch2_project`,
`sketch2_3d`, `sketch2_palette`; counts of the final run are in the report. Updated:
`modeling2_sketch` (SciForge's fillet). Unit tests: `test_sketch_select_core.py`,
`test_sketch_fillet_core.py`, `test_sketch3d_core.py`, `test_sketch_chamfer_core.LineAndArc`,
`test_browser_core` (curves under their sketch), `test_selection_core` (work geometry).
Regression in one profile: every `sketch_*`, `sketch_text_*`, `sketch_tools_*`,
`fixsketch_*`, `selection_*`, `emboss_*`, `timeline_browser*`, `sweep_loft_sweep`,
`sketch_sweep`, `ribbon_sweep`, `bodies_delete`, `mesh_separate_combine`, `modeling2_sketch`,
plus `--only base`.

## Gaps (also in the parity docs)

- 3D Sketch: no rotation handles on the manipulator, no key to cycle planes, no typed
  length / angle for a 3D line, no constraints or dimensions on 3D curves, no 3D arcs; a
  spline drawn with the box checked is a 3D curve even when it lies on the sketch plane.
- Project to Surface curves cannot be dimensioned from the sketch; no Break Link.
- The FreeCAD TNP limit above (re-project the edge); a repair by geometry is not built.
- No Linetype Centerline.
- The double-click chain keeps to the clicked curve's line type (Guess).

## Shared files touched (one or two lines each, for the merger)

`sketch_mode.py` (session hooks: chain / box, 3D layer, companions observer, Show Projected
Geometries), `sketch_draw.py` (`curve_at(own=)`, 3D preview points), `sketch_palette.py` (the
3D Sketch box), `sketch_tools_ui.py` (L in 3D), `sketch_project.py` (adopted by its sketch),
`text_core.py` / `text_ui.py` (frame resize), `selection_core.py` / `selection_ui.py` (planes),
`browser_core.py` / `browser_ui.py` (curves under their sketch, Delete), `delete.py` and
`timeline_ops.GOES_WITH_STEP` (deleted with the sketch), `sweep_ui.py` (3D curves as a path),
`ribbon_config.py` (the Fillet and Fit Point Spline lines only).
