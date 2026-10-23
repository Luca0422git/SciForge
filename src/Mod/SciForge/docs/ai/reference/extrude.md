# `extrude`: Extrude

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Extrude. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Extrude 10 mm". Needs an open design.
It builds the design step(s) `extrude` (the golden models' step language).

## What it does

Extrude a sketch's areas into a solid (SciForge's Extrude). distance goes along the sketch normal; flip: true goes the other way, for cuts too: a cut from a sketch lying on top of the part needs flip: true. regions picks some areas by a point inside each ([x, y] in sketch coordinates); without it the outer areas are used and shapes inside them are holes (a point in the ring and one in the disc fill it). direction one_side (default), symmetric (distance is the whole length, half on each side) or two_sides (distance one way, distance2 the other). through_all goes through the whole part instead of a distance. taper in degrees. More of Fusion's dialog: face (a flat face of the part as the profile, instead of a sketch), more_profiles (more sketches extruded together), to (Extent To Object: a plane, a face or a body to stop at), extent2 / to2 / taper2 (side two), measurement (symmetric: whole or half length), start (profile, offset with start_offset, or object with start_from), thin {location side1|center|side2, thickness, location2, thickness2} (a Thin Extrude: a wall along the profile; with curves it extrudes open sketch curves), bodies (Bodies to Cut / Join: auto or step ids), extend / object_offset (To Object). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `profile` | string |  |  |  | id of a create_sketch step |
| `regions` | array of arrays |  |  | at least 1 item(s) |  |
| `distance` | number | mm |  | > 0 |  |
| `operation` | `join` \| `cut` \| `intersect` \| `new_body` |  | `"join"` |  | join adds to the current body, cut removes from it, intersect keeps only the overlap, new_body makes a separate body |
| `direction` | `one_side` \| `symmetric` \| `two_sides` |  | `"one_side"` |  |  |
| `distance2` | number | mm |  | > 0 |  |
| `through_all` | boolean |  | `false` |  |  |
| `taper` | number | deg | `0` | >= -89, <= 89 |  |
| `flip` | boolean |  | `false` |  |  |
| `face` | object |  |  |  | instead of profile: a flat face of the part as the profile (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `more_profiles` | array of strings |  |  | at least 1 item(s) | more sketch steps extruded with profile |
| `curves` | string or object |  |  |  | open sketch curves for a thin extrude. (rules: [curves](sciforge://docs/tools.md#help-curves)) |
| `to` | object |  |  |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `extent2` | `distance` \| `through_all` \| `to_object` |  |  |  | side two's extent |
| `to2` | object |  |  |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `taper2` | number | deg |  | >= -89, <= 89 | side two's taper (degrees) |
| `measurement` | `whole` \| `half` |  | `"whole"` |  | symmetric: distance is the whole length or each half |
| `start` | `profile` \| `offset` \| `object` |  | `"profile"` |  | where the extrude starts |
| `start_offset` | number | mm |  |  | start offset along the normal (mm) |
| `start_from` | object |  |  |  | what an extent goes to or a start is measured from: {"plane": "XY"\|"XZ"\|"YZ"}, {"face": face selector} (a face of the current body; add "of": step id for a face of another body) or {"step": id} (the solid of that step's body) |
| `thin` | object |  |  |  | Thin Extrude: a wall along the profile instead of a solid |
| `thin.location` | `side1` \| `center` \| `side2` |  | `"side1"` |  |  |
| `thin.thickness` | number | mm |  | > 0 | wall thickness (mm) |
| `thin.location2` | `side1` \| `center` \| `side2` |  |  |  |  |
| `thin.thickness2` | number | mm |  | > 0 | side two's wall thickness (mm) |
| `bodies` | string or array |  |  |  | "auto": every body the feature passes through is cut / joined (what the dialog lists by itself); or a list of step ids: exactly those bodies (the dialog's "Bodies to Cut" row) |
| `extend` | `face` \| `adjacent` \| `body` \| `through` |  |  |  | To Object: how the target face is extended |
| `extend2` | `face` \| `adjacent` \| `body` \| `through` |  |  |  | side two's extend |
| `object_offset` | number | mm |  |  | To Object: stop this far from the object (mm) |
| `object_offset2` | number | mm |  |  | side two's object offset (mm) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give profile (a sketch id) or face (a flat face selector), one of them; distance is missing (or set through_all to true).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`taper`, `taper2`, `thin.thickness`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: a 10 mm plate

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}}
```

The answer:

```text
Done: AI: Extrude 10 mm. Its id is 'Extrude1'. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## Example 2: pull the top face up 5 mm with a 10 degree taper

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
{"tool": "extrude", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "distance": 5, "taper": 10}}
```

The answer:

```text
Done: AI: Extrude 5 mm. Its id is 'Extrude2'. Bodies now: Body1: 36446 mm3, 61.76 x 41.76 x 15 mm.
```

## More argument examples

- a 10 mm solid from Sketch1's areas:
  `{"profile": "Sketch1", "distance": 10}`
- cut a sketch lying on the top face down through the whole part:
  `{"profile": "Sketch2", "through_all": true, "operation": "cut", "flip": true}`
- extrude up to the top face (Extent To Object):
  `{"profile": "Sketch3", "to": {"face": {"normal": [0, 0, 1], "count": 1}}, "operation": "join"}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- Recipe: [threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `blend_chamfer_angle`, `blend_chamfer_top_face`, `blend_chamfer_two_flip`, `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature`, `blend_fillet_edit_radius`, `blend_fillet_presspull_radius`, `blend_fillet_slot_chain`, `blend_fillet_top_face`, `blend_insert_chamfer_before_fillet`, `bodies_combine_cut`, `bodies_combine_cut_cylinder` and 400 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
