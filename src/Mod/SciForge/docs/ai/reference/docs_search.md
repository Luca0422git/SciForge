# `docs_search`: Search the documentation

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (Fusion's help search, for SciForge). Category: Help. Read-only. Needs nothing.

## What it does

Search SciForge's documentation for AI models: the handbook (how SciForge works, Fusion's ideas mapped to SciForge, coordinates, the timeline, undo, checking your work, failures and how to recover), the selector cookbook, tested recipes for common parts, one reference page per tool (every argument, errors, a real example) and SciForge's own user documentation (cheat sheet, known issues, one Fusion parity spec per feature). Answers the best sections, ranked by how well their words match (BM25), each with a snippet and its address (a path with #anchor) to give to docs_read. Search before guessing how a tool or feature behaves. scope: all, or recipes, reference, user, examples, or one document path.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `query` (required) | string |  |  |  | words to look for, e.g. 'shell remove top face thickness' |
| `limit` | integer |  | `8` | >= 1, <= 30 | how many sections to answer |
| `scope` | string |  | `"all"` |  | all (default), a folder (recipes, reference, user, examples) or a document path such as handbook.md |

## Answer

A plain sentence, then JSON with: `query`, `results`, `total`. The example below shows a real one.

## Errors

- Called without arguments, the arguments are refused before anything runs: `Not done: query is missing.`
- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: find how to hollow a part

Starting from SciForge with no design open.

The call:

```json
{"tool": "docs_search", "args": {"query": "shell open top wall thickness", "limit": 3}}
```

The answer:

```text
3 of 576 matching sections (read one with docs_read and its path):
{
 "query": "shell open top wall thickness",
 "results": [
  {
   "uri": "sciforge://docs/reference/docs_search.md#example-1",
   "path": "reference/docs_search.md",
   "anchor": "example-1",
   "document": "`docs_search`: Search the documentation",
   "section": "Example 1:",
   "score": 19.814,
   "snippet": "... ```json {\"tool\": \"docs_search\", \"args\": {\"query\": \"shell open top wall thickness\", \"limit\": 3}} ``` The answer: ```text 3 of 98 matching sections (read one with docs_read and its path): { \"query\": \"shell open top wall thickness\", \"results\": [ { \"uri\": \"sciforge://docs/tools.md#shell-shell\", ..."
  },
  {
   "uri": "sciforge://docs/examples/golden-models.md#shell-14",
   "path": "examples/golden-models.md",
   "anchor": "shell-14",
   "document": "Golden models by feature",
   "section": "shell (14)",
   "score": 19.338,
   "snippet": "... hollow] - `sf_shell_open_box`: Box 40x30x10, Shell: top face taken away, 2 mm inside [sciforge-shell] - `sf_shell_outside_rounded`: Box, Shell Outside 1 mm (top taken away), Shell Type Rounded [sciforge-shell] - `sf_shell_outside_sharp`: Box, Shell Outside 1 mm (top taken away), sharp corners ..."
  },
  {
   "uri": "sciforge://docs/reference/shell.md#what-it-does",
   "path": "reference/shell.md",
   "anchor": "what-it-does",
   "document": "`shell`: Shell",
   "section": "What it does",
   "score": 18.185,
   "snippet": "Hollow the current body out with a wall thickness (SciForge's Shell). faces: the faces to remove (open), a face selector, e.g. the top face {\"normal\": [0, 0, 1], \"count\": 1}. direction inside (default: the outside stays where it is) or ..."
  }
 ],
 "total": 576
}
```

## More argument examples

- how to pick the edges to fillet:
  `{"query": "fillet edges after a hole"}`
- the recipes about boxes with a lid:
  `{"query": "enclosure lid", "scope": "recipes", "limit": 3}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
