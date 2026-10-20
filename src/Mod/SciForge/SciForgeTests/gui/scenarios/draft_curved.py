# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft of curved walls, only real input (Luca, 2026-10-20: "I cant seem to select curved
faces"; Fusion takes free-form faces too). The part: a 30 x 20 rounded rectangle (corners
r 3) whose front side is a spline bulging 3 mm out, tangent to the corner arcs, extruded 10.
Its 8 side walls (4 flat, 3 round... and the spline) are one tangent chain.

Ribbon Draft with nothing selected, click the XY square (pull +Z), click the spline wall: it
is taken (FreeCAD's own Draft refuses such a face) with its whole tangent chain; type 3,
Tangent Chain off (the spline alone) and on again, OK, Ctrl+Z / Ctrl+Y, edit from the
timeline, an angle the r 3 corners cannot take (explained, OK waits), 5, OK, and a second
Draft started with the spline wall selected beforehand, Cancel.

Volumes, measured on a mesh (OpenCASCADE's volume of B-spline faces is ~0.5 % off): the
outline is smooth all round, so at height z it is offset inward by z tan(a), with area
A - P d + pi d^2 (Steiner): V(a) = A H - P tan(a) H^2 / 2 + pi tan(a)^2 H^3 / 3.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import widget_input as w

V = App.Vector
H = 10.0
SPLINE = V(15, -3, 5)  # on the spline wall (the spline goes through (15, -3))
s = {}


def outline_edges():
    import Part

    spline = Part.BSplineCurve()
    spline.interpolate(
        [V(3, 0, 0), V(15, -3, 0), V(27, 0, 0)],
        Tangents=[V(1, 0, 0), V(0, 0, 0), V(1, 0, 0)],
        TangentFlags=[True, False, True],
    )

    def arc(cx, cy, a0, a1):
        circle = Part.Circle(V(cx, cy, 0), V(0, 0, 1), 3)
        return Part.ArcOfCircle(circle, math.radians(a0), math.radians(a1))

    return [
        spline,
        arc(27, 3, -90, 0),
        Part.LineSegment(V(30, 3, 0), V(30, 17, 0)),
        arc(27, 17, 0, 90),
        Part.LineSegment(V(27, 20, 0), V(3, 20, 0)),
        arc(3, 17, 90, 180),
        Part.LineSegment(V(0, 17, 0), V(0, 3, 0)),
        arc(3, 3, 180, 270),
    ]


def profile(sketch):
    for geometry in outline_edges():
        sketch.addGeometry(geometry)
    App.ActiveDocument.recompute()


def outline():
    """(area, perimeter) of the outline: the area from many points (OpenCASCADE's area of a
    spline-bounded face is a little off)."""
    import Part

    wire = Part.Wire(Part.__sortEdges__([g.toShape() for g in outline_edges()]))
    pts = wire.discretize(100000)
    area = 0.5 * abs(sum(p.x * q.y - q.x * p.y for p, q in zip(pts, pts[1:])))
    return area, wire.Length


def drafted(a):
    area, length = outline()
    t = math.tan(math.radians(a))
    return area * H - length * t * H * H / 2.0 + math.pi * t * t * H**3 / 3.0


def base_volume():
    return outline()[0] * H


def mesh_volume():
    import Mesh

    return Mesh.Mesh(h.body().Shape.tessellate(0.002)).Volume


def near(v, want, tol=2e-4):
    return abs(v - want) <= tol * abs(want)


def box_point(checkbox):
    """The tick box itself (a check box without text is as wide as the dialog)."""
    return QtCore.QPoint(8, checkbox.height() // 2)


def own_drafts():
    return sd.features(None, "Draft")


def ribbon_draft():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def waiting():
    p = sd.draft_panel()
    h.check("Draft dialog open", p is not None and Gui.Control.activeDialog())
    h.check("waits for the pull direction", p is not None and p.active == "plane")
    s["base"] = mesh_volume()
    h.check("part made: the outline extruded 10", near(s["base"], base_volume()), s["base"])


def click_xy():
    h.fit()
    pl.click_square("XY_Plane")


def plane_picked():
    p = sd.draft_panel()
    h.check("XY picked", p is not None and p.plane_ref is not None)
    h.check("Faces box takes the clicks", p is not None and p.active == "faces")


def click_spline():
    h.fit()
    h.click(SPLINE)


def spline_picked():
    p = sd.draft_panel()
    names = p.names() if p else []
    h.check("the curved wall is taken", p is not None and len(p.picked) == 1, p and p.picked)
    h.check("with its tangent chain: all 8 walls", len(names) == 8, names)
    h.check("no error", p is not None and not p.error, p and p.error)
    h.check(
        "SciForge's own Draft step (FreeCAD's cannot tilt a spline face)",
        p is not None and p.target is not None and getattr(p.target, "SciForgeType", "") == "Draft",
    )
    v = mesh_volume()
    h.check("preview: the 8 walls drafted 1 deg", near(v, drafted(1)), (v, drafted(1)))
    h.check("the angle handle is shown", p is not None and p.handle is not None)
    h.shot("1-spline-chain")
    if p:
        sd.type_into(p.angle.widget, "3")


def three_degrees():
    v = mesh_volume()
    h.check("typed 3 deg previews", near(v, drafted(3)), (v, drafted(3)))
    p = sd.draft_panel()
    if p:
        w.click(p.tangent, box_point(p.tangent))  # Tangent Chain off


def spline_alone():
    p = sd.draft_panel()
    names = p.names() if p else []
    h.check("Tangent Chain off: the spline wall alone", len(names) == 1, names)
    h.check("no error", p is not None and not p.error, p and p.error)
    v = mesh_volume()
    s["alone"] = v
    h.check(
        "less taken away than with the whole chain",
        drafted(3) < v < s["base"] - 1.0,
        (drafted(3), v, s["base"]),
    )
    h.check("still a valid solid", h.body().Shape.isValid())
    h.shot("2-spline-alone")
    if p:
        w.click(p.tangent, box_point(p.tangent))  # on again


def chain_again():
    p = sd.draft_panel()
    h.check("Tangent Chain on: 8 walls again", p is not None and len(p.names()) == 8)
    h.check("back to the chain's volume", near(mesh_volume(), drafted(3)), mesh_volume())
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    shape = h.body().Shape
    h.check("valid solid", shape.isValid())
    h.check("still 10 faces (the chain stays tangent)", len(shape.Faces) == 10, len(shape.Faces))
    v = mesh_volume()
    h.check("drafted 3 deg", near(v, drafted(3)), (v, drafted(3)))
    d = own_drafts()
    h.check("one Draft step at the end", len(d) == 1 and h.body().Tip is d[0], d)
    h.check("timeline shows Draft 1", "Draft 1" in sd.timeline_titles(), sd.timeline_titles())
    h.shot("3-ok")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check(
        "Ctrl+Z takes the draft away",
        near(mesh_volume(), s["base"], 1e-5) and not own_drafts(),
        mesh_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("Ctrl+Y brings it back", near(mesh_volume(), drafted(3)) and own_drafts())
    h.fit()


def edit_from_timeline():
    sd.timeline_double_click("Draft 1")


def edit_open():
    p = sd.draft_panel()
    h.check("double-click opens the Draft dialog on the step", p is not None and p.editing)
    h.check("its 8 walls are shown picked", p is not None and len(p.names()) == 8)
    h.check("3 deg shown", p is not None and abs(p.angle.value() - 3) < 1e-9)
    if p:
        sd.type_into(p.angle.widget, "40")


def too_steep():
    p = sd.draft_panel()
    text = p.message.text() if p else ""
    h.check("an angle the r 3 corners cannot take is explained", "bends too tightly" in text, text)
    h.task_button("OK")


def ok_waits():
    h.check("OK waits while the draft fails", sd.draft_panel() is not None)
    p = sd.draft_panel()
    if p:
        sd.type_into(p.angle.widget, "5")


def edit_ok():
    p = sd.draft_panel()
    h.check(
        "message gone at 5 deg", p is not None and p.message.text() == "", p and p.message.text()
    )
    h.task_button("OK")


def after_edit():
    v = mesh_volume()
    h.check("edited to 5 deg", near(v, drafted(5)), (v, drafted(5)))
    h.check("still one draft", len(own_drafts()) == 1, own_drafts())
    h.check("valid", h.body().Shape.isValid())
    s["v"] = v
    h.shot("4-edited")


def preselect_spline():
    h.fit()
    h.click(SPLINE)


def second_draft():
    h.check("the drafted spline wall is selected", len(sd.selected()) == 1, sd.selected())
    sd.modify_menu("Draft")


def second_started():
    p = sd.draft_panel()
    h.check("Draft started with the curved wall", p is not None and len(p.picked) == 1)
    h.check("it waits for the pull direction", p is not None and p.active == "plane")
    h.fit()
    pl.click_square("XY_Plane")


def second_preview():
    p = sd.draft_panel()
    h.check(
        "an already drafted (leaning) free-form wall is refused, with the reason",
        p is not None and p.error and "run along the pull direction" in p.error,
        p and p.error,
    )
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the part as it was", near(mesh_volume(), s["v"], 1e-5))
    h.check("still one draft", len(own_drafts()) == 1)
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("5-end")


h.run(
    "draft_curved",
    b.box_steps("DraftCurved", profile=profile)
    + [
        ribbon_draft,
        waiting,
        click_xy,
        plane_picked,
        click_spline,
        spline_picked,
        three_degrees,
        spline_alone,
        chain_again,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        too_steep,
        ok_waits,
        edit_ok,
        after_edit,
        preselect_spline,
        second_draft,
        second_started,
        second_preview,
        after_cancel,
    ],
)
