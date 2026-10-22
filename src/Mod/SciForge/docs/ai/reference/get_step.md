# `get_step`: Get step

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > double-click a step (the dialog's fields). Category: Timeline (history). Read-only. Needs an open design.

## What it does

Read one step's definition, the way its dialog shows it when you double-click it: its kind and every option (distances, angles, operation, what it is built on), the formulas that drive values, its status and what it uses. The names of the options are the ones edit_step takes.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `step` (required) | string |  |  |  | the step |

## Answer

A plain sentence, then JSON with: `id`, `label`, `type`, `kind`, `name`, `state`, `status`, `suppressed`, `uses`, `definition`, `values`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: step is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: every option of the extrude

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
{"tool": "get_step", "args": {"step": "Extrude1"}}
```

The answer:

```text
{
 "id": "Extrude1",
 "label": "Extrude1",
 "type": "PartDesign::Pad",
 "kind": "extrude",
 "name": "Extrude 1",
 "state": "done",
 "status": "ok",
 "suppressed": false,
 "uses": [
  "Sketch1"
 ],
 "definition": {
  "profiles": [
   "Sketch1"
  ],
  "options": {
   "operation": "join",
   "start": "profile",
   "start_offset": 0.0,
   "start_object": null,
   "direction": "one_side",
   "extent": "distance",
   "distance": 10.0,
   "extent_object": null,
   "extend": "",
   "object_offset": 0.0,
   "taper": 0.0,
   "extent2": "distance",
   "distance2": 10.0,
   "extent_object2": null,
   "extend2": "",
   "object_offset2": 0.0,
   "taper2": 0.0,
   "measurement": "whole",
   "flip": false,
   "bodies": null,
   "thin": false,
   "wall_location": "side1",
   "wall_thickness": 1.0,
   "wall_location2": "side1",
   "wall_thickness2": 1.0,
   "expressions": {}
  }
 },
 "values": {
  "Distance": 10.0,
  "Taper": 0.0
 }
}
```

## More argument examples

- Extrude1's options:
  `{"step": "Extrude1"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
