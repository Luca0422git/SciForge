# `diff_design`: Diff design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE (compare before and after). Category: Inspect and measure. Read-only. Needs an open design.

## What it does

What changed in the design since: a snapshot id that inspect_design answered ("S3"), "last_change" (just before the latest change an AI made: what that change did), or a step id (the solid as it was right after that step, compared with now: what the later steps did). Answers the bodies added, removed and changed (volume, area, size, faces, edges before and after), the timeline steps added, removed or changed (values, state, status) and the parameters changed.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `since` (required) | string |  |  |  | a snapshot id ("S1"), "last_change" or a step id |

## Answer

A plain sentence, then JSON with: `bodies`, `steps`, `parameters`, `since`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: since is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: what the hole did

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

The call:

```json
{"tool": "diff_design", "args": {"since": "last_change"}}
```

The answer:

```text
Since the last change: steps added: Hole 1 (Hole1); Body1 volume 24000 -> 23497.3 mm3.
{
 "bodies": {
  "added": [],
  "removed": [],
  "changed": [
   {
    "id": "Body",
    "label": "Body1",
    "volume_mm3": {"before": 24000.0, "after": 23497.345175, "change": -502.654825},
    "area_mm2": {"before": 6800.0, "after": 6950.796447, "change": 150.796447},
    "faces": {"before": 6, "after": 7, "change": 1.0},
    "edges": {"before": 12, "after": 15, "change": 3.0},
    "vertices": {"before": 8, "after": 10, "change": 2.0}
   }
  ]
 },
 "steps": {"added": [{"id": "Hole1", "name": "Hole 1", "kind": "hole"}], "removed": [], "changed": []},
 "parameters": {"added": [], "removed": [], "changed": []},
 "since": "last_change"
}
```

## More argument examples

- what the last change did:
  `{"since": "last_change"}`
- everything that changed since inspect_design gave S1:
  `{"since": "S1"}`
- what the steps after Extrude1 did to the solid:
  `{"since": "Extrude1"}`

## See also

- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
