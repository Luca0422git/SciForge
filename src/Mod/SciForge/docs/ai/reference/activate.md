# `activate`: Activate body / component

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > a body or component > Activate. Category: Assemble. Not an undo step: `undo` after it takes back the step before it; call it again to reverse it. Needs an open design.
It builds the design step(s) `use_body` (the golden models' step language).

## What it does

Make a body (by any step in it) or a component the one you work in: the next sketches and features go into it (Fusion's Activate Component). Not an undo step: activate the previous one again to go back (undo would take back the step before it).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `target` (required) | string |  |  |  | a body, a step in it, or a component |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: target is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: work in the plate's body again

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
{"tool": "activate", "args": {"target": "Extrude1"}}
```

The answer:

```text
The active body is now Body1 (id 'Body').
```

## More argument examples

- work in Extrude2's body:
  `{"target": "Extrude2"}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `extrude_multi_cut`, `extrude_multi_cut_all`, `extrude_multi_cut_all_far`, `extrude_multi_cut_edit`, `extrude_multi_cut_excluded`, `extrude_multi_cut_other_body`, `extrude_multi_cut_profile_body_excluded`, `extrude_multi_cut_reopen`, `extrude_multi_cut_split`, `extrude_multi_cut_timeline`, `extrude_multi_intersect`, `extrude_multi_join_delete` and 14 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
