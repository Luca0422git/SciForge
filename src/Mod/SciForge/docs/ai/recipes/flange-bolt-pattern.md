# Recipe: flange with a bolt circle

Tags: flange, bolt-pattern, pcd, revolve, hole, circular_pattern, fillet, chamfer, turned-part

A pipe flange: a 100 mm disc, 10 mm thick, with a 40 mm hub 30 mm tall, a 20 mm bore, a
3 mm fillet where the hub meets the disc, and six 9 mm bolt holes (for M8) on a 70 mm pitch
circle. Turned parts are best drawn as a half profile and revolved, as in Fusion. Every call
was run by SciForge's tests; `expect` is what the answer must contain.

## 1. Revolve the half profile

On the XZ plane sketch x is the radius (the design's X) and sketch y is the height (Z). The
profile includes the bore (it starts at radius 10), so no separate cut is needed. Pappus:
pi (50^2 - 10^2) x 10 + pi (20^2 - 10^2) x 20 = 94247.8 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Flange"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [
    {"polyline": [[10, 0], [50, 0], [50, 10], [20, 10], [20, 30], [10, 30]]}]}},
  {"tool": "revolve", "args": {"profile": "Sketch1", "axis": "Z"},
   "expect": {"contains": ["Its id is 'Revolve1'", "94247.8 mm3", "100 x 100 x 30 mm"]}}
]
```

## 2. One bolt hole, then the circular pattern

A hole only needs its centre: draw a small circle where it goes, on a sketch in the plane of
the face it drills into (the disc's top, z = 10). Then repeat the hole step around Z with
[circular_pattern](sciforge://docs/reference/circular_pattern.md): `quantity` counts the original too.
Each hole removes pi x 4.5^2 x 10 = 636.17 mm3.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [
    {"circle": [35, 0, 1]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 9, "through_all": true},
   "expect": {"contains": ["Its id is 'Hole1'", "93611.6 mm3"]}},
  {"tool": "circular_pattern", "args": {"features": ["Hole1"], "axis": "Z", "quantity": 6},
   "expect": {"contains": ["90430.7 mm3"]}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 4.5}},
   "expect": {"json": {"count": 6}}}
]
```

## 3. Fillet the hub, chamfer the bore

The inside corner between the hub and the disc is the circle of radius 20 at z = 10 (the
hub's outer circle at the top, z = 30, has the same radius: `at` tells them apart). The
bore's top edge is the circle of radius 10 at the top.

```json sciforge-calls
[
  {"tool": "fillet", "args": {"edges": {"type": "circle", "radius": 20,
    "at": {"axis": "z", "value": 10}, "count": 1}, "radius": 3},
   "expect": {"contains": ["Its id is 'Fillet1'"]}},
  {"tool": "chamfer", "args": {"edges": {"type": "circle", "radius": 10,
    "at": {"axis": "z", "value": "max"}, "count": 1}, "distance": 1},
   "expect": {"contains": ["Its id is 'Chamfer1'"]}},
  {"tool": "diff_design", "args": {"since": "Fillet1"},
   "expect": {"contains": ["Chamfer1"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.solids": 1, "bodies.0.valid": true,
     "bodies.0.volume_mm3": [90649.1, 0.5]}}}
]
```

The fillet adds the corner's spandrel turned around the axis (about +250.8 mm3) and the
chamfer removes a 1 x 1 triangle turned at radius 10.33 (about -32.5 mm3).

## Variations

- More holes or another circle: `edit_step` on the pattern (`{"step": "Pattern1",
  "set": {"quantity": 8}}`, the id the pattern answered) and on the hole sketch
  (`set_sketch_dimension` on its `g0.x`).
- A raised face: another revolve, or `press_pull` on the disc's top face.
- Bolt holes from a standard: `hole` with `tap_type: "clearance"`, `standard: "iso"`,
  `size: "8"`, `fit: "normal"` sizes the hole for M8 by itself.
