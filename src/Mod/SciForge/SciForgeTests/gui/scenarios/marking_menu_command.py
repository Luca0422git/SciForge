# SPDX-License-Identifier: LGPL-2.1-or-later
"""The right-click marking menu while a command is open has OK and Cancel (Fusion).

Block 40 x 30 x 10. A right click with nothing open: the top slot repeats the last
command and there is no Cancel. Click the top face, Q, type 2, right click: the top
slot is OK and the list starts with Cancel; click OK: 40 x 30 x 12, the dialog is
closed. Q again, type 3, right click, click Cancel in the list: still 40 x 30 x 12,
no new feature. A list row starts its command (Fillet) and Cancel ends it again.

Hand-derived: 40*30*10 = 12000; 40*30*12 = 14400."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def open_menu():
    """Right click on an empty spot of the 3D view; returns the marking menu."""
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    gl = h.gl_widget()
    w.click(gl, QtCore.QPoint(gl.width() - 140, 140), button=QtCore.Qt.RightButton)
    menu = marking_menu._last_menu["widget"]
    h.check("right click opens the marking menu", menu is not None and menu.isVisible())
    return menu


def rows(menu):
    return [menu.list.item(i) for i in range(menu.list.count())]


def click_row(menu, text):
    for row in rows(menu):
        if row.text().split("    ")[0] == text:
            rect = menu.list.visualItemRect(row)
            w.click(menu.list.viewport(), rect.center())
            return True
    h.check("list row %r exists" % text, False, [r.text() for r in rows(menu)])
    return False


def close(menu):
    if menu is not None and menu.isVisible():
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("MarkingCommand")
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()


def menu_without_command():
    menu = open_menu()
    if menu is not None:
        h.check("top slot repeats", menu.slots[0].text().startswith("Repeat"), menu.slots[0].text())
        texts = [r.text() for r in rows(menu)]
        h.check(
            "no Cancel without a command", not any(t.startswith("Cancel") for t in texts), texts
        )
    close(menu)


def pick_top():
    h.click(V(20, 15, 10))


def start_press_pull():
    h.check("top face selected", len(Gui.Selection.getSelectionEx()) == 1)
    h.press("q")
    p = panel()
    h.check("Press Pull started on the face", p is not None and p.target is not None)
    s["count"] = len(h.body().Group)


def type_2():
    ui.type_into(panel().field.widget, "2")


def menu_ok():
    h.check("preview 40 x 30 x 12", near(h.solid_volume(), 14400.0), h.solid_volume())
    menu = open_menu()
    if menu is None:
        return
    h.check("top slot is OK", menu.slots[0].text() == "OK", menu.slots[0].text())
    h.check("OK is enabled", menu.slots[0].isEnabled())
    first = rows(menu)[0] if rows(menu) else None
    h.check("list starts with Cancel", first is not None and first.text().startswith("Cancel"))
    h.check(
        "Cancel is enabled", first is not None and bool(first.flags() & QtCore.Qt.ItemIsEnabled)
    )
    h.shot("1-ok-cancel")
    w.click(menu.slots[0])


def after_ok():
    h.check("OK closed the dialog", not Gui.Control.activeDialog())
    h.check("OK kept 40 x 30 x 12", near(h.solid_volume(), 14400.0), h.solid_volume())
    h.check("one feature added", len(h.body().Group) >= s["count"], len(h.body().Group))
    s["count"] = len(h.body().Group)
    s["volume"] = h.solid_volume()
    h.fit()


def pick_top_again():
    h.click(V(20, 15, 12))


def start_again():
    h.press("q")
    p = panel()
    h.check("Press Pull started again", p is not None and p.target is not None)


def type_3():
    ui.type_into(panel().field.widget, "3")


def menu_cancel():
    h.check("preview moved the face", not near(h.solid_volume(), s["volume"]), h.solid_volume())
    menu = open_menu()
    if menu is not None:
        click_row(menu, "Cancel")


def after_cancel():
    h.check("Cancel closed the dialog", not Gui.Control.activeDialog())
    h.check("Cancel left 40 x 30 x 12", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("Cancel left no feature", len(h.body().Group) == s["count"], len(h.body().Group))


def list_row_starts_fillet():
    menu = open_menu()
    if menu is not None:
        click_row(menu, "Fillet")


def fillet_open():
    h.check("the Fillet row opened Fillet", bool(Gui.Control.activeDialog()))
    menu = open_menu()
    if menu is not None:
        h.check("top slot is OK", menu.slots[0].text() == "OK", menu.slots[0].text())
        click_row(menu, "Cancel")


def fillet_cancelled():
    h.check("Cancel closed Fillet", not Gui.Control.activeDialog())
    h.check("part unchanged", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("no feature added", len(h.body().Group) == s["count"], len(h.body().Group))


h.run(
    "marking_menu_command",
    [
        setup,
        menu_without_command,
        pick_top,
        start_press_pull,
        type_2,
        menu_ok,
        after_ok,
        pick_top_again,
        start_again,
        type_3,
        menu_cancel,
        after_cancel,
        list_row_starts_fillet,
        fillet_open,
        fillet_cancelled,
    ],
)
