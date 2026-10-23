# `open_design`: Open design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > Open. Category: Designs and files. Changes which design is open or active, changes no design. Needs nothing.

## What it does

Open a design (.FCStd) or a STEP / IGES file as a new design (its components and bodies kept). A design that is already open comes to the front. It becomes the active design. For a STEP / IGES file the answer also lists what the file had that did not come in or came in changed ("Not brought in, or changed:" and one line each: loose faces, curves and points, surface bodies, bodies with geometry errors).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `path` (required) | string |  |  |  | full path of the file |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: open a saved design (already open here: it is switched to)

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
{"tool": "open_design", "args": {"path": "/home/me/sciforge/plate.FCStd"}}
```

The answer:

```text
Opened /home/me/sciforge/plate.FCStd as design 'plate' (id 'Example'). Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- open a saved design:
  `{"path": "/home/me/designs/bracket.FCStd"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
