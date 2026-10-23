# `joint`: Joint

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: ASSEMBLE > Joint (J). Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Joint (revolute)". Needs an open design.

## What it does

Fusion's Joint: the first component moves so that its snap point meets the second's. type rigid | revolute | slider | cylindrical | pinslot | planar | ball; first / second: {component, face | edge | vertex, snap, point}: the element is found on that component with a selector, snap picks which of its snap points (centre of a circle or face, vertex, midpoint...). offset x / y / z (mm), angle (degrees), flip; rotate / slide: the motion axis x | y | z. Answers where the component went and whether the joint holds.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `type` | `rigid` \| `revolute` \| `slider` \| `cylindrical` \| `pinslot` \| `planar` \| `ball` |  | `"rigid"` |  |  |
| `first` (required) | object |  |  |  | one side of a joint: a component and an element of it with a snap point |
| `first.component` (required) | string |  |  |  | the component or body this side is on (a step in it works) |
| `first.face` | object |  |  |  | the face clicked (on that component) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `first.edge` | object |  |  |  | the edge clicked (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `first.vertex` | array of 3 numbers |  |  |  | the corner clicked |
| `first.snap` | `centre` \| `vertex` \| `midpoint` \| `circle` \| `point` \| `origin` |  |  |  | which snap point of the element (default: the nearest to point, else its centre) |
| `first.point` | array of 3 numbers | mm |  |  | where on the element (design coordinates) |
| `second` (required) | object |  |  |  | one side of a joint: a component and an element of it with a snap point |
| `second.component` (required) | string |  |  |  | the component or body this side is on (a step in it works) |
| `second.face` | object |  |  |  | the face clicked (on that component) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `second.edge` | object |  |  |  | the edge clicked (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `second.vertex` | array of 3 numbers |  |  |  | the corner clicked |
| `second.snap` | `centre` \| `vertex` \| `midpoint` \| `circle` \| `point` \| `origin` |  |  |  | which snap point of the element (default: the nearest to point, else its centre) |
| `second.point` | array of 3 numbers | mm |  |  | where on the element (design coordinates) |
| `offset` | array of 3 numbers | mm |  |  | [x, y, z] offset of the joint origin (mm) |
| `angle` | number | deg | `0` |  | (degrees) |
| `flip` | boolean |  | `false` |  |  |
| `rotate` | `x` \| `y` \| `z` |  |  |  | the rotation axis |
| `slide` | `x` \| `y` \| `z` |  |  |  | the slide axis |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: first is missing; second is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the wheel sits on the base and turns about the joint's axis

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "new_component", "args": {"label": "Base"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [-30, -30, 30, 30]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "new_component", "args": {"label": "Wheel"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 20, "geometry": [{"circle": [0, 0, 15]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "joint", "args": {"type": "revolute", "first": {"component": "Wheel", "face": {"normal": [0, 0, -1], "count": 1}, "snap": "centre"}, "second": {"component": "Base", "face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "snap": "centre"}}}
```

The answer:

```text
Done: revolute joint between Wheel and Base. Its id is 'Joint'. Moved: Wheel (now at [3.19189e-15, 7.4607e-16, -10]). Bodies now: Body001: 36000 mm3, 60 x 60 x 10 mm; Body002: 3534.29 mm3, 30 x 30 x 5 mm.
```

## More argument examples

- the wheel turns on the axle:
  `{"type": "revolute", "first": {"component": "Wheel", "face": {"type": "cylinder", "count": 1}, "snap": "circle"}, "second": {"component": "Axle", "face": {"type": "cylinder", "count": 1}, "snap": "circle"}}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
