# Parity spec: Rectangular Pattern, Circular Pattern, Pattern on Path, Mirror (outline 7.6)

Source: Fusion's documented behaviour (public help topics on the pattern commands and Mirror)
and everyday use. Not yet checked against Luca's own screen captures (outline 2.4); the
choices marked **(assumed)** below need his confirmation. Implemented in
`src/Mod/SciForge/sciforge/pattern_ui.py` (dialogs, commands, pickers), `mirror_ui.py`
(Mirror's command), `pattern.py` (the document side, no GUI) and `pattern_core.py` (where the
copies go, pure Python). Status: **first pass, not yet signed off**.

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
| Pattern Type Faces / Bodies / Features / Components | Faces, Bodies, Features. Components greyed (SciForge has no components) |
| Objects: click features in the timeline (Features) | Same; a click on a face in the view takes the feature that made it; a sketch is refused with the reason |
| Selection boxes: blue while they take the clicks, click one to make it active, x clears | Same |
| Direction: an edge, an axis, a flat face (its normal) | Same; the origin X / Y / Z axes are drawn while a direction or axis box waits and can be clicked where the part does not hide them |
| Direction 2 offered at right angles | **(assumed)** After Direction 1 SciForge offers the origin axis (or an edge of the part) at right angles in the floor plane, Quantity 1 |
| Quantity, Distance, Distribution Extent / Spacing, Direction Type One Direction / Symmetric, per direction | Same. Extent: the distance from the original to the last copy; Spacing: the gap. A negative distance goes the other way. **Symmetric (assumed):** the quantity counts each side, the original shared (Quantity 3 gives 5 in a row), the distance is measured on each side |
| Circular: Axis (an axis, an edge, a round face's axis), Type Full / Angle / Symmetric, Quantity, Total Angle | Same. Angle: Quantity copies from the original to Total Angle (360 = Full). **Symmetric (assumed):** Quantity and Total Angle per side. Switching to Angle starts at 180 deg, Symmetric at 90 |
| Pattern on Path: Path (an edge or sketch curve), Distance, Quantity, Distribution, Direction Type, Orientation Identical / Path Direction | Same. The copies start at the point of the path nearest to the objects; closed paths go round; Path Direction turns the copies with the path (about the path's plane). Running off an open path's end is said in the dialog |
| Mirror: Objects, Mirror Plane (origin plane, flat face, construction plane), Operation for bodies | Same. The origin planes are the big squares of Create Sketch; a square in front of the part takes the click, the part takes it where it is in front |
| Values take parameters and formulas | Same for the distances, the angle and the quantities; a symmetric pattern's gaps are expressions of its spacing, so the copies follow a parameter change. A quantity that follows a parameter is rounded to a whole number; a pattern with one is built by SciForge's `PatternFeature` (FreeCAD's features cannot change their number of copies from a parameter); the arrows of the Quantity box make it a plain number again. A pattern of bodies takes a plain number (each copy is a body) |
| Live preview of the copies | Same (FreeCAD's feature, recomputed 60 ms after a change) |
| Blue arrows to drag the distances; a handle for the angle | One blue arrow per direction (Rectangular), one along the path (Path), a curved one for Total Angle (Circular, Angle/Symmetric, up to 180 deg by dragging; type larger angles). Drawn on top of the part |
| Errors shown in the dialog, OK waits | Same; nothing is printed to the Report view while the dialog is open |
| OK / Enter, Cancel / Esc, one undo step, Ctrl+Z in the dialog cancels it | Same |
| Double-click in the timeline edits it | Same (all four kinds, every Pattern Type) |
| Deleting a pattern of bodies deletes its bodies | Same (they go a moment later, as their own undo step) |
| Suppression: a dot on every copy, click one to leave that copy out | Same for Rectangular, Circular and Path patterns (dots drawn over the part; a left-out copy's dot turns grey; clicking it again puts the copy back; unticking Suppression makes every copy again). FreeCAD's pattern features cannot leave a copy out, so a pattern with suppressed copies is built by SciForge's `PatternFeature` (same result otherwise); a pattern of bodies simply makes fewer bodies |

## Known gaps (never faked: shown greyed with the reason, or listed here)

| Fusion option | Why not yet |
|---|---|
| Compute Option Optimized / Adjust | Copies are identical (FreeCAD repeats the feature's tool). Shown greyed |
| Pattern Type Components | SciForge has no components yet |
| Faces: copies "heal" into different surroundings | The closed faces are copied as they are (a hole copied into a thicker area stays as deep as the original). Faces that do not close up with one face around each opening (a fillet's face) are refused with the reason |
| A pattern of bodies whose references lie in another body with a moved placement | The references are read in the copied body's coordinates |
| Pattern on Path: an explicit start point | The copies start at the point of the path nearest to the objects |
| Timeline icon of Pattern on Path | Shown with the generic icon and the name "Pattern On Path" (the timeline module has no entry for it yet) |

## Tests

- Scenarios (real clicks, keys, drags; any Report-view error fails them):
  `patterns_rect.py`, `patterns_circ.py`, `patterns_mirror.py`, `patterns_path.py`,
  `patterns_suppress.py`, `patterns_params.py`, `patterns_qa.py` (wrong picks, Ctrl+Z in the dialog, type switch, timeline delete of a body
  pattern, save and reopen). Volumes and positions checked with hand-derived formulas.
- Golden models (ops `rectangular_pattern`, `circular_pattern`, `path_pattern`,
  `fusion_mirror`, `pattern_edit` in `golden/pattern_ops.py`, the dialogs' code):
  `pattern_rect_hole_grid_fusion`, `pattern_rect_symmetric_bosses`,
  `pattern_circ_faces_bolt_circle`, `pattern_circ_symmetric_holes`, `mirror_features_yz_fusion`,
  `mirror_body_join_face`, `mirror_body_new_body`, `mirror_faces_hole`, `mirror_fillet_feature`,
  `pattern_bodies_rect_new`, `pattern_path_bosses`, `pattern_path_circle_turned`,
  `pattern_symmetric_parameter`, `pattern_edit_quantity_fusion`, `pattern_rect_suppressed`,
  `pattern_circ_suppressed_bodies`, `pattern_sciforge_extrude`, `mirror_hole_and_its_pattern`,
  `pattern_quantity_parameter`.
- Unit tests: `SciForgeTests/unit/test_pattern_core.py`.

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
