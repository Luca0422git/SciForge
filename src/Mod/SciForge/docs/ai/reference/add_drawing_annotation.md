# `add_drawing_annotation`: Add drawing annotation

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: DRAWING > TEXT / TABLES / SYMBOLS (Text, Table (parts list), Center Mark). Category: Drawings. Changes the design (one undo step). Its undo step is named like "AI: Drawing text". Needs a drawing.

## What it does

Add to a drawing: kind text (text lines at [x, y], size mm), parts_list (a table of the view's components with balloons, at = its top-left corner) or center_marks (a centre mark on every circle of a view).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `drawing` | string |  |  |  | the drawing (default: the newest) |
| `kind` (required) | `text` \| `parts_list` \| `center_marks` |  |  |  |  |
| `text` | string |  |  |  | text (new lines split it) |
| `size` | number | mm | `3.5` | > 0 | text height (mm) |
| `view` | string |  |  |  | parts list / centre marks: the view |
| `at` | array of 2 numbers | mm |  |  | [x, y] on the sheet (mm) |
| `balloons` | boolean |  | `true` |  | parts list: balloons on the view |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without a drawing: `The design has no drawing yet: call create_drawing first.`
- Called without arguments, the arguments are refused before anything runs: `Not done: kind is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a note on the sheet

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
{"tool": "add_drawing_annotation", "args": {"kind": "text", "text": "Break all sharp edges", "at": [20, 40]}}
```

The answer:

```text
Done: text on Example Drawing (id 'Text').
```

## More argument examples

- a note on the sheet:
  `{"kind": "text", "text": "Break all sharp edges", "at": [20, 40]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
