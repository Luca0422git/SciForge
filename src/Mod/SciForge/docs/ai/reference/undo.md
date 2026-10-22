# `undo`: Undo

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: Quick Access Toolbar > Undo (Ctrl+Z). Category: Designs and files. Changes the open designs (not an undo step). Needs an open design.

## What it does

Undo the last change in SciForge (each AI change is one undo step).

## Arguments

No arguments.

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: take back the fillet

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 5}}
]
```

The call:

```json
{"tool": "undo", "args": {}}
```

The answer:

```text
Undo: AI: Fillet 5 mm. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- take back the last change:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
