# SPDX-License-Identifier: LGPL-2.1-or-later
"""The test helpers click a 3D point that the command dialog covers like a person would:
they pan the view until the point is clear, then click it.

The dialog floats over the right of the 3D view and its width depends on the machine's
fonts: on GitHub's runner it covered a box corner that the local run could click, and
inspect_qa8's clicks there went to the dialog (it said "on top: TaskPanel"). Here the
points are put under the dialog on purpose (checked: the dialog is on top there):

  V  Plane Through Three Points: the corner (40, 30, 10) under the dialog, clicked with
     the corner helper, then (0, 0, 10) and (40, 0, 10): the top plane z = 10.
  F  Center of Mass: the top face's point (30, 20, 10) under the dialog, clicked with the
     plain click helper: the box is picked, its centre (20, 15, 5).

Part: box 40 x 30 x 10 from the origin (real input)."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}


def dialog_rect():
    """The command dialog's rectangle in the 3D view's pixels, or None."""
    gl = h.gl_widget()
    for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::TaskView::TaskPanel" and w.isVisible():
            return QtCore.QRect(gl.mapFromGlobal(w.mapToGlobal(QtCore.QPoint(0, 0))), w.size())
    return None


def put_under_dialog(point, label):
    """Pan the view so the 3D point shows under the middle of the dialog."""
    rect = dialog_rect()
    if not h.check("%s: the dialog is shown over the view" % label, rect is not None):
        return
    pos = h.screen_point(point)
    h.pan(rect.center().x() - pos.x(), rect.center().y() - pos.y())
    pos = h.screen_point(point)
    h.check("%s: the point is under the dialog now" % label, h.covered(pos) is not None, pos)


# -- V: corners under the dialog ---------------------------------------------------------------
def v_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Through Three Points")


def v_hide():
    h.fit()
    put_under_dialog(V(40, 30, 10), "V")


def v_p1():
    h.check("V the hidden corner is clicked", s.click_vertex(V(40, 30, 10)), h.state["last_click"])


def v_p2():
    p = s.construct_panel()
    first = p.picks[0] if p else None
    h.check(
        "V the hidden corner is the first point",
        first is not None and first[2] is not None and (first[2] - V(40, 30, 10)).Length < 1e-6,
        (p and p.picks, h.state["last_click"]),
    )
    h.fit()
    s.click_vertex(V(0, 0, 10))


def v_p3():
    s.click_vertex(V(40, 0, 10))


def v_plane():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("V three corners: a plane", d is not None, p and p.picks)
    if d is not None:
        n = s.normal_of(d)
        h.check("V the top plane", abs(abs(n.z) - 1.0) < 1e-9, n)
        h.check("V at z = 10", s.close(d.getGlobalPlacement().Base.z, 10.0))
    h.press(QtCore.Qt.Key_Escape)


# -- F: a face point under the dialog ----------------------------------------------------------
def f_start():
    h.check("V closed", not Gui.Control.activeDialog())
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def f_hide():
    h.fit()
    put_under_dialog(V(30, 20, 10), "F")


def f_click():
    h.click(V(30, 20, 10))


def f_picked():
    p = b.active_panel()
    if not h.check("F Center of Mass open", p is not None and hasattr(p, "coords")):
        return
    h.check("F the box picked", len(p.picked) == 1, (p.picked, h.state["last_click"]))
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("F its centre", got == ["20.000 mm", "15.000 mm", "5.000 mm"], got)
    h.press(QtCore.Qt.Key_Escape)


def f_closed():
    h.check("F closed", not Gui.Control.activeDialog())


h.run(
    "harness_covered_click",
    b.box_steps("CoveredClick")
    + [v_start, v_hide, v_p1, v_p2, v_p3, v_plane]
    + [f_start, f_hide, f_click, f_picked, f_closed],
)
