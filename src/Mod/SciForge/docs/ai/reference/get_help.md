# `get_help`: Get help

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (SciForge's documentation for AI models). Category: Help. Read-only. Needs nothing.

## What it does

Read SciForge's rules for AI tools: overview, selectors (how to pick faces and edges), picks (planes, axes, faces, edges, corners), body_picks, sketches (planes and coordinates), geometry (sketch shapes), curves (paths and rails), steps (ids), expressions (parameters in fields), workflow (how to build and check a part), checking (the tools that check your work with numbers and pictures), docs (where the documentation is and how to search it), tools (every tool by category with its Fusion command). Without topic: overview.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `topic` | `overview` \| `selectors` \| `picks` \| `body_picks` \| `sketches` \| `geometry` \| `curves` \| `steps` \| `expressions` \| `workflow` \| `checking` \| `docs` \| `tools` |  | `"overview"` |  |  |

## Answer

A plain sentence. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: the pick rules

Starting from SciForge with no design open.

The call:

```json
{"tool": "get_help", "args": {"topic": "picks"}}
```

The answer:

```text
A pick is one of {"plane": "XY"|"XZ"|"YZ"}, {"axis": "X"|"Y"|"Z"}, {"origin": true}, {"face": face selector}, {"edge": edge selector}, {"vertex": [x, y, z]} (a corner of the part) or {"construct": id} (a construction plane, axis or point made earlier). Face and edge selectors must pick exactly one element of the current body.
```

## More argument examples

- how selectors pick faces and edges:
  `{"topic": "selectors"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
