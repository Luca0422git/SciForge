# `physical_properties`: Physical properties

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > a body > Properties (INSPECT). Category: Inspect and measure. Read-only. Needs an open design.

## What it does

Physical properties of bodies, as Fusion's Properties: volume (mm3), area (mm2), material and density, mass (g), centre of mass and bounding box (mm), number of faces, edges and solids, and whether the solid is valid. bodies: step ids (default every body).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies (default: all) |

## Answer

A plain sentence, then JSON with: `bodies`. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: volume, area, mass

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}}
]
```

The call:

```json
{"tool": "physical_properties", "args": {}}
```

The answer:

```text
{
 "bodies": [
  {
   "id": "Body",
   "label": "Body1",
   "volume_mm3": 24000.0,
   "area_mm2": 6800.0,
   "material": "Steel (default)",
   "density_kg_m3": 7900.0,
   "mass_g": 189.6,
   "center_of_mass_mm": [
    30.0,
    20.0,
    5.0
   ],
   "bbox_mm": [
    0.0,
    0.0,
    0.0,
    60.0,
    40.0,
    10.0
   ],
   "faces": 6,
   "edges": 12,
   "solids": 1,
   "valid": true
  }
 ]
}
```

## More argument examples

- every body's mass, volume and centre of mass:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
