# Recipe: revolved knob with grip grooves

Tags: knob, revolve, grip, knurl, circular_pattern, extrude-cut, fillet, turned-part

A 40 mm control knob, 20 mm tall with a chamfered top, 18 grip grooves around it, a 6 mm
bore for the shaft from below and a rounded top edge. Every call was run by SciForge's tests;
`expect` is what the answer must contain.

## 1. Revolve the profile

Half profile on XZ (sketch x is the radius, sketch y the height), revolved about Z: a
cylinder r 20 x 15 plus a cone frustum from r 20 to r 16 over 5 mm:
pi 400 x 15 + pi x 5 / 3 (400 + 320 + 256) = 23959.9 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Knob"}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "geometry": [
    {"polyline": [[0, 0], [20, 0], [20, 15], [16, 20], [0, 20]]}]}},
  {"tool": "revolve", "args": {"profile": "Sketch1", "axis": "Z"},
   "expect": {"contains": ["Its id is 'Revolve1'", "23959.9 mm3", "40 x 40 x 20 mm"]}}
]
```

## 2. One groove, then 18 of them

A groove is a 3 mm circle centred on the rim (x = 20), cut upward 15 mm from the bottom. The
sketch is on XY at z = 0 (the knob's underside); an XY extrude goes up (+Z), into the knob,
so no `flip` here. Then [circular_pattern](sciforge://docs/reference/circular_pattern.md) repeats the
cut around Z.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [20, 0, 1.5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 15, "operation": "cut"},
   "expect": {"contains": ["Its id is 'Extrude1'"], "not_contains": ["Warning"]}},
  {"tool": "circular_pattern", "args": {"features": ["Extrude1"], "axis": "Z", "quantity": 18},
   "expect": {"contains": ["Its id is 'Pattern1'"]}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder", "radius": 1.5}},
   "expect": {"json": {"count": 18}}}
]
```

## 3. The bore and the top edge

The bore is a cut too (6 mm, 12 deep, upward from the bottom sketch). A `hole` from the same
sketch would do as well: a hole drills into the part, so from a sketch under the part it
goes up by itself. The top edge is the circle of radius 16 at the top.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [0, 0, 3]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch3", "distance": 12, "operation": "cut"},
   "expect": {"contains": ["Its id is 'Extrude2'"], "not_contains": ["Warning"]}},
  {"tool": "fillet", "args": {"edges": {"type": "circle", "radius": 16,
    "at": {"axis": "z", "value": "max"}, "count": 1}, "radius": 1.5},
   "expect": {"contains": ["Its id is 'Fillet1'"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}},
  {"tool": "render", "args": {"view": "top", "width": 400, "height": 400},
   "expect": {"image": [400, 400]}}
]
```

## Variations

- More or fewer grooves: `edit_step` on the pattern: `{"step": "Pattern1", "set":
  {"quantity": 24}}`.
- A pointer line on top: an `extrude` cut from a thin `rect` on a sketch on the top face
  (`create_sketch` with `face`, then `flip: true` to cut into the knob).
- A D-shaped bore: draw the D with `segments` (a line and an arc) instead of the circle.
