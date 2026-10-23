# `get_sketch`: Get sketch

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > Sketches (and the Sketch Palette). Category: Sketch. Read-only. Needs an open design.

## What it does

Read a sketch: its plane and placement, every curve by index (type, points, radius, construction or not), every constraint by index (type, name, the curves it ties, its value for dimensions, driving or not), how many degrees of freedom are left (0: fully constrained, Fusion's padlock), the constraints that conflict or are redundant, and its closed areas (with a point inside each, for regions). Use the indexes in sketch_constraint, sketch_dimension, set_sketch_dimension and sketch_delete.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch to read |

## Answer

A plain sentence, then JSON with: `id`, `label`, `placement`, `geometry`, `constraints`, `on`, `solver`, `degrees_of_freedom`, `fully_constrained`, `closed_areas`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: its curves

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}}
]
```

The call:

```json
{"tool": "get_sketch", "args": {"sketch": "Sketch1"}}
```

The answer:

```text
{
 "id": "Sketch1",
 "label": "Sketch1",
 "placement": {
  "origin": [
   0.0,
   0.0,
   0.0
  ],
  "normal": [
   0.0,
   0.0,
   1.0
  ],
  "x_axis": [
   1.0,
   0.0,
   0.0
  ]
 },
 "geometry": [
  {
   "index": 0,
   "type": "LineSegment",
   "construction": false,
   "start": [
    0.0,
    0.0
   ],
   "end": [
    60.0,
    0.0
   ],
   "length": 60.0
  },
  {
   "index": 1,
   "type": "LineSegment",
   "construction": false,
   "start": [
    60.0,
    0.0
   ],
   "end": [
    60.0,
    40.0
   ],
   "length": 40.0
  },
  {
   "index": 2,
   "type": "LineSegment",
   "construction": false,
   "start": [
    60.0,
    40.0
   ],
   "end": [
    0.0,
    40.0
   ],
   "length": 60.0
  },
  {
   "index": 3,
   "type": "LineSegment",
   "construction": false,
   "start": [
    0.0,
    40.0
... (254 more lines)
```

## More argument examples

- curves, constraints and areas of Sketch1:
  `{"sketch": "Sketch1"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
