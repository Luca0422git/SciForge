# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Measure (key I) with real input: faces, edges, corners, bodies, snap points,
precision, a third pick starting over, a picked item clicked again, Restart Selection, a value
copied by clicking it, Close / Esc, a face selected before pressing I, no undo step.

Part (real input): box 40 x 30 x 10 from the origin with a round boss r = 5 on top, centre
(10, 10), 10 high. Hand-derived values:
  top face area 40 * 30 - pi * 5^2 = 1121.460 mm^2 (its outer edge 140 mm)
  top face and right face: they touch (distance 0), at 90 degrees
  front top edge length 40; to the boss's top circle (z = 20): the nearest points are
    (10, 0, 10) and (10, 5, 20): distance sqrt(5^2 + 10^2) = 11.180, dX 0, dY 5, dZ 10
  corners (0, 0, 10) and (40, 30, 10): 50, dX 40, dY 30, dZ 0
  the body: volume 12000 + 250 pi = 12785.398 mm^3, area 3800 + 100 pi = 4114.159 mm^2
  snap points: the boss circle's centre (10, 10, 20) to the front top edge's middle
    (20, 0, 10): sqrt(3 * 10^2) = 17.321"""
from PySide import QtCore, QtWidgets

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import widget_input as w

V = App.Vector
st = {}
CIRCLE_TOP = V(13.5355339, 6.4644661, 20)  # a point of the boss's top edge facing the viewer


def panel():
    from sciforge import measure_ui, taskui

    p = taskui.current()
    return p if isinstance(p, measure_ui.MeasurePanel) else None


def values():
    p = panel()
    return p.values() if p is not None else {}


def value(section, name):
    return values().get(section, {}).get(name)


def press_i():
    st["undo"] = list(App.ActiveDocument.UndoNames)
    h.click_empty()
    h.press("i")


def opened():
    p = panel()
    h.check("I opens Measure", p is not None)
    if p is None:
        return
    h.check(
        "Selection Filter: faces / edges / corners", p.filter.currentText() == "Face/Edge/Vertex"
    )
    h.check("Precision 0.123", p.precision.currentText() == "0.123")
    h.check("asks for a pick", "Click" in p.message.text(), p.message.text())
    s.no_popups("I")


def click_top():
    h.fit()
    h.click(V(30, 20, 10))


def top_area():
    h.check("top face area", value("Selection 1", "Area") == "1121.460 mm^2", values())
    h.check("its outer edge", value("Selection 1", "Perimeter") == "140.000 mm", values())


def copy_area():
    p = panel()
    if p is None:
        return
    top = p.tree.topLevelItem(0)
    item = [top.child(i) for i in range(top.childCount()) if top.child(i).text(0) == "Area"][0]
    rect = p.tree.visualItemRect(item)
    pos = QtCore.QPoint(p.tree.columnViewportPosition(1) + 10, rect.center().y())
    QtWidgets.QApplication.clipboard().setText("")
    w.click(p.tree.viewport(), pos)


def copied():
    text = QtWidgets.QApplication.clipboard().text()
    h.check("clicking the value copied it", text == "1121.460 mm^2", text)


def click_right():
    h.click(V(40, 15, 5))


def two_faces():
    r = values().get("Results", {})
    h.check("touching faces: distance 0", r.get("Distance") == "0.000 mm", values())
    h.check("at 90 degrees", r.get("Angle") == "90.000 deg", values())
    h.check(
        "both stay picked", len(s.selection()) == 1 and len(s.selection()[0][1]) == 2, s.selection()
    )
    h.shot("1-two-faces")


def third_pick_edge():
    h.click_edge(V(25, 0, 10))


def started_over():
    v = values()
    h.check("a third pick starts over", "Selection 2" not in v and "Results" not in v, v)
    h.check("edge length 40", value("Selection 1", "Length") == "40.000 mm", v)


def click_circle():
    h.click_edge(CIRCLE_TOP)


def edge_to_circle():
    r = values().get("Results", {})
    h.check("edge to circle: 11.180", r.get("Distance") == "11.180 mm", values())
    h.check("dX 0", r.get("Delta X") == "0.000 mm", r)
    h.check("dY 5", r.get("Delta Y") == "5.000 mm", r)
    h.check("dZ 10", r.get("Delta Z") == "10.000 mm", r)
    h.check("no angle for a circle", "Angle" not in r, r)
    h.check("circle radius shown", value("Selection 2", "Radius") == "5.000 mm", values())
    p = panel()
    h.check("the distance is drawn", p is not None and p.relation is not None)
    h.shot("2-edge-circle")


def click_circle_again():
    h.click_edge(CIRCLE_TOP)


def circle_dropped():
    v = values()
    h.check("clicking a pick again drops it", "Selection 2" not in v and "Selection 1" in v, v)


def precision_one():
    p = panel()
    if p is not None:
        h.check("precision offered", di.choose(p.precision, "0.1"))


def one_decimal():
    h.check("one decimal now", value("Selection 1", "Length") == "40.0 mm", values())
    p = panel()
    if p is not None:
        di.click(p.restart)


def restarted():
    h.check("Restart Selection empties it", not values(), values())
    h.check("nothing selected", not Gui.Selection.getSelectionEx(), s.selection())


def corner_1():
    s.click_vertex(V(0, 0, 10))


def corner_2():
    h.check("corner position", value("Selection 1", "X") == "0.0 mm", values())
    s.click_vertex(V(40, 30, 10))


def corners():
    r = values().get("Results", {})
    h.check("corner to corner 50", r.get("Distance") == "50.0 mm", values())
    h.check(
        "dX 40, dY 30, dZ 0",
        (r.get("Delta X"), r.get("Delta Y"), r.get("Delta Z")) == ("40.0 mm", "30.0 mm", "0.0 mm"),
        r,
    )
    p = panel()
    if p is not None:
        di.choose(p.precision, "0.123")


def body_filter():
    p = panel()
    if p is not None:
        h.check("Body filter offered", di.choose(p.filter, "Body"))


def click_body():
    h.check("switching the filter starts over", not values(), values())
    h.click(V(30, 20, 10))


def body_values():
    h.check("body volume", value("Selection 1", "Volume") == "12785.398 mm^3", values())
    h.check("body area", value("Selection 1", "Area") == "4114.159 mm^2", values())
    sel = s.selection()
    h.check("the whole body is picked", len(sel) == 1 and sel[0][0] == "Body", sel)


def snap_on():
    p = panel()
    if p is None:
        return
    di.choose(p.filter, "Face/Edge/Vertex")
    p.snap.click()


def hover_circle():
    p = panel()
    h.check("snap points on", p is not None and p.snap.isChecked())
    h.move(h.screen_point(CIRCLE_TOP))


def click_centre():
    p = panel()
    h.check("dots on the circle", p is not None and p.dots is not None and p.snaps, p and p.snaps)
    names = [n for n, _p in p.snaps] if p else []
    h.check("one is its centre", "Centre" in names, names)
    h.shot("3-snap-points")
    h.click(V(10, 10, 20))


def centre_picked():
    v = values()
    one = v.get("Selection 1", {})
    h.check(
        "the centre is picked",
        (one.get("X"), one.get("Y"), one.get("Z")) == ("10.000 mm", "10.000 mm", "20.000 mm"),
        v,
    )
    h.move(h.screen_point(V(25, 0, 10)))


def click_middle():
    p = panel()
    names = [n for n, _p in p.snaps] if p else []
    h.check("dots on the edge", "Middle" in names, names)
    pl.click_on_plane(V(20, 0, 10))


def centre_to_middle():
    r = values().get("Results", {})
    h.check("centre to middle 17.321", r.get("Distance") == "17.321 mm", values())


def close():
    h.task_button("Close")


def closed():
    h.check("Close closes Measure", panel() is None and not Gui.Control.activeDialog())
    h.check("nothing left selected", not Gui.Selection.getSelectionEx(), s.selection())
    h.check(
        "no undo step",
        list(App.ActiveDocument.UndoNames) == st["undo"],
        App.ActiveDocument.UndoNames,
    )
    h.check("part unchanged", s.close(h.solid_volume(), 12000 + 3.141592653589793 * 250))


def preselect():
    h.fit()
    h.click(V(30, 20, 10))


def preselected_i():
    h.check("face selected", bool(s.selection()), s.selection())
    h.press("i")


def preselected_taken():
    h.check(
        "the selected face is measured", value("Selection 1", "Area") == "1121.460 mm^2", values()
    )
    s.press_escape()


def esc_closed():
    h.check("Esc closes Measure", panel() is None and not Gui.Control.activeDialog())
    h.check("no pop-ups", not h.popups(), h.popups())


h.run(
    "inspect_measure",
    b.box_steps("InspectMeasure")
    + s.boss_steps()
    + [
        press_i,
        opened,
        click_top,
        top_area,
        copy_area,
        copied,
        click_right,
        two_faces,
        third_pick_edge,
        started_over,
        click_circle,
        edge_to_circle,
        click_circle_again,
        circle_dropped,
        precision_one,
        one_decimal,
        restarted,
        corner_1,
        corner_2,
        corners,
        body_filter,
        click_body,
        body_values,
        snap_on,
        hover_circle,
        click_centre,
        centre_picked,
        click_middle,
        centre_to_middle,
        close,
        closed,
        preselect,
        preselected_i,
        preselected_taken,
        esc_closed,
    ],
)
