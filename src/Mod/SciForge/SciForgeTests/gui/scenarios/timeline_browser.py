# SPDX-License-Identifier: LGPL-2.1-or-later
"""The design timeline with the mouse, like in Fusion: build a box with a boss
(Create Sketch, Extrude, sketch on the top face, Extrude), then use the timeline's
right-click menu (Suppress/Unsuppress, Roll History Marker Here, Rename, Edit
Profile Sketch, Delete, Find in Browser), drag steps (refused moves show why),
drag the history marker, double-click to edit, Undo/Redo from the quick-access
bar. Every number is worked out by hand:

  box      40 x 30 x 10               = 12000
  boss     circle r5 on top, 10 high   = pi * 25 * 10 = 785.398...
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
BOX = 40 * 30 * 10
BOSS = math.pi * 5**2 * 10
s = {}


def tl():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()  # rebuilds only when the design changed
    QtWidgets.QApplication.processEvents()  # new widgets get shown and laid out
    return widget


def step_button(title):
    for b in tl()._buttons:
        if b.item.display == title:
            return b
    h.check("timeline has %r" % title, False, tl().titles())
    return None


def volume():
    doc = App.ActiveDocument
    body = doc.getObject("Body")
    if body is None or body.Shape.isNull():
        return 0.0
    try:
        return body.Shape.Volume
    except Exception:
        return 0.0


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def menu(title, entry):
    b = step_button(title)
    ok = b is not None and w.right_click(b, w.center(b), entry)
    h.check("menu %s > %s" % (title, entry), ok)
    return ok


# -- build the part with the mouse ---------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Timeline")
    h.fit()


def empty_timeline():
    h.check("empty design: timeline has no steps", tl().titles() == [], tl().titles())


def create_sketch_1():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_rect():
    sk = h.in_sketch()
    h.check("sketch 1 open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_1():
    h.ribbon("Finish Sketch")


def extrude_1():
    h.fit()
    h.press("e")


def extrude_1_ok():
    h.task_button("OK")


def check_box():
    h.check("box volume 40*30*10", near(volume(), BOX), volume())
    h.fit()


def create_sketch_2():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_top():
    h.fit()
    h.click(V(20, 15, 10))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch 2 open on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, 10))
        h.draw_circle(sk, x, y, 5)


def finish_2():
    h.ribbon("Finish Sketch")


def extrude_2():
    h.fit()
    h.press("e")


def extrude_2_ok():
    h.task_button("OK")


def check_part():
    s["full"] = BOX + BOSS
    h.check("box + boss volume", near(volume(), s["full"]), volume())
    titles = tl().titles()
    h.check(
        "one timeline: Sketch 1, Extrude 1, Sketch 2, Extrude 2",
        titles == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        titles,
    )
    h.check("marker at the end", tl()._timeline.at_end)
    icons = [b.item.icon for b in tl()._buttons]
    h.check("feature icons", icons == ["sk_rectangle", "extrude", "sk_rectangle", "extrude"], icons)
    h.shot("1-part")


# -- right-click menu ------------------------------------------------------------------
def menu_entries():
    b = step_button("Extrude 2")
    texts = [t for t, _on in w.menu_texts(b, w.center(b))]
    wanted = [
        "Edit Feature",
        "Edit Profile Sketch",
        "Suppress Features",
        "Roll History Marker Here",
        "Rename",
        "Delete",
        "Find in Browser",
        "Find in Window",
    ]
    h.check("Fusion's timeline menu", texts == wanted, texts)


def suppress_boss():
    menu("Extrude 2", "Suppress Features")


def check_suppressed():
    h.check("boss suppressed: box only", near(volume(), BOX), volume())
    b = step_button("Extrude 2")
    h.check("Extrude 2 shown suppressed", b is not None and b.item.suppressed)
    h.check(
        "tooltip says suppressed", b is not None and "Suppressed" in b.toolTip(), b and b.toolTip()
    )
    h.shot("2-suppressed")


def undo():
    w.click(w.quick_access("Undo"))


def check_undo_suppress():
    h.check("Undo brings the boss back", near(volume(), s["full"]), volume())
    h.check("not suppressed after undo", not step_button("Extrude 2").item.suppressed)


def redo():
    w.click(w.quick_access("Redo"))


def check_redo_suppress():
    h.check("Redo suppresses it again", near(volume(), BOX), volume())


def unsuppress_boss():
    menu("Extrude 2", "Unsuppress Features")


def check_unsuppressed():
    h.check("Unsuppress: boss back", near(volume(), s["full"]), volume())


def suppress_first():
    """Fusion: the steps that depend on it go off with it (sketch 2 sits on its face)."""
    menu("Extrude 1", "Suppress Features")


def check_all_off():
    items = {i.display: i for i in tl().items()}
    h.check(
        "dependents suppressed with Extrude 1",
        all(items[t].suppressed for t in ("Extrude 1", "Sketch 2", "Extrude 2")),
        [(t, i.suppressed) for t, i in items.items()],
    )
    h.check("nothing left of the part", volume() < 1e-6, volume())
    h.check("no step shown red", all(i.status != "error" for i in items.values()))
    h.shot("3-first-suppressed")


def unsuppress_first():
    menu("Extrude 1", "Unsuppress Features")


def check_all_back():
    h.check("Unsuppress Extrude 1 restores everything", near(volume(), s["full"]), volume())
    items = tl().items()
    h.check("nothing suppressed", not any(i.suppressed for i in items))
    h.check(
        "nothing red or yellow",
        all(i.status == "ok" for i in items),
        [(i.display, i.message) for i in items],
    )


# -- history marker -----------------------------------------------------------------------
def roll_here():
    menu("Extrude 1", "Roll History Marker Here")


def check_rolled():
    h.check("rolled back to the box", near(volume(), BOX), volume())
    states = [i.state for i in tl().items()]
    h.check(
        "Extrude 2 after the marker", states[3] == "rolled_back" and states[1] == "done", states
    )
    h.shot("4-rolled-back")


def drag_marker_to_end():
    marker = tl().marker()
    last = tl()._buttons[-1]
    end = last.mapToGlobal(last.rect().center()) + QtCore.QPoint(30, 0)
    w.drag(marker, QtCore.QPoint(4, 4), end)


def check_marker_end():
    h.check("marker dragged to the end: boss back", near(volume(), s["full"]), volume())
    h.check("marker at the end again", tl()._timeline.at_end)


def playback_start():
    w.click(tl().findChild(QtWidgets.QToolButton, "SciForgeTimeline_start"))


def check_start():
    h.check("Go to beginning: first extrude only", near(volume(), BOX), volume())


def playback_end():
    w.click(tl().findChild(QtWidgets.QToolButton, "SciForgeTimeline_end"))


def check_end():
    h.check("Go to end", near(volume(), s["full"]), volume())


# -- reorder by dragging --------------------------------------------------------------------
def drag_extrude_before_its_sketch():
    b = step_button("Extrude 2")
    target = step_button("Sketch 2")
    end = target.mapToGlobal(QtCore.QPoint(2, target.height() // 2))
    s["order"] = tl().titles()
    w.drag(b, w.center(b), end)


def check_refused():
    reason = tl().refusal()
    h.check(
        "refused with Fusion's reason",
        "Extrude 2 uses Sketch 2" in reason,
        reason,
    )
    h.check("order unchanged", tl().titles() == s["order"], tl().titles())
    h.shot("5-refused-move")


def drag_sketch_before_box():
    b = step_button("Sketch 2")
    target = step_button("Extrude 1")
    w.drag(b, w.center(b), target.mapToGlobal(QtCore.QPoint(2, target.height() // 2)))


def check_refused_2():
    reason = tl().refusal()
    h.check(
        "sketch on a face cannot go before that face", "Sketch 2 uses Extrude 1" in reason, reason
    )
    h.check("volume unchanged", near(volume(), s["full"]), volume())


# -- rename ---------------------------------------------------------------------------------
def rename_boss():
    menu("Extrude 2", "Rename")


def type_boss():
    editor = tl().findChild(QtWidgets.QLineEdit, "SciForgeTimelineRename")
    h.check("name field opens in place", editor is not None and editor.isVisible())
    if editor is not None:
        w.key(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(editor, "Boss")
        w.key(editor, QtCore.Qt.Key_Return)


def check_renamed():
    titles = tl().titles()
    h.check("renamed to Boss", titles[3] == "Boss", titles)
    h.check(
        "label stored", App.ActiveDocument.getObject(step_button("Boss").item.name).Label == "Boss"
    )


def rename_cancel():
    b = step_button("Extrude 1")
    w.click(b)
    w.key(b, QtCore.Qt.Key_F2)
    editor = tl().findChild(QtWidgets.QLineEdit, "SciForgeTimelineRename")
    h.check("F2 opens the name field", editor is not None)
    if editor is not None:
        w.type_text(editor, "zzz")
        w.key(editor, QtCore.Qt.Key_Escape)


def check_rename_cancelled():
    h.check("Esc keeps the old name", "Extrude 1" in tl().titles(), tl().titles())


# -- edit by double-click -------------------------------------------------------------------
def edit_box_cancel():
    w.double_click(step_button("Extrude 1"))


def edit_box_cancel_2():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check(
        "double-click opens Extrude on Extrude 1",
        p is not None
        and p.target is not None
        and p.target.Name == step_button("Extrude 1").item.name,
    )
    h.task_button("Cancel")


def check_cancel():
    h.check("Cancel leaves the part as it was", near(volume(), s["full"]), volume())


def edit_box():
    w.double_click(step_button("Extrude 1"))


def type_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    field = p.distance.widget
    w.click(field)
    w.key(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    w.type_text(field, "20")
    w.key(field, QtCore.Qt.Key_Tab)


def edit_ok():
    h.task_button("OK")


def check_edit():
    s["full20"] = BOX * 2 + BOSS
    h.check("box now 20 high, boss rides on top", near(volume(), s["full20"]), volume())
    h.check("still four steps", len(tl().titles()) == 4, tl().titles())


# -- edit profile sketch ----------------------------------------------------------------------
def edit_profile():
    menu("Boss", "Edit Profile Sketch")


def check_in_profile():
    sk = h.in_sketch()
    h.check(
        "editing the boss's sketch",
        sk is not None and sk.Name == step_button("Sketch 2").item.name,
        sk and sk.Name,
    )


def finish_profile():
    h.ribbon("Finish Sketch")


def check_after_profile():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("part unchanged", near(volume(), s["full20"]), volume())


# -- delete -----------------------------------------------------------------------------------
def select_boss():
    w.click(step_button("Boss"))


def check_selected():
    sel = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("click selects the step", sel == [step_button("Boss").item.name], sel)


def delete_key():
    w.key(step_button("Boss"), QtCore.Qt.Key_Delete)


def check_deleted():
    h.check("Delete key removes the boss", near(volume(), BOX * 2), volume())
    h.check(
        "three steps left", tl().titles() == ["Sketch 1", "Extrude 1", "Sketch 2"], tl().titles()
    )
    sk = App.ActiveDocument.getObject(step_button("Sketch 2").item.name)
    h.check("its sketch shows again", sk.ViewObject.Visibility)


def undo_delete():
    w.click(w.quick_access("Undo"))


def check_undo_delete():
    h.check("Undo restores the boss", near(volume(), s["full20"]), volume())
    h.check("Boss back in the timeline", "Boss" in tl().titles(), tl().titles())


def delete_sketch():
    menu("Sketch 2", "Delete")


def check_sketch_deleted():
    b = step_button("Boss")
    h.check("Boss shown red", b is not None and b.item.status == "error", b and b.item.status)
    h.check(
        "the reason is in the tooltip",
        b is not None and "profile" in b.toolTip().lower(),
        b and b.toolTip(),
    )
    h.check("the box is still there", volume() >= BOX * 2 - 1e-6, volume())
    h.shot("6-error-step")


def undo_delete_sketch():
    w.click(w.quick_access("Undo"))


def check_restored():
    h.check("Undo: sketch and boss back", near(volume(), s["full20"]), volume())
    h.check(
        "nothing red",
        all(i.status == "ok" for i in tl().items()),
        [(i.display, i.message) for i in tl().items()],
    )


# -- find in browser / window -------------------------------------------------------------------
def find_in_browser():
    menu("Sketch 1", "Find in Browser")


def check_found():
    from sciforge import browser_ui

    item = browser_ui.widget().currentItem()
    h.check(
        "browser shows Sketch 1's row",
        item is not None and item.text(1) == "Sketch",
        item and item.text(1),
    )


def find_in_window():
    menu("Extrude 1", "Find in Window")


def check_find_window():
    sel = [x.ObjectName for x in Gui.Selection.getSelectionEx()]
    h.check("Find in Window selects the body", sel == ["Body"], sel)


def second_suppress():
    """A second use of the same command."""
    menu("Boss", "Suppress Features")


def second_unsuppress():
    h.check("second suppress", near(volume(), BOX * 2), volume())
    menu("Boss", "Unsuppress Features")


# -- groups ----------------------------------------------------------------------------------
def header():
    for widget, _left, _right in tl()._slots:
        if widget.objectName().startswith("SciForgeGroup_"):
            return widget
    return None


def group_menu(entry):
    g = header()
    ok = g is not None and w.right_click(g, w.center(g), entry)
    h.check("group menu > %s" % entry, ok)


def select_two():
    s["sk2"] = step_button("Sketch 2").item.name
    s["boss"] = step_button("Boss").item.name
    w.click(step_button("Sketch 2"))
    w.click(step_button("Boss"), modifiers=QtCore.Qt.ShiftModifier)


def group_them():
    h.check("Shift+click selects both", tl().selected() == [s["sk2"], s["boss"]], tl().selected())
    menu("Boss", "Group Features")


def check_group():
    g = header()
    h.check("one folder for the group", g is not None)
    h.check("its steps are hidden while closed", tl().button(s["boss"]) is None)
    h.check(
        "timeline still knows all steps",
        tl().titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Boss"],
        tl().titles(),
    )
    h.check("part unchanged", near(volume(), s["full20"]), volume())
    h.shot("8-group")


def open_group():
    w.click(header())


def check_open():
    h.check("click opens the group", tl().button(s["boss"]) is not None)
    w.click(header())


def check_closed():
    h.check("click closes it again", tl().button(s["boss"]) is None)
    group_menu("Rename")


def type_group_name():
    editor = tl().findChild(QtWidgets.QLineEdit, "SciForgeTimelineRename")
    h.check("group name field", editor is not None)
    if editor is not None:
        w.key(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(editor, "Boss work")
        w.key(editor, QtCore.Qt.Key_Return)


def check_group_name():
    g = header()
    h.check("group renamed", g is not None and g.name == "Boss work", g and g.name)
    group_menu("Suppress Features")


def check_group_off():
    h.check("suppressing the group removes the boss", near(volume(), BOX * 2), volume())
    group_menu("Unsuppress Features")


def check_group_on():
    h.check("unsuppress brings it back", near(volume(), s["full20"]), volume())
    group_menu("Ungroup")


def check_ungrouped():
    h.check("ungrouped: no folder", header() is None)
    h.check("steps visible again", tl().button(s["boss"]) is not None)
    w.click(w.quick_access("Undo"))


def check_regrouped():
    h.check("Undo brings the group back", header() is not None)


def check_end_state():
    h.check("final part", near(volume(), s["full20"]), volume())
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("7-end")


h.run(
    "timeline_browser",
    [
        new_design,
        empty_timeline,
        create_sketch_1,
        pick_xy,
        draw_rect,
        finish_1,
        extrude_1,
        extrude_1_ok,
        check_box,
        create_sketch_2,
        pick_top,
        draw_circle,
        finish_2,
        extrude_2,
        extrude_2_ok,
        check_part,
        menu_entries,
        suppress_boss,
        check_suppressed,
        undo,
        check_undo_suppress,
        redo,
        check_redo_suppress,
        unsuppress_boss,
        check_unsuppressed,
        suppress_first,
        check_all_off,
        unsuppress_first,
        check_all_back,
        roll_here,
        check_rolled,
        drag_marker_to_end,
        check_marker_end,
        playback_start,
        check_start,
        playback_end,
        check_end,
        drag_extrude_before_its_sketch,
        check_refused,
        drag_sketch_before_box,
        check_refused_2,
        rename_boss,
        type_boss,
        check_renamed,
        rename_cancel,
        check_rename_cancelled,
        edit_box_cancel,
        edit_box_cancel_2,
        check_cancel,
        edit_box,
        type_distance,
        edit_ok,
        check_edit,
        edit_profile,
        check_in_profile,
        finish_profile,
        check_after_profile,
        select_boss,
        check_selected,
        delete_key,
        check_deleted,
        undo_delete,
        check_undo_delete,
        delete_sketch,
        check_sketch_deleted,
        undo_delete_sketch,
        check_restored,
        find_in_browser,
        check_found,
        find_in_window,
        check_find_window,
        second_suppress,
        second_unsuppress,
        select_two,
        group_them,
        check_group,
        open_group,
        check_open,
        check_closed,
        type_group_name,
        check_group_name,
        check_group_off,
        check_group_on,
        check_ungrouped,
        check_regrouped,
        check_end_state,
    ],
)
