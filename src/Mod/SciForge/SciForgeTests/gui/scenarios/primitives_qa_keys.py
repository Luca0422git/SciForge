# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA, the keyboard of a Fusion power user (only real input).

K1. Box on XY, first corner on the origin; with the mouse over the 3D view type 3 0:
    the number goes into Length (Fusion's box next to the mouse), the view does not jump
    to FreeCAD's "right" view (key 3); Tab, 2 0 into Width, Enter: placed 30 x 20 (the
    mouse only says on which side). Over the view again: - 5 goes into the Height
    handle's value box (Fusion's box next to the arrow); Enter takes it and is OK:
    30 x 20 x 5 below the plane.
K2. Cylinder: the centre at (50, 10), then 1 2 over the view, Enter: diameter 12 (the
    mouse is 5 mm away: the typed value wins). 8 over the view goes into the Height
    handle's box; Enter.
K3. Sphere: 6 typed over the view before the centre click: the click places a sphere of
    diameter 6 (not the size worked out from the zoom). Enter.
K4. Another command's key while a dialog is open: Torus, plane, centre, then E: the
    torus is not placed, so it is dropped and Extrude opens (no error, no torus); Esc.
    Box placed 10 x 10 (not OK'd yet), then Q: Fusion keeps the box and Press Pull
    starts; Esc closes Press Pull. Ctrl+Z takes the box away, Ctrl+Y brings it back.
K5. Esc in the middle of the pick: Cylinder, plane, centre, Esc: nothing is left.

Hand-derived volumes: box 30 x 20 x 5 = 3000; cylinder d12 h8 = 288 pi; sphere d6 = 36 pi;
box 10 x 10 x 10 = 1000.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
PI = math.pi
s = {}


def doc():
    return App.ActiveDocument


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def camera():
    return tuple(round(q, 6) for q in h.view().getCameraOrientation().Q)


def keys_to_focus(text, enter=False):
    """Keys on whatever has the keyboard focus now (after the first digit over the view
    the dialog's field has it, as with a real keyboard)."""
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    QtTest.QTest.keyClicks(target, text)
    if enter:
        target = QtWidgets.QApplication.focusWidget() or target
        QtTest.QTest.keyClick(target, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def key_to_focus(key):
    target = QtWidgets.QApplication.focusWidget() or h.gl_widget()
    QtTest.QTest.keyClick(target, key)
    QtWidgets.QApplication.processEvents()


def body_count():
    return len(pi.bodies())


def box_text(p, key):
    """What the value box of the handle `key` holds while it has the keyboard (digits typed
    over the 3D view go there once the shape is placed, like Fusion's box next to the
    arrow; the dialog's field takes the value on Enter), else None."""
    try:
        box = p.value_boxes.current() if p is not None else None
        if box is None or box is not p.value_boxes.boxes.get(key) or not box.hasFocus():
            return None
        return box.text().strip()
    except Exception:
        return None


# == K1: Box, sizes typed over the view =====================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PrimQAKeys")
    h.fit()
    pi.menu("Box")


def k1_plane():
    h.click(V(15, -15, 0))


def k1_corner():
    h.click(V(0, 0, 0))


def k1_mouse():
    pi.hover(V(6, 4, 0))
    pi.hover(V(8, 6, 0))
    s["camera"] = camera()


def k1_type_length():
    h.press("3")


def k1_length_more():
    p = pi.panel("BoxPanel")
    h.check("K1 the view did not jump (FreeCAD's key 3)", camera() == s["camera"])
    h.check(
        "K1 3 went into Length",
        p is not None and near(p.length.value(), 3.0),
        p and p.length.value(),
    )
    keys_to_focus("0")


def k1_tab():
    p = pi.panel("BoxPanel")
    h.check("K1 Length 30", p is not None and near(p.length.value(), 30.0), p and p.length.value())
    key_to_focus(QtCore.Qt.Key_Tab)
    keys_to_focus("20", enter=True)


k1_tab.wait_ms = 1500


def k1_placed():
    p = pi.panel("BoxPanel")
    h.check(
        "K1 Enter placed the box (dialog still open)",
        p is not None and p.state == "ready",
        p and p.state,
    )
    box = p.target if p is not None else None
    h.check(
        "K1 30 x 20 as typed",
        box is not None and near(box.Length.Value, 30.0) and near(box.Width.Value, 20.0),
        box and (box.Length.Value, box.Width.Value),
    )
    h.check("K1 no message", msg(p) == "", msg(p))
    h.fit()
    pi.hover(V(15, 10, 0))
    h.press("-")


k1_placed.wait_ms = 1500


def k1_height():
    keys_to_focus("5")


def k1_height_typed():
    p = pi.panel("BoxPanel")
    h.check(
        "K1 -5 went into the Height handle's box",
        box_text(p, "height") == "-5",
        box_text(p, "height"),
    )
    keys_to_focus("", enter=True)  # Enter takes the box's value and is OK (Fusion)


k1_height_typed.wait_ms = 1500


def k1_done():
    h.check("K1 Enter was OK", pi.no_dialog())
    h.check("K1 30 x 20 x 5", near(vol(), 3000.0), vol())
    bb = pi.bbox(h.body().Shape) if h.body() else None
    h.check(
        "K1 below the plane",
        bb is not None and near(bb[2], -5.0, 1e-3) and near(bb[5], 0.0, 1e-3),
        bb,
    )
    pi.menu("Cylinder")


# == K2: Cylinder, the diameter typed after the centre click ===============================
def k2_plane():
    h.click(V(15, -15, 0))


def k2_centre():
    h.click(V(50, 10, 0))


def k2_mouse():
    pi.hover(V(53, 10, 0))
    pi.hover(V(55, 10, 0))
    s["camera"] = camera()
    h.press("1")


def k2_more():
    p = pi.panel("CylinderPanel")
    h.check("K2 the view did not jump (FreeCAD's key 1)", camera() == s["camera"])
    keys_to_focus("2", enter=True)


k2_more.wait_ms = 1500


def k2_placed():
    p = pi.panel("CylinderPanel")
    cyl = p.target if p is not None else None
    h.check("K2 placed", p is not None and p.state == "ready", p and p.state)
    h.check(
        "K2 diameter 12 as typed",
        cyl is not None and near(cyl.Radius.Value, 6.0),
        cyl and cyl.Radius.Value,
    )
    if cyl is not None:
        c = pi.bbox(cyl.Shape)
        h.check(
            "K2 centred on the click",
            near((c[0] + c[3]) / 2.0, 50.0, 1e-3) and near((c[1] + c[4]) / 2.0, 10.0, 1e-3),
            c,
        )
    pi.hover(V(50, 10, 0))
    h.press("8")


k2_placed.wait_ms = 1500


def k2_height():
    p = pi.panel("CylinderPanel")
    h.check(
        "K2 8 went into the Height handle's box",
        box_text(p, "height") == "8",
        box_text(p, "height"),
    )
    keys_to_focus("", enter=True)  # Enter takes the box's value and is OK (Fusion)


k2_height.wait_ms = 1500


def k2_done():
    h.check("K2 OK", pi.no_dialog())
    h.check("K2 box + cylinder d12 h8", near(vol(), 3000.0 + 288.0 * PI), vol())
    h.check("K2 a body of its own", body_count() == 2, body_count())
    pi.menu("Sphere")


# == K3: Sphere, the diameter typed before the centre ======================================
def k3_plane():
    h.click(V(15, -15, 0))


def k3_type():
    pi.hover(V(40, -20, 0))
    h.press("6")


def k3_centre():
    p = pi.panel("SpherePanel")
    h.check(
        "K3 6 went into Diameter",
        p is not None and near(p.diameter.value(), 6.0),
        p and p.diameter.value(),
    )
    h.click(V(50, -20, 0))


k3_centre.wait_ms = 1200


def k3_placed():
    p = pi.panel("SpherePanel")
    sph = p.target if p is not None else None
    h.check(
        "K3 a sphere of diameter 6",
        sph is not None and near(sph.Radius.Value, 3.0),
        sph and sph.Radius.Value,
    )
    h.press(QtCore.Qt.Key_Return)


k3_placed.wait_ms = 1500


def k3_done():
    h.check("K3 Enter over the view is OK", pi.no_dialog())
    h.check("K3 + sphere d6", near(vol(), 3000.0 + 288.0 * PI + 36.0 * PI), vol())
    s["vol"] = vol()
    pi.menu("Torus")


# == K4: another command's key while a dialog is open ======================================
def k4_plane():
    h.click(V(15, -15, 0))


def k4_centre():
    h.click(V(-30, -30, 0))


def k4_extrude_key():
    p = pi.panel("TorusPanel")
    h.check("K4 placing the torus", p is not None and p.state == "place", p and p.state)
    h.press("e")


k4_extrude_key.wait_ms = 1500


def k4_extrude_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("K4 the torus dialog is gone", pi.panel("TorusPanel") is None)
    h.check(
        "K4 Extrude opened",
        current is not None and "Extrude" in type(current).__name__,
        current and type(current).__name__,
    )
    h.check("K4 no torus made", not pi.steps_of("Torus"), [o.Name for o in pi.steps_of("Torus")])
    h.check("K4 the part unchanged", near(vol(), s["vol"]), vol())
    h.check("K4 no pop-up", not h.popups(), h.popups())
    h.press(QtCore.Qt.Key_Escape)


k4_extrude_open.wait_ms = 1500


def k4_box():
    h.check("K4 Esc closed Extrude", pi.no_dialog())
    pi.menu("Box")


def k4_box_plane():
    h.click(V(15, -15, 0))


def k4_box_c1():
    h.click(V(-30, 0, 0))


def k4_box_c2():
    h.click(V(-20, 10, 0))


k4_box_c2.wait_ms = 1500


def k4_presspull_key():
    p = pi.panel("BoxPanel")
    h.check(
        "K4 a 10 x 10 box placed",
        p is not None and p.target is not None and near(p.target.Length.Value, 10.0),
        p and p.target,
    )
    h.press("q")


k4_presspull_key.wait_ms = 1500


def k4_presspull_open():
    from sciforge import taskui

    current = taskui.current()
    h.check("K4 the box dialog finished", pi.panel("BoxPanel") is None)
    h.check(
        "K4 Press Pull opened",
        current is not None and "PressPull" in type(current).__name__,
        current and type(current).__name__,
    )
    h.check(
        "K4 the box was kept (Fusion keeps a finished shape)", near(vol(), s["vol"] + 1000.0), vol()
    )
    h.press(QtCore.Qt.Key_Escape)


k4_presspull_open.wait_ms = 1500


def k4_undo():
    h.check("K4 Esc closed Press Pull", pi.no_dialog())
    h.check("K4 still kept", near(vol(), s["vol"] + 1000.0), vol())
    h.press("z", QtCore.Qt.ControlModifier)


k4_undo.wait_ms = 1200


def k4_redo():
    h.check("K4 Ctrl+Z took the box away", near(vol(), s["vol"]), vol())
    h.press("y", QtCore.Qt.ControlModifier)


k4_redo.wait_ms = 1200


def k4_done():
    h.check("K4 Ctrl+Y brought it back", near(vol(), s["vol"] + 1000.0), vol())
    h.shot("k4")
    pi.menu("Cylinder")


# == K5: Esc in the middle of the pick =======================================================
def k5_plane():
    h.click(V(15, -15, 0))


def k5_centre():
    h.click(V(-30, -30, 0))


def k5_esc():
    pi.hover(V(-27, -30, 0))
    h.press(QtCore.Qt.Key_Escape)


k5_esc.wait_ms = 1200


def k5_done():
    h.check("K5 Esc closed it", pi.no_dialog())
    h.check("K5 nothing left", near(vol(), s["vol"] + 1000.0), vol())
    h.check(
        "K5 four bodies (box, cylinder, sphere, the box of K4)", body_count() == 4, body_count()
    )


h.run(
    "primitives_qa_keys",
    [
        new_design,
        k1_plane,
        k1_corner,
        k1_mouse,
        k1_type_length,
        k1_length_more,
        k1_tab,
        k1_placed,
        k1_height,
        k1_height_typed,
        k1_done,
        k2_plane,
        k2_centre,
        k2_mouse,
        k2_more,
        k2_placed,
        k2_height,
        k2_done,
        k3_plane,
        k3_type,
        k3_centre,
        k3_placed,
        k3_done,
        k4_plane,
        k4_centre,
        k4_extrude_key,
        k4_extrude_open,
        k4_box,
        k4_box_plane,
        k4_box_c1,
        k4_box_c2,
        k4_presspull_key,
        k4_presspull_open,
        k4_undo,
        k4_redo,
        k4_done,
        k5_plane,
        k5_centre,
        k5_esc,
        k5_done,
    ],
)
