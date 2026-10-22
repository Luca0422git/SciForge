# `create_curve_sketch`: Create sketch of curves

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Create Sketch (lines, arcs, points). Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Sketch of curves on XZ". Needs nothing.
It builds the design step(s) `sf_curves` (the golden models' step language).

## What it does

Create a sketch of open curves and points: the paths, rails, guide curves and rib / web curves that sweep, loft, pipe, rib, web, pattern_on_path and split_body use, and points for holes and lofts. Arcs run counter-clockwise from a0 to a1 (degrees); a polyline stays open. Closed shapes (areas) are made with create_sketch. (rules: [sketches](sciforge://docs/tools.md#help-sketches)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` (required) | `XY` \| `XZ` \| `YZ` |  |  |  |  |
| `offset` | number | mm | `0` |  | mm along the plane's normal |
| `curves` (required) | array of objects |  |  | at least 1 item(s) | the curves and points |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: plane is missing; curves is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: an open path: a line up and a quarter arc (a sweep path)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "create_curve_sketch", "args": {"plane": "XZ", "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}]}}
```

The answer:

```text
Done: AI: Sketch of curves on XZ. Its id is 'Sketch1'. No solid body yet.
```

## More argument examples

- a sweep path: a straight line up, then a quarter arc:
  `{"plane": "XZ", "curves": [{"line": [0, 0, 0, 40]}, {"arc": [20, 40, 20, 90, 180]}]}`
- two sketch points (hole centres):
  `{"plane": "XY", "curves": [{"point": [10, 10]}, {"point": [30, 10]}]}`

## See also

- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Recipe: [curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `extrude_thin_arc_center`, `extrude_thin_open_l`, `sf_loft_centerline_ends`, `sf_loft_centerline_torus`, `sf_loft_cone_point`, `sf_loft_cut_cone`, `sf_loft_ends_dome`, `sf_loft_one_rail`, `sf_loft_rails_ends`, `sf_loft_rails_turning`, `sf_loft_two_rails`, `sf_rib_arc` and 48 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
