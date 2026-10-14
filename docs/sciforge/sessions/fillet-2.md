# 2026-10-14: Fillet and Chamfer, part 2 (branch `sf/fillet-2`, wave 4)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
The full behaviour spec with sources is at the top of `docs/sciforge/parity/fillet.md`.

## What was built

1. **Radius sets** (Fusion's "+" rows in the selection box): the Fillet and Chamfer dialogs
   have a "Sets" list with + / −; each set has its own edges, Radius Type and size (chamfer:
   type, distances, angle, Flip), its own arrow and value box on the canvas; all sets are one
   timeline step and one undo step. Clicking a row, dragging a set's arrow or typing in its
   value box makes that set the current one; an edge picked into another set moves there,
   and an edge picked on its own beats a face of another set that has it.
2. **Radius Type**: Constant, **Chord Length** (each edge gets R = chord / (2 sin(t/2)) at both
   of its ends, t = the turn of the faces' normals; measured 3.000 mm on a 90° and a 120°
   edge), **Variable** (start / end radius, radius points with position 0..1 and radius: a
   click on the picked edge adds one there, Add Point puts one in the widest gap, ✕ removes;
   each point has its arrow and value box; measured 1 / 3 / 1.5 at start / point / end).
3. **Tangent Chain** can be turned off, for each set (Fusion's API has it per edge set):
   OpenCASCADE always rounds the whole chain, so the material taken off along the unpicked
   chain edges is put back (cut square to the picked edge where they meet). Exact (a slot's
   straight edge alone removes 20 r² (1 − π/4)).
4. **Rule Fillet** (Type drop-down): All Edges / Between Faces/Features, two boxes of faces
   or timeline features, Rounds / Fillets; the edges are found again at every compute, so a
   hole drawn later in the picked extrude's sketch gets its rims rounded.
5. **Full Round Fillet**: click the centre face (a rib's top or end); its two side faces are
   found; the slab under it minus a cylinder of half the width is cut away (exact half
   round). "+" for more; faces that are not between flat parallel walls, do not span the
   width or whose walls are too low are refused with the reason.
6. **Chamfer sets** (Equal / Two Distances / Distance and Angle, Flip, per row); Corner Type
   Miter / Blend and fillet Setback / G2 greyed with the kernel reason.
7. SciForge's own step `PartDesign::FeaturePython` (SciForgeType `FilletSets` /
   `ChamferSets`, `sciforge/fillet_sets.py`) for everything a FreeCAD Fillet / Chamfer cannot
   hold; a one-set constant fillet stays FreeCAD's (Press Pull and the parameters table keep
   working). The dialog turns FreeCAD's step into SciForge's the moment an option needs it,
   in the same timeline place and inside its undo step (a SciForge step made simple again
   stays SciForge's); later steps stay on their edges (`blend.References` now also tracks SciForge's
   step's `Picks`). Each set's size is a property (`Size1`, `SizeB1`, `Angle1`...) so formulas
   drive it; the parameters table lists the ones in use.
8. **Press Pull** (Q) on a round of SciForge's step edits the size of the set that made it
   (Constant, Chord Length, Rule); a variable round or a full round is pushed like any face.
9. Maths in `sciforge/fillet_core.py` (no FreeCAD): chord ↔ radius, the variable law and how
   a chain is cut at its points, rounds / fillets, Distance and Angle as two distances,
   full round radius, the settings (JSON on the step). 23 unit tests.

## FreeCAD 1.1 / OpenCASCADE findings (worth copying into MEMORY.md)

- FreeCAD's Python `Shape.makeFillet(r1, r2, edges)` gives every edge the same radii; a
  radius per edge (one `BRepFilletAPI_MakeFillet` run, so corners where sets meet blend
  properly) is only reachable through a `Part::Fillet` feature (`Edges = [(index, r1, r2)]`;
  `Part::Chamfer` likewise). SciForge runs one in a hidden throw-away document
  (`App.newDocument(name, label, True, True)`), opened and closed per compute (~20 ms); a
  hidden temp document does not even become the active one.
- **A document made and closed while a dialog's transaction is open ends that transaction**
  if it joined it (`doc.openTransaction` also sets the application's active transaction):
  the dialog's step was committed half-way and FreeCAD opened its own "Delete" step for the
  rest (Ctrl+Z after OK left the old fillet). `UndoMode = 0` on the throw-away document.
- The throw-away document's element names are references into its own string table and
  carry its object's tag (a new number each time): later steps lost their edge at every
  compute. `UseHasher = False` on the throw-away document keeps the names in plain text;
  replacing its input object's tag (`:H<hex>`) by the real input shape's tag gives names
  like FreeCAD's own makeFillet's: stable, and a really lost edge is still reported.
  `TopoShape.mapShapes(generated, modified)` from Python produced no names at all in tests.
- `BRepFilletAPI_MakeFillet` with a radius pair per edge of one contour runs one smooth law
  through all the values (not straight per edge): a 1 → 3 piece measured 2.134 at its middle.
  A two-radius edge is not linear either (volume 18.95 vs 18.60 for a straight law).
- `shape.generalFuse([Part.Vertex(p)])` puts a vertex into an edge without touching faces:
  the way to give one edge several radius points.
- OpenCASCADE always rounds the whole tangent chain (`Add(E)` builds the contour); listing
  one edge of a slot's top rounded the whole loop.
- A full round by filleting both edges with r = half the width fails ("command not done"),
  r slightly smaller leaves a sliver face; slab minus cylinder is exact.
- Three rounds at a box corner: one spherical corner face (rolling ball); three chamfers:
  one triangular face. No setback, miter or blend corners in OpenCASCADE's builders.
- A `QCheckBox` without text toggles only on its tick square (a click in its middle does
  nothing): `fillet2_steps.click_check`.
- Enter in an arrow's value box finishes the command (Fusion): a scenario that types there
  and wants the dialog to stay open must not press Enter.

## Gaps left, and why (details: parity/fillet.md, Known gaps)

- Continuity G2, Corner Type Setback, Radius Type Asymmetric, Chamfer corners Miter / Blend:
  OpenCASCADE has no such blends (needs kernel work, outline 9.2).
- Full Round of a curved rib or with tangent centre faces: refused with the reason.
- Radius points take plain numbers (no formulas); no dot is drawn under the mouse on the
  edge before a radius point is clicked; Press Pull on a variable round or a full round
  pushes the face (no single size to edit).
- Rule Fillet: Fusion's exact rule for features changed by later steps is undocumented.

## Small changes in other areas (for the merger)

- `timeline_core.KIND_BY_SCIFORGE_TYPE` and `bodies_gui.ICONS`: `FilletSets` / `ChamferSets`.
- `parameters.SCIFORGE_PROPS`: the set sizes of SciForge's fillet / chamfer step.
- `blend.References`: also SciForge's step (`Picks`).
- `presspull_core.owning_fillet(body, face, sciforge=False)` (the dialog passes True) and
  `presspull_ui._start_blend_edit(blend, face)`: Press Pull on a round of SciForge's step.
- Golden: `golden/fillet2_ops.py` (ops `fillet_sets`, `rule_fillet`, `full_round`,
  `blend_radius_expect`), `schema.py` (a new `validate` wrapper at the end: mind the merge
  trap in MEMORY's handoff), `builder.py` (one import line; `press_pull` with `fillet_face`
  also edits a set of SciForge's step).

## Tests (final runs at the end of this file)

All runs on real FreeCAD 1.1.4 under xvfb, one scenario at a time
(`tools/sciforge/run_tests.sh --scenario NAME`).

| Run | Result |
|---|---|
| `fillet2_sets` (two sets with "+", each set's arrow and value box, one step, one undo / redo, edit from the timeline, a set too big explained, Esc, save / reopen and edit) | PASS, 56 checks |
| `fillet2_chord` (Chord Length on a 90° and a 120° edge, measured) | PASS, 30 checks |
| `fillet2_variable` (start / end and a radius point by clicking the edge, Add Point, ✕, measured 1 / 3 / 1.5) | PASS, 40 checks |
| `fillet2_rule` (All Edges, Between Faces/Features, Rounds / Fillets, a hole drawn later gets rounded) | PASS, 30 checks |
| `fillet2_full_round` (a rib's top, the end of a wall, refused faces with the reason) | PASS, 28 checks |
| `fillet2_chamfer` (chamfer sets: Equal, Distance and Angle with Flip, measured; greyed corners; Cancel) | PASS, 37 checks |
| `fillet2_chain` (Tangent Chain on / off per set on a slot; Variable on a closed chain refused; G2 / Setback greyed) | PASS, 33 checks |
| `fillet2_component` (two sets on a body inside a component) | PASS, 23 checks |
| `fillet2_edit_later` (FreeCAD's fillet with a chamfer after it edited into two sets; undo / redo; Press Pull on set 2's round) | PASS, 26 checks |
| Part 1 scenarios `fillet`, `fillet_chain`, `fillet_chamfer`, `fillet_qa_more` | PASS: 67, 14, 48, 93 checks |
| Press Pull scenarios `presspull`, `extrude_presspull_qa2`, `extrude_presspull_qa3`, `misc_compute` (Press Pull code touched) | PASS: 53, 78, 75, 14 checks |
| `--only base`: unit tests | 926 run, OK (23 new in `test_fillet_core.py`) |
| `--only base`: golden models | 350 pass, 1 xfail (`plate_hole_grid`, known before this branch); all 11 `fillet2_*` pass |
| `--only base`: smoke + journey | PASS (71 + 25 checks) |

Last-minute fix found by a headless edge-case run (a face in set 1 and one of its edges in
set 2): the face's set took the edge. Now an edge picked on its own wins, for fillets and
chamfers (golden `fillet2_face_and_its_edge_in_two_sets`, same volume as FreeCAD's own
Part Fillet with those radii). `fillet2_chain`, `fillet2_chamfer`, `fillet2_chord` and
`fillet2_component` were run again after it: PASS, 33, 37, 30 and 23 checks (the other
fillet scenarios above started after the fix; the Press Pull ones ran just before it, on
code it does not touch).

Headless checks (freecadcmd, not part of the suite): a formula on `Size2` ("1 mm * 2")
drives set 2 (volume exact), survives save / reopen, and typing a value after clearing it
works; twelve edge cases (sets meeting at a corner, Variable with two edges / a face / a
circle refused, Chord Length on a face and a circle's rim, Distance and Angle on a face,
an angle past 90° refused, Rule Between Faces, Full Round on a box top refused, Tangent
Chain off with no chain, set 2 too big named) gave the expected volume or refusal.
