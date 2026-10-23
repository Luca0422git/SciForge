# `get_drawing`: Get drawing

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > Drawings. Category: Drawings. Read-only. Needs a drawing.

## What it does

Describe drawings: each drawing's id, sheet, standard, units, title block values and views (id, kind, orientation, scale, position on the sheet, size) with their dimensions (value) and, with edges true, each view's elements (lines with ends, circles with centre and radius, in the view's own mm from its centre) for add_drawing_dimension.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `drawing` | string |  |  |  | one drawing (default: all) |
| `edges` | boolean |  | `false` |  | list each view's lines and circles |

## Answer

A plain sentence, then JSON with: `drawings`. The example below shows a real one.

## Errors

- Without a drawing: `The design has no drawing yet: call create_drawing first.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the sheet and its views

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
{"tool": "get_drawing", "args": {}}
```

The answer:

```text
{
 "drawings": [
  {
   "id": "Drawing",
   "label": "Example Drawing",
   "standard": "ISO",
   "sheet": "A3",
   "units": "mm",
   "sheet_size_mm": [
    420.0,
    297.0
   ],
   "title_block": {
    "ApprovedBy": "",
    "CheckedBy": "",
    "Date": "2026-10-22",
    "Description": "",
    "DrawnBy": "root",
    "Material": "Steel",
    "PartNumber": "Example",
    "Revision": "",
    "Scale": "",
    "Sheet": "1 / 1",
    "Size": "A3",
    "Title": "Example",
    "Units": "mm"
   },
   "views": [
    {
     "id": "BaseView",
     "label": "Base View",
     "kind": "BaseView",
     "orientation": "Front",
     "scale": 2.0,
     "at": [
      134.4,
      172.26
     ],
     "half_size_mm": [
      60.0,
      10.0
     ]
    },
    {
     "id": "ProjectedView",
     "label": "Top View",
     "kind": "ProjectedView",
     "orientation": "Front",
     "scale": 2.0,
     "at": [
      134.4,
      77.22
     ],
     "half_size_mm": [
      60.0,
      40.0
     ],
     "parent": "BaseView"
    },
    {
     "id": "ProjectedView001",
     "label": "Right View",
     "kind": "ProjectedView",
     "orientation": "Front",
     "scale": 2.0,
     "at": [
      0.0,
      172.26
     ],
     "half_size_mm": [
... (10 more lines)
```

## More argument examples

- views and their lines and circles:
  `{"edges": true}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
