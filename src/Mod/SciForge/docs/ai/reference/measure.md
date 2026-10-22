# `measure`: Measure

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSPECT > Measure. Category: Inspect and measure. Read-only. Needs an open design.

## What it does

Measure between two picks a and b of the current body or the origin: the minimum distance (mm) and, where it makes sense, the angle (degrees), like SciForge's Measure tool; also the X / Y / Z distances, the two nearest points and what each pick is (length, area, radius...). Only a: the size of that one pick (an edge's length and radius, a face's area and perimeter). (rules: [picks](sciforge://docs/tools.md#help-picks)) (rules: [selectors](sciforge://docs/tools.md#help-selectors))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `a` (required) | object |  |  |  | the first pick. (rules: [picks](sciforge://docs/tools.md#help-picks)) |
| `b` | object |  |  |  | the second pick (optional). (rules: [picks](sciforge://docs/tools.md#help-picks)) |

## Answer

A plain sentence, then JSON with: `a`, `b`, `distance_mm`, `angle_deg`, `delta_mm`, `nearest_points_mm`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: a is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the height of the top face above the XY plane

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

The call:

```json
{"tool": "measure", "args": {"a": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}}, "b": {"plane": "XY"}}}
```

The answer:

```text
Measured: distance 10 mm, angle 0 degrees.
{
 "a": {"kind": "face", "properties": {"area_mm2": 2349.734518, "perimeter_mm": 200.0}},
 "b": {"kind": "plane", "properties": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0}},
 "distance_mm": 10.0,
 "angle_deg": 0.0,
 "delta_mm": [0.0, 0.0, 10.0],
 "nearest_points_mm": [[0.0, 0.0, 10.0], [0.0, 0.0, 0.0]]
}
```

## Example 2: the size of one pick: the hole's round face

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

The call:

```json
{"tool": "measure", "args": {"a": {"face": {"type": "cylinder", "count": 1}}}}
```

The answer:

```text
Measured a (face): area 251.327 mm2, radius 4 mm, diameter 8 mm, perimeter 50.2655 mm.
{
 "a": {
  "kind": "face",
  "properties": {"area_mm2": 251.327412, "radius_mm": 4.0, "diameter_mm": 8.0, "perimeter_mm": 50.265482}
 }
}
```

## More argument examples

- the height of the top face above the XY plane:
  `{"a": {"face": {"normal": [0, 0, 1], "count": 1}}, "b": {"plane": "XY"}}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
