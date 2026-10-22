# `coil`: Coil

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Coil. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Coil". Needs nothing.
It builds the design step(s) `sf_coil` (the golden models' step language).

## What it does

Make a coil (spring, helix) or a flat spiral (Fusion's Coil): plane and x / y of its centre, diameter, type rev_height (revolutions + height), rev_pitch, height_pitch or spiral; revolutions, height, pitch (mm per turn), angle (taper, degrees), clockwise; section circular | square | tri_ext | tri_int, section_position inside | center | outside, section_size (mm). operation auto, join, cut, intersect, new_body. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` | string or object |  |  |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | mm | `0` |  | (mm) |
| `y` | number | mm | `0` |  | (mm) |
| `diameter` | number | mm | `20` | > 0 | mm |
| `type` | `rev_height` \| `rev_pitch` \| `height_pitch` \| `spiral` |  | `"rev_height"` |  |  |
| `revolutions` | number |  | `5` | > 0 |  |
| `height` | number | mm | `20` |  | (mm) |
| `pitch` | number | mm | `4` | > 0 | mm per turn |
| `angle` | number | deg | `0` |  | taper (degrees) |
| `clockwise` | boolean |  | `true` |  |  |
| `section` | `circular` \| `square` \| `tri_ext` \| `tri_int` |  | `"circular"` |  |  |
| `section_position` | `inside` \| `center` \| `outside` |  | `"inside"` |  |  |
| `section_size` | number | mm | `2` | > 0 | mm |
| `operation` | `auto` \| `join` \| `cut` \| `intersect` \| `new_body` |  | `"auto"` |  | auto (default: what the dialog picks by itself), join, cut, intersect or new_body |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a 4-turn spring, 20 mm tall

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "coil", "args": {"plane": "XY", "diameter": 20, "revolutions": 4, "height": 20, "section_size": 2}}
```

The answer:

```text
Done: AI: Coil. Its id is 'Coil1'. Bodies now: Body1: 710.612 mm3, 20 x 20 x 22 mm.
```

## More argument examples

- a 6-turn spring, 30 mm tall:
  `{"plane": "XY", "diameter": 20, "revolutions": 6, "height": 30, "section_size": 2}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sf_coil_basic`, `sf_coil_cut_block`, `sf_coil_edit_turns`, `sf_coil_old_narrow_upgraded`, `sf_coil_param_driven`, `sf_coil_square_spiral`, `sf_coil_taper_height_pitch_param`, `sf_coil_taper_narrow`, `sf_coil_taper_param_driven`, `sf_coil_taper_raised_narrow_down`, `sf_coil_taper_raised_widen`, `sf_coil_taper_rev_pitch_param` and 1 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
