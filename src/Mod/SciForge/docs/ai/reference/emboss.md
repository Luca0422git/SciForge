# `emboss`: Emboss

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > CREATE > Emboss. Category: Create (SOLID). Changes the design (one undo step). Its undo step is named like "AI: Emboss". Needs a solid body.
It builds the design step(s) `emboss` (the golden models' step language).

## What it does

Emboss (raise) or deboss (sink) a sketch's areas onto faces of the part, wrapping them onto curved faces (Fusion's Emboss). Every closed area of the sketch is a profile (a sketch_text works too). faces: the faces to wrap onto; depth (mm; negative swaps the effect); effect emboss | deboss; h / v (mm): horizontal / vertical offset along the face; angle (degrees): rotation; tangent_chain (default true).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `sketch` (required) | string |  |  |  | the sketch (or text) with the areas |
| `faces` (required) | object |  |  |  | the faces to wrap onto (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `depth` | number | mm | `1` |  | mm |
| `effect` | `emboss` \| `deboss` |  | `"emboss"` |  |  |
| `h` | number | mm | `0` |  | horizontal offset (mm) |
| `v` | number | mm | `0` |  | vertical offset (mm) |
| `angle` | number | deg | `0` |  | rotation (degrees) |
| `tangent_chain` | boolean |  | `true` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: sketch is missing; faces is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: raise a small rectangle 0.5 mm on the round face

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "primitive", "args": {"kind": "cylinder", "plane": "XY", "diameter": 10, "height": 30}},
  {"tool": "create_sketch", "args": {"plane": "XZ", "offset": -5, "geometry": [{"center_rect": [0, 15, 6, 4]}]}}
]
```

The call:

```json
{"tool": "emboss", "args": {"sketch": "Sketch1", "faces": {"type": "cylinder", "count": 1}, "depth": 0.5}}
```

The answer:

```text
Done: AI: Emboss. Its id is 'Emboss1'. Bodies now: Body1: 2368.79 mm3, 10 x 10.5 x 30 mm.
```

## More argument examples

- raise Sketch3's text 0.5 mm on a round face:
  `{"sketch": "Sketch3", "faces": {"type": "cylinder", "count": 1}, "depth": 0.5}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `emboss_cylinder_deboss`, `emboss_cylinder_rect`, `emboss_flat_deboss`, `emboss_flat_rect`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
