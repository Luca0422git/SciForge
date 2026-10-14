# SPDX-License-Identifier: LGPL-2.1-or-later
"""Canvas: insert, edit, calibrate (INSERT menu, browser), only real input.

Body = box 0..40 x 0..30 x 10. Fixture: canvas.png, 80 x 40 pixels with two dots 60 px apart.

A  INSERT > Canvas with the picture: the dialog waits for a face; click the top face: a
   canvas in the browser's Canvases folder, 52 x 26 mm (sized to the 40 mm design), on the
   face's centre, 50 % opacity (see-through), Display Through on (drawn over the part).
B  Canvas Opacity 80: less see-through. Display Through off: drawn like the part; on again.
   X Distance 5: moved 5 mm. Horizontal Flip on and off.
C  OK: no canvas step in the timeline; the browser row's eye hides and shows it.
D  Right-click the canvas in the browser > Calibrate: click the two dots, type 60, Enter:
   the canvas is 80 x 40 mm (one pixel = one mm).
E  Ctrl+Z: 52 wide again. Ctrl+Y: 80.
F  Browser double-click the canvas: Edit Canvas shows 80 %; 50, Cancel: still 80 %.
G  Delete on the canvas row: gone; Ctrl+Z: back.
"""

import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
FACE_CENTRE = V(20, 15, 10)
state = {}


def canvas():
    found = i.canvases()
    return found[0] if found else None


def size(obj):
    return (round(obj.XSize.Value, 3), round(obj.YSize.Value, 3))


def about(obj, width, height, tol=0.1):
    """The size within a tenth of a millimetre: the clicks land on screen pixels, so the two
    picked points are a little off the dots (as a person's clicks are)."""
    w, h = size(obj)
    return abs(w - width) <= tol and abs(h - height) <= tol


def calibrated(obj):
    """The size Calibrate gives for the distance actually picked: 52 x 26 scaled by 60 /
    picked. The clicks land on whole pixels, worth more than a tenth of a millimetre at
    this zoom (a CI window one pixel different picked 38.88), so the exact 80 x 40 holds
    only within the pixel tolerance; the scaling itself is checked to the micrometre."""
    picked = state.get("picked")
    if not picked:
        return about(obj, 80, 40)
    return about(obj, 52 * 60.0 / picked, 26 * 60.0 / picked, 0.01) and about(
        obj, 80, 40, 2 * 60.0 / picked * state.get("pixel_mm", 0.05) + 0.01
    )


def drawn_through(obj):
    """True when the canvas is drawn as a Coin annotation (Display Through)."""
    from pivy import coin

    root = obj.ViewObject.RootNode
    return (
        root.getNumChildren() == 1
        and root.getChild(0).getTypeId() == coin.SoAnnotation.getClassTypeId()
    )


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.use_file(i.fixture("canvas.png"))
    h.fit()
    h.ribbon("Canvas")


def a_waits():
    p = i.panel()
    h.check("Canvas dialog waits for a face", p is not None and p.title == "Canvas", p)
    s.no_popups("Canvas")
    h.check("no canvas yet", canvas() is None)


def a_click_face():
    h.click(FACE_CENTRE)


a_click_face.wait_ms = 1200


def a_check():
    c = canvas()
    h.check("a canvas", c is not None)
    if c is None:
        return
    h.check("sized to the design: 52 x 26", size(c) == (52, 26), size(c))
    h.check(
        "on the face's centre", (c.Placement.Base - FACE_CENTRE).Length < 1e-6, c.Placement.Base
    )
    h.check(
        "in the Canvases folder",
        i.browser_has("canvas") and i.browser_has("Canvases"),
        i.browser_labels(),
    )
    h.check(
        "50 % opacity",
        c.ViewObject.Transparency == 50 and c.CanvasOpacity == 50,
        c.ViewObject.Transparency,
    )
    h.check("Display Through on", c.DisplayThrough and drawn_through(c))
    # FreeCAD 1.x keeps the picture inside the design: ImageFile is the saved copy's path
    h.check("the picture is kept in the design", bool(c.ImageFile) and os.path.isfile(c.ImageFile))


# -- B ----------------------------------------------------------------------------------------
def b_opacity():
    p = i.panel()
    if p is not None:
        i.set_spin(p.opacity, 80)


def b_check_opacity():
    c = canvas()
    h.check(
        "80 %: transparency 20",
        c is not None and c.ViewObject.Transparency == 20,
        c and c.ViewObject.Transparency,
    )


def b_through_off():
    p = i.panel()
    if p is not None:
        i.set_check(p.through, False)


def b_check_through_off():
    c = canvas()
    h.check("Display Through off: drawn like the part", c is not None and not drawn_through(c))


def b_through_on():
    p = i.panel()
    if p is not None:
        i.set_check(p.through, True)


def b_check_through_on():
    c = canvas()
    h.check("Display Through on again", c is not None and drawn_through(c))


def b_offset():
    p = i.panel()
    if p is not None:
        i.type_value(p.dx, "5")


def b_check_offset():
    c = canvas()
    moved = (c.Placement.Base - FACE_CENTRE).Length if c else None
    h.check("X Distance 5: moved 5 mm", moved is not None and abs(moved - 5) < 1e-6, moved)
    state["rotation"] = c.Placement.Rotation if c else None


def b_flip():
    p = i.panel()
    if p is not None:
        i.set_check(p.flip_h, True)


def b_check_flip():
    c = canvas()
    turned = c is not None and not c.Placement.Rotation.isSame(state["rotation"], 1e-9)
    h.check("horizontal flip turns the picture over", turned)
    p = i.panel()
    if p is not None:
        i.set_check(p.flip_h, False)


# -- C ----------------------------------------------------------------------------------------
def c_ok():
    h.task_button("OK")


def c_check():
    h.check("dialog closed", i.panel() is None)
    c = canvas()
    h.check("canvas kept", c is not None)
    titles = i.timeline_titles()
    h.check("no canvas step in the timeline", not any("Canvas" in t for t in titles), titles)


def c_eye_off():
    tree = s.browser()
    item = tree.row("canvas") if tree is not None else None
    if h.check("browser row canvas", item is not None):
        w.click(tree.viewport(), tree.eye_point(item))


def c_check_hidden():
    c = canvas()
    h.check("eye: hidden", c is not None and not s.shown(c))


def c_eye_on():
    tree = s.browser()
    item = tree.row("canvas") if tree is not None else None
    if item is not None:
        w.click(tree.viewport(), tree.eye_point(item))


def c_check_shown():
    c = canvas()
    h.check("eye: shown again", c is not None and s.shown(c))


# -- D ----------------------------------------------------------------------------------------
def d_calibrate_menu():
    tree = s.browser()
    item = tree.row("canvas") if tree is not None else None
    if h.check("browser row canvas", item is not None):
        ok = w.right_click(tree.viewport(), tree.label_point(item), "Calibrate")
        h.check("Calibrate in the right-click menu", ok)


d_calibrate_menu.wait_ms = 1200


def d_waits():
    p = i.panel()
    h.check("Calibrate dialog", p is not None and p.title == "Calibrate", p)
    c = canvas()
    # the dots sit at pixels 10 and 70 of 80: 3/8 of the width left and right of the centre
    half = c.XSize.Value * 60.0 / 80.0 / 2.0
    state["dot1"] = c.Placement.multVec(V(-half, 0, 0))
    state["dot2"] = c.Placement.multVec(V(half, 0, 0))
    h.fit()
    # How many millimetres one screen pixel is worth here (the clicks' own precision).
    a, b = h.screen_point(state["dot1"]), h.screen_point(state["dot2"])
    pixels = max(1.0, ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5)
    state["pixel_mm"] = 2.0 * half / pixels


def d_click_first():
    h.click(state["dot1"])


def d_click_second():
    h.click(state["dot2"])


def d_type_distance():
    p = i.panel()
    if p is None:
        return
    shown = p.distance.value()
    state["picked"] = shown
    # each click is within a pixel of its dot
    tol = 2 * state.get("pixel_mm", 0.05) + 0.01
    h.check("the picked distance is shown (39 mm)", abs(shown - 39.0) <= tol, (shown, tol))
    i.type_value(p.distance, "60")


def d_enter():
    h.task_button("OK")


def d_check():
    c = canvas()
    h.check("calibrated: 80 x 40 mm", c is not None and calibrated(c), c and size(c))
    h.check("dialog closed", i.panel() is None)


# -- E ----------------------------------------------------------------------------------------
def e_undo():
    i.undo()


def e_check_undo():
    c = canvas()
    h.check("Ctrl+Z: 52 wide again", c is not None and size(c) == (52, 26), c and size(c))


def e_redo():
    i.redo()


def e_check_redo():
    c = canvas()
    h.check("Ctrl+Y: 80 wide", c is not None and calibrated(c), c and size(c))


# -- F ----------------------------------------------------------------------------------------
def f_edit():
    si.browser_double_click("canvas")


f_edit.wait_ms = 1200


def f_dialog():
    p = i.panel()
    h.check("Edit Canvas dialog", p is not None and p.title == "Edit Canvas", p and p.title)
    if p is not None:
        h.check("shows 80 %", p.opacity.value() == 80, p.opacity.value())
        i.set_spin(p.opacity, 50)


def f_check_changed():
    c = canvas()
    h.check("50 %: transparency 50", c is not None and c.ViewObject.Transparency == 50)


def f_cancel():
    h.task_button("Cancel")


def f_check_cancel():
    c = canvas()
    h.check(
        "Cancel: 80 % again",
        c is not None and c.CanvasOpacity == 80 and c.ViewObject.Transparency == 20,
        c and (c.CanvasOpacity, c.ViewObject.Transparency),
    )
    h.check("still drawn through", c is not None and drawn_through(c))


# -- G ----------------------------------------------------------------------------------------
def g_delete():
    tree = s.browser()
    item = tree.row("canvas") if tree is not None else None
    if h.check("browser row canvas", item is not None):
        w.click(tree.viewport(), tree.label_point(item))
        tree.setFocus()
        from PySide6 import QtTest

        QtTest.QTest.keyClick(tree, QtCore.Qt.Key_Delete)


g_delete.wait_ms = 1200


def g_check_deleted():
    h.check("Delete: no canvas", canvas() is None, [c.Label for c in i.canvases()])


def g_undo():
    i.undo()


def g_check_undo():
    c = canvas()
    h.check("Ctrl+Z: the canvas is back", c is not None and calibrated(c), c and size(c))
    i.no_file()
    h.shot("end")


h.run(
    "insert_canvas",
    [i.new_design("InsertCanvas")]
    + s.box_steps("box", (0, 0, 40, 30), 10, i.XY_CLICK)
    + [
        a_open,
        a_waits,
        a_click_face,
        a_check,
        b_opacity,
        b_check_opacity,
        b_through_off,
        b_check_through_off,
        b_through_on,
        b_check_through_on,
        b_offset,
        b_check_offset,
        b_flip,
        b_check_flip,
        c_ok,
        c_check,
        c_eye_off,
        c_check_hidden,
        c_eye_on,
        c_check_shown,
        d_calibrate_menu,
        d_waits,
        d_click_first,
        d_click_second,
        d_type_distance,
        d_enter,
        d_check,
        e_undo,
        e_check_undo,
        e_redo,
        e_check_redo,
        f_edit,
        f_dialog,
        f_check_changed,
        f_cancel,
        f_check_cancel,
        g_delete,
        g_check_deleted,
        g_undo,
        g_check_undo,
    ],
)
