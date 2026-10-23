# `render`: Render

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > Capture Image (returned to the AI as a picture). Category: View. Read-only. Needs an open design.

## What it does

Take a picture of the design and get the image itself (PNG), to look at what was built. view: iso (default: from front, right and top, as Fusion's Home view), front, back, top, bottom, left or right; or direction [x, y, z]: where the camera looks from. fit (default true) frames the whole design. highlight: {faces: selector, edges: selector, of: step id} marks those faces / edges in orange (check what a selector picks before using it). renderer: window (SciForge's own 3D view, as the person sees it), software (a simple picture of the solids drawn by SciForge itself: works without the window), auto (default: the window when there is one). Numbers from inspect_design / query_geometry are more exact than a picture: use both.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `view` | `iso` \| `front` \| `back` \| `top` \| `bottom` \| `left` \| `right` |  | `"iso"` |  |  |
| `direction` | array of 3 numbers |  |  |  | where the camera looks from |
| `width` | integer |  | `800` | >= 64, <= 2048 | picture width in pixels |
| `height` | integer |  | `600` | >= 64, <= 2048 | picture height in pixels |
| `fit` | boolean |  | `true` |  | frame the whole design |
| `highlight` | object |  |  |  | faces / edges to mark in orange |
| `highlight.faces` | object |  |  |  | the faces to mark (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `highlight.edges` | object |  |  |  | the edges to mark (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `highlight.of` | string |  |  |  | the body or step they belong to (default: the body worked on) |
| `edges` | boolean |  | `true` |  | draw the edges (software renderer) |
| `renderer` | `auto` \| `window` \| `software` |  | `"auto"` |  |  |

## Answer

A plain sentence, and the picture as a PNG image. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: an iso picture with the hole marked in orange

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
{"tool": "render", "args": {"width": 400, "height": 300, "highlight": {"faces": {"type": "cylinder"}}}}
```

The answer:

```text
A 400 x 300 picture of Example (iso view, software renderer); in orange: 1 faces of body Body; 1 pixel = 0.2009 mm.
```

With it, the picture itself: a 400 x 300 PNG (MCP image content).

## More argument examples

- an iso picture of the whole design, 800 x 600:
  `{}`
- from the top, the round faces (holes) in orange:
  `{"view": "top", "highlight": {"faces": {"type": "cylinder"}}}`
- a quick small picture:
  `{"renderer": "software", "width": 400, "height": 300}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
