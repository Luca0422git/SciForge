# `sketch_text`: Text

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > CREATE > Text. Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Text 'SF'". Needs an open design.

## What it does

Write text in a sketch (Fusion's sketch Text): its letters become areas you can extrude (profile: the text's id) or emboss. corner is the frame's top-left corner in sketch coordinates, height the letter height (mm); font a font family installed on the computer (default: SciForge's), bold, italic, angle (degrees), h_align left | center | right, v_align top | middle | bottom, width / frame_height: the text frame (0: fits the text), spacing (extra letter spacing).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch to write in |
| `text` (required) | string |  |  |  | the text |
| `height` | number | mm | `5` | > 0 | letter height (mm) |
| `corner` | array of 2 numbers | mm |  |  | the frame's top-left corner [x, y] |
| `font` | string |  |  |  | a font family |
| `bold` | boolean |  | `false` |  |  |
| `italic` | boolean |  | `false` |  |  |
| `angle` | number | deg | `0` |  | degrees |
| `h_align` | `left` \| `center` \| `right` |  | `"left"` |  |  |
| `v_align` | `top` \| `middle` \| `bottom` |  | `"top"` |  |  |
| `width` | number | mm |  | >= 0 | frame width (mm, 0: fits the text) |
| `frame_height` | number | mm |  | >= 0 | frame height (mm, 0: fits the text) |
| `spacing` | number | mm |  |  | extra letter spacing |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; text is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the letters SF, 8 mm high

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "sketch_text", "args": {"sketch": "Sketch1", "text": "SF", "height": 8, "corner": [5, 5]}}
```

The answer:

```text
Done: AI: Text 'SF'. Its id is 'Text1': extrude it with profile 'Text1'. No solid body yet.
```

## More argument examples

- a 6 mm high text; extrude it with profile = the text's id:
  `{"sketch": "Sketch2", "text": "SciForge", "height": 6, "corner": [2, 18]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
