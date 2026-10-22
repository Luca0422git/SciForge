# `delete_bodies`: Delete bodies

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > a body > Delete. Category: Modify. Changes the design (one undo step), destructive. Its undo step is named like "AI: Delete bodies". Needs an open design.
It builds the design step(s) `delete_bodies` (the golden models' step language).

## What it does

Delete bodies (picked in the browser, then Delete): they are gone from the whole history; what used them keeps working where it can. bodies: step ids.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` (required) | array of strings |  |  | at least 1 item(s) | the bodies to delete |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: bodies is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: delete the box's body and its steps

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 40, "y": 10, "length": 40, "width": 20, "height": 20, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "delete_bodies", "args": {"bodies": ["Primitive1"]}}
```

The answer:

```text
Done: AI: Delete bodies. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- delete Extrude3's body:
  `{"bodies": ["Extrude3"]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `bodies_combine_new_body_target_deleted`, `bodies_combine_tool_deleted`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
