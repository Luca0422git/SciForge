# `section_analysis`: Section analysis

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSPECT > Section Analysis. Category: Inspect and measure. Read-only. Needs a solid body.

## What it does

Cut the design with a plane to look inside (Fusion's Section Analysis): plane (a pick: an origin plane or a flat face), distance (offset, mm), x_angle / y_angle (tilt, degrees), flip. Answers the volume kept (on the side the plane's normal points away from) and the area of the cut faces; nothing is left in the design.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` (required) | object |  |  |  | the section plane. (rules: [picks](sciforge://docs/tools.md#help-picks)) |
| `distance` | number | mm | `0` |  | (mm) |
| `x_angle` | number | deg | `0` |  | (degrees) |
| `y_angle` | number | deg | `0` |  | (degrees) |
| `flip` | boolean |  | `false` |  |  |

## Answer

A plain sentence, then JSON with: `plane_point_mm`, `plane_normal`, `bodies`. The example below shows a real one.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: plane is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a cut through the hole, 20 mm from XZ

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
{"tool": "section_analysis", "args": {"plane": {"plane": "XZ"}, "distance": 20}}
```

The answer:

```text
Section: 23497.3 mm3 kept, 0 mm2 of cut faces.
{
 "plane_point_mm": [
  0.0,
  -20.0,
  0.0
 ],
 "plane_normal": [
  0.0,
  -1.0,
  0.0
 ],
 "bodies": [
  {
   "body": "Body",
   "kept_volume_mm3": 23497.345175,
   "cut_area_mm2": 0.0
  }
 ]
}
```

## More argument examples

- a cut 5 mm from XZ:
  `{"plane": {"plane": "XZ"}, "distance": 5}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
