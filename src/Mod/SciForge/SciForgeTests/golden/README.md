# Golden models

Reference parts that measure SciForge's progress toward Fusion parity (outline section 2.3).
Each model is one JSON file in `models/`: the steps a Fusion user would take, plus the
measurements the finished part must have. The runner rebuilds every model in real FreeCAD and
compares.

## Running

```
tools/sciforge/get_freecad.sh                 # once: downloads stock FreeCAD 1.1.4
tools/sciforge/run_tests.sh --only golden     # report: .sciforge-cache/test-output/golden-report.md
SCIFORGE_GOLDEN_FILTER=fillet tools/sciforge/run_tests.sh --only golden   # just some models
```

In a SciForge build: `FreeCADCmd -c "from SciForgeTests.golden import runner; runner.main()"`.

## Results

| Result | Meaning |
|---|---|
| PASS | every expected measurement matched |
| FAIL | built, but a measurement is off (the report says which, by how much) |
| ERROR | a step could not be built (the report says which step and why) |
| xfail | a documented known gap (`"xfail"`) or a stock-FreeCAD bug SciForge fixes (`"upstream_bug"`, only on stock FreeCAD) |
| XPASS | a known gap now passes: remove its `xfail` |

## Where the expected numbers come from

Every model must say so in `expect.source`, and explain the numbers in `expect.note`:

- `analytic`: worked out by hand from geometry (the formula is in the note). Preferred.
- `fusion`: measured in Autodesk Fusion by the owner (volume, area, bounding box, face count).
- `baseline-freecad-1.1.4`: what stock FreeCAD produced. Only for shapes too complex to work out
  by hand, and only until a Fusion measurement replaces it. It proves "did not get worse", not "is right".

Never copy the numbers FreeCAD prints into an `analytic` model. That would test FreeCAD against
itself.

## File format

```json
{
  "id": "box_basic",                       // must equal the file name
  "title": "Rectangle 40x20 extruded 10",
  "tags": ["extrude", "basic"],
  "steps": [ ... ],
  "expect": {"volume": 8000, "area": 2800, "faces": 6, "edges": 12, "solids": 1,
             "bbox": [0, 0, 0, 40, 20, 10], "source": "analytic", "note": "V = 40*20*10 ..."},
  "xfail": "optional: why this is a known gap",
  "upstream_bug": "optional: stock FreeCAD bug fixed in SciForge (core-patches.md #N)"
}
```

Tolerances: `rel_tol` (default 1e-6, relative, for volume/area) and `abs_tol` (default 1e-4 mm,
bounding box). Face, edge and solid counts must match exactly. Every result must be a valid solid.

### Steps

| op | keys | Fusion equivalent |
|---|---|---|
| `sketch` | `id`, `plane` (XY/XZ/YZ), `offset`, `geometry` | Create Sketch (on an offset plane) |
| `extrude` | `id`, `profile`, `distance`, `operation` (join/cut/new_body), `direction` (one_side/symmetric/two_sides), `distance2`, `extent` (distance/through_all), `taper`, `flip` | Extrude |
| `revolve` | `id`, `profile`, `axis` (X/Y/Z/sketch_h/sketch_v), `angle`, `operation` | Revolve |
| `sf_revolve` | `id`, `profile` (+ `regions`) or `face`, `axis` (X/Y/Z, `{"sketch", "at"}`, `{"sketch", "construction"}`, `{"sketch", "axis": "H"/"V"}`, `{"edge": selector}`), `type` (angle/full), `direction` (one_side/two_sides/symmetric), `angle`, `angle2`, `operation` (auto = the dialog's own choice) | Revolve dialog (`sciforge/revolve.py`, details in `golden/revolve_ops.py`) |
| `sf_revolve_edit` | `target`, `set` {revolve options} | double-click a revolve in the timeline and change it |
| `fillet` | `id`, `edges` (selector), `radius` | Fillet |
| `chamfer` | `id`, `edges`, `distance`, `distance2` or `angle` | Chamfer |
| `blend_fillet` | `id`, `radius`, and `edges` / `faces` (every sharp edge around them) / `features` (step ids: the edges each made) | Fillet dialog (`sciforge/blend.py`, the F command's code) |
| `blend_chamfer` | `id`, `distance`, `chamfer_type` (equal/two/angle), `distance2`, `angle`, `flip`, and `edges` / `faces` / `features` | Chamfer dialog |
| `shell` | `id`, `faces` (faces to remove), `thickness`, `direction` (inside/outside) | Shell |
| `hole` | `id`, `sketch` (hole centres = its circles' centres), `diameter`, `depth` or `through_all`, `counterbore {diameter, depth}` or `countersink {diameter, angle}` | Hole |
| `pattern_rect` | `id`, `features`, `direction`, `count`, `spacing`, optional second direction `direction2`, `count2`, `spacing2` | Rectangular Pattern |
| `pattern_circ` | `id`, `features`, `axis`, `count`, `angle` | Circular Pattern |
| `mirror` | `id`, `features`, `plane` | Mirror |
| `edit` | `target`, `set` {option: value} or `constraint` + `value` | double-click a timeline item and change it |
| `check` | `expect` | measure the part at this point (before an edit, for example) |
| `sketch_polygon` | `sketch`, `center`, `point` (middle of an edge, or a corner), `sides`, `circumscribed`, `diameter`, `name` | Circumscribed / Inscribed Polygon in a sketch (golden/sketch_ops.py) |
| `sketch_trim` | `sketch`, `points` (one Trim click each) | Trim (T) in a sketch |

Conventions:
- Sketch planes: the sketch normal is +Z for XY, **-Y for XZ** and +X for YZ (FreeCAD's origin).
  Sketch (x, y) map to (X, Y), (X, Z) and (Y, Z).
- Extrude `distance` goes along the sketch normal; `"flip": true` reverses it, for cuts too.
  A cut from a sketch on top of a part therefore needs `"flip": true`.
- Every feature is created with Refine on, because Fusion never leaves split seam faces.

### Sketch geometry

`rect [x0, y0, x1, y1]`, `center_rect [cx, cy, w, h]`, `circle [cx, cy, r]`,
`polyline [[x, y], ...]` (closed), `polygon {center, radius, sides, rotation}`,
`slot [x1, y1, x2, y2, width]`.

Give geometry a `name` to get Fusion-style dimensions you can `edit` later:
`<name>.width`, `<name>.height`, `<name>.x`, `<name>.y` for rectangles, and `<name>.diameter`,
`<name>.x`, `<name>.y` for circles.

### Selectors (which edges or faces a user would click)

Never use names like `Edge7`. Describe the geometry instead (full list in `selectors.py`):

```json
{"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}          // the 4 top edges
{"normal": [0, 0, 1], "count": 1}                                           // the top face
{"type": "line", "parallel": [0, 1, 0],
 "at": [{"axis": "x", "value": 5}, {"axis": "z", "value": 5}], "count": 1}  // one specific edge
```

Always give `count`: if a change makes the selector pick different geometry, the model fails
loudly instead of quietly testing something else.
