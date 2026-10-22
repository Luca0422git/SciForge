# `add_drawing_view`: Add drawing view

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: DRAWING > CREATE > Base View / Projected View / Section View / Detail View. Category: Drawings. Changes the design (one undo step). Its undo step is named like "AI: Projected view". Needs a drawing.

## What it does

Add a view to a drawing: kind base (orientation, at, scale, style), projected (parent view id, direction Top / Right / ... / FrontTopRight), section (parent, line [[x1, y1], [x2, y2]] in the parent view's own mm from its centre, side 1 | -1) or detail (parent, center [x, y] in the parent's mm, radius, scale). at: where on the sheet [x, y] mm.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `drawing` | string |  |  |  | the drawing (default: the newest) |
| `kind` (required) | `base` \| `projected` \| `section` \| `detail` |  |  |  |  |
| `parent` | string |  |  |  | the view it is made from |
| `orientation` | `Front` \| `Back` \| `Top` \| `Bottom` \| `Left` \| `Right` \| `Home` |  |  |  |  |
| `direction` | `Top` \| `Bottom` \| `Left` \| `Right` \| `FrontTopRight` \| `FrontTopLeft` \| `FrontBottomRight` \| `FrontBottomLeft` |  |  |  |  |
| `line` | array of 2 arrays |  |  |  | section line [[x1, y1], [x2, y2]] |
| `side` | integer |  |  |  | section: 1 looks from the left of the line's direction, -1 from the right (default: from where the view is placed) |
| `center` | array of 2 numbers | mm |  |  | detail centre [x, y] |
| `radius` | number | mm |  | > 0 | detail circle radius (mm) |
| `at` | array of 2 numbers | mm |  |  | [x, y] on the sheet (mm) |
| `scale` | number |  |  | > 0 |  |
| `style` | `Visible Edges` \| `Visible and Hidden Edges` \| `Shaded` \| `Shaded with Hidden Edges` |  |  |  |  |
| `label` | string |  |  |  | section / detail letter |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without a drawing: `The design has no drawing yet: call create_drawing first.`
- Called without arguments, the arguments are refused before anything runs: `Not done: kind is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: an isometric view projected from the base view

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
{"tool": "add_drawing_view", "args": {"kind": "projected", "parent": "BaseView", "direction": "FrontTopRight"}}
```

The answer:

```text
Done: projected view 'Isometric (top right) View' (id 'ProjectedView002') on Example Drawing.
```

## More argument examples

- a section through the middle of the base view:
  `{"kind": "section", "parent": "BaseView", "line": [[-50, 0], [50, 0]]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
