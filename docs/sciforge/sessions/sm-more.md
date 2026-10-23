# Session log: SHEET METAL more forming tools (`sf/sm-more`, wave 6, 2026-10-23)

Builder sm-more of wave 6 (brief `docs/sciforge/dev/briefs/sm-more.md`). Parity doc with the
behaviour table, tests and known gaps: `docs/sciforge/parity/sheet-metal-more.md`.

## Built

- **Bend** (SHEET METAL > CREATE > Bend, Fusion's Fold): Stationary Side + Bend Lines boxes,
  Angle (round handle with value box), Bend Line Start / Center / End, Flip, Bend / Corner
  Relief, Override Bend Radius. Several lines in one step (bent farthest first), each
  line with its own angle / position / flip / Bend Relief through "Values For". A line across a tab bends
  only the tab and cuts the rule's bend reliefs (Straight / Round, Tear as a 0.01 mm split)
  beside it.
  The zone is laid onto the bend's cylinders by mapping its outline in the cylinder's (angle,
  height) parameters, so holes in the zone come through.
- **Hem** (CREATE > Hem): Flat / Open / Rolled / Teardrop / Rope / Double with their values,
  Bend Position, Flip, Miter Corners, Override Rules; the Length arrow with its value box.
- **Join by Bend** (CREATE > Join by Bend): First / Second Edge on two sheet metal bodies, rule
  radius or Bend Radius; the other body is used up (`bodies.CONSUMERS`).
- **Corner Closure** (MODIFY > Corner Closure): Dominant / Submissive Edge, Symmetric Gap /
  Overlap, rule gap or own gap, Overlap, Flip Overlap; Trim To Bend (what lies inside both
  bend zones cut away), Tear (no cut), Round and Square reliefs
  at the Intersection, Vertex or Tangent (Round) placement (cut in the flat state through
  sm-flat's unfolder and folded back: `sf/sm-flat` merged in; the result must still lay flat).
  Works on square flange ends and on ends already mitred by Flange.
- **Lofted Flange** (CREATE > Lofted Flange, own entry under Flange): two profiles (auto-chain),
  Brake Form with the four facet controls (laid out like a transition piece: corner fans,
  matched by direction round each profile's centre), Die Form, Orientation, New Body / Join.
- **Sheet metal Fillet / Chamfer** (MODIFY > Fillet / Chamfer of the SHEET METAL tab): only the
  edges through the thickness; Fillet radius sets ("+ New Set"), a radius arrow with its value
  box; on a solid body they open the SOLID commands.
- Golden ops (`sheetmetal_ops.py` block `# --- sm-more ---`), schema block, 32 golden models,
  26 unit tests, 8 scenarios (237 checks), 7 icons (`tools/sciforge/icons_sheetmetal2.py`).

## FreeCAD / OpenCASCADE facts found

- `Part.Face(cylinder, wire)` where the wire's edges are `Geom2d.Line2dSegment(...).toShape(
  cylinder)` gives an exact face on the cylinder from a region drawn in its (u, v)
  parameters; `Part.Circle(...)` with `XAxis` set, then `Part.Cylinder(circle)`, fixes where u = 0
  is. `face.validate()` on such faces segfaults FreeCAD 1.1.4: never call it.
- `face.makeOffsetShape(t, tol, fill=True)` on a cylindrical face makes a clean thick bend
  piece, but its side faces come out as B-splines (removeSplitter cannot merge them with the
  walls' planar sides). For the bend zone SciForge revolves the zone's cross-section instead
  (exact planes and cylinders) and only cuts holes with mapped plugs.
- `makeOffsetShape` on a faceted shell (lofted brake form) or on a multi-face loft fails ("no
  image for shape", "ThruSections failed", "not done"): the lofted flange is built by hand
  (each facet moved T along its normal, corners solved where the moved planes meet, kept in
  their profile's plane; `shell.sewShape()` then `Part.Solid`).
- `App::PropertyLinkSubList` drops an entry whose sub-element list is empty: store a whole
  sketch as its list of `EdgeN` names.
- One solid cannot hold two layers touching face to face: a fuse merges them (the reason for
  the Flat hem's 0.01 mm hairline).
- `frame_box`: a box placed with a left-handed frame is mirrored inside out; keep frames
  right-handed.
- Names in `tools/sciforge/icons_*.py` are global to make_icons.py: a helper called `_sheet`
  replaced another file's helper and broke a dozen icons. Prefix helpers (`_smm_`).
- The scratchpad is shared between the builders' sessions: probes go in a folder of their own.
- A slanted (mitred) flange end extruded along the bend's axis gives the bend's extension as a
  `SurfaceOfExtrusion` of an ellipse arc, not a `Cylinder`: removeSplitter cannot merge it and
  the unfolder refuses it ("curved in two directions"). Sweeping the end's outline seen along
  the axis (its bend end is then a circle arc) gives true cylinders.
- Folding a relief cut back at a mitred corner (sm-flat's `refold`) can leave specks of a few
  millionths of a mm3 beside the mitre; Corner Closure drops pieces under 0.001 T^3.
- sm-flat's `unfold` can raise a raw OpenCASCADE "Wire is not closed" on some cut corners from
  one side of the sheet and lay the same part flat from the other side (a note for sm-flat).
- Selection inside a component: after a PickPanel `_sync`, FreeCAD can report a later click as
  "one added and one dropped" at once; the sm-more panel keeps the old picks then
  (`picks_changed`), and re-selects elements with their component path (`rooted`).
- A sketch line lying exactly on a see-through (ghosted) face is hard to click; the same line
  on the solid face is fine. The panel makes the part unpickable (its SoPickStyle nodes,
  Coin only) while a box takes sketch curves only. A step made for the preview must not hide
  the sketch its next picks come from: the sketches are hidden on OK.

## Tests run (FreeCAD 1.1.4, this sandbox)

- `--only unit`: all pass. Golden models: the 32 `sheetmetal_smm_*` pass (with sm-forming's).
- Scenarios: smmore_bend 44, smmore_bend_two 18, smmore_bend_tab 20, smmore_hem 40,
  smmore_join 25, smmore_corner 37, smmore_round 26, smmore_lofted 27 checks: all PASS.

- sm-flat's unfolder (`sheetmetal_unfold.unfold`, a read-only copy of `sf/sm-flat`'s file in
  the scratchpad) lays this branch's bends flat to exactly the plate they were bent from
  (100 x 40, volume 4000.0000): Bend's zone mapping is the exact inverse of the unfolder's
  development (both use R + K T). Hems, Join by Bend and the rounds unfold too.

- Merged `sf/sm-forming` three times (its Flange for scenarios / golden models) and
  `sf/sm-flat` twice (its unfolder for Corner Closure reliefs); no conflicts but
  `ribbon_config.py`'s adjacent CREATE lines the first time (resolved keeping both builders'
  entries). After the last merges (sm-forming `ca79f2b`, sm-flat `83f16ad`) the sm-more
  golden models still measure the same.
- Ribbon sweep of the SHEET METAL tab (`SWEEP_TABS=sheet_metal`): every sm-more command passes;
  the one failure then was sm-forming's Sheet Metal Rules opening its window, which
  sm-forming has since listed as intended in `ribbon_sweep.py`.

## Notes for the merge into develop

- sm-flat's Flat Pattern cuts the rule's 2-bend corner relief wherever two bends' centre lines
  cross (`flatpattern.with_corner_reliefs`). At a corner closed by Corner Closure that adds a
  relief the folded part does not have (Trim To Bend, Tear) or a second one (Square, Vertex,
  Tangent): the flat pattern should leave out corners whose relief a `SheetMetalCornerClosure`
  step chose.
- `sheetmetal_unfold.unfold` can raise a raw OpenCASCADE "Wire is not closed" (not an
  `UnfoldError`) on some cut corners; Corner Closure catches it, other callers may not.
- Lofted Flange steps carry `Developable` (False for Die Form); the flat pattern could give
  that reason instead of the unfolder's "sharp corner ... fillet it or Rip it".

## Open (see the parity doc's Known gaps)

Corner relief where bend lines meet with Center (Start / End work), Relief Remnant, Corner Closure's weld relief shapes,
bend transitions and 3-bend corners, Lofted Flange inside the Flange dialog and with real bends
between facets (so a Brake Form lofted flange has no flat pattern yet).
