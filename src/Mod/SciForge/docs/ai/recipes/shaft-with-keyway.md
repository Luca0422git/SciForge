# Recipe: stepped shaft with a keyway

Tags: shaft, keyway, revolve, slot, extrude-cut, chamfer, fillet, turned-part

A stepped shaft: 20 mm diameter for 30 mm, then 15 mm diameter for 30 mm, with a 6 mm wide,
20 mm long, 3.5 mm deep keyway in the large end (DIN 6885 for a 6 x 6 key on a 20 mm
shaft), 1 mm chamfers on both ends and a 1 mm fillet in the shoulder. Every call was run by
SciForge's tests; `expect` is what the answer must contain.

## 1. Revolve the half profile

The profile is drawn on XZ: sketch x is the radius (X), sketch y the length (Z). Revolving it
about Z gives pi (10^2 x 30 + 7.5^2 x 30) = 14726.2 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Shaft"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [
    {"polyline": [[0, 0], [10, 0], [10, 30], [7.5, 30], [7.5, 60], [0, 60]]}]}},
  {"tool": "revolve", "args": {"profile": "Sketch1", "axis": "Z"},
   "expect": {"contains": ["Its id is 'Revolve1'", "14726.2 mm3", "20 x 20 x 60 mm"]}}
]
```

## 2. The keyway: a slot cut from a tangent plane

The YZ plane with offset 10 is the plane x = 10 that touches the 20 mm cylinder; on YZ,
sketch x is the design's Y and sketch y is Z. A `slot` between the centre points (0, 8) and
(0, 22), 6 wide, is 20 mm long overall. Extruding a YZ sketch goes along +X, away from the
shaft, so the cut needs `flip: true` to go 3.5 mm into it (to x = 6.5).

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "YZ", "offset": 10, "geometry": [
    {"slot": [0, 8, 0, 22, 6], "name": "key"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 3.5, "operation": "cut",
    "flip": true},
   "expect": {"contains": ["Its id is 'Extrude1'"], "not_contains": ["Warning"]}},
  {"tool": "query_geometry", "args": {"select": {"type": "plane", "normal": [1, 0, 0],
    "count": 1}},
   "expect": {"json": {"elements.0.area_mm2": [112.274, 0.001],
     "elements.0.center_mm.0": [6.5, 0.0001]}}}
]
```

The keyway's floor is the flat face facing +X at x = 6.5; its area is the slot's,
14 x 6 + pi x 3^2 = 112.27 mm2, which proves the depth and the size.

## 3. Chamfer the ends, fillet the shoulder

`any_of` joins two selectors: the bottom circle (r 10 at z = 0) and the top circle (r 7.5 at
z = 60). The shoulder's inside corner is the circle of radius 7.5 at z = 30 (the circle of
radius 10 at z = 30 is the outside edge of the step).

```json sciforge-calls
[
  {"tool": "chamfer", "args": {"edges": {"any_of": [
    {"type": "circle", "radius": 10, "at": {"axis": "z", "value": "min"}, "count": 1},
    {"type": "circle", "radius": 7.5, "at": {"axis": "z", "value": "max"}, "count": 1}],
    "count": 2}, "distance": 1},
   "expect": {"contains": ["Its id is 'Chamfer1'"]}},
  {"tool": "fillet", "args": {"edges": {"type": "circle", "radius": 7.5,
    "at": {"axis": "z", "value": 30}, "count": 1}, "radius": 1},
   "expect": {"contains": ["Its id is 'Fillet1'"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "get_timeline", "args": {},
   "expect": {"json": {"steps.#": 6, "steps.4.id": "Chamfer1", "steps.5.id": "Fillet1"}}}
]
```

## Variations

- Another key size: `set_sketch_dimension` on Sketch2 (`get_sketch` lists the slot's
  dimensions) or `edit_step` on Extrude1 (`{"distance": 4}` for a deeper keyway).
- A thread on the small end: `thread` with `{"faces": {"type": "cylinder", "radius": 7.5,
  "count": 1}, "modeled": true}` (see [the threaded fastener](sciforge://docs/recipes/threaded-fastener.md)).
- A cross hole: a `hole` from a sketch on XZ (it drills along +Y through the shaft).
