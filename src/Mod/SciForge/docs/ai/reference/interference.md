# `interference`: Interference

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSPECT > Interference. Category: Inspect and measure. Read-only. Needs a solid body.

## What it does

Find where bodies overlap (Fusion's Interference): every pair that overlaps with the overlapping volume (mm3). bodies: step ids (default every body); include_coincident: count bodies that only touch.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies (default: all) |
| `include_coincident` | boolean |  | `false` |  |  |

## Answer

A plain sentence, then JSON with: `pairs`. The example below shows a real one.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: two bodies that overlap

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 40, "y": 10, "length": 40, "width": 20, "height": 20, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "interference", "args": {}}
```

The answer:

```text
1 pair(s) overlap, 4000 mm3 in all.
{
 "pairs": [
  {
   "body1": "Body1",
   "body2": "Body2",
   "volume_mm3": 4000.0
  }
 ]
}
```

## More argument examples

- do any parts collide?:
  `{}`

## See also

- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
