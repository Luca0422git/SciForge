# `roll_timeline`: Move history marker

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > drag the history marker (and the playback buttons). Category: Timeline (history). Changes the design (one undo step). Its undo step is named like "AI: Roll history marker". Needs an open design.
It builds the design step(s) `roll` (the golden models' step language).

## What it does

Move the timeline's history marker: to start (an empty design), end, previous / next (one step), or after / before a step. Steps after the marker are rolled back (not computed); a new feature goes in at the marker, as in Fusion. Move it back to the end when you are done.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `to` | `start` \| `end` \| `previous` \| `next` |  |  |  |  |
| `after` | string |  |  |  | put the marker right after this step |
| `before` | string |  |  |  | put the marker right before this step |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give exactly one of to, after, before (where the marker goes).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: roll the history marker back to just after the extrude

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
{"tool": "roll_timeline", "args": {"after": "Extrude1"}}
```

The answer:

```text
History marker moved: after Extrude 1 (Extrude1), 2 step(s) rolled back. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- roll back to just after Extrude1:
  `{"after": "Extrude1"}`
- roll forward to the end:
  `{"to": "end"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `blend_insert_chamfer_before_fillet`, `comp_move_captured_roll`, `extrude_multi_cut_timeline`, `extrude_multi_move`, `plastic2_snap_rolled_back`, `tl_insert_before_fillet`, `tl_roll_back`, `tl_roll_back_and_forward`, `tl_roll_to_start`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
