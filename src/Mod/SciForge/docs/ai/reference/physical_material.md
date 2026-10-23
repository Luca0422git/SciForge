# `physical_material`: Physical material

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Physical Material. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Physical material aluminium". Needs an open design.
It builds the design step(s) `body_material` (the golden models' step language).

## What it does

Give a body its physical material (Fusion's Physical Material): density for mass and the material's look. body: a step of it (default: the current body). material: one of SciForge's library (list_materials lists them with densities), or a user material (user:<name>).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `body` | string |  |  |  | a step of the body |
| `material` (required) | string |  |  |  | library key, e.g. aluminium, abs, steel |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: material is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: make the plate aluminium

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
{"tool": "physical_material", "args": {"body": "Extrude1", "material": "aluminium"}}
```

The answer:

```text
Done: Body1 is Aluminium, 64.8 g.
```

## More argument examples

- make the part aluminium 6061:
  `{"body": "Extrude1", "material": "aluminium_6061"}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `export_report_design`, `inspect_com_materials`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
