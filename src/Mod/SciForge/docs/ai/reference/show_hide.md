# `show_hide`: Show / hide

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > the eye icon (Show / Hide). Category: View. Not an undo step: `undo` after it takes back the step before it; call it again to reverse it. Needs an open design.

## What it does

Show or hide bodies, components, sketches, construction geometry or drawings in the 3D view (they stay in the design). targets: ids; visible: true shows, false hides. Not an undo step: call it again to reverse it (undo would take back the step before it).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `targets` (required) | array of strings |  |  | at least 1 item(s) | what to show or hide |
| `visible` (required) | boolean |  |  |  |  |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: targets is missing; visible is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: show the plate's sketch

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
{"tool": "show_hide", "args": {"targets": ["Sketch1"], "visible": true}}
```

The answer:

```text
Showing Sketch1.
```

## More argument examples

- hide Sketch1:
  `{"targets": ["Sketch1"], "visible": false}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
