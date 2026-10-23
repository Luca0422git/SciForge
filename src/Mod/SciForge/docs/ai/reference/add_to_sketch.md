# `add_to_sketch`: Add to sketch

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > CREATE (Line, Rectangle, Circle, Arc, Polygon, Slot, Spline, Point). Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Draw in Sketch1". Needs an open design.

## What it does

Draw more in an existing sketch (Fusion: edit the sketch and draw): closed shapes (geometry, the same items as create_sketch, with their named dimensions) and open curves or points (curves, the same items as create_curve_sketch). construction: true draws construction geometry (dashed, it makes no area: guides for constraints and axes). Coordinates are the sketch's own x / y (see get_sketch). Everything built from the sketch updates. (rules: [geometry](sciforge://docs/tools.md#help-geometry)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch to draw in |
| `geometry` | array of objects |  |  | at least 1 item(s) | closed shapes |
| `curves` | array of objects |  |  | at least 1 item(s) | open curves and points |
| `construction` | boolean |  | `false` |  | construction geometry |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a named circle inside the rectangle

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "add_to_sketch", "args": {"sketch": "Sketch1", "geometry": [{"circle": [30, 20, 6], "name": "bore"}]}}
```

The answer:

```text
Done: AI: Draw in Sketch1. New curves 4 in Sketch1. No solid body yet.
```

## More argument examples

- a circle (bore.diameter) added to Sketch1:
  `{"sketch": "Sketch1", "geometry": [{"circle": [20, 10, 4], "name": "bore"}]}`
- a construction line (for example a revolve axis):
  `{"sketch": "Sketch1", "curves": [{"line": [0, -5, 0, 25]}], "construction": true}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
