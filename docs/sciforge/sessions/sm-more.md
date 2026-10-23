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
- Booleans next to tangent geometry can go quietly wrong: a relief slot whose side touched a round
  notch at a tangent was "cut" and then came back in the fuse (16.75 mm3 too much). Every Bend
  now checks that its pieces add up (bent zone = flat zone x ((R + T)^2 - R^2) / (2 (R + K T) T))
  and refuses otherwise; a hole in the zone is laid on the bend slightly bigger than that exact
  ratio (0.06 mm3 on a 1 mm hole), so a fifth of the holes' volume is allowed.
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

- Final run on the branch with sm-forming and sm-flat merged (09:00 UTC): `--only base` all
  passed (unit 1906 OK, 9 skipped; golden 505 pass + 2 known xfail, the 32 `sheetmetal_smm_*`
  among them; smoke, journey, restart).
- The siblings' 16 scenarios (sheetmetal_* and flatpattern_*) all PASS on this merged branch,
  and the SHEET METAL ribbon sweep (`SWEEP_TABS=sheet_metal ribbon_sweep`) passes, 109 checks.
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

## QA pass (branch `sf/sm-more-qa`, 2026-10-23, independent QA)

Ran the builder's 8 scenarios, the unit tests (1906 OK) and the golden models (505 + 2 known
xfail) on `sf/sm-more` first: all passed. Then probed what Luca would do next, headless
(FreeCADCmd + the golden Builder) and through the GUI, and fixed what broke:

- **Bend along a diagonal line was always refused** ("would run the sheet into itself"). Two
  causes in `sheetmetal_bend.py`: `_moving_spans` compared the moving side's front with the
  zone's whole extent along the line, so a zone whose ends are slanted looked wider than what
  moves (a tab); and `_bend_zone_solid` pushed the corners of the zone's missing triangles
  square to the zone's sides, so the plug no longer followed the slanted outline. A tab is now
  a moving side narrower than the zone's own slices, and corners slide along the outline.
  Golden `sheetmetal_smm_bend_diagonal` (analytic); the unfolder lays it flat to the plate.
- **Join by Bend of an upright below the plate, or of edges overlapping only in part, was
  refused** ("would split the body"): the extension pieces were placed along the bend's axis
  from the wrong edge's start. Picking a plate's far edge (the bend would remove the whole
  plate) is now refused with what to pick. Goldens `sheetmetal_smm_join_bend_below` /
  `_overlap` (analytic).
- **A first click on another sheet metal body was silently ignored** by every sm-more dialog
  (they open on the active body). With nothing picked yet it now moves the dialog to that body
  (`SmPanel._other_sheet` / `_move_to`, using PickPanel's `switch_body`): Fusion's First Edge
  of Join by Bend may be on any body. Scenario `smmore_qa_join_order` (fails without the fix).
- **Lofted Flange between two straight lines** on separate planes was refused as "in one
  plane" (two parallel lines always share a plane): now a flat slanted flange. Golden
  `sheetmetal_smm_lofted_lines` (analytic).
- **Lofted Flange Brake Form, Face Number 1 or 2 on a circle** made a pyramid / wedge
  silently: a full circle keeps at least 3 facets (unit test).
- **Lofted Flange edit, Operation**: Join edited to New Body dropped the body's earlier
  shape; New Body edited to Join stayed its own body. The Operation is greyed in an edit.
- **Corner Closure, Extend Aligned off on a corner mitred to the gap** was refused while on
  built the relief cut: both now cut the relief. Golden `..._mitred_square`.
- **Change Parameters** listed values the step's choices do not use (a Rolled hem's Gap, a
  rule gap's Gap, a rule radius's Bend Radius): hidden like Shell / Flange do (`show_used`).
- **Bend's Corner Relief checkbox** changed nothing: greyed with the reason.

New scenarios: `smmore_qa_reopen` (save / reopen of Hem, two-set Fillet, Corner Closure, Join
by Bend, Lofted Flange; each edited from the timeline, a value changed, Cancel / Esc leave
values and part as they were; Join deleted from the timeline brings the other body back,
Ctrl+Z hides it again), `smmore_qa_refusals` (empty design for every command, the SOLID
Fillet fallback, Join of two thicknesses, a Lofted Flange's new body gone after Esc),
`smmore_qa_join_order`.

Facts: the golden runner's `SCIFORGE_GOLDEN_FILTER` runs a subset; a check step's `expect`
needs its own `source`. Comparing a step's property strings before / after Cancel must skip
shapes, `ShapeMaterial` and `SciForgePicks` (rebuilt with float noise).

Left (parity doc Known gaps 13-15 and the builder's): Corner Closure's default relief is not
the rule's (Fusion's "Use rule defaults"), Hem's Override Rules has no bend relief override,
a Brake Form lofted flange still has no flat pattern, Join by Bend reads the other body live.
