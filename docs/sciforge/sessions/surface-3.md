# Session log: surface-3 (wave 6, 2026-10-23), branch `sf/surface-3`

SURFACE part 3: the options of the surface tools that the audit
(`dev/research/surface-gaps.md`) found missing in the `surface*` files, plus INSPECT >
Environmental Map Analysis and Sketch > Project / Include > Isoparametric Curve. The parity
doc (`parity/surface.md`, section "Part 3") has the behaviour table with sources and the gaps.

## What was built

| Audit # | Fusion | Where |
|---|---|---|
| 3 | Offset Type Sharp / Rounded (Sharp default; old files keep Rounded) | `surface_geom.offset_faces` (join 2 / 0), `surface_core.LEGACY` + `with_saved` |
| 8 | Patch Group Edges off (Continuity per edge), Reverse Normal + Flip, Tangency Weight 0.5 (greyed) | `surface_geom.patch` (3-tuples), `PatchPanel` edge rows |
| 9 | Extend Natural on spheres, tori, revolved / extruded / free-form faces | `surface_geom._grow_rectangle`, `_refit` |
| 11 | Untrim Manual (loops) and Keep Copy | `surface_geom.untrim_loops`, Keep Copy = an Unstitch-style piece body (`_sync_pieces(copy=True)`) |
| 12 | Revolve Project Axis, "Partial", To with Two Sides | `surface_geom.project_axis`, `surface_core.two_sided_to` |
| 13 | Extrude flat faces as profiles; Chain Faces / Extend Faces | `surface.edges_of` (Face picks), `ExtrudePanel` |
| 7, 14 | Sweep Path + Guide Surface; rail Extent Perpendicular to Path / Full Extents, Guide Rail Distance | `surface_geom.sweep_curves`, `_rail_extent`, `sweep._surface_aux` reused |
| 15 | Loft corner matching of closed profiles (Sept 2026); Edge Alignment row (greyed) | `surface_geom.match_corners`, `surface_core.corner_shift` |
| 21 | Stitch Operation New Body / Join / Cut / Intersect | `surface._c_stitch`, `surface_geom.stitched_operation`, `StitchPanel.solid_target` |
| 22 | Trim with one face of a solid as the tool | `TrimPanel.interpret` |
| 24 | Ruled Corner Type Rounded / Mitered | `RuledPanel` (maps onto the saved `mitered`) |
| 17 | INSPECT > Environmental Map Analysis | `surface_analysis.ENVIRONMENT`, `environment_image`, `ViewProviderSurfaceAnalysis._environment` |
| 18 | Sketch > Project / Include > Isoparametric Curve | `surface_iso.py`, `surface_iso_ui.py` |
| (map 4.3) | Change Parameters lists the surface steps' numbers | `surface_ui.register_parameters` |

## FreeCAD / OpenCASCADE facts learned (measured in FreeCAD 1.1.4)

- `makeOffsetShape(d, 1e-6, False, False, 0, join, False)`: join 2 (intersection) on an open
  or closed box shell gives the sharp offset (6 planes for a closed box, valid); join 0 gives
  cylinders and spheres at the corners (Fusion's Rounded).
- `BSplineSurface.value(u, v)` past the bounds extrapolates the last polynomial piece;
  `toShape` past the bounds is invalid. Refit with `BSplineSurface.interpolate(grid)` (24 x
  24): 3e-6 mm off on a wavy face, 2e-3 mm on a circle-to-ellipse loft carried on 20 %.
- `Surface.toShape(u0, u1, v0, v1)` past the face's range works for cylinders, cones,
  spheres (v within the poles), tori and surfaces of revolution / extrusion.
- `Part.makeLoft` already pairs the starts of two squares drawn from different corners (its
  compatibility check is on): corner matching adds the deterministic rule, it rarely changes
  the result.
- Stitching a face with a copy of itself sews a "closed" shell whose solid has volume 0: a
  closed stitch now needs a volume (`surface_geom.stitch`). The Stitch dialog's target test
  must stitch the bodies as they were before the preview (the preview body already holds the
  stitch).
- `curve.toShape(a, b).common(face)` cuts an isoparametric curve to a trimmed face (a hole
  splits it in two).
- Coin's `SoTextureCoordinateEnvironment` with a generated grey `SoTexture2` (BLEND between
  two colours) gives a live reflection map; no camera tracking needed.

## Traps for the scenarios

- A click exactly on a circle's seam point picks its Vertex, not the edge: click elsewhere on
  the circle.
- Sketch curves lying on a body's edge or in front of it take the click: hide the sketches
  (or move the curves off the edge) before clicking body edges and vice versa.
- An origin plane click behind a face hits the face (it is a flat face, taken as a plane):
  click the plane square where nothing is in front.
- Ruled's chain is tangent-only: two lines at a corner are two clicks.
- Revolve Two Sides waits for Object Two: the preview body is dropped and made again, so
  read the step's body again after the second pick.

## Tests

- Unit: `test_surface_core.py` (+ PartThreeTests, IsoCurveTests; two part-2 tests updated
  for the new Sweep type).
- Golden: `surface3_offset_sharp_rounded`, `surface3_revolve_to_two_sides`,
  `surface3_revolve_project_axis`, `surface3_extend_natural_sphere`,
  `surface3_extend_natural_strip`, `surface3_untrim_manual`, `surface3_sweep_guide_surface`,
  `surface3_stitch_join` (with reopen), `surface3_loft_corner_matching`.
- Scenarios: `surface3_offset_patch`, `surface3_untrim_revolve`, `surface3_sweep_extrude`,
  `surface3_stitch_trim_ruled`, `surface3_extend_envmap`, `surface3_isocurve`. Updated:
  `surface_reopen` (the offset of the L is now Sharp: 560 outside), `surface2_revolve_sweep`
  (Type reads Partial / To / Full).

## Shared files touched

- `ribbon_config.py`: one INSPECT item (Environmental Map Analysis) and one sketch Project /
  Include item (Isoparametric Curve), both marked `# owner: surface-3`.
- `browser_core.py`: the Environmental Map's icon in `ANALYSIS_ICONS` (one line).

## Gaps left (details and evidence in the parity doc)

Patch Tangency Weight (OpenCASCADE has no weight), Extend Align Edges and Loft Edge
Alignment Align Edges / Align to Surface (no OpenCASCADE control; greyed with the reason),
Extrude Match Shape (not found in Fusion's documentation), Full Extents' rail mapping (G),
the Isoparametric Curves live in a companion of the sketch (FreeCAD's sketches are flat) and
have no edit dialog, Ruled Type default unverified.
