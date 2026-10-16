# SPDX-License-Identifier: LGPL-2.1-or-later
"""Box selection of construction planes and axes in the canvas (parity/selection.md,
"Sketch, part 2"), real mouse drags.

An empty design with a body and an Offset Plane 20 above XY (60 x 60 as the view draws it).

  A  a window round the offset plane selects it (whole, as a click on it does), nothing
     else; Create Sketch then puts the sketch on it, as on a clicked plane
  B  the origin shown: a window round the XY plane's square in the top view selects the XY
     plane, not the axes that stick out of it; a crossing box over the X axis alone selects
     the X axis
  C  Selection Filters > Work Geometry off: the same window selects nothing; on again
  D  an origin that is hidden is not boxed (the planes are not drawn)
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as sel
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def picked():
    """The selected objects (planes resolve through their path)."""
    return sorted({x.Object.Name for x in Gui.Selection.getSelectionEx()})


def setup():
    from sciforge import commands, construct, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("BoxPlanes")
    body = commands.ensure_body()
    s["body"] = body
    s["planes"] = sketch_ui.origin_planes(body)
    App.ActiveDocument.openTransaction("Offset Plane")
    s["plane"] = construct.make(
        body, "OffsetPlane", [(s["planes"]["XY_Plane"], "")], {"distance": 20.0}
    )
    App.ActiveDocument.commitTransaction()
    App.ActiveDocument.recompute()
    Gui.Selection.clearSelection()
    h.fit()


def box_of(obj, margin=6, crossing=False):
    box = obj.ViewObject.getBoundingBox()
    corners = [
        V(x, y, z)
        for x in (box.XMin, box.XMax)
        for y in (box.YMin, box.YMax)
        for z in (box.ZMin, box.ZMax)
    ]
    sel.box_around(corners, margin=margin, crossing=crossing)


# -- A ----------------------------------------------------------------------------------------
def a_window():
    s["plane_name"] = s["plane"].Name
    box_of(s["plane"])


a_window.wait_ms = 900


def a_check():
    h.check("A a window round the offset plane selects it", picked() == [s["plane_name"]], picked())
    h.ribbon("Create Sketch")


a_check.wait_ms = 1500


def a_sketch():
    sk = h.in_sketch()
    h.check("A Create Sketch with the plane selected opens a sketch", sk is not None)
    if sk is not None:
        z = sk.getGlobalPlacement().Base.z
        h.check("A ...on the offset plane (20 up)", abs(z - 20.0) < 1e-6, z)
    h.ribbon("Finish Sketch")


a_sketch.wait_ms = 900


# -- B ----------------------------------------------------------------------------------------
def b_show_origin():
    Gui.Selection.clearSelection()
    origin = s["body"].Origin
    origin.ViewObject.Visibility = True
    for o in origin.OriginFeatures:
        o.ViewObject.Visibility = True
    s["plane"].ViewObject.Visibility = False  # only the origin now
    for o in App.ActiveDocument.Objects:
        if o.TypeId == "Sketcher::SketchObject":
            o.ViewObject.Visibility = False
    h.view().viewTop()
    h.fit(iso=False)


def b_window():
    box_of(s["planes"]["XY_Plane"], margin=2)


b_window.wait_ms = 900


def b_check():
    h.check(
        "B a window round the XY plane's square selects the XY plane",
        picked() == [s["planes"]["XY_Plane"].Name],
        picked(),
    )
    Gui.Selection.clearSelection()
    axis = [o for o in s["body"].Origin.OriginFeatures if o.Role == "X_Axis"][0]
    s["x_axis"] = axis
    box = axis.ViewObject.getBoundingBox()
    # a small crossing box over the axis's outer end, beyond the XY plane's square
    tip = V(box.XMax - 1.0, 0, 0)
    sel.box_at(tip, half=4, crossing=True)


b_check.wait_ms = 900


def b_axis_check():
    h.check(
        "B a crossing box over the X axis's end selects the X axis",
        picked() == [s["x_axis"].Name],
        picked(),
    )
    Gui.Selection.clearSelection()


# -- C ----------------------------------------------------------------------------------------
def c_filter_off():
    result = sel.choose_select(["Selection Filters", "Work Geometry"])
    h.check("C Work Geometry turned off", result is not False, result)


def c_window():
    from sciforge import selection_ui

    h.check("C the filter is off", not selection_ui.work_geometry_on())
    box_of(s["planes"]["XY_Plane"], margin=2)


c_window.wait_ms = 900


def c_check():
    h.check("C with Work Geometry off the window selects no plane", not picked(), picked())
    sel.choose_select(["Selection Filters", "Work Geometry"])


def c_back():
    from sciforge import selection_ui

    h.check("C Work Geometry on again", selection_ui.work_geometry_on())


# -- D ----------------------------------------------------------------------------------------
def d_hide_origin():
    s["body"].Origin.ViewObject.Visibility = False
    Gui.Selection.clearSelection()


def d_window():
    box_of(s["planes"]["XY_Plane"], margin=2)


d_window.wait_ms = 900


def d_check():
    h.check("D a hidden origin's planes are not boxed", not picked(), picked())


h.run(
    "sketch2_box_planes",
    si.watched(
        [
            setup,
            a_window,
            a_check,
            a_sketch,
            b_show_origin,
            b_window,
            b_check,
            b_axis_check,
            c_filter_off,
            c_window,
            c_check,
            c_back,
            d_hide_origin,
            d_window,
            d_check,
        ]
    ),
)
