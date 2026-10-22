# `press_pull`: Press pull

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Press Pull (Q). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Press Pull 5 mm". Needs a solid body.
It builds the design step(s) `press_pull`, `press_pull_type` (the golden models' step language).

## What it does

Fusion's Press Pull: push or pull faces by a distance (mm, negative pushes in), or give edges (they get a fillet of that radius), or fillet_face (a face a fillet made: that fillet's radius becomes distance). offset_type (faces): automatic (default), new (a new Press Pull step), modify (change the extrude that made the faces, no new step).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` | object |  |  |  | the faces to move (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `edges` | object |  |  |  | edges to round (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `fillet_face` | object |  |  |  | a face of a fillet (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `distance` (required) | number | mm |  |  | mm (a radius for edges / fillet faces) |
| `offset_type` | `automatic` \| `new` \| `modify` |  | `"automatic"` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: distance is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: pull the top face up 5 mm

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
{"tool": "press_pull", "args": {"faces": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "distance": 5}}
```

The answer:

```text
Done: AI: Press Pull 5 mm. Its id is 'PressPull1'. Bodies now: Body1: 36000 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- pull the top face up 5 mm:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "distance": 5}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `blend_fillet_presspull_radius`, `direct_history_off_on`, `direct_split_face_then_press_pull`, `fillet2_presspull_set_radius`, `pp_boss_grow`, `pp_edge_fillet`, `pp_edit_distance`, `pp_fillet_face_radius`, `pp_hole_grow`, `pp_hole_shrink`, `pp_multi_face_corner`, `pp_multi_face_push_corner` and 17 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
