# SPDX-License-Identifier: LGPL-2.1-or-later
"""The generated part of SciForge's documentation for AI models (docs/ai/ in the SciForge
module), written from the catalogue and the tests' data so it can never drift
(docs/sciforge/dev/cadcraft-lessons.md idea 3: "docs that cannot drift"):

  * tools.md: every tool in tools/list order with its Fusion command, kind and needs, linked
    to its reference page, and the shared rules (selectors, picks, sketch planes...) once;
  * reference/<tool>.md: one page per tool: what it does, every argument (type, unit,
    default, limits), the answer, the errors (what it needs, what a call without arguments
    is told), a complete example (the calls that make the design it starts from, the call,
    and the real answer recorded in FreeCAD: SciForgeTests/docs/tool_results.json, checked
    by SciForgeTests/headless/docs_runner.py), more argument examples, the recipes and
    golden models that use it;
  * examples/golden-models.md: the golden models (SciForgeTests/golden/models) by feature and
    by design-step op, with the tools that build each op;
  * user/...: a copy of SciForge's documentation for people (docs/sciforge: the cheat sheet,
    known issues, the feature outline, the parity specs...), so an AI can read everything
    the person can, also in an installed SciForge and the Claude extension.

tools/sciforge/make_ai_docs.py writes the files (generated() is the whole set); the unit test
test_ai_docs_contract.py fails when a file differs from what generated() makes now, when a
tool has no page or no example, or when a stale page is left over.

Pure Python: no FreeCAD, no Qt.
"""

import json
import os

from . import catalog, docs_core, value_fit
from .catalog import kit, registry

FILE = "tools.md"  # under the docs root (docs_core.docs_root())
REFERENCE = "reference"
GOLDEN_INDEX = "examples/golden-models.md"
USER = "user"
RESULTS = ("SciForgeTests", "docs", "tool_results.json")  # under the module root
HEADER = (
    "<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by "
    "tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test "
    "test_ai_docs_contract.py fails when this file and the catalogue differ. -->"
)
COPY_HEADER = (
    "<!-- A copy of docs/sciforge/%s for AI models, made by tools/sciforge/make_ai_docs.py: "
    "edit the original, then run the script. -->"
)
# The person's documentation copied under user/ (paths under docs/sciforge): every page at
# the top, the parity specs, and the developer guides (not the build briefs or the session
# logs).
USER_FOLDERS = ("", "parity", "dev")
SHOWN_TMP = "/home/me/sciforge"
MAX_ANSWER_LINES = 70

# The shared texts the descriptions include, written once under "Shared rules" in tools.md.
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
# Tools that change the open designs rather than a design's history: no undo step.
NOT_UNDO_STEPS = ("new_design", "close_design", "undo", "redo")
# Tools that change only what is shown or which body is active: neither is recorded, so they
# make no undo step and an `undo` after them takes back the step before.
VIEW_STATE_ONLY = ("show_hide", "activate")
# Tools that only open or switch designs (they write nothing and change no design).
OPENS_DESIGNS = ("open_design", "switch_design")


def _shorten(text, base=""):
    """The text with the shared rules replaced by a link to them (base: the link's
    document, "" for tools.md itself)."""
    for shared, topic in SHARED:
        if shared in text:
            link = "(rules: [%s](%s#help-%s))" % (topic, base, topic)
            text = text.replace(shared, link)
            while "%s %s" % (link, link) in text:
                text = text.replace("%s %s" % (link, link), link)
    return " ".join(text.split())


def _cell(text, base=""):
    return _shorten(str(text), base).replace("|", "\\|")


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
    if node.get("minItems") is not None and node.get("minItems") != node.get("maxItems"):
        words.append("at least %d item(s)" % node["minItems"])
    if node.get("maxItems") is not None and node.get("minItems") != node.get("maxItems"):
        words.append("at most %d item(s)" % node["maxItems"])
    return ", ".join(words)


def _unit(key, node):
    """The unit of a value, read from its description and the catalogue's conventions."""
    words = (node.get("description") or "").lower()
    kind = node.get("type")
    if kind not in ("number", "integer") and not (
        kind == "array"
        and isinstance(node.get("items"), dict)
        and node["items"].get("type") == "number"
    ):
        return ""
    if "degree" in words and "mm" in words:
        return "mm or deg"  # (a dimension's value: a length or an angle)
    if "degree" in words or key in ("angle", "angle2", "taper", "taper2", "twist", "rotation"):
        return "deg"
    if kind == "integer":
        return (
            "count" if key in ("quantity", "quantity2", "count", "count2", "teeth", "sides") else ""
        )
    if "pixel" in words:
        return "px"
    if "0..1" in words or "fraction" in key:
        return "0..1"
    if "mm" in words or key in (
        "distance",
        "distance2",
        "depth",
        "radius",
        "diameter",
        "thickness",
        "length",
        "width",
        "height",
        "offset",
        "x",
        "y",
        "dx",
        "dy",
        "dz",
        "spacing",
        "spacing2",
        "section_size",
        "at",
        "point",
        "center",
        "corner",
    ):
        return "mm"
    return ""


def _is_reference(node):
    """A selector or pick: explained by the shared rules, not row by row."""
    words = (node.get("description") or "").lower()
    return "selector" in words or "pick" in words or "properties" not in node


def _argument_rows(schema, base):
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    rows = []
    for key, node in props.items():
        rows.append((key, node, key in required))
        if node.get("type") == "object" and not _is_reference(node):
            inner_required = set(node.get("required") or [])
            for sub, subnode in (node.get("properties") or {}).items():
                rows.append(("%s.%s" % (key, sub), subnode, sub in inner_required))
    lines = [
        "| Argument | Type | Unit | Default | Limits | Description |",
        "|---|---|---|---|---|---|",
    ]
    for key, node, req in rows:
        default = node.get("default")
        default = "" if default is None else "`%s`" % json.dumps(default)
        lines.append(
            "| `%s`%s | %s | %s | %s | %s | %s |"
            % (
                key,
                " (required)" if req else "",
                _type_of(node),
                _unit(key.split(".")[-1], node),
                default,
                _cell(_limits(node)),
                _cell(node.get("description", ""), base),
            )
        )
    return lines if rows else ["No arguments."]


def _arguments(schema):
    """The argument table of tools.md's older form (kept for callers)."""
    return _argument_rows(schema, "")


def _flags(entry):
    words = []
    if entry["name"] in OPENS_DESIGNS:
        words.append("changes which design is open or active, changes no design")
    elif registry.is_read_only(entry):
        words.append("read-only")
    else:
        if entry["changes_design"]:
            if entry["name"] == "undo":
                words.append("takes back the last undo step")
            elif entry["name"] == "redo":
                words.append("brings back the last undone step")
            elif entry["name"] in NOT_UNDO_STEPS:
                words.append("changes the open designs (not an undo step)")
            elif entry["name"] in VIEW_STATE_ONLY:
                words.append(
                    "not an undo step: `undo` after it takes back the step before it; call it "
                    "again to reverse it"
                )
            else:
                words.append("changes the design (one undo step)")
        if entry["writes_files"]:
            words.append("writes files")
    if entry["destructive"]:
        words.append("destructive")
    return ", ".join(words)


def _needs(entry):
    return ", ".join(NEED_WORDS[n] for n in entry["needs"]) or "nothing"


def _anchor(text):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower()).strip("-")


def page_path(name):
    return "%s/%s.md" % (REFERENCE, name)


# -- tools.md -------------------------------------------------------------------------------------
def render():
    """tools.md: the table of every tool and the shared rules."""
    tools = catalog.TOOLS
    titles = dict(catalog.CATEGORIES)
    out = [
        "# SciForge AI tools",
        "",
        HEADER,
        "",
        "SciForge offers %d tools to AI apps (through MCP, the built-in chat panel and the "
        "command line), listed here in the order tools/list gives them. %s Every tool that "
        'changes the design is one undo step named "AI: ..."; errors come back as plain '
        "sentences. Each tool has a reference page (reference/<tool>.md: every argument, "
        "the answer, the errors and a complete example with its real answer); the resource "
        "sciforge://tools has every schema as JSON." % (len(tools), kit.UNITS),
        "",
        "## All tools",
        "",
        "| Tool | Title | Category | Fusion command | Kind | Needs |",
        "|---|---|---|---|---|---|",
    ]
    for t in tools:
        out.append(
            "| [`%s`](sciforge://docs/%s) | %s | %s | %s | %s | %s |"
            % (
                t["name"],
                page_path(t["name"]),
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
        out += ["", "## %s" % title, ""]
        for t in members:
            first = t["description"].split(". ")[0].rstrip(".")
            out.append(
                "- [`%s`](sciforge://docs/%s): %s."
                % (t["name"], page_path(t["name"]), _shorten(first))
            )
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


# -- reference pages ------------------------------------------------------------------------------
def load_results(path=None):
    """The recorded examples {"tool#n": {setup, setup_calls, args, note, answer}}."""
    path = path or os.path.join(docs_core.module_root(), *RESULTS)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def examples_of(name, results):
    out = []
    n = 1
    while "%s#%d" % (name, n) in results:
        out.append(results["%s#%d" % (name, n)])
        n += 1
    return out


def _shown(value):
    """Arguments as the pages show them: the tests' temporary folder as /home/me/sciforge."""
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("{tmp}", SHOWN_TMP)


def _call_line(call):
    return '{"tool": "%s", "args": %s}' % (call["tool"], _shown(call.get("args", {})))


def _answer_block(answer):
    lines = (answer.get("text") or "").rstrip("\n").split("\n")
    if len(lines) > MAX_ANSWER_LINES:
        more = len(lines) - MAX_ANSWER_LINES
        lines = lines[:MAX_ANSWER_LINES] + ["... (%d more lines)" % more]
    fence = "~~~~" if any("```" in line for line in lines) else "```"  # (never closed early)
    out = [fence + "text"] + lines + [fence]
    if answer.get("image"):
        out.append("")
        out.append(
            "With it, the picture itself: a %d x %d PNG (MCP image content)."
            % tuple(answer["image"])
        )
    if answer.get("is_error"):
        out.append("")
        out.append("(This answer is an error: isError is true.)")
    return out


def _answer_words(entry, examples):
    if entry["kind"] == "steps":
        return [
            "On success: `Done: <undo title>. Its id is '<id>'. Bodies now: <each solid "
            "body's volume in mm3 and size in mm>.` (some steps report no id); then `These "
            "steps now fail: ...` when the change broke later steps, and `Warning: no solid "
            "changed ...` when it changed no solid at all. On failure nothing changes and the "
            "answer is `Not done (<undo title>): <the reason>`."
        ]
    keys = []
    for ex in examples:
        data = docs_core_json(ex["answer"].get("text", ""))
        if isinstance(data, dict):
            for key in data:
                if key not in keys:
                    keys.append(key)
    words = "A plain sentence"
    if keys:
        words += ", then JSON with: %s" % ", ".join("`%s`" % k for k in keys)
    if any(ex["answer"].get("image") for ex in examples):
        words += ", and the picture as a PNG image"
    return [words + ". The example below shows a real one."]


def docs_core_json(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except ValueError:
        return None


def _errors(entry):
    lines = []
    for need in entry["needs"]:
        lines.append("- Without %s: `%s`" % (NEED_WORDS[need], catalog.NEEDS[need]))
    problems = catalog.validate(entry["name"], {})
    if problems:
        lines.append(
            "- Called without arguments, the arguments are refused before anything runs: "
            "`Not done: %s.`" % "; ".join(problems)
        )
    lines.append(
        "- Arguments of the wrong type, out of their limits or not in the table are refused "
        'the same way, each problem in a sentence ("radius must be a number above 0").'
    )
    if entry["kind"] == "steps":
        lines.append(
            "- When SciForge cannot build the step (a selector that picks another number of "
            "elements than `count`, a size that does not fit, an id that does not exist), "
            "the answer is `Not done (<undo title>): <reason>` and nothing changes; "
            "[troubleshooting](sciforge://docs/troubleshooting.md) lists the usual causes."
        )
    else:
        lines.append(
            "- When it cannot be done the answer says why in a sentence (isError true) and "
            "nothing changes."
        )
    limited = value_fit.LIMITED.get(entry["name"])
    if limited or entry["name"] == "edit_step":
        names = sorted({_dotted(path) for path, _words, _unit in limited or ()})
        which = (
            " (%s)" % ", ".join("`%s`" % n for n in names)
            if names
            else " (a radius, distance, thickness or angle in `set`)"
        )
        lines.append(
            "- A size that does not fit%s is refused, never built smaller in its place: the "
            "reason ends with the largest value that fits, found by trying smaller ones "
            "(`Largest radius that fits here: 19.99 mm (30 mm does not; ... give radius "
            "19.99 or less).`; `Furthest ... that fits here` for a value below 0). A "
            "value given as a formula is not searched. See "
            "[troubleshooting](sciforge://docs/troubleshooting.md#a-size-that-does-not-fit)."
            % which
        )
    if entry["name"] in SKETCH_EXPLAINED:
        lines.append(
            "- A constraint or dimension that conflicts with the sketch, or that the sketch "
            "already says, is not added (a new value it cannot take is not set): the answer "
            "names the constraints it fights or repeats, as the sketch tools do in the window "
            "(`Vertical: not added, it conflicts with the 50 mm dimension 'len' (constraint 1 "
            "of Sketch1: ...).`, `..., the 50 mm dimension 'len' already makes it so ...`, "
            "`That value does not fit: it conflicts with ...`). See "
            "[sketches](sciforge://docs/sketches.md#constraints-and-dimensions)."
        )
    return lines


SKETCH_EXPLAINED = ("sketch_constraint", "sketch_dimension", "set_sketch_dimension")


def _dotted(path):
    return ".".join("[]" if key == "*" else key for key in path).replace(".[]", "[]")


def reference_page(entry, results, recipes=(), golden=()):
    """The Markdown page of one tool."""
    name = entry["name"]
    titles = dict(catalog.CATEGORIES)
    base = "sciforge://docs/" + FILE
    examples = examples_of(name, results)
    flags = _flags(entry)
    undo = ""
    if entry["changes_design"] and name not in NOT_UNDO_STEPS + VIEW_STATE_ONLY:
        sample = (
            examples[0]["args"]
            if examples
            else (entry["examples"][0]["arguments"] if entry["examples"] else {})
        )
        undo = ' Its undo step is named like "%s".' % catalog.step_title(name, sample)
    out = [
        "# `%s`: %s" % (name, entry["title"]),
        "",
        HEADER,
        "",
        "Fusion: %s. Category: %s. %s.%s Needs %s."
        % (
            entry["ribbon"],
            titles[entry["category"]],
            flags[:1].upper() + flags[1:],
            undo,
            _needs(entry),
        ),
    ]
    if entry["ops"]:
        out.append(
            "It builds the design step(s) %s (the golden models' step language)."
            % ", ".join("`%s`" % op for op in entry["ops"])
        )
    out += ["", "## What it does", "", _shorten(entry["description"], base), ""]
    out += ["## Arguments", ""] + _argument_rows(entry["input_schema"], base)
    out += ["", "## Answer", ""] + _answer_words(entry, examples)
    out += ["", "## Errors", ""] + _errors(entry)
    for i, ex in enumerate(examples, start=1):
        out += ["", "## Example %d: %s" % (i, ex.get("note", ""))]
        if ex.get("setup_calls"):
            out += ["", "Starting from this design (made by these calls):", "", "```json", "["]
            calls = ex["setup_calls"]
            out += [
                "  %s%s" % (_call_line(c), "," if j < len(calls) - 1 else "")
                for j, c in enumerate(calls)
            ]
            out += ["]", "```"]
        else:
            out += ["", "Starting from SciForge with no design open."]
        out += [
            "",
            "The call:",
            "",
            "```json",
            _call_line({"tool": name, "args": ex["args"]}),
            "```",
            "",
            "The answer:",
            "",
        ]
        out += _answer_block(ex["answer"])
    if entry["examples"]:
        out += ["", "## More argument examples", ""]
        for ex in entry["examples"]:
            out.append("- %s:" % _cell(ex["note"]).rstrip("."))
            out.append("  `%s`" % json.dumps(ex["arguments"], ensure_ascii=False))
    see = []
    for rel, title in recipes:
        title = title.replace("Recipe: ", "", 1)
        see.append("- Recipe: [%s](sciforge://docs/%s)" % (title, rel))
    if golden:
        ids = ", ".join("`%s`" % g for g in golden[:12])
        more = " and %d more" % (len(golden) - 12) if len(golden) > 12 else ""
        see.append(
            "- Golden models built with its steps (read one with docs_read golden/<id>): "
            "%s%s" % (ids, more)
        )
    see.append(
        "- [All tools](sciforge://docs/%s), [the handbook](sciforge://docs/handbook.md)" % FILE
    )
    out += ["", "## See also", ""] + see
    return "\n".join(out).rstrip() + "\n"


# -- golden models --------------------------------------------------------------------------------
def golden_index(models=None):
    models = docs_core.golden_models() if models is None else models
    tools_of = docs_core.op_tools()
    out = [
        "# Golden models by feature",
        "",
        HEADER,
        "",
        "SciForge's golden models are %d small designs, each a list of design steps with the "
        "measurements the finished part must have (volume, area, faces, bounding box), worked "
        "out by hand where possible (`expect.source: analytic`, the formula in `expect.note`). "
        "The tests rebuild every one in real FreeCAD. They prove what each feature does and "
        "show which options exist. Their steps are SciForge's design-step language (what the "
        "AI tools build), not tool calls: the table at the end gives the tools that build "
        "each op. Read one with docs_read `golden/<id>` (or the resource "
        "sciforge://examples/golden/<id>); examples_search finds them by words, op, tool or "
        "tag. Models marked (known gap) document something SciForge does not do yet." % len(models),
        "",
        "## By feature",
        "",
        "Each model is listed under its first tag; its other tags follow it.",
    ]
    groups = {}
    for model in models:
        tag = model["tags"][0] if model["tags"] else "other"
        groups.setdefault(tag, []).append(model)
    for tag in sorted(groups, key=lambda t: (-len(groups[t]), t)):
        out += ["", "### %s (%d)" % (tag, len(groups[tag])), ""]
        for model in groups[tag]:
            extra = [t for t in model["tags"][1:]]
            out.append(
                "- `%s`: %s%s%s"
                % (
                    model["id"],
                    " ".join(model["title"].split()),
                    " [%s]" % ", ".join(extra) if extra else "",
                    " (known gap)" if model["xfail"] else "",
                )
            )
    ops = {}
    for model in models:
        for op in model["ops"]:
            ops.setdefault(op, []).append(model["id"])
    out += [
        "",
        "## By design-step op",
        "",
        "| Op | Built by the tools | Models | Some of them |",
        "|---|---|---|---|",
    ]
    for op in sorted(ops):
        out.append(
            "| `%s` | %s | %d | %s |"
            % (
                op,
                ", ".join("`%s`" % t for t in tools_of.get(op, [])) or "(a test helper)",
                len(ops[op]),
                ", ".join("`%s`" % m for m in ops[op][:5]),
            )
        )
    return "\n".join(out).rstrip() + "\n"


# -- the person's documentation -------------------------------------------------------------------
def user_sources(repo):
    """[(path under docs/sciforge, absolute path)] of the person's documents to copy."""
    base = os.path.join(repo, "docs", "sciforge")
    found = []
    for folder in USER_FOLDERS:
        here = os.path.join(base, folder) if folder else base
        if not os.path.isdir(here):
            continue
        for name in sorted(os.listdir(here)):
            if name.endswith(".md") and not name.startswith("."):
                rel = (folder + "/" + name) if folder else name
                found.append((rel, os.path.join(here, name)))
    return found


def user_copy(rel, text):
    return COPY_HEADER % rel + "\n\n" + text


# -- everything -----------------------------------------------------------------------------------
def _recipes_by_tool():
    lib = docs_core.library()
    out = {}
    for ex in lib.examples():
        if ex["kind"] != "recipe":
            continue
        rel = ex["uri"][len(docs_core.DOCS_URI) :]
        for tool in ex["tools"]:
            out.setdefault(tool, []).append((rel, ex["title"]))
    return out


def generated(repo=None, results=None):
    """{path under the docs root: text} of every generated document. repo: the source tree's
    root (the user/ copies are made only when its docs/sciforge is there)."""
    results = load_results() if results is None else results
    models = docs_core.golden_models()
    recipes = _recipes_by_tool()
    golden_by_op = {}
    for model in models:
        for op in model["ops"]:
            golden_by_op.setdefault(op, []).append(model["id"])
    files = {FILE: render(), GOLDEN_INDEX: golden_index(models)}
    for entry in catalog.TOOLS:
        golden = []
        for op in entry["ops"]:
            for ident in golden_by_op.get(op, []):
                if ident not in golden:
                    golden.append(ident)
        files[page_path(entry["name"])] = reference_page(
            entry, results, recipes.get(entry["name"], []), golden
        )
    if repo and os.path.isdir(os.path.join(repo, "docs", "sciforge")):
        for rel, full in user_sources(repo):
            with open(full, encoding="utf-8") as handle:
                files["%s/%s" % (USER, rel)] = user_copy(rel, handle.read())
    return files


def generated_folders():
    """The folders whose every file is generated (a file there that generated() does not
    make is stale)."""
    return (REFERENCE, USER)
