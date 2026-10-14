# Session log: Modify, part 2 (branch `sf/modify-2`, wave 4, 2026-10-14)

To be folded into MEMORY.md's Session log at the merge (this branch does not edit MEMORY.md).

## What was built

- **Pattern Compute Option** (Rectangular, Circular, Pattern on Path, Mirror; Pattern Type
  Features): Optimized (Fusion's default), Identical, Adjust. Optimized and Identical are
  FreeCAD's pattern of the feature (same result). Adjust runs every extrude among the
  originals again at each copy (`pattern_adjust.py`: the profile moved, the same extent; an
  extrude To Object ends on the object where the copy lands; SciForge's Extrude and FreeCAD's
  Pad / Pocket); other features stay identical. Built by SciForge's `PatternFeature` (property
  `ComputeOption`); native patterns keep the choice in their meta.
- **Pattern on Path Start Point** (0..1 along the path; the field shows where it starts by
  itself until a value is typed; property `StartPoint`, -1 = nearest the objects). A sketch's
  browser row as the path takes its chained curves; the Path box names a whole sketch as the
  browser does.
- **Pattern of a multi-body extrude**: a cut that went through several bodies is repeated in
  each of them (a hidden `PatternFollower` per other body).
- **Draft**: Type Fixed Plane / Parting Line; Draft Sides One Side / Two Side / Symmetric
  (Angle 1, Angle 2) for both types; Parting Tool box (plane, flat face, edges, sketch
  curves); Fix Parting Line (Move Parting Line listed, greyed with the reason). SciForge's
  `DraftFeature` splits the faces at the line and tilts each group of pieces with FreeCAD's own
  Draft run in a hidden throw-away document. One Draft over faces of several bodies.
- **Shell, Draft, Scale over several bodies in one step**: the step lives in the first body;
  every other body gets a hidden follower step (`modify_bodies.py`: `ShellFollower`,
  `DraftFollower`, `ScaleFollower`, `PatternFollower`, role `ModifyFollower`, linked by
  `Source`). The timeline's roll back, suppress, move and delete take them along
  (`timeline_ops.FOLLOWER_ROLES`); SciForge's Delete and the orphan cleanup know them.
- **Scale of sketches**: a sketch's browser row (or the sketch selected before Scale) in the
  Entities box; uniform only (Non Uniform refused with the reason); the curves and their
  driving dimensions are scaled (a dimension that follows a parameter keeps its value, the
  dialog says which); a "Scale" step (`SketchScaleFeature`) keeps the factor: editing scales
  from the sketch as drawn, deleting it puts the sketch back (`SketchScaleWatch`, same undo
  step).
- **Move Object Faces** (Move/Copy): faces of one body; Free Move / Translate / Rotate /
  Point to Point / Point to Position; a Move step (`move_face.py`): a closed feature (boss,
  hole) moves whole, a flat face is replaced onto its moved plane; the picked faces are shaded
  where the movement puts them.
- **Press Pull Offset Type**: Automatic / Modify Existing Feature / New Offset
  (`offset_type.py`): Modify Existing changes the extrude whose end face was picked (its
  Length) or the earlier Press Pull / Offset Face that put the face there (its Distance), no
  new step; other faces refused with the reason.
- **Replace Face onto any surface** OpenCASCADE gives (cone, torus, NURBS face): the target is
  extended by a quarter of its size, its inner side found by sweeping it backward.
- Fixes found on the way: Ctrl+Z after a Draft that used the throw-away document left the
  drafted shape behind (see the facts); the timeline's Delete of a step built on another
  step's follower also deleted that follower; a sharp Shell OpenCASCADE gives up on (where
  rounded works) now says so and suggests Rounded instead of "too thick".

## FreeCAD facts and traps

- **In the GUI, closing any document ends the open undo step** of the others
  (`App.getActiveTransaction()` turns None, the open step is committed), and clears the whole
  selection (`Gui::Application::slotDeleteDocument` -> `clearCompleteSelection`). FreeCADCmd
  does not. A dialog preview that made and closed a throw-away document inside its undo step
  split the step: the rest of the preview went unrecorded, Ctrl+Z after OK removed the Draft
  but left the body's drafted shape. The throw-away document is now reused (UndoMode 0) and
  closed later, when no undo step is open, nothing is selected and no dialog is open
  (`drafting._scratch_document` / `_try_close`). Creating a document does not end the step.
  `insert.py` closes its import document the same way (outside a dialog's step today).
- FreeCAD's `PartDesign::Draft` runs fine in a hidden document on a Body whose
  `FeatureBase.BaseFeature` is a plain `Part::Feature` holding the solid, with a
  `PartDesign::Plane` (MapMode Deactivated) as NeutralPlane and a `PartDesign::Line` as
  PullDirection; `obj.recompute()` per object is enough. Positive angle with pull +Z: the
  part gets narrower toward +Z.
- Scaling a sketch: assign the scaled geometry first, then `setDatum` every driving
  dimension (value x factor). Turning the dimensions into references, scaling and solving
  moved the corners half way (a 30 x 15 rectangle came out 15 x 7.5).
- `pattern.face_tool` tells faces apart with `isSame`: faces must come from
  `shape.getElement(name)` of that same shape, never from a copy.
- OpenCASCADE's `makeThickness` with the Intersection join (Fusion's sharp walls) returns the
  input unchanged on a part with a narrow slot open at its side where the Arc join works;
  1 mm walls on a 2 mm rib fail in both.
- The timeline's Delete (`timeline_ops._helpers_of`) took every unused "helper" in a deleted
  step's OutList: a follower is a helper (it has a SciForgeRole), so deleting a step whose
  BaseFeature was a follower deleted the follower too. Followers now only go with their lead.
- Black adds a blank line after the module docstring of the older files; it was removed again
  so the diff stays small.
- Scale's dialog moves on to the Point box after the first body (as before); a second body is
  added by clicking the Entities box first.

## Shared files touched (one or two lines each)

`timeline_ops.py` (FOLLOWER_ROLES += "ModifyFollower"; followers are not unused helpers),
`timeline_core.py` (KIND_BY_SCIFORGE_TYPE MoveFace, SketchScale), `delete.py` (modify
followers deleted with their lead, orphans cleaned up), `bodies_gui.py` (modify followers in
the lead/follower lists; MoveFace icon), `shelling.py` (followers moved when a shell is
rebuilt; the sharp-shell message), `pickpanel.py` (members: other bodies of a step),
`golden/schema.py` and `golden/builder.py` (one import line each), `golden/pattern_ops.py`
(compute, start_point value keys). No FreeCAD core change.

## Tests

Scenarios (real input, FreeCAD 1.1.4 under xvfb), all passing on the final tree:

| Scenario | Checks | Paths |
|---|---|---|
| `modify2_pattern_adjust` | 51 | a wedge, a hole cut up To Object its slope, 3 copies: Optimized blind (each copy measured), Adjust through, OK, undo / redo, edit + Identical + Cancel, save / reopen |
| `modify2_pattern_path` | 36 | an L path from the browser, Start Point 0 then 0.25 (the copy moves), 1 refused (OK waits), undo / redo, edit reads 0.25 |
| `modify2_draft` | 72 | Parting Line with a construction plane, OK refused without the parting tool, One Side, Two Side 5 / 3, undo / redo, edit to Symmetric 4, Esc |
| `modify2_shell` | 52 | two bodies in one Shell, 2 mm, undo / redo, edit drops Body2, undo, save / reopen / edit / Cancel, timeline Delete |
| `modify2_scale` | 56 | two bodies 0.5, undo / redo, a sketch from the browser, Non Uniform refused, x2, undo / redo, edit 1.5, timeline Delete puts it back |
| `modify2_move_face` | 56 | Move Object Faces, the top up 5 mm, undo / redo, edit to -3, the right face 5 mm, Esc |
| `modify2_presspull_type` | 48 | Modify Existing Feature on Extrude 1's top (no new step), undo / redo, New Offset, Modify Existing on that offset, a side face refused, Esc |
| `modify2_bodies` | 77 | empty design (Draft / Shell / Scale say what to make), a cut through two bodies patterned (both cut), undo / redo, edit, save / reopen, timeline Delete of the pattern and of the cut, a Shell across a component |

Regression runs on the final tree, all passing: `shell_draft`, `shell_draft_draft`,
`shell_draft_hollow`, `shell_draft_qa`, `shell_draft_qa_draft`, `shell_draft_qa_mix`,
`shell_draft_qa_scale`, `shell_draft_qa_shell`, `shell_draft_scale`, the 12 `patterns_*`,
the 11 `extrude_presspull_*`, `direct_commands`, `direct_step_box`, `direct_base_feature`,
`direct_components`, `bodies_move`, `bodies_delete`, `components_move`, `extrude_multibody`,
`extrude_multibody_edit`, `extrude_multibody_move`, `modify_replace_face`, `modify_remove`,
`timeline_browser`, `timeline_browser_qa`, `timeline_rolled_cut`, `inspect_section`,
`inspect_construct_use`, and `--only base` (914 unit tests, 363 golden models + the known
xfail `plate_hole_grid`, smoke, journey).

Golden models `golden/models/modify2_*.json` (24, analytic numbers). Unit tests
`SciForgeTests/unit/test_modify2_schema.py` (the golden steps' schema).

## Not built (and why)

- Draft Move Parting Line: the line moving needs a step face along it; OpenCASCADE's draft
  (`BRepOffsetAPI_DraftAngle`) cannot make one. Greyed with the reason.
- Draft: a parting line that bends inside one face (each piece turns about one line).
- Adjust for features that are no extrude (holes, revolves): their copies stay identical.
- Start Point and Angle 2 have no drag handle (typed only).
- Pattern Type Components, Scale of components, Split Body with several tools, Move of
  components: the components area (components-2).
- Move Set Pivot; Move Object Faces of several bodies at once.
- Press Pull Modify Existing on a base feature's, revolve's or sweep's face; whether Fusion's
  Automatic lengthens an extrude when its end face is pulled is not settled (Automatic still
  adds a step; Modify Existing lengthens the extrude).
- Rolling the marker back before a sketch's Scale step leaves the sketch scaled.
- Split Face / Split Body (brief item 4): the remaining gaps in the parity docs belong to
  components-2 (several tools) or are kernel limits (a later Refine merges split faces;
  Split Shelled Body's hidden inner outline). Thicken / Offset Face (item 6): the parity docs
  list no gaps.
