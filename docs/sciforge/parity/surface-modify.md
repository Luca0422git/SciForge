# Parity spec: SURFACE MODIFY on surface bodies (wave 6, surface-4)

The SOLID tools that Fusion repeats on its SURFACE tab now work on **surface bodies** (a
body whose result has faces and no solid, `surface.is_surface_body`), and Merge is new.
Built on branch `sf/surface-4` (2026-10-23). Not yet signed off by Luca.

Code (all under `src/Mod/SciForge/sciforge/`):

- `surfmod_core.py`: the rules, pure Python (kinds, defaults, value checks, the Delete tab
  rule, the Press Pull neighbour rule, the Merge verdict). Unit tested.
- `surfmod.py`: the geometry and the steps (`SurfaceModifyFeature`, one class for the five
  new step kinds), plus the helpers the SOLID tools call for surface bodies
  (`body_has_faces`, `extended_tool`, `open_pieces`, `stitch_join`).
- `surfmod_ui.py`: the dialog (`SurfaceModifyPanel`, on `pickpanel.PickPanel` like Shell and
  Draft), the hand-over functions the SOLID commands call, the Merge command.
- Small changes in the SOLID tool files (each marked "surface-4" in a comment): `split.py`,
  `split_ui.py`, `delete.py`, `delete_ui.py`, `fillet_ui.py`, `presspull_ui.py`, `move.py`,
  `align.py`, `scale.py`, `scale_ui.py`, `pattern.py`, `pattern_ui.py`, `combine.py`,
  `silhouette.py`, `material_ui.py`; the ribbon's Merge entry; the golden ops block at the
  end of `ai/ops/surface3_ops.py` and its schema block at the end of
  `SciForgeTests/golden/surface3_schema.py`; `ai/ops/bodies_ops.py` measures surface bodies.

## Behaviour spec (researched before building)

**A** = Autodesk (help pages H-MOD "Modify a surface" SFC-MODIFY-SURFACE, H-FILCH
SFC-FILLET-CHAMFER, H-MIRROR SLD-REF-MIRROR-DIALOG, H-MERGE SFC-MERGE; the API reference
pages `SurfaceDeleteFaceFeatures`, `DeleteFaceFeatures`, `MirrorFeatureInput.stitchTolerance`,
`Features.mergeFacesFeatures`, `OffsetFacesFeatures` and the API stub `adsk/fusion.py`; full
keys in `docs/sciforge/dev/research/fusion-surface.md`), **F** = Autodesk Community forum
([Filleting two intersecting surfaces](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/filleting-two-intersecting-surfaces-in-the-patch-environment/m-p/6698674),
[Delete face](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/delete-face/idc-p/6453888),
[Merge surfaces](https://forums.autodesk.com/t5/fusion-design-validate-document/merge-surfaces/m-p/9629574),
[Merge missing?](https://forums.autodesk.com/t5/fusion-design-validate-document/merge-missing/m-p/5826824),
[Offset faces command](https://forums.autodesk.com/t5/fusion-360-design-validate/offset-faces-command/m-p/8050259),
[Combine feature seems very strict](https://forums.autodesk.com/t5/fusion-support-forum/combine-feature-seems-very-strict/m-p/12522016)),
**G** = SciForge's guess (nothing found; Luca's screen captures settle it).

| Fusion | SciForge | Src |
|---|---|---|
| SURFACE > MODIFY lists Press Pull, Fillet, Chamfer, Trim, Untrim, Extend, Stitch, Unstitch, Merge, Reverse Normal, Scale, Split Face, Split Body | Same entries (the ribbon of wave 6); every one now works on surface bodies | A |
| **Split Body**: Body to Split = solid or open bodies; Splitting Tool = a body (solid or open), a plane, a profile, a face; Extend Splitting Tool | A surface body is a Splitting Tool: a click on a face of a surface body (not the body being split) takes the whole surface body. Extend Splitting Tool (on) carries its open edges on (Natural where the surface allows, else Tangent, `surface_geom.extend`) far enough to cross the body, so a sculpted surface smaller than the body still cuts it in two. A surface body can be split too: its pieces become surface bodies | A |
| Splitting a solid with a sculpted surface (the "hybrid" workflow) | Kept piece = the bigger one (as for any split); the tool body stays a surface | A, G (which piece stays) |
| **Delete** on the SURFACE tab: SurfaceDeleteFaceFeature, faces removed without healing; a solid becomes a surface body at the first deleted face. On SOLID, Delete heals (DeleteFaceFeature, fails if it cannot) | Decided by the tab Delete runs from (`ribbon.current_tab()`, read when Del / the menu runs): SURFACE removes the faces (a "Delete Face" step, `SurfaceDeleteFace`; a solid becomes a surface body), SOLID keeps healing. Faces of a surface body are never healed, whatever the tab (there is no solid to close). Every other Delete (bodies, steps, sketch curves) is unchanged | A, F; G (a surface body on the SOLID tab) |
| **Fillet / Chamfer** of edges of a surface body (Surface > Modify > Fillet / Chamfer; the SOLID dialog) | A step of its own (`SurfaceFillet` / `SurfaceChamfer`): FreeCAD's PartDesign::Fillet refuses a body that is not a solid ("Base feature's shape is not a solid", probed), OpenCASCADE's `makeFillet` / `makeChamfer` on the shell work. Radius Type Constant or Variable (Start Radius at the edge's start, End Radius at its end; `makeFillet(r1, r2)`), Chord Length greyed with the reason (fillet); Equal Distance / Two Distances / Distance and Angle with Flip (chamfer); Tangent Chain; a drag arrow with its value box | A |
| Fusion cannot fillet between two separate surface bodies: trim, Stitch, then fillet the shared edge | Same: an edge on the outside of a surface (one face) is refused: "...two separate surface bodies are stitched first (Stitch), as in Fusion" | F |
| Which command opens it | F / SOLID's Fillet or Chamfer hand over (`fillet_ui.start` -> `surfmod_ui.take_blend`) when the picked edges are on a surface body, or when nothing is picked and the SURFACE tab shows a surface body (or no solid exists at all). In that dialog a first click on a solid's edge hands it back to the SOLID Fillet / Chamfer (Fusion's Fillet rounds solids on the SURFACE tab too) | G |
| **Press Pull** (Q) on a face of a surface body: an Offset Face / Press Pull feature; the faces around follow | Press Pull hands over at the first pick on a surface body (`presspull_ui._take`). A flat face moves along its normal (+ along it). Among flat polygons (a box, a tray with slanted walls) each corner of the face slides along the edge that leaves it to the moved plane and the faces around are rebuilt with it (exact, like Fusion's offset of a face of a solid); otherwise a neighbour that runs along the move (a round or flat extruded wall) grows by a band or is cut back to the moved face. Several parallel flat faces move together. One curved face is offset (a cup's round wall: the floor grows or is cut back with it). A "Press Pull" step (`SurfacePressPull`) | A (presence), G (the neighbour rule) |
| Press Pull on a fillet's face changes the fillet | The face of a surface Fillet / Chamfer step opens that step's dialog (its size) | A (H-MOD: Press Pull resizes fillets) |
| Press Pull on an edge: Fillet | An edge of a surface body opens the surface Fillet | A |
| **Move/Copy** (M), **Align** of surface bodies | Same dialogs; the steps take a body with faces (`surfmod.body_has_faces`) instead of needing a solid. A copy of a surface body is a surface body | G (present in Fusion's menu) |
| **Pattern** (Rectangular / Circular / on Path) and **Mirror** of surface bodies, Object Type Bodies | Same dialogs. A click on a surface body sets Pattern Type to Bodies (a surface body has no features to pattern); with nothing selected and no solid, the dialog opens on the shown surface body | A |
| **Mirror, Operation Join**: the mirrored surface bodies are **stitched** to the originals with a **Stitch Tolerance** | Same: SciForge's PatternFeature stitches the copy to the body (`surface_geom.stitch`); a stitch that closes is a solid. Stitch Tolerance row (shown for a surface body with Join), default 1 mm; kept on edit | A (stitch, tolerance), G (default 1 mm) |
| **Scale** of surface bodies | Same dialog and step; uniform or per-axis. Faces that end up in one plane are merged (Refine, as for solids) | A |
| **Merge**: adjacent faces of one surface body merged into one face; only in direct modelling (Capture Design History off) or inside a base feature; "it will change the shape of the surface" | SURFACE > MODIFY > Merge: picked adjacent faces that lie on **one** surface (one plane, cylinder, ... e.g. the pieces Split Face or Trim left) become one face, exactly (`UnifySameDomain`). Faces that only meet smoothly (tangent, within 1 degree) are refitted as one surface through their outer boundary and points sampled on them; the dialog says how far it moved them (refused above 0.01 mm or 0.1 % of their size). Faces meeting at a sharp edge are refused with the reason. Offered in parametric designs too, as a "Merge" step in the timeline (Fusion hides it there) | A, F; G (the tolerances; offered with history on) |
| **Combine** | A surface body is refused with the reason: "...Combine works on solids. Join surfaces with Stitch, or make it a solid with Thicken" (the forum's workaround) | G, F |
| **Silhouette Split**: Target Body = one solid body | A surface body is refused with the reason (Split Face, or make it a solid first) | A |
| **Physical Material**, **Appearance** | Work on surface bodies (they did); the Physical Material dialog now lists surface bodies under In This Design (no mass: no volume) | G |
| Value fields take parameters and formulas | The surface dialogs' Radius / Distance fields (and the box beside the arrow) take a parameter or a formula; the step's value then follows it (an expression on the property, as the SOLID dialogs do); Change Parameters lists them | A |
| Components | Every step works in the body's own coordinates: a surface body in a moved component is filleted, pushed and deleted where it is shown | G |

## How each one works (for Luca)

- **Split a solid with a surface**: SURFACE > MODIFY > Split Body, click the solid, then click
  the curved surface. Even when the surface is smaller than the solid, Extend Splitting Tool
  makes it cut right through. OK: two bodies.
- **Delete a face of a surface**: on the SURFACE tab click the face and press Del: the face
  goes and the hole stays. The same on a solid turns it into a surface body. On the SOLID tab
  Del still closes the hole (or says why it cannot).
- **Round or bevel an edge**: click the edge between two faces of a surface body, press F
  (or MODIFY > Fillet / Chamfer), type the radius or drag the arrow, OK.
- **Push or pull a flat face**: press Q, click the face, type a distance (+ along the face's
  arrow) or drag the arrow: the walls around it grow or shrink with it.
- **Merge**: MODIFY > Merge, click faces that lie on one surface or run into each other
  smoothly, OK: one face.
- **Move, Align, Scale, Pattern, Mirror**: exactly as for solids; Mirror with Operation Join
  stitches the mirrored half on (Stitch Tolerance closes small gaps).

Every one is a step in the timeline (double-click to change it), undoes in one step and is
saved with the design.

## Tests

- Scenarios (real input, FreeCAD 1.1.4): `surface4_fillet` (fillet, edit with a parameter
  that the radius then follows, chamfer with a pre-selected edge, a free-edge refusal, Esc,
  a Variable radius fillet),
  `surface4_split` (a box split by a curved surface, undo / redo, save with Ctrl+S, reopen),
  `surface4_delete_merge` (an empty design, SURFACE Delete of a floor, of a solid's face,
  SOLID Delete still heals, edit from the timeline, Merge, a Merge refusal, a solid's edge
  handed to the SOLID Fillet),
  `surface4_presspull` (Q hand-over, -5, edit to +3, undo / redo, Q on an edge, Q on the
  fillet's face edits the fillet, a curved face offset, a too-far refusal, save with Ctrl+S,
  reopen, edit after the reopen), `surface4_move_mirror` (Mirror Join
  with stitch, edit with Stitch Tolerance, Move, Move with Create Copy, Scale),
  `surface4_pattern` (rectangular and circular patterns of a surface body, undo / redo, Esc),
  `surface4_misc` (Align, Combine refusal, Physical Material, Appearance),
  `surface4_component` (fillet, press pull and delete on a surface body in a moved
  component, undo / redo).
- Golden models `surface4_*.json` (13): fillet + edit + reopen, variable fillet, chamfer +
  SURFACE delete, press pull + edit + reopen, press pull of a tray with slanted walls, press
  pull of a cup's round wall, merge, merge of
  tangent faces (refit), split of a solid by a surface, split of a surface, rectangular
  pattern and pattern on path of a surface body, mirror join + scale.
- Unit tests: `SciForgeTests/unit/test_surfmod_core.py`.

## Known gaps

- **Press Pull** is refused with the reason when a face next to the moved one does not run
  along the move: a flat face whose curved neighbours meet it at an angle, a curved face with
  a tangent neighbour (a D-shaped wall), several curved faces at once. OpenCASCADE has no
  per-face offset of an open shell bound to Python (`BRepOffset_MakeOffset::SetOffsetOnFace`
  is not exposed: `research/surface-gaps.md`): SciForge slides the corners among flat
  polygons, offsets one curved face, and grows / trims the faces that run along the move.
- **Merge of faces that meet at a sharp edge** is refused; faces that meet smoothly are
  refitted (OpenCASCADE's filling through their boundary and sample points), not tangent to
  the faces around them along the outer boundary (it passes through that boundary).
  Fusion's own refit rules are not documented (G).
- **Surface Fillet options**: Constant and Variable (start / end radius per edge) only;
  Chord Length (no OpenCASCADE equivalent; greyed with the reason), Variable with points
  along the edge, Curvature (G2), Setback corners and Rule Fillet are not offered on surface
  bodies (their SOLID implementations build on PartDesign::Fillet / SciForge's rule fillet,
  which need a solid). Fusion's documentation does not confirm Rule Fillet on surfaces (G).
- **Merge with Capture Design History on**: Fusion hides Merge there; SciForge offers it as
  a timeline step (a deliberate difference: nothing is lost, the step can be edited).
- **Delete on the SURFACE tab of a whole solid's faces in a body without history** (a STEP
  part): it goes through the same no-heal step after the body is adopted (as SOLID's Delete
  does); not covered by a scenario.
