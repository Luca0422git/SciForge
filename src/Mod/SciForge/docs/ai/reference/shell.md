# `shell`: Shell

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Shell. Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Shell 2 mm". Needs a solid body.
It builds the design step(s) `shell`, `sf_shell`, `sf_shell_bodies` (the golden models' step language).

## What it does

Hollow the current body out with a wall thickness (SciForge's Shell). faces: the faces to remove (open), a face selector, e.g. the top face {"normal": [0, 0, 1], "count": 1}. direction inside (default: the outside stays where it is) or outside. More of Fusion's dialog: body: true (hollow and closed, no face removed), direction both with inside / outside thicknesses, shell_type sharp | rounded (rounded outer corners), bodies [{"body": step id, "faces": selector}] (one Shell over several bodies). All lengths are in millimetres (mm) and all angles in degrees.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `faces` | object |  |  |  | The faces to remove. (rules: [selectors](sciforge://docs/tools.md#help-selectors)) |
| `thickness` | number | mm |  | > 0 |  |
| `direction` | `inside` \| `outside` \| `both` |  | `"inside"` |  |  |
| `body` | boolean |  |  |  | hollow the whole body, closed (no face removed) |
| `inside` | number | mm |  | > 0 | inside thickness (mm) |
| `outside` | number | mm |  | > 0 | outside thickness (mm) |
| `shell_type` | `sharp` \| `rounded` |  | `"sharp"` |  |  |
| `bodies` | array of objects |  |  | at least 1 item(s) | several bodies in one Shell |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: give faces (the faces to remove) or body: true (hollow, closed); thickness is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.

## Example 1: hollow the plate, open at the top, 2 mm walls

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
{"tool": "shell", "args": {"faces": {"normal": [0, 0, 1], "at": {"axis": "z", "value": "max"}, "count": 1}, "thickness": 2}}
```

The answer:

```text
Done: AI: Shell 2 mm. Its id is 'Shell1'. Bodies now: Body1: 7872 mm3, 60 x 40 x 10 mm.
```

## More argument examples

- an open box with 2 mm walls:
  `{"faces": {"normal": [0, 0, 1], "count": 1}, "thickness": 2}`

## See also

- Recipe: [enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md)
- Golden models built with its steps (read one with docs_read golden/<id>): `edit_extrude_then_shell`, `shell_filleted_box`, `shell_open_box`, `picks_shell_kept_on_taper`, `sf_draft_then_shell`, `sf_shell_both`, `sf_shell_both_edit_presspull`, `sf_shell_both_follows_extrude_edit`, `sf_shell_cup`, `sf_shell_edit_to_both`, `sf_shell_hollow_body`, `sf_shell_hollow_both` and 5 more
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
