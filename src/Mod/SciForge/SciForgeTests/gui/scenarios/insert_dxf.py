# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert DXF (INSERT menu) into a sketch with its layers, then extrude; only real input.

Fixture: plate.dxf, layer "Outline" (a 30 x 20 rectangle, 5..35 x 5..25) and layer "Holes"
(a 10 mm circle at (20, 15)), in mm.

A  INSERT > Insert DXF: the dialog waits; click the XY square: a sketch with 5 fixed curves;
   the layer list shows Outline (4 curves) and Holes (1 curves), both ticked.
B  Untick Holes: 4 curves. Tick it: 5.
C  Insert Mode One Sketch per Layer: two sketches, "plate Outline" (4) and "plate Holes" (1);
   Single Sketch again: one sketch with 5.
D  Units Inch (the file's numbers taken as inches): rectangle 127..889. As in the file: 5..35.
E  OK (the sketch opens), Finish Sketch, E, click inside the plate beside the hole, 5, OK:
   2607.3 mm3.
F  Ctrl+Z twice: no sketch; Ctrl+Y twice: 2607.3.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import insert_steps as i

V = App.Vector


def rect_box(sk):
    xs, ys = [], []
    for geo in sk.Geometry:
        if geo.TypeId == "Part::GeomLineSegment":
            for p in (geo.StartPoint, geo.EndPoint):
                xs.append(round(p.x, 3))
                ys.append(round(p.y, 3))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def counts():
    return [(sk.Label, sk.GeometryCount) for sk in i.sketches()]


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.use_file(i.fixture("plate.dxf"))
    h.fit()
    i.menu("INSERT", "Insert DXF")


def a_waits():
    p = i.panel()
    h.check("Insert DXF dialog", p is not None and p.title == "Insert DXF", p)
    s.no_popups("Insert DXF")
    if p is not None:
        rows = [p.layer_list.item(k).text() for k in range(p.layer_list.count())]
        h.check("layers listed", rows == ["Outline (4 curves)", "Holes (1 curves)"], rows)
        h.check(
            "Units: as in the file",
            p.units.currentText() == "As in the file",
            p.units.currentText(),
        )


def a_click_xy():
    pl.click_on_plane(i.XY_CLICK)


a_click_xy.wait_ms = 1200


def a_check():
    h.check("one sketch with 5 curves", counts() and counts()[0][1] == 5, counts())
    sk = i.sketches()[0] if i.sketches() else None
    if sk is not None:
        h.check("rectangle 5..35 x 5..25", rect_box(sk) == (5, 5, 35, 25), rect_box(sk))
        h.check("all fixed", i.block_constraints(sk) == 5, i.block_constraints(sk))


# -- B ----------------------------------------------------------------------------------------
def b_untick_holes():
    p = i.panel()
    if p is not None:
        i.check_list_item(p.layer_list, 1, False)


def b_check_untick():
    h.check("without Holes: 4 curves", counts() and counts()[0][1] == 4, counts())


def b_tick_holes():
    p = i.panel()
    if p is not None:
        i.check_list_item(p.layer_list, 1, True)


def b_check_tick():
    h.check("with Holes again: 5 curves", counts() and counts()[0][1] == 5, counts())


# -- C ----------------------------------------------------------------------------------------
def c_per_layer():
    p = i.panel()
    if p is not None:
        b.choose(p.mode, "One Sketch per Layer")


c_per_layer.wait_ms = 1200


def c_check_per_layer():
    got = sorted(counts())
    h.check("two sketches, one per layer", got == [("plate Holes", 1), ("plate Outline", 4)], got)


def c_single():
    p = i.panel()
    if p is not None:
        b.choose(p.mode, "Single Sketch")


c_single.wait_ms = 1200


def c_check_single():
    h.check("one sketch with 5 again", len(counts()) == 1 and counts()[0][1] == 5, counts())


# -- D ----------------------------------------------------------------------------------------
def d_inch():
    p = i.panel()
    if p is not None:
        b.choose(p.units, "Inch")


def d_check_inch():
    sk = i.sketches()[0] if i.sketches() else None
    h.check("inch: 127..889", sk and rect_box(sk) == (127, 127, 889, 635), sk and rect_box(sk))


def d_back():
    p = i.panel()
    if p is not None:
        b.choose(p.units, "As in the file")


def d_check_back():
    sk = i.sketches()[0] if i.sketches() else None
    h.check("as in the file: 5..35", sk and rect_box(sk) == (5, 5, 35, 25), sk and rect_box(sk))


# -- E ----------------------------------------------------------------------------------------
def e_ok():
    h.task_button("OK")


e_ok.wait_ms = 1200


def e_finish():
    h.check("dialog closed", i.panel() is None)
    h.check("sketch open for editing", h.in_sketch() is not None)
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")


def e_extrude():
    h.fit()
    h.press("e")


def e_click_region():
    h.click(V(10, 10, 0))


def e_distance():
    panel = b.active_panel()
    field = getattr(getattr(panel, "distance", None), "widget", None)
    if h.check("extrude dialog", field is not None):
        b.type_into(field, "5")
        from PySide6 import QtTest

        QtTest.QTest.keyClick(field, QtCore.Qt.Key_Tab)


e_distance.wait_ms = 1200


def e_extrude_ok():
    h.task_button("OK")


def e_check():
    volume = s.total_volume()
    h.check("plate with a hole: 2607.3 mm3", i.close(volume, i.DRAWING_AREA * 5, 1e-3), volume)


# -- F ----------------------------------------------------------------------------------------
def f_undo_twice():
    i.undo()
    i.undo()


def f_check_undo():
    h.check("two Ctrl+Z: no sketch", not i.sketches(), counts())


def f_redo_twice():
    i.redo()
    i.redo()


def f_check_redo():
    volume = s.total_volume()
    h.check("two Ctrl+Y: 2607.3", i.close(volume, i.DRAWING_AREA * 5, 1e-3), volume)
    i.no_file()
    h.shot("end")


h.run(
    "insert_dxf",
    [
        i.new_design("InsertDxf"),
        a_open,
        a_waits,
        a_click_xy,
        a_check,
        b_untick_holes,
        b_check_untick,
        b_tick_holes,
        b_check_tick,
        c_per_layer,
        c_check_per_layer,
        c_single,
        c_check_single,
        d_inch,
        d_check_inch,
        d_back,
        d_check_back,
        e_ok,
        e_finish,
        e_extrude,
        e_click_region,
        e_distance,
        e_extrude_ok,
        e_check,
        f_undo_twice,
        f_check_undo,
        f_redo_twice,
        f_check_redo,
    ],
)
