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
| Deleting a rule that is in use is refused | Refused with the bodies that use it; also refused for the active rule, a Sheet Metal component's active rule (QA) and the design's last rule | G |
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
| Base flange Operation New Body / Join (also New Component) | New Body (default; the sketch's own empty body becomes the sheet metal body), New Component (a new Sheet Metal component with the rule active), Join (into the active sheet metal body, in its rule; the new plate must carry on one of its sheets in that sheet's plane, QA) | A[R27] |
| Rule drop-down for the body being made | Same (design rules, then library ones, copied into the design when used) | A[R44] |
| Contour flange: an open chain of lines and arcs; sharp corners become bends with the rule's radius | Same: every line-line corner gets the radius that makes the bend's **inside** radius the rule's (the line is the inner or outer face depending on the side and the turn); tangent arcs stay as drawn | A[R5], F[F15] |
| Contour Distance (drag handle), Direction One Side / Symmetric / Two Sides, thickness side | Same (Flip turns One Side round); a blue arrow with its value box sets Distance | A[R2], A[R27] |
| A contour profile drawn from the end of a sheet edge (sketch plane square to the edge) is joined along that edge | Same: the dialog finds the edge, sets Join and runs the flange along the whole edge; the corner between the sheet and the first line is bent with the rule's radius, the sheet cut back for it, the thickness on the side that carries the sheet on (the Distance options do not apply) | G (research 2.2.3) |
| Edge flange Height Extent Distance / To Object (one edge only) | Same; To Object lights the Object box: the flange runs to the picked face's or plane's plane (+ Offset) | A[R2], A[R27] |
| Height Datum Inner Faces / Outer Faces / Tangent To Bend | Same (research 4.3): walls H - R tan(a/2), H - (R + T) tan(a/2), H | A[R2], F[F15] |
| Bend Position Inside / Outside / Adjacent / Tangent | Same (research 4.4): the plate is cut back (R + T) tan(a/2), R tan(a/2), 0; Tangent keeps the bend's outside on the side face from 90 degrees up (below 90 it is Inside, G) | A[R2], A[R29] |
| Angle, default 90; Flip turns the flange over the plate | Same; angle 0 < a <= 180 | A[R27], A[R2] |
| Width Full Edge / Symmetric / Two Sides / Two Offsets (between two picked reference faces or planes, an offset from each) | Same: Two Offsets lights Offset Object 1 then 2; the flange runs between where the two references cross the edge, each offset inwards. With no reference picked the offsets count from the edge's ends (SciForge) | A[R2] |
| Several edges; adjacent ones mitred with the Miter/Rip/Seam Gap; the corner closes up to the gap (research 4.7) | Same: each pair of picked edges that meet at a corner of the same face is cut on the corner's bisector, gap/2 each side (a four-edge tray and the inside corner of an L-shaped plate work). Where the flanges stand out past the plate's edges (Bend Position Outside / Adjacent, or walls leaning out below 90 degrees), each one runs on past the outside corner far enough to meet the mitre, so the corner closes up to the gap (QA; before, those corners were left open) | A[R6], G(Inv) |
| Bend relief where the flange stops inside its edge: Straight / Tear / Round, width, depth, remnant | Same (research 4.5): a slot from the edge back across the bend zone and Relief Depth more, Relief Width wide; Round ends in a half circle; a plate sliver narrower than Relief Remnant is cut away; Tear is a 0.05 mm slit (a solid cannot hold a zero-width cut) | A[R6], A[R1], G |
| Rule overrides with their check boxes: Bend Radius, Bend Relief, Corner Relief (2 bends), Corner Relief (3 bends) | Same check boxes and fields. Bend Radius and Bend Relief change the geometry; the corner relief overrides are kept on the step (see Known gaps) | A[R1] |
| Live preview, drag arrow with its value box, OK / Cancel | Same: the preview is the real step; the height arrow stands on the Height Datum point and points along the wall; an angle handle turns about the bend's axis (G); every field and value box takes a number, a user parameter or a formula | A[R2], G |
| Timeline "Flange<n>" with the flange icon; edit from the timeline | Same (double-click opens the dialog with the picks and values) | G |
| A later Flange on a plate edge next to an earlier flange | Works: the edge's side face runs on into the earlier flange's end face (one coplanar face), and the edge is still recognised as a sheet edge by probing the solid's thickness under it (QA; it was refused as "not on the sheet's thickness") | G |
| Errors: curved edge, an edge not on a sheet metal body, a flange that runs into the part, a height that does not reach past the bend | Refused in the dialog with the reason (OK keeps it open): curved edge, edge across the thickness, edge of another body, overlapping flanges, a flange that would run into the part, Height Datum Inner / Outer or Bend Position Inside / Outside at 180 degrees, a contour line too short for its bends, a closed or branched contour, a spline in a contour, a Join sheet laid on the body's sheet (double thickness), standing on it or across its edge (not in its plane: a sharp corner, QA) or apart from it | G |

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
- QA (2026-10-23, branch `sf/sm-forming-qa`): scenario `sheetmetal_qa` (an empty design:
  Flange waits, OK refused, Esc adds no undo step, Sheet Metal Rules visit with Esc in the
  editor; an edge picked before Flange; Cancel; a mitred corner saved, closed and reopened
  with its proxies, view providers and rule link; edit from the timeline and Cancel; a rule
  edit after the reopen with Undo / Redo; a later Flange on the two edges next to the earlier
  ones; a component's active rule cannot be deleted; New Component with another rule; an
  Outside mitre that closes its corner), golden models
  `sheetmetal_edge_flange_adjacent_later` and `sheetmetal_edge_flange_miter_outside` (volumes
  by hand).

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

## QA pass (2026-10-23)

Fixed on `sf/sm-forming-qa`:

- **A second Flange next to an earlier one was refused.** After an edge flange, the plate's
  side face next to it and the flange's end face are one coplanar face, so the edge's "side
  face" was wider than the thickness and `edge_frame` refused it ("not on the sheet's
  thickness"): flanging a box one edge at a time was impossible. `edge_frame` now probes the
  solid (material half a thickness under the face, none past the thickness) when the face
  extents cannot tell.
- **Mitred corners of flanges that stand out past the plate were left open** (Bend Position
  Outside / Adjacent, or walls leaning out below 90 degrees: a notch or a widening V at the
  corner). Each flange now runs on past the outside corner by its reach and is cut on the
  bisector, so the corner closes up to the gap (research 4.7). Inside corners and flanges
  that stay inside the plate's outline are as before (every earlier golden model unchanged).
- **A rule that was a Sheet Metal component's active rule could be deleted**, leaving the
  component pointing at a rule the design no longer had. Refused now with the reason.
- **New Component with the Rule changed after the pick** gave the body the new rule but left
  the new component's active rule at the old one. The component follows the Rule box now.
- **A library rule tried in the Flange's Rule box and then left for another** stayed In This
  Design after OK (it is copied in when chosen). OK now takes it out again when nothing
  follows it (a body, the active rule, a component's rule).
- **Inserting a design that has its own rule** into a design that already used sheet metal
  silently rebuilt the inserted parts with the default rule (a 0.5 mm part became 1 mm, with
  only a console warning): FreeCAD copies the rule store the flanges link under another name
  (`SheetMetalRules001`), which `find_rule` never read. Copied stores' rules now count as
  the design's (`sheetmetal.design_rules`), and the next rule save keeps them in the store.
- **Editing a stand-alone contour flange from the timeline hid its options.** The dialog
  looked for a sheet edge the contour starts from in the flange's own solid (the body's
  first step has no sheet before it), took it for a contour on a sheet edge and hid
  Distance, Orientation, Direction and Flip ("it runs the whole edge"). A flange that is its
  body's first step is never attached now, and neither the Join target nor an attachment is
  looked for in the body the dialog's own preview made.
- **The Sheet Metal Rules window showed Close while a rule was edited**: Close dropped the
  typed values without a word. Only Save / Cancel show on the editor page now.
- **An edge flange's override fields started at the active component's rule**, not at the
  body's (Bend Radius 1.00 shown for a 1.5 mm Aluminum body). They follow the picked body's
  rule now.
- **A To Object / Two Offsets face clicked on the flange being previewed** was looked up by
  its name on the part before the flange; the preview numbers its faces its own way, so the
  same name was another face (a wrong height or a refusal, depending on the face hit). It
  is now the face in the same plane on the part before the flange (a face only the new
  flange has is refused with the reason).
- **Editing an earlier flange took edges and faces of the later steps** (the part is shown
  whole while a flange is edited): a click on a later flange's edge was linked to that
  later step and failed ("Edge54 is gone"). Picks on the flange itself and on later steps
  are now mapped to the part before the flange (same line / same plane), or refused with the
  reason ("made by a later step").
- **Choosing other units for a new rule left the old unit in every box** ("1.0 mm" in an
  inch rule), and Save refused them. The plain-number lengths are converted now ("0.0394
  in"); expressions in Thickness stay as typed.
- **Two profiles that do not touch made one body holding two separate plates** (SciForge's
  Extrude refuses that: a body holds one solid, and the flat pattern unfolds one sheet).
  Refused now with the reason (pick touching profiles, or one plate at a time; Fusion may
  make a body per plate: not checked).
- **To Object (or Two Offsets) chosen and then left kept the dialog waiting for a face**:
  the next edge clicked was refused as a face pick ("To Object: pick a flat face or a
  plane"). Leaving the option hands the clicks back to the edge selection.
- **A base or contour flange Join standing on the sheet (or across its edge)** was fused
  into a T or a sharp L: a solid no flat pattern can unfold (a corner between two sheets
  needs a bend). Join now needs the new sheet (a contour: one of its walls) to carry on a
  sheet of the body in its own plane, touching it; the dialog says why. A contour drawn
  from the end of a sheet edge is joined as before.

Left as they are (reported, not fixed):

- An inserted design's rule with the same name as one In This Design but other values takes
  the design's values (Fusion's behaviour unknown).
- Paste New of a sheet metal component leaves a hidden copy of the rule store in the design
  (harmless: its rules are the design's).
- A Flange added later next to an earlier one meets it with an open corner (no mitre against
  the existing flange; Fusion's behaviour here was not found).
- The Sheet Metal Rules window is not modal: Esc reaches it only while it has the focus.
