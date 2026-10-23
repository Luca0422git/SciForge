# `delete_parameter`: Delete parameter

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: MODIFY > Change Parameters > a user parameter > Delete. Category: Parameters. Changes the design (one undo step), destructive. Its undo step is named like "AI: Delete parameter gap". Needs an open design.

## What it does

Delete a user parameter. Refused, with the names, while formulas still use it.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `name` (required) | string |  |  |  | the parameter |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: name is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: delete an unused parameter

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "set_parameter", "args": {"name": "gap", "value": 2, "unit": "mm"}}
]
```

The call:

```json
{"tool": "delete_parameter", "args": {"name": "gap"}}
```

The answer:

```text
Deleted the parameter gap.
```

## More argument examples

- delete the unused parameter gap:
  `{"name": "gap"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
