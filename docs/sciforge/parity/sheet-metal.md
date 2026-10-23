# Parity spec: SHEET METAL, forming (rules, sheet metal bodies, Flange)

Wave 6, branch `sf/sm-forming` (2026-10-23). Implemented in `src/Mod/SciForge/sciforge/`:

| File | What it holds |
|---|---|
| `sheetmetal_core.py` | the shared contract (rules, expressions in Thickness, bend maths) plus the flange maths: thickness sides, Bend Position, Height Datum, width ranges, reliefs (pure Python, unit tested) |
| `sheetmetal.py` | the shared contract: the design's rule store, which body is sheet metal and its rule |
| `sheetmetal_form.py` | the geometry, Qt-free and without a document: `base_flange`, `contour_flange`, `edge_frame`, `bend_wall` (one bend + wall on a sheet edge, public for sm-more's Hem), `edge_flange` |
| `sheetmetal_flange.py` | the Flange step (`PartDesign::FeaturePython`, timeline type `SciForge::Flange`), `make` / `update` / `discard` |
| `sheetmetal_flange_ui.py` | the Flange command and dialog, view provider, timeline name and icon, Change Parameters fields |
| `sheetmetal_rules.py`, `sheetmetal_rules_ui.py` | the Sheet Metal Rules dialog (In This Design / Library) and the user's own library (preferences) |
| `sheetmetal_component.py` | New Component's Type: Standard / Sheet Metal |
| `ai/ops/sheetmetal_ops.py` | golden / AI steps `sf_sheet_rule`, `sf_flange`, `sf_flange_edit` |

Fusion's behaviour comes from `docs/sciforge/dev/research/fusion-sheet-metal.md` (sources there:
**A** = Autodesk help / API / blog, **F** = forum or tutorial, **G** = guess; that file's
critic pass is followed where it corrects the first pass). Rows below name the source of the
behaviour SciForge copies.

## Behaviour

### Sheet Metal Rules (SHEET METAL > MODIFY > Sheet Metal Rules)

| Fusion | SciForge | Src |
|---|---|---|
| Two lists: In This Design and Library (the user's library, shared by every design) | Same. Library = SciForge's eight built-in rules (Steel, Stainless Steel, Aluminum, Copper, each mm and in) + the user's own rules, kept in the user's preferences | A[R7], F[F19] |
| A library rule is the default ("Steel (mm) (Default)"); it cannot be deleted | Steel (mm) is shown "(Default)"; built-in rules cannot be deleted or edited (New makes an editable copy) | F[F6], A[R26] |
| New Rule starts from a rule and keeps its units; units are fixed once a rule exists | New copies the selected rule (free name "... 2"); Units can be chosen only in a new rule | A[R20], F[F5] |
| Edit (pencil) shows every field: Thickness, Miter/Rip/Seam Gap, Bend Radius, K Factor, Bend Relief shape / width / depth / remnant, 2-bend corner relief shape / placement / size, 3-bend corner relief shape / radius | Same fields on the same window (Save / Cancel). Every length takes a number in the rule's units ("1.5 mm") or an expression in Thickness ("Thickness * 2") | A[R6], A[R45] |
| Values as functions of Thickness | Same (`sheetmetal_core.evaluate_expression`) | A[R45] |
| K factor outside 0..1 refused; names unique in a list | Refused with the reason in the dialog | A[R25], A[R26] |
| Round 2-bend relief allows Intersection / Tangent placement, Square Intersection only, others none | Same (Placement greyed for the other shapes, Square forces Intersection) | A[R24] |
| Copy between Library and In This Design | Copy to Library / Copy to Design (a new name when the name is taken) | F[F8] |
| Deleting a rule that is in use is refused | Refused with the bodies that use it; also refused for the active rule and the design's last rule | G |
| Editing a rule In This Design recomputes every body that follows it | Same: the bodies' flanges read the rule when they compute and depend on the design's rule store, so Save (and its Undo) rebuild them | G |
| Active rule per component | Set Active (the rule new flanges in the active component start with); a Sheet Metal component keeps its own | G |
| (not in the browser) | SciForge shows "Sheet Metal Rule: <active rule>" under Document Settings once the design has sheet metal; a click opens the dialog | G |

Library values: K = 0.44 and Bend Radius = Thickness for every rule (F[F1], F[F2]); the
thicknesses 1.0 / 1.0 / 1.5 / 1.0 mm and 0.06 / 0.048 / 0.063 / 0.04 in are SciForge's
starting values (research 3.2, G). The other fields keep the contract's Inventor-style
defaults (critic pass CP1 item 4): gap = Thickness, relief Round, width Thickness, depth
Thickness / 2, remnant Thickness * 2, 2-bend Round / Intersection / Thickness * 4, 3-bend Round
With Radius / Thickness * 4. SciForge's choice for CP1 item 7: the Round 2-bend relief Size is
its **diameter** (said in the tooltip).

### Sheet metal bodies

| Fusion | SciForge | Src |
|---|---|---|
| A sheet metal body carries its rule; the browser marks sheet metal | A body with `SciForgeSheetMetalRule`; the browser shows it with a bent-sheet icon, its rule in the tooltip | A (BRepBody.isSheetMetal), G (icon) |
| SOLID tools keep working on sheet metal (Extrude cut, Hole, patterns) | Unchanged: `commands.find_body` does not skip sheet metal bodies | G |
| New Component Type: Standard / Sheet Metal | Same in the New Component dialog; Sheet Metal shows a Rule box (the design's rules, then the library's) and makes the component's active rule. Standard is unchanged | A[R48] |
| The flange's Rule drop-down starts at the component's active rule | Same | A[R44], G |
| One rule per body (thickness cannot follow two rules) | A Join / Edge flange uses the body's own rule; the Rule box only shows for a new body | CP2 item 3 |

### Flange (SHEET METAL > CREATE > Flange)

| Fusion | SciForge | Src |
|---|---|---|
| One command; the mode follows what is picked: a closed profile = base flange, an open profile = contour flange, edges of a sheet metal body = edge flange | Same. A click inside a shaded closed sketch area picks a profile, a click on a sketch line takes its whole joined chain, a click on an edge of a sheet metal body picks the edge. Picks of another kind start the dialog over in that mode | A[R2], A[R4], A[R5] |
| Base flange: closed profile(s) -> a plate of the rule's thickness; Orientation Side 1 / Side 2 / Center | Same (several profiles fuse when they touch) | A[R2], A[R28] |
| Base flange Operation New Body / Join (also New Component) | New Body (default; the sketch's own empty body becomes the sheet metal body), New Component (a new Sheet Metal component with the rule active), Join (into the active sheet metal body, in its rule) | A[R27] |
| Rule drop-down for the body being made | Same (design rules, then library ones, copied into the design when used) | A[R44] |
| Contour flange: an open chain of lines and arcs; sharp corners become bends with the rule's radius | Same: every line-line corner gets the radius that makes the bend's **inside** radius the rule's (the line is the inner or outer face depending on the side and the turn); tangent arcs stay as drawn | A[R5], F[F15] |
| Contour Distance (drag handle), Direction One Side / Symmetric / Two Sides, thickness side | Same (Flip turns One Side round); a blue arrow with its value box sets Distance | A[R2], A[R27] |
| A contour profile drawn from the end of a sheet edge (sketch plane square to the edge) is joined along that edge | Same: the dialog finds the edge, sets Join and runs the flange along the whole edge; the corner between the sheet and the first line is bent with the rule's radius, the sheet cut back for it, the thickness on the side that carries the sheet on (the Distance options do not apply) | G (research 2.2.3) |
| Edge flange Height Extent Distance / To Object (one edge only) | Same; To Object lights the Object box: the flange runs to the picked face's or plane's plane (+ Offset) | A[R2], A[R27] |
| Height Datum Inner Faces / Outer Faces / Tangent To Bend | Same (research 4.3): walls H - R tan(a/2), H - (R + T) tan(a/2), H | A[R2], F[F15] |
| Bend Position Inside / Outside / Adjacent / Tangent | Same (research 4.4): the plate is cut back (R + T) tan(a/2), R tan(a/2), 0; Tangent keeps the bend's outside on the side face from 90 degrees up (below 90 it is Inside, G) | A[R2], A[R29] |
| Angle, default 90; Flip turns the flange over the plate | Same; angle 0 < a <= 180 | A[R27], A[R2] |
| Width Full Edge / Symmetric / Two Sides / Two Offsets (between two picked reference faces or planes, an offset from each) | Same: Two Offsets lights Offset Object 1 then 2; the flange runs between where the two references cross the edge, each offset inwards. With no reference picked the offsets count from the edge's ends (SciForge) | A[R2] |
| Several edges; adjacent ones mitred with the Miter/Rip/Seam Gap | Same: each pair of picked edges that meet at a corner of the same face is cut on the corner's bisector, gap/2 each side (a four-edge tray works) | A[R6], G(Inv) |
| Bend relief where the flange stops inside its edge: Straight / Tear / Round, width, depth, remnant | Same (research 4.5): a slot from the edge back across the bend zone and Relief Depth more, Relief Width wide; Round ends in a half circle; a plate sliver narrower than Relief Remnant is cut away; Tear is a 0.05 mm slit (a solid cannot hold a zero-width cut) | A[R6], A[R1], G |
| Rule overrides with their check boxes: Bend Radius, Bend Relief, Corner Relief (2 bends), Corner Relief (3 bends) | Same check boxes and fields. Bend Radius and Bend Relief change the geometry; the corner relief overrides are kept on the step (see Known gaps) | A[R1] |
| Live preview, drag arrow with its value box, OK / Cancel | Same: the preview is the real step; the height arrow stands on the Height Datum point and points along the wall; an angle handle turns about the bend's axis (G); every field and value box takes a number, a user parameter or a formula | A[R2], G |
| Timeline "Flange<n>" with the flange icon; edit from the timeline | Same (double-click opens the dialog with the picks and values) | G |
| Errors: curved edge, an edge not on a sheet metal body, a flange that runs into the part, a height that does not reach past the bend | Refused in the dialog with the reason (OK keeps it open): curved edge, edge across the thickness, edge of another body, overlapping flanges, a flange that would run into the part, Height Datum Inner / Outer or Bend Position Inside / Outside at 180 degrees, a contour line too short for its bends, a closed or branched contour, a spline in a contour | G |

Geometry rule (what sm-flat's unfolder relies on): every solid is flat walls plus cylindrical
bends of the rule's thickness whose inner radius is the rule's bend radius (or the override);
a radius of 0 gives a sharp inside corner (the inner cylinder collapses to a line).

## Tests

- Golden models (`SciForgeTests/golden/models/sheetmetal_*.json`, 19, volumes derived by hand
  except the inside corner's FreeCAD baseline): base flange rect, Side 2 / Centered with a
  0.5 mm rule, New Component, Join, L bracket, every Bend Position and Height Datum, mitred
  corner, a four-edge tray, an inside corner, flange on a flange, partial width with reliefs,
  Two Offsets between two planes, rule edit recomputes, contour L, contour Two Sides / Side 2,
  a contour on a sheet edge, angle edit, To Object, an Extrude cut through the sheet then a
  flange edit.
- Unit tests: `SciForgeTests/unit/test_sheetmetal_flange_core.py` (flange maths, rule lists).
- Scenarios (real clicks): `sheetmetal_flange` (base + edge, Rule drop-down, datums,
  positions, height arrow and angle handle drags, undo/redo, edit, Esc, swapping the body's
  rule), `sheetmetal_rules` (the whole rules dialog, refusals, undo of the visit),
  `sheetmetal_contour` (contour options, drag, Cancel, save / reopen, edit after reopen, a
  contour on a sheet edge), `sheetmetal_edge_options` (miter, reliefs, refusals, To Object,
  Two Offsets, Sheet Metal component), `sheetmetal_parameters` (a user parameter in Height),
  `sheetmetal_components` (New Component, Extrude cut through sheet metal, Join), and
  `ribbon_sweep` with `SWEEP_TABS=sheet_metal`.

## Known gaps

- **Corner relief shapes are not cut into the folded part.** Two flanges meeting at a corner
  are mitred and the plate's corner under both bends is removed (what Trim To Bend gives), but
  a Round / Square / weld relief is a hole Fusion places on the flat pattern (at the crossing
  of the two bend centre lines) and folds back with the part. Cutting it in the folded solid
  means cutting across the bends, which needs the unfolder (sm-flat): a hole wrapped round a
  bend has faces that are neither planes nor cylinders, which a planar + cylindrical unfolder
  cannot lay flat, and the default rule (Round) would put one in every mitred corner. The
  shape, placement and size (rule or override) are kept on the flange step for the flat
  pattern to cut: `sheetmetal_flange.corner_reliefs(step)` lists every mitred corner (the
  corner of the two bends' tangent lines, the two flange directions) with its relief. The
  same goes for the 3-bend corner relief.
- **Edge flange Operation New Body** (Fusion: single edge only) is not offered: an edge
  flange always joins its body.
- **Contour flange attached to an edge** runs the whole edge: its width types and bend position
  (Fusion, G) are not offered.
- **Splines in a contour flange** are refused (only lines and arcs can be bent with the rule's
  radius here); Fusion accepts them.
- **No flip arrow** on a base flange (the Orientation box only).
- **Tear bend relief** is a 0.05 mm slit, not a zero-width split (a solid cannot hold one).
- **The Lofted flange type** is sm-more's own entry.
- **Rule expressions** accept Thickness only, not user parameters (critic pass CP2 item 4); the
  Flange's own fields do take user parameters.
