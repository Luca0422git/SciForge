You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Wave 4 closes the gaps listed at the end of the parity docs (`docs/sciforge/dev/remaining-gaps.md` is the survey).

## Your area: Modify, part 2 (patterns, draft, split, multi-body steps), branch `sf/modify-2`

Read the parity docs `patterns.md`, `shell-draft-scale.md`, `bodies.md`, `direct-modify.md` to the end. Build:
1. **Pattern Compute Option**: Identical / Adjust / Optimized (Fusion: Adjust recomputes each copy's extents against its new surroundings, e.g. an extrude To Object that reaches a sloped face at every copy; build Adjust by re-running the feature per instance, Optimized = Identical with speed). **Pattern on Path** start point and Distance Type (Extent / Spacing), Orientation (Identical / Path Direction), Suppress where missing. Pattern of a multi-body extrude repeats every body it changed. (Object type Components belongs to components-2.)
2. **Draft**: Fusion's Draft with **Parting Line** type (fixed plane / parting edge, Two Sides with a second angle, Symmetric), one step over several bodies.
3. **Shell** and **Scale** over several bodies in one step; Scale of sketches (Fusion scales a sketch) and non-uniform scale if missing.
4. **Split Face** / **Split Body** gaps the docs list that components-2 does not own (Split Body with several tools belongs to components-2).
5. **Move** of faces (Fusion's Move with Object type Faces, a direct edit that becomes a Move Face step), **Press Pull Offset Type** (New Offset / Modify Existing / Automatic) and Replace Face onto any surface type if OCC allows.
6. **Thicken** and **Offset Face** gaps from `direct-modify.md` / `surface.md`, if any remain small.
Scenarios `modify2_*.py` (8+ paths: a rectangular pattern with Adjust (each copy measured), pattern on a path from a start point, draft with a parting line two sides, shell of two bodies in one step, scale a sketch, move a face 5 mm, press pull offset types, edit from the timeline, undo/redo, save/reopen). Golden models for the new options. Unit tests for the Qt-free parts. Update the parity docs you touch.
