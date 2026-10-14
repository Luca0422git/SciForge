# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commands of the SKETCH tab's remaining Fusion tools (outline 7.5): the drawing tools
SciForge draws itself (sketch_draw_tools.py), Trim / Extend / Break
(sketch_modify_tools.py), the Collinear / Concentric / Midpoint / Curvature constraints
(sketch_constrain_tools.py) and Project to Surface (sketch_project_tool.py).

Every command says next to the mouse when it cannot start (no sketch open)."""

import FreeCAD as App

from . import sketch_constrain_tools as constrain
from . import sketch_draw_tools as tools
from . import sketch_modify_tools as modify
from . import sketch_project_tool as project
from . import ui_icon_path, warn


class _ToolCommand:
    title = ""
    tip = ""
    icon = ""
    tool = None  # the sketch_draw.DrawTool subclass to run

    def GetResources(self):
        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            res["Pixmap"] = ui_icon_path(self.icon)
        return res

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            from . import sketch_draw

            sketch_draw.run(self.tool)
        except Exception as exc:
            warn("%s failed: %s" % (self.title, exc))


def _command(tool, icon, tip):
    return type(
        "Command_" + tool.__name__,
        (_ToolCommand,),
        {"title": tool.title, "tip": tip, "icon": icon, "tool": tool},
    )


COMMANDS = {
    "SciForge_SketchMidpointLine": _command(
        tools.MidpointLine,
        "sk_line",
        "A line drawn out both ways from its middle: click the middle, then an end "
        "(or type the length and angle)",
    ),
    "SciForge_SketchRectangle3Point": _command(
        tools.ThreePointRectangle,
        "sk_rectangle",
        "A rectangle at any angle: click two corners (one side), then the width (or type "
        "the length, angle and width)",
    ),
    "SciForge_SketchCircle2Point": _command(
        tools.TwoPointCircle,
        "sk_circle",
        "A circle across two points: click both ends of the diameter",
    ),
    "SciForge_SketchCircle2Tangent": _command(
        tools.TwoTangentCircle,
        "sk_circle",
        "A circle touching two lines: click the lines, then the side (or type the radius)",
    ),
    "SciForge_SketchCircle3Tangent": _command(
        tools.ThreeTangentCircle,
        "sk_circle",
        "A circle touching three lines: click them, then click near the circle you want",
    ),
    "SciForge_SketchTangentArc": _command(
        tools.TangentArc,
        "sk_arc",
        "An arc that continues a line or arc smoothly: click its end, then the arc's end",
    ),
    "SciForge_SketchPolygonEdge": _command(
        tools.EdgePolygon,
        "sk_polygon",
        "A polygon from one edge: click the edge's two ends, then the side it goes to",
    ),
    "SciForge_SketchSlotCenter": _command(
        tools.CenterToCenterSlot,
        "sk_slot",
        "A slot from the centres of its ends: click both centres, then the width",
    ),
    "SciForge_SketchSlotOverall": _command(
        tools.OverallSlot,
        "sk_slot",
        "A slot from its overall length: click both ends, then the width",
    ),
    "SciForge_SketchSlotCenterPoint": _command(
        tools.CenterPointSlot,
        "sk_slot",
        "A slot around its middle: click the middle, then one end's centre, then the width",
    ),
    "SciForge_SketchSlotArc3Point": _command(
        tools.ThreePointArcSlot,
        "sk_slot",
        "A curved slot: click both end centres, a point on its centre arc, then the width",
    ),
    "SciForge_SketchConic": _command(
        tools.ConicCurve,
        "sk_conic",
        "A conic curve: click the start, the end and the apex, then shape it with rho",
    ),
    "SciForge_SketchProjectToSurface": _command(
        project.ProjectToSurface,
        "sk_project",
        "Project sketch curves or edges onto faces of the part (as 3D curves)",
    ),
    "SciForge_SketchTrim": _command(
        modify.Trim,
        "sk_trim",
        "Remove the piece of a curve between the curves crossing it: click it, or press "
        "and drag across several (T)",
    ),
    "SciForge_SketchExtend": _command(
        modify.Extend,
        "sk_extend",
        "Extend a line or arc to the next curve it meets: click near its end",
    ),
    "SciForge_SketchBreak": _command(
        modify.Break, "sk_break", "Break a curve where other curves cross it: click it"
    ),
    "SciForge_SketchCollinear": _command(
        constrain.Collinear, "c_collinear", "Put two lines on one line: click them"
    ),
    "SciForge_SketchConcentric": _command(
        constrain.Concentric,
        "c_concentric",
        "Give two circles, arcs or ellipses the same centre: click them",
    ),
    "SciForge_SketchMidpoint": _command(
        constrain.Midpoint,
        "c_midpoint",
        "Put a point at the middle of a line or arc: click the point, then the line",
    ),
    "SciForge_SketchCurvature": _command(
        constrain.Curvature,
        "c_smooth",
        "Join a spline smoothly to a curve (curvature): click the spline, then the curve",
    ),
}
