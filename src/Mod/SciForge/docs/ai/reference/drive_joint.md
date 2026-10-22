# `drive_joint`: Drive joint

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: ASSEMBLE > Drive Joints. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Drive joint Joint". Needs an open design.

## What it does

Put a joint at an angle (degrees) and / or slide distance (mm), within its limits; what hangs on it follows. joint: its id.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `joint` (required) | string |  |  |  | the joint |
| `angle` | number | deg |  |  | (degrees) |
| `slide` | number | mm |  |  | (mm) |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: joint is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: turn the joint 45 degrees (the joint is made first)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "new_component", "args": {"label": "Base"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [-30, -30, 30, 30]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_component", "args": {"label": "Wheel"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [0, 0, 15]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}},
  {"tool": "joint", "args": {"type": "revolute", "first": {"component": "Wheel", "face": {"normal": [0, 0, -1], "count": 1}, "snap": "centre"}, "second": {"component": "Base", "face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "snap": "centre"}}}
]
```

The call:

```json
{"tool": "drive_joint", "args": {"joint": "Joint", "angle": 45}}
```

The answer:

```text
Done: Revolute 1 at angle 45 degrees, slide 0 mm. Bodies now: Body001: 36000 mm3, 60 x 60 x 10 mm; Body002: 3534.29 mm3, 30 x 30 x 5 mm.
```

## More argument examples

- turn the revolute joint to 45 degrees:
  `{"joint": "Joint1", "angle": 45}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
