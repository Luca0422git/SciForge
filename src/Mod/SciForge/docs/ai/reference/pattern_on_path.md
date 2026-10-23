# `pattern_on_path`: Pattern on path

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pattern > Pattern on Path. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Pattern on path". Needs a solid body.
It builds the design step(s) `path_pattern` (the golden models' step language).

## What it does

Fusion's Pattern on Path: repeat features, faces or the body along a sketch curve. path {"sketch": id} or {"sketch": id, "edge": n} (n-th curve, 1 = first); quantity; distance with distribution extent | spacing; direction_type one | symmetric; orientation identical (copies keep their direction) | path (they turn with the path); start_point 0..1 (where on the path it starts). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `features` | array of strings |  |  | at least 1 item(s) | Pattern Type Features: the steps to repeat |
| `faces` | object |  |  |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  |  |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  |  |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  |  |  | Compute Option |
| `path` (required) | object |  |  |  | {"sketch": id} or {"sketch": id, "edge": n} |
| `quantity` | integer | count | `2` | >= 1 |  |
| `distance` | number | mm | `20` |  | (mm) |
| `distribution` | `extent` \| `spacing` |  | `"extent"` |  |  |
| `direction_type` | `one` \| `symmetric` |  | `"one"` |  |  |
| `orientation` | `identical` \| `path` |  | `"identical"` |  |  |
| `start_point` | number |  |  | >= 0, <= 1 | 0 (start) .. 1 (end) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: three bosses along a line, 20 mm apart

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [10, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "offset": 10, "curves": [{"line": [10, 20, 50, 20]}]}}
]
```

The call:

```json
{"tool": "pattern_on_path", "args": {"features": ["Extrude2"], "path": {"sketch": "Sketch3"}, "quantity": 3, "distance": 20, "distribution": "spacing"}}
```

The answer:

```text
Done: AI: Pattern on path. Its id is 'Pattern1'. Bodies now: Body1: 25178.1 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- five copies along Sketch3's curve:
  `{"features": ["Extrude2"], "path": {"sketch": "Sketch3"}, "quantity": 5, "distance": 80}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `modify2_pattern_path_auto_start`, `modify2_pattern_path_start_point`, `pattern_path_bosses`, `pattern_path_circle_turned`, `surface4_pattern_path`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
