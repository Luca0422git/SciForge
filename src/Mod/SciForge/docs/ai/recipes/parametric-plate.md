# Recipe: parametric mounting plate

Tags: parameters, parametric, expressions, set_parameter, set_sketch_dimension, set_model_parameter, rectangular_pattern, design-intent

A mounting plate whose size, thickness and hole positions are driven by named parameters,
so one change updates everything, like Fusion's Change Parameters. Every call was run by
SciForge's tests; `expect` is what the answer must contain.

## 1. The parameters

[set_parameter](sciforge://docs/reference/set_parameter.md) creates (or changes) a user parameter;
`unit` is mm by default. A value may be a formula of other parameters.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Plate"}},
  {"tool": "set_parameter", "args": {"name": "width", "value": 80}},
  {"tool": "set_parameter", "args": {"name": "depth", "value": 50}},
  {"tool": "set_parameter", "args": {"name": "thickness", "value": 6}},
  {"tool": "set_parameter", "args": {"name": "margin", "value": 8}},
  {"tool": "set_parameter", "args": {"name": "hole_d", "value": 5.5,
    "comment": "M5 clearance"}},
  {"tool": "list_parameters", "args": {}, "expect": {"contains": ["width", "hole_d"]}}
]
```

## 2. The plate follows width, depth and thickness

A rectangle drawn with `"name": "plate"` has the dimensions `plate.width` and
`plate.height`; [set_sketch_dimension](sciforge://docs/reference/set_sketch_dimension.md) with
`expression` ties them to the parameters. The extrude's distance is its model parameter
`Distance` (list_parameters shows every model parameter's label):
[set_model_parameter](sciforge://docs/reference/set_model_parameter.md) ties it to `thickness`.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [
    {"rect": [0, 0, 80, 50], "name": "plate"}]}},
  {"tool": "set_sketch_dimension", "args": {"sketch": "Sketch1", "constraint": "plate.width",
    "expression": "width"}},
  {"tool": "set_sketch_dimension", "args": {"sketch": "Sketch1", "constraint": "plate.height",
    "expression": "depth"}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 6},
   "expect": {"contains": ["24000 mm3"]}},
  {"tool": "set_model_parameter", "args": {"step": "Extrude1", "label": "Distance",
    "expression": "thickness"}}
]
```

## 3. Four holes that keep their margin

The hole sketch is on the plate's top face (`face`), not on an offset origin plane: a sketch
on a face moves with the face when `thickness` changes, a sketch on XY with `offset` 6 would
stay at z = 6. On the top face the sketch's x / y are the design's X / Y. One hole at
(margin, margin), then a rectangular pattern in two directions whose distances are formulas
(`expressions`), so the holes stay `margin` from every edge. Four holes of 5.5 mm through 6
mm remove 4 x pi x 2.75^2 x 6 = 570.2 mm3.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z",
    "value": "max"}, "count": 1}, "geometry": [{"circle": [8, 8, 2.75], "name": "h"}]}},
  {"tool": "set_sketch_dimension", "args": {"sketch": "Sketch2", "constraint": "h.x",
    "expression": "margin"}},
  {"tool": "set_sketch_dimension", "args": {"sketch": "Sketch2", "constraint": "h.y",
    "expression": "margin"}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 5.5, "through_all": true},
   "expect": {"contains": ["Its id is 'Hole1'"]}},
  {"tool": "set_model_parameter", "args": {"step": "Hole1", "label": "Diameter",
    "expression": "hole_d"}},
  {"tool": "rectangular_pattern", "args": {"features": ["Hole1"], "direction": "X",
    "quantity": 2, "distance": 64, "direction2": "Y", "quantity2": 2, "distance2": 34,
    "expressions": {"distance": "width - 2 * margin", "distance2": "depth - 2 * margin"}},
   "expect": {"contains": ["23429.8 mm3"]}},
  {"tool": "inspect_design", "args": {}, "expect": {"json": {"snapshot": "S1"}}}
]
```

## 4. Change one parameter, check everything followed

Make the plate 100 wide: the volume becomes 100 x 50 x 6 - 570.2 = 29429.8 mm3 and the far
holes move to x = 92 (100 - margin). [diff_design](sciforge://docs/reference/diff_design.md) since the
snapshot shows what changed; [query_geometry](sciforge://docs/reference/query_geometry.md) shows where
the holes are now.

```json sciforge-calls
[
  {"tool": "set_parameter", "args": {"name": "width", "value": 100},
   "expect": {"contains": ["29429.8 mm3", "100 x 50 x 6 mm"]}},
  {"tool": "diff_design", "args": {"since": "S1"},
   "expect": {"json": {"bodies.changed.0.volume_mm3.after": [29429.8, 0.01]}}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 2.75,
    "at": {"axis": "x", "value": "max"}}},
   "expect": {"json": {"count": 2, "elements.0.center_mm.0": [92, 0.0001]}}},
  {"tool": "set_parameter", "args": {"name": "thickness", "value": 10},
   "expect": {"contains": ["49049.7 mm3", "100 x 50 x 10 mm"]}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 2.75}},
   "expect": {"json": {"count": 4, "elements.0.bbox_mm.5": [10, 0.0001]}}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

After `thickness` became 10 the holes still go through the whole plate (their top is at
z = 10, and the volume is 100 x 50 x 10 - 4 x pi x 2.75^2 x 10 = 49049.7 mm3): the hole
sketch followed the top face.

## Variations

- `make_parametric` (an MCP prompt) walks an AI through doing this to an existing design.
- Parameters can drive patterns' `quantity` too (a count, no unit: `unit: ""`).
