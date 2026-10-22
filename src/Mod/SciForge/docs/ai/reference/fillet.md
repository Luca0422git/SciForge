# `fillet`: Fillet

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Fillet. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Fillet 5 mm". Needs a solid body.
It builds the design step(s) `blend_fillet`, `blend_insert` (the golden models' step language).

## What it does

Round edges of the current body with a radius (SciForge's Fillet). Pick them with edges (an edge selector), faces (every sharp edge around the faces a face selector picks) and/or features (the edges earlier steps made, by step id). Errors such as 'the radius is too big for this edge' come back as sentences. For several radii, chord length, variable radius or tangent chain off use fillet_sets; Rule Fillet and Full Round Fillet are their own tools. With the timeline marker rolled back the fillet goes in at the marker and later fillets keep their edges. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `edges` | object |  |  |  | The edges to round. (rules: [selectors](sciforge://docs/tools.md#help-selectors)) |
| `faces` | object |  |  |  | Round every sharp edge around these faces. (rules: [selectors](sciforge://docs/tools.md#help-selectors)) |
| `features` | array of strings |  |  | at least 1 item(s) | ids of earlier steps (from get_design's timeline) |
| `radius` (required) | number | mm |  | > 0 |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: radius is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: round the four vertical corners

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
{"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 5}}
```

The answer:

```text
Done: AI: Fillet 5 mm. Its id is 'Fillet1'. Bodies now: Body1: 23785.4 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- round the 4 top edges of a box, 3 mm:
  `{"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 3}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature`, `blend_fillet_edit_radius`, `blend_fillet_presspull_radius`, `blend_fillet_slot_chain`, `blend_fillet_top_face`, `blend_insert_chamfer_before_fillet`, `mirror_fillet_feature`, `pattern_edit_keeps_later_fillet`, `picks_fillet_chamfer_kept_after_reopen`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
