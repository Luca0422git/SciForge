# `switch_design`: Switch design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: click a design tab. Category: Designs and files. Changes which design is open or active, changes no design. Needs nothing.

## What it does

Make another open design the active one (the tools then work on it). A text that fits several open designs (one's id is another's name) is refused with their ids.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `design` (required) | string |  |  |  | its id or name (list_designs) |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: design is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: make another open design the active one

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_design", "args": {"name": "Second"}}
]
```

The call:

```json
{"tool": "switch_design", "args": {"design": "Example"}}
```

The answer:

```text
The active design is now Example. Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- work on Bracket:
  `{"design": "Bracket"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
