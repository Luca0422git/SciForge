# `get_timeline`: Get timeline

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE (the bar at the bottom). Category: Timeline (history). Read-only. Needs an open design.

## What it does

List the timeline in order: every step with its id, its name as the timeline shows it ("Extrude 2"), its kind, the body / component it belongs to, whether it is before the history marker (done) or after it (rolled_back), suppressed, its status (ok, warning, error, with the reason in plain words) and its main values (distance, radius, quantity...); plus where the history marker stands.

## Arguments

No arguments.

## Answer

A plain sentence, then JSON with: `steps`, `history_marker`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the steps in order

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
{"tool": "get_timeline", "args": {}}
```

The answer:

```text
{
 "steps": [
  {
   "index": 0,
   "id": "Sketch1",
   "name": "Sketch 1",
   "kind": "sketch",
   "type": "Sketcher::SketchObject",
   "body": "Body",
   "state": "done",
   "values": {
    "base.width": 60.0,
    "base.height": 40.0,
    "base.x": 0.0,
    "base.y": 0.0
   }
  },
  {
   "index": 1,
   "id": "Extrude1",
   "name": "Extrude 1",
   "kind": "extrude",
   "type": "PartDesign::Pad",
   "body": "Body",
   "state": "done",
   "values": {
    "Distance": 10.0,
    "Taper": 0.0
   }
  },
  {
   "index": 2,
   "id": "Sketch2",
   "name": "Sketch 2",
   "kind": "sketch",
   "type": "Sketcher::SketchObject",
   "body": "Body",
   "state": "done",
   "values": {
    "g0.diameter": 8.0,
    "g0.x": 30.0,
    "g0.y": 20.0
   }
  },
  {
   "index": 3,
   "id": "Hole1",
   "name": "Hole 1",
   "kind": "hole",
   "type": "PartDesign::Hole",
   "body": "Body",
   "state": "done",
   "values": {
    "Diameter": 8.0
   }
  }
 ],
 "history_marker": {
  "after_step": "Hole1",
  "slot": 4,
  "at_end": true
 }
}
```

## More argument examples

- the steps, their state and the marker:
  `{}`

## See also

- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
