# `construct_point`: Construction point

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CONSTRUCT > (points). Category: Construct. Changes the design (one undo step). Its undo step is named like "AI: Construction point". Needs an open design.
It builds the design step(s) `construct` (the golden models' step language).

## What it does

Make a construction point (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}). preset and its refs: PointVertex: a corner or sketch point; PointTwoEdges: two edges that cross; PointThreePlanes: three planes / flat faces; PointCenter: a circular edge or a ball; PointEdgePlane: an edge and a plane it crosses; PointAlongPath: an edge or sketch curve. distance (mm, OffsetPlane), angle (degrees, PlaneAtAngle / TangentPlane), fraction (0..1 along the path), distance_type physical | proportional (along a path); points: where each face was clicked ([x, y, z] or null, per ref). (rules: [picks](sciforge://docs/tools.md#help-picks))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `preset` (required) | `PointVertex` \| `PointTwoEdges` \| `PointThreePlanes` \| `PointCenter` \| `PointEdgePlane` \| `PointAlongPath` |  |  |  |  |
| `refs` (required) | array of objects |  |  | at least 1 item(s), at most 3 item(s) | what it is built on, in order |
| `distance` | number | mm |  |  | OffsetPlane distance (mm) |
| `angle` | number | deg |  |  | PlaneAtAngle / TangentPlane (degrees) |
| `fraction` | number | 0..1 |  | >= 0, <= 1 | 0..1 along a path |
| `distance_type` | `physical` \| `proportional` |  |  |  |  |
| `points` | array of array or nulls |  |  |  | per ref: the point clicked on a face, or null |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: preset is missing; refs is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a point at the centre of the hole's top edge

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
{"tool": "construct_point", "args": {"preset": "PointCenter", "refs": [{"edge": {"type": "circle", "at": {"axis": "z", "value": "max"}, "count": 1}}]}}
```

The answer:

```text
Done: AI: Construction point. Its id is 'Point'. Bodies now: Body1: 23497.3 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- the centre of a circular edge:
  `{"preset": "PointCenter", "refs": [{"edge": {"type": "circle", "count": 1}}]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `inspect_angle_plane_notch`, `inspect_construct_all`, `inspect_midplane_hole`, `inspect_offset_plane_boss`, `inspect_offset_plane_to_object`, `inspect_three_points_oblique_hole`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
