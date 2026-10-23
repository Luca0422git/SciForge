You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: SURFACE part 4, the MODIFY tools on surface bodies, and Merge, branch `sf/surface-4`

Fusion's behaviour: `docs/sciforge/dev/research/fusion-surface.md`; the audit with file:line
evidence and kernel probes: `docs/sciforge/dev/research/surface-gaps.md`. Read
`docs/sciforge/parity/surface.md`, `bodies.md`, `direct-modify.md`, `fillet.md`, `patterns.md`
to the end. The SURFACE tab's MODIFY menu (`ribbon_config.py`, `SURFACE_MODIFY`, lines marked
`# owner: surface-4`) already lists the SOLID tools Fusion repeats there; today most refuse a
surface body. surface-3 owns the `surface*` files (do not edit them; call their public
functions, e.g. `surface.is_surface_body`, `surface_geom.unstitch`); put new code in
`surfmod_*.py` files and in the tool files below.

Make these work on surface bodies (Fusion's SURFACE > MODIFY), each a timeline step with edit,
undo/redo, save/reopen, refusals with the reason, and without changing what they do to solids
(re-run those tools' existing scenarios):
- #1 **Split Body** with a surface body as the Splitting Tool (the classic hybrid workflow:
  cut a solid with a sculpted surface), and splitting surface bodies (`split.py`).
- #2 **Delete** on the SURFACE tab: faces removed without healing (Fusion's
  SurfaceDeleteFaceFeature; a solid becomes a surface body at the first deleted face). On the
  SOLID tab Delete keeps healing (`delete.py`); decide by the tab the command came from, as
  Fusion does, and say how in the parity doc.
- #4 **Fillet / Chamfer** on edges of surface bodies (`fillet_ui.py`; the kernel's
  makeFillet / makeChamfer work on open shells: the audit's probes).
- #5 **Move/Copy** and **Align** of surface bodies (`move.py`, `align.py`).
- #6 **Pattern** (Rectangular / Circular / on Path) and **Mirror** of surface bodies; Mirror
  Operation Join stitches the copies with a Stitch Tolerance (`pattern.py`, `pattern_ui.py`).
- #10 **Scale** of surface bodies (`scale.py`).
- #16 **Press Pull** on surface faces (offset the face, the neighbours follow) and edges (to
  Fillet), where the kernel allows; refuse the rest with the reason (`presspull.py`).
- #23 **Merge** (Fusion: direct-modeling designs only; merges adjacent faces of one surface
  body into one face): wire the `Merge` ribbon entry (`None` today) to your command.
- Combine, Silhouette Split, Physical Material, Appearance with surface bodies: check each and
  fix what refuses.
Scenarios `surface4_*.py` (8+ paths: split a solid with a lofted surface, delete a face of a
surface box, fillet two stitched surfaces' edge, move/copy and mirror-join a surface, scale,
press pull a surface face, merge, edit from the timeline, undo/redo, save/reopen, a refusal),
golden models (put your steps in `surface3_ops.py` only by appending at the end in a block
headed `# --- surface-4 ---`, and your checks in `surface3_schema.py` the same way), unit
tests. Add a "SURFACE MODIFY on surface bodies" section to `docs/sciforge/parity/surface.md`
ONLY as a new file `docs/sciforge/parity/surface-modify.md` (surface-3 owns surface.md).
