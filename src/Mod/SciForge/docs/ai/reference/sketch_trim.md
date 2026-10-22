# `sketch_trim`: Trim

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SKETCH > MODIFY > Trim (T). Category: Sketch. Changes the design (one undo step). Its undo step is named like "AI: Trim". Needs an open design.
It builds the design step(s) `sketch_trim` (the golden models' step language).

## What it does

Trim sketch curves, as clicking Trim at each point in turn: the curve nearest the point loses the piece between its neighbouring intersections. Points are [x, y] in the sketch's coordinates, on the piece to remove.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch |
| `points` (required) | array of arrays |  |  | at least 1 item(s) | one Trim click each |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; points is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: trim the bottom line of the rectangle

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "sketch_trim", "args": {"sketch": "Sketch1", "points": [[30, 0]]}}
```

The answer:

```text
Done: AI: Trim. No solid body yet.
```

## More argument examples

- remove the piece of curve through (20, 0):
  `{"sketch": "Sketch1", "points": [[20, 0]]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `sketch_trim_union`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
