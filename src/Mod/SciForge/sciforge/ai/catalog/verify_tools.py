# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools that let an agent check its own work with numbers before it trusts a picture
(docs/sciforge/dev/cadcraft-lessons.md idea 3, "checking tools"): inspect_design (every body,
step, parameter, component and the selection at once), query_geometry (the faces, edges or
corners a selector picks, with facts and a stable reference for each), check_design (is the
design sound: valid solids, failed steps, overlapping bodies), render (a picture returned
as an image, also without the window) and diff_design (what changed since a snapshot, the
last change or a step). Fusion shows the same facts in its browser, timeline, Measure,
Properties and Interference; here they come back as JSON. Pure Python (the work is in
sciforge/ai/actions/verify_actions.py)."""

from . import kit
from .kit import boolean, enum, integer, obj, schema, selector, step_id, step_ids, string
from .registry import define, example

VIEWS = ("iso", "front", "back", "top", "bottom", "left", "right")
ELEMENTS = ("faces", "edges", "vertices")

define(
    "inspect_design",
    "Inspect design",
    "inspect",
    "BROWSER + TIMELINE + Properties (everything at once)",
    "Read the whole design as numbers, to check work before trusting a picture: every body "
    "(valid solid or not, volume mm3, area mm2, bounding box and size mm, centre of mass, "
    "number of solids, faces, edges and corners, material and mass, shown or hidden); every "
    "timeline step in order (id, name, kind, body, done or rolled back, suppressed, status "
    "and the error message when it failed, its main values; detail full adds every option as "
    "get_step shows them); user parameters; components and joints; construction geometry; "
    "sketches (closed areas, fully constrained); drawings; and what is selected in SciForge "
    "(window only). The answer has a snapshot id: diff_design since it shows what changed "
    "later. bodies: only these (step ids).",
    schema(
        {
            "detail": enum(
                ("summary", "full"), "full adds every step's definition", default="summary"
            ),
            "bodies": step_ids("only these bodies (default: all)"),
        }
    ),
    changes=False,
    needs=(),
    examples=[
        example({}, "everything about the open design, with a snapshot id"),
        example({"detail": "full"}, "also every step's options"),
    ],
)


def _extra_query(args, problems):
    element = args.get("element", "faces")
    spec = args.get("select")
    if spec is None:
        return
    if element == "vertices":
        if not isinstance(spec, dict):
            problems.append("select must be a selector object")
            return
        extra = set(spec) - {"at", "all", "count"}
        if extra:
            problems.append(
                "select for vertices takes only at, all and count (not %s)"
                % ", ".join(sorted(extra))
            )
        if "at" in spec:
            kit.check_at(spec["at"], "select", problems)
    else:
        kit.check_selector(spec, "select", element, problems)


define(
    "query_geometry",
    "Query geometry",
    "inspect",
    "Selection filters + INSPECT > Measure (on what a selector picks)",
    "List the faces, edges or corners (vertices) of a body or step that a selector picks, with "
    "facts about each: type (plane, cylinder... / line, circle...), area mm2 or length mm, "
    "centre, normal of flat faces, axis and radius of round ones, start / end and direction "
    "of edges, bounding box. Each comes with ref: a selector that picks exactly that one "
    "element by its geometry (stable when FreeCAD renumbers faces), and pick: the same ready "
    "for measure, create_sketch face, construct_plane... Pass ref straight to fillet, chamfer, "
    "shell, draft (edges / faces) to change exactly that element. of: a body or step id "
    "(default the body being worked on; a step: the solid as it was after that step). "
    "element: faces (default), edges or vertices. select: a selector (default all; for "
    "vertices only at / all / count). limit: at most this many (default 60).",
    schema(
        {
            "of": step_id("the body or step (default: the body being worked on)"),
            "element": enum(ELEMENTS, default="faces"),
            "select": {
                "type": "object",
                "description": "a selector (see get_help topic selectors); vertices take only "
                "at / all / count. Default: all",
            },
            "limit": integer("at most this many elements", default=60, minimum=1, maximum=500),
            "refs": boolean("give each element its stable reference", default=True),
        }
    ),
    changes=False,
    needs=("design",),
    extra=_extra_query,
    examples=[
        example({"select": {"type": "cylinder"}}, "every round face: the holes and bosses"),
        example(
            {"element": "edges", "select": {"at": {"axis": "z", "value": "max"}}},
            "the edges at the top, each with a selector fillet can take",
        ),
        example({"of": "Extrude1", "element": "vertices"}, "the corners after Extrude1"),
    ],
)
define(
    "check_design",
    "Check design",
    "inspect",
    "INSPECT > Interference + the timeline's warnings",
    "Check that the design is sound, before saving or exporting it: every body is one valid, "
    "closed solid (invalid or open shapes, bodies made of several pieces, empty bodies), "
    "timeline steps that failed or warn (with the reason), steps left after the history "
    "marker, suppressed steps, sketches with conflicting constraints, and bodies that overlap "
    "(Fusion's Interference; interference: false skips it, it takes longest). Answers ok "
    "(true when there are no problems), the problems and warnings in plain sentences, and "
    "the facts behind them. bodies: only these (step ids).",
    schema(
        {
            "interference": boolean("look for bodies that overlap", default=True),
            "bodies": step_ids("only these bodies (default: all)"),
        }
    ),
    changes=False,
    needs=("design",),
    examples=[example({}, "is everything valid and nothing broken or overlapping?")],
)


def _extra_render(args, problems):
    if "view" in args and "direction" in args:
        problems.append("give view or direction, not both")
    high = args.get("highlight")
    if isinstance(high, dict):
        if "faces" not in high and "edges" not in high:
            problems.append("highlight needs faces and / or edges (selectors)")


define(
    "render",
    "Render",
    "view",
    "File > Capture Image (returned to the AI as a picture)",
    "Take a picture of the design and get the image itself (PNG), to look at what was "
    "built. view: iso (default: from front, right and top, as Fusion's Home view), front, "
    "back, top, bottom, left or right; or direction [x, y, z]: where the camera looks from. "
    "fit (default true) frames the whole design. highlight: {faces: selector, edges: "
    "selector, of: step id} marks those faces / edges in orange (check what a selector "
    "picks before using it). renderer: window (SciForge's own 3D view, as the person sees "
    "it), software (a simple picture of the solids drawn by SciForge itself: works without "
    "the window), auto (default: the window when there is one). Numbers from "
    "inspect_design / query_geometry are more exact than a picture: use both.",
    schema(
        {
            "view": enum(VIEWS, default="iso"),
            "direction": dict(kit.vector3("where the camera looks from")),
            "width": integer("picture width in pixels", default=800, minimum=64, maximum=2048),
            "height": integer("picture height in pixels", default=600, minimum=64, maximum=2048),
            "fit": boolean("frame the whole design", default=True),
            "highlight": obj(
                {
                    "faces": selector("the faces to mark", "faces"),
                    "edges": selector("the edges to mark", "edges"),
                    "of": step_id("the body or step they belong to (default: the body worked on)"),
                },
                description="faces / edges to mark in orange",
            ),
            "edges": boolean("draw the edges (software renderer)", default=True),
            "renderer": enum(("auto", "window", "software"), default="auto"),
        }
    ),
    changes=False,
    needs=("design",),
    extra=_extra_render,
    examples=[
        example({}, "an iso picture of the whole design, 800 x 600"),
        example(
            {"view": "top", "highlight": {"faces": {"type": "cylinder"}}},
            "from the top, the round faces (holes) in orange",
        ),
        example({"renderer": "software", "width": 400, "height": 300}, "a quick small picture"),
    ],
)
define(
    "diff_design",
    "Diff design",
    "inspect",
    "TIMELINE (compare before and after)",
    "What changed in the design since: a snapshot id that inspect_design answered (\"S3\"), "
    '"last_change" (just before the latest change an AI made: what that change did), or a '
    "step id (the solid as it was right after that step, compared with now: what the later "
    "steps did). Answers the bodies added, removed and changed (volume, area, size, faces, "
    "edges before and after), the timeline steps added, removed or changed (values, state, "
    "status) and the parameters changed.",
    schema(
        {"since": string('a snapshot id ("S1"), "last_change" or a step id')},
        ["since"],
    ),
    changes=False,
    needs=("design",),
    examples=[
        example({"since": "last_change"}, "what the last change did"),
        example({"since": "S1"}, "everything that changed since inspect_design gave S1"),
        example({"since": "Extrude1"}, "what the steps after Extrude1 did to the solid"),
    ],
)
