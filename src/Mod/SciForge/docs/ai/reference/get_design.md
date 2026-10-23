# `get_design`: Get design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER (the design's bodies, sketches, parameters) and TIMELINE. Category: Inspect and measure. Read-only. Needs nothing.

## What it does

Describe the open SciForge design: its bodies (volume in mm3, bounding box in mm), the timeline steps with their ids (use these ids in profile, sketch and features arguments), the user parameters and the sketches with their areas. Call it before changing a design and after each change to check the result. All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

No arguments.

## Answer

A plain sentence, then JSON with: `design`, `id`, `file`, `units`, `active_body`, `bodies`, `history_marker`, `timeline`, `parameters`, `sketches`. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the plate as JSON

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
{"tool": "get_design", "args": {}}
```

The answer:

```text
{
 "design": "Example",
 "id": "Example",
 "file": null,
 "units": "mm",
 "active_body": "Body",
 "bodies": [
  {
   "id": "Body",
   "label": "Body1",
   "volume_mm3": 24000.0,
   "area_mm2": 6800.0,
   "bbox_mm": [
    0.0,
    0.0,
    0.0,
    60.0,
    40.0,
    10.0
   ],
   "solids": 1,
   "faces": 6,
   "tip": "Extrude1",
   "material": "Steel (default)",
   "mass_g": 189.6
  }
 ],
 "history_marker": 2,
 "timeline": [
  {
   "id": "Sketch1",
   "label": "Sketch1",
   "type": "Sketcher::SketchObject",
   "name": "Sketch 1",
   "state": "done"
  },
  {
   "id": "Extrude1",
   "label": "Extrude1",
   "type": "PartDesign::Pad",
   "name": "Extrude 1",
   "state": "done"
  }
 ],
 "parameters": [],
 "sketches": [
  {
   "id": "Sketch1",
   "label": "Sketch1",
   "closed_areas": 1
  }
 ]
}
```

## More argument examples

- everything about the open design, as JSON:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
