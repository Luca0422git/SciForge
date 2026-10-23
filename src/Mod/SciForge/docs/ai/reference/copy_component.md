# `copy_component`: Copy / paste component

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: Copy (Ctrl+C) a component, then Paste / Paste New. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Paste Wheel". Needs an open design.
It builds the design step(s) `component_paste` (the golden models' step language).

## What it does

Copy a component and paste it: new false (default) makes a linked instance (it changes with the original, Fusion's Paste), new true an independent copy (Paste New); moved by dx / dy / dz (mm).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `component` (required) | string |  |  |  | the component |
| `new` | boolean |  | `false` |  | Paste New: an independent copy |
| `dx` | number | mm | `0` |  | (mm) |
| `dy` | number | mm | `0` |  | (mm) |
| `dz` | number | mm | `0` |  | (mm) |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: component is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: a linked copy of the wheel 40 mm along X

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
{"tool": "copy_component", "args": {"component": "Wheel", "dx": 40}}
```

The answer:

```text
Done: AI: Paste Wheel. Its id is 'Component002' (shown as 'Wheel:2'). Bodies now: Body001: 36000 mm3, 60 x 60 x 10 mm; Body002: 3534.29 mm3, 30 x 30 x 5 mm; Body003: 3534.29 mm3, 30 x 30 x 5 mm.
```

## More argument examples

- a linked copy of Bolt 30 mm along X:
  `{"component": "Bolt", "dx": 30}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `comp_paste_instance_follows`, `comp_paste_new_independent`, `export_report_design`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
