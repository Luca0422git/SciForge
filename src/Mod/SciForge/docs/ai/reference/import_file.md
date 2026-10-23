# `import_file`: Insert file

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSERT > Insert Mesh / Insert DXF / Insert STEP, and Insert into Current Design. Category: Import and export. Changes the design (one undo step). Its undo step is named like "AI: Insert part.step". Needs nothing.

## What it does

Bring a file into the active design: STEP / IGES (one component with the file's structure, its bodies and colours), STL / OBJ / 3MF (a mesh body; unit: the file's unit), DXF (its curves into a new sketch on sketch_plane XY | XZ | YZ, ready to extrude), FCStd (another design's bodies as a component). label names what is made. The answer also lists what the file had that did not come in or came in changed ("Not brought in, or changed:" and one line each, as INSERT's message says: an open mesh, a 3MF's unit or colours, DXF texts, hatches and points, loose faces of a STEP...); a mesh whose file says another unit can be inserted again with unit.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `path` (required) | string |  |  |  | full path of the file |
| `unit` | `mm` \| `cm` \| `m` \| `in` \| `ft` |  | `"mm"` |  | mesh / DXF files: the file's unit |
| `sketch_plane` | `XY` \| `XZ` \| `YZ` |  | `"XY"` |  | DXF: the plane |
| `label` | string |  |  |  | the name of what is made |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: path is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: insert a STEP file (written first by the setup)

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 10, "width": 10, "height": 10}},
  {"tool": "export", "args": {"format": "step", "path": "/home/me/sciforge/part.step"}},
  {"tool": "new_design", "args": {"name": "Assembly"}}
]
```

The call:

```json
{"tool": "import_file", "args": {"path": "/home/me/sciforge/part.step"}}
```

The answer:

```text
Inserted part.step: part.step: 1 component, 1 body. Its id is 'Component'. Bodies now: Body001: 1000 mm3, 10 x 10 x 10 mm.
```

## More argument examples

- a motor model as a component:
  `{"path": "/home/me/parts/motor.step"}`
- a DXF outline as a sketch:
  `{"path": "/home/me/logo.dxf", "sketch_plane": "XY"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
