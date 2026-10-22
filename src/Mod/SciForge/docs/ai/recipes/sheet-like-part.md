# Recipe: sheet-like U bracket (thin extrude with bends)

Tags: sheet-metal, sheet, thin, thin-extrude, open-profile, bend, fillet_sets, hole, u-bracket

A U-shaped bracket bent from 2 mm sheet: a 40 mm wide base with two 25 mm legs, 30 mm deep,
inside bend radius 2 (outside 4) and a 5 mm hole in the base. SciForge has no sheet metal
workspace yet; a thin extrude of an open profile with the bends rounded gives the same solid.
Every call was run by SciForge's tests; `expect` is what the answer must contain.

## 1. The open profile, thin extruded

[create_curve_sketch](sciforge://docs/reference/create_curve_sketch.md) draws open curves (a
`create_sketch` polyline is always closed). An extrude of `curves` needs `thin`: a wall of
`thickness` along the curve. `location: "side1"` puts the wall on the curve's left: the
curve runs down the left leg, along the base and up the right leg, so its left is the inside
of the U (the drawn lines are the outside of the sheet). On XZ, sketch x is X and sketch y is
Z; the extrude goes along -Y. Area 25 x 2 + 40 x 2 + 25 x 2 - 2 x 2 x 2 (the corners counted
once) = 172 mm2, x 30 = 5160 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "U bracket"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "curves": [
    {"polyline": [[0, 25], [0, 0], [40, 0], [40, 25]]}]},
   "expect": {"contains": ["Its id is 'Sketch1'"]}},
  {"tool": "extrude", "args": {"curves": "Sketch1", "distance": 30,
    "thin": {"location": "side1", "thickness": 2}},
   "expect": {"contains": ["Its id is 'Extrude1'", "5160 mm3", "40 x 30 x 25 mm"]}}
]
```

## 2. The bends

A bend is a fillet on the outside corner (radius = inside radius + thickness) and on the
inside corner, so the sheet stays 2 mm thick around it. The outside corners are the straight
edges along Y at z = 0 (x = 0 and x = 40), the inside ones those at z = 2.
[fillet_sets](sciforge://docs/reference/fillet_sets.md) does both radii in one step: -2 x 16 (1 - pi / 4)
x 30 + 2 x 4 (1 - pi / 4) x 30 = -154.5 mm3.

```json sciforge-calls
[
  {"tool": "fillet_sets", "args": {"sets": [
    {"edges": {"type": "line", "parallel": [0, 1, 0], "at": {"axis": "z", "value": 0},
     "count": 2}, "radius": 4},
    {"edges": {"type": "line", "parallel": [0, 1, 0], "at": {"axis": "z", "value": 2},
     "count": 2}, "radius": 2}]},
   "expect": {"contains": ["5005.49 mm3"]}}
]
```

## 3. A hole in the base

The base's top (inside) face is at z = 2: a hole sketched on XY with offset 2 drills down
through the base. The part runs from y = -30 to 0, so the middle is y = -15.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 2, "geometry": [
    {"circle": [20, -15, 1]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 5, "through_all": true},
   "expect": {"contains": ["4966.22 mm3"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.bbox_mm.min": [0.0, -30.0, 0.0],
     "bodies.0.bbox_mm.max": [40.0, 0.0, 25.0]}}}
]
```

## Variations

- Flanges out instead of in: `location: "side2"` puts the wall on the curve's right.
- Another thickness: `edit_step` on Extrude1 does not reach the thin options yet: redraw.
  (Check with `get_step` which options a step has.)
- Tabs and slots: cut them with `extrude` (`operation: "cut"`) from sketches on the legs'
  faces (`create_sketch` with `face`).
