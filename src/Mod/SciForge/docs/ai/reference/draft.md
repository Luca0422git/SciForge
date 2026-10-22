# `draft`: Draft

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Draft. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Draft 3 degrees". Needs a solid body.
It builds the design step(s) `sf_draft`, `sf_draft2` (the golden models' step language).

## What it does

Fusion's Draft: tilt faces by an angle for a mould. plane: the fixed plane (XY | XZ | YZ or {"face": selector}: a flat face, its outward side the pull direction); faces: the faces to tilt (or [{body, faces}, ...] for several bodies in one step); angle (degrees, positive narrows the part toward the pull direction); flip. draft_type fixed (default) | parting (with parting: XY / {"face": sel} / {"edges": sel} / {"sketch": id}, the parting line); sides one | two (with angle2) | symmetric.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` (required) | string or object |  |  |  | XY, XZ, YZ or {"face": selector} |
| `faces` (required) | object or array |  |  |  | a face selector, or [{body, faces}] for several bodies |
| `angle` | number | deg | `1` |  | (degrees) |
| `flip` | boolean |  | `false` |  |  |
| `draft_type` | `fixed` \| `parting` |  | `"fixed"` |  |  |
| `parting` | string or object |  |  |  | parting line: a plane name, face, edges or sketch |
| `sides` | `one` \| `two` \| `symmetric` |  | `"one"` |  |  |
| `angle2` | number | deg |  |  | side two (degrees) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: plane is missing; faces is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: 3 degrees of draft on the four side walls

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
{"tool": "draft", "args": {"plane": "XY", "faces": {"along": [0, 0, 1], "type": "plane", "count": 4}, "angle": 3}}
```

The answer:

```text
Done: AI: Draft 3 degrees. Its id is 'Draft1'. Bodies now: Body1: 23479.6 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- 3 degrees on the four side walls, pulled up from XY:
  `{"plane": "XY", "faces": {"along": [0, 0, 1], "count": 4}, "angle": 3}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_draft_cylinder`, `sf_draft_edit_angle`, `sf_draft_ellipse_wall`, `sf_draft_ellipse_wall_edit`, `sf_draft_ellipse_wall_flip`, `sf_draft_flip`, `sf_draft_four_sides`, `sf_draft_front_face`, `sf_draft_spline_pocket`, `sf_draft_spline_side_corners`, `sf_draft_tangent_chain`, `sf_draft_then_shell` and 6 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
