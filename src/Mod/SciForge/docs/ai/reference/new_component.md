# `new_component`: New component

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: ASSEMBLE > New Component. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: New component Lid". Needs nothing.

## What it does

Make a new, empty component (Fusion's New Component) with its own body, inside parent (a component id) or at the top of the design; it becomes the active component, so the next sketches and features go into it. label names it.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `label` | string |  |  |  | its name |
| `parent` | string |  |  |  | the component it goes into |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: a component

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}}
]
```

The call:

```json
{"tool": "new_component", "args": {"label": "Lid"}}
```

The answer:

```text
Done: new component 'Lid' (id 'Component') with the body 'Body001'; it is the active component: the next sketches go into it.
```

## More argument examples

- a component called Lid, active:
  `{"label": "Lid"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
