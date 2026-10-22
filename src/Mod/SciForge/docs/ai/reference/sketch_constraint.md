# `sketch_constraint`: Sketch constraint

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > CONSTRAINTS. Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Horizontal constraint". Needs an open design.

## What it does

Add a geometric constraint to a sketch, as Fusion's Constraints panel: coincident (two points, or a point on a curve), horizontal / vertical (a line, or two points), parallel, perpendicular, tangent, equal, collinear (two lines), concentric (two circles or arcs), midpoint (a point and a line or arc), symmetric (two points or curves and the line they mirror about, third), fix (lock a curve or point), point_on (a point on a curve), smooth (G2 where a spline meets a curve; tangent only when the solver cannot keep curvature). items are curves by index (get_sketch) with the point that matters. A constraint that conflicts with the sketch is not added: the answer names the constraints it fights with.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `kind` (required) | `coincident` \| `horizontal` \| `vertical` \| `parallel` \| `perpendicular` \| `tangent` \| `equal` \| `symmetric` \| `concentric` \| `collinear` \| `midpoint` \| `fix` \| `point_on` \| `smooth` |  |  |  |  |
| `items` (required) | array of objects |  |  | at least 1 item(s), at most 3 item(s) | the curves / points it ties, in order |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; kind is missing; items is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: make the first line horizontal

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 40, 2]}, {"line": [40, 2, 40, 30]}]}}
]
```

The call:

```json
{"tool": "sketch_constraint", "args": {"sketch": "Sketch1", "kind": "horizontal", "items": [{"curve": 0}]}}
```

The answer:

```text
Done: AI: Horizontal constraint, constraint 0 of Sketch1. No solid body yet.
```

## More argument examples

- make line 0 horizontal:
  `{"sketch": "Sketch1", "kind": "horizontal", "items": [{"curve": 0}]}`
- put circle 4's centre on the sketch origin:
  `{"sketch": "Sketch1", "kind": "coincident", "items": [{"curve": 4, "point": "center"}, {"curve": -1, "point": "start"}]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
