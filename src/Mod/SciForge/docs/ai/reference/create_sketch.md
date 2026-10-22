# `create_sketch`: Create sketch

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Create Sketch. Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Sketch on XY". Needs nothing.
It builds the design step(s) `sketch` (the golden models' step language).

## What it does

Create a sketch with closed shapes (and lines) in it, ready for extrude, revolve or hole. It becomes one timeline step; its id is the profile for the next tools. (rules: [sketches](sciforge://docs/tools.md#help-sketches)) (rules: [geometry](sciforge://docs/tools.md#help-geometry)) on: the id of a construction plane (construct_plane) to sketch on instead. auto_project (with face): the face's edges are projected into the sketch, as Fusion does. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` | `XY` \| `XZ` \| `YZ` |  |  |  |  |
| `offset` | number | mm | `0` |  | mm along the plane's normal |
| `face` | object |  |  |  | Instead of plane: the flat face to sketch on (one face). (rules: [selectors](sciforge://docs/tools.md#help-selectors)) |
| `on` | string |  |  |  | Instead of plane: the id of a construction plane to sketch on |
| `auto_project` | boolean |  |  |  | with face: project the face's edges into the sketch |
| `geometry` (required) | array of objects |  |  | at least 1 item(s) | (rules: [geometry](sciforge://docs/tools.md#help-geometry)) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: geometry is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a 60 x 40 rectangle on XY whose dimensions are named base.width / base.height

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
```

The answer:

```text
Done: AI: Sketch on XY. Its id is 'Sketch1'. No solid body yet.
```

## Example 2: a circle on the plate's top face

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
{"tool": "create_sketch", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "geometry": [{"circle": [30, 20, 5]}]}}
```

The answer:

```text
Done: AI: Sketch on face. Its id is 'Sketch2'. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- a 40 x 20 mm rectangle on the XY plane, its sizes named base.width / base.height:
  `{"plane": "XY", "geometry": [{"rect": [0, 0, 40, 20], "name": "base"}]}`
- a 6 mm circle 10 mm above XY (on top of a 10 mm thick part):
  `{"plane": "XY", "offset": 10, "geometry": [{"circle": [20, 10, 3]}]}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- Recipe: [threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `blend_chamfer_angle`, `blend_chamfer_top_face`, `blend_chamfer_two_flip`, `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature`, `blend_fillet_edit_radius`, `blend_fillet_presspull_radius`, `blend_fillet_slot_chain`, `blend_fillet_top_face`, `blend_insert_chamfer_before_fillet`, `bodies_combine_cut`, `bodies_combine_cut_cylinder` and 377 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
