# `scale`: Scale

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Scale. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Scale". Needs a solid body.
It builds the design step(s) `sf_scale`, `sf_scale_bodies`, `sf_scale_sketch` (the golden models' step language).

## What it does

Fusion's Scale: make the current body (or bodies: several step ids, one step; or a sketch: its curves and dimensions) bigger or smaller. factor (uniform) or factors [x, y, z] (non-uniform, bodies only); point: "origin" (default) or [x, y, z], a corner of the part to scale about.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `factor` | number |  |  | > 0 | uniform scale factor |
| `factors` | array of 3 numbers |  |  |  | [x, y, z] factors |
| `point` | string or array |  |  |  | "origin" or [x, y, z] (a corner of the part) |
| `bodies` | array of strings |  |  | at least 1 item(s) | several bodies, by a step of each |
| `sketch` | string |  |  |  | scale this sketch instead |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give factor (uniform) or factors [x, y, z], one of them.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: half as big

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
{"tool": "scale", "args": {"factor": 0.5}}
```

The answer:

```text
Done: AI: Scale. Its id is 'Scale1'. Bodies now: Body1: 3000 mm3, 30 x 20 x 5 mm.
```

## More argument examples

- twice as big about the origin:
  `{"factor": 2}`
- half as tall:
  `{"factors": [1, 1, 0.5]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_scale_about_corner`, `sf_scale_corner_follows_edit`, `sf_scale_edit_factor`, `sf_scale_non_uniform`, `sf_scale_non_uniform_keeps_faces`, `sf_scale_uniform`, `surface4_mirror_join_scale`, `modify2_scale_two_bodies`, `modify2_scale_sketch`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
