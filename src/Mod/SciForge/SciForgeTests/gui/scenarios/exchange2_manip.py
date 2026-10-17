# SPDX-License-Identifier: LGPL-2.1-or-later
"""The manipulators of Insert SVG / Insert DXF and Canvas (exchange-2,
docs/sciforge/parity/insert-export.md Part 2): two arrows move the curves or the picture
on its plane, the curved handle turns it, the arrow at its right edge scales it, each with
its value box; Edit Canvas has them too. Real mouse drags and typing; the file dialog is
the only stand-in.

P1  INSERT > Insert SVG, the XY square: the curves centred on the origin, the manipulator
    at their middle (four handles, value boxes).
P2  The X arrow dragged: X Distance follows the drag, the curves move by it.
P3  The curved handle dragged a quarter turn the other way: the SVG's Z Angle is negative
    (Fusion: positive turns clockwise) and the rectangle's long side turned
    counter-clockwise by as much.
P4  The scale arrow dragged outwards: Scale grows, the rectangle's long side is 30 x Scale.
P5  12 typed in the X value box, Enter: X Distance 12, and Enter finishes the command
    (Fusion's Enter in a value box): the sketch keeps the moved curves.
P6  Ctrl+Z: no sketch; Ctrl+Y: back, the same.
P7  INSERT > Canvas, the XY square: the handles at the picture's middle; the curved handle
    turns it (Z Angle > 0, counter-clockwise), the Y arrow moves it; OK.
P8  Browser: right-click the canvas > Edit Canvas: the handles where the picture is now;
    the scale arrow scales it (Scale X and Y by the same factor); Esc: as it was.
P9  INSERT > Insert DXF on XY: the manipulator at the DXF's origin (the sketch origin); the
    X arrow moves the curves; Cancel: nothing inserted.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import timeline_input as t

V = App.Vector
s = {}


def sketch():
    found = i.sketches()
    return found[-1] if found else None


def lines(sk):
    return [g for g in sk.Geometry if g.TypeId == "Part::GeomLineSegment"]


def rect_box(sk):
    xs, ys = [], []
    for geo in lines(sk):
        for p in (geo.StartPoint, geo.EndPoint):
            xs.append(p.x)
            ys.append(p.y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def long_side(sk):
    """(length, direction in degrees, counter-clockwise from X) of the rectangle's long side."""
    best = None
    for geo in lines(sk):
        d = geo.EndPoint - geo.StartPoint
        if best is None or d.Length > best.Length:
            best = d
    if best is None:
        return None
    a = math.degrees(math.atan2(best.y, best.x)) % 180.0
    return best.Length, a


def circle_centre(sk):
    for geo in sk.Geometry:
        if geo.TypeId == "Part::GeomCircle":
            return geo.Center
    return None


def panel():
    return i.panel()


def _settled_arrow(key, timeout_ms=3000):
    """The dialog's arrow `key` once it stays put on the screen: after a Fit the handles
    are rebuilt and their boxes moved by timers, later on a slow machine (CI #145, #148:
    the press went where the arrow had been)."""
    last, arrow = None, None
    waited = 0
    while waited <= timeout_ms:
        p = panel()
        arrow = p.handle_by.get(key) if p is not None else None
        if arrow is None:
            return None
        now = (
            h.screen_point(ai.arrow_point(arrow, 0.2)),
            h.screen_point(ai.arrow_point(arrow, 0.9)),
        )
        if now == last:
            return arrow
        last = now
        QtTest.QTest.qWait(250)
        waited += 250
    return arrow


def drag_arrow(key, mm):
    p = panel()
    if p is None or key not in getattr(p, "handle_by", {}):
        h.check("handle %s shown" % key, False)
        return
    arrow = _settled_arrow(key)
    # an arrow reaching under the dialog (its width follows the machine's fonts): a person
    # slides the view first
    if arrow is not None and h.uncover(ai.arrow_point(arrow, 1.0)):
        arrow = _settled_arrow(key)
    if arrow is None:
        h.check("handle %s shown" % key, False)
        return
    # a visible part of the arrow, as a hand grabs it: rests on it a moment, then presses
    # where nothing (a value box) covers it
    start = ai.arrow_point(arrow, 0.6)
    for part in (0.6, 0.8, 0.45, 0.9, 0.3):
        point = ai.arrow_point(arrow, part)
        h.move(h.screen_point(point))
        QtTest.QTest.qWait(150)
        if h.covered(h.screen_point(point)) is None:
            start = point
            break
    end = start + arrow.direction * mm
    h.drag(h.screen_point(start), h.screen_point(end), steps=16)


def drag_turn(degrees):
    p = panel()
    if p is None or "angle" not in getattr(p, "handle_by", {}):
        h.check("turn handle shown", False)
        return
    turn = p.handle_by["angle"]
    now, target = turn.screen_points(degrees)
    h.drag(h.screen_point(now), h.screen_point(target), steps=20)


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Manipulators")
    h.fit()


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    i.use_file(i.fixture("shape.svg"))
    i.menu("INSERT", "Insert SVG")


def p1_click_xy():
    h.click(i.XY_CLICK)


p1_click_xy.wait_ms = 1500


def p1_check():
    p = panel()
    sk = sketch()
    h.check("P1 a sketch with the curves", sk is not None and sk.GeometryCount == 5)
    if sk is not None:
        box = rect_box(sk)
        h.check(
            "P1 centred on the origin",
            box is not None and x.near3(box, (-15, -10, 15, 10), 1e-3),
            box,
        )
    h.check("P1 four handles", p is not None and len(p.handles) == 4, p and p.handles)
    if p is None or not p.handles:
        return
    point = p.handle_point()
    h.check("P1 the manipulator at the middle", x.near3(tuple(point), (0, 0, 0), 1e-6), point)
    shown = sorted(p.value_boxes.shown())
    h.check("P1 value boxes beside the handles", shown == ["angle", "scale", "x", "y"], shown)
    h.shot("1-svg-handles")


# -- P2 ----------------------------------------------------------------------------------------
def p2_drag_x():
    h.fit()
    drag_arrow("x", 8.0)


p2_drag_x.wait_ms = 1500


def p2_check():
    p = panel()
    sk = sketch()
    if p is None or sk is None:
        h.check("P2 the dialog and the sketch", False)
        return
    dx = p.dx.value()
    s["dx"] = dx
    h.check("P2 X Distance followed the drag", dx > 3.0, dx)
    box = rect_box(sk)
    h.check(
        "P2 the curves moved by X Distance",
        box is not None and x.near3(box, (-15 + dx, -10, 15 + dx, 10), 1e-3),
        (dx, box),
    )
    h.check(
        "P2 the handles followed",
        x.near3(tuple(p.handle_point()), (dx, 0, 0), 1e-6),
        p.handle_point(),
    )


# -- P3 ----------------------------------------------------------------------------------------
def p3_turn():
    drag_turn(40.0)


p3_turn.wait_ms = 1500


def p3_check():
    p = panel()
    sk = sketch()
    if p is None or sk is None:
        return
    angle = p.angle.value()
    s["angle"] = angle
    h.check("P3 the Z Angle is negative (positive turns clockwise)", angle < -10.0, angle)
    side = long_side(sk)
    h.check(
        "P3 the long side turned counter-clockwise by as much",
        side is not None and abs(side[1] - (-angle) % 180.0) < 0.05,
        (side, angle),
    )
    centre = circle_centre(sk)
    h.check(
        "P3 it turned about its middle (the hole stays put)",
        centre is not None and x.near3(tuple(centre), (s["dx"], 0, 0), 1e-3),
        centre,
    )


# -- P4 ----------------------------------------------------------------------------------------
def p4_scale():
    drag_arrow("scale", 6.0)


p4_scale.wait_ms = 1500


def p4_check():
    p = panel()
    sk = sketch()
    if p is None or sk is None:
        return
    scale = p.scale.value()
    h.check("P4 Scale grew", scale > 1.1, scale)
    side = long_side(sk)
    h.check(
        "P4 the long side is 30 x Scale",
        side is not None and abs(side[0] - 30.0 * scale) < 1e-3,
        (side, scale),
    )
    s["scale"] = scale


# -- P5 ----------------------------------------------------------------------------------------
def p5_type():
    p = panel()
    if p is None:
        return
    box = p.value_boxes.boxes.get("x")
    if h.check("P5 the X value box", box is not None and box.isVisible()):
        ai.type_in_box(box, "12")


p5_type.wait_ms = 1200


def p5_check():
    sk = sketch()
    h.check("P5 Enter finished the command", panel() is None)
    h.check("P5 the sketch is kept", sk is not None and sk.GeometryCount == 5)
    if sk is None:
        return
    centre = circle_centre(sk)
    h.check(
        "P5 the curves at X 12 (the typed value)",
        centre is not None and abs(centre.x - 12.0) < 1e-6,
        centre,
    )
    side = long_side(sk)
    h.check(
        "P5 still turned and scaled",
        side is not None
        and abs(side[1] - (-s["angle"]) % 180.0) < 0.05
        and abs(side[0] - 30.0 * s["scale"]) < 1e-3,
        side,
    )
    s["geometry"] = [round(v, 6) for v in rect_box(sk)]
    h.shot("5-svg-moved")


# -- P6 ----------------------------------------------------------------------------------------
def p6_finish():
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")


p6_finish.wait_ms = 1000


def p6_undo():
    t.ctrl("z")


p6_undo.wait_ms = 1200


def p6_redo():
    h.check("P6 Ctrl+Z: no sketch", sketch() is None, [o.Label for o in i.sketches()])
    t.ctrl("y")


p6_redo.wait_ms = 1200


def p6_check():
    sk = sketch()
    h.check(
        "P6 Ctrl+Y: back, the same",
        sk is not None and [round(v, 6) for v in rect_box(sk)] == s["geometry"],
        sk and rect_box(sk),
    )
    if sk is not None:
        sk.ViewObject.Visibility = False


# -- P7 ----------------------------------------------------------------------------------------
def p7_canvas():
    i.use_file(i.fixture("canvas.png"))
    h.fit()
    i.menu("INSERT", "Canvas")


def p7_click_xy():
    h.click(i.XY_CLICK)


p7_click_xy.wait_ms = 1500


def p7_turn():
    p = panel()
    canvases = i.canvases()
    h.check("P7 a canvas", len(canvases) == 1)
    h.check("P7 four handles", p is not None and len(getattr(p, "handles", [])) == 4)
    if p is None or not canvases:
        return
    obj = canvases[0]
    h.check(
        "P7 the manipulator at the picture's middle",
        x.near3(tuple(p.handle_point()), tuple(obj.Placement.Base), 1e-6),
        (p.handle_point(), obj.Placement.Base),
    )
    drag_turn(35.0)


p7_turn.wait_ms = 1500


def p7_fit():
    h.fit()


p7_fit.wait_ms = 800


def p7_move_y():
    obj = i.canvases()[0]
    h.check("P7 the curved handle turned it (counter-clockwise)", obj.ZAngle > 10.0, obj.ZAngle)
    drag_arrow("y", 6.0)


p7_move_y.wait_ms = 1500


def p7_ok():
    obj = i.canvases()[0]
    h.check("P7 the Y arrow moved it", obj.YDistance > 3.0, obj.YDistance)
    s["canvas"] = (obj.XDistance, obj.YDistance, obj.ZAngle, obj.ScaleX, obj.ScaleY)
    h.shot("7-canvas")
    h.task_button("OK")


p7_ok.wait_ms = 1200


# -- P8 ----------------------------------------------------------------------------------------
def p8_edit():
    obj = i.canvases()[0]
    h.check("P8 OK kept the canvas", panel() is None and obj.ZAngle == s["canvas"][2])
    t.row_menu(obj.Label, "Edit Canvas")


p8_edit.wait_ms = 1500


def p8_scale():
    p = panel()
    obj = i.canvases()[0]
    h.check(
        "P8 Edit Canvas opened with handles", p is not None and len(getattr(p, "handles", [])) == 4
    )
    if p is None:
        return
    h.check(
        "P8 the handles where the picture is now",
        x.near3(tuple(p.handle_point()), tuple(obj.Placement.Base), 1e-6),
        (p.handle_point(), obj.Placement.Base),
    )
    drag_arrow("scale", 8.0)


p8_scale.wait_ms = 1500


def p8_fit():
    # a step of its own: the value boxes follow the handles to their new place on the
    # screen before the drag (a box left where the arrow was would take the press)
    h.fit()


p8_fit.wait_ms = 800


def p8_escape():
    obj = i.canvases()[0]
    h.check("P8 the scale arrow scaled it", obj.ScaleX > 1.1, obj.ScaleX)
    h.check("P8 in proportion", abs(obj.ScaleX - obj.ScaleY) < 1e-9, (obj.ScaleX, obj.ScaleY))
    h.press(QtCore.Qt.Key_Escape)


p8_escape.wait_ms = 1200


def p8_check():
    obj = i.canvases()[0]
    now = (obj.XDistance, obj.YDistance, obj.ZAngle, obj.ScaleX, obj.ScaleY)
    h.check("P8 Esc: as it was", panel() is None and now == s["canvas"], (now, s["canvas"]))
    obj.ViewObject.Visibility = False


# -- P9 ----------------------------------------------------------------------------------------
def p9_dxf():
    i.use_file(i.fixture("plate.dxf"))
    h.fit()
    i.menu("INSERT", "Insert DXF")


def p9_click_xy():
    h.click(i.XY_CLICK)


p9_click_xy.wait_ms = 1500


def p9_drag():
    p = panel()
    h.check("P9 four handles", p is not None and len(getattr(p, "handles", [])) == 4)
    if p is None or not p.handles:
        return
    h.check(
        "P9 the manipulator at the DXF's origin",
        x.near3(tuple(p.handle_point()), (0, 0, 0), 1e-6),
        p.handle_point(),
    )
    s["dxf_sketch"] = sketch().Name if sketch() is not None else None
    h.fit()


p9_drag.wait_ms = 800


def p9_drag_x():
    # a step of its own after the fit (as P8's): the value boxes follow the handles to
    # their new place first; dragged in the fit's step, a box left where the arrow was
    # took the press and X stayed 0 (CI #136 re-run, #137, with FreeCAD's own layout)
    if panel() is not None and panel().handles:
        drag_arrow("x", 6.0)


p9_drag_x.wait_ms = 1500


def p9_cancel():
    p = panel()
    sk = sketch()
    if p is not None and sk is not None:
        dx = p.dx.value()
        box = rect_box(sk)
        h.check("P9 X Distance followed", dx > 3.0, dx)
        h.check(
            "P9 the DXF moved by it (5..35 + X)",
            box is not None and x.near3(box, (5 + dx, 5, 35 + dx, 25), 1e-3),
            (dx, box),
        )
    h.task_button("Cancel")


p9_cancel.wait_ms = 1200


def p9_check():
    doc = App.ActiveDocument
    h.check("P9 Cancel: no DXF sketch", doc.getObject(s.get("dxf_sketch") or "") is None)
    h.check("P9 the dialog closed", panel() is None)
    i.no_file()
    h.shot("9-end")


def cleanup():
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)
    h.new_errors()


h.run(
    "exchange2_manip",
    [
        setup,
        p1_open,
        p1_click_xy,
        p1_check,
        p2_drag_x,
        p2_check,
        p3_turn,
        p3_check,
        p4_scale,
        p4_check,
        p5_type,
        p5_check,
        p6_finish,
        p6_undo,
        p6_redo,
        p6_check,
        p7_canvas,
        p7_click_xy,
        p7_fit,
        p7_turn,
        p7_move_y,
        p7_ok,
        p8_edit,
        p8_fit,
        p8_scale,
        p8_escape,
        p8_check,
        p9_dxf,
        p9_click_xy,
        p9_drag,
        p9_drag_x,
        p9_cancel,
        p9_check,
        cleanup,
    ],
)
