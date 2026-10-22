# `move_step`: Reorder step

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > drag a step. Category: Timeline (history). Changes the design (one undo step). Its undo step is named like "AI: Move Fillet1". Needs an open design.
It builds the design step(s) `move` (the golden models' step language).

## What it does

Move a step before or after another one in the timeline. A step can never move before what it is built on: the refusal says why.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `step` (required) | string |  |  |  | the step |
| `before` | string |  |  |  | id of an earlier step |
| `after` | string |  |  |  | id of an earlier step |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: step is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: move the fillet before the hole

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 2}}
]
```

The call:

```json
{"tool": "move_step", "args": {"step": "Fillet1", "after": "Extrude1"}}
```

The answer:

```text
Moved Fillet1 after Extrude1. Bodies now: Body1: 23328.7 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- fillet after the boss:
  `{"step": "Fillet1", "after": "Extrude2"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `extrude_multi_move`, `tl_move_fillet_earlier`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
