# `delete_step`: Delete step

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > right-click a step > Delete. Category: Timeline (history). Changes the design (one undo step), destructive. Its undo step is named like "AI: Delete steps". Needs an open design.
It builds the design step(s) `delete` (the golden models' step language).

## What it does

Delete steps from the timeline (Fusion asks the same: steps that depend on them may break and are named in the answer). Undo brings them back.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `steps` (required) | array of strings |  |  | at least 1 item(s) | the steps |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: steps is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: delete the hole step

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
{"tool": "delete_step", "args": {"steps": ["Hole1"]}}
```

The answer:

```text
Deleted Hole1 (undo brings them back). Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- delete the chamfer:
  `{"steps": ["Chamfer1"]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `extrude_multi_cut_timeline`, `extrude_multi_join_delete`, `hole_second_survives_first`, `tl_delete_before_fillet`, `tl_delete_hole`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
