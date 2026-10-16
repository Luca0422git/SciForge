# Session log: fix-extrude-to-face (branch `sf/fix-extrude-to-face`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
Started from `d5a3690b9d`. No FreeCAD core file changed (no full build needed).

Luca's request: "when extruding, clicking on a face should bring that extrusion to the same
height as that face".

## What Fusion does (research; sources in `parity/extrude-presspull.md`, top section)

- An extrude's profiles and faces must all lie in one plane (Autodesk API reference).
- With the Distance extent, picking another object "only sets the extrusion distance to the
  current value", not parametric; To Object is the parametric way and takes a face, a body
  or a vertex, not an edge (Autodesk Community, "Extrude to Face / Edge / Vertex").
- Dragging the arrow and clicking a face snaps to it (Autodesk Community, two threads; the
  Press Pull one says the drag must have started); Snap To infers a distance from a parallel
  plane (Autodesk alumnus); a user describes clicking "a surface, a point" to set the
  distance (Shapr3D forum, about Fusion).
- To Object ends at "a body, face, or plane"; a curved surface is reached with To (Autodesk
  help, Autodesk Community).
- autodesk.com and the Autodesk forum could only be read through search excerpts (the
  sandbox's fetch cannot resolve them).

## What was built

1. `sciforge/extrude_to_face_core.py` (new, Qt-free, 24 unit tests in
   `SciForgeTests/unit/test_extrude_to_face_core.py`): which targets give a height (a flat
   face parallel to the profile, a vertex, a parallel plane), which run along the extrusion
   (refused), which are To Object (curved, tilted); the side of Two Sides; Symmetric half /
   whole; the dialog's words ("Up to the face: 12.5 mm", "Side Two up to the point: 10 mm",
   "Ends on the curved face (To Object)") and the refusals.
2. `sciforge/extrude_to_face.py` (new): what a click or the mouse points at, in design
   coordinates (`target`, `hits_at` through `view.getObjectsInfo`, the front-most spot,
   corners first), a face of the part found again by the clicked point after the preview
   merged with it (`base_face_at`), the blue snap mark (`SnapHighlight`, node
   `SciForgeSnapTarget`).
3. `sciforge/extrude_ui.py`: with a profile picked, a click on a face out of the profile's
   plane goes to `_end_at` (distance, To Object or a refusal); a face in the profile's plane,
   the preview's own end and an empty Profiles box work as before. A mouse-position filter
   on the view; `_dragged` / `_dragged2` snap while the arrow is held (`_drag_snap`: a press
   let go without moving snaps to nothing; the release's selection is ignored for 0.4 s).
   ZERO_HINT now says a face can be clicked. A coplanar face clicked after a Join preview
   changed it is found again by the click point (before: "That face belongs to this extrude
   itself.").
4. `sciforge/extrude.py`: **To Object on a curved face of another body is SciForge's own
   extrude feature** (`curved_face`, `curved_elsewhere`, used by `_structure`). FreeCAD's Pad
   "up to face" on a curved face of another body ended in the wrong place (golden
   `extrude_to_cylinder_face`: 22494 mm^3 through the cylinder instead of 4753). A curved
   face of the same body was right with the Pad, so that stays a Pad (an older Pad with later
   steps on it cannot change its kind: `build` refuses that).

## Tests

- Unit: `test_extrude_to_face_core` (24 tests).
- Golden: `extrude_to_cylinder_face` (new; fails without the fix, passes with it).
- Scenarios (real input), all pass: `extrudeface_basic` (click the tower's top =
  30 exactly, Extent Distance, the words, the arrow; OK; Undo / Redo; edit from the timeline
  and click another face = 12; Esc keeps 12; save / reopen; a side that is To Object takes
  the clicked face as its new object), `extrudeface_sides` (77: below
  the sketch = -30 Join; a cut down to a face = -30 Cut by itself; Two Sides with a face and
  a corner; Symmetric half and whole; a coplanar face is still a profile and drops again; a
  face along the extrusion refused; an empty Profiles box takes the face; Press Pull on a
  sketch area), `extrudeface_objects` (47: a rod's curved face = To Object, exact volume;
  Symmetric refused; Undo / Redo; New Body up to a block in a component moved up 5 = 17),
  `extrudeface_drag` (55: held over the tower's top = 30 while the button is down, mark
  shown, kept on release; a plain click on the arrow; a plain drag; a corner = -10 and a cut;
  side two's arrow onto a corner = 10; Esc).
- Regression, run in one profile (as a CI shard does), all pass: `components_extrude`,
  `extrude_bodies_highlight`, `extrude_edit_sketch_shown`, `extrude_feel`, `extrude_feel_box`,
  `extrude_feel_cut`, `extrude_feel_keys`, `extrude_from_edited_sketch`, `extrude_multibody`,
  `extrude_multibody_edit`, `extrude_multibody_move`, every `extrude_presspull_*` (objects,
  options, presspull, qa .. qa7, regions), `extrude_review_fixes`, `gaps_extrude_taper_to`,
  `gaps_join_new_body`, `gaps_thin_extrude`, `handles_on_top`, `modeling2_extrude`,
  `modify2_presspull_type`, `sketch_areas_face`, `sketch_text_cut`, `sketch_tools_extrude`,
  `value_box_units`. `--only base`: unit 1112 OK, golden 400 pass + the 1 known xfail, smoke
  and journey pass; `check_install.sh` OK.

## FreeCAD facts and traps

- `view.getObjectsInfo(pixel)` lists every document object along the line of sight, front
  first (Coin's pick-all), skipping nodes that are no view provider (the arrows, the overlays):
  good for "what is under the mouse while an arrow is dragged".
- A Coin `SoTranslate1Dragger` takes its position from the mouse on every move (start matrix
  plus the projected motion): setting its translation while it is held is undone by the next
  move (the arrow would flicker), so a snap shows in the value and the preview and moves the
  arrow on the release.
- `SelectionObject.PickedPoints` is (0, 0, 0) for an element selected without a 3D click
  (browser, box selection): treat it as "no point".
- PartDesign Pad / Pocket `UpToFace` with a curved face of another body: wrong result (see
  above). With a tilted flat face it is right.
- Test mouse events (`QTest`, `sendEvent`) do not move `QCursor`: the dialog reads the mouse
  position from an event filter on the view's widget, which sees both real and test input.

## Gaps (also in the parity doc)

Press Pull on a face (offset) does not snap to a clicked face yet; no snapping to edges,
sketch points or planes while dragging (planes work with a click); the held arrow jumps only
on release; App::Link instances use the original's place; a sketch area at another height is
still a profile; a sketch area hidden behind another body can still take a click; a tilted
(flat, not parallel) face is tested in the unit tests and through the same To Object path as
the curved face, not by its own scenario.
