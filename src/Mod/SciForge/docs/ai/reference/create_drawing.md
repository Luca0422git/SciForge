# `create_drawing`: Create drawing

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > New Drawing > From Design. Category: Drawings. Changes the design (one undo step). Its undo step is named like "AI: New drawing". Needs a solid body.

## What it does

Make a 2D drawing of the design (Fusion's New Drawing From Design), kept in the design and updated with it: bodies (step ids, default every visible body), standard ISO | ASME, sheet (A4..A0 for ISO, A..E for ASME), units mm | in, title_block; a base view (base_view orientation Front, Back, Top, Bottom, Left, Right or Home (isometric), at [x, y] on the sheet in mm from the bottom left, scale, style) and projected views (projected: Top, Right, FrontTopRight... placed next to it). Answers the drawing's and views' ids.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies to draw (default: every visible body) |
| `standard` | `ISO` \| `ASME` |  | `"ISO"` |  |  |
| `sheet` | string |  |  |  | A4, A3, A2, A1, A0 (ISO) or A, B, C, D, E (ASME) |
| `units` | `mm` \| `in` |  | `"mm"` |  |  |
| `title_block` | boolean |  | `true` |  |  |
| `label` | string |  |  |  | the drawing's name |
| `base_view` | `Front` \| `Back` \| `Top` \| `Bottom` \| `Left` \| `Right` \| `Home` |  | `"Front"` |  | the base view's orientation |
| `at` | array of 2 numbers | mm |  |  | [x, y] of the base view on the sheet (mm) |
| `scale` | number |  |  | > 0 | view scale (default: fits the sheet) |
| `style` | `Visible Edges` \| `Visible and Hidden Edges` \| `Shaded` \| `Shaded with Hidden Edges` |  | `"Visible and Hidden Edges"` |  |  |
| `projected` | array of strings |  |  |  | projected views to add |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: three views and an isometric

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

The call:

```json
{"tool": "create_drawing", "args": {"base_view": "Front", "projected": ["Top", "Right", "FrontTopRight"]}}
```

The answer:

```text
Done: drawing 'Example Drawing' (id 'Drawing') on a ISO A3 sheet, scale 2:1; views BaseView (Base View), ProjectedView (Top View), ProjectedView001 (Right View), ProjectedView002 (Isometric (top right) View).
```

## More argument examples

- the classic three views plus an isometric:
  `{"base_view": "Front", "projected": ["Top", "Right", "FrontTopRight"]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
