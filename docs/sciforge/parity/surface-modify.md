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
  `split_face.py`, `replace_face.py`, `move_face.py`,
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
| SURFACE > MODIFY lists Press Pull, Fillet, Chamfer, Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal, Merge, Replace Face, Split Face, Split Body, Silhouette Split, Scale, Combine, Move/Copy, Align, Delete, Physical Material, Appearance | Same entries (the ribbon of wave 6); every one now takes surface bodies (Combine and Silhouette Split refuse them with the reason: they need solids, as in Fusion) | A |
| **Split Body**: Body to Split = solid or open bodies; Splitting Tool = a body (solid or open), a plane, a profile, a face; Extend Splitting Tool | A surface body is a Splitting Tool: a click on a face of a surface body (not the body being split) takes the whole surface body. Extend Splitting Tool (on) carries the open edges that touch or run inside the body on (Natural where the surface allows, else Tangent, `surface_geom.extend`) far enough to cross the body, so a sculpted surface smaller than the body still cuts it in two; edges already outside the body stay as they are (carrying a twisted loft on would curl it back into the body). A surface body can be split too: its pieces become surface bodies | A |
| Splitting a solid with a sculpted surface (the "hybrid" workflow) | Kept piece = the bigger one (as for any split); the tool body stays a surface | A, G (which piece stays) |
| **Delete** on the SURFACE tab: SurfaceDeleteFaceFeature, faces removed without healing; a solid becomes a surface body at the first deleted face. On SOLID, Delete heals (DeleteFaceFeature, fails if it cannot) | Decided by the tab Delete runs from (`ribbon.current_tab()`, read when Del / the menu runs): SURFACE removes the faces (a "Delete Face" step, `SurfaceDeleteFace`; a solid becomes a surface body), SOLID keeps healing. Faces of a surface body are never healed, whatever the tab (there is no solid to close). Every other Delete (bodies, steps, sketch curves) is unchanged | A, F; G (a surface body on the SOLID tab) |
| **Fillet / Chamfer** of edges of a surface body (Surface > Modify > Fillet / Chamfer; the SOLID dialog) | A step of its own (`SurfaceFillet` / `SurfaceChamfer`): FreeCAD's PartDesign::Fillet refuses a body that is not a solid ("Base feature's shape is not a solid", probed), OpenCASCADE's `makeFillet` / `makeChamfer` on the shell work. Radius Type Constant, Chord Length or Variable (Start Radius at the edge's start, End Radius at its end; `makeFillet(r1, r2)`). Chord Length: OpenCASCADE has no chord-length fillet, so the radius comes from the angle between the two faces' normals at the edge (chord = 2 r sin(angle / 2)): exact all along where the faces meet at one angle (a box's 90 degrees: r = chord / sqrt 2), from the angle at each end (the radius changing evenly) on one edge whose angle changes; edges at different angles in one fillet are refused with the reason (fillet); Equal Distance / Two Distances / Distance and Angle with Flip (chamfer); Tangent Chain; a drag arrow with its value box | A |
| Fusion cannot fillet between two separate surface bodies: trim, Stitch, then fillet the shared edge | Same: an edge on the outside of a surface (one face) is refused: "...two separate surface bodies are stitched first (Stitch), as in Fusion" | F |
| Which command opens it | F / SOLID's Fillet or Chamfer hand over (`fillet_ui.start` -> `surfmod_ui.take_blend`) when the picked edges are on a surface body, or when nothing is picked and the SURFACE tab shows a surface body (or no solid exists at all). In that dialog a first click on a solid's edge hands it back to the SOLID Fillet / Chamfer (Fusion's Fillet rounds solids on the SURFACE tab too) | G |
| **Press Pull** (Q) on a face of a surface body: an Offset Face / Press Pull feature; the faces around follow | Press Pull hands over at the first pick on a surface body (`presspull_ui._take`). A flat face moves along its normal (+ along it). Among flat polygons (a box, a tray with slanted walls) each corner of the face slides along the edge that leaves it to the moved plane and the faces around are rebuilt with it (exact, like Fusion's offset of a face of a solid); otherwise a neighbour that runs along the move (a round or flat extruded wall) grows by a band or is cut back to the moved face. A face whose neighbours meet it at an angle (the flat lid of a cone, a lampshade) is moved with its neighbours carried on along their own surfaces (exactly for a cone, cylinder or plane; else `surface_geom.extend`) or cut back to the moved plane, and the moved face is the piece of that plane they close round; a neighbour that meets it tangentially (a fillet) is refused with the reason. Several parallel flat faces move together. Flat faces that face different ways (two walls of a box, of a tray) move together among flat polygons, each along its own normal: every corner goes where its faces' planes meet again, a corner on the open edge of a face that stays slides along that edge, the rim between two moved walls stays flat. One curved face is offset (a cup's round wall: the floor grows or is cut back with it). A "Press Pull" step (`SurfacePressPull`) | A (presence, several faces: `OffsetFacesFeatures`), G (the neighbour rule, the rim) |
| Press Pull on a fillet's face changes the fillet | The face of a surface Fillet / Chamfer step opens that step's dialog (its size) | A (H-MOD: Press Pull resizes fillets) |
| Press Pull on an edge: Fillet | An edge of a surface body opens the surface Fillet | A |
| **Move/Copy** (M), **Align** of surface bodies | Same dialogs; the steps take a body with faces (`surfmod.body_has_faces`) instead of needing a solid. A copy of a surface body is a surface body. Move Object Faces moves flat faces of a surface body (translate or turn): each face is replaced by itself moved and the faces round it are carried on or cut back, as Replace Face does (`move_face._move_open`); a curved face is refused with the reason (Press Pull offsets it) | G (present in Fusion's menu) |
| **Pattern** (Rectangular / Circular / on Path) and **Mirror** of surface bodies, Object Type Bodies | Same dialogs. A click on a surface body sets Pattern Type to Bodies (a surface body has no features to pattern); with nothing selected and no solid, the dialog opens on the shown surface body | A |
| **Mirror, Operation Join**: the mirrored surface bodies are **stitched** to the originals with a **Stitch Tolerance** | Same: SciForge's PatternFeature stitches the copy to the body (`surface_geom.stitch`); a stitch that closes is a solid. Stitch Tolerance row (shown for a surface body with Join), default 1 mm; kept on edit | A (stitch, tolerance), G (default 1 mm) |
| **Scale** of surface bodies | Same dialog and step; uniform or per-axis. Faces that end up in one plane are merged (Refine, as for solids) | A |
| **Merge**: adjacent faces of one surface body merged into one face; only in direct modelling (Capture Design History off) or inside a base feature; "it will change the shape of the surface" | SURFACE > MODIFY > Merge: picked adjacent faces that lie on **one** surface (one plane, cylinder, ... e.g. the pieces Split Face or Trim left) become one face, exactly (`UnifySameDomain`). Faces that only meet smoothly (tangent, within 1 degree) are refitted as one surface through their outer boundary and points sampled on them; the dialog says how far it moved them (refused above 0.01 mm or 0.1 % of their size). Faces meeting at a sharp edge are refused with the reason. Offered in parametric designs too, as a "Merge" step in the timeline (Fusion hides it there) | A, F; G (the tolerances; offered with history on) |
| **Split Face** on the SURFACE tab: divides faces of a surface body (it stays one body); Merge is its counterpart | The SOLID Split Face step takes a surface body too: its faces are divided by the tool and sewn back into the same surfaces (`split_face._split_open`); everything else of the dialog as for solids. The pieces can be merged again with Merge | A |
| **Replace Face** on the SURFACE tab: a face of a surface body replaced by a target surface; the faces round it are extended or trimmed to it | The SOLID Replace Face step takes a surface body too (`replace_face._replace_open` -> `surfmod.replace_open`): one source face, or touching faces (a floor and the fillet round it), closed round by other faces. A flat target (an origin or construction plane, a flat face) is taken as its whole plane, a curved one as Replace Face takes it on solids (a cylinder whole, another surface a quarter bigger: `replace_face.target_surface`); each neighbour is carried on along its own surface or cut back to the target, and the piece of the target they close round takes the face's place (a face made on the target's own surface through their edges: a floor replaced by a roller's side is arched). A face with an open edge (Tangent Chain through a fillet into an open-topped wall picks one), a neighbour that meets the faces smoothly or runs along the target, a target beyond the faces round it, a ball (no face can be made on it through the edges) are refused with the reason | A (presence), G (ball targets) |
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
  (or MODIFY > Fillet / Chamfer), type the radius or drag the arrow, OK. Radius Type Chord
  Length makes the round that wide across instead.
- **Push or pull a face**: press Q, click the face, type a distance (+ along the face's
  arrow) or drag the arrow: the walls around it grow or shrink with it, also slanted or
  cone-shaped walls. Click more faces (two walls of a box) to move them together, each
  straight out of itself. A round wall on its own is moved out or in as a whole.
- **Merge**: MODIFY > Merge, click faces that lie on one surface or run into each other
  smoothly, OK: one face.
- **Split Face / Replace Face**: as for solids. Split Face cuts faces of a surface body into
  pieces (Merge puts them back together); Replace Face moves one face onto a flat face or
  plane and the walls round it follow.
- **Move, Align, Scale, Pattern, Mirror**: exactly as for solids; Mirror with Operation Join
  stitches the mirrored half on (Stitch Tolerance closes small gaps).

Every one is a step in the timeline (double-click to change it), undoes in one step and is
saved with the design.

## Tests

Results and check counts: `docs/sciforge/sessions/surface-4.md`.

- Scenarios (real input, FreeCAD 1.1.4), 16:
  - `surface4_fillet`: fillet, edit with a parameter that the radius then follows, chamfer
    with a pre-selected edge, a free-edge refusal, Esc, a Variable radius fillet, edited to
    Chord Length.
  - `surface4_split`: a box split by a curved surface, undo / redo, save with Ctrl+S, reopen.
  - `surface4_split_loft`: a box split by a lofted surface, edit with Extend Splitting Tool
    off, the loft itself split by the box's face, a refusal (a face that does not reach it),
    undo / redo.
  - `surface4_split_face`: Split Face of a surface body's floor by the YZ square, then Merge
    of the two halves, undo / redo.
  - `surface4_delete_merge`: an empty design, SURFACE Delete of a floor and of a solid's
    face, SOLID Delete still heals, edit from the timeline, Merge, a Merge refusal, a solid's
    edge handed to the SOLID Fillet.
  - `surface4_presspull`: Q hand-over, -5, edit to +3, undo / redo, Q on an edge, Q on the
    fillet's face edits the fillet, a curved face offset, a too-far refusal, save with
    Ctrl+S, reopen, edit after the reopen.
  - `surface4_presspull_faces`: two walls facing different ways pushed out together, edit,
    undo / redo, a too-far refusal.
  - `surface4_presspull_shade`: the lid of a cone frustum pulled up and pushed down (the
    cone carried on / cut back), edit, undo / redo, a refusal past the cone's tip.
  - `surface4_replace_face`: a surface box's floor replaced by a block's top (the walls cut
    back), undo / redo, a target beyond the walls refused in the edit, Cancel; edited onto a
    roller's round side (an arched floor).
  - `surface4_move_mirror`: Mirror Join with stitch, edit with Stitch Tolerance, Move, Move
    with Create Copy, Scale.
  - `surface4_move_faces`: Move Object Faces: a surface box's floor 5 down (the walls grow),
    Ctrl+Z / Ctrl+Y, a curved face refused, Esc.
  - `surface4_pattern`: rectangular and circular patterns of a surface body, undo / redo,
    Esc.
  - `surface4_misc`: Align, Combine refusal, Physical Material, Appearance.
  - `surface4_component`: fillet, press pull and delete on a surface body in a moved
    component, undo / redo.
  - `surface4_direct`: a design without history (where Fusion offers Merge): Merge, Ctrl+Z /
    Ctrl+Y, SURFACE Delete, Fillet, history turned on again.
  - `surface4_step_part`: SURFACE Delete of a face of a STEP part without history (taken
    into a body, it becomes a surface body), Ctrl+Z / Ctrl+Y, Fillet on it.
  - `surface4_qa` (QA): an empty design (Fillet, Q and Del open no surface dialog and raise
    nothing); a Fillet edited to another radius then Esc (the radius and the shape come
    back, one Ctrl+Z then removes the fillet); Q on a floor with a rounded corner (the
    fillet grows with the walls); a Press Pull edit and a Delete Face edit cancelled with
    Esc; the Fillet deleted in the timeline while a Press Pull and a Delete Face come after
    it (both keep working on the same faces); Merge; save, close, reopen, edit again.
  - `surface4_qa_reopen` (QA): Mirror Join with Stitch Tolerance 0.5 and Split Body by a
    surface, a Split Body edit (Extend off) cancelled with Esc, save, close, reopen: still
    stitched with 0.5, the pieces kept; the Mirror edits with Join and 0.5 read back.
- Golden models `surface4_*.json`, 22: fillet + edit + reopen, variable fillet, chord length
  fillet, chamfer + SURFACE delete, press pull + edit + reopen, press pull of a tray with
  slanted walls (its floor; two of its walls at once), of a cup's round wall, of a
  lampshade's lid, merge, merge of tangent faces (refit), split face + merge, replace face (onto a flat face; onto a cylinder; a floor with its
  fillet),
  move faces (down, then turned),
  split of a solid by a surface and by a lofted surface, split of a surface, rectangular
  pattern and pattern on path of a surface body, mirror join + scale.
- Unit tests: `SciForgeTests/unit/test_surfmod_core.py`.

## Known gaps

- **Press Pull** is refused with the reason for: a flat face with an open edge whose
  neighbours meet it at an angle, a flat face next to a tangent face (a floor next to a
  fillet: Fusion lets the fillet follow), a curved face with a tangent neighbour (a D-shaped
  wall), several curved faces at once, several faces at an angle to their neighbours, faces
  facing different ways among faces that are not flat polygons. OpenCASCADE has no
  per-face offset of an open shell bound to Python (`BRepOffset_MakeOffset::SetOffsetOnFace`
  is not exposed: `research/surface-gaps.md`): SciForge slides the corners among flat
  polygons, offsets one curved face, grows / trims the faces that run along the move, and
  carries on / cuts back the faces at an angle round one flat face.
- **Merge of faces that meet at a sharp edge** is refused; faces that meet smoothly are
  refitted (OpenCASCADE's filling through their boundary and sample points), not tangent to
  the faces around them along the outer boundary (it passes through that boundary).
  Fusion's own refit rules are not documented (G).
- **Surface Fillet options**: Constant, Chord Length and Variable (start / end radius per
  edge) only. Chord Length is exact where the faces meet at one angle along the edge; on an
  edge whose angle changes it is exact at the two ends (the radius changes evenly between),
  and picked edges at different angles must go in separate fillets. Variable with points
  along the edge, Curvature (G2), Setback corners and Rule Fillet are not offered on surface
  bodies (their SOLID implementations build on PartDesign::Fillet / SciForge's rule fillet,
  which need a solid). Fusion's documentation does not confirm Rule Fillet on surfaces (G).
- **Merge with Capture Design History on**: Fusion hides Merge there; SciForge offers it as
  a timeline step (a deliberate difference: nothing is lost, the step can be edited).
- **Without history** (Do Not Capture Design History) Merge, Delete, Fillet and the other
  surface tools work (scenario `surface4_direct`), but a surface body's steps are not baked
  into one Base Feature as a solid's are (`direct.freeze` bakes solids only; that file
  belongs to the direct-modify area): they stay hidden while history is off and show in the
  timeline again when it is turned back on.
- **Scale of a surface body merges faces that end up in one plane** (Refine, as SciForge's
  Scale does on solids: the two floor halves of a mirrored and stitched box become one face).
  Fusion's Scale keeps every face; a face split on purpose (Split Face) is joined again by a
  Scale after it. Left as built (the solid Scale behaves the same; G).
- **Surface Fillet / Chamfer take edges only**: Fusion's selection also takes a face (all
  its edges). A face of a surface body selected before F opens the dialog on that body with
  nothing picked: click the edges.

## QA pass (branch `sf/surface-4-qa`, 2026-10-23)

Found and fixed:

- **A step deleted from the timeline broke the surface steps after it, or made them take
  another face.** Deleting a Fillet under a Press Pull emptied the Press Pull's picks (its
  floor had been changed by the fillet, so Delete could not re-link it): the step went red,
  "Select a face of a surface body". Worse, a Delete Face after it kept its face *number*
  while the faces were numbered again, and silently deleted the left wall instead of the
  right one. Every surface-4 step now remembers a point inside each pick (hidden property
  `SciForgePickPoints`, written when it computes and when its picks change): a pick whose
  step was deleted is found again where it was, and a pick whose number now names a face
  somewhere else is replaced by the face that is where it was (`surfmod._names_on`,
  `refound_picks`, `_checked`). The edit dialog reads the picks the same way. Files saved
  before have no memory: they behave as before until their first recompute.
- Press Pull of a wall next to a fillet (a flat face with an open edge and a tangent
  neighbour) was refused with "the faces next to it meet it at an angle": it now gives the
  real reason (a face next to it meets it smoothly).
- A face of a surface body selected before F / Fillet opened the surface Fillet on the first
  surface body shown, not on the picked one.
- The surface dialog switching to another body could leave the new step of the first body
  behind for a moment (the last pick dropped and another body clicked before the preview
  ran): the step now goes before the switch.

Checked and found right: Cancel / Esc of every surface dialog after a change (the step's
values and the shape come back; one undo step per OK), save and reopen of Fillet, Press Pull,
Delete Face, Merge, Mirror Join (Stitch Tolerance kept) and Split Body by a surface, no
exception or unprefixed log line in any scenario log, the maths of Press Pull (slanted,
filleted and two-wall cases), Chord Length and the chamfer types (headless probes).

