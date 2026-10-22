# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools that read SciForge's documentation for AI models (Luca, 2026-10-21: "absolutely all
the documentation available"): docs_search (keyword search over every document, ranked, with
snippets and section anchors), docs_read (a document or one section, in pages) and
examples_search (tested recipes and golden models by words, tool, op or tag). Fusion has its
help pages and sample designs; here they come back as text an AI can act on.

They only read files, need no design and no window, and the MCP server answers them itself
(mcp_core.py), so they work even while SciForge is closed. The work is in
sciforge/ai/docs_core.py. Pure Python.
"""

from .kit import enum, integer, schema, string
from .registry import define, example


def _extra_search(args, problems):
    query = args.get("query")
    if isinstance(query, str) and not query.strip():
        problems.append("query must not be empty: give a few words, e.g. fillet radius too big")


def _extra_read(args, problems):
    path = args.get("path")
    if isinstance(path, str) and not path.strip():
        problems.append("path must not be empty: give e.g. handbook.md or recipes/bracket.md")


def _extra_examples(args, problems):
    if not any(
        isinstance(args.get(k), str) and args.get(k).strip() for k in ("query", "tool", "op", "tag")
    ) and args.get("kind", "all") == "all":
        problems.append("give query, tool, op, tag or kind (recipe / golden): what to look for")


define(
    "docs_search",
    "Search the documentation",
    "help",
    "(Fusion's help search, for SciForge)",
    "Search SciForge's documentation for AI models: the handbook (how SciForge works, Fusion's "
    "ideas mapped to SciForge, coordinates, the timeline, undo, checking your work, failures "
    "and how to recover), the selector cookbook, tested recipes for common parts, one "
    "reference page per tool (every argument, errors, a real example) and SciForge's own user "
    "documentation (cheat sheet, known issues, one Fusion parity spec per feature). Answers "
    "the best sections, ranked by how well their words match (BM25), each with a snippet and "
    "its address (a path with #anchor) to give to docs_read. Search before guessing how a "
    "tool or feature behaves. scope: all, or recipes, reference, user, examples, or one "
    "document path.",
    schema(
        {
            "query": string("words to look for, e.g. 'shell remove top face thickness'"),
            "limit": integer("how many sections to answer", default=8, minimum=1, maximum=30),
            "scope": string(
                "all (default), a folder (recipes, reference, user, examples) or a document "
                "path such as handbook.md",
                default="all",
            ),
        },
        ["query"],
    ),
    changes=False,
    needs=(),
    extra=_extra_search,
    examples=[
        example({"query": "fillet edges after a hole"}, "how to pick the edges to fillet"),
        example(
            {"query": "enclosure lid", "scope": "recipes", "limit": 3},
            "the recipes about boxes with a lid",
        ),
    ],
)
define(
    "docs_read",
    "Read documentation",
    "help",
    "(Fusion's help page, for SciForge)",
    "Read one document of SciForge's documentation for AI models, or one section of it: path "
    "is what docs_search answers (handbook.md, recipes/bracket.md, reference/extrude.md, "
    "user/known-issues.md), optionally with #anchor for one section (or give section). Long "
    "documents come in pages of about 12000 characters: page 2, 3... for the rest; the first "
    "page of a long document lists its sections. A golden model is read with "
    "golden/<id> (its design steps and measurements). sciforge://docs/index lists every "
    "document.",
    schema(
        {
            "path": string(
                "a document path (handbook.md), with #anchor for one section, a URI "
                "sciforge://docs/<path> or golden/<id>"
            ),
            "section": string("the anchor of one section (instead of #anchor in path)"),
            "page": integer("which page of a long document", default=1, minimum=1),
        },
        ["path"],
    ),
    changes=False,
    needs=(),
    extra=_extra_read,
    examples=[
        example({"path": "handbook.md"}, "the handbook, first page"),
        example(
            {"path": "selectors.md", "section": "cookbook"}, "only the selector cookbook"
        ),
        example({"path": "golden/box_basic"}, "a golden model's steps and measurements"),
    ],
)
define(
    "examples_search",
    "Search examples",
    "help",
    "(Fusion's sample designs, for SciForge)",
    "Find worked examples: recipes (tested sequences of tool calls that build a common part: "
    "bracket, enclosure with lid, shaft with keyway, gear pair, flange with bolt pattern, "
    "threaded fastener, snap-fit, sheet-like part, revolved knob, lofted handle, surface "
    "patch...) and golden models (about 450 small designs in SciForge's design-step "
    "language, each with its measured volume and size: proof of what a feature does). "
    "Filter by words (query), a tool name (tool), a design-step op (op, e.g. blend_fillet), "
    "a tag or kind (recipe or golden). Read a hit with docs_read (its uri).",
    schema(
        {
            "query": string("words, e.g. 'counterbore hole pattern'"),
            "tool": string("only examples that use this tool, e.g. circular_pattern"),
            "op": string("only golden models with this design-step op, e.g. sf_shell"),
            "tag": string("only examples with this tag, e.g. fillet"),
            "kind": enum(("all", "recipe", "golden"), "which examples", default="all"),
            "limit": integer("how many to answer", default=10, minimum=1, maximum=50),
        }
    ),
    changes=False,
    needs=(),
    extra=_extra_examples,
    examples=[
        example({"query": "bolt circle flange"}, "examples of a flange with a bolt pattern"),
        example({"tool": "shell", "kind": "recipe"}, "recipes that use shell"),
        example({"op": "sf_revolve", "kind": "golden", "limit": 5}, "golden models of revolves"),
    ],
)
