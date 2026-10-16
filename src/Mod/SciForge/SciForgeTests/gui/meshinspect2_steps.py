# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the mesh-inspect-2 scenarios (scenarios/meshinspect2_*.py): the Direct
Edit dialog, the faces it picks, points on the test sphere that face the camera. Real input
only: clicks, drags and keys on the 3D view, buttons and fields of the dialog."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import mesh_steps as m

V = App.Vector
R = 10.0  # the test sphere's radius (mesh_steps.sphere_triangles)


def grid_box_triangles(sx=20.0, sy=20.0, sz=10.0, n=4):
    """A box sx x sy x sz from the origin whose every side is an n x n grid of squares (two
    triangles each), facing out: enough faces to paint over, flat sides for face groups."""

    def side(origin, u, v):
        tris = []
        for i in range(n):
            for j in range(n):
                p = [
                    tuple(origin[k] + u[k] * (i + a) / n + v[k] * (j + b) / n for k in range(3))
                    for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))
                ]
                tris.append((p[0], p[1], p[2]))
                tris.append((p[0], p[2], p[3]))
        return tris

    o = (0.0, 0.0, 0.0)
    X, Y, Z = (sx, 0.0, 0.0), (0.0, sy, 0.0), (0.0, 0.0, sz)
    tris = []
    tris += side(o, Y, X)  # bottom (faces -Z)
    tris += side((0.0, 0.0, sz), X, Y)  # top (+Z)
    tris += side(o, X, Z)  # front (-Y)
    tris += side((0.0, sy, 0.0), Z, X)  # back (+Y)
    tris += side(o, Z, Y)  # left (-X)
    tris += side((sx, 0.0, 0.0), Y, Z)  # right (+X)
    return tris


def panel():
    return m.panel()


def direct_panel():
    p = panel()
    return p if p is not None and getattr(p, "step_kind", "") == "MeshDirectEdit" else None


def look():
    """The view direction (into the screen), unit."""
    d = V(Gui.ActiveDocument.ActiveView.getViewDirection())
    d.normalize()
    return d


def screen_axes():
    """(right, up) of the camera, unit."""
    rot = Gui.ActiveDocument.ActiveView.getCameraOrientation()
    return rot.multVec(V(1, 0, 0)), rot.multVec(V(0, 1, 0))


def on_sphere(right=0.0, up=0.0, radius=R, centre=V(0, 0, 0)):
    """A point of the sphere seen from the camera: the one facing it straight on, moved
    `right` / `up` (fractions of the radius) across the screen."""
    r, u = screen_axes()
    d = look() * -1.0 + r * right + u * up
    d.normalize()
    return centre + d * radius


def front_extent(obj):
    """How far the body reaches towards the camera (mm)."""
    from sciforge import mesh

    points = mesh.global_mesh(obj).Topology[0]
    toward = look() * -1.0
    return max(p.dot(toward) for p in points)


def facing_all(p, indices):
    """True when every face of `indices` faces the camera."""
    state = p.work()[0]
    from sciforge import mesh_core as core

    d = tuple(look())
    for i in indices:
        n = core.facet_normal(state.points, state.facets[i])
        if core.dot(n, d) >= 0:
            return False
    return True


def button(p, name):
    widget = p.form.findChild(QtWidgets.QPushButton, "SciForgeDirectEdit_" + name)
    h.check("Direct Edit button %s" % name, widget is not None)
    return widget


def press_button(p, name):
    widget = button(p, name)
    if widget is not None:
        b.click_widget(widget)
        QtWidgets.QApplication.processEvents()


def choose(p, name, text):
    combo = p.form.findChild(QtWidgets.QComboBox, "SciForgeDirectEdit_" + name)
    if h.check("Direct Edit list %s" % name, combo is not None):
        b.choose(combo, text)
        QtWidgets.QApplication.processEvents()


def key(k, modifiers=QtCore.Qt.NoModifier):
    """A key over the 3D view (Del, Shift+Up, Alt+G ...)."""
    h.press(k, modifiers)


def drag_screen(a, b_, steps=14, modifiers=QtCore.Qt.NoModifier):
    """Drag the left button from 3D point a to 3D point b over the view (panned clear of
    the dialog first, as a person would)."""
    h.uncover(a)
    h.uncover(b_)
    h.drag(h.screen_point(a), h.screen_point(b_), steps=steps, modifiers=modifiers)


def drag_box(centre, half_px, right_to_left=False):
    """A box drag around the 3D point `centre`, `half_px` pixels each way."""
    h.uncover(centre)
    c = h.screen_point(centre)
    a = QtCore.QPoint(c.x() - half_px, c.y() - half_px)
    z = QtCore.QPoint(c.x() + half_px, c.y() + half_px)
    if right_to_left:
        a, z = QtCore.QPoint(z.x(), a.y()), QtCore.QPoint(a.x(), z.y())
    h.drag(a, z, steps=12)


def lasso(centre, radius_px, corners=20):
    """Draw round the 3D point `centre` with the left button held (Free Form selection): a
    circle of `radius_px` pixels, back to where it started."""
    from PySide import QtGui

    h.uncover(centre)
    c = h.screen_point(centre)
    widget = h.gl_widget()
    pts = [
        QtCore.QPoint(
            int(round(c.x() + radius_px * math.cos(2 * math.pi * k / corners))),
            int(round(c.y() + radius_px * math.sin(2 * math.pi * k / corners))),
        )
        for k in range(corners + 1)
    ]
    h.move(pts[0])
    QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pts[0])
    for p in pts[1:]:
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(p),
            QtCore.QPointF(widget.mapToGlobal(p)),
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pts[-1])
    QtWidgets.QApplication.processEvents()


def edits(p):
    return p.edit_list.count()


def set_double(spin, value):
    from SciForgeTests.gui import insert_steps as i

    i.set_spin(spin, value)


def tab():
    QtTest.QTest.keyClick(QtWidgets.QApplication.focusWidget(), QtCore.Qt.Key_Tab)


def angle_between(a, b_):
    a, b_ = V(a), V(b_)
    if a.Length < 1e-12 or b_.Length < 1e-12:
        return None
    return math.degrees(a.getAngle(b_))
