# SPDX-License-Identifier: LGPL-2.1-or-later
"""The MCP resources and prompts SciForge offers (docs/sciforge/dev/cadcraft-lessons.md idea
3: "the design summary and the command catalogue as readable resources"). mcp_core.py
answers resources/list, resources/templates/list, resources/read, prompts/list and
prompts/get with what is here.

Resources (MCP 2025-06-18 / 2025-11-25 server/resources):
  sciforge://design            the open design as numbers (the inspect_design tool)
  sciforge://design/check      is it sound (check_design)
  sciforge://design/timeline   the timeline (get_timeline)
  sciforge://step/{id}         one step's definition (get_step)
  sciforge://tools             the tool catalogue (sciforge/ai/catalog) as JSON
  sciforge://tools/{name}      one tool
  sciforge://help/{topic}      the rules the tools' descriptions refer to (get_help)
  sciforge://docs/index        the list of documents below
  sciforge://docs/{path}       every document under the docs root (<Mod>/SciForge/docs/ai,
                               or $SCIFORGE_AI_DOCS): Markdown written for AI models; with
                               #anchor, only that section (docs_core.py finds sections)
  sciforge://examples/golden/{id}  one golden model (a design-step list with measurements)
  sciforge://handbook          every document in one file (sciforge://handbook/full adds
                               SciForge's user documentation, /compact leaves out the tool
                               reference pages)
The design resources ask SciForge through call_tool, so they work the same through the
bridge, headless and in the tests; the rest is read here (the server never imports
FreeCAD).

Prompts (server/prompts): workflow templates an AI app shows its user as commands
("model a part from a description", "fix a failed step", "prepare for 3D printing"...).
Each names the tools it relies on; the unit tests check they exist.

Pure Python: no FreeCAD, no Qt.
"""

import json
import os

from . import catalog, docs_core

SCHEME = "sciforge://"
ENV_DOCS = docs_core.ENV_DOCS
DOC_TYPES = docs_core.DOC_TYPES
MAX_DOC_BYTES = docs_core.MAX_DOC_BYTES

RESOURCE_NOT_FOUND = -32002  # (the MCP specification's code for an unknown resource)
INVALID_PARAMS = -32602


class ResourceError(Exception):
    """A request that cannot be answered: code (JSON-RPC) and a plain message."""

    def __init__(self, code, message, data=None):
        Exception.__init__(self, message)
        self.code = code
        self.data = data


def docs_root():
    """Where the documents for AI models are: $SCIFORGE_AI_DOCS, else <Mod>/SciForge/docs/ai
    (next to the sciforge package, in the source tree, an install and the Claude extension)."""
    return docs_core.docs_root()


# -- the design: asked from SciForge ----------------------------------------------------------
DESIGN_RESOURCES = (
    (
        "sciforge://design",
        "design",
        "The open design",
        "Every body (valid?, volume, area, bounding box, centre of mass, counts), every "
        "timeline step (state, error, values), parameters, components, joints, the selection "
        "(the inspect_design tool).",
        "inspect_design",
        {},
    ),
    (
        "sciforge://design/check",
        "design-check",
        "Design check",
        "Problems and warnings: invalid or open solids, failed steps, overlapping bodies (the "
        "check_design tool).",
        "check_design",
        {},
    ),
    (
        "sciforge://design/timeline",
        "design-timeline",
        "Timeline",
        "The timeline's steps in order with their state and values, and the history marker "
        "(the get_timeline tool).",
        "get_timeline",
        {},
    ),
)
TEMPLATES = (
    {
        "uriTemplate": "sciforge://step/{id}",
        "name": "step",
        "title": "A timeline step",
        "description": "One step's definition, as its dialog shows it (the get_step tool); id "
        "is a step id from the timeline.",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "sciforge://tools/{name}",
        "name": "tool",
        "title": "A tool",
        "description": "One tool of the catalogue: description, argument schema, examples, "
        "whether it changes the design and what it needs.",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "sciforge://help/{topic}",
        "name": "help",
        "title": "A help topic",
        "description": "The rules the tools refer to: overview, selectors, picks, sketches, "
        "workflow, checking...",
        "mimeType": "text/plain",
    },
    {
        "uriTemplate": "sciforge://docs/{path}",
        "name": "doc",
        "title": "A document for AI models",
        "description": "A document of SciForge's documentation for AI models; "
        "sciforge://docs/index lists them. Add #anchor for one section.",
        "mimeType": "text/markdown",
    },
    {
        "uriTemplate": "sciforge://examples/golden/{id}",
        "name": "golden-model",
        "title": "A golden model",
        "description": "One of SciForge's golden models: a small design as design steps with "
        "its measured volume, area and size (sciforge://docs/examples/golden-models.md lists "
        "them by feature; examples_search finds them).",
        "mimeType": "application/json",
    },
)


def _json_part(text):
    """The JSON of a tool's answer (the sentence before it dropped), or None."""
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.dumps(json.loads(text[start:]), indent=1, ensure_ascii=False)
    except ValueError:
        return None


def _from_tool(uri, tool, args, call_tool):
    try:
        answer = call_tool(tool, args)
    except Exception as exc:
        return [
            {"uri": uri, "mimeType": "text/plain", "text": "SciForge could not answer: %s" % exc}
        ]
    text = (answer or {}).get("text", "") if isinstance(answer, dict) else str(answer)
    if isinstance(answer, dict) and not answer.get("is_error"):
        body = _json_part(text)
        if body is not None:
            return [{"uri": uri, "mimeType": "application/json", "text": body}]
    return [{"uri": uri, "mimeType": "text/plain", "text": text}]


# -- documents --------------------------------------------------------------------------------
def doc_files(root=None):
    """[(relative path with /, absolute path)] of the documents (docs_core.doc_files)."""
    return docs_core.doc_files(root or docs_root())


def _title_of(path):
    try:
        with open(path, encoding="utf-8") as handle:
            head = handle.read(8192)
    except OSError:
        head = ""
    fallback = os.path.splitext(os.path.basename(path))[0]
    if not path.lower().endswith(".md"):
        return fallback
    return docs_core.title_of_text(head, fallback)


def _doc_path(rel, root=None):
    """The absolute path of a document named in a URI, only inside the docs root."""
    return docs_core.safe_rel(rel, root or docs_root())


def docs_index(root=None):
    """A Markdown list of the documents and the other resources."""
    lines = [
        "# SciForge documentation for AI models",
        "",
        "Read these with resources/read. The tools themselves are in tools/list; "
        "sciforge://tools has them all as JSON.",
        "",
    ]
    files = doc_files(root)
    if files:
        for rel, full in files:
            lines.append(
                "- [%s](sciforge://docs/%s) `sciforge://docs/%s`" % (_title_of(full), rel, rel)
            )
    else:
        lines.append("(No documents are installed yet.)")
    lines += ["", "Also:", ""]
    for uri, _name, title, _desc, _tool, _args in DESIGN_RESOURCES:
        lines.append("- [%s](%s)" % (title, uri))
    lines.append("- [The tool catalogue](sciforge://tools)")
    for topic in help_topics():
        lines.append("- [Help: %s](sciforge://help/%s)" % (topic, topic))
    return "\n".join(lines) + "\n"


def help_topics():
    return list(catalog.HELP) + ["tools"]


# -- the lists --------------------------------------------------------------------------------
def _size(root, **kind):
    """ About how big a single-file export is, in tokens (an AI app's context is counted in
    them), for its resource description."""
    try:
        text = docs_core.export_text(lib=docs_core.library(root or docs_root()), **kind)
        return " About %s tokens." % docs_core.tokens_text(len(text))
    except Exception:
        return ""


def resources(root=None):
    """resources/list's resources (every document listed, not only the index)."""
    out = []
    for uri, name, title, description, _tool, _args in DESIGN_RESOURCES:
        out.append(
            {
                "uri": uri,
                "name": name,
                "title": title,
                "description": description,
                "mimeType": "application/json",
            }
        )
    out.append(
        {
            "uri": "sciforge://tools",
            "name": "tools",
            "title": "Tool catalogue",
            "description": "Every tool with its Fusion command, argument schema, examples, "
            "whether it changes the design and what it needs (%d tools)." % len(catalog.TOOLS),
            "mimeType": "application/json",
        }
    )
    for topic in help_topics():
        out.append(
            {
                "uri": "sciforge://help/%s" % topic,
                "name": "help-%s" % topic,
                "title": "Help: %s" % topic,
                "description": "SciForge's rules for AI tools: %s." % topic,
                "mimeType": "text/plain",
            }
        )
    out.append(
        {
            "uri": "sciforge://docs/index",
            "name": "docs-index",
            "title": "Documentation index",
            "description": "The documents for AI models and the other resources.",
            "mimeType": "text/markdown",
        }
    )
    out.append(
        {
            "uri": "sciforge://handbook",
            "name": "handbook",
            "title": "SciForge for AI models (one file)",
            "description": "Every document for AI models in one Markdown file: handbook, "
            "recipes and the reference page of every tool." + _size(root),
            "mimeType": "text/markdown",
        }
    )
    out.append(
        {
            "uri": "sciforge://handbook/compact",
            "name": "handbook-compact",
            "title": "SciForge for AI models, compact (one file)",
            "description": "The handbook, the guides, the recipes and the list of tools in one "
            "Markdown file (without the reference page of every tool)."
            + _size(root, compact=True),
            "mimeType": "text/markdown",
        }
    )
    out.append(
        {
            "uri": "sciforge://handbook/full",
            "name": "handbook-full",
            "title": "SciForge for AI models, with the user documentation (one file)",
            "description": "sciforge://handbook plus SciForge's documentation for people "
            "(cheat sheet, known issues, the Fusion parity spec of every feature)."
            + _size(root, full=True),
            "mimeType": "text/markdown",
        }
    )
    for rel, full in doc_files(root):
        row = {
            "uri": "sciforge://docs/%s" % rel,
            "name": "doc-%s" % rel,
            "title": _title_of(full),
            "mimeType": DOC_TYPES[os.path.splitext(rel)[1].lower()],
        }
        try:
            row["size"] = os.path.getsize(full)
        except OSError:
            pass
        out.append(row)
    return out


def templates():
    return [dict(t) for t in TEMPLATES]


def read(uri, call_tool, root=None):
    """resources/read's contents for a URI; ResourceError when there is no such resource."""
    if not isinstance(uri, str) or not uri.startswith(SCHEME):
        raise ResourceError(RESOURCE_NOT_FOUND, "Resource not found: %s" % uri, {"uri": uri})
    for known, _name, _title, _desc, tool, args in DESIGN_RESOURCES:
        if uri == known:
            return _from_tool(uri, tool, args, call_tool)
    rest = uri[len(SCHEME) :]
    if rest == "tools":
        text = json.dumps(catalog.catalogue(), indent=1, ensure_ascii=False)
        return [{"uri": uri, "mimeType": "application/json", "text": text}]
    if rest.startswith("tools/"):
        entry = catalog.tool(rest[len("tools/") :])
        if entry is not None:
            text = json.dumps(catalog.public(entry), indent=1, ensure_ascii=False)
            return [{"uri": uri, "mimeType": "application/json", "text": text}]
    if rest.startswith("help/"):
        topic = rest[len("help/") :]
        if topic in help_topics():
            return [{"uri": uri, "mimeType": "text/plain", "text": catalog.help_text(topic)}]
    if rest.startswith("step/") and len(rest) > len("step/"):
        return _from_tool(uri, "get_step", {"step": rest[len("step/") :]}, call_tool)
    if rest == "docs/index":
        return [{"uri": uri, "mimeType": "text/markdown", "text": docs_index(root)}]
    if rest in ("handbook", "handbook/full", "handbook/compact"):
        lib = docs_core.library(root or docs_root())
        text = docs_core.export_text(
            full=rest.endswith("/full"), lib=lib, compact=rest.endswith("/compact")
        )
        return [{"uri": uri, "mimeType": "text/markdown", "text": text}]
    if rest.startswith("examples/golden/"):
        ident = rest[len("examples/golden/") :]
        models = {m["id"]: m for m in docs_core.golden_models()}
        if ident in models:
            with open(models[ident]["path"], encoding="utf-8") as handle:
                text = handle.read()
            return [{"uri": uri, "mimeType": "application/json", "text": text}]
    if rest.startswith("docs/") and "#" in rest:
        rel, _sep, anchor = rest[len("docs/") :].partition("#")
        if _doc_path(rel, root) is not None and anchor:
            lib = docs_core.library(root or docs_root())
            sec = lib.find_section(rel, anchor) if lib.doc(rel) else None
            if sec is not None:
                lines = lib.doc(rel).text.split("\n")
                text = "\n".join(lines[sec["start"] : sec["end"]]).strip("\n") + "\n"
                return [{"uri": uri, "mimeType": "text/markdown", "text": text}]
    if rest.startswith("docs/"):
        full = _doc_path(rest[len("docs/") :], root)
        if full is not None:
            if os.path.getsize(full) > MAX_DOC_BYTES:
                raise ResourceError(INVALID_PARAMS, "The document %s is too big to read." % uri)
            with open(full, encoding="utf-8") as handle:
                text = handle.read()
            kind = DOC_TYPES[os.path.splitext(full)[1].lower()]
            return [{"uri": uri, "mimeType": kind, "text": text}]
    raise ResourceError(RESOURCE_NOT_FOUND, "Resource not found: %s" % uri, {"uri": uri})


# -- prompts ----------------------------------------------------------------------------------
_CHECK = (
    "After every change read the numbers the tool answers; when in doubt call diff_design "
    '(since "last_change") to see exactly what the change did, query_geometry before picking '
    "faces or edges (its ref is a selector that picks exactly one element), and render "
    "(with highlight) to look. Trust the numbers first and the picture second."
)

PROMPTS = (
    {
        "name": "model_part",
        "title": "Model a part from a description",
        "description": "Build a part in SciForge from a description in words, step by step "
        "and checked with numbers.",
        "arguments": [
            {"name": "description", "description": "what to model, with sizes", "required": True},
            {"name": "material", "description": "the material (e.g. Aluminum)", "required": False},
            {
                "name": "save_as",
                "description": "a .FCStd path to save to at the end",
                "required": False,
            },
        ],
        "tools": [
            "examples_search",
            "docs_search",
            "inspect_design",
            "new_design",
            "create_sketch",
            "extrude",
            "set_parameter",
            "query_geometry",
            "diff_design",
            "render",
            "check_design",
            "physical_material",
            "save_as",
        ],
        "text": (
            "Model this part in SciForge: {description}\n\n"
            "Work like a careful CAD designer:\n"
            "1. Call inspect_design to see what is open; call new_design when you need an "
            "empty design. Look for a tested recipe of a similar part with examples_search, "
            "and search the documentation with docs_search when unsure how a tool behaves.\n"
            "2. Plan the steps first (base sketch, extrude / revolve, then holes, fillets, "
            "patterns), in millimetres. Name the key sizes with set_parameter and use them in "
            "expressions so the part stays easy to change.\n"
            "3. Build one step at a time: create_sketch on an origin plane (or a face), then "
            "extrude / revolve / hole / fillet / chamfer / pattern. " + _CHECK + "\n"
            "4. If a step fails, read the sentence, fix the arguments and try again; undo takes "
            "back a step that came out wrong.\n"
            "5. When the part is done, call check_design and render (iso and one more view), "
            "and compare the volume and bounding box with the description.\n"
            "6. {material}\n"
            "7. {save}"
        ),
    },
    {
        "name": "fix_failed_step",
        "title": "Fix a failed timeline step",
        "description": "Find out why a timeline step fails and repair it without breaking the "
        "later steps.",
        "arguments": [
            {
                "name": "step",
                "description": "the step id (default: every failed step)",
                "required": False,
            },
        ],
        "tools": [
            "check_design",
            "get_step",
            "get_timeline",
            "edit_step",
            "roll_timeline",
            "query_geometry",
            "diff_design",
            "render",
        ],
        "text": (
            "A step in the SciForge timeline fails{step}. Repair it:\n"
            "1. Call check_design: it lists the failed steps with the reason.\n"
            "2. For the step, call get_step (its options and what it uses) and get_timeline "
            "(what comes before and after it).\n"
            "3. Typical causes: a face or edge it used is gone after an earlier change (pick it "
            "again: query_geometry on the step before shows the faces and edges with refs, and "
            "render with highlight shows them), a size that no longer fits (a fillet radius "
            "too big, a cut deeper than the part), a sketch with no closed area.\n"
            "4. Change it with edit_step (or roll_timeline to before it, change what it builds "
            "on, then roll forward again). Do not delete steps unless the person agrees.\n"
            "5. Call check_design again until ok is true, and diff_design to confirm nothing "
            "else changed."
        ),
    },
    {
        "name": "prepare_for_3d_printing",
        "title": "Prepare for 3D printing",
        "description": "Check that the design is printable and export it as STL or 3MF.",
        "arguments": [
            {"name": "format", "description": "stl or 3mf (default 3mf)", "required": False},
            {"name": "path", "description": "where to write the file", "required": False},
            {"name": "material", "description": "the filament (e.g. PLA)", "required": False},
        ],
        "tools": [
            "check_design",
            "inspect_design",
            "interference",
            "physical_properties",
            "query_geometry",
            "render",
            "export",
        ],
        "text": (
            "Prepare the open SciForge design for 3D printing{material}.\n"
            "1. Call check_design: every body must be one valid, closed solid; a body in "
            "several pieces, an open shell or a failed step must be fixed first.\n"
            "2. Bodies that overlap print as one lump: check_design (and interference) lists "
            "them; tell the person.\n"
            "3. Call inspect_design and physical_properties: report each body's size (bounding "
            "box) and volume, and the mass in the chosen material; warn when a body is larger "
            "than a typical printer's bed (about 220 x 220 x 250 mm).\n"
            "4. Look for thin walls and small holes with query_geometry (cylinder faces and "
            "their radius) and render from two views.\n"
            "5. Suggest the orientation with the largest flat face down.\n"
            "6. Export with export (format {format}{path}) and report the file written."
        ),
    },
    {
        "name": "review_design",
        "title": "Review the open design",
        "description": "Describe the open design and point out problems and improvements.",
        "arguments": [],
        "tools": ["inspect_design", "check_design", "get_timeline", "render", "list_parameters"],
        "text": (
            "Review the design open in SciForge. Call inspect_design and check_design, read the "
            "timeline (get_timeline) and the parameters (list_parameters), and render it from "
            "the iso and top views. Then describe in plain words what the part is, its size "
            "and mass, how it was built (the steps), and list problems (failed steps, invalid "
            "or overlapping bodies, sketches that are not fully constrained, sizes typed as "
            "numbers that should be parameters) with a suggested fix for each. Change nothing."
        ),
    },
    {
        "name": "make_parametric",
        "title": "Make the design parametric",
        "description": "Turn the design's key sizes into named parameters that drive it.",
        "arguments": [
            {
                "name": "sizes",
                "description": "which sizes to name (default: the main ones)",
                "required": False,
            },
        ],
        "tools": [
            "inspect_design",
            "list_parameters",
            "set_parameter",
            "set_model_parameter",
            "diff_design",
            "check_design",
        ],
        "text": (
            "Make the open SciForge design parametric{sizes}. Call inspect_design and "
            "list_parameters to see every size the steps use. Create user parameters with "
            "set_parameter for the key sizes (clear names like width, wall, hole_d), then make "
            "the steps' values follow them with set_model_parameter expressions. After each "
            'change call diff_design (since "last_change") to confirm the shape did not '
            "change; finally change one parameter as a test, check the result with "
            "check_design, and set it back."
        ),
    },
)


def prompts():
    """prompts/list's prompts."""
    return [
        {
            "name": p["name"],
            "title": p["title"],
            "description": p["description"],
            "arguments": [dict(a) for a in p["arguments"]],
        }
        for p in PROMPTS
    ]


def _material(prompt, material):
    if prompt == "model_part":
        if material:
            return "Set the material to %s with physical_material and report the mass." % material
        return (
            "If the description names a material, set it with physical_material and report "
            "the mass."
        )
    return " in %s" % material if material else ""


def get_prompt(name, arguments=None):
    """prompts/get's result; ResourceError(INVALID_PARAMS) for an unknown prompt or a
    missing required argument."""
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise ResourceError(INVALID_PARAMS, "Invalid params: arguments must be an object")
    found = [p for p in PROMPTS if p["name"] == name]
    if not found:
        raise ResourceError(INVALID_PARAMS, "Unknown prompt: %s" % name)
    prompt = found[0]
    known = {a["name"] for a in prompt["arguments"]}
    for arg in prompt["arguments"]:
        value = arguments.get(arg["name"])
        if arg.get("required") and (not isinstance(value, str) or not value.strip()):
            raise ResourceError(
                INVALID_PARAMS, "Invalid params: the prompt %s needs %s" % (name, arg["name"])
            )
    unknown = sorted(set(arguments) - known)
    if unknown:
        raise ResourceError(
            INVALID_PARAMS,
            "Invalid params: the prompt %s has no argument %s" % (name, ", ".join(unknown)),
        )
    values = {k: str(v).strip() for k, v in arguments.items() if v is not None}
    fill = {
        "description": values.get("description", ""),
        "material": _material(name, values.get("material")),
        "save": (
            "Save it with save_as to %s." % values["save_as"]
            if values.get("save_as")
            else "Ask the person whether and where to save it (save_as)."
        ),
        "step": (" (%s)" % values["step"]) if values.get("step") else "",
        "format": values.get("format") or "3mf",
        "path": (", path %s" % values["path"]) if values.get("path") else "",
        "sizes": (": %s" % values["sizes"]) if values.get("sizes") else "",
    }
    text = prompt["text"].format(**fill)
    return {
        "description": prompt["description"],
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }
