# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Viewports, Pan, Zoom and Zoom Window with real input. Multiple Views:
four panes (Top, Front, Right and the 3D view that was there), a click in a pane makes it
the active one; Two Views Horizontal (side by side), Two Views Vertical (one above the
other), Single View (one tabbed view again, the extra views closed, the first one kept);
Shift+1 switches Multiple Views on and off. Pan: the hand moves the view with the mouse
(the model follows the pointer: the camera moves the other way by the dragged pixels times
the view's millimetres per pixel); Esc ends it. Zoom: a drag up of 160 pixels halves the
view's size; a right click ends it. Zoom Window: a box round the upper left quarter fills
the view (half the size, its middle moves to the box's middle) and the command ends.

The part: the 40 x 30 x 10 box."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import nav_input as n
from SciForgeTests.gui import widget_input as w

V = App.Vector
st = {}
VP = "Viewports"


def area():
    return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)


def views():
    return list(Gui.ActiveDocument.mdiViewsOfType("Gui::View3DInventor"))


def panes():
    """Shown 3D sub-windows of the design, (left, top) first."""
    found = []
    for sub in area().subWindowList():
        widget = sub.widget()
        if widget is None or widget.metaObject().className() != "Gui::View3DInventor":
            continue
        if sub.isVisible():
            found.append(sub)
    return sorted(found, key=lambda s: (s.geometry().top(), s.geometry().left()))


def gl_of(sub):
    for widget in sub.findChildren(QtWidgets.QWidget):
        if widget.metaObject().className() == "QOpenGLWidget":
            return widget
    return None


def direction(view):
    d = view.getViewDirection()
    return tuple(round(float(x), 3) for x in d)


def layout():
    from sciforge import viewports_ui

    return viewports_ui.current()


# -- viewports ----------------------------------------------------------------------------------
def multiple():
    st["iso"] = direction(h.view())
    n.choose(VP, "Multiple Views")


def four():
    subs = panes()
    h.check("Multiple Views", layout() == "Multiple Views")
    h.check("four panes", len(subs) == 4, len(subs))
    h.check("tiled, not tabbed", area().viewMode() == QtWidgets.QMdiArea.SubWindowView)
    if len(subs) == 4:
        g = [s.geometry() for s in subs]
        h.check(
            "two rows of two",
            g[0].top() == g[1].top()
            and g[2].top() == g[3].top()
            and g[0].left() == g[2].left()
            and g[0].top() < g[2].top(),
        )
        h.check("they fill the area", g[3].right() >= area().viewport().width() - 3)
    dirs = sorted(direction(v) for v in views())
    expect = sorted([(0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), st["iso"]])
    h.check("Top, Front, Right and the 3D view", dirs == expect, dirs)
    h.check("Multiple Views ticked", n.entry_state(VP, "Multiple Views") == (True, True))
    h.shot("1-multiple")
    if len(subs) == 4:
        st["pane"] = subs[1]
        gl = gl_of(subs[1])
        w.click(gl, QtCore.QPoint(10, gl.height() - 10))


def pane_active():
    h.check("a click in a pane makes it the active one", area().activeSubWindow() is st.get("pane"))
    h.check("the active view is that pane's", direction(h.view()) != st["iso"], direction(h.view()))
    n.choose(VP, "Two Views Horizontal")


def two_h():
    subs = panes()
    h.check("Two Views Horizontal", layout() == "Two Views Horizontal")
    h.check(
        "two panes side by side",
        len(subs) == 2
        and subs[0].geometry().top() == subs[1].geometry().top()
        and subs[0].geometry().left() < subs[1].geometry().left(),
        [s.geometry() for s in subs],
    )
    h.check("three views were closed, one made", len(views()) == 2, len(views()))
    n.choose(VP, "Two Views Vertical")


def two_v():
    subs = panes()
    h.check("Two Views Vertical", layout() == "Two Views Vertical")
    h.check(
        "one above the other",
        len(subs) == 2
        and subs[0].geometry().left() == subs[1].geometry().left()
        and subs[0].geometry().top() < subs[1].geometry().top(),
        [s.geometry() for s in subs],
    )
    n.choose(VP, "Single View")


def single():
    h.check("Single View", layout() == "Single View")
    h.check("tabs again", area().viewMode() == QtWidgets.QMdiArea.TabbedView)
    h.check("one 3D view of the design", len(views()) == 1, len(views()))
    h.check("the first view kept its camera", direction(h.view()) == st["iso"], direction(h.view()))
    h.press(QtCore.Qt.Key_1, QtCore.Qt.ShiftModifier)


def shift_1():
    h.check("Shift+1: Multiple Views", layout() == "Multiple Views", layout())
    h.press(QtCore.Qt.Key_1, QtCore.Qt.ShiftModifier)


def shift_1_again():
    h.check("Shift+1 again: one view", layout() == "Single View", layout())
    h.check("one 3D view", len(views()) == 1)
    h.fit()
    n.click("Pan")


# -- Pan, Zoom, Zoom Window ------------------------------------------------------------------
def camera():
    cam = h.view().getCameraNode()
    pos = cam.position.getValue()
    return tuple(float(x) for x in pos), float(cam.height.getValue())


def pan_drag():
    from sciforge import navigate_ui

    h.check("Pan is on", navigate_ui.mode() == "pan")
    st["before"] = camera()
    gl = h.gl_widget()
    c = gl.rect().center()
    h.drag(c, QtCore.QPoint(c.x() + 100, c.y()), steps=10)


def panned():
    (p0, height), p1 = st["before"], camera()[0]
    gl = h.gl_widget()
    moved = V(*p1) - V(*p0)
    right = h.view().getCameraOrientation().multVec(V(1, 0, 0))
    expect = -100 * height / gl.height()
    h.check(
        "the camera moved left by the dragged pixels' millimetres",
        abs(moved.dot(right) - expect) < 0.02 * abs(expect),
        (moved.dot(right), expect),
    )
    h.check("only sideways", abs(moved.Length - abs(moved.dot(right))) < 1e-6)
    h.press(QtCore.Qt.Key_Escape)


def pan_ended():
    from sciforge import navigate_ui

    h.check("Esc ends Pan", navigate_ui.mode() is None)
    n.choose("Zoom", "Zoom")


def zoom_drag():
    st["before"] = camera()
    gl = h.gl_widget()
    c = gl.rect().center()
    h.drag(c, QtCore.QPoint(c.x(), c.y() - 160), steps=10)


def zoomed():
    from sciforge import navigate_ui

    height0, height1 = st["before"][1], camera()[1]
    h.check(
        "a drag up of 160 pixels: half the size",
        abs(height1 / height0 - 0.5) < 0.01,
        (height0, height1),
    )
    gl = h.gl_widget()
    w.click(gl, gl.rect().center(), button=QtCore.Qt.RightButton)
    h.check("still on before the right click", navigate_ui.mode() in ("zoom", None))


def zoom_ended():
    from sciforge import navigate_ui

    h.check("a right click ends Zoom", navigate_ui.mode() is None)
    from SciForgeTests.gui import harness

    harness.close_popups()
    h.fit()
    n.choose("Zoom", "Zoom Window")


def window_drag():
    from sciforge import navigate_ui

    h.check("Zoom Window is on", navigate_ui.mode() == "window")
    st["before"] = camera()
    gl = h.gl_widget()
    width, height = gl.width(), gl.height()
    h.drag(QtCore.QPoint(2, 2), QtCore.QPoint(width // 2 + 2, height // 2 + 2), steps=10)


def windowed():
    from sciforge import navigate_ui

    (p0, height0), (p1, height1) = st["before"], camera()
    h.check(
        "the box fills the view: half the size",
        abs(height1 / height0 - 0.5) < 0.02,
        (height0, height1),
    )
    moved = V(*p1) - V(*p0)
    up = h.view().getCameraOrientation().multVec(V(0, 1, 0))
    h.check("the middle moved up and left", moved.dot(up) > 0, moved)
    h.check("Zoom Window ends by itself", navigate_ui.mode() is None)


h.run(
    "navbar_viewports",
    b.box_steps("Viewports")
    + [
        multiple,
        four,
        pane_active,
        two_h,
        two_v,
        single,
        shift_1,
        shift_1_again,
        pan_drag,
        panned,
        pan_ended,
        zoom_drag,
        zoomed,
        zoom_ended,
        window_drag,
        windowed,
    ],
)
