# Session log: surface-4, SURFACE MODIFY on surface bodies (wave 6, branch `sf/surface-4`, 2026-10-23)

Brief: `docs/sciforge/dev/briefs/surface-4.md`. Parity doc (behaviour spec with sources,
how it works, known gaps): `docs/sciforge/parity/surface-modify.md`.

## What was built

The SOLID tools Fusion repeats on its SURFACE tab now work on surface bodies, and Merge is
new (all in one undo step, a timeline step with edit, saved with the design):

| Command | How |
|---|---|
| Split Body | a surface body as the Splitting Tool (a click on its face takes the whole body; Extend Splitting Tool carries its open edges on so a smaller surface still cuts the solid in two); a surface body can be split (its pieces are surface bodies) |
| Delete | on the SURFACE tab faces go without healing (step `SurfaceDeleteFace`; a solid becomes a surface body); SOLID heals as before; faces of a surface body never heal |
| Fillet / Chamfer | new steps `SurfaceFillet` / `SurfaceChamfer` (Radius Type Constant / Variable; Equal / Two Distances / Distance and Angle + Flip; Tangent Chain; drag arrow + value box); F and SOLID's Fillet / Chamfer hand over when the picks are on a surface body (or nothing is picked on the SURFACE tab) |
| Press Pull (Q) | a flat face of a surface body moves along its normal: among flat polygons its corners slide along the edges leaving them (slanted walls follow exactly), else the faces running along the move grow or are cut back (step `SurfacePressPull`); an edge of a surface body opens its Fillet; a surface fillet's face opens that fillet |
| Move/Copy, Align, Scale | the steps accept a body with faces (no solid needed) |
| Pattern (Rect / Circ / Path), Mirror | bodies of type Bodies; a surface pick switches Pattern Type to Bodies; Mirror Join stitches the copy on with a Stitch Tolerance (dialog row, default 1 mm, kept on edit) |
| Merge (ribbon entry wired) | `SciForge_SurfaceMerge`: adjacent faces on one surface become one face (`UnifySameDomain`); faces that meet smoothly are refitted as one surface (filling through their boundary and sample points, refused when it moves them more than 0.01 mm / 0.1 %); a sharp edge is refused with the reason (step `SurfaceMerge`) |
| Parameters | the surface dialogs' Radius / Distance fields take parameters and formulas (expressions on the step) |
| Combine, Silhouette Split | a surface body refused with a clear reason (Stitch / Thicken / Split Face) |
| Physical Material | lists surface bodies under In This Design |

New files: `sciforge/surfmod_core.py` (rules, unit tested), `sciforge/surfmod.py` (geometry +
`SurfaceModifyFeature`, saved as `sciforge.surfmod.SurfaceModifyFeature`: never rename),
`sciforge/surfmod_ui.py` (dialog on `pickpanel.PickPanel`, hand-overs, Merge command,
`ViewProviderSurfaceModify`), `tools/sciforge/icons_surface4.py` (5 icons `surfmod_*`),
`SciForgeTests/gui/surface4_steps.py`, 7 scenarios `surface4_*`, 8 golden models
`surface4_*`, `SciForgeTests/unit/test_surfmod_core.py`.

Shared files touched (small, each marked "surface-4"): `split.py`, `split_ui.py`,
`delete.py`, `delete_ui.py`, `fillet_ui.py`, `presspull_ui.py`, `move.py`, `align.py`,
`scale.py`, `scale_ui.py`, `pattern.py`, `pattern_ui.py`, `combine.py`, `silhouette.py`,
`material_ui.py`, `ribbon_config.py` (the Merge line only), `ai/ops/bodies_ops.py`
(`measure_bodies` measures a surface body's faces), the `# --- surface-4 ---` blocks at the
end of `ai/ops/surface3_ops.py` and `SciForgeTests/golden/surface3_schema.py`. No FreeCAD core
change.

## FreeCAD / OpenCASCADE facts found (probed in FreeCAD 1.1.4)

- `PartDesign::Fillet` on a body whose base is a shell: Invalid, "Base feature's shape is not
  a solid". `shell.makeFillet(r, edges)` / `makeChamfer(d, edges)` / `makeChamfer(d1, d2,
  edges)` work, but return a **Compound of loose faces**: sew them again
  (`surface_geom.sew`) to keep one shell. A free edge (one face) fails with "BRep_API: command
  not done"; refuse it before.
- `ShapeUpgrade.UnifySameDomain(shape, UnifyEdges, UnifyFaces, ConcatBSplines)`: the third
  argument must be True to merge faces (passing False silently merged nothing).
- `shell.defeaturing(faces)` refuses shells (`BOPAlgo_AlertTooFewArguments`): delete without
  healing = sew the remaining faces.
- `BOPTools.SplitAPI.slice(solid, [shell])` splits a solid by an open shell; slicing a shell
  by a plane gives a compound of shells (`surface_geom.shells_or_faces` lists the pieces).
- `surface_geom.away_in_face` points OUT of the face (into = its negative).
- Black (the installed version) reformats a few old lines of shared files (a blank line after
  a module docstring, a long `if (...)`): never run black on a whole shared file; only lint.
- In the iso view an open box's floor centre is hidden by its front wall: click floor points
  near the back (y > depth / 2, x < width - height).
- The XZ origin plane's normal is -Y: a surface extruded from an XZ sketch goes to y < 0.

## Tests (all with FreeCAD 1.1.4 in the sandbox)

- Scenarios: surface4_fillet PASS (45), surface4_split PASS (25), surface4_delete_merge PASS
  (48), surface4_presspull PASS (46), surface4_move_mirror PASS (41), surface4_pattern PASS
  (27), surface4_misc PASS (28), surface4_component PASS (24).
- Regression (scenarios of the tools touched, all PASS): bodies_combine, bodies_delete,
  bodies_move, bodies_split, split_preview, extrude_presspull_presspull, modify2_presspull_type,
  fillet, fillet_chamfer, fillet2_chamfer, patterns_rect, patterns_circ, patterns_mirror,
  fixpattern_mirror, shell_draft_scale, modify2_scale, modify_align, modify_silhouette,
  misc_materials, surface_stitch, surface_misc.
- Golden: the 12 `surface4_*` models pass; the full golden run 448 pass, 2 xfail (old
  upstream bugs) before the last two models were added.
- Unit: all OK (16 new in test_surfmod_core.py).

## Gaps (details and evidence in the parity doc)

Press Pull of a curved face, or of a flat one whose curved neighbours meet it at an angle (no
per-face offset of an open shell in OpenCASCADE's Python API; flat polygons are handled by
sliding the corners); Merge of faces on different surfaces (Fusion refits them); surface Fillet's Chord Length,
Variable-with-points, G2, Setback and Rule options; Merge offered with history on (Fusion hides it).
