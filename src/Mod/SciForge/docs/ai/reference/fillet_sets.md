# `fillet_sets`: Fillet / chamfer with sets

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Fillet / Chamfer (several selection sets, Chord Length, Variable). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Fillet (2 sets)". Needs a solid body.
It builds the design step(s) `fillet_sets` (the golden models' step language).

## What it does

Fusion's Fillet or Chamfer dialog with several selection sets in one step (the "+" rows): each set picks edges / faces / features and has its own size. Fillet rows: radius, radius_type constant | chord (chord) | variable (start, end, points [[position 0..1, radius]]), tangent_chain. Chamfer rows (kind chamfer): chamfer_type equal | two | angle, distance, distance2, angle, flip. tangent_chain (the step's, default true). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `kind` | `fillet` \| `chamfer` |  | `"fillet"` |  |  |
| `sets` (required) | array of objects |  |  | at least 1 item(s) | the selection sets |
| `tangent_chain` | boolean |  | `true` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sets is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`sets[].chord`, `sets[].distance`, `sets[].distance2`, `sets[].end`, `sets[].radius`, `sets[].start`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: two radii in one step

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
{"tool": "fillet_sets", "args": {"sets": [{"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 5}, {"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 1}]}}
```

The answer:

```text
Done: AI: Fillet (2 sets). Its id is 'Fillet1'. Bodies now: Body1: 23744.6 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- 3 mm on the top edges and 1 mm on the vertical edges, one step:
  `{"sets": [{"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 3}, {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 1}]}`

## See also

- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `fillet2_chamfer_sets_angle_flip`, `fillet2_chord_90_120`, `fillet2_face_and_its_edge_in_two_sets`, `fillet2_presspull_set_radius`, `fillet2_sets_tangent_chain_each`, `fillet2_tangent_chain_off`, `fillet2_two_sets`, `fillet2_variable_points`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
