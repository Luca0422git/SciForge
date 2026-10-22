# `list_materials`: List materials

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Physical Material / Appearance (libraries). Category: Modify. Read-only. Needs nothing.

## What it does

List SciForge's physical materials (key, name, density kg/m3, group) and appearances (key, name, colour), for physical_material and appearance.

## Arguments

No arguments.

## Answer

A plain sentence, then JSON with: `materials`, `appearances`. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: materials and appearances

Starting from SciForge with no design open.

The call:

```json
{"tool": "list_materials", "args": {}}
```

The answer:

```text
{
 "materials": [
  {
   "key": "steel",
   "name": "Steel",
   "group": "Metal",
   "density_kg_m3": 7900.0
  },
  {
   "key": "stainless",
   "name": "Stainless Steel",
   "group": "Metal",
   "density_kg_m3": 7800.0
  },
  {
   "key": "iron",
   "name": "Iron",
   "group": "Metal",
   "density_kg_m3": 7874.0
  },
  {
   "key": "aluminium",
   "name": "Aluminium",
   "group": "Metal",
   "density_kg_m3": 2700.0
  },
  {
   "key": "aluminium_6061",
   "name": "Aluminium 6061",
   "group": "Metal",
   "density_kg_m3": 2700.0
  },
  {
   "key": "copper",
   "name": "Copper",
   "group": "Metal",
   "density_kg_m3": 8960.0
  },
  {
   "key": "titanium",
   "name": "Titanium",
   "group": "Metal",
   "density_kg_m3": 4430.0
  },
  {
   "key": "abs",
   "name": "ABS Plastic",
   "group": "Plastic",
   "density_kg_m3": 1060.0
  },
  {
   "key": "pla",
   "name": "PLA",
   "group": "Plastic",
   "density_kg_m3": 1240.0
  },
  {
   "key": "pet",
   "name": "PET / PETG",
   "group": "Plastic",
   "density_kg_m3": 1380.0
  },
  {
   "key": "nylon",
   "name": "Nylon 6",
   "group": "Plastic",
   "density_kg_m3": 1150.0
  },
  {
   "key": "polycarbonate",
... (330 more lines)
```

## More argument examples

- the material and appearance libraries:
  `{}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
