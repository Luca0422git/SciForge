# `get_view`: Get view

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (the 3D view's camera). Category: View. Read-only. Needs an open design, the SciForge window.

## What it does

The 3D view's camera now (a string set_view takes back), its projection, and the saved named views of the design.

## Arguments

No arguments.

## Answer

A plain sentence, then JSON with: `camera`, `projection`, `named_views`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Without the SciForge window: `This needs the SciForge window, and SciForge is running without one (headless / command line).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the camera (needs the SciForge window)

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
{"tool": "get_view", "args": {}}
```

The answer:

```text
{
 "camera": "#Inventor V2.1 ascii\n\n\nOrthographicCamera {\n  viewportMapping ADJUST_CAMERA\n  position 0 0 1\n  orientation 0 0 1  0\n  nearDistance 0.99900001\n  farDistance 1.001\n  aspectRatio 1\n  focalDistance 5\n  height 4.1421356\n\n}\n",
 "projection": "Orthographic",
 "named_views": []
}
```

## More argument examples

- the camera and the named views:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
