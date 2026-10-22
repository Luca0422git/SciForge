# `pattern_components`: Pattern components

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Pattern (Pattern Type: Components). Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Pattern of components". Needs an open design.
It builds the design step(s) `component_pattern` (the golden models' step language).

## What it does

Pattern a whole component (its copies are linked instances, as Fusion's): kind rectangular (direction, direction2: origin axes X / Y / Z; quantity, quantity2, distance, distance2, distribution extent | spacing) or circular (axis, quantity, angle, circular_type full | angle | symmetric). component: the component's id.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `component` (required) | string |  |  |  | the component |
| `kind` (required) | `rectangular` \| `circular` |  |  |  |  |
| `axis` | `X` \| `Y` \| `Z` |  |  |  |  |
| `direction` | `X` \| `Y` \| `Z` |  |  |  |  |
| `direction2` | `X` \| `Y` \| `Z` |  |  |  |  |
| `quantity` | integer | count | `2` | >= 1 |  |
| `quantity2` | integer | count |  | >= 1 |  |
| `distance` | number | mm |  |  | (mm) |
| `distance2` | number | mm |  |  | (mm) |
| `angle` | number | deg | `360` |  | (degrees) |
| `circular_type` | `full` \| `angle` \| `symmetric` |  | `"full"` |  |  |
| `distribution` | `extent` \| `spacing` |  | `"extent"` |  |  |
| `direction_type` | `one` \| `symmetric` |  |  |  |  |
| `direction_type2` | `one` \| `symmetric` |  |  |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: component is missing; kind is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: three wheels around Z

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "new_component", "args": {"label": "Base"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [-30, -30, 30, 30]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_component", "args": {"label": "Wheel"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [0, 0, 15]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "pattern_components", "args": {"component": "Wheel", "kind": "circular", "axis": "Z", "quantity": 3}}
```

The answer:

```text
Done: AI: Pattern of components. Its id is 'CircularPattern'. Bodies now: Body001: 36000 mm3, 60 x 60 x 10 mm; Body002: 3534.29 mm3, 30 x 30 x 5 mm; Body003: 3534.29 mm3, 30 x 30 x 5 mm; Body004: 3534.29 mm3, 30 x 30 x 5 mm.
```

## More argument examples

- six copies of a component around Z:
  `{"component": "Part", "kind": "circular", "axis": "Z", "quantity": 6}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `comp_pattern_circular_6`, `comp_pattern_rect_extent`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
