# Parity spec: SHEET METAL, more forming tools (Bend, Hem, Join by Bend, Corner Closure, Lofted Flange, sheet metal Fillet / Chamfer)

Wave 6, branch `sf/sm-more` (2026-10-23). Implemented in `src/Mod/SciForge/sciforge/`:

| File | What it holds |
|---|---|
| `sheetmetal_bend_core.py` | pure maths (no FreeCAD, no Qt, unit tested): bend zones (Start / Center / End), strips of sheet walked as a centre line (lines + arcs given by their inner radius) and their outline, the six hem shapes, the Join by Bend fillet, Corner Closure reaches, Brake Form facet counts, the thickness-edge test |
| `sheetmetal_bend.py` | Bend (Fusion's Fold): `fold()` and the `BendFeature` step; shared helpers (`edge_frame`, `strip_solid`, `frame_box`, `fuse_all`, `one_solid`, `rule_values`) |
| `sheetmetal_hem.py` | Hem: `hem_shape()` / `edge_strips()` and the `HemFeature` step |
| `sheetmetal_bend_join.py` | Join by Bend: `join_shapes()` and the `JoinBendFeature` step (the other body is used up, `bodies.CONSUMERS`) |
| `sheetmetal_corner.py` | Corner Closure: `closure_shape()` and the `CornerClosureFeature` step |
| `sheetmetal_corner_round.py` | sheet metal Fillet / Chamfer: `round_shape()` and the `RoundFeature` step (radius sets kept in `SciForgeSmRound`) |
| `sheetmetal_lofted.py` | Lofted Flange: `lofted_shape()` (Brake Form facets, Die Form loft) and the `LoftedFlangeFeature` step |
| `sheetmetal_bend_panel.py` | the shared dialog base (Fusion's selection boxes, value rows, live preview, OK / Cancel / Esc, edit), view provider base, timeline kinds |
| `sheetmetal_bend_ui.py`, `sheetmetal_hem_ui.py`, `sheetmetal_bend_join_ui.py`, `sheetmetal_corner_ui.py`, `sheetmetal_corner_round_ui.py`, `sheetmetal_lofted_ui.py` | the commands `SciForge_SheetMetalBend`, `..Hem`, `..JoinBend`, `..CornerClosure`, `..Fillet`, `..Chamfer`, `..LoftedFlange` and their dialogs |
| `ai/ops/sheetmetal_ops.py` (block `# --- sm-more ---`) | golden / AI steps `sf_sm_bend`, `sf_sm_hem`, `sf_sm_join_bend`, `sf_sm_corner_closure`, `sf_sm_lofted_flange`, `sf_sm_fillet`, `sf_sm_chamfer`, `sf_sm_more_edit` |
| `tools/sciforge/icons_sheetmetal2.py` | icons `sm_bend`, `sm_hem`, `sm_join_bend`, `sm_corner_closure`, `sm_lofted_flange`, `sm_fillet`, `sm_chamfer` (original artwork) |

Fusion's behaviour comes from `docs/sciforge/dev/research/fusion-sheet-metal.md` (sources there:
**A** = Autodesk help / API / blog, **F** = forum or tutorial, **G** = guess, **G(Inv)** =
Inventor; its critic pass is followed where it corrects the first pass). Every solid these
tools make is flat walls + cylindrical bends of the rule's thickness with the rule's (or the
override's) inner bend radius, so sm-flat's unfolder can lay it flat; the exceptions are named
(Flat hem, Lofted Flange).

## Behaviour

### Bend (SHEET METAL > CREATE > Bend; the API's Fold)

| Fusion | SciForge | Src |
|---|---|---|
| Stationary Side: a top or bottom planar face of the sheet; that side stays | Same box; only a planar face with the sheet's thickness behind it lights up. The side of the bend line where the face was clicked stays (the click point is stored) | A[R18], A[R31] |
| Bend Lines: sketch lines in a plane parallel to the stationary face, several, one row each | Same box (several lines); "Values For" picks a line to give it its own angle / position / flip / Bend Relief. Lines not parallel to the face are refused with the reason; lines in a parallel plane are projected onto the face | A[R11], A[R31] |
| Several lines: pick the farthest from the stationary side first | SciForge sorts them itself (farthest bent first), so any picking order works | A[R11] (order), G (sorting) |
| Bend Line position Start / Center / End (where the line sits on the bend zone in the flat state) | Same three choices, default Center. The zone is BA = angle x (R + K T) wide, placed against the line | A[R31], F[F3] |
| Angle (default 90°) | Same, with a round angle handle on the bend and its value box | A[R31], G (default) |
| Flip (bend up or down) | Same: up turns toward the stationary face's outside, Flip turns the other way | A[R47], G |
| The body is reshaped, no material added | Same: the sheet beyond the zone moves back by BA and swings round the bend's axis; the zone is laid onto the bend's cylinders | A[R11] |
| With Center the bend runs across the whole body | Same: the line is extended across the sheet. Where the sheet beyond the bend is narrower than the sheet the line crosses (a tab), only that width bends and the rest of the zone stays | F[F3], A[R31] (bend relief at the bend's ends) |
| Holes or cut-outs in the bend zone | They come through bent: the zone's outline is mapped onto the cylinders (a straight line in the flat zone is a straight line in the cylinder's angle / height parameters) | G (geometry) |
| Bend Radius from the rule | Same, with an Override Bend Radius row (G: Fusion's API shows no radius) | F[F5], G |
| Bend Relief (per line) / Corner Relief checkboxes | Bend Relief (default on, and per line through Values For): where a bend ends beside sheet that stays (a tab), the rule's bend relief is cut into that sheet at both ends: a slot of the rule's Relief Width from the rule's Relief Depth below the zone to its far side, Straight or Round-ended (research 4.5), or the rule's Tear: a split along the bend's end, cut as a 0.01 mm hairline across the zone (one solid cannot hold two faces touching); off on a tab is refused with the reason. Corner Relief is stored (crossing lines are refused, Known gaps) | A[R31], A[R1], research 4.5 |
| A zone that is not flat sheet | Refused: "The bend zone crosses something that is not flat sheet ... Move the bend line onto a flat part of the sheet." | G |
| A bend that would run the sheet into itself | Refused: every bend is checked to add up (the bent zone holds ((R + T)^2 - R^2) / (2 (R + K T) T) of its flat volume at any angle), so an overlap or a failed cut is refused with "This bend would run the sheet into itself, or it could not be built cleanly here" | G |
| Timeline Bend<n>, the sketch consumed | "Bend 1"; the bend lines' sketch is hidden | G |

### Hem (SHEET METAL > CREATE > Hem)

| Fusion | SciForge | Src |
|---|---|---|
| Edges (several) where the top or bottom face meets a side | Same; only those edges light up (straight, side as thick as the sheet) | A[R13] |
| Types Flat / Open / Rolled / Teardrop / Rope / Double with their values (Length, Gap, Angle, Radius, Setback, the API's set*Hem signatures) | Same types, each showing only its values (Flat: Length; Open: Length, Gap; Rolled: Radius, Angle; Teardrop: Radius, Length, Gap; Rope: Length, Gap, Radius; Double: Gap, Length, Setback) | A[R13], A[R14], A[R30] |
| Default values not published | Open, Length 4T, Gap 0.5T, Radius 2T, Angle 270°, Setback 0 | G |
| Bend Position Inside / Outside / Adjacent / Tangent | Same. Inside / Tangent: the hem's outside stays at the edge (the sheet is cut back by r + T); Outside: by r; Adjacent: not cut | A[R14], A[R29], research 4.4 |
| Flip | Hems under the sheet instead of over it | A[R14] |
| Miter Corners at a corner shared by two hemmed edges | On: each hem stops half the rule's Miter/Rip/Seam gap short of the corner's bisector; off: the hems overlap | A[R14] |
| Override Rules (bend radius) | Override Rules + Bend Radius (used by the Rope's reverse bend) | A[R13] |
| Length | Measured from the hem's outside (its outermost point) back over the sheet (G: "distance from the selected edge") | A[R14], G |
| Shapes | Flat: a 180° fold pressed shut; Open: 180° fold of inner radius Gap/2; Rolled: a roll of inner radius Radius through Angle; Teardrop: a roll then a straight run that comes back down to Gap above the sheet; Rope: a roll, a reverse bend of the rule radius, then a run lying Gap above the sheet; Double: a 180° fold, a return of Length, a second 180° fold the other way and a run back out that stops Setback short | A[R30] (descriptions), G (exact shapes) |
| Live preview, a Length handle | The blue arrow drags the Length (value box beside it) | A, G |
| Timeline Hem<n>; redefine as another type | "Hem 1"; the edit dialog changes the type | G, A[R30] |

### Join by Bend (SHEET METAL > CREATE > Join by Bend; Sep 2026)

| Fusion | SciForge | Src |
|---|---|---|
| First Edge on one sheet metal body, Second Edge on another | Same two boxes; the step goes into the First Edge's body, the other body is used up (hidden while the step is in the design, back on Undo or delete) | A[R40], A[R42] |
| Use rule bend radius (default on) / Bend Radius | Same | A[R40] |
| The plates are extended or trimmed so one bend joins them | Same: the bend (inner radius R) is tangent to both plates' middle planes; each plate is extended or cut back to its tangent line; the bend runs where the two edges overlap | A[R42], G (geometry) |
| Refusals | Different thicknesses; parallel sheets ("no bend can join them"); edges not along the line where the sheets meet; edges that do not overlap; sheets in line | G |

### Corner Closure (SHEET METAL > MODIFY > Corner Closure)

| Fusion | SciForge | Src |
|---|---|---|
| Dominant Edge, Submissive Edge (the two flanges at a corner) | Same boxes; an edge at each flange's end (where its face meets its end), square or already mitred (two flanges made together by Flange: the corner can be closed further, to a smaller gap) | A[R39] |
| Alignment Symmetric Gap / Overlap | Same. Symmetric Gap: each flange end (wall, and its bend where it ends in the same plane) is taken in line until half the Gap short of the corner's bisector (a mitred corner). Overlap: the dominant runs over the other's end to its outside face (less (1 - Overlap) T), the submissive stops the Gap short of the dominant's inside face | A[R39], G (geometry) |
| Gap (rule's Miter/Rip/Seam gap by default) | Rule Gap on by default, or your own Gap | A[R39] |
| Overlap 0..1, Flip Overlap | Same | A[R39] |
| Extend Aligned (default on) | On: each end is taken in line with its flange; off: square toward the other flange (the same on a 90° corner) | A[R39] |
| Bend Transition Smooth / Straight Line / Trim To Bend | The row is shown; Trim To Bend is built (the bends meet the relief as cut), the other two are greyed with the reason | A[R39] |
| Relief Placement Tangent / Intersection / Vertex | All three, shown for Round / Square, default Intersection (the rule's default; Fusion's API default is Tangent). Intersection: centred where the two bends' centre lines cross; Vertex: centred where both bends start on the flat side (the inner corner); Tangent: a Round whose edge touches the far side of both bend zones, so it clears their whole crossing (a Square is refused with the reason, research 4.6) | A[R39], A[R1], G (Vertex, and which side Tangent touches) |
| Relief Shape Round / Square / Tear / Trim To Bend / Linear Weld / Arc Weld / Laser Weld | Round, Square, Tear, Trim To Bend (default). Tear: no cut, the bends are carried to the mitre with the walls, the Gap between them. Trim To Bend: whatever lies inside both bend zones is cut away, so each bend stops where the other one starts and the corner stays open under the closed walls (in the flat state: the patch between both bends' start and end lines; works with Overlap too). Round (Size = diameter) and Square (Size = side), the rule's 2-bend size or your own: the closed part is laid flat with sm-flat's unfolder, the shape cut at its placement, and the cut folded back onto bends and walls (sm-flat's refold). The result must still lay flat, else it is refused saying to try another placement or size (so is a cut that would split the body). With Overlap a Round or Square relief is refused (the overlapped corner lies over itself when laid flat). The weld shapes are not built | A[R39], A[R22], A[R1], research 4.6 |

### Lofted Flange (Fusion: the Lofted type of the Flange dialog)

| Fusion | SciForge | Src |
|---|---|---|
| Type Lofted inside the Flange dialog | Its own command right under Flange in the CREATE menu (one dialog later: Known gaps) | A[R44] |
| Two profiles on separate planes, both open or both closed, lines and arcs only; auto-chain | Same: a click on a sketch curve takes its whole connected chain; mixed open / closed, splines, coplanar profiles refused with the reason | A[R15], A[R16] |
| Forming Type Brake Form / Die Form | Brake Form: arcs become straight facets; each corner of one profile fans out to the stretch of the other in the same direction round its centre, one flat facet along each side (a square-to-round transition), each facet moved T along its normal; Die Form: a smooth loft of the profiles thickened in their own planes (open profiles: very fine facets) | A[R16], A[R38], G (geometry) |
| Facet Control Chord Tolerance / Facet Angle / Facet Distance / Face Number | Same four, with SciForge's defaults 0.1 mm / 10° / 5 mm / 6 | A[R15], A[R38], A[R44], G (values) |
| Orientation Side 1 / Side 2 / Center | Same | A[R15] |
| Operation New Body / Join, Rule | New Body (a new sheet metal body; its Rule box lists the design's rules then the library's, the active rule first) or Join (into the active sheet metal body, its own rule) | A[R44], CP2 item 3, G |
| Die Form flat pattern | The step says `Developable = False`; the flat pattern can refuse it with that reason | CP2 item 7 |

### Sheet metal Fillet / Chamfer (SHEET METAL > MODIFY > Fillet / Chamfer; Sep 2026)

| Fusion | SciForge | Src |
|---|---|---|
| Only the edges through the thickness can be picked | Only those light up (straight, as long as the sheet is thick, square to its faces); any other is refused with the reason | A[R41] |
| Fillet radius sets (at least one) | "+ New Set" keeps the corners picked with their radius and starts another set; the sets are listed and come back on edit. A blue arrow on the corner drags the radius (value box beside it) | A[R41] |
| Chamfer distance | Equal distance per set | A[R42], G |
| The flat pattern keeps the rounds | The rounds are cylinders through the thickness, so they show as arcs in the outline | G |
| The SHEET METAL tab's MODIFY Fillet / Chamfer | The same buttons; on a body that is not sheet metal they open the SOLID Fillet / Chamfer (Fusion repeats the solid commands) | A[R42], G |

## Tests

| Kind | What | Result (2026-10-23) |
|---|---|---|
| Unit | `SciForgeTests/unit/test_sheetmetal_bend_core.py`: bend zones (research 4.2 worked example), strips, every hem type and its refusals, the open / teardrop / rope geometry, the join fillet, closure reaches, the corner relief placements (Intersection / Vertex / Tangent) and their refusals, facet counts, the transition triangulation (corner fans), the thickness-edge test | 26 tests pass |
| Golden | 32 models `sheetmetal_smm_*.json`: a bend on a plate that has an edge flange; a hem on a bent wall; save + reopen of a hemmed, filleted, bent plate then an edit; a hem on an edge flange; bend centre / two lines / flip-start-45 edited to 60 / hole in the zone / a tab bent on a line across its root (Center, and End on a short line: reliefs cut) / a plus-shaped blank folded into an open box by four lines in one Bend; the six hem types, two mitred hems, a hem edited to Rolled; join by bend; corner closure symmetric (Trim To Bend), Tear, overlap, Extend Aligned off, on an already mitred corner, with a Round relief, a Round at the Tangent placement and a Square at the Vertex placement (on the mitred corner); lofted brake, die (edited to Face Number 4) and joined to a plate; fillet + chamfer. Analytic volumes where the shape allows (bends, tabs with reliefs, hems, join, fillet); FreeCAD 1.1.4 baselines for the rest | all pass |
| Cross-check with sm-flat's unfolder | `sheetmetal_unfold.unfold` (branch `sf/sm-flat`, read-only copy) run on this branch's shapes: a 90° bend, a 45° flipped Start bend, the U (two lines) and a bend with a hole in its zone all lay flat to exactly the 100 x 40 plate they were bent from (volume 4000.0000, holed 3999.2148 = less the hole); the six hems, the join and a filleted plate unfold too (flat lengths = cut-back sheet + neutral-layer length of the strip) | all unfold |
| Scenario `smmore_bend` | ribbon Bend, waits; stationary face; line; 90° preview (hand-worked volume); type 45; Start; Flip; OK; Bend 1; Ctrl+Z / Ctrl+Y; edit from the timeline back to 90 Center; a line past the sheet refused (OK waits); Esc; save, close, reopen | PASS, 44 checks |
| Scenario `smmore_bend_two` | Bend in an empty design (no dialog, no error); a plate in a moved component; the face, then two lines: a U; Values For Line 2 at 45 (Line 1 keeps 90; All lines shows the common value); Bend Radius override 2; OK | PASS, 18 checks |
| Scenario `smmore_bend_tab` | a plate with a 20 mm tab, a line across its root; ribbon Bend; face, line: only the tab bends, round reliefs beside it (hand-worked volume, points in the plate and in a slot); Bend Relief off refused with the reason, back on; Line 1's own Bend Relief (Values For) off refused, All lines still on, back on; OK; Bend 1; Ctrl+Z / Ctrl+Y; the unfolder lays it flat to the plate and tab less the two reliefs | PASS, 20 checks |
| Scenario `smmore_hem` | every type from the Type list (volumes from the cross-section), the rows each type shows, the Length arrow dragged (value box), a Length too short refused, a second edge mitred, OK, Hem 1, Ctrl+Z / Ctrl+Y, edit (Flip), Cancel | PASS, 40 checks |
| Scenario `smmore_join` | CREATE menu Join by Bend; parallel plate refused, Esc; joined (hand-worked volume); the other body hidden; Ctrl+Z / Ctrl+Y; edit to a 3 mm Bend Radius | PASS, 25 checks |
| Scenario `smmore_corner` | two edge flanges (Flange code) on a notched plate; MODIFY menu Corner Closure; Symmetric Gap (points inside / in the gap); Round relief (rule size), Square; Trim To Bend by default, Tear (more material), Tangent with a Square refused, Round at Tangent (cuts more), Vertex (on this notched corner refused with what to try), back to Intersection; Overlap with a relief refused, Trim To Bend, a 0 gap; OK; Ctrl+Z / Ctrl+Y; edit back; Cancel | PASS, 37 checks |
| Scenario `smmore_round` | MODIFY Fillet; a top edge not taken; 5 mm; the radius arrow dragged (value box); + New Set, 10 mm (hand-worked volumes); OK; Fillet 1; Ctrl+Z / Ctrl+Y; Chamfer 4 mm; edit (sets back) | PASS, 26 checks |
| Scenario `smmore_lofted` | CREATE menu Lofted Flange; square + circle: Brake Form in a new sheet metal body; chord 0.5; Die Form (not developable); Face Number 4; OK; Ctrl+Z / Ctrl+Y; edit from the timeline to Die Form; an open line with a closed square refused; Esc | PASS, 27 checks |

## Known gaps

1. **Bend: per-line values through a "Values For" list.** Fusion shows a row per bend line;
   SciForge has one set of fields with a "Values For" list (All lines, Line 1, Line 2, ...):
   choose a line to give it its own angle, Bend Line position, flip and Bend Relief (marked "*").
2. **Bend: Corner Relief where bend lines meet.** Lines that meet at a corner of the sheet (a
   box folded from a plus-shaped blank) work with Bend Line Start or End: the zones lie in the
   arms and never overlap (golden `sheetmetal_smm_bend_box`). With Center the zones overlap at
   the corners and the bend is refused with the reason: Fusion cuts its corner relief there
   first; SciForge does not yet (the checkbox is stored; a trial that cut the rule's round
   relief first left booleans that did not add up, so it was not shipped). Lines that cross
   inside the sheet are refused the same way.
3. **Bend: Bend Relief.** Built for a tab (the sheet beyond the bend narrower than the sheet
   the line crosses): Straight and Round reliefs, and Tear as a 0.01 mm hairline split (the
   Flat hem's reason, gap 5); the rule's Relief Remnant is not applied. A tongue cut inside a plate (sheet that stays
   on both sides beyond the line) still bends all the sheet beyond the line.
4. (fixed) A second line drawn on the face was hard to click once the preview showed the part
   see-through: while a box takes sketch curves only, clicks now go through the part.
5. **Flat hem keeps a 0.01 mm hairline gap.** OpenCASCADE cannot hold two layers of one solid
   touching face to face (they would merge into one thick layer and the sheet could no longer
   be unfolded). The flat length changes by pi x 0.005 mm = 0.016 mm.
6. **Hem shapes are SciForge's reading of Fusion's descriptions** (Teardrop's leg comes back to
   the Gap, Rope = roll + reverse bend + flat run, Double = Z-fold with Setback): Fusion's exact
   sections were not published (research §5 item 5).
7. **Corner Closure: weld relief shapes (Linear / Arc / Laser Weld), Smooth / Straight Line
   bend transitions, 3-bend corners, a Round or Square relief with Overlap.** Built: Tear,
   Trim To Bend (both alignments), Round and Square at the Intersection, Vertex and Tangent
   (Round) placements with Symmetric Gap, Extend Aligned on and off; a Round or Square relief
   with Overlap is refused with the reason. "Rule Relief Size" takes only the size from the
   rule (Fusion's "Use rule defaults" also takes the shape and placement, and Fusion's API
   default placement is Tangent; SciForge's default relief is Trim To Bend at Intersection).
   Some placements cannot be cut on some corners (on the notched test corner the Vertex cut
   fails): the dialog says so and suggests another placement or size.
8. **Lofted Flange is its own command**, not yet a Type of the Flange dialog (sm-forming owns
   that dialog; one dialog later).
9. **Lofted Flange, Brake Form: the facets meet in sharp folds**, not in bends of the rule's
   radius. The facets are laid out like a press-brake transition (each corner of one profile
   fans out to the part of the other profile in the same direction, one flat facet along each
   side), but sm-flat's unfolder (planar walls + cylindrical bends) refuses sharp folds
   ("edge ... is a sharp corner between two walls, not a bend: fillet it ... or Rip it", checked
   2026-10-23), so a Brake Form lofted flange has no flat pattern yet. Die Form is refused too
   ("the thickness could not be measured at that face"); its step says `Developable = False`
   (the flat pattern could name that reason: a note for sm-flat's code).
10. **Lofted Flange, Die Form: the wall is T thick measured in the profile planes** (a loft of
    the thickened profiles), slightly thinner across a sloping wall.
11. **Join by Bend: no flip or position options** (the API shows none, research §5 item 9);
    the bend always takes the inside of the corner the two plates make.
12. **Sheet metal Chamfer: equal distance only** (research §5 item 16).
