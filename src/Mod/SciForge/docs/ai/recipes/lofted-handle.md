# Recipe: lofted handle

Tags: handle, grip, loft, ellipse, profiles, extrude-cut, ergonomic

A tool handle 80 mm long that is oval at both ends and round and thinner in the middle,
made by lofting through three profiles, with a 6 mm hole for the tool's rod. Every call was
run by SciForge's tests; `expect` is what the answer must contain.

## 1. Three profiles on parallel planes

Profiles on XY with `offset` stack along Z. `ellipse` is `[cx, cy, major, minor]` with the
major radius along sketch x.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Handle"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"ellipse": [0, 0, 12, 8]}]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 40, "geometry": [
    {"circle": [0, 0, 7]}]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 80, "geometry": [
    {"ellipse": [0, 0, 10, 6]}]}}
]
```

## 2. The loft

[loft](sciforge://docs/reference/loft.md) goes through the profiles in the order given (Fusion's Loft).
A loft through three or more profiles is a smooth surface through them; here it stays
within the largest profile (24 x 16 mm), but with very different profiles it can bulge
between them: check the bounding box, and add profiles or guide it with `rails` /
`centerline` to control the shape.

```json sciforge-calls
[
  {"tool": "loft", "args": {"profiles": [{"profile": "Sketch1"}, {"profile": "Sketch2"},
    {"profile": "Sketch3"}]},
   "expect": {"contains": ["Its id is 'Loft1'"]}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.solids": 1, "bodies.0.valid": true,
     "bodies.0.bbox_mm.size.2": [80, 0.001], "bodies.0.bbox_mm.size.0": [24, 0.001],
     "bodies.0.bbox_mm.size.1": [16, 0.001]}}}
]
```

## 3. The rod hole

A 6 mm hole 30 mm deep, cut upward from the bottom end (the sketch at z = 0 extrudes +Z into
the handle). It removes exactly pi x 3^2 x 30 = 848.23 mm3, which `diff_design` confirms.

```json sciforge-calls
[
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"circle": [0, 0, 3]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch4", "distance": 30, "operation": "cut"},
   "expect": {"contains": ["Its id is 'Extrude1'"], "not_contains": ["Warning"]}},
  {"tool": "diff_design", "args": {"since": "last_change"},
   "expect": {"json": {"bodies.changed.0.volume_mm3.change": [-848.23, 0.01]}}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

## Variations

- A bent handle: a `sweep` of one profile along a curved path (`create_curve_sketch` with an
  `arc`), or a loft with `centerline` (a curve the loft follows).
- Smoother ends: `start_condition` / `end_condition` `"direction"` with an angle.
- Finger grooves: more profiles (smaller circles) at the finger positions.
