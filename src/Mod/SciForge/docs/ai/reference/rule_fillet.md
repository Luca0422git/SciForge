# `rule_fillet`: Rule fillet

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: SOLID > MODIFY > Fillet (Type: Rule Fillet). Category: Modify. Changes the design (one undo step). Its undo step is named like "AI: Rule fillet". Needs a solid body.
It builds the design step(s) `rule_fillet` (the golden models' step language).

## What it does

Fusion's Rule Fillet: round every edge a rule finds, found again whenever the part changes. rule all (every edge of faces / features) or between (the edges between the first group and faces2 / features2); rounds (concave edges) and fillets (convex) on or off; radius (mm).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `radius` (required) | number | mm |  | > 0 | mm |
| `rule` | `all` \| `between` |  | `"all"` |  |  |
| `faces` | object |  |  |  | the faces (first group) (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `features` | array of strings |  |  | at least 1 item(s) | steps whose faces form the first group |
| `faces2` | object |  |  |  | the second group, rule between (a face selector: filters type, normal, along, radius, at, all, count, any_of; see get_help topic selectors). Give count. |
| `features2` | array of strings |  |  | at least 1 item(s) | steps for the second group |
| `rounds` | boolean |  | `true` |  |  |
| `fillets` | boolean |  | `true` |  |  |

## Answer

On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid body's volume in mm3 and size in mm>.` (some steps report no id); then `These steps now fail: ...` when the change broke later steps, and `Warning: no solid changed ...` when it changed no solid at all. On failure nothing changes and the answer is `Not done (<undo title>): <the reason>`.

## Errors

- Without a solid body: `The design has no solid body yet: make one first (create_sketch + extrude, or primitive).`
- Called without arguments, the arguments are refused before anything runs: `Not done: radius is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When SciForge cannot build the step (a selector that picks another number of elements than `count`, a size that does not fit, an id that does not exist), the answer is `Not done (<undo title>): <reason>` and nothing changes; [troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes.
- A size that does not fit (`radius`) is refused, never built smaller in its place: the reason ends with the largest value that fits, found by trying smaller ones (`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius 19.99 or less).`; `Furthest ... that fits here` for a value below 0). A value given as a formula is not searched. See [troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit).

## Example 1: round every edge of the boss

Starting from this design (made by these calls):

```json
[
  {"tool": "new_design", "args": {"name": "Example"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "base"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 10}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 10, "geometry": [{"circle": [10, 20, 5]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 5}}
]
```

The call:

```json
{"tool": "rule_fillet", "args": {"radius": 1, "rule": "all", "features": ["Extrude2"]}}
```

The answer:

```text
Done: AI: Rule fillet. Its id is 'Fillet1'. Bodies now: Body1: 24393.3 mm3, 60 x 40 x 15 mm.
```

## More argument examples

- round every edge the boss Extrude2 made:
  `{"radius": 1, "rule": "all", "features": ["Extrude2"]}`

## See also

- Golden models built with its steps (read one with docs_read golden/<id>): `fillet2_rule_all_edges`, `fillet2_rule_between_follows_edit`
- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
