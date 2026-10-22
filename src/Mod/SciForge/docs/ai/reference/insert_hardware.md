# `insert_hardware`: Insert hardware

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: INSERT > Hardware (McMaster-Carr / fasteners in Fusion). Category: Assemble. Changes the design (one undo step). Its undo step is named like "AI: Hardware iso4762". Needs a solid body.
It builds the design step(s) `sf_hardware` (the golden models' step language).

## What it does

Insert a fastener with the hole it needs: click a flat face of the current body at at ([x, y, z], design coordinates) or a round edge (a hole's rim). standard iso4762 (socket head cap screw), iso7380 (button head), iso10642 (countersunk), iso4032 (hex nut), iso7089 (washer), insert (heat-set insert), magnet; size ("3" for M3, "6x3" for a magnet), length (mm), flip, make_hole (default true), fit close | normal | loose, sink_head (counterbore / countersink for the head), hole_depth all | length, clearance (a magnet's pocket, mm). The part becomes its own component.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `face` | object |  |  |  | the flat face clicked (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `at` | array of 3 numbers | mm |  |  | where on it |
| `edge` | object |  |  |  | instead: a round edge (a hole's rim) (an edge selector: filters type, parallel, radius, on_faces, not_on_faces, at, all, count, any_of; see get_help topic selectors). Give count. |
| `standard` | `iso4762` \| `iso7380` \| `iso10642` \| `iso4032` \| `iso7089` \| `insert` \| `magnet` |  | `"iso4762"` |  |  |
| `size` | string |  |  |  | e.g. 3 (M3) or 6x3 |
| `length` | number | mm |  | > 0 | mm |
| `flip` | boolean |  | `false` |  |  |
| `make_hole` | boolean |  | `true` |  |  |
| `fit` | `close` \| `normal` \| `loose` |  | `"normal"` |  |  |
| `sink_head` | boolean |  |  |  | counterbore / countersink for the head; default true, false for iso7380 (a button head sits on the face) |
| `hole_depth` | `all` \| `length` |  | `"all"` |  |  |
| `clearance` | number | mm |  | >= 0 | mm |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give face + at (a click on a flat face) or edge (a hole's round rim).`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: an M3 x 10 socket head screw with its hole

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
{"tool": "insert_hardware", "args": {"face": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "at": [10, 10, 10], "standard": "iso4762", "size": "3", "length": 10}}
```

The answer:

```text
Done: AI: Hardware iso4762. Its id is 'Hardware'. Bodies now: Body1: 23827.3 mm3, 60 x 40 x 10 mm; Body001: 134.924 mm3, 5.5 x 5.5 x 13 mm.
```

## More argument examples

- an M3 x 10 socket head screw with its hole:
  `{"face": {"normal": [0, 0, 1], "count": 1}, "at": [10, 10, 10], "standard": "iso4762", "size": "3", "length": 10}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `hardware_button_head_m4`, `hardware_countersunk_m4_on_rim`, `hardware_edit_length`, `hardware_insert_m3_hole`, `hardware_magnet_6x3_pocket`, `hardware_nut_top`, `hardware_shcs_m3_counterbore`, `hardware_washer_bottom`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
