# `set_model_parameter`: Set model parameter

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: MODIFY > Change Parameters > Model Parameters. Category: Parameters. Changes the design (one undo step). Its undo step is named like "AI: Extrude1 Distance". Needs an open design.

## What it does

Change a model parameter: one value of a step (label as list_parameters shows it: "Distance", "Radius", "Set 1 Size", "Quantity"...) or a sketch dimension (its name or label). value (mm / degrees / a count) or expression (a formula with user parameters, kept as a link). Everything after it updates.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `step` (required) | string |  |  |  | the step or sketch |
| `label` (required) | string |  |  |  | which of its values (from list_parameters) |
| `value` | number |  |  |  |  |
| `expression` | string |  |  |  | a formula |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: step is missing; label is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: drive the plate's thickness from the parameter gap

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "set_parameter", "args": {"name": "gap", "value": 2, "unit": "mm"}}
]
```

The call:

```json
{"tool": "set_model_parameter", "args": {"step": "Extrude1", "label": "Distance", "expression": "gap * 6"}}
```

The answer:

```text
Done: Extrude1 Distance = 12.0. Bodies now: Body1: 28800 mm3, 60 x 40 x 12 mm.
```

## More argument examples

- Extrude1's distance follows the parameter height:
  `{"step": "Extrude1", "label": "Distance", "expression": "height"}`

## See also

- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
