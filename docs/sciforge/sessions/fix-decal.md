# 2026-10-16: Decals stay on their faces (branch `sf/fix-decal`)

Luca's report: "decals dont follow their faces when moved". Spec, sources and gaps:
`docs/sciforge/parity/misc.md`, Decal, "Following the face". No core patch (no full build
needed).

## Reproduced (real clicks, before the fix)

`fixdecal_body_move` on d5a3690b9d: a decal on the box's top, M, X Distance 30, Z Angle 90:
the decal's step turned red ("The face under the decal is gone") and the picture stayed where
the top had been, 27 mm off the body; the same after OK, Ctrl+Y, editing the Move, the
cylinder's wrapped decal after its Move, a drag of the Move arrow (33 failed checks of 107).
A small move along the face (X 5) was worse: the moved top still lay under the old spot, so
the decal stayed put and looked fine in the timeline.

## Root cause

A decal kept its frame (`Anchor`) as a fixed placement in its component's coordinates and,
at every compute, looked for "a face under that spot with the same normal" (plus "a parallel
flat face under it"). It never knew how its face had moved: a Move/Copy step (which moves
the body's solid), a joint or Component Drag (which move a root body by its Placement, with
no recompute at all), a body put into another component (the decal stayed in the old one
and was drawn in the old component's frame), a cylinder made thicker. FreeCAD's own face
naming (toponaming) does not help: SciForge's Python steps (Move, Press Pull) drop the element
map, a link to "Face6" becomes "?Face6" (probed).

## The fix

- `decal.follow()`: at every compute the decal compares its face with what it remembered of
  it at the last good compute (`FaceRecord`, JSON: the face's own surface frame under the
  decal's middle and its (u, v) there, its corners, area, centre, outward normal, the body's
  volume and centre), in this order:
  1. the same face where it was (renamed only) -> nothing moves;
  2. the same face moved as a whole: for each face of the same kind and area, the move that
     takes the remembered surface frame onto the face's frame at the same (u, v), accepted
     when it also takes the remembered centre, corners and normal onto the face (a move of
     the shape keeps a surface's parameters). Several faces can match (a box's top and
     bottom are alike under a turn): when the body moved as a whole (same volume, its centre
     moved the same way) the face of the same name wins (a move keeps names), else the
     least motion (a pushed face does not turn); a turn without a whole-body move is only
     taken when nothing fits in place (3, 4);
  3. the face still under the decal's middle (a hole under it is allowed: half the decal's
     smaller side), for a face that grew, was cut or renamed;
  4. a flat face pushed / pulled along its normal under the middle; a cylinder about the
     same axis made thicker / thinner (the decal keeps its size, wraps the new radius);
  5. else the face is gone: the step is red with the reason and the mesh is emptied (no
     picture floating in the air).
  The decal's frame (and its cylinder axis) is moved the same way, the mesh built again, the
  record written again.
- `BodyPlace` (the body's own placement when the mesh was computed) and an `SoTransform` in
  `ViewProviderDecal`: the picture is drawn at `body.Placement * BodyPlace^-1`, so a joint,
  a drive, Component Drag or an undo that moves a root body by its placement carries the
  picture at once; `decal_ui._Watch.slotChangedObject` re-places the drawings when a body's
  or component's Placement (or a component's Group) changes.
- Components: `decal.carry(body)` puts a body's decals into its component (called by
  `components.place` and `components.from_bodies`, and for designs saved before, when they
  open); a component's placement moves its decals through Coin's scene graph.
- Undo / redo: `_Watch` recomputes (quietly) a decal that no longer matches its body after
  an undo / redo (a step whose recompute ran after its undo step was closed), and flags red
  a decal whose face a redo took away (the redo restores the empty mesh, not the red mark).
- Edit Decal: **Select Face** (any face, of any body: `decal.relay`), and when the face is
  gone the dialog says so and waits for a click on a face. The red step's message says so.
- Old designs: `onDocumentRestored` remembers the face as saved and the body's placement.
- Copies of a component (Copy / Paste, Move's Create Copy, component patterns: instances.py
  repeats the bodies' solids in copy bodies) now show its decals too: the view provider
  shares the picture's Coin nodes under one more transform per copy body
  (`decal.copy_places`: the copy's placement times its source component's inverse, or the
  pattern's move), re-placed when an instance moves, is shown / hidden, made or deleted,
  or a pattern changes.
- `decal_core.upright_hint(normal, up, right)`: the picture's up in a turned component.
- Found on the way: **Press Pull at distance 0 dropped a primitive's placement**
  (`presspull_core.press_pull` returned `base.copy()`, and the feature's Shape takes the
  feature's placement): while the dialog opened on a cylinder made with the primitive tool,
  the body jumped to the origin for a moment (and a decal on it with it). The copy now has
  the placement built into its geometry.

## Tests

Scenarios (real mouse and keys; the checks read where Coin draws the picture, through every
transform in the scene graph, and how far it lies from the body's faces):

- `fixdecal_body_move` (132): Move/Copy of the body (live in the dialog, OK, Ctrl+Z / Ctrl+Y,
  edited from the timeline, an arrow dragged), a cylinder tipped over (still wrapped round
  it), Create Copy (the decal stays on the original), the history marker dragged before the
  moves and back to the end.
- `fixdecal_components` (130): Create Components from Bodies (the decal goes into the
  component), Move/Copy of the component captured (live, OK, undo, redo) and not captured
  (turned), Component Drag of another component with a wrapped decal, a body dragged in the
  browser into another component, Copy / Paste of the component (both pictures on the copy;
  the copy moved and Esc; hidden and shown).
- `fixdecal_face_change` (104): Press Pull of the top (live and OK) and of a cylinder's side
  (thicker: still wrapped, same size), the extrude distance edited from the timeline, undo /
  redo, a neighbour pulled out (the top grows, the decal stays), Esc during a Press Pull.
- `fixdecal_face_gone` (61): the face's step deleted (red with the reason, nothing drawn),
  Ctrl+Z / Ctrl+Y, Edit Decal waits for a face and puts it there, undo / redo of that,
  Select Face onto another body's cylinder.
- `fixdecal_joints` (88): a decal on a root body; the joint made (the body flips onto the
  other), Drive Joints (live, OK), undo / redo, Component Drag along the joint, undo.
- `fixdecal_reopen` (75): moved, saved, reopened (drawn in place, nothing to recompute),
  moved again after reopening, undo / redo; a design saved by the earlier SciForge (no face
  remembered) brought up to date and followed.
- `misc_decal` (54) still passes; all seven pass in one profile.

Other areas run after the change (they use `components.place` / `from_bodies`, Press Pull,
primitives): `components_basic` 251, `components2_bodies` 298, `components2_copy` 277,
`components2_pattern` 278, `direct_components` 219, `extrude_presspull_presspull` 53,
`primitives_qa_keys` 47, `primitives_qa_part` 85: all pass. Unit: `test_misc_cores` 40.
`--only base`: unit 1089 OK, golden 399 pass + the known XFAIL `plate_hole_grid`, smoke 71, journey 25: all pass.

Headless probes (in the session's scratch folder) checked the maths on their own: Move
translate / rotate, Pad length, Press Pull top and side, cylinder radius, the face's step
removed, copies of an instance and of a circular component pattern in a turned component.

## FreeCAD facts and traps found

- FreeCAD's toponaming does not survive SciForge's Python features: a `PropertyLinkSub` to a
  body's "Face6" becomes "?Face6" after a Move step (element map lost), though the face
  keeps its index. PartDesign's own Pad keeps it.
- A rigid move of a shape (`transformShape`, a placement) keeps every surface's (u, v)
  parameters: the surface frame at the same (u, v) moves with it (planes, cylinders,
  B-splines).
- A PartDesign primitive (AdditiveCylinder at x 100) keeps its placement as the shape's
  location: any step that hands its base shape on unchanged with `shape.copy()` loses it
  (the feature's Shape takes the feature's own placement). Bake it in
  (`transformShape(place.toMatrix(), True)` on a copy with an identity Placement).
- A joint moves a body at the root by its own Placement without recomputing it; Component
  Drag commits its undo step before recomputing (`joints_drag.finish`), so whatever the
  recompute changes is outside the undo step: a drawing must follow the Placement itself.
- After a redo, a FeaturePython whose execute had raised is "Up-to-date" again (the state is
  not restored, only the properties).
- `DocumentObject.recompute()` on an object whose execute raises prints a pyException with a
  traceback to the Report view; `preview.quiet()` keeps it out (the step is red anyway).
- Coin: a node can be shared; `SoGetMatrixAction` on the path to the coordinates node gives
  where the points are drawn, transforms inside the view provider included (the tests use
  it: what is drawn, not what is stored).

## Gaps

- A component's copies (instances) show its decals, but the browser lists the decal under
  the original only.
- Fusion keeps its own face names; SciForge follows what it remembers of the face's shape
  and place, so a face rebuilt so that it both changes shape and moves in one step may not
  be found (the step goes red; Edit Decal > Select Face puts it back).
