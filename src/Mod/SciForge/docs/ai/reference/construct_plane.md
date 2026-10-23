# `construct_plane`: Construction plane

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CONSTRUCT > (planes). Category: Construct. Changes the design (one undo step). Its undo step is named like "AI: Construction plane". Needs an open design.
It builds the design step(s) `construct` (the golden models' step language).

## What it does

Make a construction plane (Fusion's CONSTRUCT menu) the way its dialog does; it follows what it is built on when the part changes and other tools can use it (sketch on a plane with create_sketch on, pick it with {"construct": id}). preset and its refs: OffsetPlane: a plane or flat face (and, extent To Object, a point); PlaneAtAngle: a line (edge, sketch line or axis); TangentPlane: a round face; Midplane: two planes / flat faces; PlaneTwoEdges: two lines in one plane; PlaneThreePoints: three points; PlaneAtPoint: a face and a point; PlaneAlongPath: an edge or sketch curve. distance (mm, OffsetPlane), angle (degrees, PlaneAtAngle / TangentPlane), fraction (0..1 along the path), distance_type physical | proportional (along a path); points: where each face was clicked ([x, y, z] or null, per ref). (rules: [picks](sciforge://docs/tools.md#help-picks))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `preset` (required) | `OffsetPlane` \| `PlaneAtAngle` \| `TangentPlane` \| `Midplane` \| `PlaneTwoEdges` \| `PlaneThreePoints` \| `PlaneAtPoint` \| `PlaneAlongPath` |  |  |  |  |
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

## Example 1: a plane 25 mm above XY

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}}
]
```

The call:

```json
{"tool": "construct_plane", "args": {"preset": "OffsetPlane", "refs": [{"plane": "XY"}], "distance": 25}}
```

The answer:

```text
Done: AI: Construction plane. Its id is 'Plane'. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- a plane 25 mm above XY:
  `{"preset": "OffsetPlane", "refs": [{"plane": "XY"}], "distance": 25}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `inspect_angle_plane_notch`, `inspect_construct_all`, `inspect_midplane_hole`, `inspect_offset_plane_boss`, `inspect_offset_plane_to_object`, `inspect_three_points_oblique_hole`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
