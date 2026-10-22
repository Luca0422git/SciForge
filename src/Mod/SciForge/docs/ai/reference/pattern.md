# `pattern`: Pattern

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pattern > Rectangular / Circular Pattern (features). Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Rectangular pattern x3". Needs a solid body.
It builds the design step(s) `pattern_rect`, `pattern_circ` (the golden models' step language).

## What it does

Repeat earlier steps (features: their ids, e.g. a cut or a hole). kind rectangular: count copies spaced by spacing (mm) along direction X, Y or Z, optionally a second row with direction2, count2, spacing2. kind circular: count copies around axis X, Y or Z over angle degrees (default 360). Counts include the original. rectangular_pattern, circular_pattern, pattern_on_path and mirror offer the whole Fusion dialogs (faces, bodies, edges as directions, symmetric, suppression).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `kind` (required) | `rectangular` \| `circular` |  |  |  |  |
| `features` (required) | array of strings |  |  | at least 1 item(s) | ids of earlier steps (from get_design's timeline) |
| `direction` | `X` \| `Y` \| `Z` |  |  |  |  |
| `count` (required) | integer | count |  | >= 2 |  |
| `spacing` | number | mm |  |  |  |
| `direction2` | `X` \| `Y` \| `Z` |  |  |  |  |
| `count2` | integer | count |  | >= 2 |  |
| `spacing2` | number | mm |  |  |  |
| `axis` | `X` \| `Y` \| `Z` |  |  |  |  |
| `angle` | number | deg | `360` | > 0, <= 360 |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: kind is missing; features is missing; count is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: three bosses 20 mm apart

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [10, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "pattern", "args": {"kind": "rectangular", "features": ["Extrude2"], "direction": "X", "count": 3, "spacing": 20}}
```

The answer:

```text
Done: AI: Rectangular pattern x3. Its id is 'Pattern1'. Bodies now: Body1: 25178.1 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- three copies of a cut, 20 mm apart along X:
  `{"kind": "rectangular", "features": ["Extrude2"], "direction": "X", "count": 3, "spacing": 20}`
- six holes around the Z axis:
  `{"kind": "circular", "features": ["Hole1"], "axis": "Z", "count": 6}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `edit_pattern_count`, `plate_hole_grid`, `flange_polar_holes`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
