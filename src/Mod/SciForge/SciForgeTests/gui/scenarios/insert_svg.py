# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert SVG (INSERT menu) into a sketch, then extrude it; only real input.

Fixture: shape.svg, a 30 x 20 mm rectangle (5..35 x 5..25) with a round 10 mm hole at
(20, 15). Fusion centres the SVG on the sketch origin (help "Insert SVG": "the image
geometry is centered on the sketch origin"), so it lands at -15..15 x -10..10, the hole at
the origin.

A  INSERT > Insert SVG: the dialog waits for a plane; click the XY square: a sketch with 5
   fixed curves (Block constraints), rectangle -15..15 x -10..10, the circle round (0, 0).
B  Scale 2: -30..30 x -20..20. Vertical Flip (about the middle): the same box. X Distance
   10: X -20..40. Back to scale 1, flip off, X 0.
C  OK: the dialog closes, the sketch stays and is open for editing; Finish Sketch.
D  E, click inside the rectangle beside the hole, 5, OK: (600 - 25 pi) x 5 = 2607.3 mm3.
E  Ctrl+Z twice (the extrude, then the whole insert): no sketch; Ctrl+Y twice: 2607.3 again.
F  Create Sketch on XZ, then Insert SVG with that sketch open: the curves go into it
   (5 curves); OK brings the sketch back; Finish Sketch.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import insert_steps as i

V = App.Vector
state = {}


def sketch():
    found = i.sketches()
    return found[-1] if found else None


def rect_box(sk):
    """Bounds of the sketch's straight lines (the rectangle)."""
    xs, ys = [], []
    for geo in sk.Geometry:
        if geo.TypeId == "Part::GeomLineSegment":
            for p in (geo.StartPoint, geo.EndPoint):
                xs.append(round(p.x, 3))
                ys.append(round(p.y, 3))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def circle_center(sk):
    for geo in sk.Geometry:
        if geo.TypeId == "Part::GeomCircle":
            return (round(geo.Center.x, 3), round(geo.Center.y, 3))
    return None


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.use_file(i.fixture("shape.svg"))
    h.fit()
    i.menu("INSERT", "Insert SVG")


def a_waits():
    p = i.panel()
    h.check("Insert SVG dialog", p is not None and p.title == "Insert SVG", p)
    s.no_popups("Insert SVG")
    if p is not None:
        h.check("waits for a plane", "Click a plane" in p.plane_label.text(), p.plane_label.text())
    h.check("no sketch yet", sketch() is None)


def a_click_xy():
    pl.click_on_plane(i.XY_CLICK)


a_click_xy.wait_ms = 1200


def a_check():
    sk = sketch()
    h.check("a sketch", sk is not None)
    if sk is None:
        return
    h.check("5 curves", sk.GeometryCount == 5, sk.GeometryCount)
    h.check("all fixed (Block)", i.block_constraints(sk) == 5, i.block_constraints(sk))
    h.check("rectangle -15..15 x -10..10", rect_box(sk) == (-15, -10, 15, 10), rect_box(sk))
    h.check("circle round (0, 0)", circle_center(sk) == (0, 0), circle_center(sk))
    h.check("in the browser", i.browser_has(sk.Label), i.browser_labels())


# -- B ----------------------------------------------------------------------------------------
def b_scale():
    p = i.panel()
    if p is not None:
        i.set_spin(p.scale, 2)


def b_check_scale():
    sk = sketch()
    h.check(
        "scale 2: -30..30 x -20..20", sk and rect_box(sk) == (-30, -20, 30, 20), sk and rect_box(sk)
    )


def b_flip():
    p = i.panel()
    if p is not None:
        i.set_check(p.flip_v, True)


def b_check_flip():
    sk = sketch()
    h.check(
        "vertical flip about the middle: the same box",
        sk and rect_box(sk) == (-30, -20, 30, 20),
        sk and rect_box(sk),
    )


def b_offset():
    p = i.panel()
    if p is not None:
        i.type_value(p.dx, "10")


def b_check_offset():
    sk = sketch()
    h.check(
        "X Distance 10: X -20..40", sk and rect_box(sk) == (-20, -20, 40, 20), sk and rect_box(sk)
    )


def b_back():
    p = i.panel()
    if p is not None:
        i.set_spin(p.scale, 1)
        i.set_check(p.flip_v, False)
        i.type_value(p.dx, "0")


def b_check_back():
    sk = sketch()
    h.check(
        "back to -15..15 x -10..10", sk and rect_box(sk) == (-15, -10, 15, 10), sk and rect_box(sk)
    )
    h.check("still 5 curves", sk and sk.GeometryCount == 5, sk and sk.GeometryCount)


# -- C ----------------------------------------------------------------------------------------
def c_ok():
    h.task_button("OK")


c_ok.wait_ms = 1200


def c_check():
    h.check("dialog closed", i.panel() is None)
    sk = sketch()
    h.check("the sketch stays with 5 curves", sk is not None and sk.GeometryCount == 5)
    h.check("the sketch is open for editing", h.in_sketch() is sk and sk is not None)


def c_finish():
    h.ribbon("Finish Sketch")


# -- D ----------------------------------------------------------------------------------------
def d_extrude():
    h.fit()
    h.press("e")


def d_click_region():
    h.click(V(-10, -6, 0))


def d_distance():
    panel = b.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        b.type_into(field, "5")
        from PySide6 import QtTest

        QtTest.QTest.keyClick(field, QtCore.Qt.Key_Tab)


d_distance.wait_ms = 1200


def d_ok():
    h.task_button("OK")


def d_check():
    volume = s.total_volume()
    h.check("plate with a hole: 2607.3 mm3", i.close(volume, i.DRAWING_AREA * 5, 1e-3), volume)


# -- E ----------------------------------------------------------------------------------------
def e_undo_twice():
    i.undo()
    i.undo()


def e_check_undo():
    h.check("two Ctrl+Z: no sketch", sketch() is None, [x.Label for x in i.sketches()])
    h.check("no solid", s.total_volume() == 0.0, s.total_volume())


def e_redo_twice():
    i.redo()
    i.redo()


def e_check_redo():
    volume = s.total_volume()
    h.check("two Ctrl+Y: 2607.3 again", i.close(volume, i.DRAWING_AREA * 5, 1e-3), volume)


# -- F ----------------------------------------------------------------------------------------
def f_sketch_xz():
    h.fit()
    h.ribbon("Create Sketch")


def f_click_xz():
    pl.click_square("XZ_Plane")  # where the XZ square shows


def f_insert_in_sketch():
    sk = h.in_sketch()
    h.check("a sketch is open on XZ", sk is not None)
    state["xz"] = sk.Name if sk else None
    i.menu("INSERT", "Insert SVG")


f_insert_in_sketch.wait_ms = 1200


def f_check_in_sketch():
    p = i.panel()
    doc = App.ActiveDocument
    sk = doc.getObject(state.get("xz") or "")
    h.check("dialog open", p is not None and p.title == "Insert SVG", p)
    h.check(
        "the open sketch got the curves",
        sk is not None and sk.GeometryCount == 5,
        sk and sk.GeometryCount,
    )
    if p is not None:
        h.check(
            "plane row names the sketch", "Sketch" in p.plane_label.text(), p.plane_label.text()
        )


def f_ok():
    h.task_button("OK")


f_ok.wait_ms = 1200


def f_check_ok():
    doc = App.ActiveDocument
    sk = doc.getObject(state.get("xz") or "")
    h.check("the sketch is open again", sk is not None and h.in_sketch() is sk)
    h.check("5 curves kept", sk is not None and sk.GeometryCount == 5)


def f_finish():
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")
    i.no_file()
    h.shot("end")


h.run(
    "insert_svg",
    [
        i.new_design("InsertSvg"),
        a_open,
        a_waits,
        a_click_xy,
        a_check,
        b_scale,
        b_check_scale,
        b_flip,
        b_check_flip,
        b_offset,
        b_check_offset,
        b_back,
        b_check_back,
        c_ok,
        c_check,
        c_finish,
        d_extrude,
        d_click_region,
        d_distance,
        d_ok,
        d_check,
        e_undo_twice,
        e_check_undo,
        e_redo_twice,
        e_check_redo,
        f_sketch_xz,
        f_click_xz,
        f_insert_in_sketch,
        f_check_in_sketch,
        f_ok,
        f_check_ok,
        f_finish,
    ],
)
