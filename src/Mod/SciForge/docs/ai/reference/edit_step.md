# `edit_step`: Edit step

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > double-click a step > change its fields > OK. Category: Timeline (history). Changes the design (one undo step). Its undo step is named like "AI: Edit Extrude1". Needs an open design.
It builds the design step(s) `edit`, `sf_revolve_edit`, `pattern_edit`, `sf_shell_edit`, `sf_draft_edit`, `sf_draft2_edit`, `sf_scale_edit`, `sf_scale_sketch_edit`, `body_tool_edit`, `blend_edit`, `sf_primitive_edit`, `sf_sweep_edit`, `sf_loft_edit`, `sf_rib_edit`, `sf_surface_edit`, `modify_edit`, `move_face_edit`, `sf_gear_edit`, `sf_hardware_edit` (the golden models' step language).

## What it does

Change an existing step's options, as double-clicking it in the timeline: set {option: value} with the names get_step shows (extrude: distance, distance2, taper, direction, operation, through_all...; revolve: angle, type, direction, operation; fillet / chamfer: radius, distance...; hole: diameter, depth, extent, hole_type...; patterns: quantity, distance, angle...; shell, draft, scale, sweep, loft, rib, primitives, coil, pipe, gear, hardware, emboss, thread, surface, combine, split, move, align, construction planes...). A fillet or chamfer also takes add_edges / add_faces (more edges). The steps after it update and keep their faces and edges; steps that break are named in the answer.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `step` (required) | string |  |  |  | the step to change |
| `set` | object |  |  |  | {option: value} |
| `add_edges` | object |  |  |  | fillet / chamfer: more edges (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `add_faces` | object |  |  |  | fillet / chamfer: every edge around more faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: step is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.
- A size that does not fit (a radius, distance, thickness or angle in `set`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: make the plate 15 mm thick (the hole follows)

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
{"tool": "edit_step", "args": {"step": "Extrude1", "set": {"distance": 15}}}
```

The answer:

```text
Done: AI: Edit Extrude1. Bodies now: Body1: 35497.3 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- make the extrude 15 mm:
  `{"step": "Extrude1", "set": {"distance": 15}}`
- change the fillet to 2 mm:
  `{"step": "Fillet1", "set": {"radius": 2}}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `blend_fillet_edit_radius`, `bodies_combine_follows_tool`, `comp_paste_instance_follows`, `comp_paste_new_independent`, `edit_extrude_then_shell`, `edit_fillet_radius`, `edit_pattern_count`, `edit_width_after_fillet_and_hole`, `extrude_multi_cut_edit`, `extrude_multi_cut_profile_body_excluded`, `extrude_multi_cut_reopen`, `extrude_start_object_follows` and 57 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
