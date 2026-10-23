# `circular_pattern`: Circular pattern

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pattern > Circular Pattern. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Circular pattern". Needs a solid body.
It builds the design step(s) `circular_pattern` (the golden models' step language).

## What it does

Fusion's Circular Pattern dialog: repeat features, faces or the whole body around an axis: X | Y | Z, {"edge": selector} (a straight edge) or {"face": selector} (a round face's axis). quantity; type full (360 degrees) | angle (the total angle) | symmetric. (rules: [expressions](sciforge://docs/tools.md#help-expressions))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `features` | array of strings |  |  | at least 1 item(s) | Pattern Type Features: the steps to repeat |
| `faces` | object |  |  |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  |  |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  |  |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  |  |  | Compute Option |
| `axis` (required) | string or object |  |  |  | X, Y, Z or a pick |
| `quantity` | integer | count | `3` | >= 1 |  |
| `type` | `full` \| `angle` \| `symmetric` |  | `"full"` |  |  |
| `angle` | number | deg |  |  | total angle (degrees) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: axis is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: four bosses around the Z axis

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
{"tool": "circular_pattern", "args": {"features": ["Extrude2"], "axis": "Z", "quantity": 4}}
```

The answer:

```text
Done: AI: Circular pattern. Its id is 'Pattern1'. Bodies now: Body1: 25570.8 mm3, 85 x 65 x 15 mm.
```

## More argument examples

- eight holes around a round face's axis:
  `{"features": ["Hole1"], "axis": {"face": {"type": "cylinder", "radius": 20, "count": 1}}, "quantity": 8}`

## See also

- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `pattern_circ_faces_bolt_circle`, `pattern_circ_suppressed_bodies`, `pattern_circ_symmetric_holes`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
