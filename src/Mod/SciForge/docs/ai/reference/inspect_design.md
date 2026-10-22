# `inspect_design`: Inspect design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER + TIMELINE + Properties (everything at once). Category: Inspect and measure. Read-only. Needs nothing.

## What it does

Read the whole design as numbers, to check work before trusting a picture: every body (valid solid or not, volume mm3, area mm2, bounding box and size mm, centre of mass, number of solids, faces, edges and corners, material and mass, shown or hidden); every timeline step in order (id, name, kind, body, done or rolled back, suppressed, status and the error message when it failed, its main values; detail full adds every option as get_step shows them); user parameters; components and joints; construction geometry; sketches (closed areas, fully constrained); drawings; and what is selected in SciForge (window only). The answer has a snapshot id: diff_design since it shows what changed later. bodies: only these (step ids).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `detail` | `summary` \| `full` |  | `"summary"` |  | full adds every step's definition |
| `bodies` | array of strings |  |  | at least 1 item(s) | only these bodies (default: all) |

## Answer

A plain sentence, then JSON with: `design`, `id`, `file`, `units`, `active_body`, `bodies`, `timeline`, `history_marker`, `parameters`, `sketches`, `selection`, `summary`, `snapshot`. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: everything at once

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [30, 20, 4]}]}},
  {"tool": "hole", "args": {"sketch": "Sketch2", "diameter": 8, "through_all": true}}
]
```

The call:

```json
{"tool": "inspect_design", "args": {}}
```

The answer:

```text
Example: 1 body, 4 steps. Snapshot S1.
{
 "design": "Example",
 "id": "Example",
 "file": null,
 "units": "mm, mm2, mm3, g, degrees",
 "active_body": "Body",
 "bodies": [
  {
   "id": "Body",
   "label": "Body1",
   "shown": true,
   "solids": 1,
   "shells": 1,
   "faces": 7,
   "edges": 15,
   "vertices": 10,
   "solid": true,
   "volume_mm3": 23497.345175,
   "area_mm2": 6950.796447,
   "bbox_mm": {"min": [0.0, 0.0, 0.0], "max": [60.0, 40.0, 10.0], "size": [60.0, 40.0, 10.0]},
   "valid": true,
   "center_of_mass_mm": [30.0, 20.0, 5.0],
   "closed": true,
   "tip": "Hole1",
   "material": "Steel (default)",
   "mass_g": 185.629027
  }
 ],
 "timeline": [
  {
   "index": 0,
   "id": "Sketch1",
   "name": "Sketch 1",
   "kind": "sketch",
   "type": "Sketcher::SketchObject",
   "body": "Body",
   "state": "done",
   "status": "ok",
   "values": {"base.width": 60.0, "base.height": 40.0, "base.x": 0.0, "base.y": 0.0}
  },
  {
   "index": 1,
   "id": "Extrude1",
   "name": "Extrude 1",
   "kind": "extrude",
   "type": "PartDesign::Pad",
   "body": "Body",
   "state": "done",
   "status": "ok",
   "values": {"Distance": 10.0, "Taper": 0.0}
  },
  {
   "index": 2,
   "id": "Sketch2",
   "name": "Sketch 2",
   "kind": "sketch",
   "type": "Sketcher::SketchObject",
   "body": "Body",
   "state": "done",
   "status": "ok",
   "values": {"g0.diameter": 8.0, "g0.x": 30.0, "g0.y": 20.0}
  },
  {
   "index": 3,
   "id": "Hole1",
   "name": "Hole 1",
   "kind": "hole",
   "type": "PartDesign::Hole",
   "body": "Body",
... (22 more lines)
```

## More argument examples

- everything about the open design, with a snapshot id:
  `{}`
- also every step's options:
  `{"detail": "full"}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- Recipe: [curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md)
- Recipe: [threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
