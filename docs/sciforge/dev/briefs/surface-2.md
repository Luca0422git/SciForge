You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Wave 5 closes more of the gaps in `docs/sciforge/dev/remaining-gaps.md` (read it).

## Your area: Surface and Loft, part 2, branch `sf/surface-2`

Read `docs/sciforge/parity/surface.md` and `sweep-loft-rib.md` to the end and the SURFACE session log in MEMORY.md. Build:
1. **Surface Extrude** From Object / All / Through All / To Object, **Surface Revolve** Type To, **Surface Sweep** with a guide rail, taper and twist, **Surface Loft** with rails, a centerline and end conditions (Free / Direction / Tangent / Curvature where OCC allows; Curvature continuity needs core patch #14, which is in full build #6).
2. **Solid Loft**: Tangent Edges Merge, end conditions together with rails / a centerline / a closed loft, rails that are edges of bodies.
3. Any other gap the two parity docs list that is small: do them; list the rest with the reason.
Scenarios `surface2_*.py` (8+ paths: a surface extrude From Object, a surface revolve To a plane, a surface sweep with a rail and a twist, a surface loft with two rails and a tangent end, a solid loft with tangent edges merged, a loft with a centerline and an end direction, edit from the timeline, undo/redo, save/reopen). Golden models for each new option; unit tests for the Qt-free parts. Update the parity docs.
