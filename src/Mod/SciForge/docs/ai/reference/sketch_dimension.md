# `sketch_dimension`: Sketch dimension

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > CREATE > Sketch Dimension (D). Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Distance dimension". Needs an open design.

## What it does

Add a driving dimension to a sketch, like Fusion's Sketch Dimension: distance (between two points, a point and a line, or one line's length), distance_x / distance_y (horizontal / vertical), radius, diameter, angle (between two lines, or of one line to the x axis). value in mm or degrees, or expression: a formula with parameters ("width / 2"). name names it for set_sketch_dimension and expressions. A dimension that over-constrains the sketch is refused with the constraints it conflicts with.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `kind` (required) | `distance` \| `distance_x` \| `distance_y` \| `radius` \| `diameter` \| `angle` |  |  |  |  |
| `items` (required) | array of objects |  |  | at least 1 item(s), at most 2 item(s) | the curves / points measured |
| `value` | number | mm or deg |  |  | mm (lengths) or degrees (angles) |
| `expression` | string |  |  |  | a formula instead of value, e.g. width / 2 |
| `name` | string |  |  |  | a name, e.g. slot.width |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; kind is missing; items is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.
- A constraint or dimension that conflicts with the sketch, or that the sketch already says, is not added (a new value it cannot take is not set): the answer names the constraints it fights or repeats, as the sketch tools do in the window (`Vertical: not added, it conflicts with the 50 mm dimension 'len' (constraint 1 of Sketch1: ...).`, `..., the 50 mm dimension 'len' already makes it so ...`, `That value does not fit: it conflicts with ...`). See [sketches](sciforge://docs/sketches.md#constraints-and-dimensions).

## Example 1: a 50 mm dimension on the first line, named len

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 40, 2]}, {"line": [40, 2, 40, 30]}]}}
]
```

The call:

```json
{"tool": "sketch_dimension", "args": {"sketch": "Sketch1", "kind": "distance", "items": [{"curve": 0}], "value": 50, "name": "len"}}
```

The answer:

```text
Done: AI: Distance dimension, constraint 0 of Sketch1 = 50.00 mm. No solid body yet.
```

## More argument examples

- circle 4 is 8 mm across:
  `{"sketch": "Sketch1", "kind": "diameter", "items": [{"curve": 4}], "value": 8, "name": "bore.diameter"}`
- the circle's centre at half the width:
  `{"sketch": "Sketch1", "kind": "distance_x", "items": [{"curve": -1, "point": "start"}, {"curve": 4, "point": "center"}], "expression": "width / 2"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
