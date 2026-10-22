# `save`: Save

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: Quick Access Toolbar > Save. Category: Designs and files. Writes files. Needs an open design.

## What it does

Save the design. Without path it is saved where it is (a new design asks for a place in SciForge). With path (a full path ending in .FCStd) it is saved there; saving over another existing file must be confirmed by the person in SciForge.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `path` | string |  |  |  |  |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: save again where it was saved

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "save_as", "args": {"path": "/home/me/sciforge/plate.FCStd"}}
]
```

The call:

```json
{"tool": "save", "args": {}}
```

The answer:

```text
Saved /home/me/sciforge/plate.FCStd.
```

## More argument examples

- save under that name:
  `{"path": "/home/me/designs/bracket.FCStd"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
