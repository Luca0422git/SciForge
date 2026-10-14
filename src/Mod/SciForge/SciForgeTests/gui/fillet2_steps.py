# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the Fillet / Chamfer part 2 scenarios (scenarios/fillet2_*.py):
the dialog's selection-set rows, its "+" / "−" buttons, the radius points of a Variable
fillet, and measurements of the finished part (the radius of a round at a place, the chord
of a round). Box geometry and formulas: blend_steps."""

import math

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
SQ2 = math.sqrt(2.0)


def steps():
    """Every fillet / chamfer step of the body: FreeCAD's and SciForge's own."""
    body = h.body()
    if body is None:
        return []
    return [
        o
        for o in body.Group
        if o.TypeId in ("PartDesign::Fillet", "PartDesign::Chamfer")
        or getattr(o, "SciForgeType", "") in ("FilletSets", "ChamferSets")
    ]


def is_sets(obj):
    return getattr(obj, "SciForgeType", "") in ("FilletSets", "ChamferSets")


def spec_of(obj):
    from sciforge import fillet_sets

    return fillet_sets.read_spec(obj)


def click_row(panel, index):
    """Click row `index` of the dialog's selection-set list."""
    rows = panel.rows
    item = rows.item(index)
    if not h.check("set %d is in the list" % (index + 1), item is not None, rows.count()):
        return
    pos = rows.visualItemRect(item).center()
    QtTest.QTest.mouseClick(rows.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()


def row_texts(panel):
    return [panel.rows.item(i).text() for i in range(panel.rows.count())]


def click_check(box):
    """Click a check box on its tick square, as a person does (a box without text toggles
    only there)."""
    style = box.style()
    option = QtWidgets.QStyleOptionButton()
    box.initStyleOption(option)
    rect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, option, box)
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
    QtWidgets.QApplication.processEvents()


def press_plus(panel):
    b.click_widget(panel.add_row_button)


def radius_at(point, faces_normals=None):
    """The radius of the round on a 90 degree box edge at `point` (the old corner): the
    round passes (sqrt(2) - 1) R from the corner."""
    import Part

    shape = h.body().Shape
    d = shape.distToShape(Part.Vertex(point))[0]
    return d / (SQ2 - 1.0)


def round_chord(kind="Cylinder", length=None):
    """The chord of the round face: the distance between its two straight edges (where it
    meets the faces next to it), or None."""
    shape = h.body().Shape
    for face in shape.Faces:
        if type(face.Surface).__name__ != kind:
            continue
        lines = [e for e in face.Edges if type(e.Curve).__name__ in ("Line", "LineSegment")]
        if length is not None:
            lines = [e for e in lines if abs(e.Length - length) < 1e-4]
        if len(lines) == 2:
            return lines[0].distToShape(lines[1])[0]
    return None


def type_point(panel, k, position=None, radius=None):
    """Type a radius point's position and / or radius into its row."""
    spin, field, _button = panel.point_rows[k]
    if position is not None:
        spin.setFocus()
        QtTest.QTest.mouseClick(spin, QtCore.Qt.LeftButton)
        QtTest.QTest.keyClick(spin, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        QtTest.QTest.keyClicks(spin, "%g" % position)
        QtTest.QTest.keyClick(spin, QtCore.Qt.Key_Tab)
        QtWidgets.QApplication.processEvents()
    if radius is not None:
        b.type_into(field.widget, "%g" % radius)
        QtTest.QTest.keyClick(field.widget, QtCore.Qt.Key_Tab)
        QtWidgets.QApplication.processEvents()


def report_errors():
    """Kernel / fillet errors printed to the Report view (there must be none). picks.py's
    note that it found a lost edge again is information, not an error."""
    return [line for line in b.report_has_kernel_errors() if "found again" not in line]
