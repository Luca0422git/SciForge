# Recipe: curved panel from a surface patch

Tags: surface, patch, thicken, freeform, panel, boundary, curves

A gently domed 40 x 30 mm panel, 2 mm thick, like a cover or a hood: four arcs make a
closed boundary in 3D, a Patch surface fills it (Fusion's SURFACE > CREATE > Patch) and
Thicken turns the surface into a solid. Every call was run by SciForge's tests; `expect` is
what the answer must contain.

## 1. Four boundary curves

The two long edges are arcs on XZ planes (sketch x is X, sketch y is Z), one at y = 0 and one
at y = 30: an XZ sketch's normal is -Y, so `offset: -30` puts it at y = +30. The short edges
are arcs on YZ planes (sketch x is Y, sketch y is Z) at x = 0 and x = 40. Each arc runs from
45 to 135 degrees around a centre below the panel, with the radius chosen so that its ends
land exactly on the corners (20 sqrt 2 = 28.284271247461902 and 15 sqrt 2 = 21.213203435596427): a patch needs
a boundary whose curves meet end to end.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Panel"}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "curves": [
    {"arc": [20, -20, 28.284271247461902, 45, 135]}]}},
  {"tool": "create_curve_sketch", "args": {"plane": "XZ", "offset": -30, "curves": [
    {"arc": [20, -20, 28.284271247461902, 45, 135]}]}},
  {"tool": "create_curve_sketch", "args": {"plane": "YZ", "curves": [
    {"arc": [15, -15, 21.213203435596427, 45, 135]}]}},
  {"tool": "create_curve_sketch", "args": {"plane": "YZ", "offset": 40, "curves": [
    {"arc": [15, -15, 21.213203435596427, 45, 135]}]},
   "expect": {"contains": ["Its id is 'Sketch4'"]}}
]
```

## 2. Patch, then thicken

[surface](sciforge://docs/reference/surface.md) with `kind: "patch"` fills the boundary given in
`refs` (each `{"sketch": id}` adds all its curves). A surface body has an area but no
volume. The patch goes into a body of its own (Body2 here) and the thicken makes another
(Body3), as in Fusion; the design's first body stays empty. `kind: "thicken"` with
`refs: [{"step": "Surface1"}]` (the patch's id) makes a solid 2 mm thick, grown outward from
the surface (so the solid is a little larger than 40 x 30).

```json sciforge-calls
[
  {"tool": "surface", "args": {"kind": "patch", "refs": [{"sketch": "Sketch1"},
    {"sketch": "Sketch2"}, {"sketch": "Sketch3"}, {"sketch": "Sketch4"}]},
   "expect": {"contains": ["Its id is 'Surface1'"]}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.1.solid": false, "bodies.1.faces": 1,
     "bodies.1.volume_mm3": 0.0}}},
  {"tool": "surface", "args": {"kind": "thicken", "refs": [{"step": "Surface1"}],
    "options": {"thickness": 2}},
   "expect": {"contains": ["Its id is 'Surface2'"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true, "warnings.#": 2},
   "contains": ["is empty", "a surface body"]}}
]
```

`check_design` is OK with two warnings that are expected here: the empty first body and the
surface body (keep it to edit the patch later, or hide it with `show_hide`).

## 3. Check the shape

The panel's corners stay at z = 0. Its middle rises well above the arcs' tops (8.3 mm for
the long arcs, 6.2 mm for the short ones), to about 14.8 mm: the patch is a smooth surface
through the boundary, not a part of a sphere, and bulges more than the arcs alone suggest.
For a flatter panel use flatter arcs (a bigger radius over a shorter angle).

```json sciforge-calls
[
  {"tool": "inspect_design", "args": {"bodies": ["Surface2"]},
   "expect": {"json": {"bodies.0.solid": true, "bodies.0.valid": true}}},
  {"tool": "render", "args": {"view": "iso", "width": 480, "height": 360},
   "expect": {"image": [480, 360]}}
]
```

## Variations

- Smooth to neighbouring faces: `options: {"continuity": "tangent"}` when the boundary is
  edges of a solid (`{"step": id, "edges": selector}` refs).
- A hole in the panel: `kind: "trim"` with a closed sketch curve and `remove` (a point on
  the piece to take away), before thickening.
- Other surfaces: `extrude`, `revolve`, `sweep`, `loft` and `ruled` kinds; `stitch` closes a set
  of surfaces into a solid, `boundary_fill` fills the cell between surfaces (see the golden
  models `surface_boundary_fill_cone` and `surface_thicken_corner` with examples_search).
