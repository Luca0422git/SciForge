# `revolve`: Revolve

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Revolve. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Revolve 360 degrees". Needs an open design.
It builds the design step(s) `sf_revolve` (the golden models' step language).

## What it does

Revolve a sketch's areas around an axis (SciForge's Revolve). axis: X, Y or Z (origin axes) or sketch_h / sketch_v (the sketch's own horizontal or vertical axis). angle in degrees, 360 (default) for a full turn. regions picks areas by a point inside each, as for extrude. operation auto (default) lets SciForge choose like its Revolve dialog does. More of the dialog: face (a flat face as the profile), axis {"sketch": id, "at": [x, y]} (the sketch line through that point), {"sketch": id, "construction": [[x1, y1], [x2, y2]]} (a construction line drawn for it), {"edge": selector} (a straight edge of the part); type angle | to | full, to (a pick it revolves up to), direction one_side | two_sides | symmetric, angle2 (side two), bodies.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `profile` | string |  |  |  | id of a create_sketch step |
| `regions` | array of arrays |  |  | at least 1 item(s) |  |
| `axis` (required) | string or object |  |  |  | X, Y, Z, sketch_h, sketch_v or an axis object (see above) |
| `angle` | number | deg | `360` | > 0, <= 360 |  |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` |  | `"auto"` |  |  |
| `face` | object |  |  |  | instead of profile: a flat face of the part as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `type` | `angle` \| `to` \| `full` |  |  |  | angle (default with an angle), full or to |
| `to` | object |  |  |  | type to: what the revolve goes up to. (rules: [picks](sciforge://docs/tools.md#help-picks)) |
| `direction` | `one_side` \| `two_sides` \| `symmetric` |  | `"one_side"` |  |  |
| `angle2` | number | deg |  | > 0, <= 360 | side two's angle (degrees) |
| `bodies` | string or array |  |  |  | "auto": every body the feature passes through is cut / joined (what the dialog lists by itself); or a list of step ids: exactly those bodies (the dialog's "Bodies to Cut" row) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: axis is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a full turn about Z: a ring

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [{"rect": [10, 0, 20, 10]}]}}
]
```

The call:

```json
{"tool": "revolve", "args": {"profile": "Sketch1", "axis": "Z"}}
```

The answer:

```text
Done: AI: Revolve 360 degrees. Its id is 'Revolve1'. Bodies now: Body1: 9424.78 mm3, 40 x 40 x 10 mm.
```

## More argument examples

- a full turn about the Z axis:
  `{"profile": "Sketch1", "axis": "Z"}`
- a quarter turn about a straight edge of the part:
  `{"profile": "Sketch1", "axis": {"edge": {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "min"}, "count": 1}}, "angle": 90}`

## See also

- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `modify2_replace_face_cone`, `sf_revolve_cone`, `sf_revolve_construction_follows`, `sf_revolve_cut_other_body`, `sf_revolve_cut_two_bodies`, `sf_revolve_cylinder`, `sf_revolve_edit_operation`, `sf_revolve_face_edge`, `sf_revolve_face_profile_follows`, `sf_revolve_groove_auto_cut`, `sf_revolve_intersect`, `sf_revolve_new_body_construction` and 8 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
