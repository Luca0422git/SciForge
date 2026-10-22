# `export_drawing`: Export drawing

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: DRAWING > EXPORT > Output PDF / Output DXF. Category: Drawings. Writes files. Needs a drawing.

## What it does

Export a drawing: format pdf (every sheet in one PDF; needs the SciForge window) or dxf (the sheet: frame, views on their own layers, dimensions, text). Replacing an existing file must be confirmed by the person in SciForge. The answer lists what the file does not keep ("Not kept in this file:": other sheets, dimensions written as plain lines and text, hatching as lines, the font...), as the drawing's Export message does.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `drawing` | string |  |  |  | the drawing (default: the newest) |
| `format` (required) | `pdf` \| `dxf` |  |  |  |  |
| `path` (required) | string |  |  |  | full path |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without a drawing: `The design has no drawing yet: call create_drawing first.`
- Called without arguments, the arguments are refused before anything runs: `Not done: format is missing; path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the drawing as DXF (PDF needs the window)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}},
  {"tool": "create_drawing", "args": {"base_view": "Front", "projected": ["Top", "Right"]}}
]
```

The call:

```json
{"tool": "export_drawing", "args": {"format": "dxf", "path": "/home/me/sciforge/plate.dxf"}}
```

The answer:

```text
Exported Example Drawing to /home/me/sciforge/plate.dxf.
```

## More argument examples

- a PDF of the drawing:
  `{"format": "pdf", "path": "/home/me/bracket.pdf"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
