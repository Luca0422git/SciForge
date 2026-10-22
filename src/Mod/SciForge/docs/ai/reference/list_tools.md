# `list_tools`: List tools

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

Fusion: (SciForge's command list). Category: Help. Read-only. Needs nothing.

## What it does

List every tool by category with its Fusion command, whether it changes the design, and whether it can run right now (and why not: no design open, no solid yet, needs the SciForge window...). category: only that category.

## Arguments

| Argument | Type | Unit | Default | Limits | Description |
|---|---|---|---|---|---|
| `category` | `help` \| `document` \| `inspect` \| `sketch` \| `create` \| `modify` \| `surface` \| `construct` \| `assemble` \| `timeline` \| `parameters` \| `import_export` \| `drawing` \| `view` |  |  |  |  |

## Answer

A plain sentence, then JSON with: `tools`, `count`. The example below shows a real one.

## Errors

- Arguments of the wrong type, out of their limits or not in the table are refused the same way, each problem in a sentence ("radius must be a number above 0").
- When it cannot be done the answer says why in a sentence (isError true) and nothing changes.

## Example 1: by category

Starting from SciForge with no design open.

The call:

```json
{"tool": "list_tools", "args": {"category": "inspect"}}
```

The answer:

```text
{
 "tools": [
  {
   "name": "get_design",
   "title": "Get design",
   "category": "inspect",
   "ribbon": "BROWSER (the design's bodies, sketches, parameters) and TIMELINE",
   "read_only": true,
   "available": true
  },
  {
   "name": "measure",
   "title": "Measure",
   "category": "inspect",
   "ribbon": "INSPECT > Measure",
   "read_only": true,
   "available": false,
   "why_not": "No design is open: call new_design or open_design first (or create_sketch, which starts a new design)."
  },
  {
   "name": "physical_properties",
   "title": "Physical properties",
   "category": "inspect",
   "ribbon": "BROWSER > a body > Properties (INSPECT)",
   "read_only": true,
   "available": false,
   "why_not": "No design is open: call new_design or open_design first (or create_sketch, which starts a new design)."
  },
  {
   "name": "center_of_mass",
   "title": "Center of mass",
   "category": "inspect",
   "ribbon": "INSPECT > Center of Mass",
   "read_only": true,
   "available": false,
   "why_not": "No design is open: call new_design or open_design first (or create_sketch, which starts a new design)."
  },
  {
   "name": "interference",
   "title": "Interference",
   "category": "inspect",
   "ribbon": "INSPECT > Interference",
   "read_only": true,
   "available": false,
   "why_not": "No design is open: call new_design or open_design first (or create_sketch, which starts a new design)."
  },
  {
   "name": "section_analysis",
   "title": "Section analysis",
   "category": "inspect",
   "ribbon": "INSPECT > Section Analysis",
   "read_only": true,
   "available": false,
   "why_not": "No design is open: call new_design or open_design first (or create_sketch, which starts a new design)."
  },
  {
   "name": "inspect_design",
   "title": "Inspect design",
   "category": "inspect",
   "ribbon": "BROWSER + TIMELINE + Properties (everything at once)",
   "read_only": true,
   "available": true
  },
  {
   "name": "query_geometry",
   "title": "Query geometry",
   "category": "inspect",
   "ribbon": "Selection filters + INSPECT > Measure (on what a selector picks)",
   "read_only": true,
   "available": false,
... (23 more lines)
```

## More argument examples

- the Modify tools and which can run now:
  `{"category": "modify"}`

## See also

- [All tools](sciforge://docs/tools.md), [the handbook](sciforge://docs/handbook.md)
