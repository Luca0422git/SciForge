# `split_body`: Split body

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Split Body. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Split body". Needs a solid body.
It builds the design step(s) `split_body` (the golden models' step language).

## What it does

Fusion's Split Body: cut a body into pieces (new bodies). body: the body (a step id); tool: XY | XZ | YZ, {"face": selector, "of": step id} (a face, of another body with of), {"body": step id} or {"sketch": id, "edge": n} (a sketch curve, cut straight through); tools: several at once. extend (default true): the splitting face is extended.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `body` (required) | string |  |  |  | the body to split |
| `tool` | string or object |  |  |  | the splitting tool |
| `tools` | array of string or objects |  |  | at least 1 item(s) | several splitting tools |
| `extend` | boolean |  | `true` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: body is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: split a cylinder in two halves at the YZ plane

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [{"rect": [0, 0, 10, 20]}]}},
  {"tool": "revolve", "args": {"profile": "Sketch1", "axis": "Z"}}
]
```

The call:

```json
{"tool": "split_body", "args": {"body": "Revolve1", "tool": "YZ"}}
```

The answer:

```text
Done: AI: Split body. Its id is 'SplitBody'. Bodies now: Body1: 3141.59 mm3, 10 x 20 x 20 mm; Body2: 3141.59 mm3, 10 x 20 x 20 mm.
```

## More argument examples

- split the body in two at YZ:
  `{"body": "Extrude1", "tool": "YZ"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `bodies_split_by_body`, `bodies_split_edit_tool`, `bodies_split_face_extended`, `bodies_split_sketch_line`, `bodies_split_two_planes`, `bodies_split_yz`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
