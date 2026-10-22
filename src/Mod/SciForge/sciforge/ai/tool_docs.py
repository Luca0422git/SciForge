# SPDX-License-Identifier: LGPL-2.1-or-later
"""The tool reference for AI models (docs/ai/tools.md in the SciForge module), written from
the catalogue (sciforge/ai/catalog) so it can never drift from what tools/list offers
(docs/sciforge/dev/cadcraft-lessons.md idea 3: "docs that cannot drift").

tools/sciforge/make_ai_docs.py writes the file; the unit test test_ai_docs_contract.py
fails when the file differs from what render() makes now, when its table differs from
tools/list, or when a tool is missing. The MCP server offers the file as the resource
sciforge://docs/tools.md (mcp_resources.py). The shared rules the descriptions repeat
(selectors, picks, sketch planes...) are written once at the end and linked.

Pure Python: no FreeCAD, no Qt.
"""

import json

from . import catalog
from .catalog import kit, registry

FILE = "tools.md"  # under the docs root (mcp_resources.docs_root())
HEADER = (
    "<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by "
    "tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test "
    "test_ai_docs_contract.py fails when this file and the catalogue differ. -->"
)
# The shared texts the descriptions include, written once under "Shared rules".
SHARED = (
    (kit.SELECTOR_HELP, "selectors"),
    (kit.BODY_PICK_HELP, "body_picks"),
    (kit.PICK_HELP, "picks"),
    (kit.MORE_GEOMETRY_HELP, "geometry"),
    (kit.GEOMETRY_HELP, "geometry"),
    (kit.SKETCH_HELP, "sketches"),
    (kit.CURVES_HELP, "curves"),
    (kit.STEP_HELP, "steps"),
    (kit.EXPRESSION_HELP, "expressions"),
)
NEED_WORDS = {
    "design": "an open design",
    "solid": "a solid body",
    "gui": "the SciForge window",
    "drawing": "a drawing",
}


def _shorten(text):
    """The text with the shared rules replaced by a link to them."""
    for shared, topic in SHARED:
        if shared in text:
            link = "(rules: [%s](#help-%s))" % (topic, topic)
            text = text.replace(shared, link)
            while "%s %s" % (link, link) in text:
                text = text.replace("%s %s" % (link, link), link)
    return " ".join(text.split())


def _cell(text):
    return _shorten(str(text)).replace("|", "\\|")


def _type_of(node):
    kind = node.get("type")
    if isinstance(kind, list):
        return " or ".join(kind)
    if kind == "array":
        items = node.get("items") if isinstance(node.get("items"), dict) else {}
        inner = items.get("type", "")
        inner = (" or ".join(inner) if isinstance(inner, list) else inner) or "item"
        if node.get("minItems") is not None and node.get("minItems") == node.get("maxItems"):
            return "array of %d %ss" % (node["minItems"], inner)
        return "array of %ss" % inner
    if "enum" in node:
        return " \\| ".join("`%s`" % v for v in node["enum"])
    return kind or "any"


def _limits(node):
    words = []
    if "exclusiveMinimum" in node:
        words.append("> %s" % kit.fmt(node["exclusiveMinimum"]))
    if "minimum" in node:
        words.append(">= %s" % kit.fmt(node["minimum"]))
    if "maximum" in node:
        words.append("<= %s" % kit.fmt(node["maximum"]))
    return ", ".join(words)


def _arguments(schema):
    props = schema.get("properties") or {}
    if not props:
        return ["No arguments."]
    required = set(schema.get("required") or [])
    lines = ["| Argument | Type | Default | Description |", "|---|---|---|---|"]
    for key, node in props.items():
        name = "`%s`%s" % (key, " (required)" if key in required else "")
        default = node.get("default")
        default = "" if default is None else "`%s`" % json.dumps(default)
        words = node.get("description", "")
        limits = _limits(node)
        if limits:
            words = (words + " (" + limits + ")").strip()
        lines.append("| %s | %s | %s | %s |" % (name, _type_of(node), default, _cell(words)))
    return lines


def _flags(entry):
    words = []
    if registry.is_read_only(entry):
        words.append("read-only")
    else:
        if entry["changes_design"]:
            words.append("changes the design (one Undo step)")
        if entry["writes_files"]:
            words.append("writes files")
    if entry["destructive"]:
        words.append("destructive")
    return ", ".join(words)


def _needs(entry):
    return ", ".join(NEED_WORDS[n] for n in entry["needs"]) or "nothing"


def _anchor(text):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower()).strip("-")


def render():
    """The whole Markdown file."""
    tools = catalog.TOOLS
    titles = dict(catalog.CATEGORIES)
    out = [
        "# SciForge AI tools",
        "",
        HEADER,
        "",
        "SciForge offers %d tools to AI apps (through MCP, the built-in chat panel and the "
        "command line), listed here in the order tools/list gives them. %s Every tool that "
        'changes the design is one Undo step named "AI: ..."; errors come back as plain '
        "sentences. The same text is in each tool's description; the resource "
        "sciforge://tools has every schema as JSON." % (len(tools), kit.UNITS),
        "",
        "## All tools",
        "",
        "| Tool | Title | Category | Fusion command | Kind | Needs |",
        "|---|---|---|---|---|---|",
    ]
    for t in tools:
        out.append(
            "| [`%s`](#%s) | %s | %s | %s | %s | %s |"
            % (
                t["name"],
                _anchor(t["name"]),
                _cell(t["title"]),
                _cell(titles[t["category"]]),
                _cell(t["ribbon"]),
                _cell(_flags(t)),
                _cell(_needs(t)),
            )
        )
    for key, title in catalog.CATEGORIES:
        members = [t for t in tools if t["category"] == key]
        if not members:
            continue
        out += ["", "## %s" % title]
        for t in members:
            out += [
                "",
                '<a id="%s"></a>' % _anchor(t["name"]),
                "",
                "### `%s`: %s" % (t["name"], t["title"]),
                "",
                "Fusion: %s. %s. Needs %s."
                % (t["ribbon"], _flags(t)[:1].upper() + _flags(t)[1:], _needs(t)),
                "",
                _shorten(t["description"]),
                "",
            ]
            out += _arguments(t["input_schema"])
            if t["examples"]:
                out += ["", "Examples:", ""]
                for ex in t["examples"]:
                    out.append("- %s:" % _cell(ex["note"]).rstrip("."))
                    out.append("  `%s`" % json.dumps(ex["arguments"], ensure_ascii=False))
    out += ["", "## Shared rules", ""]
    for topic in list(catalog.HELP):
        out += [
            '<a id="help-%s"></a>' % topic,
            "",
            "### %s" % topic,
            "",
            catalog.help_text(topic).replace("\n", "\n\n"),
            "",
        ]
    return "\n".join(out).rstrip() + "\n"


def table_names(markdown):
    """The tool names in the "All tools" table of a tools.md text, in order."""
    names = []
    inside = False
    for line in markdown.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## All tools"
            continue
        if inside and line.startswith("| [`"):
            names.append(line.split("`")[1])
    return names
