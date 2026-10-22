# `capture_design_history`: Capture design history

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: the design's menu: Capture Design History / Do Not Capture Design History. Category: Timeline (history). Changes the open designs (not an undo step), destructive. Needs an open design.
It builds the design step(s) `history_on`, `history_off` (the golden models' step language).

## What it does

Turn the timeline on or off for the design (Fusion's Capture Design History). on: false freezes every body into one step (direct modelling: press_pull, move_copy... still work); on: true starts a timeline again from there.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `on` (required) | boolean |  |  |  | capture the history |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: on is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: stop recording steps (direct modelling)

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
{"tool": "capture_design_history", "args": {"on": false}}
```

The answer:

```text
Done: AI: Do not capture design history. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- switch to direct modelling (no timeline):
  `{"on": false}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_history_off_on`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
