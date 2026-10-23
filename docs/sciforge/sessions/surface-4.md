# Session log: surface-4, SURFACE MODIFY on surface bodies (wave 6, branch `sf/surface-4`, 2026-10-23)

Brief: `docs/sciforge/dev/briefs/surface-4.md`. Parity doc (behaviour spec with sources,
how it works, known gaps): `docs/sciforge/parity/surface-modify.md`.

## What was built

The SOLID tools Fusion repeats on its SURFACE tab now work on surface bodies, and Merge is
new (all in one undo step, a timeline step with edit, saved with the design):

| Command | How |
|---|---|
| Split Body | a surface body as the Splitting Tool (a click on its face takes the whole body; Extend Splitting Tool carries on only the open edges that touch or run inside the body, so a smaller surface still cuts the solid in two and a twisted loft whose edges lie outside is not curled back into it); a surface body can be split (its pieces are surface bodies) |
| Delete | on the SURFACE tab faces go without healing (step `SurfaceDeleteFace`; a solid, also a STEP part without history, becomes a surface body); SOLID heals as before; faces of a surface body never heal |
| Fillet / Chamfer | new steps `SurfaceFillet` / `SurfaceChamfer` (Radius Type Constant / Chord Length / Variable; Equal / Two Distances / Distance and Angle + Flip; Tangent Chain; drag arrow + value box); F and SOLID's Fillet / Chamfer hand over when the picks are on a surface body (or nothing is picked on the SURFACE tab); a solid's edge clicked in the surface dialog goes back to the SOLID dialog |
| Press Pull (Q) | step `SurfacePressPull`. A flat face of a surface body moves along its normal: among flat polygons its corners slide along the edges leaving them (slanted walls follow exactly); faces running along the move grow or are cut back; neighbours at an angle (a cone under a lid) are carried on along their own surface or cut back and the lid is rebuilt in the moved plane; several flat faces facing different ways (two walls of a box or tray) each move along their own normal; one curved face is offset (a cup's wall, the floor follows). An edge of a surface body opens its Fillet; a surface fillet's face opens that fillet |
| Move/Copy, Align, Scale | the steps accept a body with faces (no solid needed); Move Object Faces moves flat faces of a surface body (the faces round them follow) |
| Pattern (Rect / Circ / Path), Mirror | bodies of type Bodies; a surface pick switches Pattern Type to Bodies; Mirror Join stitches the copy on with a Stitch Tolerance (dialog row, default 1 mm, kept on edit) |
| Merge (ribbon entry wired) | `SciForge_SurfaceMerge`: adjacent faces on one surface become one face (`UnifySameDomain`); faces that meet smoothly are refitted as one surface (filling through their boundary and sample points, refused when it moves them more than 0.01 mm / 0.1 %); a sharp edge is refused with the reason (step `SurfaceMerge`). Works in a design without history too (where Fusion offers it) |
| Split Face, Replace Face | the SOLID steps take a surface body: Split Face divides its faces and sews them back (Merge joins them again); Replace Face moves one face onto a flat target, the faces round it carried on or cut back |
| Parameters | the surface dialogs' Radius / Distance fields take parameters and formulas (expressions on the step) |
| Combine, Silhouette Split | a surface body refused with a clear reason (Stitch / Thicken / Split Face) |
| Physical Material | lists surface bodies under In This Design |

New files: `sciforge/surfmod_core.py` (rules, unit tested), `sciforge/surfmod.py` (geometry +
`SurfaceModifyFeature`, saved as `sciforge.surfmod.SurfaceModifyFeature`: never rename),
`sciforge/surfmod_ui.py` (dialog on `pickpanel.PickPanel`, hand-overs, Merge command,
`ViewProviderSurfaceModify`), `tools/sciforge/icons_surface4.py` (5 icons `surfmod_*`),
`SciForgeTests/gui/surface4_steps.py`, 16 scenarios `surface4_*`, 20 golden models
`surface4_*`, `SciForgeTests/unit/test_surfmod_core.py`.

Shared files touched (small, each marked "surface-4"): `split.py`, `split_ui.py`,
`split_face.py`, `replace_face.py`, `move_face.py`, `delete.py`, `delete_ui.py`, `fillet_ui.py`,
`presspull_ui.py`, `move.py`, `align.py`, `scale.py`, `scale_ui.py`, `pattern.py`,
`pattern_ui.py`, `combine.py`, `silhouette.py`, `material_ui.py`, `ribbon_config.py` (the
Merge line only), `ai/ops/bodies_ops.py` (`measure_bodies` measures a surface body's faces),
the `# --- surface-4 ---` blocks in `ai/ops/surface3_ops.py` and
`SciForgeTests/golden/surface3_schema.py` (appended to the scaffold, right after its
header). No FreeCAD core change.

## FreeCAD / OpenCASCADE facts found (probed in FreeCAD 1.1.4)

- `PartDesign::Fillet` on a body whose base is a shell: Invalid, "Base feature's shape is not
  a solid". `shell.makeFillet(r, edges)` / `makeChamfer(d, edges)` / `makeChamfer(d1, d2,
  edges)` work, but return a **Compound of loose faces**: sew them again
  (`surface_geom.sew`) to keep one shell. A free edge (one face) fails with "BRep_API: command
  not done"; refuse it before. `makeFillet(r1, r2, edges)` is a radius changing evenly from
  each edge's start to its end; there is no chord-length law in the Python API.
- `ShapeUpgrade.UnifySameDomain(shape, UnifyEdges, UnifyFaces, ConcatBSplines)`: the third
  argument must be True to merge faces (passing False silently merged nothing). Never run it
  on a whole body after a change: it also merges faces the user split on purpose.
- `shell.defeaturing(faces)` refuses shells (`BOPAlgo_AlertTooFewArguments`): delete without
  healing = sew the remaining faces.
- `BOPTools.SplitAPI.slice(solid, [shell])` splits a solid by an open shell; slicing a shell
  by a plane gives a compound of shells (`surface_geom.shells_or_faces` lists the pieces).
- Carrying a twisted loft's edges on (`surface_geom.extend`, Natural or Tangent) curls the new
  parts back into a box it already crosses: a split then cut two extra slivers off. Only
  edges inside the body are carried on now.
- `surface_geom.extend` grows a cone / cylinder face exactly only when it has 4 edges; a full
  round face (3 edges: two circles and the seam) gets Tangent BSpline bands, whose
  `BoundBox` is loose (`optimalBoundingBox()` is tight). `surface.toShape(u0, u1, v0, v1)`
  on the face's own parameter rectangle grows it exactly (`surfmod._carry_on`); a cone's
  apex is at v = -Radius / sin(SemiAngle).
- A cone's seam line ends on its top circle: picking "the edge through a point of the
  circle" at the seam's end finds the seam; pick another point of the circle.
- `surface_geom.away_in_face` points OUT of the face (into = its negative).
- Black (the installed version) reformats a few old lines of shared files (a blank line after
  a module docstring, a long `if (...)`): never run black on a whole shared file; only lint.
- In the iso view an open box's floor is hidden near its front and right walls: click floor
  points near the back-left (y > depth / 2, x < width - height).
- The XZ origin plane's normal is -Y: a surface extruded from an XZ sketch goes to y < 0, a
  sketch offset +5 on it lies at y = -5.

## Tests (all with FreeCAD 1.1.4 in the sandbox)

SCENARIO_RESULTS

## Gaps (details and evidence in the parity doc)

Press Pull of a face next to a tangent face (a floor next to a fillet: Fusion lets the
fillet follow), of several curved faces, of a curved face with a tangent neighbour, of faces
facing different ways that are not among flat polygons; Replace Face onto a curved target
or of several faces at once; Merge of faces that meet at a sharp edge (faces that meet
smoothly are refitted); surface Fillet's Variable-with-points, G2, Setback and Rule options;
Merge offered with history on (Fusion hides it); a surface body's steps are not baked into
a Base Feature when history is off (`direct.freeze` bakes solids only).
