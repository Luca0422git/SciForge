# `docs_read`: Read documentation

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (Fusion's help page, for SciForge). Category: Help. Read-only. Needs nothing.

## What it does

Read one document of SciForge's documentation for AI models, or one section of it: path is what docs_search answers (handbook.md, recipes/bracket.md, reference/extrude.md, user/known-issues.md), optionally with #anchor for one section (or give section). Long documents come in pages of about 12000 characters: page 2, 3... for the rest; the first page of a long document lists its sections. A golden model is read with golden/<id> (its design steps and measurements). sciforge://docs/index lists every document.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `path` (required) | string |  |  |  | a document path (handbook.md), with #anchor for one section, a URI sciforge://docs/<path> or golden/<id> |
| `section` | string |  |  |  | the anchor of one section (instead of #anchor in path) |
| `page` | integer |  | `1` | >= 1 | which page of a long document |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: one section of the handbook

Starting from SciForge with no design open.

The call:

```json
{"tool": "docs_read", "args": {"path": "handbook.md", "section": "units-and-coordinates"}}
```

The answer:

~~~~text
sciforge://docs/handbook.md#units-and-coordinates (SciForge handbook for AI models), section Units and coordinates, page 1 of 1:

## Units and coordinates

All lengths are millimetres and all angles degrees, in every argument and every answer
(areas mm2, volumes mm3, masses grams). The design's axes are Fusion's with Z up: X to the
right, Y away from you, Z up; the Home (iso) view looks from the front-right-top.

The three origin planes and their sketch coordinates:

| Plane | Normal (extrude direction) | Sketch x is | Sketch y is | `offset` d puts the plane at |
|---|---|---|---|---|
| XY | +Z | X | Y | z = d |
| XZ | -Y | X | Z | y = -d |
| YZ | +X | Y | Z | x = d |

So an extrude from an XZ sketch goes toward -Y, and on XZ a positive offset moves the sketch
to negative Y. A sketch on a flat face of the part (`create_sketch` with `face`) has its own
x / y axes; on a face that faces +Z (a top face) they are the design's X and Y, and
`get_sketch` always tells (its `placement`: origin, normal, x axis).

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Planes"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [{"rect": [0, 0, 20, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.bbox_mm.min": [0.0, -5.0, 0.0],
     "bodies.0.bbox_mm.max": [20.0, 0.0, 10.0]}}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "offset": 10,
    "curves": [{"point": [0, 0]}]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch2"},
   "expect": {"json": {"placement.origin": [0.0, -10.0, 0.0],
     "placement.normal": [0.0, -1.0, 0.0]}}},
  {"tool": "create_sketch", "args": {"plane": "YZ", "geometry": [{"rect": [0, 0, 20, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch3", "distance": 5, "operation": "new_body"}},
  {"tool": "inspect_design", "args": {"bodies": ["Extrude2"]},
   "expect": {"json": {"bodies.0.bbox_mm.min": [0.0, 0.0, 0.0],
     "bodies.0.bbox_mm.max": [5.0, 20.0, 10.0]}}}
]
```
~~~~

## More argument examples

- the handbook, first page:
  `{"path": "handbook.md"}`
- only the selector cookbook:
  `{"path": "selectors.md", "section": "cookbook"}`
- a golden model's steps and measurements:
  `{"path": "golden/box_basic"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
