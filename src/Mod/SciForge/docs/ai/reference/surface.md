# `surface`: Surface

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SURFACE > CREATE / MODIFY (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill, Thicken, Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal). Category: Surface. Changes the design (one undo step). Its undo step is named like "AI: Surface extrude". Needs nothing.
It builds the design step(s) `sf_surface` (the golden models' step language).

## What it does

One of the SURFACE tab's tools (thin surface bodies with no volume; Thicken, Boundary Fill and Stitch make solids). kind picks the tool; refs / refs2 / refs3 are the dialog's selection boxes in order (profile, then path / axis / rails / tools...). options: the dialog's fields: extrude: start, start_offset, direction one_side|two_sides|symmetric, measurement, extent distance|to_object|all, distance, distance2, taper, taper2, flip, operation new_body|new_component; revolve: type angle|to|full, direction, angle, angle2; sweep: type single|rail, distance, distance2, orientation, twist, taper, scaling; loft: guide, closed, merge, start_/end_condition, _weight, _angle; patch: continuity connected|tangent|curvature, weight, group_edges; ruled: ruled_type tangent|normal|direction, distance, angle, alternate, mitered; offset: distance; boundary_fill: remove_tools, operation join|cut|intersect|new_body; thicken: thickness, direction, thicken_type sharp|rounded, operation; untrim: loop_type all|internal|external, extend, distance; extend: distance, extend_type natural|perpendicular|tangent, alignment free|align; stitch: tolerance (mm), operation; every kind: chain (chain selection). remove (trim): [{step, at: [x, y, z]}] a point on each piece to take away; cells (boundary_fill): [[x, y, z], ...] a point in each cell kept; bodies (reverse_normal): step ids; target: the solid body a thicken / boundary fill joins or cuts. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `kind` (required) | `extrude` \| `revolve` \| `sweep` \| `loft` \| `patch` \| `ruled` \| `offset` \| `boundary_fill` \| `thicken` \| `trim` \| `untrim` \| `extend` \| `stitch` \| `unstitch` \| `reverse_normal` |  |  |  |  |
| `refs` | array of objects |  |  | at least 1 item(s) | the first selection box |
| `refs2` | array of objects |  |  | at least 1 item(s) | the second selection box |
| `refs3` | array of objects |  |  | at least 1 item(s) | the third selection box |
| `options` | object |  |  |  | the dialog's fields (see above) |
| `remove` | array of objects |  |  | at least 1 item(s) | trim: the pieces to take away |
| `cells` | array of arrays |  |  | at least 1 item(s) | boundary_fill: a point inside each cell |
| `bodies` | array of strings |  |  | at least 1 item(s) | reverse_normal: the bodies |
| `target` | string |  |  |  | thicken / boundary_fill: the solid body it joins or cuts |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: kind is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`options.thickness`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: a 20 mm surface from a sketch line

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 30, 0]}]}}
]
```

The call:

```json
{"tool": "surface", "args": {"kind": "extrude", "refs": [{"sketch": "Sketch1", "at": [15, 0]}], "options": {"distance": 20}}}
```

The answer:

```text
Done: AI: Surface extrude. Its id is 'Surface1'. No solid body yet.
```

## More argument examples

- a 20 mm surface from a sketch curve:
  `{"kind": "extrude", "refs": [{"sketch": "Sketch1", "at": [10, 0]}], "options": {"distance": 20}}`
- turn the surface into a 2 mm solid:
  `{"kind": "thicken", "refs": [{"step": "Surface1"}], "options": {"thickness": 2}}`

## See also

- Recipe: [curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `surface2_extrude_all`, `surface2_extrude_from_curved_face`, `surface2_extrude_from_face`, `surface2_extrude_to_body`, `surface2_extrude_to_chain_faces`, `surface2_loft_centerline`, `surface2_loft_tangent_end`, `surface2_loft_two_rails`, `surface2_revolve_to_plane`, `surface2_sweep_rail`, `surface2_sweep_taper`, `surface3_extend_align_edges` and 41 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
