# `appearance`: Appearance

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Appearance (A). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Appearance". Needs an open design.

## What it does

Fusion's Appearance: colour a body, or some faces of it, without changing its material. body: a step of it (default: the current body); faces: a selector (only these faces); look: a library key (list_materials) or color [r, g, b] (0..1) with shininess (0..1) and transparency (0..1). clear: true removes the body's own appearance.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `body` | string |  |  |  | a step of the body |
| `faces` | object |  |  |  | only these faces (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `look` | string |  |  |  | an appearance key, e.g. plastic_red |
| `color` | array of 3 numbers | 0..1 |  |  | [r, g, b] 0..1 |
| `shininess` | number |  | `0.5` | >= 0, <= 1 |  |
| `transparency` | number |  | `0` | >= 0, <= 1 |  |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give look (a library key) or color ([r, g, b] 0..1), one of them.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: red plastic

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
{"tool": "appearance", "args": {"body": "Extrude1", "look": "plastic_red"}}
```

The answer:

```text
Done: Body1 in Glossy plastic, red.
```

## More argument examples

- the current body in glossy red:
  `{"look": "plastic_red"}`
- just the top face blue:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "color": [0.1, 0.3, 0.8]}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
