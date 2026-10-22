# `set_sketch_dimension`: Set sketch dimension

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > double-click a dimension (or MODIFY > Change Parameters, Model Parameters). Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: base.width = 80". Needs an open design.
It builds the design step(s) `edit` (the golden models' step language).

## What it does

Change a sketch dimension: by its name (rectangles made by create_sketch with a name have <name>.width, <name>.height, <name>.x, <name>.y; circles <name>.diameter, <name>.x, <name>.y) or by its index (get_sketch). value in mm / degrees, or expression (a formula with parameters; an empty expression removes the formula). Everything built from the sketch updates; steps that break are named in the answer.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `constraint` | string |  |  |  | the dimension's name, e.g. base.width |
| `index` | integer |  |  | >= 0 | the constraint's index (get_sketch) |
| `value` | number | deg |  |  | mm or degrees |
| `expression` | string |  |  |  | a formula, e.g. width * 2 |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.
- A constraint or dimension that conflicts with the sketch, or that the sketch already says, is not added (a new value it cannot take is not set): the answer names the constraints it fights or repeats, as the sketch tools do in the window (`Vertical: not added, it conflicts with the 50 mm dimension 'len' (constraint 1 of Sketch1: ...).`, `..., the 50 mm dimension 'len' already makes it so ...`, `That value does not fit: it conflicts with ...`). See [sketches](sciforge://docs/sketches.md#constraints-and-dimensions).

## Example 1: make the plate 80 mm wide (the extrude follows)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}}
]
```

The call:

```json
{"tool": "set_sketch_dimension", "args": {"sketch": "Sketch1", "constraint": "base.width", "value": 80}}
```

The answer:

```text
Done: base.width = 80.00 mm. Bodies now: Body1: 32000 mm3, 80 x 40 x 10 mm.
```

## More argument examples

- make the rectangle 60 mm wide:
  `{"sketch": "Sketch1", "constraint": "base.width", "value": 60}`

## See also

- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `blend_fillet_edit_radius`, `bodies_combine_follows_tool`, `comp_paste_instance_follows`, `comp_paste_new_independent`, `edit_extrude_then_shell`, `edit_fillet_radius`, `edit_pattern_count`, `edit_width_after_fillet_and_hole`, `extrude_multi_cut_edit`, `extrude_multi_cut_profile_body_excluded`, `extrude_multi_cut_reopen`, `extrude_start_object_follows` and 19 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
