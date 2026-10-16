# Session log: sketch, part 3 (branch `sf/sketch-3`, 2026-10-16)

Phase 2 of Luca's improvement list (plan "Luca's improvement list", items F5 to F10), started
from `develop` 551de541. Spec, sources and gaps: `docs/sciforge/parity/sketch.md`, section
"Sketch, part 3" and Known gaps. No FreeCAD core file changed (no full build needed).

## What was built

- **F8 Auto project** (`sketch_auto_project.py`, `sketch_ui.create_sketch`): a sketch on a flat
  face gets the face's edges as purple, profile-making curves (one external reference to the
  face; FreeCAD projects every edge of a face). Preferences > Design > Sketch: "Auto project the
  face's edges when sketching on a face", default on (reset in the harness via
  `preferences_ui.reset_for_tests`). The face is the one of the step the sketch hangs on
  (`_earliest`); P on an edge or face already in the sketch adds nothing, P on a face adds only
  the edges still missing (`sketch_mode.projection_refused`, `sketch_auto_project.missing_edges`).
  Extrude takes the areas inside the one area the drawn curves close on their own
  (`sketch_regions.drawn_regions`), so "circle on a face, E" still picks the disc. Extrude says
  so when FreeCAD could not make an area the sketch shows (`extrude.lost_area`). Golden builder:
  a sketch step can take `face` (selector) and `auto_project`.
- **The face's own area** (found by the regression run: with Auto project the face around
  a drawing became a profile and took clicks meant for the face; 14 extrude / Press Pull /
  revolve scenarios broke): an area that only the curves Auto project made bound (ids kept
  in the sketch's hidden `SciForgeAutoProjected`) is the face's. It is not shaded in the open
  sketch (`sketch_regions.profile_regions`), not offered by Extrude / Press Pull / Revolve
  (`extrude.face_areas`, `profile_pick`), and an idle click over it goes to the face
  (`sketch_area_pick` lets that one click through; only the 3D view's own mouse events
  update it, the window's copies of the same event reset it before). Areas drawn against
  the projected edges and areas of P-projected curves stay profiles. Extrude and Revolve take
  by themselves what the drawn curves close (`extrude.taken_by_itself`). Revolve takes a
  part edge on an area's border as the axis (`_edge_on_border`).
- **F5 one snapping engine** (`sketch_infer_core.snap_points`, `crossings`, `nearest_snap`):
  ends, middles of lines and arcs, centres, quadrants, conic / spline ends, sketch points, the
  origin, crossings of curves, for the sketch's own and projected curves; radius `SnapPixels`
  (8, never under FreeCAD's own pick radius in screen pixels). FreeCAD's tools get the pointer
  moved exactly onto the point (`Inference._plan`); after the click `_snap_constraints` makes
  it exact and replaces what FreeCAD got wrong (a PointOnObject on the line through a corner ->
  Coincident at the corner; Symmetric; PointOnObject on circles / arcs / both crossing curves);
  the snapped curves are held still (Block) meanwhile. SciForge's own tools use the same points
  (`sketch_draw.DrawTool.snap_point`).
- **F6 45 degrees**: `DIAGONAL` in `_direction` (after level / upright and perpendicular),
  `DiagonalDegrees` (4; 0 = off), FreeCAD's grid off for it, an Angle constraint after the click
  (`sketch_infer.diagonal_constraint`, also in `DrawTool.snap_constraints`).
- **F7 glyphs**: square (end), triangle (middle), circle with dot (centre), diamond (quadrant),
  X (crossing), arc + stroke digits "45"; drawn by `sketch_infer.Overlay` and the SciForge
  tools' preview.
- **F9**: covered by F5 (the end landing exactly on the projected corner closes the loop) and
  the region checks; scenario `sketch_projected_profiles`.
- **F10 z-fighting**: `SoPolygonOffset(-1, -1)` inside FreeCAD's `SoSketchFaces` (made with the
  pick node, `sketch_area_pick._make`) and in `profile_pick.ProfilePicker` (was the default +1,
  the faces' own push); the front shift is brought up to date after a wheel zoom.

## FreeCAD facts and traps found

- **The "slightly off the corner" cause**: FreeCAD's `PickRadius` counts device pixels (Coin's
  viewport), Qt's mouse positions are logical pixels. On a 150 % screen FreeCAD reaches 3.3
  logical pixels, SciForge assumed 5 and left the snap to FreeCAD up to 5: in between nothing
  snapped. Reproduced with `QT_SCALE_FACTOR=1.5` under xvfb (environment variable passes
  through `run_tests.sh`): a click 4 / 3 px off a projected corner gave a PointOnObject on the
  projected line and a start at (0.297, 0). `QT_SCALE_FACTOR=1.5` is a cheap way to test scaled
  screens in the sandbox.
- `SketchObject.addExternal(obj, "FaceN", defining, intersection)`: a face is one external
  reference that yields one curve per edge (`rebuildExternalGeometry`, `processFace`). Adding the
  same face twice raises ValueError "Not able to add external shape element FaceN" and FreeCAD's
  own Project tool shows "Link to Face5 already exists in this sketch" plus a pyException in the
  Report view.
- Referencing the face of a later step (a hole drilled in the face) from a sketch that hangs on
  an earlier step broke the sketch when the hole was suppressed (fixsketch_hole D): project from
  the step the sketch hangs on.
- **FreeCAD 1.1.4's sketch areas (`SketchObject::buildInternals`, `Part::WireJoiner` with
  TightBound + MergeEdges) lose an area where an arc ends tangent on the middle of a line**: a
  rounded rectangle with a sharp rectangle drawn over it gives only the four corner slivers
  (1.93 mm2 each), not the 5634 mm2 inside; `sketch_regions` (generalFuse) finds it. Overlaps of
  straight edges alone (a rectangle from a projected corner, a line over a projected edge) are
  fine. `WireJoiner` is not exposed to Python; overwriting `InternalShape` from Python is undone
  by the next recompute (tried). Left as a known gap with a message in Extrude.
- `sketch.setConstruction(geoId, on)` on an external curve toggles its Defining flag per curve
  and FreeCAD keeps the flags of existing curves across `rebuildExternalGeometry` (copyFlags);
  not used in the end (it did not help the case above).
- FreeCAD snaps to a line's middle within 5 % of its length and to an arc's middle within 10 %
  of its angle, but only adds Symmetric for a line (`isLineCenterAutoConstraint`); quadrants,
  arc middles and crossings need SciForge's exact move afterwards.
- A move of a point onto a quadrant solved the whole sketch and nudged the free circle (its
  centre moved by 1e-5): the snapped curves are now pinned (Block) during the exact move.
- On a tilted view the forwarded pixel of a vertex can light up the line through it; the Line
  chain's own click at the line end (`LineChain._aim_at_vertex`) tries neighbouring pixels: the
  snapping must not move those probes back onto the vertex (`Inference.aiming`), or the next
  line started on the line, not its end (sketch_infer_undo U5).
- Under xvfb's software renderer equal depths resolve the same way every time: the z-fighting
  stripes Luca saw on his graphics card do not show in the sandbox, so `sketch_face_zfight`
  guards the drawing (uniform colours) rather than reproducing the bug.
- `pkill -f <pattern>` / `pgrep -f` in a wait loop match the waiting shell's own command line
  (also noted in MEMORY): count result files instead.

## Tests

New scenarios: `sketch_snaps`, `sketch_projected_profiles`, `sketch_face_zfight`; extended
`sketch_glyphs`. Updated where the behaviour changed on purpose: `sketch_face` (the face's
sides are projected; P adds only the boss's circle), `sketch_areas_more` (four areas: the face
around the circles too), `sketch_areas_face` and `pi5_case`'s lid sketch (Auto project off there:
the first is about the face outside the drawn areas, the second draws over a rounded rim, the
FreeCAD limit above). Unit tests: `test_sketch_infer_core` (SnapPoints, Crossings,
SnapAfterTheClick, Diagonal, Glyphs). Golden: `sketch_face_projected_corner`,
`sketch_face_projected_rest`. Regression (real FreeCAD, one run each, shared profile): all 65 sketch / fixsketch /
sketch2 / selection_sketch / emboss / timeline_browser / pi5_case / polish2 scenarios PASS
(selection_sketch after its update); extrude / Press Pull / extrudeface / hole / revolve /
sweep / misc_preferences (57): PASS after the face's-own-area rule, except
`extrude_feel` ("the held drag ran to the end": fails the same on the base commit under the
machine's load), `sweep_loft_loft` ("sketch open on XZ": fails the same on the base commit)
and `revolve_qa_part` P10 (below).

Open: `revolve_qa_part` P10 "the top back edge is the axis": the sketch's rectangle sits on
the top face's back edge, so with Auto project the rest of the face is an area bordered by
that edge; the harness's edge click presses where FreeCAD's pick finds the face (Face5), so
Revolve takes the press as an area click and ignores the edge FreeCAD selects on release.
`_edge_on_border` only helps when the press itself finds the edge. Fix idea: decide on the
release (as FreeCAD's selection does) or treat a press within a few pixels of a border edge
as the edge.

## Gaps (also in the parity doc)

- Shift for hidden midpoints (every midpoint is offered).
- Snapping to a not-projected edge or corner of the part does not project it (Fusion's "Auto
  project edges on reference").
- The FreeCAD WireJoiner limit above (a C++ fix in `buildInternals` / WireJoiner would be the
  root fix).
- Auto project takes the face of the step the sketch hangs on: a later fillet's rounded corners
  or a later hole are not in the outline (P adds them).
- Revolve and Sweep do not use the "drawn areas" rule for their automatic profile (sketches for
  them are rarely on faces).
- FreeCAD's own length / angle boxes show the pointer's raw value (44.84 deg) while the line
  snaps to 45; after the click it is exact.

## Shared files touched (for the merger)

`sketch_ui.py` (create_sketch: two lines), `sketch_mode.py` (Project refusal in the view
filter), `sketch_line.py` (`aiming` around the chain's own click), `extrude.py` (`lost_area`),
`extrude_ui.py` (`single_region`, `newest_single_region` returns a list, the lost-area note),
`sketch_regions.py`, `profile_pick.py` (offset), `sketch_area_pick.py`, `prefs_core.py` /
`preferences_ui.py` (one option, one reset key), golden `builder.py` / `schema.py` (sketch on a
face); scenarios `sketch_face`, `sketch_areas_face`, `sketch_areas_more`, `pi5_case`,
`sketch_glyphs`.
