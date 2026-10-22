# `add_drawing_dimension`: Add drawing dimension

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: DRAWING > DIMENSIONS > Dimension. Category: Drawings. Changes the design (one undo step). Its undo step is named like "AI: Drawing dimension". Needs a drawing.

## What it does

Dimension a drawing view, as Fusion's Dimension command does from what is clicked: one line (its length, horizontal / vertical / aligned), one circle (diameter) or arc (radius), two points / lines (the distance or angle between them). picks: the view's elements, each {kind: line | circle | arc | vertex, near: [x, y] in the view's own mm from its centre (get_drawing lists the elements), radius}; type forces a kind of dimension (linear, aligned, radius, diameter, angular); at: where the text goes on the sheet [x, y] mm. Answers the measured value.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `view` (required) | string |  |  |  | the view |
| `picks` (required) | array of objects |  |  | at least 1 item(s), at most 2 item(s) | one or two elements |
| `type` | `linear` \| `aligned` \| `radius` \| `diameter` \| `angular` |  |  |  |  |
| `at` | array of 2 numbers | mm |  |  | text position on the sheet (mm) |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without a drawing: `The design has no drawing yet: call create_drawing first.`
- Called without arguments, the arguments are refused before anything runs: `Not done: view is missing; picks is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the length of the line nearest to (0, 5) in the base view

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
{"tool": "add_drawing_dimension", "args": {"view": "BaseView", "picks": [{"kind": "line", "near": [0, 5]}]}}
```

The answer:

```text
Done: DistanceX dimension 'Dimension' on Base View: 60.
```

## More argument examples

- the diameter of the 6 mm hole:
  `{"view": "BaseView", "picks": [{"kind": "circle", "radius": 3}]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
