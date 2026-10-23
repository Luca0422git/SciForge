# `rename`: Rename

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE / BROWSER > right-click > Rename. Category: Timeline (history). Changes the design (one undo step). Its undo step is named like "AI: Rename Extrude1". Needs an open design.

## What it does

Rename a timeline step, a body, a component, a sketch or a drawing (what the timeline and browser show). The id stays the same.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `target` (required) | string |  |  |  | the thing to rename |
| `name` (required) | string |  |  |  | the new name |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: target is missing; name is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a clearer name in the timeline

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
{"tool": "rename", "args": {"target": "Extrude1", "name": "Base plate"}}
```

The answer:

```text
Renamed Extrude1 (id 'Extrude1') to 'Base plate'.
```

## More argument examples

- name the first extrude:
  `{"target": "Extrude1", "name": "Base plate"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
