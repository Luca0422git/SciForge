# `close_design`: Close design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > Close. Category: Designs and files. Changes the open designs (not an undo step), destructive. Needs an open design.

## What it does

Close a design (default: the active one). Unsaved changes are refused unless discard_changes is true (the person in SciForge is asked first).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `design` | string |  |  |  | the design's name (list_designs) |
| `discard_changes` | boolean |  | `false` |  | close even with unsaved changes |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: close a design that was never saved (a new design counts as changed)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_design", "args": {"name": "Second"}}
]
```

The call:

```json
{"tool": "close_design", "args": {"design": "Second", "discard_changes": true}}
```

The answer:

```text
Closed Second. No design is open now.
```

## More argument examples

- close the active design (it must be saved):
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
