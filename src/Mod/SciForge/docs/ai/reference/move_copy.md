# `move_copy`: Move / copy

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Move/Copy (M). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Move". Needs an open design.
It builds the design step(s) `move_bodies`, `move_face`, `component_move` (the golden models' step language).

## What it does

Fusion's Move/Copy. What moves: bodies (step ids), faces (a selector: the faces move, the body follows) or components (component ids). move_type free (dx dy dz and rotations rx ry rz about pivot), translate (dx, dy, dz), rotate (angle about axis X / Y / Z through pivot), point_to_point (from_point to to_point), point_to_position (from_point goes to px, py, pz). copy: move a copy (bodies). capture (components): record the move as a timeline step (Capture Position). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies |
| `faces` | object |  |  |  | the faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `components` | array of strings |  |  | at least 1 item(s) | the components |
| `move_type` | `free` \| `translate` \| `rotate` \| `point_to_point` \| `point_to_position` |  |  |  |  |
| `dx` | number | mm | `0` |  | (mm) |
| `dy` | number | mm | `0` |  | (mm) |
| `dz` | number | mm | `0` |  | (mm) |
| `rx` | number | deg | `0` |  | (degrees) |
| `ry` | number | deg | `0` |  | (degrees) |
| `rz` | number | deg | `0` |  | (degrees) |
| `angle` | number | deg |  |  | rotate (degrees) |
| `axis` | `X` \| `Y` \| `Z` |  |  |  | rotate: an origin axis |
| `pivot` | array of 3 numbers |  |  |  | the point rotations turn about |
| `from_point` | array of 3 numbers | mm |  |  | [x, y, z] in design coordinates (mm) |
| `to_point` | array of 3 numbers | mm |  |  | [x, y, z] in design coordinates (mm) |
| `px` | number | mm |  |  | (mm) |
| `py` | number | mm |  |  | (mm) |
| `pz` | number | mm |  |  | (mm) |
| `copy` | boolean |  | `false` |  |  |
| `capture` | boolean |  | `false` |  | components: a Move step in the timeline |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give exactly one of bodies, faces, components (what is moved).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: move the box 30 mm along X

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 40, "y": 10, "length": 40, "width": 20, "height": 20, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "move_copy", "args": {"bodies": ["Primitive1"], "move_type": "translate", "dx": 30}}
```

The answer:

```text
Done: AI: Move. Its id is 'Move'. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm; Body2: 16000 mm3, 40 x 20 x 20 mm.
```

## More argument examples

- move a body 30 mm along X:
  `{"bodies": ["Extrude2"], "move_type": "translate", "dx": 30}`
- push the +X face out 5 mm:
  `{"faces": {"normal": [1, 0, 0], "count": 1}, "dx": 5}`

## See also

- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `bodies_move_copy`, `bodies_move_edit`, `bodies_move_free`, `bodies_move_point_to_point`, `bodies_move_point_to_position`, `bodies_move_rotate_pivot`, `bodies_move_rotate_z`, `bodies_move_then_cut`, `bodies_move_translate`, `bodies_move_two_bodies`, `mirror_body_new_body_move_after`, `pattern_bodies_move_original_after` and 8 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
