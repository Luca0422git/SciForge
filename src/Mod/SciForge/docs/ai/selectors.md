# Selectors: picking faces, edges and corners

In Fusion you click a face or an edge. SciForge's tools pick them with a selector instead: an
object that describes the geometry a person would click ("the four straight edges at the
top"), never internal names like `Edge7` (those change whenever the model changes). Every
tool that takes `edges`, `faces`, `face`, `select`, a pick (`{"face": ...}`) or a highlight
uses this language; [query_geometry](sciforge://tools/query_geometry) shows what a selector
picks before you use it.

## The filters

All filters are optional; they combine with AND and are applied in this order:

| Filter | For | Keeps |
|---|---|---|
| `type` | edges: `line`, `circle` (also arcs), `ellipse`, `bspline`; faces: `plane`, `cylinder`, `cone`, `sphere`, `torus`, `bspline`, `extrusion` (the side of an extruded spline or ellipse) | elements of that kind |
| `normal` | faces | flat faces whose outward normal points exactly that way (`[0, 0, 1]`: facing up) |
| `parallel` | edges (and faces) | straight edges parallel to the direction, either sense; for faces: flat faces whose normal is parallel to it (both sides of a plate) |
| `along` | faces | faces that run along the direction (their normal is square to it everywhere): the side walls of a part extruded that way, flat, round or free-form |
| `radius` | edges, faces | circles, cylinders and spheres of this radius (within 0.000001 mm) |
| `on_faces` | edges | the edges that bound the faces a face selector picks |
| `not_on_faces` | edges | the edges that do not bound those faces |
| `at` | any | `{"axis": "x"/"y"/"z", "value": "max"/"min"/a number}`: the elements whose centre is at the extreme (or at that coordinate, within 0.0001 mm) along the axis, among those the filters above kept; a list of conditions applies each in turn |
| `all` | any | every element (combine only with `count`) |
| `count` | any | not a filter: the pick must have exactly this many elements, or the tool fails and changes nothing. Always give it to tools that change the design |
| `any_of` | any | `[selector, ...]`: the union of several selectors (each may have its own `count`) |

Facts that matter:
- "Centre" in `at` is the element's centre of mass: a straight edge's middle, a circle's
  centre, a flat face's centroid, a cylinder face's point on its axis halfway along it. A
  full round hole's top edge has its centre on the hole's axis.
- Selectors look at the current body as it is now (or the body / step given with `of` where
  a tool takes it). After a change the faces are different: select again, do not reuse a
  list of names.
- Vertices (corners: `query_geometry` with `element: "vertices"`, or a body pick's
  `{"vertex": {"at": ...}}`) take only `at`, `all` and `count`.
- A cylinder face has a seam: a straight edge along it. A plate with a round hole has five
  straight vertical edges (four corners and the hole's seam): exclude the hole with
  `not_on_faces`, or pick by `at`.
- A fillet on a straight edge is a cylinder face (a fillet on a circle a torus): after
  filleting, `type: cylinder` also picks the fillets; add `radius`.
- When a count is wrong the answer lists what the selector picked: `selector {...} picked 4
  edges, expected 3: Edge4, Edge7, Edge10, Edge12`.

## References from query_geometry

`query_geometry` answers each element with its facts (type, area / length, centre, normal,
axis and radius, start / end, bounding box) and a `ref`: a selector SciForge built and checked
that picks exactly that one element by its geometry, plus `pick`, the same as a pick
(`{"edge": ref}`) for `measure`, `construct_*` or `create_sketch` `face`. Give `ref` straight
to fillet / chamfer / shell / draft; join several with `any_of`. A `ref` carries `body`, the
body it was made for: those tools work on the active body and refuse a ref made for another
one (activate it first), instead of changing the matching element of the wrong body.

<a id="cookbook"></a>

## Cookbook

The part used below: a 60 x 40 x 10 plate (x 0 to 60, y 0 to 40, z 0 to 10) with an 8 mm hole
through its middle, then with its vertical corners rounded. Each call is checked by
SciForge's tests (`expect` gives what the selector picks).

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Cookbook"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

Faces:

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"select": {"normal": [0, 0, 1], "count": 1}},
   "expect": {"json": {"elements.0.center_mm.2": [10, 0.0001]}}},
  {"tool": "query_geometry", "args": {"select": {"normal": [0, 0, -1], "count": 1}},
   "expect": {"json": {"elements.0.center_mm.2": [0, 0.0001]}}},
  {"tool": "query_geometry", "args": {"select": {"normal": [0, 0, 1],
    "at": {"axis": "z", "value": "max"}, "count": 1}}, "expect": {"json": {"count": 1}}},
  {"tool": "query_geometry", "args": {"select": {"along": [0, 0, 1], "type": "plane", "count": 4}},
   "expect": {"json": {"count": 4}}},
  {"tool": "query_geometry", "args": {"select": {"along": [0, 0, 1]}},
   "expect": {"json": {"count": 5}}},
  {"tool": "query_geometry", "args": {"select": {"normal": [1, 0, 0], "count": 1}},
   "expect": {"json": {"elements.0.center_mm.0": [60, 0.0001]}}},
  {"tool": "query_geometry", "args": {"select": {"parallel": [1, 0, 0], "count": 2}},
   "expect": {"json": {"count": 2}}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 4, "count": 1}},
   "expect": {"json": {"elements.0.axis_point_mm.0": [30, 0.0001]}}}
]
```

| Want | Selector |
|---|---|
| the top face | `{"normal": [0, 0, 1], "count": 1}` (with bosses or steps add `"at": {"axis": "z", "value": "max"}`) |
| the bottom face | `{"normal": [0, 0, -1], "count": 1}` |
| the four flat side walls | `{"along": [0, 0, 1], "type": "plane", "count": 4}` (without `type` the hole's wall counts too) |
| the right side (x = 60) | `{"normal": [1, 0, 0], "count": 1}` |
| the left and right sides together | `{"parallel": [1, 0, 0], "count": 2}` |
| the hole's wall | `{"type": "cylinder", "radius": 4, "count": 1}` |

Edges:

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "at": {"axis": "z", "value": "max"}, "count": 4}}, "expect": {"json": {"count": 4}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [0, 0, 1]}}, "expect": {"json": {"count": 5}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [0, 0, 1], "not_on_faces": {"type": "cylinder"}, "count": 4}},
   "expect": {"json": {"count": 4}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"on_faces":
    {"normal": [0, 0, 1], "count": 1}}}, "expect": {"json": {"count": 5}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "circle",
    "radius": 4, "at": {"axis": "z", "value": "max"}, "count": 1}},
   "expect": {"json": {"elements.0.center_mm": [30.0, 20.0, 10.0]}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [1, 0, 0], "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "max"}],
    "count": 1}}, "expect": {"json": {"elements.0.center_mm": [30.0, 0.0, 10.0]}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"any_of": [
    {"type": "circle", "radius": 4, "at": {"axis": "z", "value": "max"}, "count": 1},
    {"type": "circle", "radius": 4, "at": {"axis": "z", "value": "min"}, "count": 1}],
    "count": 2}}, "expect": {"json": {"count": 2}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "at": {"axis": "z", "value": "max"}, "count": 3}},
   "expect": {"error": true, "contains": ["picked 4 edges, expected 3"]}}
]
```

| Want | Selector |
|---|---|
| the four top edges | `{"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}` (`type` keeps the hole's circle out) |
| the four vertical corner edges of a part with a round hole | `{"type": "line", "parallel": [0, 0, 1], "not_on_faces": {"type": "cylinder"}, "count": 4}` |
| every edge around the top face | `{"on_faces": {"normal": [0, 0, 1], "count": 1}}` (4 lines and the hole's circle) |
| the hole's top edge (to chamfer it) | `{"type": "circle", "radius": 4, "at": {"axis": "z", "value": "max"}, "count": 1}` |
| one particular edge: the front top edge | `{"type": "line", "parallel": [1, 0, 0], "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "max"}], "count": 1}` |
| both ends of the hole | `{"any_of": [{...top circle...}, {...bottom circle...}], "count": 2}` |

After a fillet on the vertical corners, the fillet faces are cylinders too:

```json sciforge-calls
[
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1],
    "not_on_faces": {"type": "cylinder"}, "count": 4}, "radius": 3}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder"}},
   "expect": {"json": {"count": 5}}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 3, "count": 4}},
   "expect": {"json": {"count": 4}}},
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "at": {"axis": "z", "value": "max"}, "count": 4}},
   "expect": {"json": {"elements.0.length_mm": [54, 0.0001]}}},
  {"tool": "query_geometry", "args": {"element": "vertices",
    "select": {"at": {"axis": "z", "value": "max"}}}, "expect": {"json": {"count": 9}}}
]
```

The top edges are now 54 and 34 mm long (the corners went into the fillets), and the top has
9 corners: 8 where the straight edges meet the fillets' arcs and the hole's seam point.

## Picks

Tools that need one element or a reference (measure, construction geometry, sketch planes,
revolve axes) take a pick: `{"plane": "XY"}`, `{"axis": "Z"}`, `{"origin": true}`,
`{"face": selector}`, `{"edge": selector}`, `{"vertex": [x, y, z]}` (a corner of the part) or
`{"construct": id}` (a construction plane, axis or point). Face and edge selectors in a pick
must pick exactly one element. Tools that work across bodies take body picks:
`{"face": selector, "of": step id}`, `{"edge": selector, "of": step id}`, `{"vertex": {"at":
...}, "of": step id}` or `{"body": step id}`; `of` names a step whose body the selector looks
at.

```json sciforge-calls
[
  {"tool": "measure", "args": {"a": {"face": {"normal": [0, 0, 1], "count": 1}},
    "b": {"plane": "XY"}}, "expect": {"contains": ["distance 10 mm"]}},
  {"tool": "measure", "args": {"a": {"edge": {"type": "circle", "radius": 4,
    "at": {"axis": "z", "value": "max"}, "count": 1}}},
   "expect": {"contains": ["radius"]}}
]
```
