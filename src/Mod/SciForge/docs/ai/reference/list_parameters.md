# `list_parameters`: List parameters

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: MODIFY > Change Parameters. Category: Parameters. Read-only. Needs an open design.

## What it does

List the design's parameters, as Change Parameters shows them: user parameters (name, unit, formula, value, comment), parameters brought in by a Derive (read-only), and model parameters: every dimension in the design (each step's values and each sketch dimension: the step id, its label, value, unit and formula).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `model` | boolean |  | `true` |  | include the model parameters |

## Answer

A plain sentence, then JSON with: `user`, `model`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: every parameter

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
{"tool": "list_parameters", "args": {}}
```

The answer:

```text
{
 "user": [
  {
   "name": "gap",
   "unit": "mm",
   "expression": "",
   "value": 2.0,
   "comment": ""
  }
 ],
 "model": [
  {
   "step": "Sketch1",
   "step_label": "Sketch1",
   "label": "base.width",
   "value": 60.0,
   "unit": "mm",
   "expression": ""
  },
  {
   "step": "Sketch1",
   "step_label": "Sketch1",
   "label": "base.height",
   "value": 40.0,
   "unit": "mm",
   "expression": ""
  },
  {
   "step": "Sketch1",
   "step_label": "Sketch1",
   "label": "base.x",
   "value": 0.0,
   "unit": "mm",
   "expression": ""
  },
  {
   "step": "Sketch1",
   "step_label": "Sketch1",
   "label": "base.y",
   "value": 0.0,
   "unit": "mm",
   "expression": ""
  },
  {
   "step": "Extrude1",
   "step_label": "Extrude1",
   "label": "Distance",
   "value": 10.0,
   "unit": "mm",
   "expression": ""
  },
  {
   "step": "Extrude1",
   "step_label": "Extrude1",
   "label": "Taper",
   "value": 0.0,
   "unit": "deg",
   "expression": ""
  }
 ]
}
```

## More argument examples

- every parameter and dimension:
  `{}`

## See also

- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
