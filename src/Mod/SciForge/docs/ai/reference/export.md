# `export`: Export

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > Export. Category: Import and export. Writes files. Needs an open design.

## What it does

Export the design's bodies to a file: format step (.step / .stp), stl or 3mf (for 3D printing). path is a full path; replacing an existing file must be confirmed by the person in SciForge. Also: iges (.igs), stl_ascii, obj, brep, and dxf (one sketch, or one flat face, as 2D curves: give sketch or face). bodies: step ids of the bodies to write (default every visible body); mesh formats take refinement Low | Medium | High (Fusion's presets), unit (Millimeter, Centimeter, Meter, Inch, Foot) and one_file_per_body. STEP keeps the components (and the colours when SciForge's window is open); mesh files keep only the triangles. No exchange file keeps the timeline, sketches or parameters. The answer lists, after the file written, what this file does not keep of this design ("Not kept in this file:" and one line each: the timeline steps, sketches, hidden bodies, colours, names, bodies merged into one mesh...), the same facts File > Export's message shows; nothing is listed when nothing is lost.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `format` (required) | `step` \| `stl` \| `3mf` \| `iges` \| `stl_ascii` \| `obj` \| `brep` \| `dxf` |  |  |  |  |
| `path` (required) | string |  |  |  |  |
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies to write (default: every visible body) |
| `sketch` | string |  |  |  | format dxf: the sketch to write |
| `face` | object |  |  |  | format dxf: the flat face to write (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `refinement` | `Low` \| `Medium` \| `High` |  | `"Medium"` |  |  |
| `unit` | `Millimeter` \| `Centimeter` \| `Meter` \| `Inch` \| `Foot` |  | `"Millimeter"` |  |  |
| `one_file_per_body` | boolean |  | `false` |  | mesh formats: one file per body |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: format is missing; path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: an STL for 3D printing

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
{"tool": "export", "args": {"format": "stl", "path": "/home/me/sciforge/plate.stl"}}
```

The answer:

```text
Exported /home/me/sciforge/plate.stl (208 triangles).
Not kept in this file:
- the timeline (4 steps): the file holds the finished shapes only
- 2 sketches
- exact curves: 1 curved face become small flat triangles (within 0.0508 mm)
```

## Example 2: a STEP file for other CAD programs

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
{"tool": "export", "args": {"format": "step", "path": "/home/me/sciforge/plate.step"}}
```

The answer:

```text
Exported /home/me/sciforge/plate.step.
Not kept in this file:
- the timeline (4 steps): the file holds the finished shapes only
- 2 sketches
```

## More argument examples

- an STL for 3D printing:
  `{"format": "stl", "path": "/home/me/part.stl"}`
- Sketch1 as a DXF for a laser cutter:
  `{"format": "dxf", "path": "/home/me/outline.dxf", "sketch": "Sketch1"}`

## See also

- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
