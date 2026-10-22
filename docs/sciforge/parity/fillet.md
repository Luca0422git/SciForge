# Parity spec: Fillet (F) and Chamfer (outline 7.7)

Source: Fusion's documented behaviour (public help topics on Fillet and Chamfer, the Fusion
API reference) and everyday use. Not yet checked against Luca's own screen captures (outline
2.4). Implemented in `src/Mod/SciForge/sciforge/fillet_ui.py` (dialogs, commands),
`sciforge/blend.py` (the geometry rules of a plain fillet / chamfer, no GUI) on top of
FreeCAD's `PartDesign::Fillet` / `PartDesign::Chamfer` with Refine on, and, for everything a
FreeCAD feature cannot hold (several sets, Chord Length, Variable, Tangent Chain off, Rule
Fillet, Full Round, chamfer sets), SciForge's own step `sciforge/fillet_sets.py` with its
maths in `sciforge/fillet_core.py` (unit tested); value boxes in `sciforge/blend_field.py`.
Status: **first pass + QA pass (2026-10-11, branch `sf/fillet-qa`), part 2 (2026-10-14,
branch `sf/fillet-2`), not yet signed off by Luca**.

## Values past what fits stop at the limit (Luca's decision, 2026-10-21)

**This deliberately differs from Fusion.** Fusion refuses a value that does not fit (a
radius too big, a wall too thick, an angle too steep) with an error, and the dialog waits
until a smaller value is typed. Luca (2026-10-21): "limit edits to stop at that limit, so if
I want to chamfer something to the max I can quickly drag it without having to type
whatever obscure value the error spits out", and "add the functionality to any tool that
can give that sort of error". So in SciForge (shared helper `sciforge/value_limits.py`):

- an arrow (or disc) dragged past the limit stops there, like the end of a slider; the
  preview shows that result and a blue note under the message says "Largest that fits
  here: 3.47 mm" ("Furthest that fits here" for a limit on the other side: a push into the
  part, a negative angle); OK works at once;
- a plain number typed past the limit is set to it and the note says so: "5 mm does not
  fit: limited to 3.47 mm" (the box keeps what is being typed and shows the limit once it
  is left);
- the limit is found once (a time-budgeted bisection), rounded toward the safe side to the
  box's precision (0.01 mm, 0.1 deg) and built once more to be sure; it is kept for the
  inputs it was found for (the part, the picks, the other values), so a drag never runs a
  search on every mouse move;
- a value from a formula or parameter ("width / 2") is never rewritten: the dialog keeps
  the explanation, with "Largest that fits here: ..." added, and OK waits.

In this dialog: Fillet (Constant radius, Chord Length, the Variable start / end / point
radii, Rule Fillet's radius), Chamfer (Equal Distance, both distances of Two Distances, the
distance and the angle of Distance and Angle), in FreeCAD's steps and in SciForge's own
(several sets: the limit of the set being edited). Press Pull's fillet / chamfer editing
too (see extrude-presspull.md). A Distance and Angle chamfer is checked as the same bevel
built as Two Distances: FreeCAD's own Distance and Angle builder crashed (an OpenCASCADE
segfault in `ChFi3d_Builder`) for some sizes where the bevel runs into a fillet, and its
step kept the last good shape without a reason when a size did not fit. Picking more
edges does not change the size: if it no longer fits it is refused, with the limit.
Scenario `limits_fillet`; `fillet`, `fillet_qa` P4, `fillet_qa_chamfer` P12, `fillet2_*`
updated (P6 and P15, which need a fillet that does not fit, now use a formula).

## Behaviour spec, part 2 (researched 2026-10-14)

Source column: Autodesk = Fusion help or the Fusion API reference (read through search
excerpts), Forum = Autodesk Community or a third-party tutorial, Guess = not documented.

| # | Fusion behaviour | Source | SciForge |
|---|---|---|---|
| 1 | The Fillet dialog has a **Type**: Fillet, Rule Fillet, Full Round Fillet | Autodesk (Fillet reference) | Built (Type drop-down) |
| 2 | The selection box has **rows (selection sets)**; "+" adds a row; each row has its own edges, Radius Type, radius and continuity; all rows are one feature (one timeline step, one undo) | Autodesk (Create a fillet) | Built: "Sets" list with + / −, one step, one undo; each set has its own arrow and value box on the canvas |
| 3 | Picking an edge that is in another set moves it (an edge belongs to one set) | Guess | Built. An edge picked on its own beats a face of another set that has it, whatever the order of the sets (golden `fillet2_face_and_its_edge_in_two_sets`) |
| 4 | "+" gives the new row the settings of the current one | Guess | Built |
| 5 | Dragging a set's arrow / typing in its value box changes that set only | Guess (from use) | Built (the set becomes the current row) |
| 6 | **Radius Type Constant**: one radius along the whole fillet | Autodesk | Built (FreeCAD's Fillet when it is the only set) |
| 7 | **Chord Length**: "the distance between the two edges where the fillet ends and the adjacent faces begin", the same chord along the whole fillet | Autodesk (Fillet reference) | Built: each edge gets R = chord / (2 sin(t/2)), t the turn of the faces' normals, at both ends of each edge (so a chord stays the same where the corner angle changes) |
| 8 | **Variable**: a start radius, an end radius and radius points along one edge; each point has a Radius and a Position (0 = start of the edge, 1 = its end) | Autodesk (Fillet reference; API VariableRadiusFilletEdgeSet.addMidPosition: positions 0..1) | Built |
| 9 | A point is added by clicking on the selected edge (a dot shows where); the points are sorted from start to end whatever order they were added in | Forum (third-party deep dive, quoted in search results) | Built: a click on the picked edge adds a point there (with the radius the law has there), and **Add Point** puts one in the middle of the widest gap; ✕ removes a point; the ✕ of the selection box drops the edge. No dot is drawn under the mouse before the click |
| 10 | A point's position is typed, not dragged along the edge | Forum (2017 Community thread) | Same: the position box; each point's radius has its arrow and value box |
| 11 | A variable set rounds one edge (with its tangent chain) | Autodesk (API: one edge or a set of tangent edges) / Forum | Built: a set with more edges is refused with the reason; the positions run along the edge and its tangent chain; a chain that closes on itself has no start: refused with the reason |
| 12 | The radius between the points | Guess | OpenCASCADE's smooth law through the radii at the points and at the ends of the edges between them (it can bulge a little past a point between two far points) |
| 13 | **Tangent Chain** checkbox, on by default: tangent edges are picked with the edge; off: only the picked edges are filleted. A setting of each selection set | Autodesk (Tangent chain reference; API: isTangentChain per edge set) / Forum | Built: the box shows the current set's (see "Tangent Chain off" below for how) |
| 14 | How a round with Tangent Chain off ends where the tangent edge begins | Guess | Cut square to the edge at that corner (a flat end) |
| 15 | **Rule Fillet**, Rule **All Edges** (every edge of the faces / features of the selection) or **Between Faces/Features** (only the edges where two selections meet); faces or features are picked, not edges | Autodesk (Create a fillet; API RuleFilletFeatureInput) | Built: two boxes for Between; a timeline click picks a feature |
| 16 | Rule Fillet's **Rounds / Fillets**: rounds on outside edges, fillets on inside edges, or both | Autodesk (Create a fillet) | Built: two check boxes; nothing left by the rule is explained |
| 17 | The rule re-applies after the model changes (new edges of the picked faces / features are rounded) | Autodesk (the "rule" idea) / Guess (exact behaviour) | Built: the edges are found again at every compute |
| 18 | **Full Round Fillet**: hover a face, its side faces highlight; click the centre face; "+" for another full round | Autodesk (Create a fillet) | Built: a click on the centre face finds its two side faces by itself; each full round is a row |
| 19 | When the centre face has tangent faces, they are rounded too | Autodesk (API FullRoundFilletFaceSet) | Not built (one flat centre face between flat parallel walls) |
| 20 | **Corner Type** Rolling Ball / Setback | Autodesk | Rolling Ball (OpenCASCADE's corner); Setback greyed: kernel limit (below) |
| 21 | **Continuity** Tangent (G1) / Curvature (G2), tangency weight | Autodesk | G1; G2 greyed: kernel limit (below) |
| 22 | Radius Type **Asymmetric** (a different distance on each face) | Autodesk (Fillet reference, newer releases; API: asymmetric sets use setback corners) | Not offered: OpenCASCADE builds circular rounds only (below) |
| 23 | **Chamfer Type** Equal Distance, Two Distances, Distance and Angle; **Flip** swaps the sides | Autodesk (Chamfer reference, Create a chamfer) | Built (first pass); Flip also for Distance and Angle |
| 24 | Chamfer selection sets ("+" rows), each with its own type and sizes | Guess (Fusion's API has chamfer edge sets) | Built |
| 25 | Chamfer **Corner Type** Chamfer / Miter / Blend | Autodesk (Chamfer reference) | Chamfer; Miter and Blend greyed: kernel limit (below) |

## Selection sets, Chord Length, Variable, Rule, Full Round (part 2, 2026-10-14)

How it is built:

- **One step for all of it.** One set of one constant radius (Tangent Chain on) stays FreeCAD's
  `PartDesign::Fillet` (so Press Pull still edits its radius and the parameters table lists
  it). The moment the dialog needs more (a second set with picks, Chord Length, Variable,
  Tangent Chain off, Rule, Full Round) the step becomes SciForge's own
  (`PartDesign::FeaturePython`, SciForgeType `FilletSets` / `ChamferSets`) in the same place
  of the timeline, inside the dialog's one undo step; the steps after it stay on it.
- **A radius per edge in one OpenCASCADE run.** FreeCAD's Python `makeFillet` takes one
  radius for every edge, so a radius per edge goes through a `Part::Fillet` (`Part::Chamfer`
  for chamfer sets) in a hidden throw-away document (opened and closed in about 20 ms). All
  sets are built together, so where two sets meet OpenCASCADE blends their corner as one
  fillet would.
- **Variable**: the edge (with its tangent chain) is cut at the radius points by a vertex
  (`generalFuse`, no face changes); each piece gets its two end radii and OpenCASCADE runs one
  smooth law through them (one round face). Measured on a 40 mm edge (start 1, point 0.5 at
  3, end 1.5): 1.000 / 3.000 / 1.500 at the three places.
- **Chord Length**: measured 3.000 mm on a 90° and on a 120° edge of one set (R 2.12 and 3).
- **Tangent Chain off**: OpenCASCADE always rounds the whole chain of tangent edges
  (`BRepFilletAPI_MakeFillet::Add` builds the contour of tangent edges; a test listing only
  one straight edge of a slot rounded the whole loop). SciForge rounds the chain, then puts
  back the material taken off along the edges that were not picked: the removed material
  is cut by a plane square to the picked edge where it meets an unpicked one, and only the
  pieces along picked edges stay removed. Exact: a slot's straight edge alone removes
  20 r² (1 − π/4).
- **Rule Fillet**: the faces are kept as picks (FreeCAD and `picks.py` follow them through
  edits), the features as links; the edges are found again at every compute (a feature's
  faces are the ones on surfaces the step before it did not have). A hole drawn later in the
  sketch of the picked extrude gets its rims rounded (scenario `fillet2_rule`).
- **Full Round**: the slab under the centre face, half the width deep, minus a cylinder of
  half the width between the side faces, is cut away (exact half round, one face). Refused
  with the reason: a face not between two flat parallel walls, a face that does not span
  the whole width, walls lower than the radius.
- **Formulas**: each set's size is a property of the step (`Size1`, `SizeB1`, `Angle1`...),
  so a parameter or formula typed in a box drives it like FreeCAD's own fillet's radius; the
  parameters table lists them (`Set 1 Size`...). The positions and radii of variable points
  are plain numbers.
- **Element names**: the throw-away document's names are kept in plain text (its string
  table goes away with it) and the throw-away input's tag in them is replaced by the part's
  own, the way FreeCAD's own makeFillet names a result: stable through recomputes and
  edits, and FreeCAD still notices when a later step's edge is really gone (picks.py then
  finds it again by geometry).

Press Pull (Q) on a round of SciForge's step edits the size of the set that made it (the box
says "Fillet radius (set 2)"; Chord Length and Rule Fillet too), as Press Pull edits a fillet
in Fusion (scenario `fillet2_edit_later`).

Dialog details: the current set's row is highlighted, its boxes show its values; clicking a
row, dragging a set's arrow or typing in a set's value box makes that set the current one.
Picks of every set stay highlighted; clicking one drops it from its set. Type changes start
the picks over (each type picks something else). Rule Fillet shows Rule, one or two
"Faces/Features" boxes, Radius, Rounds / Fillets; Full Round shows "Center Face" and the
radius it found ("Half the width between the side faces: 2.00 mm"). A size that does not fit
names its set ("Set 2: Radius 40 mm is too big here ..."); a plain size dragged or
typed there is held at the largest that fits that set instead (Luca, 2026-10-21, see
the top); OK waits only for a formula that does not fit.

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| MODIFY > Fillet or `F`; with nothing selected the dialog opens and waits | Same. The dialog says "Click edges or faces ..." |
| `F` with edges/faces already selected starts with them | Same (also for Chamfer from the ribbon or the right-click menu). Edges selected on another body make that body active |
| Click edges to add them; no Ctrl needed; click a picked edge again to drop it; clicking empty space does not lose picks | Same (FreeCAD's "greedy" selection style while the dialog is open) |
| Click a face: all its edges are rounded | Same; the face itself is stored, so if an earlier edit adds edges to that face they are rounded too |
| Click a feature (timeline): its edges are rounded | Same: a click on a timeline item adds the sharp edges that step created |
| Tangent Chain (on): tangent edges are picked together and highlighted | Same; off, only the picked edges are highlighted and rounded (part 2) |
| Only edges that can be rounded light up under the mouse | Same (selection filter: smooth edges, vertices, sketches, other bodies do not highlight) |
| Live preview | The result is shown solid; the part before the fillet is shown see-through around it, with the picks highlighted at their original corner (so they stay clickable) |
| Blue drag arrow on the first picked edge | Same. It lies on the face next to the edge, its tip on the line where the round starts, pointing away from the edge; drag it out to make the round bigger |
| A value box floating next to the drag arrow; digits typed over the view go into it | Same since 2026-10-13 (`taskui.ValueBoxes`): the box shows the dialog's value with units, follows the arrow, takes a value or formula (Enter = OK). A digit typed with the mouse over the 3D view goes into it |
| The chamfer's arrow is where you can see it | Same since 2026-10-13 (Luca: "the chamfer tool doesn't have an arrow to drag"): Equal Distance and Distance and Angle put the arrow on the face toward the viewer, as the fillet does; it is sized for the screen (about 75 px, never longer than about half the picked edge, never shorter than about 1 mm), so it shows on a 400 mm part and on a 4 mm part. Two Distances keeps one arrow per face. Drawn in front of the part and grabbable through it |
| Radius field, units, parameters and formulas (`r`, `r * 2`, `0.1 in`) | Same: a formula is kept on the feature as an expression (the value follows the parameter) and listed under the boxes ("Radius = r*2"); a bare number is always mm (degrees for an angle); a typo is explained in the dialog and OK waits; no FreeCAD pop-up |
| Dragging the arrow back through the edge | The size stops at 0.1 mm and the arrow comes back to the value shown when the mouse is let go |
| Impossible radius: the dialog says so, OK stays disabled | **Differs (Luca, 2026-10-21):** dragged or typed, the radius stops at the largest that fits, the preview shows it and a blue note says "Largest that fits here: 9.99 mm" (typed: "50 mm does not fit: limited to 9.99 mm"); OK works. A radius from a formula is not rewritten: explained, with the largest radius, and OK waits. **Nothing** is printed to the Report view |
| OK / Enter finishes, Cancel / Esc cancels, one undo step | Same (Esc also works with the mouse over the 3D view) |
| Ctrl+Z while the dialog is open | Ends the dialog and takes the unfinished fillet away; Ctrl+Y brings it back as a normal step |
| Double-click the fillet in the timeline: edit with the edges shown and editable | Same. The model rolls back to the fillet while editing (later steps hidden) and comes back after OK |
| Starting another command finishes this one | Same (kept if valid, else cancelled); F pressed inside Fillet starts a new one with nothing picked; Ctrl+S / Ctrl+N / Ctrl+O finish the dialog first, so a saved file never holds a half-made fillet |
| Right-click marking menu while the command is open | OK (3 o'clock) and Cancel (9 o'clock) work like the dialog's buttons |
| Edits earlier in the timeline keep later fillets on "their" edges | A fillet inserted with the marker rolled back, or an earlier fillet edited to round one more edge, used to break the later fillets/chamfers ("Invalid edge link"): their edges are now found again by geometry (`blend.References`), also when an edge got shorter |
| A body made of several separate solids | Fillets work on it (it used to say "would cut the part into pieces") |
| Distance and Angle chamfer with an angle the bevel cannot reach | The angle stops at the steepest one whose bevel still fits (Luca, 2026-10-21); a formula's angle is explained with that limit |
| Every pick dropped again | The preview step goes away: the body, the timeline and a measurement show the part as it was |

Chamfer: the same picking, plus **Chamfer Type** Equal Distance / Two Distances / Distance and
Angle, a **Flip** button (two distances, distance and angle) and one drag arrow per distance,
each lying on the face its distance is measured on (so it is visible which side is which).

Press Pull on a round or bevelled face still edits that fillet's/chamfer's size (it is the same
PartDesign feature), as before.

## Picked edges kept through edits, saving and reopening (2026-10-14, gaps work)

Fusion keeps a fillet on the edge it rounds when an earlier step changes (it names edges by
the history that made them). FreeCAD 1.1 mostly does too (a wider or taller box, a hole added
to the sketch, a symmetric extrude: all fine, also after reopening), but loses the name in
some edits: a taper added to the extrude under a round made its edge "?Edge4" and the round
went red (the same for a chamfer and a shell's open face; also after a save and reopen).
`sciforge/picks.py` remembers where every picked edge, face and corner of a step or a sketch
was after each good compute (the hidden property `SciForgePicks`, saved in the file) and,
the moment FreeCAD marks one lost, points the step at the element found again there (same
kind, facing about the same way, nearest relative to the part's bounding box, within a
quarter of its size), before the step is computed: no red step. The same keeper serves
Chamfer, Shell, Draft, Hole, Thread, the patterns, Split, Move and sketches on faces (any
step with picks; Sweep, Loft, Press Pull and the constructions keep their own). Timeline
suppress, delete and move decide themselves which steps break and pause it. Sources:
**Guess** (from use: a Fusion fillet stays on its edge when the extrude under it gets a
taper; no help page says how Fusion names edges), and how far a found-again edge may be
from the old place. Golden
`picks_fillet_chamfer_kept_after_reopen`, `picks_shell_kept_on_taper`; scenario
`gaps_picks_kept.py`. Left: a Draft of a tapered extrude's side face is found again but
FreeCAD's Draft cannot draft that face (it is a B-spline), so it stays red.

## Picks made while a preview is built (2026-10-16, the Pi 5 case test)

The dialog takes clicks from FreeCAD's selection 30 ms after they happen and then makes the
selection show exactly its picks (`_sync`: clear, add). When the first preview appears, the
part turns see-through and `_sync` runs again; a click that had come in meanwhile was wiped
before the dialog read it: one edge of several quick clicks was lost (three lid corners
clicked, two taken), and on CI's slow machine one of seven edges clicked a step apart
(`inspect_analysis_curvature`, CI #136). `_sync` now keeps what FreeCAD selected or
unselected since the dialog last looked, while such clicks are waiting. The corners of short
edges are covered by the selection fall-through (`parity/selection.md`).

## Known gaps (shown greyed in the dialog with the reason, never faked)

| Fusion option | Why not |
|---|---|
| Continuity: Curvature (G2), tangency weight | Kernel. OpenCASCADE's `BRepFilletAPI_MakeFillet` builds rounds of circular section, tangent (G1) to the faces: its section shapes (`ChFi3d_Rational`, `ChFi3d_QuasiAngular`, `ChFi3d_Polynomial`) are all circular-arc forms, and FreeCAD's Python does not reach that choice anyway. A curvature-continuous blend needs a new algorithm (a conic / G2 section swept along the edge, e.g. with `GeomFill`): kernel work (outline 9.2) |
| Corner Type: Setback | Kernel. `BRepFilletAPI_MakeFillet` has no setback distances; where three rounds meet it fills the corner itself (a box corner with three rounds gets one spherical face, measured). Needs a corner builder of our own |
| Radius Type: Asymmetric | Kernel. No two-distance (conic) fillet in `BRepFilletAPI_MakeFillet` |
| Chamfer Corner Type: Miter, Blend | Kernel. `BRepFilletAPI_MakeChamfer` closes a corner where chamfers meet with one flat face only (three chamfers at a box corner: one triangle, measured) |
| Full Round of a curved rib, or a centre face with tangent faces | Not built: SciForge's full round takes a flat centre face between two flat parallel walls (a straight rib or wall). Others are refused with the reason |
| Press Pull on a variable round or a full round | It has no single size to edit: Press Pull pushes that face like any other |
| Radius points driven by a formula | A radius point's position and radius are plain numbers (a formula typed in is worked out once); each set's size does follow a formula |
| Window (drag-box) selection of edges inside the dialog | Not handled specially yet |
| A formula shown *inside* the value box | FreeCAD's number box can only show the number: the formula is listed under the boxes (as in Extrude) |
| Edges of several bodies in one fillet | One step belongs to one body: edges of another body are not picked (they do not light up) |
| Fusion draws no seam line on a cylinder | FreeCAD draws the seam of a round boss as a line; it cannot be picked (it is not an edge to round) |

## Tests

- Scenarios (real clicks, keys, drags; any Report-view error fails them):
  `SciForgeTests/gui/scenarios/fillet.py`, `fillet_chamfer.py`, `fillet_features.py`,
  `fillet_chain.py`. Volumes are checked with hand-derived formulas (`gui/blend_steps.py`).
- QA scenarios (22 paths, a beginner's and a power user's habits): `fillet_qa.py` (nothing
  picked, values before picks, Esc mid-pick, fast typing, far / negative drags, three
  timeline edits with undo/redo, E / Q / F / Ctrl+S inside the dialog, save-close-reopen-edit),
  `fillet_qa_part.py` (a part built with sketches, extrudes, Press Pull, a pocket and a chamfer,
  then its first extrude made taller; history edits and an insert with the marker rolled back;
  a two-solid body; a radius from a parameter), `fillet_qa_chamfer.py` (wrong values and
  angles, Flip, a drag through the edge, two edits, undo/redo, reopen, a chamfer round a hole,
  F inside Chamfer), `fillet_qa_more.py` (marking menu, two designs open, two bodies, keys in
  the radius box, the x button, Ctrl+Z in an edit, timeline Delete, empty design, a Press Pull
  edited under a fillet, the design closed under the dialog).
- Golden models `blend_*` (ops `blend_fillet`, `blend_chamfer` in the builder; same code as the
  dialogs): face pick, feature pick (inside + outside round), tangent chain on a slot, edit,
  Press Pull on a dialog-made fillet, two distances + flip, distance and angle; and
  (`sciforge/ai/ops/blend_ops.py`: ops `blend_insert`, `blend_edit`) a chamfer inserted before a
  fillet with the marker rolled back, a fillet edited to trim a later chamfer's edge.
- Unit tests: `SciForgeTests/unit/test_blend_core.py`.
- Part 2 scenarios (real input; volumes and sizes measured on the part):
  `fillet2_sets.py` (two radius sets in one step: "+", each set's arrow and value box, a
  drag of set 1's arrow, Enter in set 2's box, a radius too big for its set refused with
  the set named, undo/redo, edit and pick a row, Esc, save / close / reopen / edit),
  `fillet2_chord.py` (Chord Length 3 on a 90° and a 120° edge of one set, measured on the
  part; the arrow drags the chord; too big refused; undo/redo; edit), `fillet2_variable.py`
  (start / end radius, a point added by clicking the edge, its position and radius typed,
  Add Point and ✕, a point's arrow dragged, Enter in its value box; radii 1 / 3 / 1.5
  measured; save / reopen / edit; an end radius of 0 refused), `fillet2_rule.py` (Rule
  Fillet All Edges of the Extrude picked in the timeline; Rounds off refused with the
  reason; a hole drawn later in its sketch gets rounded rims; edit the radius),
  `fillet2_full_round.py` (a rib's end and a bar's end as two full rounds, a top face
  refused, undo/redo, edit, ✕ of a row, Esc), `fillet2_chamfer.py` (chamfer sets: Equal and
  Distance and Angle with Flip, measured; greyed corner types; edit each row; Cancel),
  `fillet2_chain.py` (Tangent Chain on / off on a slot, Variable on a closed chain refused,
  Variable with Tangent Chain off, G2 / Setback greyed), `fillet2_component.py` (two sets on
  a body inside a component made by Extrude > New Component), `fillet2_edit_later.py` (a
  plain fillet with a chamfer after it edited to two sets: the step changes kind in place,
  the chamfer keeps its edge, one undo step; Press Pull on set 2's round edits its radius).
- Part 2 golden models (`sciforge/ai/ops/fillet2_ops.py`: ops `fillet_sets`, `rule_fillet`,
  `full_round`, `blend_radius_expect`): `fillet2_two_sets` (saved and reopened),
  `fillet2_chord_90_120`, `fillet2_variable_points` (radius read off the part at 3 places),
  `fillet2_tangent_chain_off`, `fillet2_sets_tangent_chain_each`, `fillet2_rule_all_edges`,
  `fillet2_rule_between_follows_edit` (the boss is made wider after the rule fillet),
  `fillet2_full_round_rib`,
  `fillet2_chamfer_sets_angle_flip`, `fillet2_presspull_set_radius` (Press Pull on set 2's
  round): analytic; `fillet2_face_and_its_edge_in_two_sets` (a face in set 1, one of its
  edges in set 2: measured against FreeCAD's own Part Fillet with the same radii).
- Part 2 unit tests: `SciForgeTests/unit/test_fillet_core.py` (chord to radius, the variable
  law and how a chain is cut at its points, rounds / fillets, Distance and Angle as two
  distances, full round, the settings).

## Lessons for other dialogs

- **A document made and closed while a dialog's undo step is open can end that step.** The
  dialog's `doc.openTransaction(...)` also sets the application's active transaction; a
  throw-away document that then changes joins it, and closing that document ended the
  transaction for every document: the dialog's step was committed half-way and FreeCAD
  opened a "Delete" step of its own for the rest (Ctrl+Z after OK left the old fillet
  behind). Set `UndoMode = 0` on a throw-away document right after making it.
- **A check box without text toggles only on its tick square**: a test (or a person) that
  clicks the middle of a wide one does nothing (`fillet2_steps.click_check`).

- View-property changes (`Visibility`, `Transparency`, `Selectable`) made while a dialog's undo
  transaction is open are recorded in the undo history: a Ctrl+Z / Ctrl+Y replays them. Use
  PartDesign's `ViewObject.makeTemporaryVisible()` and Coin node fields instead, and put them
  back exactly.
- FreeCAD lets Ctrl+Z run while a task dialog is open; it commits and undoes the dialog's own
  transaction. Watch `slotUndoDocument` / `slotRedoDocument` and end the dialog.
- Esc pressed over the 3D view does not reach a SciForge task dialog (FreeCAD only handles Esc
  when the task panel has the focus): listen for `SoKeyboardEvent` on the view.
- A failing PartDesign recompute prints "Label: reason" to the Report view. Check first with a
  kernel call (`shape.makeFillet`), and mute the console observers around the preview recompute.
- A see-through shape that shares faces with an opaque one flickers (z-fighting): raise the
  opaque view provider's own `SoPolygonOffset` (a node added at the root is overridden).
- **FreeCAD's number box (`Gui::QuantitySpinBox`, `taskui.DistanceField`) reads a number
  without a unit in the unit it is *showing*.** Below 0.1 mm it shows micrometres, so after
  a value of 0.01 mm the next "1.5" typed became 1.5 µm. `blend_field.ValueField` reads the
  typed text itself (a bare number is mm). Its `autoNormalize` swallows the first Enter
  after a sum ("2*0.25"): set the property to False.
- `QTest.mouseDClick` never releases the button: Qt then believes the left button is held,
  and a dialog that ignores keys while a handle is dragged ignored Esc. A person's
  double-click is press, release, double-click, release (`widget_input.double_click`,
  `blend_steps.timeline_double_click(title, click_first=True)`): on the timeline the first
  click also selects the step, which a dialog must cope with.
- A PartDesign feature inserted in the middle of a body (marker rolled back) or an edit that
  trims an edge breaks later dress-ups whose element name no longer resolves. Keep their
  edges as geometry before the change and find them again after it (`blend.References`).
