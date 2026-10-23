# `split_face`: Split face

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Split Face. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Split face". Needs a solid body.
It builds the design step(s) `split_face` (the golden models' step language).

## What it does

Fusion's Split Face: split faces of a body with a tool, so they can be drafted or coloured on their own. faces (selector, of: the body's step), tool: a body pick, extend, split_type surface | vector (along direction) | closest. (rules: [body_picks](sciforge://docs/tools.md#help-body_picks))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` (required) | object |  |  |  | the faces to split (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `of` | string |  |  |  | the body the faces are on (default: the current one) |
| `tool` (required) | string or object |  |  |  | the splitting tool (a body pick) |
| `extend` | boolean |  | `false` |  |  |
| `split_type` | `surface` \| `vector` \| `closest` |  | `"surface"` |  |  |
| `direction` | string or object |  |  |  | split_type vector: the direction (a body pick) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: faces is missing; tool is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: split the cylinder's round face in two at the XZ plane

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
{"tool": "split_face", "args": {"faces": {"type": "cylinder", "count": 1}, "tool": "XZ"}}
```

The answer:

```text
Done: AI: Split face. Its id is 'SplitFace'. Bodies now: Body1: 6283.19 mm3, 20 x 20 x 20 mm.
```

## More argument examples

- split the side walls at the XY plane:
  `{"faces": {"along": [0, 0, 1], "count": 4}, "tool": "XY"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_split_face_closest_point`, `direct_split_face_extend`, `direct_split_face_then_press_pull`, `direct_split_face_yz`, `surface4_split_face_merge`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
