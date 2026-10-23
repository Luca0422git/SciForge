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
| 9 | Extend Natural on spheres, tori, revolved / extruded / free-form faces; Edge Alignment Align Edges | `surface_geom._grow_rectangle`, `_refit`, `_aligned_extend` |
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
- Corner matching must stay out of `_thru_shell`: the rail loft (`_rail_stations`, the
  solid Loft too) reads the plain loft of the profiles as given; restarting the wires there
  broke `sf_loft_rails_turning` (+63 % volume). It runs on the plain loft only.
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
  `surface3_extend_natural_strip`, `surface3_extend_align_edges`, `surface3_untrim_manual`, `surface3_sweep_guide_surface`,
  `surface3_stitch_join` (with reopen), `surface3_loft_corner_matching`.
- Scenarios: `surface3_offset_patch`, `surface3_untrim_revolve`, `surface3_sweep_extrude`,
  `surface3_stitch_trim_ruled`, `surface3_extend_envmap`, `surface3_isocurve`. Updated:
  `surface_reopen` (the offset of the L is now Sharp: 560 outside), `surface2_revolve_sweep`
  (Type reads Partial / To / Full).

## Results (FreeCAD 1.1.4, this sandbox)

- Scenarios (all PASS): surface3_offset_patch 76 checks, surface3_untrim_revolve 77,
  surface3_sweep_extrude 58, surface3_stitch_trim_ruled 63, surface3_extend_envmap 53,
  surface3_isocurve 26. Existing ones re-run and passing: every `surface*` and `surface2*`
  scenario, gaps_sweep_guide_surface, inspect_analysis_components / curvature / zebra,
  ribbon_sweep (221).
- Golden: the full run 449 pass, 2 known xfail; the surface set (30, the 10 `surface3_*`
  among them) re-run after the last change: all pass. Unit: 1862 OK; base smoke and journey pass.

## Shared files touched

- `ribbon_config.py`: one INSPECT item (Environmental Map Analysis) and one sketch Project /
  Include item (Isoparametric Curve), both marked `# owner: surface-3`.
- `browser_core.py`: the Environmental Map's icon in `ANALYSIS_ICONS` (one line).

## Gaps left (details and evidence in the parity doc)

Patch Tangency Weight (OpenCASCADE has no weight), Loft Edge Alignment Align Edges / Align to
Surface (no OpenCASCADE control; greyed with the reason),
Extrude Match Shape (not found in Fusion's documentation), Full Extents' rail mapping (G),
the Isoparametric Curves live in a companion of the sketch (FreeCAD's sketches are flat) and
have no edit dialog, Ruled Type default unverified.

## QA pass (branch `sf/surface-3-qa`, 2026-10-23)

An independent QA engineer ran every part-3 scenario, the existing `surface*` scenarios, the
unit tests and the golden models, read the whole diff, and clicked the paths the builder's
scenarios leave out. Details in `parity/surface.md`, section "Part 3 QA".

Fixed:

- Offset Sharp (the default) on a box top with rounded edges returned a "valid" surface
  2e7 mm across: now refused with the reason (`surface_geom._runaway`); Rounded works.
- Natural Extend of a free-form / extruded-spline face went up to 40 % too far (sized by the
  speed at the edge): now measured along the surface (`_grow_by`).
- Sweep Perpendicular to Path with a rail shorter than the path and leaving it: the end was
  square to the rail, not the path (8 mm too far, tilted): fixed (`_section_through`), golden
  `surface3_sweep_rail_perpendicular`.
- Change Parameters listed numbers a step's choices do not use: the dialog saves which rows
  it hid (`hidden_numbers` in the choices) and the step hides those properties whenever its
  choices change (`SurfaceFeature.onChanged`), so undo / redo / Cancel follow.
- Patch with a Connected edge next to a Tangent one: the refusal now names the mix (it said
  "walls this steep" though all-Tangent works there).
- `surface_iso_ui.py` reformatted (black).

FreeCAD / OpenCASCADE facts (measured in FreeCAD 1.1.4):

- `makeOffsetShape(d, 1e-6, False, False, 0, 2, False)` (intersection join) on faces where two
  rounds meet at a corner returns `isValid()` True with faces 1e7 mm out; with the whole box
  it returns a null shape. Compare the result's bound box with the faces'.
- `BSplineSurface.value()` past the bounds speeds up or slows down with the last polynomial
  piece: size an extension by arc length, not by `getD1` at the edge.
- Property editor modes (Hidden) are not part of undo: a mode set from a dialog stays after
  Ctrl+Z or Cancel. Derive it from a saved property in the proxy's `onChanged` instead.
- `MakeFilling` with a G0 edge next to G1 edges: the deviation from tangency spreads over a
  third of the G1 edge whatever `setResolParam` / `setApproxParam` say (15 to 25 points,
  2 to 3 iterations, measured).
- Chain Selection on a box top with rounded top edges takes nine faces (the walls are tangent
  to the rounds too).

Traps for the scenarios:

- From a view of the whole design a hole's edge on a patch is a few pixels from the face: the
  edge click lands on the face (`Face1`). Frame the patch first (select it, `ViewSelection`,
  clear the selection before opening the dialog).
- On the SURFACE tab there is no Create Sketch big button: switch to SOLID first.

Tests added: `surface3_qa` (86 checks), `surface3_qa2` (55), `surface3_qa3` (58); golden
`surface3_sweep_rail_perpendicular`.
