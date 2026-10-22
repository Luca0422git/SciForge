# `replace_face`: Replace face

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Replace Face. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Replace face". Needs a solid body.
It builds the design step(s) `replace_face` (the golden models' step language).

## What it does

Fusion's Replace Face: move faces of a body onto a target (a plane or a face): faces (selector, of: the body's step), tangent_chain, target (a body pick: XY / XZ / YZ or {"face": selector, "of": id}).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` (required) | object |  |  |  | the faces to replace (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `of` | string |  |  |  | the body they are on |
| `tangent_chain` | boolean |  | `true` |  |  |
| `target` (required) | string or object |  |  |  | the new face (a body pick) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: faces is missing; target is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: raise the low box's top to the high box's top

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 20, "width": 20, "height": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 30, "length": 20, "width": 20, "height": 15, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "replace_face", "args": {"faces": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "of": "Primitive1", "target": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "of": "Primitive2"}}}
```

The answer:

```text
Done: AI: Replace face. Its id is 'ReplaceFace'. Bodies now: Body1: 6000 mm3, 20 x 20 x 15 mm; Body2: 6000 mm3, 20 x 20 x 15 mm.
```

## More argument examples

- move the top face up to another body's top:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "target": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude2"}}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_replace_face_edit_down`, `direct_replace_face_up_to_body`, `modify2_replace_face_cone`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
