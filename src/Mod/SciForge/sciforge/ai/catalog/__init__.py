# SPDX-License-Identifier: LGPL-2.1-or-later
"""The catalogue of AI tools: the single source of truth for every tool an AI can call in
SciForge (docs/sciforge/dev/cadcraft-lessons.md idea 3; brief home-cloud-ai.md section 4.2).

Each tool has an id (its name), a title, a description written for an AI model, the place
of the Fusion command it copies ("SOLID > CREATE > Extrude"), a category, the JSON Schema of
its arguments (units and defaults described), example calls, the design steps (ops) it
builds, whether it only reads or changes the design (or writes files), and what it needs
before it can run (availability() says why not, in a sentence). Everything that offers tools
reads this list: the MCP server's tools/list (mcp_core), the AI bridge and the headless
backend (sciforge/ai/executor.py), the built-in chat panel's tool definitions (chat_core),
the Claude extension's manifest (installers) and the generated documentation.

The tools are defined in the modules below, grouped like Fusion's ribbon: core_tools (the
first sixteen, whose names and argument shapes never change), sketch_tools, create_tools,
modify_tools, more_tools (surface, construct, assemble, inspect), history_tools
(timeline, parameters, files, drawings, view, help), verify_tools (the tools an agent checks
its own work with: inspect_design, query_geometry, check_design, render, diff_design) and
docs_tools (the documentation: docs_search, docs_read, examples_search). There is no tool
that runs arbitrary code. Pure Python: no FreeCAD, no Qt (the MCP server an AI app starts
imports it).
"""

import copy

from . import kit, registry
from . import core_tools  # noqa: F401  (the first sixteen first: tools/list keeps their order)
from . import sketch_tools  # noqa: F401
from . import create_tools  # noqa: F401
from . import modify_tools  # noqa: F401
from . import more_tools  # noqa: F401
from . import history_tools  # noqa: F401
from . import verify_tools  # noqa: F401  (checking: inspect_design, query_geometry, render...)
from . import docs_tools  # noqa: F401  (documentation: docs_search, docs_read, examples_search)
from .kit import (  # noqa: F401  (the shared texts, re-exported)
    BODY_PICK_HELP,
    CURVES_HELP,
    EDGE_TYPES,
    EXPRESSION_HELP,
    FACE_TYPES,
    GEOMETRY_HELP,
    MORE_GEOMETRY_HELP,
    PICK_HELP,
    SELECTOR_HELP,
    SELECTOR_KEYS,
    SKETCH_HELP,
    STEP_HELP,
    UNITS,
)

TOOLS = registry.TOOLS
TOOL_NAMES = tuple(t["name"] for t in TOOLS)
CATEGORIES = registry.CATEGORIES
NEEDS = registry.NEEDS
LEGACY_NAMES = (
    "get_design",
    "screenshot",
    "measure",
    "create_sketch",
    "extrude",
    "revolve",
    "fillet",
    "chamfer",
    "hole",
    "pattern",
    "shell",
    "set_parameter",
    "undo",
    "redo",
    "save",
    "export",
)
# Ops of the step language that are test helpers of the golden models, not things a person
# does in Fusion: no tool builds them (the unit tests check every other op has a tool).
TEST_ONLY_OPS = (
    "check",
    "reopen",
    "age",
    "measure_bodies",
    "measure_components",
    "construct_extrude",  # (create_sketch "on" + extrude does the same)
    "sf_path_sketch",  # (create_curve_sketch draws the same lines and arcs)
    "fillet",  # PartDesign's plain fillet (fillet builds SciForge's, blend_fillet)
    "chamfer",
    "revolve",  # PartDesign's plain revolve (revolve builds SciForge's, sf_revolve)
    "mirror",  # PartDesign's plain mirror (mirror builds Fusion's dialog, fusion_mirror)
)


def tool(name):
    """The tool's entry for this name, or None."""
    return registry.BY_NAME.get(name)


def is_read_only(name):
    entry = tool(name)
    return entry is not None and registry.is_read_only(entry)


def public(entry):
    """A tool as plain JSON (for `sciforge-cli tools`, the documentation, list_tools)."""
    return {
        "name": entry["name"],
        "title": entry["title"],
        "category": entry["category"],
        "ribbon": entry["ribbon"],
        "description": entry["description"],
        "input_schema": copy.deepcopy(entry["input_schema"]),
        "examples": copy.deepcopy(entry["examples"]),
        "ops": list(entry["ops"]),
        "read_only": registry.is_read_only(entry),
        "changes_design": entry["changes_design"],
        "writes_files": entry["writes_files"],
        "destructive": entry["destructive"],
        "needs": list(entry["needs"]),
        "kind": entry["kind"],
    }


def catalogue():
    """The whole catalogue as plain JSON."""
    return {
        "format": 1,
        "units": UNITS,
        "categories": [{"key": k, "title": t} for k, t in CATEGORIES],
        "tools": [public(t) for t in TOOLS],
    }


def mcp_tools():
    """The tools in MCP "tools/list" shape."""
    result = []
    for item in TOOLS:
        read_only = registry.is_read_only(item)
        result.append(
            {
                "name": item["name"],
                "title": item["title"],
                "description": item["description"],
                "inputSchema": copy.deepcopy(item["input_schema"]),
                "annotations": {
                    "title": item["title"],
                    "readOnlyHint": read_only,
                    "destructiveHint": bool(item["destructive"]),
                    "idempotentHint": read_only,
                    "openWorldHint": False,
                },
            }
        )
    return result


# After the first sixteen, the tools an AI app that takes only some tools gets first (the
# built-in chat with a provider that limits how many tools a request may carry).
CHAT_ORDER = (
    "list_tools",
    "get_help",
    "docs_search",
    "docs_read",
    "examples_search",
    "inspect_design",
    "query_geometry",
    "check_design",
    "render",
    "diff_design",
    "get_timeline",
    "get_step",
    "edit_step",
    "physical_properties",
    "get_sketch",
    "add_to_sketch",
    "set_sketch_dimension",
    "sketch_dimension",
    "sketch_constraint",
    "create_curve_sketch",
    "primitive",
    "press_pull",
    "sweep",
    "loft",
    "mirror",
    "rectangular_pattern",
    "circular_pattern",
    "draft",
    "fillet_sets",
    "move_copy",
    "combine",
    "construct_plane",
    "list_parameters",
    "set_model_parameter",
    "roll_timeline",
    "suppress_step",
    "delete_step",
    "new_design",
    "open_design",
    "save_as",
    "list_designs",
    "physical_material",
    "appearance",
    "thread",
    "emboss",
    "set_view",
)


def chat_tools(limit=None):
    """The tools for an AI provider's request; at most `limit` (OpenAI takes 128 tools, a
    small local model far fewer): the first sixteen, then CHAT_ORDER, then the rest in
    catalogue order."""
    order = list(LEGACY_NAMES) + [n for n in CHAT_ORDER if n not in LEGACY_NAMES]
    tools = [tool(n) for n in order if tool(n) is not None]
    tools += [t for t in TOOLS if t["name"] not in order]
    return tools if limit is None else tools[:limit]


# -- validation -------------------------------------------------------------------------------
def validate(tool_name, args):
    """A list of plain-sentence problems with these arguments (empty: they are fine)."""
    item = tool(tool_name)
    if item is None:
        return [
            "there is no tool called %r (call list_tools for the %d tools)"
            % (tool_name, len(TOOLS))
        ]
    if args is None:
        args = {}
    problems = []
    kit.check(item["input_schema"], args, "", problems)
    if isinstance(args, dict) and not problems:
        for key, element in item["_selectors"].items():
            if key in args:
                kit.check_selector(args[key], key, element, problems)
        kit.check_marked(item["input_schema"], args, "", problems)
        if item["_extra"] is not None:
            item["_extra"](args, problems)
    unique = []
    for problem in problems:  # (a selector checked by its schema and by a tool's rule)
        if problem not in unique:
            unique.append(problem)
    return unique


def to_steps(tool_name, args, step_id):
    """The design steps (golden step language) a valid call makes; [] for the tools the
    executor does itself. Call validate() first: this assumes the arguments are valid."""
    item = tool(tool_name)
    if item is None:
        raise ValueError("there is no tool called %r" % tool_name)
    if item["_steps"] is None:
        return []
    return item["_steps"](args or {}, step_id)


def step_title(tool_name, args):
    """The undo / timeline title of a call, e.g. "AI: Extrude 10 mm"."""
    a = args if isinstance(args, dict) else {}
    item = tool(tool_name)
    if item is None:
        return "AI: %s" % tool_name
    if item["_title"] is not None:
        try:
            return item["_title"](a)
        except Exception:
            pass
    return "AI: " + item["title"]


def availability(tool_name, state):
    """(True, "") when the tool can run now, else (False, the reason in a sentence). state:
    {"design": a design is open, "solid": it has a solid body, "gui": the SciForge window is
    there, "drawing": it has a drawing}."""
    item = tool(tool_name)
    if item is None:
        return False, "There is no tool called %r." % tool_name
    for need in item["needs"]:
        if need == "solid" and not state.get("design"):
            return False, NEEDS["design"]
        if not state.get(need):
            return False, NEEDS[need]
    return True, ""


def tool_list(state=None, category=None):
    """[{name, title, category, ribbon, read_only, available, why_not}] for list_tools."""
    rows = []
    for item in TOOLS:
        if category and item["category"] != category:
            continue
        row = {
            "name": item["name"],
            "title": item["title"],
            "category": item["category"],
            "ribbon": item["ribbon"],
            "read_only": registry.is_read_only(item),
        }
        if state is not None:
            ok, why = availability(item["name"], state)
            row["available"] = ok
            if not ok:
                row["why_not"] = why
        rows.append(row)
    return rows


# -- help -------------------------------------------------------------------------------------
OVERVIEW = (
    "SciForge is a parametric CAD program (built on FreeCAD) that works like Autodesk Fusion. "
    "These tools build and change the design open in SciForge step by step in its timeline, "
    "with the same code as SciForge's own dialogs; every change is one undo step. "
    + UNITS
    + " Faces and edges are picked with selectors that describe their geometry (get_help "
    "topic selectors), never by internal names. " + STEP_HELP + " Errors come back as plain "
    "sentences: read them, fix the arguments and try again. Read-only tools (inspect_design, "
    "query_geometry, check_design, render, diff_design, get_design, get_timeline, get_step, "
    "measure, physical_properties...) never change anything."
)
WORKFLOW = (
    "1. inspect_design (or get_design, list_designs / new_design / open_design) to see what "
    "is there. 2. Build: create_sketch on a plane, then extrude / revolve / sweep / loft; "
    "primitive, coil, pipe, gear make solids directly; hole, thread, fillet, chamfer, shell, "
    "draft change the solid. 3. After every change check the numbers it answers (volumes, "
    "bounding boxes); diff_design since last_change says exactly what it did; query_geometry "
    "lists the faces / edges a selector picks (with a stable ref for each) before you fillet "
    "or chamfer them; check_design says whether the design is sound; render returns a picture "
    "(highlight shows what a selector picks). Trust the numbers first, the picture second. "
    "4. Name things with set_parameter and expressions so the design stays easy to change; "
    "edit_step and set_model_parameter change what exists; get_timeline shows the history "
    "and roll_timeline / suppress_step / move_step / delete_step change it. 5. undo takes "
    "back the last change. 6. save / save_as / export / export_drawing write files."
)
CHECKING_HELP = (
    "Check your work with numbers before trusting a picture. inspect_design: every body "
    "(valid?, volume, area, bounding box, centre of mass, faces / edges / corners), every "
    "step (state, error message, values), parameters, components, joints, the selection; it "
    "answers a snapshot id. diff_design since that id, since last_change or since a step id: "
    "what changed (bodies, steps, parameters). query_geometry: the faces / edges / corners a "
    "selector picks with their facts (type, area / length, normal, axis, radius, centre) and "
    "a ref, a selector that picks exactly that element: give it to fillet / chamfer / shell "
    '/ draft, or pick ({"face": ref}) to measure / create_sketch. check_design: invalid '
    "or open solids, bodies in several pieces, failed steps, overlapping bodies. measure: the "
    "distance / angle between two picks, or the size of one. render: a PNG picture (iso, "
    "front, top... or a direction), highlight marks faces / edges in orange; it works "
    "without the window too (renderer software)."
)
DOCS_HELP = (
    "SciForge's documentation for AI models is searchable: docs_search finds the sections "
    "that match a few words (with a snippet and a path#anchor), docs_read reads a document or "
    "one section, examples_search finds tested recipes and golden models by words, tool, op "
    "or tag. Start with handbook.md (how SciForge works, Fusion's ideas mapped to it, "
    "coordinates, undo, checking, recovering from failures), selectors.md (the selector "
    "cookbook) and recipes/index.md (step-by-step parts); reference/<tool>.md has every "
    "argument of a tool with a real example; user/ has SciForge's documentation for people. "
    "Over MCP the same documents are resources sciforge://docs/<path>, and "
    "sciforge://handbook is all of them in one file."
)
HELP = {
    "overview": OVERVIEW,
    "selectors": SELECTOR_HELP,
    "picks": PICK_HELP,
    "body_picks": BODY_PICK_HELP,
    "sketches": SKETCH_HELP,
    "geometry": GEOMETRY_HELP + " " + MORE_GEOMETRY_HELP,
    "curves": CURVES_HELP,
    "steps": STEP_HELP,
    "expressions": EXPRESSION_HELP
    + " User parameters are made with set_parameter; formulas use their names with + - * / "
    "( ) and mm / deg units.",
    "workflow": WORKFLOW,
    "checking": CHECKING_HELP,
    "docs": DOCS_HELP,
}


def help_text(topic="overview"):
    """The text of one help topic (get_help)."""
    if topic == "tools":
        lines = []
        for key, title in CATEGORIES:
            items = [t for t in TOOLS if t["category"] == key]
            if not items:
                continue
            lines.append("%s:" % title)
            for t in items:
                lines.append(
                    "  %s - %s (%s)%s"
                    % (
                        t["name"],
                        t["title"],
                        t["ribbon"],
                        "" if t["changes_design"] or t["writes_files"] else " [read-only]",
                    )
                )
        return "\n".join(lines)
    return HELP.get(topic, HELP["overview"])


INSTRUCTIONS = (
    OVERVIEW
    + " Workflow: "
    + WORKFLOW
    + " Selectors: "
    + SELECTOR_HELP.replace("\n", " ")
    + " Picks: "
    + PICK_HELP
    + " Sketches: "
    + SKETCH_HELP
    + " Curves: "
    + CURVES_HELP
    + " Checking: "
    + CHECKING_HELP
    + " Documentation: "
    + DOCS_HELP
)
