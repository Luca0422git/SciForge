# `mirror`: Mirror

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Mirror. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Mirror". Needs a solid body.
It builds the design step(s) `fusion_mirror` (the golden models' step language).

## What it does

Fusion's Mirror: mirror features, faces or the whole body about a plane: XY | XZ | YZ or {"face": selector} (a flat face of the part). A body mirror takes operation join (one body with the original) or new_body.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `features` | array of strings |  |  | at least 1 item(s) | Pattern Type Features: the steps to repeat |
| `faces` | object |  |  |  | Pattern Type Faces: faces of the part to repeat (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `body` | boolean |  |  |  | Pattern Type Bodies: the whole current body (the copies are new bodies) |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |
| `suppressed` | array of integers |  |  |  | copies left out, by their number among the copies (Suppression) |
| `compute` | `optimized` \| `identical` \| `adjust` |  |  |  | Compute Option |
| `plane` (required) | string or object |  |  |  | XY, XZ, YZ or {"face": selector} |
| `operation` | `join` \| `new_body` |  | `"new_body"` |  | body mirror only |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: plane is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: mirror the boss about the XZ plane (y = 0: the copy lands outside the plate)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [10, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "mirror", "args": {"features": ["Extrude2"], "plane": "XZ"}}
```

The answer:

```text
Done: AI: Mirror. Its id is 'Mirror1'. Bodies now: Body1: 24785.4 mm3, 60 x 65 x 15 mm.
```

## More argument examples

- mirror the whole body about YZ into one body:
  `{"body": true, "plane": "YZ", "operation": "join"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `mirror_body_join_face`, `mirror_body_new_body`, `mirror_body_new_body_move_after`, `mirror_faces_hole`, `mirror_features_yz_fusion`, `mirror_fillet_feature`, `mirror_hole_and_its_pattern`, `modify2_mirror_adjust_to_slope`, `surface4_mirror_join_scale`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
