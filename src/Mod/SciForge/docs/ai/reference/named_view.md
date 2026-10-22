# `named_view`: Named view

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > Named Views (New Named View, go to, delete). Category: View. Changes the design (one undo step). Its undo step is named like "AI: Named view ". Needs an open design.

## What it does

Named views kept in the design (Fusion's Named Views): action save (the current camera under name), go (turn the view to it), delete, list.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `action` (required) | `save` \| `go` \| `delete` \| `list` |  |  |  |  |
| `name` | string |  |  |  | the view's name |

## Answer

A plain sentence, then JSON with: `named_views`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: action is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the design's named views

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}}
]
```

The call:

```json
{"tool": "named_view", "args": {"action": "list"}}
```

The answer:

```text
{
 "named_views": []
}
```

## More argument examples

- remember this camera:
  `{"action": "save", "name": "Assembly view"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
