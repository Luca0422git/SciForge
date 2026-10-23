# `components_from_bodies`: Components from bodies

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: BROWSER > a body > Create Components from Bodies. Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Components from bodies". Needs an open design.
It builds the design step(s) `components_from_bodies` (the golden models' step language).

## What it does

Put bodies into components of their own (one component per body), so joints can move them. bodies: step ids; label names the component (one body).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `bodies` (required) | array of strings |  |  | at least 1 item(s) | the bodies |
| `label` | string |  |  |  | the new component's name |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without an open design: `No design is open: call new_design or open_design first (or create_sketch, which starts a new design).`
- Called without arguments, the arguments are refused before anything runs: `Not done: bodies is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: the box's body becomes the component Block

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "primitive", "args": {"kind": "box", "plane": "XY", "x": 40, "y": 10, "length": 40, "width": 20, "height": 20, "operation": "new_body"}}
]
```

The call:

```json
{"tool": "components_from_bodies", "args": {"bodies": ["Primitive1"], "label": "Block"}}
```

The answer:

```text
Done: AI: Components from bodies. Its id is 'Component' (shown as 'Block'). Bodies now: Body1: 24000 mm3, 60 x 40 x 10 mm; Body2: 16000 mm3, 40 x 20 x 20 mm.
```

## More argument examples

- Extrude1's body as Base:
  `{"bodies": ["Extrude1"], "label": "Base"}`

## See also

- Recipe: [a pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `comp_move_captured_roll`, `comp_move_rotate_pivot`, `comp_paste_instance_follows`, `comp_paste_new_independent`, `comp_pattern_circular_6`, `comp_pattern_rect_extent`, `export_report_design`, `pattern_bodies_in_moved_component`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
