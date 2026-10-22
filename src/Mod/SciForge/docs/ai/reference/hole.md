# `hole`: Hole

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Hole. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Hole 6 mm". Needs a solid body.
It builds the design step(s) `hole`, `hole_points`, `hole_at` (the golden models' step language).

## What it does

Drill holes into the part (SciForge's Hole). First create_sketch on the face where the holes start (for example plane XY with offset = the top's height) with a small circle at each hole centre; the holes go at the circles' centres, whatever their size; the holes go into the part (also from a sketch under it). Give depth or through_all. Optional counterbore {diameter, depth} or countersink {diameter, angle} (angle in degrees, default 90). Single Hole instead of a sketch: face (the flat face clicked) and at ([x, y, z] on it), with up to two references [{edge: edge selector, distance}] that place the centre from straight edges. All of Fusion's Hole dialog: hole_type simple | counterbore | countersink (cbore_diameter, cbore_depth, csink_diameter, csink_angle), extent distance | all | to (to: a plane or face), drill_point flat | angle (drill_angle), tap_type simple | clearance | tapped | taper, standard iso | ansi, size / designation (e.g. M6x1, 1/4-20 UNC), fit close | normal | loose, fastener socket_head | hex_head | countersunk, fastener_head (head pocket sized for it), taper_kind npt | bspt with taper_size, thread_class, thread_direction right | left, modeled (real thread), full_tap, tap_depth, flip. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` | string |  |  |  | id of the sketch with the centres |
| `diameter` | number | mm |  | > 0 |  |
| `depth` | number | mm |  | > 0 |  |
| `through_all` | boolean |  | `false` |  |  |
| `counterbore` | object |  |  |  |  |
| `counterbore.diameter` (required) | number | mm |  | > 0 |  |
| `counterbore.depth` (required) | number | mm |  | > 0 |  |
| `countersink` | object |  |  |  |  |
| `countersink.diameter` (required) | number | mm |  | > 0 |  |
| `countersink.angle` | number | deg | `90` | > 0, <= 179 |  |
| `face` | object |  |  |  | Single Hole: the flat face the hole starts on (one face) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `at` | array of 3 numbers | mm |  |  | Single Hole: the clicked point on that face |
| `references` | array of objects |  |  | at most 2 item(s) | Single Hole: up to two edges that place the centre |
| `hole_type` | `simple` \| `counterbore` \| `countersink` |  | `"simple"` |  |  |
| `cbore_diameter` | number | mm |  | > 0 | counterbore diameter (mm) |
| `cbore_depth` | number | mm |  | > 0 | counterbore depth (mm) |
| `csink_diameter` | number | mm |  | > 0 | countersink diameter (mm) |
| `csink_angle` | number | deg |  | > 0, <= 179 | countersink angle (degrees) |
| `extent` | `distance` \| `all` \| `to` |  | `"distance"` |  |  |
| `to` | object |  |  |  | extent to: {"plane": "XY"\|"XZ"\|"YZ"} or {"face": selector} |
| `drill_point` | `flat` \| `angle` |  | `"flat"` |  |  |
| `drill_angle` | number | deg |  | > 0, <= 180 | drill point angle (degrees) |
| `tap_type` | `simple` \| `clearance` \| `tapped` \| `taper` |  | `"simple"` |  |  |
| `standard` | `iso` \| `ansi` |  | `"iso"` |  |  |
| `size` | string |  |  |  | nominal size, e.g. 8 (M8: its coarse thread) or 1/4 |
| `designation` | string |  |  |  | thread designation, e.g. M6x1 or 1/4-20 UNC |
| `fit` | `close` \| `normal` \| `loose` |  | `"normal"` |  | clearance hole fit |
| `fastener` | `socket_head` \| `hex_head` \| `countersunk` |  |  |  | clearance: the fastener the hole is for |
| `fastener_head` | boolean |  |  |  | size the counterbore / countersink for that fastener |
| `taper_kind` | `npt` \| `bspt` |  |  |  |  |
| `taper_size` | string |  |  |  | taper thread size, e.g. 1/8 |
| `thread_class` | string |  |  |  | e.g. 6H or 2B |
| `thread_direction` | `right` \| `left` |  | `"right"` |  |  |
| `modeled` | boolean |  |  |  | cut the real thread (default: cosmetic) |
| `full_tap` | boolean |  |  |  | thread the whole depth |
| `tap_depth` | number | mm |  | > 0 | thread depth (mm) |
| `flip` | boolean |  |  |  | drill along the sketch's normal (left out: into the part, whichever side the sketch is on) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give sketch (a sketch with the hole centres) or face + at; give either depth or through_all: true; diameter is missing (or give tap_type with a designation / size).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a single 6 mm hole, 8 mm deep, on the top face

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
{"tool": "hole", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "at": [30, 20, 10], "diameter": 6, "depth": 8}}
```

The answer:

```text
Done: AI: Hole 6 mm. Its id is 'Hole1'. Bodies now: Body1: 23773.8 mm3, 60 x 40 x 10 mm.
```

## Example 2: a counterbored hole for an M5 socket head screw

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
{"tool": "hole", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "at": [15, 20, 10], "diameter": 5.5, "through_all": true, "counterbore": {"diameter": 10, "depth": 5.5}}}
```

The answer:

```text
Done: AI: Hole 5.5 mm. Its id is 'Hole1'. Bodies now: Body1: 23461.1 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- 6 mm holes through the part at Sketch2's circle centres:
  `{"sketch": "Sketch2", "diameter": 6, "through_all": true}`
- one tapped M6 hole 12 mm deep, clicked on the top face:
  `{"face": {"normal": [0, 0, 1], "count": 1}, "at": [20, 10, 10], "tap_type": "tapped", "designation": "M6x1", "depth": 12}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `hole_blind`, `hole_counterbore`, `hole_countersink`, `hole_points_flipped`, `hardware_countersunk_m4_on_rim`, `hole_clearance_countersunk`, `hole_clearance_m6`, `hole_clearance_socket_cbore`, `hole_curved_follows`, `hole_references_follow_edge`, `hole_second_survives_first`, `hole_single_angled` and 9 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
