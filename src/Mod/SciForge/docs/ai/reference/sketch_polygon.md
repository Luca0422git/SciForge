# `sketch_polygon`: Polygon

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > CREATE > Polygon > Circumscribed / Inscribed Polygon. Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Polygon". Needs an open design.
It builds the design step(s) `sketch_polygon` (the golden models' step language).

## What it does

Add a regular polygon to a sketch, Fusion's way: center and point, where point is the middle of an edge (circumscribed, default) or a corner (inscribed). diameter dimensions it (across flats when circumscribed, across corners when inscribed), named <name>.diameter. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `center` (required) | array of 2 numbers | mm |  |  | [x, y] in sketch coordinates (mm) |
| `point` (required) | array of 2 numbers | mm |  |  | the middle of an edge (circumscribed) or a corner (inscribed) |
| `sides` (required) | integer | count |  | >= 3 | number of sides |
| `circumscribed` | boolean |  | `true` |  | point is the middle of an edge |
| `diameter` | number | mm |  | > 0 | across flats / corners, mm |
| `name` | string |  |  |  | names its dimension <name>.diameter |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; center is missing; point is missing; sides is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a hexagon 10 mm across the corners

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "sketch_polygon", "args": {"sketch": "Sketch1", "center": [30, 20], "point": [35, 20], "sides": 6, "diameter": 10, "name": "nut"}}
```

The answer:

```text
Done: AI: Polygon. No solid body yet.
```

## More argument examples

- a hexagon 10 mm across flats:
  `{"sketch": "Sketch1", "center": [0, 0], "point": [5, 0], "sides": 6, "diameter": 10, "name": "nut"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sketch_inscribed_pentagon`, `sketch_nut_trap_polygon`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
