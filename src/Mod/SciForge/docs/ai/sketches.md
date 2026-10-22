# Sketches and profiles

A sketch is a flat drawing on a plane; its closed areas are the profiles that solid features
use (Fusion's sketches and profiles). This page covers where sketches go, what can be drawn,
how areas become profiles, and how to change a sketch later. Every call block is run by
SciForge's tests (`expect` is what the answer must contain).

## Where a sketch goes

- An origin plane, `"plane": "XY" | "XZ" | "YZ"`, moved along its normal by `offset` (XY +Z,
  XZ -Y, YZ +X: see [coordinates](sciforge://docs/handbook.md#units-and-coordinates)).
- A flat face of the part, `"face": selector` (exactly one face). The sketch moves with the
  face when the part changes. `auto_project: true` projects the face's edges into it.
- A construction plane, `"on": id` (from `construct_plane`: offset, at an angle, tangent,
  midplane, through three points...).

A sketch on an origin plane with an offset stays where it is when the part changes; a sketch
on a face follows the face. `get_sketch` reports the placement (origin, normal, x axis), so
you never have to guess a face sketch's axes.

## What can be drawn

`create_sketch` takes `geometry`, a list of closed shapes (and lines); `create_curve_sketch`
takes `curves`, open curves and points; `add_to_sketch` adds either to an existing sketch.

| Item | Form | Notes |
|---|---|---|
| `rect` | `[x0, y0, x1, y1]` two opposite corners | named: `<name>.width`, `.height`, `.x`, `.y` |
| `center_rect` | `[cx, cy, width, height]` | |
| `circle` | `[cx, cy, radius]` | named: `<name>.diameter`, `.x`, `.y` |
| `polyline` | `[[x, y], ...]` at least 3 corners | always closed in `create_sketch`; open in `create_curve_sketch` |
| `polygon` | `{center, radius, sides, rotation}` | corners on `radius` (a hexagon 13 across flats: radius 13 / sqrt 3) |
| `slot` | `[x1, y1, x2, y2, width]` | straight slot between two centre points |
| `ellipse` | `[cx, cy, major, minor]` | major radius along sketch x |
| `spline_loop` | `[[x, y], ...]` | a closed smooth curve through the points |
| `segments` | `[{line}, {arc}, {spline}, ...]` | a closed chain; arcs `[cx, cy, r, a0, a1]` counter-clockwise |
| `line` | `[x0, y0, x1, y1]` | an open line: no area |
| curves: `line`, `arc`, `circle`, `point`, `polyline` | (create_curve_sketch) | paths, rails, rib / web curves, hole points |

Give a shape a `name` to get named dimensions; an unnamed shape's dimensions are called
`g<index>.width`, `g<index>.diameter`... after its place in the list (`g0`, `g1`...).
`sketch_text` writes text (a font's outlines: areas for extrude or emboss);
`sketch_polygon` draws a regular polygon by centre and a point that is the middle of an
edge (the default, `circumscribed`; `diameter` is then across the flats) or a corner
(`circumscribed: false`), with a dimension; `sketch_trim`
trims curves at a point; `sketch_delete` removes curves or constraints by index.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Sketches"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [
    {"rect": [0, 0, 60, 40], "name": "plate"}, {"circle": [30, 20, 5]}]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch1"},
   "expect": {"json": {"closed_areas.#": 2, "fully_constrained": true},
     "contains": ["plate.width", "plate.height", "g1.diameter"]}}
]
```

## Areas and profiles

The closed areas of a sketch are its profiles. Shapes inside each other make separate areas:
a circle inside a rectangle makes a ring area and a disc area (`get_sketch` lists each area
with its size and a point inside it). Without `regions`, extrude and revolve use the outer
areas with the shapes inside them as holes: that sketch extrudes as a plate with a hole.
`regions` picks areas by a point inside each (sketch coordinates); pick both the ring and
the disc to get a full plate.

```json sciforge-calls
[
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10},
   "expect": {"contains": ["23214.6 mm3"]}},
  {"tool": "undo", "args": {}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10, "regions": [[30, 20]]},
   "expect": {"contains": ["785.398 mm3", "10 x 10 x 10 mm"]}},
  {"tool": "undo", "args": {}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10,
    "regions": [[5, 5], [30, 20]]}, "expect": {"contains": ["24000 mm3"]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10, "regions": [[70, 70]]},
   "expect": {"error": true}}
]
```

Separate shapes side by side are separate areas, all extruded. A `line` alone makes no area;
lines that close a loop together do (a triangle of three lines is an area). Open curves
(create_curve_sketch) are extruded only as thin walls (`extrude` with `curves` and `thin`).

## Constraints and dimensions

Shapes made by `create_sketch` come with their constraints and dimensions (a rectangle is
fully constrained: Fusion's padlock). `get_sketch` lists every curve and constraint by index,
the degrees of freedom left, and conflicting or redundant constraints; `inspect_design` and
`check_design` give every sketch's `fully_constrained` and `degrees_of_freedom` (how many
ways its curves can still move; 0 and fully constrained: the padlock the person sees in the
browser and the timeline).

- `sketch_constraint` adds coincident, horizontal, vertical, parallel, perpendicular,
  tangent, equal, collinear, concentric, midpoint, symmetric, fix, point_on, smooth; items
  are curves by index with the point that matters (`start`, `end`, `center`, `whole`).
- `sketch_dimension` adds a driving dimension (distance, distance_x / distance_y, radius,
  diameter, angle) with a value or a formula, and a `name`.
- `set_sketch_dimension` changes a dimension by name or index, to a value or a formula
  (`expression`; an empty expression removes the formula). Everything built from the sketch
  updates.
- A constraint or dimension that conflicts with the sketch is not added: the answer names the
  constraints it fights with, in the words the sketch tools use in the window ("Vertical:
  not added, it conflicts with the 50 mm dimension 'len'") and by index (`constraint 1 of
  Sketch1`, for sketch_delete or set_sketch_dimension). One that the sketch already says is
  not added either ("..., the 50 mm dimension 'len' already makes it so"). A new value for a
  dimension that the sketch cannot take says what it conflicts with ("That value does not
  fit: it conflicts with ...").

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Constraints"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XY", "curves": [{"line": [0, 0, 40, 3]}]}},
  {"tool": "sketch_constraint", "args": {"sketch": "Sketch1", "kind": "horizontal",
    "items": [{"curve": 0}]}, "expect": {"contains": ["Done"]}},
  {"tool": "sketch_dimension", "args": {"sketch": "Sketch1", "kind": "distance",
    "items": [{"curve": 0}], "value": 50, "name": "len"},
   "expect": {"contains": ["constraint 1 of Sketch1 = 50.00 mm"]}},
  {"tool": "sketch_constraint", "args": {"sketch": "Sketch1", "kind": "vertical",
    "items": [{"curve": 0}]}, "expect": {"error": true, "contains": [
    "Vertical: not added, it conflicts with the 50 mm dimension 'len'",
    "constraint 1 of Sketch1"]}},
  {"tool": "sketch_dimension", "args": {"sketch": "Sketch1", "kind": "distance_x",
    "items": [{"curve": 0, "point": "start"}, {"curve": 0, "point": "end"}], "value": 50},
   "expect": {"error": true, "contains": ["the 50 mm dimension 'len' already makes it so"]}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"sketches.0.fully_constrained": false,
     "sketches.0.degrees_of_freedom": 2}}},
  {"tool": "set_sketch_dimension", "args": {"sketch": "Sketch1", "constraint": "len",
    "value": 60}, "expect": {"contains": ["len = 60"]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch1"},
   "expect": {"json": {"geometry.0.length": [60, 0.0001]}}}
]
```

## Sketches on faces and construction planes

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Planes"}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "length": 40, "width": 30,
    "height": 10}},
  {"tool": "create_sketch", "args": {"face": {"normal": [0, 0, 1], "count": 1},
    "geometry": [{"circle": [20, 15, 5]}]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch1"},
   "expect": {"json": {"placement.origin.2": [10, 0.0001], "placement.normal": [0.0, 0.0, 1.0],
     "placement.x_axis": [1.0, 0.0, 0.0]}}},
  {"tool": "construct_plane", "args": {"preset": "OffsetPlane", "refs": [{"plane": "XY"}],
    "distance": 25}, "expect": {"contains": ["Its id is 'Plane'"]}},
  {"tool": "create_sketch", "args": {"on": "Plane", "geometry": [{"circle": [0, 0, 3]}]}},
  {"tool": "get_sketch", "args": {"sketch": "Sketch2"},
   "expect": {"json": {"placement.origin.2": [25, 0.0001]}}}
]
```

The construction plane's id is the one its answer gives (`Plane` here, not `Plane1`): pass it
to `create_sketch` as `on`.

## Changing a sketch later

- Move or resize a named shape: `set_sketch_dimension` (`plate.width`, `g1.diameter`...).
- Add shapes: `add_to_sketch` (closed `geometry` and open `curves`; `construction: true`
  for construction lines that make no area).
- Remove: `sketch_delete` (curves or constraints by index, from `get_sketch`).
- The steps built from the sketch update, and keep their faces where they can; the answer
  names any that break.
