# `gear`: Gear

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Gear. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Gear". Needs nothing.
It builds the design step(s) `sf_gear` (the golden models' step language).

## What it does

Make an involute gear (SciForge's Gear tool): type spur | internal (a ring with teeth inside: rim) | rack (rack_size teeth or length with rack_length, rack_height); standard metric (module, mm) | english (diametral_pitch, teeth per inch); teeth, pressure_angle (14.5, 20 or 25 degrees), backlash, fillet (root fillet, mm), thickness, symmetric (both sides of the plane), hole (bore diameter, 0 none), plane, x / y. operation join | cut | new_body (default) | new_component. (rules: [expressions](sciforge://docs/tools.md#help-expressions)) All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `plane` | string or object |  |  |  | "XY" \| "XZ" \| "YZ" (an origin plane of the current body) or {"face": selector} (a flat face of the part, as clicked) |
| `x` | number | mm | `0` |  | (mm) |
| `y` | number | mm | `0` |  | (mm) |
| `type` | `spur` \| `internal` \| `rack` |  | `"spur"` |  |  |
| `standard` | `metric` \| `english` |  | `"metric"` |  |  |
| `module` | number | mm | `2` | > 0 | mm |
| `diametral_pitch` | number |  | `12` | > 0 | teeth per inch |
| `teeth` | integer | count | `24` | >= 1, <= 400 |  |
| `pressure_angle` | number | deg | `20` |  | degrees: 14.5, 20 or 25 |
| `backlash` | number | mm | `0` | >= 0 | mm |
| `fillet` | number | mm | `0.5` | >= 0 | root fillet (mm) |
| `thickness` | number | mm | `10` | > 0 | mm |
| `symmetric` | boolean |  | `false` |  |  |
| `hole` | number | mm | `10` | >= 0 | bore diameter (mm, 0: none) |
| `rim` | number | mm | `5` | > 0 | internal gear: rim (mm) |
| `rack_size` | `teeth` \| `length` |  | `"teeth"` |  |  |
| `rack_length` | number | mm | `100` | > 0 | mm |
| `rack_height` | number | mm | `5` | > 0 | mm |
| `operation` | `join` \| `cut` \| `new_body` \| `new_component` |  | `"new_body"` |  |  |
| `expressions` | object |  |  |  | {field: formula}: a parameter or formula typed in a field (it keeps driving it) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`backlash`, `fillet`, `hole`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: a 20-tooth spur gear, module 1.5

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "gear", "args": {"module": 1.5, "teeth": 20, "thickness": 8, "hole": 8}}
```

The answer:

```text
Done: AI: Gear. Its id is 'Gear1'. Bodies now: Body1: 5131.56 mm3, 33 x 33 x 8 mm.
```

## More argument examples

- a 30-tooth spur gear, module 1.5:
  `{"module": 1.5, "teeth": 30, "thickness": 8, "hole": 8}`

## See also

- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `sf_gear_cut_block`, `sf_gear_edit_teeth`, `sf_gear_english`, `sf_gear_internal`, `sf_gear_join_block`, `sf_gear_rack`, `sf_gear_spur_basic`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
