# `new_design`: New design

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: File > New Design. Category: Designs and files. Changes the open designs (not an undo step). Needs nothing.

## What it does

Start a new, empty design (with one body) and make it the active one. name: its name.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `name` | string |  | `"Untitled"` |  | the design's name |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a new design

Starting from SciForge with no design open.

The call:

```json
{"tool": "new_design", "args": {"name": "Bracket"}}
```

The answer:

```text
New design 'Bracket' (id 'Bracket') with an empty body 'Body'; it is the active design.
```

## More argument examples

- a new design called Bracket:
  `{"name": "Bracket"}`

## See also

- Recipe: [L bracket with mounting holes](sciforge://docs/recipes/bracket.md)
- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Recipe: [flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md)
- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Recipe: [lofted handle](sciforge://docs/recipes/lofted-handle.md)
- Recipe: [parametric mounting plate](sciforge://docs/recipes/parametric-plate.md)
- Recipe: [revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md)
- Recipe: [stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md)
- Recipe: [sheet-like U bracket (thin extrude with bends)](sciforge://docs/recipes/sheet-like-part.md)
- Recipe: [cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md)
- Recipe: [curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md)
- Recipe: [threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
