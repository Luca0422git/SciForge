# Session log: surface-2 (wave 5, branch `sf/surface-2`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
Started from `2273d4e0ab`. No FreeCAD core file changed (no full build needed). Surface
Extrude's To Object does not share the solid Extrude's code (`extrude.curved_elsewhere`), so
the `extrudeface_*` scenarios are not affected.

## What was built

1. **Surface Extrude** (`surface_geom.extrude_curves`, `surface.target_of_ref`, `ExtrudePanel`):
   - Start **From Object**: a plane, flat face or point parallel to the profile sets the start
     height (Offset added on); a slanted plane or a curved face starts every line of the
     extrusion where it meets the object (a long band is cut with `generalFuse`, and the
     pieces are kept by line-hit tests, `_hits` / `_between`). A start face that does not
     cover the profile, a taper from a curved start and a whole body are refused with the
     reason.
   - Extent **To Object** on a curved face (carried on past its edges: `extended_face`), a
     whole body or a point; **Chain Faces** (on): the face and the faces joined smoothly to
     it (`shelling.tangent_faces`).
   - Extent **All** (Fusion's former Through All): as far as the visible bodies reach (they are
     saved in Refs2 with the step), Flip for One Side, both ways for Two Sides / Symmetric;
     no body that way: refused.
2. **Surface Revolve Type To**: a plane or flat face through the axis, an edge or a point; the
   shorter way round (`surface_core.stop_angle`, with `revolve.target_directions`).
3. **Surface Sweep Path + Guide Rail** with Profile Scaling Scale / Stretch / None (the solid
   Sweep's `_rail_part` / `_rail_sections` / `_transported`), and **Taper Angle** on Single
   Path (with Twist): `surface_core.taper_factor`.
4. **Surface Loft**: Guide Type Rails (one or two; sketch curves or edges of bodies) and
   Centerline; end conditions Free / Direction (sketch curves), Free / Tangent / Curvature
   (edges of bodies), Point Tangent (a point); Closed; Tangent Edges Merge.
   - Rails: 8 stations between each pair of profiles, iso curves of the plain loft, moved
     (one rail) or turned, moved and stretched toward the rails (two rails:
     `surface_core.stretch_similarity`); three or more: refused.
   - End conditions: `loft_ends.thru_rows` re-interpolates every column through the rows
     (profiles and stations) with Hermite end derivatives; rows that are not flat are found on
     the loft's sides by distance (`_nearest_v`). A closed loft repeats the first row and
     uses its condition at both ends; the last profile's condition is ignored.
   - Merge: `loft_ends.merged_wire` joins each tangent run of edges into one polynomial
     B-spline edge (`BSplineCurve.join`).
5. **Solid Loft** (`loft.py`, `loft_ui.py`): Tangent Edges Merge (was greyed; off by
   default); end conditions with rails, with a centerline and on a closed loft (first profile,
   Direction); rails that are edges of other bodies (taken directly, no longer read as a body
   to cut); rails between profiles in planes that are not parallel (`_rail_loft_turning`, was
   refused); a centerline that runs on past the profiles is used between them
   (`loft_ends.between_profiles`); Takeoff / Tangency Weight and Takeoff Angle take a
   parameter (an expression on the loft, read back when editing; `_update` leaves a property
   driven by an expression alone); a third rail is refused (it used to be ignored).
6. **Stitch**: the edges the stitch closes are drawn green, the ones left open red
   (`surface_geom.stitched_edges`), a small gap from `parity/surface.md`.
7. Parity docs: a part-2 behaviour spec with sources at the top of `parity/surface.md`, a
   wave-5 section in `parity/sweep-loft-rib.md`; both docs' known gaps updated.

## Tests

Scenarios (real input):
- `surface2_extrude` (84 checks): From Object (a slanted plane), All with a refusal and Flip,
  To Object a body, edit from the timeline, undo / redo, Esc, an empty design.
- `surface2_revolve_sweep` (89): Revolve To a plane (edit, refusal, Cancel), Sweep with a guide
  rail and Profile Scaling, Twist, Taper, undo / redo, Esc.
- `surface2_loft` (106): two rails with a Tangent end, a refusal, New Component, a centerline
  with Direction, save / reopen / edit, Merge.
- `surface2_solid_loft` (77): Merge, a rail on another body with Direction ends, a parameter
  for the weight (then a number typed over it), a centerline with ends, Closed refusal, undo /
  redo, Esc.
- `surface_stitch` gained the green-edge checks (63).

Goldens new (all analytic): `surface2_extrude_from_face`, `_from_curved_face`, `_to_body`,
`_to_chain_faces`, `_all`, `surface2_revolve_to_plane`, `surface2_sweep_rail`, `_sweep_taper`,
`surface2_loft_two_rails`, `_loft_tangent_end`, `_loft_centerline`, `sf_loft_merge_slot`,
`sf_loft_merge_slot_volume` (expected failure: OpenCASCADE's volume, see below),
`sf_loft_rails_ends`, `sf_loft_centerline_ends`, `sf_loft_closed_direction`,
`sf_loft_rail_body_edges`, `sf_loft_rails_turning`. The golden schema takes a `merge` key for
lofts. Unit tests: `test_surface_core.py` PartTwoTests (stop_angle, all_lengths, taper_factor,
lerp_fraction, similarity, stretch_similarity, the new value checks).

Regression runs (one at a time, all pass): `--only base` (unit 1131 OK, golden 420 pass + 2
expected failures `plate_hole_grid` (older) and `sf_loft_merge_slot_volume`, smoke, journey);
`surface_boundary_fill` (58), `surface_extrude` (60), `surface_misc` (70), `surface_patch`
(70), `surface_reopen` (44), `surface_stitch` (63), `surface_thicken` (74), `surface_trim` (59);
`sweep_loft_loft` (71, its Merge check now expects the box enabled and unticked),
`sweep_loft_loft_guides` (45), `sweep_loft_qa_loft` (249), `gaps_loft_ends` (51),
`modeling2_bodies` (54); then the four `surface2_*` again (84, 106, 89, 77).

## FreeCAD facts and traps found

- `MakePipeShell.simulate(n)` returns n + 1 plain `Part.Shape`s (not wires, no OrderedEdges),
  the last section twice: deduplicate and make wires (`loft_ends.simulated`, `as_wire`).
- `Shape.transformGeometry(m)` returns a plain Shape too: wrap it in `Part.Wire` before
  lofting.
- `removeSplitter()` can hand back a sewn solid turned inside out (negative volume):
  `LoftFeature` reverses it (the golden `sf_loft_closed_direction` caught it).
- `Wire.approximate()` hung on a slot wire; `BSplineCurve.join()` of polynomial pieces works.
- OpenCASCADE's volume of a B-spline face closed in u, or running over C0 / C1 knots, is
  several % off (the merged slot: 8822 for 8356 mm³; its mesh 8355): BRepGProp does not split
  the face at its knots. Why Merge is off by default.
- A loft along a centerline makes 2 side faces for a circle (a seam), not 1.
- `App.Units.Quantity("0.75 * 2")` evaluates arithmetic, so `parameters.is_plain_number`
  treats a sum as a number: only a formula with a parameter name becomes an expression (in
  every SciForge dialog). Scenarios that test a formula must use a user parameter.
- `freecadcmd file.py` drops into the interactive console after the file; use
  `freecadcmd -c "exec(open('file.py').read())" < /dev/null`.
- Scenario design: the iso view looks from (+1, -1, +1), so a plane whose normal is square to
  (1, -1, 1) is seen edge-on and cannot be clicked; a sketch line inside a solid cannot be
  clicked either (draw it running out of the solid); a sketch on an offset plane opens by
  selecting the plane's browser row, then Create Sketch.

## Not built (and why)

- Sweep Path + Guide Rail Full Extents / Perpendicular To Path with Path and Guide Rail
  Distance: needs a second distance handle and Fusion's stopping rule.
- A loft with three or more rails (refused in both lofts): the turn-move-stretch fit is exact
  for two rails only; OpenCASCADE has no rail loft.
- A closed loft with rails or a centerline (refused; Fusion's behaviour not found).
- Merge default: off (Keep) because of OpenCASCADE's volume above; Fusion's default unknown.
- Two rails stretch the section toward the rails in the surface loft and in a solid loft
  that turns, but scale it evenly in a solid loft between parallel profiles (the older rule,
  kept so its goldens and scenarios stay as they were).
- A closed loft of sketches drawn from different start corners twists (no start-point
  matching).
- Extrude All uses the bodies visible when the step was made.
- Patch per-edge continuity (Group Edges off) and Tangency Weight (OpenCASCADE's filling has
  no weight; the per-edge rows are a larger dialog job), Extend Align Edges (no OpenCASCADE
  extension keeps edges aligned), Offset corner type (Fusion's option unconfirmed), Boundary
  Fill from planes alone (one forum report; accepting them does no harm).
