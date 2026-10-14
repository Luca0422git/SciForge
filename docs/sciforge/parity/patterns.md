# Parity spec: Rectangular Pattern, Circular Pattern, Pattern on Path, Mirror (outline 7.6)

Source: Fusion's documented behaviour (public help topics on the pattern commands and Mirror)
and everyday use. Not yet checked against Luca's own screen captures (outline 2.4); the
choices marked **(assumed)** below need his confirmation. Implemented in
`src/Mod/SciForge/sciforge/pattern_ui.py` (dialogs, commands, pickers), `mirror_ui.py`
(Mirror's command), `pattern.py` (the document side, no GUI) and `pattern_core.py` (where the
copies go, pure Python). Status: **first pass, not yet signed off**.

## Behaviour spec: Compute Option, Start Point, extrudes over several bodies (modify-2, 2026-10-14)

Sources (A = Autodesk help, blog or API reference; F = Autodesk Community forum; G = guess,
to be checked against Fusion):

1. Autodesk blog, "Understanding Compute Options for Mirror and Pattern in Autodesk Fusion"
   (https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-mirror-and-pattern-compute-options/).
2. Fusion API, `PatternComputeOptions` (OptimizedPatternCompute, IdenticalPatternCompute,
   AdjustPatternCompute) (https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/PatternComputeOptions.htm).
3. Autodesk Community, "Trying to understand Pattern Compute Option: Optimized, Identical &
   Adjust" (Jeff Strater: Adjust "recomputes each instance almost as if it were a separate
   feature")
   (https://forums.autodesk.com/t5/fusion-design-validate-document/trying-to-understand-pattern-compute-option-optimized-identical/td-p/6516163).
4. Autodesk help, "Create a pattern on a path"
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-EF6AC718-E891-42FE-A2B5-C289D320FEDF.htm);
   Fusion API `PathPatternFeatureInput.startPoint` (0 to 1 along the path), `isFlipDirection`,
   `isOrientationAlongPath`
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/PathPatternFeatureInput.htm).
5. Autodesk Community, "Pattern on path - start point value"
   (https://forums.autodesk.com/t5/fusion-design-validate-document/pattern-on-path-start-point-value/m-p/10867017).

| # | Fusion | SciForge | Source |
|---|---|---|---|
| C1 | Compute Option (Features): Optimized (the default), Identical, Adjust, at the bottom of the dialog | Same three, Optimized chosen; each has a tooltip saying what it does | A (1, 2) |
| C2 | Optimized: identical copies, fastest (the feature's faces copied) | The copies are FreeCAD's pattern of the feature (its tool moved): identical copies | A (1) |
| C3 | Identical: identical copies of the feature's result | Same as Optimized (the same result; there is nothing slower to choose in FreeCAD) | A (1), G (same result) |
| C4 | Adjust: every copy computed again where it lands, e.g. an extrude To Object ends on the object at every copy | An extrude (SciForge's Extrude, FreeCAD's Pad / Pocket) is run again for every copy: its profile moved to the copy, the same extent (Distance, To Object, All, Through All); the object it goes to stays where it is. The copies are then joined or cut like the original | A (1), F (3) |
| C5 | Adjust on a feature that has nothing to adjust | Holes, revolves, fillets and other features: their copies stay identical (no message) | G |
| C6 | A copy that cannot be computed where it lands | The pattern step says which copy and why ("Copy 2 of Extrude 2: ..."); the dialog shows it and OK waits | G |
| C7 | Compute Option shown for Pattern Type Features only | Same (hidden for Faces and Bodies) | G |
| P1 | Pattern on Path: Start Point, where along the path the pattern starts (0 = the path's start, 1 = its end) | A Start Point field (0 to 1, 3 decimals). The Distance is counted from that point along the path; every copy is moved by the step from the start point to its own point (Orientation Path Direction also turns it by the change of the path's direction there) | A (4), F (5) |
| P2 | Start Point before it is set | It shows where SciForge starts: the point of the path nearest to the objects (0 when they sit at the path's start). Typing a value fixes it | G |
| P3 | Copies running off an open path | The dialog says so (also when the Start Point pushes them off the end); OK waits | A (4) |
| P4 | Distance Type Extent / Spacing, Orientation Identical / Path Direction, Suppression on Pattern on Path | Already there (Distribution Extent / Spacing, Orientation, Suppression dots) | A (4) |
| M1 | A pattern of an extrude that cut several bodies | Fusion repeats the extrude's change in every body it changed: the pattern step lives in the extrude's own body and gets a hidden step in every other body the extrude changed (like the extrude's own hidden steps); undo, the timeline's Delete, suppress and the history marker treat them as one step | G (follows from Fusion's one-feature-many-bodies extrude) |

## What gets built

| Pattern Type | Built as |
|---|---|
| Features | FreeCAD's `PartDesign::LinearPattern` / `PolarPattern` / `Mirrored` (Direction 2 is LinearPattern's second direction). FreeCAD 1.1 also repeats dress-up features (fillets, chamfers). Pattern on Path and features FreeCAD cannot repeat use SciForge's `PatternFeature` (`PartDesign::FeaturePython`): the feature's tool, or the difference it made, copied |
| Faces | `PatternFeature`: the picked faces are closed into a solid with the faces around them (a hole's wall gives the hole's cylinder, a boss's side and top give the boss); the solid is cut (a hollow) or joined (material) at every copy |
| Bodies | Rectangular / Circular / Path: **one new body per copy**, like Fusion (a top-level step + one small copy feature per new body, which follows the source body). Mirror: Operation **New Body** (the same) or **Join** (`Mirrored` in "Whole shape" mode inside the body) |

Every feature carries `SciForgeType`, so the timeline shows Fusion's step name and a
double-click opens SciForge's dialog (also on plain FreeCAD patterns from older files).

FreeCAD 1.1.4 stores `LinearPattern.Spacings2 = [0.0]` by default, which stacks a second row
on the first (core patch #4 fixes it in C++). SciForge always writes both spacing lists, so
two-direction patterns are right on stock FreeCAD and in old files too (golden
`pattern_rect_hole_grid_fusion` passes on stock 1.1.4, `plate_hole_grid` needs the patch).

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| CREATE > Pattern > Rectangular / Circular / Pattern on Path, CREATE > Mirror; nothing selected: the dialog waits | Same. A hint says what to click; the model does not change until there is something to pattern |
| Started with features selected (timeline) / faces / a body | Taken at once, Pattern Type set to match; the next box (Direction, Axis, Path, Mirror Plane) is the active one |
| Pattern Type Faces / Bodies / Features / Components | Faces, Bodies, Features. Components greyed with the reason (the components area builds it) |
| Objects: click features in the timeline (Features) | Same; a click on a face in the view takes the feature that made it; a sketch is refused with the reason |
| Selection boxes: blue while they take the clicks, click one to make it active, x clears | Same |
| Direction: an edge, an axis, a flat face (its normal) | Same; the origin X / Y / Z axes are drawn while a direction or axis box waits and can be clicked where the part does not hide them |
| Direction 2 offered at right angles | **(assumed)** After Direction 1 SciForge offers the origin axis (or an edge of the part) at right angles in the floor plane, Quantity 1 |
| Quantity, Distance, Distribution Extent / Spacing, Direction Type One Direction / Symmetric, per direction | Same. Extent: the distance from the original to the last copy; Spacing: the gap. A negative distance goes the other way. **Symmetric (assumed):** the quantity counts each side, the original shared (Quantity 3 gives 5 in a row), the distance is measured on each side |
| Circular: Axis (an axis, an edge, a round face's axis), Type Full / Angle / Symmetric, Quantity, Total Angle | Same. Angle: Quantity copies from the original to Total Angle (360 = Full). **Symmetric (assumed):** Quantity and Total Angle per side. Switching to Angle starts at 180 deg, Symmetric at 90 |
| Pattern on Path: Path (an edge or sketch curve), Start Point, Distance, Quantity, Distribution, Direction Type, Orientation Identical / Path Direction | Same. The copies start at the Start Point (until one is typed: the point of the path nearest to the objects); closed paths go round; Path Direction turns the copies with the path (about the path's plane). Running off an open path's end is said in the dialog. A sketch's browser row as the path takes all its curves (chained) |
| Mirror: Objects, Mirror Plane (origin plane, flat face, construction plane), Operation for bodies | Same. The origin planes are the big squares of Create Sketch; a square in front of the part takes the click, the part takes it where it is in front |
| Values take parameters and formulas | Same for the distances, the angle and the quantities; a symmetric pattern's gaps are expressions of its spacing, so the copies follow a parameter change. A quantity that follows a parameter is rounded to a whole number; a pattern with one is built by SciForge's `PatternFeature` (FreeCAD's features cannot change their number of copies from a parameter); the arrows of the Quantity box make it a plain number again. A pattern of bodies takes a plain number (each copy is a body) |
| Live preview of the copies | Same (FreeCAD's feature, recomputed 60 ms after a change) |
| Compute Option Optimized / Identical / Adjust (Features) | Same: see C1-C7 above (Adjust runs an extrude again at every copy) |
| Blue arrows to drag the distances; a handle for the angle | One blue arrow per direction (Rectangular), one along the path (Path), a curved one for Total Angle (Circular, Angle/Symmetric, dragged round up to a full turn). Drawn on top of the part |
| Errors shown in the dialog, OK waits | Same; nothing is printed to the Report view while the dialog is open. **SciForge limit:** at most 2500 instances in one pattern (50 x 50 holes take about 20 s to build here); more is refused with the count, so a typo cannot freeze SciForge. A quantity is taken when the field is left (typing 1000 does not build 1, 10 and 100 copies on the way) |
| OK / Enter, Cancel / Esc, one undo step, Ctrl+Z in the dialog cancels it | Same |
| Double-click in the timeline edits it | Same (all four kinds, every Pattern Type) |
| Deleting a pattern of bodies deletes its bodies | Same (they go a moment later, as their own undo step) |
| Suppression: a dot on every copy, click one to leave that copy out | Same for Rectangular, Circular and Path patterns (dots drawn over the part; a left-out copy's dot turns grey; clicking it again puts the copy back; unticking Suppression makes every copy again). FreeCAD's pattern features cannot leave a copy out, so a pattern with suppressed copies is built by SciForge's `PatternFeature` (same result otherwise); a pattern of bodies simply makes fewer bodies |
| Objects picked in any order (the hole in a boss before the boss) | Repeated in timeline order, like Fusion (FreeCAD repeats them in list order: the copied boss filled its own hole) |
| Fusion has no active body: a feature of any body can be picked | Same: the dialog takes the body of what is clicked (and makes it active); features of two bodies in one pattern are refused with the reason |
| Picked features and bodies are shaded in the view | Same (blue), also when they are picked in the timeline |
| Changing a pattern keeps what was built on it (a sketch on its top face, a fillet on its edges, a Press Pull of its face) | Same. When a change needs the other kind of feature (FreeCAD's pattern cannot leave a copy out, follow a parameter in its count or repeat faces) SciForge rebuilds the step and moves every link to it over to the new step, each face / edge found again by where it is |
| Deleting the feature a pattern repeats | The pattern adds nothing and shows a warning in the timeline (FreeCAD kept the copies of the deleted hole and froze the steps after it); edit it to pick others. Undo brings everything back |
| Deleting the body a pattern of bodies copies | The step shows why it cannot be computed; the copies keep their shape |

## Known gaps (never faked: shown greyed with the reason, or listed here)

| Fusion option | Why not yet |
|---|---|
| Adjust for features other than extrudes (a hole reaching a slanted face, a revolve To Object) | Their copies stay identical: only extrudes are run again at every copy (`pattern_adjust.py`) |
| Optimized faster than Identical | Both are FreeCAD's pattern of the feature's tool: the same result at the same speed |
| Pattern Type Components | Not built yet: it belongs to the components area (components-2) |
| Faces: copies "heal" into different surroundings | The closed faces are copied as they are (a hole copied into a thicker area stays as deep as the original). Faces that do not close up with one face around each opening (a fillet's face) are refused with the reason |
| A pattern of bodies whose references lie in another body with a moved placement | The references are read in the copied body's coordinates |
| Pattern on Path: Start Point dragged along the path in the view | Typed in its field only (no handle on the path yet) |
| Timeline icon of Pattern on Path | Named "Pattern on Path", shown with the Rectangular Pattern's icon (there is no icon of its own yet) |
| Patterning a pattern step alone | Repeats the step's copies, not the original it copies (as Fusion's pattern feature stands for its copies); pick the original step too for whole rows |

## Tests

- Scenarios (real clicks, keys, drags; any Report-view error fails them):
  `patterns_rect.py`, `patterns_circ.py`, `patterns_mirror.py`, `patterns_path.py`,
  `patterns_suppress.py`, `patterns_params.py`, `patterns_qa.py` (wrong picks, Ctrl+Z in the dialog, type switch, timeline delete of a body
  pattern, save and reopen). Volumes and positions checked with hand-derived formulas.
- QA scenarios (break-and-fix pass, 17 paths): `patterns_qa_paths.py` (beginner with nothing
  picked, values and direction before the objects, Esc in the middle of a pick, values while
  the preview runs, arrows dragged far and back, Enter in Quantity), `patterns_qa_edit.py`
  (three timeline edits with Ctrl+Z inside one, undo/redo through them, a boss on the pattern's
  top face kept through a rebuild and a taller box, Ctrl+S with the dialog open, reopen and
  edit), `patterns_qa_part.py` (a second body, a construction plane as mirror plane, the
  repeated hole deleted, E / F / Delete with a dialog open), `patterns_qa_more.py` (Press Pull
  after a rebuilt pattern, a pattern of a pattern, Total Angle 270 typed and dragged),
  `patterns_qa_features.py` (two steps picked in the wrong order, a Faces pattern following the
  hole, a fillet's face refused in words, the copied body deleted).
- Golden models (ops `rectangular_pattern`, `circular_pattern`, `path_pattern`,
  `fusion_mirror`, `pattern_edit` in `golden/pattern_ops.py`, the dialogs' code):
  `pattern_rect_hole_grid_fusion`, `pattern_rect_symmetric_bosses`,
  `pattern_circ_faces_bolt_circle`, `pattern_circ_symmetric_holes`, `mirror_features_yz_fusion`,
  `mirror_body_join_face`, `mirror_body_new_body`, `mirror_faces_hole`, `mirror_fillet_feature`,
  `pattern_bodies_rect_new`, `pattern_path_bosses`, `pattern_path_circle_turned`,
  `pattern_symmetric_parameter`, `pattern_edit_quantity_fusion`, `pattern_rect_suppressed`,
  `pattern_circ_suppressed_bodies`, `pattern_sciforge_extrude`, `mirror_hole_and_its_pattern`,
  `pattern_quantity_parameter`, `pattern_rect_features_any_order`,
  `pattern_edit_keeps_later_fillet`.
- Unit tests: `SciForgeTests/unit/test_pattern_core.py`.
- modify-2 (2026-10-14): scenarios `modify2_pattern_adjust.py` (a wedge, a hole cut up To Object its slope, three copies: Optimized leaves them blind under the slope, Adjust takes each up to the slope where it lands, each copy measured; edit, Cancel, undo, save/reopen), `modify2_pattern_path.py` (an L path, Start Point 0.25 moves the copy, Start Point 1 refused, edit), `modify2_bodies.py` (the pattern of a cut through two bodies cuts both, undo, edit, save/reopen, timeline Delete). Golden models `modify2_pattern_adjust_to_slope`, `modify2_pattern_identical_to_slope`, `modify2_pattern_path_start_point`, `modify2_pattern_path_auto_start`, `modify2_pattern_multibody_cut`.

## Lessons for other dialogs

- FreeCAD reads a pattern spacing of exactly -1 as "use Offset": a symmetric walk of gaps must
  never contain -1 (it is moved by a nanometre).
- List properties take a whole-list expression (`list(Offset.Value; ...)`, plain numbers), not
  per-element expressions.
- A PartDesign body takes its base feature's shape *without* the shape's placement: bake the
  placement into the geometry (`transformShape(matrix, True)`) before handing a shape over.
- `Part::FeaturePython` outside a body that links into one needs the `...Global` link types,
  or FreeCAD prints "Link(s) ... go out of the allowed scope".
- A click on an overlay drawn over the part also selects the part on release: remember the
  overlay click and ignore the selection that follows (`OVERLAY_CLICK_S`).
- Keep the word "error" out of scenario step names: the harness reads it in the log line.
- PartDesign features already have a `Suppressed` (bool) property: a Python feature adding its
  own `Suppressed` list silently keeps the bool (SciForge uses `SuppressedCopies`).
- Rebuilding a step as a new object drops every link to it (FreeCAD clears links to a deleted
  object, silently): move them first (`pattern.relink_dependents`, faces found again by place).
- FreeCAD's pattern features return without touching their shape when nothing is left to
  repeat (`originals.empty()`): an App observer's `slotRecomputedObject` can set the shape
  right after (`pattern.OrphanWatch`); setting `Shape` there does not leave the step touched.
- A flat drag handle is a sliver when its plane is seen nearly edge-on, and a press that misses
  it lands on the part behind it: give handles some thickness in every direction, and never
  take the release after a press on a handle as a pick (`PatternPanel._button`).
- OpenCASCADE's Python errors print as "<unknown exception data>": catch them in a Python
  feature's `execute` and raise a sentence instead.

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
