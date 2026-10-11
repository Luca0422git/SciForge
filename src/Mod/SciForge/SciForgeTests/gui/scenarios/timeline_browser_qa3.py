# SPDX-License-Identifier: LGPL-2.1-or-later
"""The BROWSER and the timeline with two bodies, the way Fusion users use them (QA,
only real input).

Path 12, two bodies made like in Fusion (Extrude > New Body): both listed, the new one
         active; Ctrl+click two body rows selects both in the 3D view; the Bodies
         folder's eye hides and shows both; the Origin folder holds one origin.
Path 13, a hidden body stays hidden when the marker is rolled back and forward.
Path 14, Esc while dragging a step: the drag is dropped, nothing moves.
Path 15, a timeline right-click while a command waits for picks (Fillet open, nothing
         picked): the command ends without a trace, the menu entry runs.
Path 16, keys that must do nothing: Delete on Document Settings / an origin plane in
         the browser, an empty name in a rename, a step dropped where it already is
         and the marker dropped where it already is (no undo step either).
Path 17, save, close, reopen with two bodies: one origin in the browser, a body to
         activate by double-click, F2 rename of a body, Delete key on a body row and
         Ctrl+Z, a group of steps deleted from its menu and Ctrl+Z.

Numbers by hand: body 1 = 40 x 30 x 10 = 12000, body 2 = 20 x 20 x 10 = 4000.
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOX1 = 12000.0
BOX2 = 4000.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def bodies():
    return [o for o in t.doc().Objects if o.TypeId == "PartDesign::Body"]


def body2():
    return t.doc().getObject(s["b2"]) if s.get("b2") else None


def undo_count():
    try:
        return len(t.doc().UndoNames)
    except Exception:
        return -1


# -- Path 12: a second body, like in Fusion -------------------------------------------------
def p12_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def p12_pick_xy():
    h.click(V(-15, -12, 0))  # inside the origin squares, clear of the box


def p12_draw():
    sk = h.in_sketch()
    h.check("sketch on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -40, -40, -20, -20)


def p12_finish():
    h.ribbon("Finish Sketch")


def p12_extrude():
    h.fit()
    h.press("e")


def p12_new_body():
    p = xpanel()
    h.check("Extrude picked the square", p is not None and p.target is not None)
    if p is not None:
        h.check("choose New Body", ui.choose(p.operation, "New Body"))


def p12_ok():
    h.task_button("OK")


def p12_two_bodies():
    found = bodies()
    h.check("two bodies", len(found) == 2, [o.Name for o in found])
    s["b1"] = "Body"
    s["b2"] = [o.Name for o in found if o.Name != "Body"][0] if len(found) == 2 else None
    s["l1"] = t.doc().getObject("Body").Label
    s["l2"] = body2().Label if body2() else "?"
    h.check("body 1 unchanged", t.near(t.volume("Body"), BOX1), t.volume("Body"))
    h.check("body 2 = 20 x 20 x 10", t.near(t.volume(body2()), BOX2), t.volume(body2()))
    rows = t.children("Bodies")
    h.check("both bodies in the browser", rows is not None and len(rows) == 2, rows)
    row = t.tree().row(s["l2"])
    h.check("the new body is the active one", row is not None and row.font(1).bold())
    h.check(
        "one timeline for both",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        t.titles(),
    )
    h.shot("1-two-bodies")


def p12_click_rows():
    t.click_row(s["l1"])
    t.click_row(s["l2"], QtCore.Qt.ControlModifier)


def p12_both_selected():
    h.check(
        "Ctrl+click: both bodies selected in the 3D view",
        sorted(t.selected()) == sorted([s["b1"], s["b2"]]),
        t.selected(),
    )
    h.click_empty()


def p12_cleared():
    h.check("a click on the background clears the rows", t.selected_rows() == [], t.selected_rows())
    t.click_eye("Bodies")


def p12_all_hidden():
    h.check(
        "the Bodies eye hides both",
        not t.shown(t.doc().getObject("Body")) and not t.shown(body2()),
    )
    t.click_eye("Bodies")


def p12_all_shown():
    h.check(
        "and shows both again",
        t.shown(t.doc().getObject("Body")) and t.shown(body2()),
    )
    origin = t.children("Origin")
    h.check(
        "one origin: O, X, Y, Z, XY, XZ, YZ",
        origin == ["O", "X", "Y", "Z", "XY", "XZ", "YZ"],
        origin,
    )


# -- Path 13: a hidden body stays hidden through marker moves ---------------------------------
def p13_hide():
    t.click_eye(s["l1"])


def p13_roll_back():
    h.check("body 1 hidden", not t.shown(t.doc().getObject("Body")))
    t.drag_marker(before_title="Extrude 2")


def p13_rolled():
    h.check("body 2 rolled back (empty)", t.volume(body2()) < 1e-6, t.volume(body2()))
    h.check("body 1 still hidden", not t.shown(t.doc().getObject("Body")))
    t.drag_marker(to_end=True)


def p13_end():
    h.check("body 2 back", t.near(t.volume(body2()), BOX2), t.volume(body2()))
    h.check("body 1 still hidden at the end", not t.shown(t.doc().getObject("Body")))
    row = t.tree().row(s["l1"])
    node = row.data(1, QtCore.Qt.UserRole) if row is not None else None
    s["eye_before"] = (row.text(1) if row else None, node and node["visible"])
    t.click_eye(s["l1"])


def p13_shown():
    h.check(
        "eye shows body 1 again",
        t.shown(t.doc().getObject("Body")),
        (s.get("eye_before"), t.labels()),
    )


# -- Path 14: Esc while dragging a step ------------------------------------------------------
def p14_drag_esc():
    s["order"] = t.titles()
    s["undo"] = undo_count()
    src = t.button("Extrude 2")
    first = t.button("Sketch 1")
    if src is None or first is None:
        return
    start = w.center(src)
    w.move(src, start)
    QtTest.QTest.mousePress(src, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
    end = first.mapToGlobal(QtCore.QPoint(2, first.height() // 2))
    begin = src.mapToGlobal(start)
    for i in range(1, 9):
        g = QtCore.QPointF(
            begin.x() + (end.x() - begin.x()) * i / 8, begin.y() + (end.y() - begin.y()) * i / 8
        )
        local = src.mapFromGlobal(g.toPoint())
        event = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(local),
            g,
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(src, event)
        QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyClick(src, QtCore.Qt.Key_Escape)
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.mouseRelease(
        src, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, src.mapFromGlobal(end)
    )
    QtWidgets.QApplication.processEvents()


def p14_nothing_moved():
    h.check("Esc drops the drag: same order", t.titles() == s["order"], t.titles())
    h.check("no undo step", undo_count() == s["undo"], (undo_count(), s["undo"]))
    lines = [
        x for x in t.tl()._inner.findChildren(QtWidgets.QFrame) if x.property("role") == "drop"
    ]
    h.check("no drop line left behind", not [x for x in lines if x.isVisible()])


# -- Path 15: timeline right-click while a command waits for picks ----------------------------
def p15_fillet():
    h.click_empty()
    h.press("f")


def p15_menu():
    h.check("Fillet waits for edges", b.blend_panel() is not None)
    t.menu("Extrude 2", "Suppress Features")


def p15_done():
    h.check("the Fillet dialog ended", not t.dialog_open())
    h.check("no fillet made", not b.blends())
    h.check("Extrude 2 suppressed", t.item("Extrude 2").suppressed, t.states())
    h.check("body 2 empty", t.volume(body2()) < 1e-6, t.volume(body2()))
    t.menu("Extrude 2", "Unsuppress Features")


def p15_back():
    h.check("body 2 back", t.near(t.volume(body2()), BOX2), t.volume(body2()))
    h.check("nothing red or yellow", all(v[1] == "ok" for v in t.states().values()), t.states())


# -- Path 16: keys that must do nothing ----------------------------------------------------------
def p16_delete_settings():
    s["undo"] = undo_count()
    s["count"] = len(t.doc().Objects)
    t.click_row("Document Settings")
    w.key(t.tree(), QtCore.Qt.Key_Delete)


def p16_delete_origin():
    h.check("Delete on Document Settings does nothing", len(t.doc().Objects) == s["count"])
    t.click_row("XY")
    w.key(t.tree(), QtCore.Qt.Key_Delete)


def p16_rename_empty():
    h.check("Delete on an origin plane does nothing", len(t.doc().Objects) == s["count"])
    h.check("still one origin", t.children("Origin") == ["O", "X", "Y", "Z", "XY", "XZ", "YZ"])
    t.click("Extrude 1")
    w.key(t.button("Extrude 1"), QtCore.Qt.Key_F2)


def p16_type_empty():
    field = t.rename_field()
    if h.check("name field open", field is not None):
        w.key(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.key(field, QtCore.Qt.Key_Delete)
        w.key(field, QtCore.Qt.Key_Return)


def p16_name_kept():
    h.check("an empty name keeps the old one", "Extrude 1" in t.titles(), t.titles())
    t.drag_step("Extrude 1", before_title="Sketch 2")  # where it already is


def p16_same_place():
    h.check("dropped where it is: same order", t.titles()[1] == "Extrude 1", t.titles())
    h.check("no refusal shown", t.tl().refusal() == "", t.tl().refusal())
    t.drag_marker(to_end=True)  # where it already is


def p16_no_undo_steps():
    h.check("nothing made an undo step", undo_count() == s["undo"], (undo_count(), s["undo"]))
    h.check("nothing deleted", len(t.doc().Objects) == s["count"])


# -- Path 17: save, close, reopen with two bodies ------------------------------------------------
def p17_save():
    s["path"] = os.path.join(tempfile.mkdtemp(), "timeline_qa3.FCStd")
    t.doc().saveAs(s["path"])


def p17_close():
    App.closeDocument(t.doc().Name)


def p17_open():
    App.openDocument(s["path"])
    h.fit()


def p17_reopened():
    h.check(
        "same timeline",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        t.titles(),
    )
    origin = t.children("Origin")
    h.check(
        "one origin after reopening (not one per body)",
        origin == ["O", "X", "Y", "Z", "XY", "XZ", "YZ"],
        origin,
    )
    h.check("both bodies listed", len(t.children("Bodies") or []) == 2, t.children("Bodies"))
    t.double_click_row(s["l1"])


def p17_active():
    from sciforge import commands

    body = commands.active_body()
    h.check("double-click activates body 1", body is not None and body.Name == "Body")
    row = t.tree().row(s["l1"])
    h.check("and marks it", row is not None and row.font(1).bold())
    t.click_row(s["l2"])
    w.key(t.tree(), QtCore.Qt.Key_F2)


def p17_type_name():
    field = t.browser_field()
    if h.check("F2 opens the name field", field is not None and field.isVisible()):
        w.key(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(field, "Bracket")
        w.key(field, QtCore.Qt.Key_Return)


def p17_renamed():
    h.check("body 2 renamed", body2() is not None and body2().Label == "Bracket")
    h.check("timeline unchanged", len(t.titles()) == 4, t.titles())
    t.click_row("Bracket")
    w.key(t.tree(), QtCore.Qt.Key_Delete)


def p17_deleted():
    h.check("Delete key removes body 2", body2() is None)
    h.check(
        "its steps left the timeline (the sketch is body 1's)",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2"],
        t.titles(),
    )
    h.check("body 1 untouched", t.near(t.volume("Body"), BOX1), t.volume("Body"))
    t.ctrl("z")


def p17_undone():
    h.check("Ctrl+Z brings body 2 back", t.near(t.volume(body2()), BOX2), t.volume(body2()))
    h.check("its steps are back", len(t.titles()) == 4, t.titles())
    t.click("Sketch 2")
    t.click("Extrude 2", QtCore.Qt.ShiftModifier)


def p17_group():
    t.menu("Extrude 2", "Group Features")


def p17_group_delete():
    header = None
    for widget, _l, _r in t.tl()._slots:
        if widget.objectName().startswith("SciForgeGroup_"):
            header = widget
    if h.check("group made", header is not None):
        ok = w.right_click(header, w.center(header), "Delete")
        h.check("group menu > Delete", ok)


def p17_group_gone():
    h.check("the group's steps are deleted", t.titles() == ["Sketch 1", "Extrude 1"], t.titles())
    h.check("no helper left behind", len(t.doc().getObject(s["b2"]).Group) == 0, body2().Group)
    h.check("body 2 empty", t.volume(body2()) < 1e-6, t.volume(body2()))
    t.ctrl("z")


def p17_group_back():
    h.check("Ctrl+Z: steps back", len(t.titles()) == 4, t.titles())
    h.check("body 2 back", t.near(t.volume(body2()), BOX2), t.volume(body2()))
    t.no_popups("the end")
    h.shot("2-end")


from PySide import QtGui  # noqa: E402  (used by the hand-made drag events)

STEPS = b.box_steps("TimelineQA3") + [
    p12_sketch,
    p12_pick_xy,
    p12_draw,
    p12_finish,
    p12_extrude,
    p12_new_body,
    p12_ok,
    p12_two_bodies,
    p12_click_rows,
    p12_both_selected,
    p12_cleared,
    p12_all_hidden,
    p12_all_shown,
    p13_hide,
    p13_roll_back,
    p13_rolled,
    p13_end,
    p13_shown,
    p14_drag_esc,
    p14_nothing_moved,
    p15_fillet,
    p15_menu,
    p15_done,
    p15_back,
    p16_delete_settings,
    p16_delete_origin,
    p16_rename_empty,
    p16_type_empty,
    p16_name_kept,
    p16_same_place,
    p16_no_undo_steps,
    p17_save,
    p17_close,
    p17_open,
    p17_reopened,
    p17_active,
    p17_type_name,
    p17_renamed,
    p17_deleted,
    p17_undone,
    p17_group,
    p17_group_delete,
    p17_group_gone,
    p17_group_back,
]

h.run("timeline_browser_qa3", t.watched(STEPS))
