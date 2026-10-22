# `sketch_delete`: Delete in sketch

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > select > Delete. Category: Sketch. Changes the design (one undo step), destructive. Its undo step is named like "AI: Delete in sketch". Needs an open design.

## What it does

Delete curves and / or constraints of a sketch by their indexes (get_sketch). Deleting a curve deletes the constraints on it too. Indexes after the deleted ones move down: call get_sketch again before the next edit.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `curves` | array of integers |  |  | at least 1 item(s) | curve indexes |
| `constraints` | array of integers |  |  | at least 1 item(s) | constraint indexes |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: delete the second line

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 40, 2]}, {"line": [40, 2, 40, 30]}]}}
]
```

The call:

```json
{"tool": "sketch_delete", "args": {"sketch": "Sketch1", "curves": [1]}}
```

The answer:

```text
Done: deleted 1 curve(s) and 0 constraint(s) of Sketch1. Indexes have moved: call get_sketch again. No solid body yet.
```

## More argument examples

- delete curve 3:
  `{"sketch": "Sketch1", "curves": [3]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
