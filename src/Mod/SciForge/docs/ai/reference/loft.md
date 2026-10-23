# `loft`: Loft

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Loft. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Loft". Needs an open design.
It builds the design step(s) `sf_loft` (the golden models' step language).

## What it does

Loft through profiles in order (Fusion's Loft). Each profile is {"profile": sketch id} (its one area, else the whole sketch), {"profile": id, "region": [x, y]} (one area), {"face": selector} or {"point": {"sketch": id, "at": [x, y]}} (a sketch point, first or last only). rails: guide rails (each a curves spec), or centerline: one centre line. closed: the loft comes back to the first profile. start_* / end_*: Fusion's end conditions of the first / last profile (free, direction, tangent, curvature, point_tangent) with weight 0.1..2 and angle. merge: merge tangent edges. operation, bodies. (rules: [curves](sciforge://docs/tools.md#help-curves))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `profiles` (required) | array of objects |  |  | at least 2 item(s) | in loft order |
| `rails` | array of string or objects |  |  | at least 1 item(s) | guide rails |
| `centerline` | string or object |  |  |  | a centre line (curves) |
| `guide` | `rails` \| `centerline` |  | `"rails"` |  |  |
| `closed` | boolean |  | `false` |  |  |
| `merge` | boolean |  | `false` |  | merge tangent edges |
| `start_condition` | `free` \| `direction` \| `tangent` \| `curvature` \| `point_tangent` |  | `"free"` |  |  |
| `start_weight` | number |  | `1` | >= 0.1, <= 2 | how strongly the start condition pulls (0.1..2) |
| `start_angle` | number | deg | `0` |  | (degrees) |
| `end_condition` | `free` \| `direction` \| `tangent` \| `curvature` \| `point_tangent` |  | `"free"` |  |  |
| `end_weight` | number |  | `1` | >= 0.1, <= 2 | how strongly the end condition pulls (0.1..2) |
| `end_angle` | number | deg | `0` |  | (degrees) |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` |  | `"auto"` |  | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `bodies` | string or array |  |  |  | Objects To Cut: "auto" (every body in the way) or a list of step ids |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: profiles is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: from a square to a circle 25 mm higher

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"center_rect": [0, 0, 30, 30]}]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 25, "geometry": [{"circle": [0, 0, 10]}]}}
]
```

The call:

```json
{"tool": "loft", "args": {"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"}]}}
```

The answer:

```text
Done: AI: Loft. Its id is 'Loft1'. Bodies now: Body1: 14619.6 mm3, 30 x 30 x 25 mm.
```

## More argument examples

- a loft from a square to a circle on an offset plane:
  `{"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"}]}`

## See also

- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `sf_loft_centerline_ends`, `sf_loft_centerline_torus`, `sf_loft_closed_direction`, `sf_loft_cone_point`, `sf_loft_cut_cone`, `sf_loft_cut_two_bodies`, `sf_loft_edit_intersect`, `sf_loft_ends_direction`, `sf_loft_ends_direction_weight`, `sf_loft_ends_dome`, `sf_loft_ends_face_curvature`, `sf_loft_ends_face_tangent` and 10 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
