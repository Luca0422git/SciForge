# `examples_search`: Search examples

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (Fusion's sample designs, for SciForge). Category: Help. Read-only. Needs nothing.

## What it does

Find worked examples: recipes (tested sequences of tool calls that build a common part: bracket, enclosure with lid, shaft with keyway, gear pair, flange with bolt pattern, threaded fastener, snap-fit, sheet-like part, revolved knob, lofted handle, surface patch...) and golden models (about 450 small designs in SciForge's design-step language, each with its measured volume and size: proof of what a feature does). Filter by words (query), a tool name (tool), a design-step op (op, e.g. blend_fillet), a tag or kind (recipe or golden). Read a hit with docs_read (its uri).

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `query` | string |  |  |  | words, e.g. 'counterbore hole pattern' |
| `tool` | string |  |  |  | only examples that use this tool, e.g. circular_pattern |
| `op` | string |  |  |  | only golden models with this design-step op, e.g. sf_shell |
| `tag` | string |  |  |  | only examples with this tag, e.g. fillet |
| `kind` | `all` \| `recipe` \| `golden` |  | `"all"` |  | which examples |
| `limit` | integer |  | `10` | >= 1, <= 50 | how many to answer |

## Answer

A plain sentence, then JSON with: `results`, `total`. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: give query, tool, op, tag or kind (recipe / golden): what to look for.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: examples of a flange with holes around a circle

Starting from SciForge with no design open.

The call:

```json
{"tool": "examples_search", "args": {"query": "bolt circle flange", "limit": 3}}
```

The answer:

```text
3 of 55 examples (read one with docs_read and its uri; a golden model's steps are design steps, the tools that build them are listed):
{
 "results": [
  {
   "kind": "recipe",
   "id": "flange-bolt-pattern",
   "title": "Recipe: flange with a bolt circle",
   "tags": [
    "flange",
    "bolt-pattern",
    "pcd",
    "revolve",
    "hole",
    "circular_pattern",
    "fillet",
    "chamfer",
    "turned-part"
   ],
   "ops": [],
   "tools": [
    "new_design",
    "create_sketch",
    "revolve",
    "hole",
    "circular_pattern",
    "query_geometry",
    "fillet",
    "chamfer",
    "diff_design",
    "check_design",
    "inspect_design"
   ],
   "note": "A pipe flange: a 100 mm disc, 10 mm thick, with a 40 mm hub 30 mm tall, a 20 mm bore, a",
   "calls": 12,
   "uri": "sciforge://docs/recipes/flange-bolt-pattern.md",
   "score": 22.22
  },
  {
   "kind": "golden",
   "id": "pattern_circ_faces_bolt_circle",
   "title": "Disc r40x10: the wall of a hole r4 patterned around Z, Full, 6 (Pattern Type Faces)",
   "tags": ["pattern", "circular", "faces", "fusion-dialog"],
   "ops": ["sketch", "extrude", "circular_pattern"],
   "tools": ["create_sketch", "extrude", "circular_pattern"],
   "note": "The picked wall is closed with the top and bottom faces into the hole's cylinder, which is cut at 60 degree steps. V = pi*40^2*10 - 6*pi*4^2*10; A = 2*1600pi + 2pi*40*10 - 12*16pi + 6*2pi*4*10 (same as flange_polar_holes).",
   "known_gap": false,
   "uri": "sciforge://examples/golden/pattern_circ_faces_bolt_circle",
   "score": 14.999
  },
  {
   "kind": "recipe",
   "id": "threaded-fastener",
   "title": "Recipe: threaded fastener (hex bolt M8 x 30)",
   "tags": ["bolt", "screw", "fastener", "thread", "hexagon", "polygon", "chamfer", "modeled-thread"],
   "ops": [],
   "tools": [
    "new_design",
    "create_sketch",
    "extrude",
    "chamfer",
    "inspect_design",
    "thread",
    "diff_design",
    "check_design"
   ],
   "note": "A hex head bolt M8 x 30: a 13 mm across-flats head 5.3 mm high (ISO 4017), a 30 mm shank",
   "calls": 10,
   "uri": "sciforge://docs/recipes/threaded-fastener.md",
   "score": 8.989
  }
... (3 more lines)
```

## More argument examples

- examples of a flange with a bolt pattern:
  `{"query": "bolt circle flange"}`
- recipes that use shell:
  `{"tool": "shell", "kind": "recipe"}`
- golden models of revolves:
  `{"op": "sf_revolve", "kind": "golden", "limit": 5}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
