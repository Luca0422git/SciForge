# `rectangular_pattern`: Rectangular pattern

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pattern > Rectangular Pattern. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Rectangular pattern". Needs a solid body.
It builds the design step(s) `rectangular_pattern` (the golden models' step language).

## What it does

Fusion's Rectangular Pattern dialog: repeat features (step ids), faces or the whole body in rows. direction X | Y | Z, or {"edge": selector} / {"face": selector} (along a straight edge, or a flat face's normal); quantity (copies, the original counted); distance with distribution extent (the whole span) or spacing (between copies); direction_type one | symmetric; a second direction with direction2, quantity2, distance2, direction_type2; suppressed: copies left out. (rules: [expressions](sciforge://docs/tools.md#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `features` | array of strings |  |  | at least 1 item(s) | Pattern Type Features: the steps to repeat |
| `faces` | object |  |  |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  |  |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  |  |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  |  |  | Compute Option |
| `direction` (required) | string or object |  |  |  | X, Y, Z or a pick |
| `quantity` | integer | count | `2` | >= 1 |  |
| `distance` | number | mm |  |  | span or spacing (mm) |
| `distribution` | `extent` \| `spacing` |  | `"extent"` |  |  |
| `direction_type` | `one` \| `symmetric` |  | `"one"` |  |  |
| `direction2` | string or object |  |  |  | X, Y, Z or a pick |
| `quantity2` | integer | count |  | >= 1 |  |
| `distance2` | number | mm |  |  | (mm) |
| `direction_type2` | `one` \| `symmetric` |  |  |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: direction is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: three bosses spread over 40 mm

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [10, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "rectangular_pattern", "args": {"features": ["Extrude2"], "direction": "X", "quantity": 3, "distance": 40, "distribution": "extent"}}
```

The answer:

```text
Done: AI: Rectangular pattern. Its id is 'Pattern1'. Bodies now: Body1: 25178.1 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- four copies spread over 60 mm along X:
  `{"features": ["Extrude2"], "direction": "X", "quantity": 4, "distance": 60, "distribution": "extent"}`

## See also

- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `mirror_hole_and_its_pattern`, `modify2_pattern_adjust_to_slope`, `modify2_pattern_identical_to_slope`, `modify2_pattern_multibody_cut`, `pattern_bodies_in_moved_component`, `pattern_bodies_move_original_after`, `pattern_bodies_rect_new`, `pattern_edit_keeps_later_fillet`, `pattern_edit_quantity_fusion`, `pattern_quantity_parameter`, `pattern_rect_features_any_order`, `pattern_rect_hole_grid_fusion` and 4 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
