# `new_body`: New body

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > Bodies > New Body. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: New body". Needs nothing.

## What it does

Make a new, empty body in the active component and make it the active body: the next sketch and extrude go into it. label names it.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `label` | string |  |  |  | its name |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a new body

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
{"tool": "new_body", "args": {"label": "Insert"}}
```

The answer:

```text
Done: new body 'Insert' (id 'Body001'), the active body now.
```

## More argument examples

- a new body called Insert:
  `{"label": "Insert"}`

## See also

- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
