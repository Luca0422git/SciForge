# Recipe: threaded fastener (hex bolt M8 x 30)

Tags: bolt, screw, fastener, thread, hexagon, polygon, chamfer, modeled-thread

A hex head bolt M8 x 30: a 13 mm across-flats head 5.3 mm high (ISO 4017), a 30 mm shank
of 8 mm with a 0.8 mm chamfer at its end, and a real (modeled) M8 x 1.25 thread on the last
22 mm. Every call was run by SciForge's tests; `expect` is what the answer must contain.

For a standard screw that only has to be in an assembly, `insert_hardware` is quicker (it
places an ISO screw with its hole, see its [reference page](sciforge://docs/reference/insert_hardware.md));
this recipe models one for printing, machining or a custom size.

## 1. The hexagon head

`polygon` items have their corners on `radius`; a hexagon 13 mm across the flats has its
corners on 13 / sqrt(3) = 7.5056 mm. Area 3 sqrt(3) / 2 x 7.5056^2 = 146.36 mm2, so the
head is 775.7 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Bolt M8x30"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [
    {"polygon": {"center": [0, 0], "radius": 7.5056, "sides": 6}}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 5.3},
   "expect": {"contains": ["Its id is 'Extrude1'", "775.7"]}}
]
```

## 2. The shank, downwards

The shank's sketch is on XY at z = 0 (the head's underside); an XY extrude goes up (+Z)
unless `flip` is true, so `flip: true` sends the 30 mm shank down to z = -30. It joins the
head: pi x 4^2 x 30 = 1508.0 mm3 more.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [0, 0, 4]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 30, "flip": true},
   "expect": {"contains": ["Its id is 'Extrude2'", "2283.6"]}},
  {"tool": "chamfer", "args": {"edges": {"type": "circle", "radius": 4,
    "at": {"axis": "z", "value": "min"}, "count": 1}, "distance": 0.8},
   "expect": {"contains": ["Its id is 'Chamfer1'"]}}
]
```

## 3. The thread

[thread](sciforge://docs/reference/thread.md) takes the size from the cylinder (8 mm: M8 x 1.25 coarse).
`modeled: true` cuts the real ISO 68-1 groove (a cosmetic thread, the default, changes
nothing in the solid: only drawings and the timeline know it). `full_length: false` with
`length` threads part of the shank.

```json sciforge-calls
[
  {"tool": "inspect_design", "args": {}, "expect": {"json": {"bodies.0.volume_mm3": [2276.15, 0.05]}}},
  {"tool": "thread", "args": {"faces": {"type": "cylinder", "radius": 4, "count": 1},
    "modeled": true, "full_length": false, "length": 22},
   "expect": {"contains": ["Done"]}},
  {"tool": "diff_design", "args": {"since": "last_change"},
   "expect": {"contains": ["volume"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true, "bodies.0.solids": 1}}}
]
```

`diff_design` since `last_change` proves the thread cut material (a cosmetic thread would
show no volume change).

## Variations

- A nut: a hexagon extruded 6.8 mm with a `hole` that has `tap_type: "tapped"`,
  `designation: "M8x1.25"` and `modeled: true`.
- Another size: change the polygon radius (across flats / sqrt(3)), the circle and the
  thread follows the cylinder (or give `designation`).
- A socket head: a 13 mm `circle` head, then a hexagon socket cut with `extrude`
  (`operation: "cut"`, `flip: true` from a sketch on the head's top face).
