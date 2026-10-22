# `full_round_fillet`: Full round fillet

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Fillet (Type: Full Round Fillet). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Full round fillet". Needs a solid body.
It builds the design step(s) `full_round` (the golden models' step language).

## What it does

Fusion's Full Round Fillet: each selector picks one centre face (a rib's top, say); it is replaced by a round that touches both side faces.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` (required) | array of objects |  |  | at least 1 item(s) | one selector per round |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: faces is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: round the top of a wall completely (the wall is made first)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 40, "width": 4, "height": 20}}
]
```

The call:

```json
{"tool": "full_round_fillet", "args": {"faces": [{"normal": [0, 0, 1], "count": 1}]}}
```

The answer:

```text
Done: AI: Full round fillet. Its id is 'Fillet1'. Bodies now: Body1: 3131.33 mm3, 40 x 4 x 20 mm.
```

## More argument examples

- round off the top of a thin wall:
  `{"faces": [{"normal": [0, 0, 1], "count": 1}]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `fillet2_full_round_rib`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
