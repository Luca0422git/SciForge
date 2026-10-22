# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI tools for the timeline (history), parameters, design files, import, drawings, the view
and help. Pure Python (the work is in sciforge/ai/actions)."""

from . import kit
from .kit import (
    array,
    boolean,
    enum,
    integer,
    number,
    obj,
    positive,
    schema,
    step_id,
    step_ids,
    string,
)
from .registry import define, example

# -- TIMELINE -----------------------------------------------------------------------------------
define(
    "get_timeline",
    "Get timeline",
    "timeline",
    "TIMELINE (the bar at the bottom)",
    "List the timeline in order: every step with its id, its name as the timeline shows it "
    '("Extrude 2"), its kind, the body / component it belongs to, whether it is before the '
    "history marker (done) or after it (rolled_back), suppressed, its status (ok, warning, "
    "error, with the reason in plain words) and its main values (distance, radius, "
    "quantity...); plus where the history marker stands.",
    schema({}),
    changes=False,
    examples=[example({}, "the steps, their state and the marker")],
)
define(
    "get_step",
    "Get step",
    "timeline",
    "TIMELINE > double-click a step (the dialog's fields)",
    "Read one step's definition, the way its dialog shows it when you double-click it: its "
    "kind and every option (distances, angles, operation, what it is built on), the "
    "formulas that drive values, its status and what it uses. The names of the options are "
    "the ones edit_step takes.",
    schema({"step": step_id("the step")}, ["step"]),
    changes=False,
    examples=[example({"step": "Extrude1"}, "Extrude1's options")],
)


def _extra_edit_step(args, problems):
    if not args.get("set") and not args.get("add_edges") and not args.get("add_faces"):
        problems.append("give set (the options to change) or add_edges / add_faces (fillets)")
    for key, element in (("add_edges", "edges"), ("add_faces", "faces")):
        if key in args:
            kit.check_selector(args[key], key, element, problems)


define(
    "edit_step",
    "Edit step",
    "timeline",
    "TIMELINE > double-click a step > change its fields > OK",
    "Change an existing step's options, as double-clicking it in the timeline: set {option: "
    "value} with the names get_step shows (extrude: distance, distance2, taper, direction, "
    "operation, through_all...; revolve: angle, type, direction, operation; fillet / chamfer: "
    "radius, distance...; hole: diameter, depth, extent, hole_type...; patterns: quantity, "
    "distance, angle...; shell, draft, scale, sweep, loft, rib, primitives, coil, pipe, gear, "
    "hardware, emboss, thread, surface, combine, split, move, align, construction planes...). "
    "A fillet or chamfer also takes add_edges / add_faces (more edges). The steps after it "
    "update and keep their faces and edges; steps that break are named in the answer. An "
    "option name the step does not have is refused with the names it has (get_step's values "
    "spellings, like Radius, are taken too; a shell takes thickness); an edit that changes "
    "nothing says so and adds no Undo step. An extrude's distance keeps the side it goes "
    "to: flip: true reverses it.",
    schema(
        {
            "step": step_id("the step to change"),
            "set": kit.free_object("{option: value}"),
            "add_edges": kit.selector("fillet / chamfer: more edges", "edges"),
            "add_faces": kit.selector("fillet / chamfer: every edge around more faces"),
        },
        ["step"],
    ),
    extra=_extra_edit_step,
    own_id=False,
    ops=[
        "edit",
        "sf_revolve_edit",
        "pattern_edit",
        "sf_shell_edit",
        "sf_draft_edit",
        "sf_draft2_edit",
        "sf_scale_edit",
        "sf_scale_sketch_edit",
        "body_tool_edit",
        "blend_edit",
        "sf_primitive_edit",
        "sf_sweep_edit",
        "sf_loft_edit",
        "sf_rib_edit",
        "sf_surface_edit",
        "modify_edit",
        "move_face_edit",
        "sf_gear_edit",
        "sf_hardware_edit",
    ],
    title_fn=lambda a: "AI: Edit %s" % a.get("step", "step"),
    examples=[
        example({"step": "Extrude1", "set": {"distance": 15}}, "make the extrude 15 mm"),
        example({"step": "Fillet1", "set": {"radius": 2}}, "change the fillet to 2 mm"),
    ],
)


def _extra_roll(args, problems):
    kit.exactly_one(args, ("to", "after", "before"), problems, "where the marker goes")


define(
    "roll_timeline",
    "Move history marker",
    "timeline",
    "TIMELINE > drag the history marker (and the playback buttons)",
    "Move the timeline's history marker: to start (an empty design), end, previous / next "
    "(one step), or after / before a step. Steps after the marker are rolled back (not "
    "computed); a new feature goes in at the marker, as in Fusion. Move it back to the end "
    "when you are done.",
    schema(
        {
            "to": enum(["start", "end", "previous", "next"]),
            "after": step_id("put the marker right after this step"),
            "before": step_id("put the marker right before this step"),
        },
    ),
    ops=["roll"],
    extra=_extra_roll,
    own_id=False,
    title_fn=lambda a: "AI: Roll history marker",
    examples=[
        example({"after": "Extrude1"}, "roll back to just after Extrude1"),
        example({"to": "end"}, "roll forward to the end"),
    ],
)
define(
    "suppress_step",
    "Suppress / unsuppress",
    "timeline",
    "TIMELINE > right-click a step > Suppress Features",
    "Suppress steps (they stay in the timeline but are skipped, as if they were not there) "
    "or bring them back (suppress: false). Steps that depend on them are suppressed with "
    "them; the answer names them.",
    schema({"steps": step_ids("the steps"), "suppress": boolean(default=True)}, ["steps"]),
    ops=["suppress", "unsuppress"],
    own_id=False,
    title_fn=lambda a: "AI: %s" % ("Suppress" if a.get("suppress", True) else "Unsuppress"),
    examples=[example({"steps": ["Fillet1"]}, "try the part without the fillet")],
)
define(
    "delete_step",
    "Delete step",
    "timeline",
    "TIMELINE > right-click a step > Delete",
    "Delete steps from the timeline (Fusion asks the same: steps that depend on them may "
    "break and are named in the answer). Undo brings them back.",
    schema({"steps": step_ids("the steps")}, ["steps"]),
    ops=["delete"],
    own_id=False,
    destructive=True,
    title_fn=lambda a: "AI: Delete steps",
    examples=[example({"steps": ["Chamfer1"]}, "delete the chamfer")],
)


def _extra_move_step(args, problems):
    kit.exactly_one(args, ("before", "after"), problems)


define(
    "move_step",
    "Reorder step",
    "timeline",
    "TIMELINE > drag a step",
    "Move a step before or after another one in the timeline. A step can never move before "
    "what it is built on: the refusal says why.",
    schema({"step": step_id("the step"), "before": step_id(), "after": step_id()}, ["step"]),
    ops=["move"],
    extra=_extra_move_step,
    own_id=False,
    title_fn=lambda a: "AI: Move %s" % a.get("step", "step"),
    examples=[example({"step": "Fillet1", "after": "Extrude2"}, "fillet after the boss")],
)
define(
    "rename",
    "Rename",
    "timeline",
    "TIMELINE / BROWSER > right-click > Rename",
    "Rename a timeline step, a body, a component, a sketch or a drawing (what the timeline "
    "and browser show). The id stays the same.",
    schema(
        {"target": step_id("the thing to rename"), "name": string("the new name")},
        ["target", "name"],
    ),
    own_id=False,
    title_fn=lambda a: "AI: Rename %s" % a.get("target", ""),
    examples=[example({"target": "Extrude1", "name": "Base plate"}, "name the first extrude")],
)


def _extra_group(args, problems):
    if args.get("ungroup"):
        if "group" not in args:
            problems.append("ungroup needs group (the group's id from get_timeline)")
    elif len(args.get("steps") or []) < 2:
        problems.append("a group needs at least 2 steps next to each other")


define(
    "group_steps",
    "Group steps",
    "timeline",
    "TIMELINE > select steps > right-click > Group",
    "Group neighbouring timeline steps under one name (Fusion's timeline groups), or "
    "ungroup (ungroup: true with the group's id).",
    schema(
        {
            "steps": step_ids("the steps (next to each other)", 2),
            "name": string("the group's name"),
            "ungroup": boolean(default=False),
            "group": string("ungroup: the group's id (get_timeline)"),
        },
    ),
    extra=_extra_group,
    own_id=False,
    title_fn=lambda a: "AI: %s" % ("Ungroup" if a.get("ungroup") else "Group steps"),
    examples=[example({"steps": ["Sketch2", "Extrude2"], "name": "Boss"}, "group the boss")],
)

# -- PARAMETERS ---------------------------------------------------------------------------------
define(
    "list_parameters",
    "List parameters",
    "parameters",
    "MODIFY > Change Parameters",
    "List the design's parameters, as Change Parameters shows them: user parameters (name, "
    "unit, formula, value, comment), parameters brought in by a Derive (read-only), and "
    "model parameters: every dimension in the design (each step's values and each sketch "
    "dimension: the step id, its label, value, unit and formula).",
    schema({"model": boolean("include the model parameters", default=True)}),
    changes=False,
    examples=[example({}, "every parameter and dimension")],
)
define(
    "delete_parameter",
    "Delete parameter",
    "parameters",
    "MODIFY > Change Parameters > a user parameter > Delete",
    "Delete a user parameter. Refused, with the names, while formulas still use it.",
    schema({"name": string("the parameter")}, ["name"]),
    own_id=False,
    destructive=True,
    title_fn=lambda a: "AI: Delete parameter %s" % a.get("name", ""),
    examples=[example({"name": "gap"}, "delete the unused parameter gap")],
)


def _extra_model_parameter(args, problems):
    if ("value" in args) == ("expression" in args):
        problems.append("give value or expression, one of them")


define(
    "set_model_parameter",
    "Set model parameter",
    "parameters",
    "MODIFY > Change Parameters > Model Parameters",
    "Change a model parameter: one value of a step (label as list_parameters shows it: "
    '"Distance", "Radius", "Set 1 Size", "Quantity"...) or a sketch dimension (its '
    "name or label). value (mm / degrees / a count) or expression (a formula with user "
    "parameters, kept as a link). Everything after it updates.",
    schema(
        {
            "step": step_id("the step or sketch"),
            "label": string("which of its values (from list_parameters)"),
            "value": number(),
            "expression": string("a formula"),
        },
        ["step", "label"],
    ),
    extra=_extra_model_parameter,
    own_id=False,
    title_fn=lambda a: "AI: %s %s" % (a.get("step", ""), a.get("label", "")),
    examples=[
        example(
            {"step": "Extrude1", "label": "Distance", "expression": "height"},
            "Extrude1's distance follows the parameter height",
        )
    ],
)

# -- DESIGNS AND FILES --------------------------------------------------------------------------
define(
    "new_design",
    "New design",
    "document",
    "File > New Design",
    "Start a new, empty design (with one body) and make it the active one. name: its name.",
    schema({"name": string("the design's name", default="Untitled")}),
    needs=(),
    title_fn=lambda a: "AI: New design",
    examples=[example({"name": "Bracket"}, "a new design called Bracket")],
)


def _extra_open(args, problems):
    path = args.get("path")
    if isinstance(path, str) and not path.lower().endswith(
        (".fcstd", ".step", ".stp", ".igs", ".iges")
    ):
        problems.append("path must be a design (.FCStd) or a STEP / IGES file")


define(
    "open_design",
    "Open design",
    "document",
    "File > Open",
    "Open a design (.FCStd) or a STEP / IGES file as a new design (its components and bodies "
    "kept). A design that is already open comes to the front. It becomes the active design. "
    "For a STEP / IGES file the answer also lists what the file had that did not come in or "
    'came in changed ("Not brought in, or changed:" and one line each: loose faces, '
    "curves and points, surface bodies, bodies with geometry errors).",
    schema({"path": string("full path of the file")}, ["path"]),
    needs=(),
    changes=False,
    extra=_extra_open,
    examples=[example({"path": "/home/me/designs/bracket.FCStd"}, "open a saved design")],
)
define(
    "save_as",
    "Save as",
    "document",
    "File > Save As",
    "Save the design under a new name (a full path ending in .FCStd); the design then lives "
    "there. Replacing another existing file must be confirmed by the person in SciForge.",
    schema({"path": string("full path ending in .FCStd")}, ["path"]),
    changes=False,
    writes_files=True,
    confirm_overwrite=True,
    extra=lambda a, p: (
        None
        if str(a.get("path", "")).lower().endswith(".fcstd")
        else p.append("path must end in .FCStd")
    ),
    examples=[example({"path": "/home/me/designs/bracket-v2.FCStd"}, "a copy under a new name")],
)


def _extra_close(args, problems):
    if "design" in args and not isinstance(args["design"], str):
        problems.append("design must be a design's name")


define(
    "close_design",
    "Close design",
    "document",
    "File > Close",
    "Close a design (default: the active one). Unsaved changes are refused unless "
    "discard_changes is true (the person in SciForge is asked first). A design text that "
    "fits several open designs (one's id is another's name) is refused with their ids. "
    "Another open design becomes the active one.",
    schema(
        {
            "design": string("the design's id or name (list_designs)"),
            "discard_changes": boolean("close even with unsaved changes", default=False),
        }
    ),
    destructive=True,
    own_id=False,
    needs=(),  # (design names one: no active design needed)
    title_fn=lambda a: "AI: Close design",
    extra=_extra_close,
    examples=[example({}, "close the active design (it must be saved)")],
)
define(
    "list_designs",
    "List designs",
    "document",
    "the design tabs",
    "List the open designs: name, label, file, whether it has unsaved changes and which one "
    "is active.",
    schema({}),
    changes=False,
    needs=(),
    examples=[example({}, "which designs are open")],
)
define(
    "switch_design",
    "Switch design",
    "document",
    "click a design tab",
    "Make another open design the active one (the tools then work on it). A text that fits "
    "several open designs (one's id is another's name) is refused with their ids.",
    schema({"design": string("its id or name (list_designs)")}, ["design"]),
    changes=False,
    needs=(),
    examples=[example({"design": "Bracket"}, "work on Bracket")],
)


def _extra_import(args, problems):
    path = args.get("path")
    if isinstance(path, str) and not path.lower().endswith(
        (".step", ".stp", ".igs", ".iges", ".stl", ".obj", ".3mf", ".dxf", ".fcstd")
    ):
        problems.append("path must be STEP, IGES, STL, OBJ, 3MF, DXF or FCStd")
    if "sketch_plane" in args and not str(path).lower().endswith(".dxf"):
        problems.append("sketch_plane is only used for DXF files")


define(
    "import_file",
    "Insert file",
    "import_export",
    "INSERT > Insert Mesh / Insert DXF / Insert STEP, and Insert into Current Design",
    "Bring a file into the active design: STEP / IGES (one component with the file's "
    "structure, its bodies and colours), STL / OBJ / 3MF (a mesh body; unit: the file's "
    "unit), DXF (its curves into a new sketch on sketch_plane XY | XZ | YZ, ready to "
    "extrude), FCStd (another design's bodies as a component). label names what is made. "
    "The answer also lists what the file had that did not come in or came in changed "
    '("Not brought in, or changed:" and one line each, as INSERT\'s message says: an '
    "open mesh, a 3MF's unit or colours, DXF texts, hatches and points, loose faces of a "
    "STEP...); a mesh whose file says another unit can be inserted again with unit.",
    schema(
        {
            "path": string("full path of the file"),
            "unit": enum(
                ["mm", "cm", "m", "in", "ft"], "mesh / DXF files: the file's unit", default="mm"
            ),
            "sketch_plane": enum(["XY", "XZ", "YZ"], "DXF: the plane", default="XY"),
            "label": string("the name of what is made"),
        },
        ["path"],
    ),
    extra=_extra_import,
    needs=(),
    id_base="Insert",
    title_fn=lambda a: "AI: Insert %s" % str(a.get("path", "")).replace("\\", "/").split("/")[-1],
    examples=[
        example({"path": "/home/me/parts/motor.step"}, "a motor model as a component"),
        example({"path": "/home/me/logo.dxf", "sketch_plane": "XY"}, "a DXF outline as a sketch"),
    ],
)

# -- DRAWINGS -----------------------------------------------------------------------------------
ORIENTATIONS = ("Front", "Back", "Top", "Bottom", "Left", "Right", "Home")
PROJECTED = (
    "Top",
    "Bottom",
    "Left",
    "Right",
    "FrontTopRight",
    "FrontTopLeft",
    "FrontBottomRight",
    "FrontBottomLeft",
)
STYLES = ("Visible Edges", "Visible and Hidden Edges", "Shaded", "Shaded with Hidden Edges")
define(
    "create_drawing",
    "Create drawing",
    "drawing",
    "File > New Drawing > From Design",
    "Make a 2D drawing of the design (Fusion's New Drawing From Design), kept in the design "
    "and updated with it: bodies (step ids, default every visible body), standard ISO | ASME, "
    "sheet (A4..A0 for ISO, A..E for ASME), units mm | in, title_block; a base view "
    "(base_view orientation Front, Back, Top, Bottom, Left, Right or Home (isometric), at "
    "[x, y] on the sheet in mm from the bottom left, scale, style) and projected views "
    "(projected: Top, Right, FrontTopRight... placed next to it). Answers the drawing's and "
    "views' ids.",
    schema(
        {
            "bodies": step_ids("the bodies to draw (default: every visible body)"),
            "standard": enum(["ISO", "ASME"], default="ISO"),
            "sheet": string("A4, A3, A2, A1, A0 (ISO) or A, B, C, D, E (ASME)"),
            "units": enum(["mm", "in"], default="mm"),
            "title_block": boolean(default=True),
            "label": string("the drawing's name"),
            "base_view": enum(ORIENTATIONS, "the base view's orientation", default="Front"),
            "at": kit.numbers(2, "[x, y] of the base view on the sheet (mm)"),
            "scale": positive("view scale (default: fits the sheet)"),
            "style": enum(STYLES, default="Visible and Hidden Edges"),
            "projected": array(enum(PROJECTED), "projected views to add"),
        },
    ),
    needs=("solid",),
    id_base="Drawing",
    title_fn=lambda a: "AI: New drawing",
    examples=[
        example(
            {"base_view": "Front", "projected": ["Top", "Right", "FrontTopRight"]},
            "the classic three views plus an isometric",
        )
    ],
)


def _extra_drawing_view(args, problems):
    kind = args.get("kind")
    if kind == "projected" and ("parent" not in args or "direction" not in args):
        problems.append("a projected view needs parent (a view id) and direction")
    if kind == "section" and ("parent" not in args or "line" not in args):
        problems.append("a section view needs parent and line [[x1, y1], [x2, y2]]")
    if kind == "detail" and ("parent" not in args or "center" not in args or "radius" not in args):
        problems.append("a detail view needs parent, center and radius")
    if kind == "base" and "orientation" not in args:
        problems.append("a base view needs orientation")


define(
    "add_drawing_view",
    "Add drawing view",
    "drawing",
    "DRAWING > CREATE > Base View / Projected View / Section View / Detail View",
    "Add a view to a drawing: kind base (orientation, at, scale, style), projected (parent "
    "view id, direction Top / Right / ... / FrontTopRight), section (parent, line [[x1, y1], "
    "[x2, y2]] in the parent view's own mm from its centre, side 1 | -1) or detail (parent, "
    "center [x, y] in the parent's mm, radius, scale). at: where on the sheet [x, y] mm.",
    schema(
        {
            "drawing": step_id("the drawing (default: the newest)"),
            "kind": enum(["base", "projected", "section", "detail"]),
            "parent": step_id("the view it is made from"),
            "orientation": enum(ORIENTATIONS),
            "direction": enum(PROJECTED),
            "line": array(kit.numbers(2), "section line [[x1, y1], [x2, y2]]", 2, 2),
            "side": integer(
                "section: 1 looks from the left of the line's direction, -1 "
                "from the right (default: from where the view is placed)"
            ),
            "center": kit.numbers(2, "detail centre [x, y]"),
            "radius": positive("detail circle radius (mm)"),
            "at": kit.numbers(2, "[x, y] on the sheet (mm)"),
            "scale": positive(),
            "style": enum(STYLES),
            "label": string("section / detail letter"),
        },
        ["kind"],
    ),
    extra=_extra_drawing_view,
    needs=("drawing",),
    id_base="View",
    title_fn=lambda a: "AI: %s view" % str(a.get("kind", "")).capitalize(),
    examples=[
        example(
            {"kind": "section", "parent": "BaseView", "line": [[-50, 0], [50, 0]]},
            "a section through the middle of the base view",
        )
    ],
)


def _extra_dimension(args, problems):
    picks = args.get("picks") or []
    if not 1 <= len(picks) <= 2:
        problems.append("picks takes one or two elements of the view")
    for i, item in enumerate(picks):
        if isinstance(item, dict) and not ({"near", "kind"} & set(item)):
            problems.append("picks[%d] needs near (a point) and / or kind" % i)


define(
    "add_drawing_dimension",
    "Add drawing dimension",
    "drawing",
    "DRAWING > DIMENSIONS > Dimension",
    "Dimension a drawing view, as Fusion's Dimension command does from what is clicked: one "
    "line (its length, horizontal / vertical / aligned), one circle (diameter) or arc "
    "(radius), two points / lines (the distance or angle between them). picks: the view's "
    "elements, each {kind: line | circle | arc | vertex, near: [x, y] in the view's own mm "
    "from its centre (get_drawing lists the elements), radius}; type forces a kind of "
    "dimension (linear, aligned, radius, diameter, angular); at: where the text goes on the "
    "sheet [x, y] mm. Answers the measured value.",
    schema(
        {
            "view": step_id("the view"),
            "picks": array(
                obj(
                    {
                        "kind": enum(["line", "circle", "arc", "vertex"]),
                        "near": kit.numbers(2, "[x, y] in the view (mm)"),
                        "radius": positive("circles / arcs: the radius"),
                    }
                ),
                "one or two elements",
                1,
                2,
            ),
            "type": enum(["linear", "aligned", "radius", "diameter", "angular"]),
            "at": kit.numbers(2, "text position on the sheet (mm)"),
        },
        ["view", "picks"],
    ),
    extra=_extra_dimension,
    needs=("drawing",),
    id_base="Dimension",
    title_fn=lambda a: "AI: Drawing dimension",
    examples=[
        example(
            {"view": "BaseView", "picks": [{"kind": "circle", "radius": 3}]},
            "the diameter of the 6 mm hole",
        )
    ],
)


def _extra_annotation(args, problems):
    kind = args.get("kind")
    if kind == "text" and not args.get("text"):
        problems.append("text needs text")
    if kind in ("parts_list", "center_marks") and "view" not in args:
        problems.append("%s needs view" % kind)


define(
    "add_drawing_annotation",
    "Add drawing annotation",
    "drawing",
    "DRAWING > TEXT / TABLES / SYMBOLS (Text, Table (parts list), Center Mark)",
    "Add to a drawing: kind text (text lines at [x, y], size mm), parts_list (a table of the "
    "view's components with balloons, at = its top-left corner) or center_marks (a centre "
    "mark on every circle of a view).",
    schema(
        {
            "drawing": step_id("the drawing (default: the newest)"),
            "kind": enum(["text", "parts_list", "center_marks"]),
            "text": string("text (new lines split it)"),
            "size": positive("text height (mm)", default=3.5),
            "view": step_id("parts list / centre marks: the view"),
            "at": kit.numbers(2, "[x, y] on the sheet (mm)"),
            "balloons": boolean("parts list: balloons on the view", default=True),
        },
        ["kind"],
    ),
    extra=_extra_annotation,
    needs=("drawing",),
    id_base="Annotation",
    title_fn=lambda a: "AI: Drawing %s" % str(a.get("kind", "")).replace("_", " "),
    examples=[
        example(
            {"kind": "text", "text": "Break all sharp edges", "at": [20, 40]}, "a note on the sheet"
        )
    ],
)
define(
    "get_drawing",
    "Get drawing",
    "drawing",
    "BROWSER > Drawings",
    "Describe drawings: each drawing's id, sheet, standard, units, title block values and "
    "views (id, kind, orientation, scale, position on the sheet, size) with their dimensions "
    "(value) and, with edges true, each view's elements (lines with ends, circles with "
    "centre and radius, in the view's own mm from its centre) for add_drawing_dimension.",
    schema(
        {
            "drawing": step_id("one drawing (default: all)"),
            "edges": boolean("list each view's lines and circles", default=False),
        }
    ),
    changes=False,
    needs=("drawing",),
    examples=[example({"edges": True}, "views and their lines and circles")],
)


def _extra_export_drawing(args, problems):
    path, fmt = str(args.get("path", "")), args.get("format")
    if fmt and not path.lower().endswith("." + fmt):
        problems.append("path must end in .%s for format %s" % (fmt, fmt))


define(
    "export_drawing",
    "Export drawing",
    "drawing",
    "DRAWING > EXPORT > Output PDF / Output DXF",
    "Export a drawing: format pdf (every sheet in one PDF; needs the SciForge window) or dxf "
    "(the sheet: frame, views on their own layers, dimensions, text). Replacing an existing "
    "file must be confirmed by the person in SciForge. The answer lists what the file does "
    'not keep ("Not kept in this file:": other sheets, dimensions written as plain lines '
    "and text, hatching as lines, the font...), as the drawing's Export message does.",
    schema(
        {
            "drawing": step_id("the drawing (default: the newest)"),
            "format": enum(["pdf", "dxf"]),
            "path": string("full path"),
        },
        ["format", "path"],
    ),
    changes=False,
    writes_files=True,
    confirm_overwrite=True,
    extra=_extra_export_drawing,
    needs=("drawing",),
    examples=[example({"format": "pdf", "path": "/home/me/bracket.pdf"}, "a PDF of the drawing")],
)

# -- VIEW ---------------------------------------------------------------------------------------
define(
    "set_view",
    "Set view",
    "view",
    "NAVIGATION BAR and VIEWCUBE (Home, Fit, Orbit, Look At)",
    "Turn the 3D view: orientation iso | home | front | back | top | bottom | left | right, "
    "fit (zoom so everything shows, default true), projection perspective | orthographic, "
    "or camera (a camera string get_view returned), or look_at: a face selector (the view "
    "looks straight at that face, Fusion's Look At).",
    schema(
        {
            "orientation": enum(["iso", "home", "front", "back", "top", "bottom", "left", "right"]),
            "fit": boolean(default=True),
            "projection": enum(["perspective", "orthographic"]),
            "camera": string("a camera description from get_view"),
            "look_at": kit.selector("look straight at this face"),
        },
    ),
    changes=False,
    needs=("design", "gui"),
    examples=[example({"orientation": "top"}, "look from the top, fitted")],
)
define(
    "get_view",
    "Get view",
    "view",
    "(the 3D view's camera)",
    "The 3D view's camera now (a string set_view takes back), its projection, and the saved "
    "named views of the design.",
    schema({}),
    changes=False,
    needs=("design", "gui"),
    examples=[example({}, "the camera and the named views")],
)


def _extra_named_view(args, problems):
    if args.get("action") in ("save", "go", "delete") and not args.get("name"):
        problems.append("%s needs name" % args.get("action"))


define(
    "named_view",
    "Named view",
    "view",
    "BROWSER > Named Views (New Named View, go to, delete)",
    "Named views kept in the design (Fusion's Named Views): action save (the current camera "
    "under name), go (turn the view to it), delete, list.",
    schema(
        {
            "action": enum(["save", "go", "delete", "list"]),
            "name": string("the view's name"),
        },
        ["action"],
    ),
    extra=_extra_named_view,
    own_id=False,
    title_fn=lambda a: "AI: Named view %s" % a.get("name", ""),
    examples=[example({"action": "save", "name": "Assembly view"}, "remember this camera")],
)
define(
    "show_hide",
    "Show / hide",
    "view",
    "BROWSER > the eye icon (Show / Hide)",
    "Show or hide bodies, components, sketches, construction geometry or drawings in the 3D "
    "view (they stay in the design). targets: ids; visible: true shows, false hides. Not an "
    "undo step: call it again to reverse it (undo would take back the step before it).",
    schema(
        {"targets": step_ids("what to show or hide"), "visible": boolean()}, ["targets", "visible"]
    ),
    own_id=False,
    title_fn=lambda a: "AI: %s" % ("Show" if a.get("visible") else "Hide"),
    examples=[example({"targets": ["Sketch1"], "visible": False}, "hide Sketch1")],
)

# -- HELP ---------------------------------------------------------------------------------------
HELP_TOPICS = (
    "overview",
    "selectors",
    "picks",
    "body_picks",
    "sketches",
    "geometry",
    "curves",
    "steps",
    "expressions",
    "workflow",
    "checking",
    "docs",
    "tools",
)
define(
    "get_help",
    "Get help",
    "help",
    "(SciForge's documentation for AI models)",
    "Read SciForge's rules for AI tools: overview, selectors (how to pick faces and edges), "
    "picks (planes, axes, faces, edges, corners), body_picks, sketches (planes and "
    "coordinates), geometry (sketch shapes), curves (paths and rails), steps (ids), "
    "expressions (parameters in fields), workflow (how to build and check a part), checking "
    "(the tools that check your work with numbers and pictures), docs (where the documentation "
    "is and how to search it), tools (every tool by category with its Fusion command). "
    "Without topic: overview.",
    schema({"topic": enum(HELP_TOPICS, default="overview")}),
    changes=False,
    needs=(),
    examples=[example({"topic": "selectors"}, "how selectors pick faces and edges")],
)
define(
    "list_tools",
    "List tools",
    "help",
    "(SciForge's command list)",
    "List every tool by category with its Fusion command, whether it changes the design, "
    "and whether it can run right now (and why not: no design open, no solid yet, needs the "
    "SciForge window...). category: only that category.",
    schema(
        {
            "category": enum(
                [
                    c
                    for c in (
                        "help",
                        "document",
                        "inspect",
                        "sketch",
                        "create",
                        "modify",
                        "surface",
                        "construct",
                        "assemble",
                        "timeline",
                        "parameters",
                        "import_export",
                        "drawing",
                        "view",
                    )
                ]
            )
        }
    ),
    changes=False,
    needs=(),
    examples=[example({"category": "modify"}, "the Modify tools and which can run now")],
)
