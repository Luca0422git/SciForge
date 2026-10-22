# `center_of_mass`: Center of mass

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSPECT > Center of Mass. Category: Inspect and measure. Read-only. Needs a solid body.

## What it does

The centre of mass of bodies together (Fusion's Center of Mass), weighted by their materials. bodies: step ids (default every body).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` | array of strings |  |  | at least 1 item(s) | the bodies (default: all) |

## Answer

A plain sentence, then JSON with: `center_of_mass_mm`, `volume_mm3`, `bodies`, `weighted_by_material`. The example below shows a real one.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the centre of mass

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
{"tool": "center_of_mass", "args": {}}
```

The answer:

```text
Centre of mass at (30, 20, 5) mm.
{
 "center_of_mass_mm": [
  30.0,
  20.0,
  5.0
 ],
 "volume_mm3": 23497.345175,
 "bodies": [
  "Body"
 ],
 "weighted_by_material": true
}
```

## More argument examples

- where the whole design balances:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
