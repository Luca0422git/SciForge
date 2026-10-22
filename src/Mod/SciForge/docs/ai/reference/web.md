# `web`: Web

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Web. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Web". Needs a solid body.
It builds the design step(s) `sf_rib` (the golden models' step language).

## What it does

Fusion's Web: a thin wall from open sketch curves; the web grows out of the sketch plane, always joined to the part. curves: (rules: [curves](sciforge://docs/tools.md#help-curves)) thickness (mm), thickness_side symmetric | one_side (flip_side: the other side), depth_type to_next (up to the part) | depth (with depth), flip (the other direction), extend (the ends reach the part). All lengths are in millimetres (mm) and all angles in degrees.

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

## Example 1: a 2 mm wall across the tray

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 20}},
  {"tool": "shell", "args": {"faces": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "thickness": 2}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "offset": 20, "curves": [{"line": [2, 20, 58, 20]}]}}
]
```

The call:

```json
{"tool": "web", "args": {"curves": "Sketch2", "thickness": 2}}
```

The answer:

```text
Done: AI: Web. Its id is 'Web1'. Bodies now: Body1: 13728 mm3, 60 x 40 x 20 mm.
```

## More argument examples

- a 2 mm web from Sketch3's curve:
  `{"curves": "Sketch3", "thickness": 2}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_rib_arc`, `sf_rib_depth`, `sf_rib_edit_thickness`, `sf_rib_far_from_origin`, `sf_rib_gusset`, `sf_rib_one_side`, `sf_rib_one_side_flip`, `sf_web_arc`, `sf_web_cross`, `sf_web_depth`, `sf_web_depth_thin_wall`, `sf_web_not_extended` and 2 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
