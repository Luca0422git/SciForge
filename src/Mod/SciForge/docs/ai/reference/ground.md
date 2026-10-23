# `ground`: Ground / unground

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > a component > Ground. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Ground Base". Needs an open design.

## What it does

Ground a component (it never moves when joints solve) or unground it (ground: false).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `component` (required) | string |  |  |  | the component or body |
| `ground` | boolean |  | `true` |  |  |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: component is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: fix Base

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "new_component", "args": {"label": "Base"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [-30, -30, 30, 30]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_component", "args": {"label": "Wheel"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [0, 0, 15]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "ground", "args": {"component": "Base"}}
```

The answer:

```text
Base is grounded.
```

## More argument examples

- the base stays put:
  `{"component": "Base"}`

## See also

- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
