# `primitive`: Box / Cylinder / Sphere / Torus

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Box, Cylinder, Sphere, Torus. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Box". Needs nothing.
It builds the design step(s) `sf_primitive` (the golden models' step language).

## What it does

Make a box, cylinder, sphere or torus (Fusion's primitives) on an origin plane or a flat face, in that plane's own x / y frame. box: x, y (first corner), length, width, height (signed: a negative height goes below the plane), sx / sy (+1 / -1: the side the box goes to); cylinder: x, y (centre), diameter, height; sphere: x, y, diameter; torus: x, y, inner_diameter, torus_diameter, position inside | center | outside. operation auto (what the dialog picks: join when it touches the part, else new_body), join, cut, intersect, new_body or new_component. (rules: [expressions](sciforge://docs/tools.md#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `kind` (required) | `box` \| `cylinder` \| `sphere` \| `torus` |  |  |  |  |
| `plane` | string or object |  |  |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | mm | `0` |  | x in the plane (mm) |
| `y` | number | mm | `0` |  | y in the plane (mm) |
| `sx` | integer |  | `1` |  | +1 / -1 |
| `sy` | integer |  | `1` |  | +1 / -1 |
| `length` | number | mm |  |  | box length (x) (mm) |
| `width` | number | mm |  |  | box width (y) (mm) |
| `height` | number | mm |  |  | height along the plane's normal (mm) |
| `diameter` | number | mm |  | > 0 | mm |
| `inner_diameter` | number | mm |  | > 0 | torus: inner diameter (mm) |
| `torus_diameter` | number | mm |  | > 0 | torus: the tube's diameter (mm) |
| `position` | `inside` \| `center` \| `outside` |  | `"inside"` |  | torus |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` \| `new_component` |  | `"auto"` |  |  |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: kind is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`torus_diameter`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: a 40 x 20 x 10 box

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 40, "width": 20, "height": 10}}
```

The answer:

```text
Done: AI: Box. Its id is 'Primitive1'. Bodies now: Body1: 8000 mm3, 40 x 20 x 10 mm.
```

## More argument examples

- a 40 x 20 x 10 box at the origin:
  `{"kind": "box", "plane": "XY", "length": 40, "width": 20, "height": 10}`
- a boss on the top face:
  `{"kind": "cylinder", "plane": {"face": {"normal": [0, 0, 1], "count": 1}}, "x": 20, "y": 10, "diameter": 8, "height": 5}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_silhouette_body_sphere`, `direct_silhouette_edit_to_faces`, `direct_silhouette_faces_sphere`, `plastic2_lip_round_rim`, `plastic2_lip_tip_radius`, `sf_box_basic`, `sf_box_param_driven`, `sf_box_pocket_edit_join`, `sf_box_pocket_top`, `sf_box_xz_flipped`, `sf_coil_cut_block`, `sf_coil_taper_raised_narrow_down` and 19 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
