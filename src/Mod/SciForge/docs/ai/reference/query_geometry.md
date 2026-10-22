# `query_geometry`: Query geometry

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: Selection filters + INSPECT > Measure (on what a selector picks). Category: Inspect and measure. Read-only. Needs an open design.

## What it does

List the faces, edges or corners (vertices) of a body or step that a selector picks, with facts about each: type (plane, cylinder... / line, circle...), area mm2 or length mm, centre, normal of flat faces, axis and radius of round ones, start / end and direction of edges, bounding box. Each comes with ref: a selector that picks exactly that one element by its geometry (stable when FreeCAD renumbers faces), and pick: the same ready for measure, create_sketch face, construct_plane... Pass ref straight to fillet, chamfer, shell, draft (edges / faces) to change exactly that element. of: a body or step id (default the body being worked on; a step: the solid as it was after that step). element: faces (default), edges or vertices. select: a selector (default all; for vertices only at / all / count). limit: at most this many (default 60).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `of` | string |  |  |  | the body or step (default: the body being worked on) |
| `element` | `faces` \| `edges` \| `vertices` |  | `"faces"` |  |  |
| `select` | object |  |  |  | a selector (see get_help topic selectors); vertices take only at / all / count. Default: all |
| `limit` | integer |  | `60` | >= 1, <= 500 | at most this many elements |
| `refs` | boolean |  | `true` |  | give each element its stable reference |

## Answer

A plain sentence, then JSON with: `of`, `shape_of`, `element`, `count`, `shown`, `elements`, `note`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the round faces, with a ref for each

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
{"tool": "query_geometry", "args": {"select": {"type": "cylinder"}}}
```

The answer:

```text
1 face of body Body.
{
 "of": "Body",
 "shape_of": "Hole1",
 "element": "faces",
 "count": 1,
 "shown": 1,
 "elements": [
  {
   "name": "Face7",
   "type": "cylinder",
   "area_mm2": 251.327412,
   "center_mm": [30.0, 20.0, 5.0],
   "axis": [0.0, 0.0, -1.0],
   "axis_point_mm": [30.0, 20.0, 10.0],
   "radius_mm": 4.0,
   "diameter_mm": 8.0,
   "bbox_mm": [26.0, 16.0, 0.0, 34.0, 24.0, 10.0],
   "edges": 3,
   "ref": {"type": "cylinder", "radius": 4.0, "count": 1},
   "pick": {"face": {"type": "cylinder", "radius": 4.0, "count": 1}}
  }
 ],
 "note": "name (Face3...) is FreeCAD's number for the element now and changes when the model changes; ref is a selector that picks the same element by its geometry: use ref (or pick) in other tools. Coordinates are in mm, in Body's own coordinates."
}
```

## Example 2: the four top edges, each with a ref that picks only it

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
{"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}}}
```

The answer:

```text
4 edges of body Body.
{
 "of": "Body",
 "shape_of": "Extrude1",
 "element": "edges",
 "count": 4,
 "shown": 4,
 "elements": [
  {
   "name": "Edge4",
   "type": "line",
   "length_mm": 60.0,
   "center_mm": [30.0, 0.0, 10.0],
   "start_mm": [0.0, 0.0, 10.0],
   "end_mm": [60.0, 0.0, 10.0],
   "closed": false,
   "direction": [1.0, 0.0, 0.0],
   "ref": {
    "type": "line",
    "parallel": [1.0, 0.0, 0.0],
    "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "max"}],
    "count": 1
   },
   "pick": {
    "edge": {
     "type": "line",
     "parallel": [1.0, 0.0, 0.0],
     "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "max"}],
     "count": 1
    }
   }
  },
  {
   "name": "Edge7",
   "type": "line",
   "length_mm": 40.0,
   "center_mm": [60.0, 20.0, 10.0],
   "start_mm": [60.0, 0.0, 10.0],
   "end_mm": [60.0, 40.0, 10.0],
   "closed": false,
   "direction": [0.0, 1.0, 0.0],
   "ref": {
    "type": "line",
    "parallel": [0.0, 1.0, 0.0],
    "at": [{"axis": "x", "value": "max"}, {"axis": "z", "value": "max"}],
    "count": 1
   },
   "pick": {
    "edge": {
     "type": "line",
     "parallel": [0.0, 1.0, 0.0],
     "at": [{"axis": "x", "value": "max"}, {"axis": "z", "value": "max"}],
     "count": 1
    }
   }
  },
  {
   "name": "Edge10",
   "type": "line",
   "length_mm": 60.0,
   "center_mm": [30.0, 40.0, 10.0],
   "start_mm": [60.0, 40.0, 10.0],
   "end_mm": [0.0, 40.0, 10.0],
   "closed": false,
   "direction": [-1.0, 0.0, 0.0],
   "ref": {
    "type": "line",
    "parallel": [-1.0, 0.0, 0.0],
    "at": [{"axis": "y", "value": "max"}, {"axis": "z", "value": "max"}],
    "count": 1
... (37 more lines)
```

## More argument examples

- every round face: the holes and bosses:
  `{"select": {"type": "cylinder"}}`
- the edges at the top, each with a selector fillet can take:
  `{"element": "edges", "select": {"at": {"axis": "z", "value": "max"}}}`
- the corners after Extrude1:
  `{"of": "Extrude1", "element": "vertices"}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
