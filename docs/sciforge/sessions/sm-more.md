# Session log: SHEET METAL more forming tools (`sf/sm-more`, wave 6, 2026-10-23)

Builder sm-more of wave 6 (brief `docs/sciforge/dev/briefs/sm-more.md`). Parity doc with the
behaviour table, tests and known gaps: `docs/sciforge/parity/sheet-metal-more.md`.

## Built

- **Bend** (SHEET METAL > CREATE > Bend, Fusion's Fold): Stationary Side + Bend Lines boxes,
  Angle (round handle with value box), Bend Line Start / Center / End, Flip, Bend / Corner
  Relief (stored), Override Bend Radius. Several lines in one step (bent farthest first), each
  line with its own angle / position / flip through "Values For".
  The zone is laid onto the bend's cylinders by mapping its outline in the cylinder's (angle,
  height) parameters, so holes in the zone come through.
- **Hem** (CREATE > Hem): Flat / Open / Rolled / Teardrop / Rope / Double with their values,
  Bend Position, Flip, Miter Corners, Override Rules; the Length arrow with its value box.
- **Join by Bend** (CREATE > Join by Bend): First / Second Edge on two sheet metal bodies, rule
  radius or Bend Radius; the other body is used up (`bodies.CONSUMERS`).
- **Corner Closure** (MODIFY > Corner Closure): Dominant / Submissive Edge, Symmetric Gap /
  Overlap, rule gap or own gap, Overlap, Flip Overlap; Trim To Bend, Round and Square reliefs
  (cut in the flat state through sm-flat's unfolder and folded back: `sf/sm-flat` merged in).
- **Lofted Flange** (CREATE > Lofted Flange, own entry under Flange): two profiles (auto-chain),
  Brake Form with the four facet controls (laid out like a transition piece: corner fans,
  matched by direction round each profile's centre), Die Form, Orientation, New Body / Join.
- **Sheet metal Fillet / Chamfer** (MODIFY > Fillet / Chamfer of the SHEET METAL tab): only the
  edges through the thickness; Fillet radius sets ("+ New Set"), a radius arrow with its value
  box; on a solid body they open the SOLID commands.
- Golden ops (`sheetmetal_ops.py` block `# --- sm-more ---`), schema block, 26 golden models,
  24 unit tests, 7 scenarios (208 checks), 7 icons (`tools/sciforge/icons_sheetmetal2.py`).

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
- Selection inside a component: after a PickPanel `_sync`, FreeCAD can report a later click as
  "one added and one dropped" at once; the sm-more panel keeps the old picks then
  (`picks_changed`), and re-selects elements with their component path (`rooted`).
- A sketch line lying exactly on a see-through (ghosted) face is hard to click; the same line
  on the solid face is fine. The panel makes the part unpickable (its SoPickStyle nodes,
  Coin only) while a box takes sketch curves only. A step made for the preview must not hide
  the sketch its next picks come from: the sketches are hidden on OK.

## Tests run (FreeCAD 1.1.4, this sandbox)

- `--only unit`: all pass. Golden models: the 26 `sheetmetal_smm_*` pass (with sm-forming's).
- Scenarios: smmore_bend 44, smmore_bend_two 17, smmore_hem 40, smmore_join 25,
  smmore_corner 29, smmore_round 26, smmore_lofted 27 checks: all PASS.

- sm-flat's unfolder (`sheetmetal_unfold.unfold`, a read-only copy of `sf/sm-flat`'s file in
  the scratchpad) lays this branch's bends flat to exactly the plate they were bent from
  (100 x 40, volume 4000.0000): Bend's zone mapping is the exact inverse of the unfolder's
  development (both use R + K T). Hems, Join by Bend and the rounds unfold too.

- Merged `sf/sm-forming` twice (its Flange for scenarios / golden models) and `sf/sm-flat`
  once (its unfolder for Corner Closure reliefs); no conflicts but `ribbon_config.py`'s
  adjacent CREATE lines (resolved keeping both builders' entries).
- Ribbon sweep of the SHEET METAL tab (`SWEEP_TABS=sheet_metal`): every sm-more command passes;
  the one failure is sm-forming's Sheet Metal Rules opening its window (intended; it needs an
  `INTENDED` entry in `ribbon_sweep.py`, a shared file).

## Open (see the parity doc's Known gaps)

Partial bends with reliefs, Corner Closure's other relief shapes and placements, Lofted
Flange inside the Flange dialog and with real bends between facets.
