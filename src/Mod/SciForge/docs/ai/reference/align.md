# `align`: Align

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Align. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Align". Needs a solid body.
It builds the design step(s) `align_bodies` (the golden models' step language).

## What it does

Fusion's Align (Objects: Bodies): move a body so that from (a face, edge or corner of it) lands on to (another face, edge, corner, plane or axis). flip turns it over; turns (0..3) quarter-turns about the aligned axis. (rules: [body_picks](sciforge://docs/tools.md#help-body_picks))

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `from` (required) | string or object |  |  |  | on the body that moves (a body pick) |
| `to` (required) | string or object |  |  |  | where it goes (a body pick) |
| `flip` | boolean |  | `false` |  |  |
| `turns` | integer |  | `0` | >= 0, <= 3 |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: from is missing; to is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: put the high box on top of the low one

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 20, "width": 20, "height": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 30, "length": 20, "width": 20, "height": 15, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "align", "args": {"from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "Primitive2"}, "to": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "of": "Primitive1"}}}
```

The answer:

```text
Done: AI: Align. Its id is 'Align'. Bodies now: Body1: 4000 mm3, 20 x 20 x 10 mm; Body2: 6000 mm3, 20 x 20 x 15 mm.
```

## More argument examples

- stand one body on the other's top face:
  `{"from": {"face": {"normal": [0, 0, -1], "count": 1}, "of": "Extrude2"}, "to": {"face": {"normal": [0, 0, 1], "count": 1}, "of": "Extrude1"}}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `direct_align_block_on_table`, `direct_align_flip_angle`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
