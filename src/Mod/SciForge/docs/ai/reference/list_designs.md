# `list_designs`: List designs

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: the design tabs. Category: Designs and files. Read-only. Needs nothing.

## What it does

List the open designs: name, label, file, whether it has unsaved changes and which one is active.

## Arguments

No arguments.

## Answer

A plain sentence, then JSON with: `designs`. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the open designs

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
{"tool": "list_designs", "args": {}}
```

The answer:

```text
{
 "designs": [
  {
   "id": "Example",
   "name": "Example",
   "file": null,
   "unsaved_changes": true,
   "active": false
  },
  {
   "id": "Second",
   "name": "Second",
   "file": null,
   "unsaved_changes": true,
   "active": true
  }
 ]
}
```

## More argument examples

- which designs are open:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
