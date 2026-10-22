# `set_view`: Set view

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: NAVIGATION BAR and VIEWCUBE (Home, Fit, Orbit, Look At). Category: View. Read-only. Needs an open design, the SciForge window.

## What it does

Turn the 3D view: orientation iso | home | front | back | top | bottom | left | right, fit (zoom so everything shows, default true), projection perspective | orthographic, or camera (a camera string get_view returned), or look_at: a face selector (the view looks straight at that face, Fusion's Look At).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `orientation` | `iso` \| `home` \| `front` \| `back` \| `top` \| `bottom` \| `left` \| `right` |  |  |  |  |
| `fit` | boolean |  | `true` |  |  |
| `projection` | `perspective` \| `orthographic` |  |  |  |  |
| `camera` | string |  |  |  | a camera description from get_view |
| `look_at` | object |  |  |  | look straight at this face (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Without the SciForge window: `This needs the SciForge window, and SciForge is running without one (headless / command line).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: look from the top (needs the SciForge window)

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
{"tool": "set_view", "args": {"orientation": "top"}}
```

The answer:

```text
View: top view, fitted.
```

## More argument examples

- look from the top, fitted:
  `{"orientation": "top"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
