# `set_parameter`: Set parameter

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: MODIFY > Change Parameters (User Parameters, +). Category: Parameters. Changes the design (one undo step). Its undo step is named like "AI: Parameter thickness = 12". Needs nothing.
It builds the design step(s) `parameter` (the golden models' step language).

## What it does

Create or change a user parameter (SciForge's Change Parameters). value is a number or an expression using other parameters, e.g. "width / 4". unit: mm (default), deg or empty for a plain number. Everything that uses the parameter updates.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `name` (required) | string |  |  |  | letters, digits and _ |
| `value` (required) | number or string |  |  |  |  |
| `unit` | string |  | `"mm"` |  |  |
| `comment` | string |  |  |  | a note shown in Change Parameters |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: name is missing; value is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a user parameter

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
{"tool": "set_parameter", "args": {"name": "thickness", "value": 12, "unit": "mm"}}
```

The answer:

```text
Done: AI: Parameter thickness = 12. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- width follows depth:
  `{"name": "width", "value": "depth * 2", "unit": "mm"}`

## See also

- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `param_driven_box`, `pattern_quantity_parameter`, `pattern_symmetric_parameter`, `sf_box_param_driven`, `sf_coil_param_driven`, `sf_coil_taper_height_pitch_param`, `sf_coil_taper_param_driven`, `sf_coil_taper_rev_pitch_param`, `sf_pipe_param_driven`, `sf_sweep_distance_parameter`, `sf_sweep_taper_parameter`, `sf_torus_param_driven`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
