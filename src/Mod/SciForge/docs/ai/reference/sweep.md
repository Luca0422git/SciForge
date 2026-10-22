# `sweep`: Sweep

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Sweep. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Sweep". Needs an open design.
It builds the design step(s) `sf_sweep` (the golden models' step language).

## What it does

Sweep a profile along a path (Fusion's Sweep). profile: a sketch id (its one area; a sketch with several areas is taken whole), with regions [[x, y], ...] to click some areas, or face: a flat face of the part. path (and rail): curves. (rules: [curves](sciforge://docs/tools.md#help-curves)) type single (path only), rail (path + guide rail: the profile follows the rail, scaling scale | stretch | none) or surface (path + guide surface faces). distance / distance2: how far along the path, 0..1 (1 = all the way); taper and twist (degrees, single path); orientation perpendicular | parallel; operation; bodies (Objects To Cut). (rules: [expressions](sciforge://docs/tools.md#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `profile` | string |  |  |  | the profile sketch |
| `regions` | array of arrays |  |  | at least 1 item(s) | areas of the profile sketch, a point inside each |
| `face` | object |  |  |  | instead of profile: a flat face as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `path` (required) | string or object |  |  |  | the path |
| `rail` | string or object |  |  |  | type rail: the guide rail |
| `surface` | object |  |  |  | type surface: the guide surface faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `type` | `single` \| `rail` \| `surface` |  | `"single"` |  |  |
| `distance` | number | 0..1 | `1` | >= 0, <= 1 | how far along the path, 0..1 |
| `distance2` | number | 0..1 |  | >= 0, <= 1 | side two, 0..1 |
| `taper` | number | deg | `0` |  | taper angle (degrees) |
| `twist` | number | deg | `0` |  | twist angle (degrees) |
| `orientation` | `perpendicular` \| `parallel` |  | `"perpendicular"` |  |  |
| `scaling` | `scale` \| `stretch` \| `none` |  | `"scale"` |  | type rail |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` |  | `"auto"` |  | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `bodies` | string or array |  |  |  | Objects To Cut: "auto" (every body in the way) or a list of step ids |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a circle swept along a line and an arc

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [0, 0, 3]}]}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}]}}
]
```

The call:

```json
{"tool": "sweep", "args": {"profile": "Sketch1", "path": "Sketch2"}}
```

The answer:

```text
Done: AI: Sweep. Its id is 'Sweep1'. Bodies now: Body1: 2019.24 mm3, 23 x 6 x 63 mm.
```

## More argument examples

- sweep Sketch1's circle along every curve of Sketch2:
  `{"profile": "Sketch1", "path": "Sketch2"}`
- along the chain through (0, 20), a quarter turn of twist:
  `{"profile": "Sketch1", "path": {"sketch": "Sketch2", "at": [0, 20]}, "twist": 90}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_sweep_both_sides`, `sf_sweep_distance_parameter`, `sf_sweep_edit_distance`, `sf_sweep_face_taper`, `sf_sweep_groove_cut`, `sf_sweep_guide_surface`, `sf_sweep_half_distance`, `sf_sweep_intersect`, `sf_sweep_join_two_bodies`, `sf_sweep_mitre_corner`, `sf_sweep_parallel_arc`, `sf_sweep_rail_scale` and 6 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
