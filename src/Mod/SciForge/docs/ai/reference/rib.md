# `rib`: Rib

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Rib. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Rib". Needs a solid body.
It builds the design step(s) `sf_rib` (the golden models' step language).

## What it does

Fusion's Rib: a thin wall from one open sketch curve; the rib grows in the sketch plane to the part, always joined to the part. curves: (rules: [curves](sciforge://docs/tools.md#help-curves)) thickness (mm), thickness_side symmetric | one_side (flip_side: the other side), depth_type to_next (up to the part) | depth (with depth), flip (the other direction), extend (the ends reach the part). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `curves` (required) | string or object |  |  |  | the curves |
| `thickness` | number | mm | `2` | > 0 | wall thickness (mm) |
| `thickness_side` | `symmetric` \| `one_side` |  | `"symmetric"` |  |  |
| `flip_side` | boolean |  | `false` |  |  |
| `depth_type` | `to_next` \| `depth` |  | `"to_next"` |  |  |
| `depth` | number | mm |  | > 0 | depth (mm), depth_type depth |
| `flip` | boolean |  | `false` |  |  |
| `extend` | boolean |  | `true` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: curves is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a 2 mm rib in the corner of an L profile

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [{"polyline": [[0, 0], [40, 0], [40, 5], [5, 5], [5, 40], [0, 40]]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 20}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "offset": 10, "curves": [{"line": [5, 25, 25, 5]}]}}
]
```

The call:

```json
{"tool": "rib", "args": {"curves": "Sketch2", "thickness": 2}}
```

The answer:

```text
Done: AI: Rib. Its id is 'Rib1'. Bodies now: Body1: 7900 mm3, 40 x 20 x 40 mm.
```

## More argument examples

- a 2 mm rib from Sketch3's curve:
  `{"curves": "Sketch3", "thickness": 2}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_rib_arc`, `sf_rib_depth`, `sf_rib_edit_thickness`, `sf_rib_far_from_origin`, `sf_rib_gusset`, `sf_rib_one_side`, `sf_rib_one_side_flip`, `sf_web_arc`, `sf_web_cross`, `sf_web_depth`, `sf_web_depth_thin_wall`, `sf_web_not_extended` and 2 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
