# Recipe: cantilever snap-fit hook

Tags: snap-fit, hook, cantilever, clip, 3d-printing, extrude, symmetric, fillet

A cantilever snap-fit on a 40 x 20 x 4 mm base: a beam 2 mm thick, 8 mm wide and 20 mm tall
with a 1.5 mm hook at its tip (a flat catch underneath and a sloped lead-in on top), and a
1 mm fillet at the beam's root, where the bending stress is highest. Every call was run by
SciForge's tests; `expect` is what the answer must contain.

## 1. Base plate

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Snap fit"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, -10, 40, 10]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 4},
   "expect": {"contains": ["3200 mm3", "40 x 20 x 4 mm"]}}
]
```

## 2. The beam and hook as one side profile

Draw the side view on XZ (sketch x is X, sketch y is Z): the beam from z = 4 (the base's
top) to z = 24, the catch at z = 20 sticking out 1.5 mm, the lead-in sloping back to the
beam at the top. Its area is 43 mm2. `direction: "symmetric"` extrudes 8 mm centred on the
sketch plane (y = -4 to 4), so the hook sits in the middle of the base. It touches the base
along a face, so it joins it into one solid: 3200 + 43 x 8 = 3544 mm3.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [
    {"polyline": [[18, 4], [20, 4], [20, 20], [21.5, 20], [20, 24], [18, 24]]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 8, "direction": "symmetric"},
   "expect": {"contains": ["Its id is 'Extrude2'", "3544 mm3", "40 x 20 x 24 mm"]}},
  {"tool": "inspect_design", "args": {}, "expect": {"json": {"bodies.0.solids": 1}}}
]
```

## 3. Root fillet

The beam's root on the inside of the bend is the straight edge along Y at x = 18, z = 4. A
1 mm fillet there adds (1 - pi / 4) x 8 = 1.72 mm3. Ask `query_geometry` first if unsure.

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [0, 1, 0], "at": [{"axis": "x", "value": 18}, {"axis": "z", "value": 4}]}},
   "expect": {"json": {"count": 1, "elements.0.length_mm": [8, 0.0001]}}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 1, 0],
    "at": [{"axis": "x", "value": 18}, {"axis": "z", "value": 4}], "count": 1}, "radius": 1},
   "expect": {"contains": ["3545.72 mm3"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

## Design notes

- The beam's strain at the root is about 1.5 h y / L^2 (h thickness 2, y deflection 1.5, L
  length 20): 1.1 %, fine for PLA / PETG (about 2 to 3 % allowed) when printed lying down.
- A longer or thinner beam bends more easily: change the polyline's points (`get_sketch`
  shows them) or redraw the profile.
- Print it with the beam lying flat (layers along the beam), never standing up.
