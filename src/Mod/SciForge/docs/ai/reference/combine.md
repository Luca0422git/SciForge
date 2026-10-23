# `combine`: Combine

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Combine. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Combine (cut)". Needs an open design.
It builds the design step(s) `combine` (the golden models' step language).

## What it does

Fusion's Combine: join, cut or intersect bodies. target: the body kept (a step id of it); tools: the bodies used (step ids). keep_tools keeps them; new_body / new_component puts the result in a new body / component.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `target` (required) | string |  |  |  | the target body (a step in it) |
| `tools` (required) | array of strings |  |  | at least 1 item(s) | the tool bodies |
| `operation` | `join` \| `cut` \| `intersect` |  | `"join"` |  |  |
| `new_body` | boolean |  | `false` |  |  |
| `new_component` | boolean |  | `false` |  |  |
| `keep_tools` | boolean |  | `false` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: target is missing; tools is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: cut the box out of the plate

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
{"tool": "combine", "args": {"target": "Extrude1", "tools": ["Primitive1"], "operation": "cut"}}
```

The answer:

```text
Done: AI: Combine (cut). Its id is 'Combine'. Bodies now: Body1: 20000 mm3, 60 x 40 x 10 mm; Body2: 16000 mm3, 40 x 20 x 20 mm.
```

## More argument examples

- cut Extrude2's body out of Extrude1's:
  `{"target": "Extrude1", "tools": ["Extrude2"], "operation": "cut"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `bodies_combine_cut`, `bodies_combine_cut_cylinder`, `bodies_combine_edit_operation`, `bodies_combine_follows_tool`, `bodies_combine_intersect`, `bodies_combine_join`, `bodies_combine_new_body`, `bodies_combine_new_body_target_deleted`, `bodies_combine_new_component`, `bodies_combine_tool_deleted`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
