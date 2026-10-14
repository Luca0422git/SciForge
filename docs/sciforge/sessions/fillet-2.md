# 2026-10-14: Fillet and Chamfer, part 2 (branch `sf/fillet-2`, wave 4)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
The full behaviour spec with sources is at the top of `docs/sciforge/parity/fillet.md`.

## What was built

1. **Radius sets** (Fusion's "+" rows in the selection box): the Fillet and Chamfer dialogs
   have a "Sets" list with + / −; each set has its own edges, Radius Type and size (chamfer:
   type, distances, angle, Flip), its own arrow and value box on the canvas; all sets are one
   timeline step and one undo step. Clicking a row, dragging a set's arrow or typing in its
   value box makes that set the current one; an edge picked into another set moves there.
2. **Radius Type**: Constant, **Chord Length** (each edge gets R = chord / (2 sin(t/2)) at both
   of its ends, t = the turn of the faces' normals; measured 3.000 mm on a 90° and a 120°
   edge), **Variable** (start / end radius, radius points with position 0..1 and radius: a
   click on the picked edge adds one there, Add Point puts one in the widest gap, ✕ removes;
   each point has its arrow and value box; measured 1 / 3 / 1.5 at start / point / end).
3. **Tangent Chain** can be turned off: OpenCASCADE always rounds the whole chain, so the
   material taken off along the unpicked chain edges is put back (cut square to the picked
   edge where they meet). Exact (a slot's straight edge alone removes 20 r² (1 − π/4)).
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
   working). The dialog swaps one for the other in the same timeline place inside its undo
   step; later steps stay on their edges (`blend.References` now also tracks SciForge's
   step's `Picks`). Each set's size is a property (`Size1`, `SizeB1`, `Angle1`...) so formulas
   drive it; the parameters table lists the ones in use.
8. Maths in `sciforge/fillet_core.py` (no FreeCAD): chord ↔ radius, the variable law and how
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
- Radius points take plain numbers (no formulas); Press Pull edits only FreeCAD's own fillet.
- Rule Fillet: Fusion's exact rule for features changed by later steps is undocumented.

## Small changes in other areas (for the merger)

- `timeline_core.KIND_BY_SCIFORGE_TYPE` and `bodies_gui.ICONS`: `FilletSets` / `ChamferSets`.
- `parameters.SCIFORGE_PROPS`: the set sizes of SciForge's fillet / chamfer step.
- `blend.References`: also SciForge's step (`Picks`).
- Golden: `golden/fillet2_ops.py` (ops `fillet_sets`, `rule_fillet`, `full_round`,
  `blend_radius_expect`), `schema.py` (a new `validate` wrapper at the end: mind the merge
  trap in MEMORY's handoff), `builder.py` (one import line).

## Tests (final runs at the end of this file)
