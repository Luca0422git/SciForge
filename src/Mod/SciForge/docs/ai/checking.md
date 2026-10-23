# Checking your work

A model that checks each step with numbers builds far better parts than one that trusts a
picture. SciForge gives you exact numbers for everything; use them after every change and
before you say a part is done. Every block below is run by SciForge's tests.

## The tools

| Tool | Answers | Use it |
|---|---|---|
| the change's own answer | `Bodies now: Body1: 23497.3 mm3, 60 x 40 x 10 mm`, broken steps, "no solid changed" | after every change: does the volume and size move the way you meant? |
| [inspect_design](sciforge://docs/reference/inspect_design.md) | every body (valid, closed, volume, area, bounding box, centre of mass, counts, material, mass), every step (state, status, error, values), parameters, sketches, components, joints, the selection; a snapshot id | at the start, and before a series of changes (its snapshot id is a checkpoint) |
| [diff_design](sciforge://docs/reference/diff_design.md) | what changed since a snapshot id, since `last_change` or since a step: bodies, steps, parameters | after a change, to confirm exactly what it did and nothing else |
| [query_geometry](sciforge://docs/reference/query_geometry.md) | the faces / edges / corners a selector picks, with facts and a `ref` each | before a fillet, chamfer, shell, draft or sketch on a face |
| [check_design](sciforge://docs/reference/check_design.md) | ok, problems (invalid or open solids, bodies in several pieces, failed steps, broken sketches, overlapping bodies), warnings | after a series of changes, and at the end |
| [measure](sciforge://docs/reference/measure.md) | distance and angle between two picks with X / Y / Z parts and the nearest points; the size of one pick | wall thickness, hole positions, clearances |
| [physical_properties](sciforge://docs/reference/physical_properties.md) | volume, area, mass, density, centre of mass, bounding box per body | weight and balance |
| [interference](sciforge://docs/reference/interference.md) | which bodies overlap and by how much | assemblies, parts that must fit |
| [section_analysis](sciforge://docs/reference/section_analysis.md) | the cut faces through a plane | inside features, wall thickness |
| [render](sciforge://docs/reference/render.md) | a PNG picture (iso, front, top... or a direction), faces / edges highlighted in orange | to look, second: after the numbers agree |

## A checking routine

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Checked"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"snapshot": "S1", "bodies.0.volume_mm3": 24000.0,
     "bodies.0.bbox_mm.size": [60.0, 40.0, 10.0], "summary.failed_steps": []}}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10,
    "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true},
   "expect": {"contains": ["23497.3 mm3"]}},
  {"tool": "diff_design", "args": {"since": "last_change"},
   "expect": {"json": {"bodies.changed.0.volume_mm3.change": [-502.65, 0.01],
     "bodies.changed.0.faces.after": 7, "steps.added.0.id": "Hole1"}}},
  {"tool": "diff_design", "args": {"since": "S1"},
   "expect": {"json": {"steps.added.#": 2}}},
  {"tool": "query_geometry", "args": {"select": {"type": "cylinder"}},
   "expect": {"json": {"count": 1, "elements.0.radius_mm": 4.0,
     "elements.0.axis_point_mm": [30.0, 20.0, 10.0]}}},
  {"tool": "measure", "args": {"a": {"face": {"type": "cylinder", "count": 1}},
    "b": {"face": {"normal": [1, 0, 0], "count": 1}}},
   "expect": {"contains": ["distance 26 mm"]}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true, "problems": []}}},
  {"tool": "render", "args": {"width": 320, "height": 240,
    "highlight": {"faces": {"type": "cylinder"}}}, "expect": {"image": [320, 240]}}
]
```

What the numbers prove: the hole removed pi x 4^2 x 10 = 502.65 mm3 (a through hole of the
right size), the body gained one face (the hole's wall), the hole's axis is at (30, 20), and
the wall between the hole and the right side is 60 - 30 - 4 = 26 mm.

## Refs: pick exactly what you checked

`query_geometry` gives each element a `ref`, a selector that picks only that element. Use it
to fillet exactly the edge you looked at:

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "at": {"axis": "z", "value": "max"}, "count": 4}},
   "expect": {"json": {"elements.0.ref.count": 1}}},
  {"tool": "chamfer", "args": {"edges": {"type": "line", "parallel": [1.0, 0.0, 0.0],
    "at": [{"axis": "y", "value": "min"}, {"axis": "z", "value": "max"}], "count": 1},
    "distance": 1}, "expect": {"contains": ["Its id is 'Chamfer1'"]}},
  {"tool": "diff_design", "args": {"since": "last_change"},
   "expect": {"json": {"bodies.changed.0.volume_mm3.change": [-30, 0.001]}}}
]
```

(The chamfer's selector is the `ref` `query_geometry` answered for the front top edge; a
1 mm chamfer along 60 mm removes 0.5 x 60 = 30 mm3.) A `ref` also names the body it came
from (`"body": "Body001"`): fillet, chamfer and the other changing tools work on the active
body, and refuse a ref of another body, so `activate` that body first.

## Pictures

`render` returns the picture itself (MCP image content). `view` is iso (Fusion's Home: from
the front-right-top), front, back, top, bottom, left, right, or `direction` [x, y, z] (where
the camera looks from); `highlight` marks what a selector picks in orange (`of` a body or a
step). In the SciForge window it uses the 3D view (the person's camera and selection are put
back after, and the selection does not show in the picture);
without the window SciForge's own software renderer draws flat-shaded solids, edges and
sketches (no appearances, no transparency, no text). The answer says how many mm one pixel
is. `screenshot` (window only) is the view as the person sees it.

## Before you say "done"

1. `check_design`: `ok` true, no problems; read the warnings.
2. Compare the numbers with what was asked: overall size (bounding box), volume or mass,
   hole sizes and positions (`query_geometry`, `measure`), wall thickness.
3. `render` iso and one more view (top or front).
4. Tell the person what you built and how you checked it, in their words, including anything
   you were unsure about.
