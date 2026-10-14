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
| `blend_insert` | `id`, `kind` (fillet/chamfer), the options above, `edges` / `faces` | Fillet / Chamfer made with the timeline marker rolled back (after a `roll`): later blends keep their edges (`golden/blend_ops.py`) |
| `blend_edit` | `target`, `add_edges` / `add_faces` (selectors on the shape it is applied to), `set` {options} | double-click a Fillet / Chamfer in the timeline, pick more edges, change sizes; later blends keep their edges |
| `shell` | `id`, `faces` (faces to remove), `thickness`, `direction` (inside/outside) | Shell |
| `hole` | `id`, `sketch` (hole centres = its circles' centres), `diameter`, `depth` or `through_all`, `counterbore {diameter, depth}` or `countersink {diameter, angle}` | Hole |
| `emboss` | `id`, `sketch` (every closed area of it is a profile), `faces` (selector), `depth`, `effect` (emboss/deboss), `h`, `v`, `angle`, `tangent_chain` | Emboss dialog (`sciforge/emboss.py`, details in `golden/emboss_ops.py`) |
| `pattern_rect` | `id`, `features`, `direction`, `count`, `spacing`, optional second direction `direction2`, `count2`, `spacing2` | Rectangular Pattern |
| `pattern_circ` | `id`, `features`, `axis`, `count`, `angle` | Circular Pattern |
| `mirror` | `id`, `features`, `plane` | Mirror |
| `rectangular_pattern` | `id`, one of `features` (step ids) / `faces` (selector) / `body: true`, `direction` (X/Y/Z or `{"edge": sel}` / `{"face": sel}`), `quantity`, `distance`, `distribution` (extent/spacing), `direction_type` (one/symmetric), `direction2`, `quantity2`, `distance2`, `direction_type2`, `expressions` | Rectangular Pattern dialog (`golden/pattern_ops.py`, `sciforge/pattern.py`: the dialog's code). Bodies make new bodies; the model is then measured over every body |
| `circular_pattern` | `id`, what (as above), `axis` (X/Y/Z, edge or round face), `quantity`, `type` (full/angle/symmetric), `angle` | Circular Pattern dialog |
| `path_pattern` | `id`, what, `path` `{"sketch": id}` or `{"sketch": id, "edge": n}`, `quantity`, `distance`, `distribution`, `direction_type`, `orientation` (identical/path) | Pattern on Path dialog |
| `fusion_mirror` | `id`, what, `plane` (XY/XZ/YZ or `{"face": sel}`), `operation` (join/new_body, bodies) | Mirror dialog |
| `pattern_edit` | `target`, `set` {dialog field: value} | double-click a pattern in the timeline and change its fields |
| `edit` | `target`, `set` {option: value} or `constraint` + `value` | double-click a timeline item and change it |
| `check` | `expect` | measure the part at this point (before an edit, for example) |
| `sketch_polygon` | `sketch`, `center`, `point` (middle of an edge, or a corner), `sides`, `circumscribed`, `diameter`, `name` | Circumscribed / Inscribed Polygon in a sketch (golden/sketch_ops.py) |
| `sketch_trim` | `sketch`, `points` (one Trim click each) | Trim (T) in a sketch |
| `extrude` + `bodies` | `"auto"` (every body in the extrusion's way) or a list of step ids (their bodies) | the Extrude dialog's "Bodies to Cut / Join / Intersect" row (`golden/extrude_bodies_ops.py`) |
| `use_body` | `step` | the next sketches go into that step's body |
| `expect_bodies` | `bodies` {step id: {`volume`, `solids`}}, `used_up` [step ids], `followers` {step id: n}, `steps` {step id: times listed in the timeline} | check several bodies at this point |
| `reopen_check` | `bodies` (as above) | save, open the file as a second design, check the bodies there |
| `expect_move_refused` | `target`, `before` or `after`, `reason` | dragging a step before / after another in the timeline is refused (a multi-body extrude moves with its hidden steps; only a move before a body it changes exists is refused) |
| `history_off` / `history_on` | (none) | the design's menu: Do Not Capture Design History (every body one frozen step) / Capture Design History (`golden/direct_ops.py`, `sciforge/direct.py`) |
| `replace_face` | `id`, `faces` (selector), `of` (step: its body; default the current one), `tangent_chain`, `target` (a pick: XY/XZ/YZ, `{"face": sel, "of": id}`) | Replace Face (measured: that body) |
| `split_face` | `id`, `faces`, `of`, `tool` (a pick: plane, face, `{"body": id}`), `extend`, `split_type` (surface/vector/closest), `direction` (a pick: X/Y/Z, a face, an edge) | Split Face |
| `silhouette_split` | `id`, `body`, `direction` (a pick), `operation` (faces/body/shelled) | Silhouette Split (measured: the body and the new ones) |
| `align_bodies` | `id`, `from`, `to` (picks: `{"face" / "edge" / "vertex": sel, "of": id}`, planes, axes), `flip`, `turns` (0..3 Angle clicks) | Align with Objects: Bodies (measured: the moved body) |
| `modify_edit` | `target` (one of the four above), `set` {option: value or pick} | double-click it in the timeline and change it |
| `remove_bodies` | `steps` | Remove (a timeline step); measured from then on: the bodies still in the design |

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
