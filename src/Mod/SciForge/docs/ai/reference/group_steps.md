# `group_steps`: Group steps

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: TIMELINE > select steps > right-click > Group. Category: Timeline (history). Changes the design (one undo step). Its undo step is named like "AI: Group steps". Needs an open design.

## What it does

Group neighbouring timeline steps under one name (Fusion's timeline groups), or ungroup (ungroup: true with the group's id).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `steps` | array of strings |  |  | at least 2 item(s) | the steps (next to each other) |
| `name` | string |  |  |  | the group's name |
| `ungroup` | boolean |  | `false` |  |  |
| `group` | string |  |  |  | ungroup: the group's id (get_timeline) |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: a group needs at least 2 steps next to each other.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: group the hole and its sketch

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
{"tool": "group_steps", "args": {"steps": ["Sketch2", "Hole1"], "name": "Mounting hole"}}
```

The answer:

```text
Grouped Sketch2, Hole1 as 'Mounting hole' (group id 'g1').
```

## More argument examples

- group the boss:
  `{"steps": ["Sketch2", "Extrude2"], "name": "Boss"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
