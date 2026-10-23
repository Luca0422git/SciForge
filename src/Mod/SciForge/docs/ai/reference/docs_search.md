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

~~~~text
3 of 623 matching sections (read one with docs_read and its path):
{
 "query": "shell open top wall thickness",
 "results": [
  {
   "uri": "sciforge://docs/examples/golden-models.md#shell-14",
   "path": "examples/golden-models.md",
   "anchor": "shell-14",
   "document": "Golden models by feature",
   "section": "shell (14)",
   "score": 18.511,
   "snippet": "... hollow] - `sf_shell_open_box`: Box 40x30x10, Shell: top face taken away, 2 mm inside [sciforge-shell] - `sf_shell_outside_rounded`: Box, Shell Outside 1 mm (top taken away), Shell Type Rounded [sciforge-shell] - `sf_shell_outside_sharp`: Box, Shell Outside 1 mm (top taken away), sharp corners ..."
  },
  {
   "uri": "sciforge://docs/reference/shell.md#example-1-hollow-the-plate-open-at-the-top-2-mm-walls",
   "path": "reference/shell.md",
   "anchor": "example-1-hollow-the-plate-open-at-the-top-2-mm-walls",
   "document": "`shell`: Shell",
   "section": "Example 1: hollow the plate, open at the top, 2 mm walls",
   "score": 18.498,
   "snippet": "... \"geometry\": [{\"rect\": [0, 0, 60, 40], \"name\": \"base\"}]}}, {\"tool\": \"extrude\", \"args\": {\"profile\": \"Sketch1\", \"distance\": 10}} ] ``` The call: ```json {\"tool\": \"shell\", \"args\": {\"faces\": {\"normal\": [0, 0, 1], \"at\": {\"axis\": \"z\", \"value\": \"max\"}, \"count\": 1}, \"thickness\": 2}} ``` The answer: ..."
  },
  {
   "uri": "sciforge://docs/reference/docs_search.md#example-1-find-how-to-hollow-a-part",
   "path": "reference/docs_search.md",
   "anchor": "example-1-find-how-to-hollow-a-part",
   "document": "`docs_search`: Search the documentation",
   "section": "Example 1: find how to hollow a part",
   "score": 17.729,
   "snippet": "... taken away, 2 mm inside [sciforge-shell] - `sf_shell_outside_rounded`: Box, Shell Outside 1 mm (top taken away), Shell Type Rounded [sciforge-shell] - `sf_shell_outside_sharp`: Box, Shell Outside 1 mm (top taken away), sharp corners ...\" }, { \"uri\": \"sciforge://docs/reference/shell.md#what-it-does\", \"path\": \"reference/shell.md\", \"anchor\": ..."
  }
 ],
 "total": 623
}
~~~~

## More argument examples

- how to pick the edges to fillet:
  `{"query": "fillet edges after a hole"}`
- the recipes about boxes with a lid:
  `{"query": "enclosure lid", "scope": "recipes", "limit": 3}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
