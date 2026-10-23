# `silhouette_split`: Silhouette split

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Silhouette Split. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Silhouette split". Needs a solid body.
It builds the design step(s) `silhouette_split` (the golden models' step language).

## What it does

Fusion's Silhouette Split: split a body along its outline seen from a direction. body (step id), direction (a body pick: a plane, face, edge or axis), operation faces (split the faces) | body (two bodies) | shelled (for a shelled part).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `body` (required) | string |  |  |  | the body |
| `direction` (required) | string or object |  |  |  | the view direction (a body pick) |
| `operation` | `faces` \| `body` \| `shelled` |  | `"faces"` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: body is missing; direction is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: split a ball into its top and bottom halves (its outline seen from Z)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "sphere", "plane": "XY", "diameter": 20}}
]
```

The call:

```json
{"tool": "silhouette_split", "args": {"body": "Primitive1", "direction": "Z", "operation": "body"}}
```

The answer:

```text
Done: AI: Silhouette split. Its id is 'SilhouetteSplit'. Bodies now: Body1: 2094.4 mm3, 20 x 20 x 10 mm; Body2: 2094.4 mm3, 20 x 20 x 10 mm.
```

## More argument examples

- split a round part into two halves seen from Z:
  `{"body": "Revolve1", "direction": "Z", "operation": "body"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_silhouette_body_sphere`, `direct_silhouette_edit_to_faces`, `direct_silhouette_faces_sphere`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
