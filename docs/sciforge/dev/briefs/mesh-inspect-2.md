You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Wave 5 closes more of the gaps in `docs/sciforge/dev/remaining-gaps.md` (read it).

## Your area: Mesh and Inspect, part 2, branch `sf/mesh-inspect-2`

Read `docs/sciforge/parity/mesh.md`, `inspect.md` and `inspect-analysis.md` to the end, and the MESH and inspect session logs in MEMORY.md. Build:
1. **Mesh**: Fusion's Direct Edit environment for meshes (select triangles / face groups by brush or box, delete, move, smooth a region, finish), Create Face Group and Combine Face Groups, mesh steps that roll back with the timeline marker like other steps.
2. **Inspect**: Interference with Create Bodies (the overlaps as new bodies), Measure's Component selection filter, the analyses on mesh bodies where Fusion allows them, Include Sharp Curves (Curvature Comb), and the other small gaps the three docs list.
Scenarios `meshinspect2_*.py` (8+ paths: brush-select triangles and delete them, move a face group, smooth a region, create and combine face groups, the marker rolled before a mesh step, interference bodies created (volume checked), measure between two components with the filter, zebra on a mesh, undo/redo, save/reopen). Unit tests for the Qt-free parts. Update the parity docs.
