# `delete_face`: Delete face

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Delete (faces). Category: Modify. Changes the design (one undo step), destructive. Its undo step is named like "AI: Delete face". Needs a solid body.
It builds the design step(s) `delete_face` (the golden models' step language).

## What it does

Delete faces of the current body (Fusion: select faces, Delete): the gap heals, as when a fillet or a hole is removed.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` (required) | object |  |  |  | the faces to delete (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: faces is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: delete the hole (the solid heals)

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
{"tool": "delete_face", "args": {"faces": {"type": "cylinder", "count": 1}}}
```

The answer:

```text
Done: AI: Delete face. Its id is 'DeleteFace'. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- remove a 6 mm hole's wall: the hole is gone:
  `{"faces": {"type": "cylinder", "radius": 3, "count": 1}}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `bodies_delete_face_fillet`, `bodies_delete_face_hole`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
