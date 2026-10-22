# `pipe`: Pipe

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pipe. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Pipe". Needs an open design.
It builds the design step(s) `sf_pipe` (the golden models' step language).

## What it does

Make a pipe along a path (Fusion's Pipe): path {"sketch": id, "edge": n} (the sketch's n-th curve, 1 = first, with the curves chained to it when chain is true) or {"edges": edge selector} (edges of the part). section circular | square | triangular, section_size (mm), hollow with thickness (mm), distance 0..1 (how far along the path). operation auto, join, cut, intersect, new_body. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `path` (required) | object |  |  |  | {"sketch": id, "edge": n} or {"edges": selector} |
| `chain` | boolean |  | `true` |  | follow the curves joined to it |
| `section` | `circular` \| `square` \| `triangular` |  | `"circular"` |  |  |
| `section_size` | number | mm | `2` | > 0 | mm |
| `hollow` | boolean |  | `false` |  |  |
| `thickness` | number | mm | `0.5` | > 0 | wall (mm), hollow |
| `distance` | number | 0..1 | `1` | >= 0, <= 1 | 0..1 of the path |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` |  | `"auto"` |  | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`section_size`, `thickness`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: a 4 mm pipe along a line

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 0, 40]}]}}
]
```

The call:

```json
{"tool": "pipe", "args": {"path": {"sketch": "Sketch1", "edge": 1}, "section_size": 4}}
```

The answer:

```text
Done: AI: Pipe. Its id is 'Pipe1'. Bodies now: Body1: 502.655 mm3, 4 x 40 x 4 mm.
```

## More argument examples

- a 4 mm pipe along Sketch2's path:
  `{"path": {"sketch": "Sketch2", "edge": 1}, "section_size": 4}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_join_away_new_body`, `sf_pipe_corner_hollow_cut`, `sf_pipe_corner_intersect`, `sf_pipe_corner_mitre_join`, `sf_pipe_edge_auto_join`, `sf_pipe_edge_cut`, `sf_pipe_hollow_half`, `sf_pipe_old_upgraded`, `sf_pipe_param_driven`, `sf_pipe_ring_hollow`, `sf_pipe_ring_hollow_cut`, `sf_pipe_sketch_path` and 2 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
