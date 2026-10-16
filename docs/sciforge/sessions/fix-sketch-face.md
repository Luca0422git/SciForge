# Session log: fix-sketch-face (branch `sf/fix-sketch-face`, 2026-10-16)

Luca's report (quick update of CI #117): "sketching on an edited object will revert it to a
previous state, making it impossible to sketch on edited faces".

## Reproduced

A probe scenario made a 40 x 30 x 10 block, one edit, then Create Sketch and a click on the
top face (real clicks), and recorded which step of the body was drawn while the sketch was
open. With every edit tried (fillet, Press Pull of a side face, Move, Move turned about Z,
Create Copy, a later Extrude Join, Shell, Hole) the body drew its **first extrude**: the
fillet, the hole, the joined block, the shell disappeared and a moved part jumped back to
where it was before the move. After Finish Sketch the part came back, and the extrude made
from the sketch was right (it builds on the body's Tip), so the model itself was never
damaged; what Luca saw is the drawing. A moved part had a second, real fault (below).

## Root cause

- `sketch_ui.create_sketch` → `_earliest` → `hole.earliest_face` hangs a sketch on the
  **earliest** step that already has the clicked flat face (made for the hole QA: suppressing
  or deleting an unrelated hole must not take the sketch along). For a face the first
  extrude made, that is the first extrude.
- FreeCAD's sketch "Show support" (`ViewProviderSketch.ShowSupport`, on by default) shows the
  object a sketch is attached to while it is open (`ViewProviderSketch::setEdit` runs
  `tv.show([ref[0] for ref in ActiveSketch.AttachmentSupport ...])` through `Show.TempoVis`).
- A PartDesign body draws one step at a time: showing the first extrude
  (`PartDesignGui::ViewProvider::onChanged(Visibility)`) hides the Tip. So the part was drawn
  as it was before every later edit, and clicks while sketching (Project, snapping) could only
  reach the old shape.
- Separate fault for Move: `earliest_face` went back past a Move step whenever the moved face
  still lay in the same plane (a move along the top). The sketch then hung on the face
  before the move: when the Move was later edited to lift the part, the sketch stayed at the
  old height and the boss sank into the part (checked on the original code: the boss's volume
  vanished). It also went past the start of a copied body to the copy step outside the body.

## The fix

- `sketch_ui.open_sketch` turns "Show support" off on the sketch before `setEdit`, then
  `sketch_ui.show_design_at(sketch)` draws the body's step at the sketch's place in the
  timeline through the sketch's own TempoVis (so Finish Sketch restores everything, the same
  way FreeCAD restores its own changes). `sketch_mode._start` calls it too, for sketches
  opened by other paths (Text, FreeCAD's commands).
- The rule is pure and unit tested: `timeline_core.shown_while_sketching(chain, at)`: the
  newest step of the body's history (from the Tip back) that does not use the sketch and
  comes before it in the timeline. A new sketch: the Tip, every edit. A sketch edited from
  the timeline: the step before it (Fusion rolls back to the sketch); FreeCAD's own "Hide
  dependent" still hides the steps that use the sketch.
- `hole.earliest_face` / `earliest_edge` stop at a step that moves the whole solid
  (`hole.moves_solid`: SciForgeType MoveCopy, Align, Scale) and never leave the body.
- `_earliest` itself is kept: the hole QA's rule (a sketch on a face the first extrude made
  survives suppressing an unrelated later step) still holds and is checked again
  (`sketch_earliest_face`, `fixsketch_fillet` E, `fixsketch_hole` D).

## FreeCAD facts and traps found

- A flat-face attachment (`MapMode FlatFace`) puts the sketch origin at the body origin
  projected onto the face's plane (`Attacher.cpp`, mmFlatFace: `GeomAPI_ProjectPointOnSurf
  (refOrg, plane)`), and its axes follow only from the normal. So a sketch never follows an
  in-plane move of its face, whichever step it hangs on; only a change of the plane (lift,
  tilt) moves it. Fusion behaves the same way for the origin (forum thread "Sketch Origin
  from Offset plane problem\bug").
- The sketch grid follows the zoom, and FreeCAD's grid snap moves a coordinate that is within
  a fifth of the grid size of a grid line (`SnapManager::snapToGrid`, tolerance
  `getGridSize() / 5`): zoomed out to a 10 mm grid, a click at x 12 became x 10. Scenario
  clicks use sketch coordinates ending in 0, 3, 5 or 7 (`fixsketch_steps.circle`).
- `ShowSupport` is a property of each sketch's view provider, set from the parameter
  `Mod/Sketcher/General/ShowSupport` only when the view provider is made: a saved file keeps
  its own value, so a parameter alone would not cover older designs. SciForge sets it off on
  each sketch it opens (saved with the file) and corrects the drawing afterwards in any case.
- A suppress or unsuppress is an undo step: a scenario that undoes a boss must do it before
  suppressing anything.

## Tests (real FreeCAD 1.1.4, one at a time)

New scenarios, all passing: `fixsketch_fillet` (72 checks), `fixsketch_presspull` (93),
`fixsketch_move` (71), `fixsketch_join` (89), `fixsketch_shell_draft` (66), `fixsketch_hole`
(65). On the original code `fixsketch_join` and `fixsketch_move` fail 17 checks (the part
drawn as the first extrude / back before the move, the boss sunk after lifting the Move, a
copy's sketch on the step outside its body). Unit tests: `ShownWhileSketchingTests` (5); all
1093 unit tests pass.

Older scenarios run in one profile (as a CI shard), all passing (74 with the new ones): every
`sketch_*` (37), `hole_qa`, `hole_qa_more`, `hole_qa_part`, `hole_qa_thread`, `hole_sketch`,
the `extrude_*` that sketch on faces or edit sketches (`extrude_review_fixes`,
`extrude_feel*`, `extrude_presspull_qa/qa2/qa3/qa5/qa6`, `_regions`, `_presspull`,
`_objects`, `extrude_from_edited_sketch`, `extrude_edit_sketch_shown`), `timeline_browser*`,
`timeline_rolled_cut`, `revolve_qa_more`, `luca_session`, `components_extrude`,
`direct_base_feature`.

## Gaps (not done)

- Only the sketch's own body is rolled back in the drawing while an older sketch is edited;
  Fusion also rolls back the other bodies' later steps. The history marker itself never
  moves while a sketch is open (as before).
- Suppressing a Move (or Press Pull) step takes a sketch on its face along (SciForge's
  suppress rule); in Fusion such a sketch would probably stay on the face. Unchanged.
