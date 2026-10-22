# Recipe: L bracket with mounting holes

Tags: bracket, sheet, extrude, hole, fillet, chamfer, material, beginner

An L-shaped angle bracket, 60 mm wide, with a 40 mm base and a 40 mm upright, 5 mm thick,
a 4 mm fillet in the inside corner (it makes the bend stronger), a chamfer on the outside
corner and two 6.5 mm clearance holes (for M6 screws) in each leg. Every call below was run
by SciForge's tests; the `expect` part of each call is what the answer must contain, not a
tool argument.

Fusion users would draw the L profile on a side plane and extrude it; that is exactly what
happens here.

## 1. The L profile, extruded

The profile is drawn on the YZ plane: sketch x is the design's Y and sketch y is Z (see
[coordinates](sciforge://docs/handbook.md#units-and-coordinates)). Extruding a YZ sketch
goes along +X. The L's area is 40 x 5 + 5 x 35 = 375 mm2, so 60 mm of it is 22500 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Bracket"}},
  {"tool": "create_sketch", "args": {"plane": "YZ", "geometry": [
    {"polyline": [[0, 0], [40, 0], [40, 5], [5, 5], [5, 40], [0, 40]]}]},
   "expect": {"contains": ["Its id is 'Sketch1'"]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 60},
   "expect": {"contains": ["Its id is 'Extrude1'", "22500 mm3", "60 x 40 x 40 mm"]}}
]
```

## 2. Inside fillet and outside chamfer

The inside corner is the straight edge along X at y = 5, z = 5. Ask
[query_geometry](sciforge://docs/reference/query_geometry.md) first when you are not sure a selector
picks the right edge: it lists what the selector picks, with a `ref` that picks exactly that
edge. A fillet in an inside corner adds material: (r^2 - pi r^2 / 4) x 60 = 206.0 mm3 for
r = 4. The outside corner (y = 0, z = 0) gets a 2 mm chamfer, which removes 2 x 2 / 2 x 60 =
120 mm3.

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [1, 0, 0], "at": [{"axis": "y", "value": 5}, {"axis": "z", "value": 5}],
    "count": 1}},
   "expect": {"json": {"count": 1, "elements.0.length_mm": [60, 0.001]}}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [1, 0, 0],
    "at": [{"axis": "y", "value": 5}, {"axis": "z", "value": 5}], "count": 1}, "radius": 4},
   "expect": {"contains": ["Its id is 'Fillet1'", "22706 mm3"]}},
  {"tool": "chamfer", "args": {"edges": {"type": "line", "parallel": [1, 0, 0],
    "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "min"}], "count": 1},
    "distance": 2},
   "expect": {"contains": ["Its id is 'Chamfer1'", "22586 mm3"]}}
]
```

## 3. Holes in the base and in the upright

A hole drills against its sketch's normal, into the face the sketch lies on. The base's top
face is at z = 5, so its hole sketch is the XY plane with offset 5. The upright's outside
face is the XZ plane itself (y = 0, normal -Y), so a hole sketched on XZ drills along +Y
into the upright; on XZ, sketch x is X and sketch y is Z. Each 6.5 mm hole through 5 mm
removes pi x 3.25^2 x 5 = 165.9 mm3.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 5, "geometry": [
    {"circle": [15, 25, 3.25]}, {"circle": [45, 25, 3.25]}]},
   "expect": {"contains": ["Its id is 'Sketch2'"]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 6.5, "through_all": true},
   "expect": {"contains": ["Its id is 'Hole1'", "22254.2 mm3"]}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [
    {"circle": [15, 28, 3.25]}, {"circle": [45, 28, 3.25]}]},
   "expect": {"contains": ["Its id is 'Sketch3'"]}},
  {"tool": "hole", "args": {"sketch": "Sketch3", "diameter": 6.5, "through_all": true},
   "expect": {"contains": ["Its id is 'Hole2'", "21922.4 mm3"]}}
]
```

## 4. Material, then check everything

[physical_material](sciforge://docs/reference/physical_material.md) sets the density, so the mass is
right: aluminium (2.7 g/cm3) gives about 59.2 g. [check_design](sciforge://docs/reference/check_design.md)
confirms one valid closed solid and no failed step; [query_geometry](sciforge://docs/reference/query_geometry.md)
confirms the four holes.

```json sciforge-calls
[
  {"tool": "physical_material", "args": {"body": "Extrude1", "material": "aluminium"}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.#": 1, "bodies.0.valid": true, "bodies.0.solids": 1,
     "bodies.0.volume_mm3": [21922.36, 0.05], "bodies.0.mass_g": [59.19, 0.05],
     "summary.failed_steps": []}}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 3.25}},
   "expect": {"json": {"count": 4}}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "render", "args": {"view": "iso", "width": 640, "height": 480},
   "expect": {"image": [640, 480]}}
]
```

## Variations

- Thicker bracket: `edit_step` on Extrude1 does not change the thickness (it is in the
  sketch); the profile's corners are in Sketch1, so redraw it, or build the profile from
  named rectangles and change them with `set_sketch_dimension`
  (see [the parametric plate](sciforge://docs/recipes/parametric-plate.md)).
- Counterbored holes: give `counterbore: {"diameter": 11, "depth": 3}` to `hole`.
- Slotted holes: draw `slot` items in the hole sketch and cut them with `extrude`
  (`operation: "cut"`, `through_all: true`, `flip: true` for a sketch on the top face).
