# SciForge for AI models

These documents are written for the AI models that use SciForge's tools (through MCP, the
chat panel inside SciForge or `tools/sciforge/sciforge-cli`). The MCP server offers every
file in this folder as a resource: `sciforge://docs/<path>` (resources/list lists them,
[sciforge://docs/index](sciforge://docs/index) has them with their titles).

- [tools.md](sciforge://docs/tools.md): every tool, its Fusion command, its arguments and
  examples. Generated from the tool catalogue (`tools/sciforge/make_ai_docs.py`); never edit
  it by hand.
- The rules the tools refer to are help topics: [selectors](sciforge://help/selectors),
  [picks](sciforge://help/picks), [sketches](sciforge://help/sketches),
  [workflow](sciforge://help/workflow), [checking](sciforge://help/checking).

## Checking your own work

Build one step at a time and check each step with numbers before trusting a picture:
[inspect_design](sciforge://tools/inspect_design) (every body, step and parameter, with a
snapshot id), [diff_design](sciforge://tools/diff_design) (what changed since that snapshot,
since `last_change` or since a step), [query_geometry](sciforge://tools/query_geometry) (the
faces and edges a selector picks, each with a `ref` selector that picks exactly that one),
[check_design](sciforge://tools/check_design) (valid solids, failed steps, overlapping bodies)
and [render](sciforge://tools/render) (a picture, with `highlight` to mark what a selector
picks). The open design itself is the resource [sciforge://design](sciforge://design).

## Adding documents

Put a Markdown file in this folder (sub-folders are fine): it becomes
`sciforge://docs/<path>` at once, in the source tree, an installed SciForge and the Claude
extension. Link tools as `sciforge://tools/<name>` and other documents as
`sciforge://docs/<path>`: a unit test (`test_ai_docs_contract.py`) checks that every such
link exists.
