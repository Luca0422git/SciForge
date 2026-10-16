# SPDX-License-Identifier: LGPL-2.1-or-later
"""Timeline groups dragged as a whole, the marker over a group, like Fusion
(docs/sciforge/parity/timeline-browser.md). Only real input.

Body 1: a box 40 x 30 x 10 (Sketch 1, Extrude 1); body 2 beside it (Sketch 2, Extrude 2,
a New Body 20 x 20 x 10); a boss r5 x 5 on the box's top (Sketch 3, Extrude 3). Sketch 2 +
Extrude 2 are grouped (Group 1), Sketch 3 + Extrude 3 too (Group 2).

P1 Drag Group 1's folder before Sketch 1: its two steps move together, before the box,
   still grouped and in their order; both bodies keep their volume.
P2 Ctrl+Z puts the group back after Extrude 1, Ctrl+Y moves it again.
P3 Drag Group 2's folder before Extrude 1: refused with the reason (Sketch 3 sits on
   Extrude 1's face); nothing moved.
P4 Group 2 opened, the marker dragged between Sketch 3 and Extrude 3: the group shows open
   with the marker inside; Collapse Group is greyed; a click on its folder keeps it open
   and says why; dragging its folder is refused (the marker is inside).
P5 Group 2 > Roll History Marker Here: the marker after Extrude 3 (the end), the boss
   back; a click on the folder now closes the group.
P6 Esc while dragging a folder: nothing moves. Rename Group 1 "Side body"; Ungroup Group 2:
   its folder goes, its steps stay; Ctrl+Z brings the group back.
P7 Saved, closed and opened again: the order (Sketch 2, Extrude 2 first) and the groups
   are kept.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOX = 12000.0
BOSS = math.pi * 25.0 * 5.0
SIDE = 4000.0


def tl():
    return t.tl()


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def bodies():
    return [o for o in t.doc().Objects if o.TypeId == "PartDesign::Body"]


def volumes():
    return sorted(round(t.volume(o), 3) for o in bodies())


def header(name):
    for widget, _left, _right in tl()._slots:
        if widget.objectName().startswith("SciForgeGroup_") and widget.name == name:
            return widget
    return None


def groups():
    """{group name: [member titles]} as the timeline knows them."""
    found = {}
    for item in tl().items():
        if item.group:
            found.setdefault(item.group_name, []).append(item.display)
    return found


def drag_header(name, before_title=None, after_last=False):
    g = header(name)
    if not h.check("the folder of %s is shown" % name, g is not None):
        return False
    if after_last:
        last = tl()._buttons[-1]
        end = last.mapToGlobal(QtCore.QPoint(last.width() + 6, last.height() // 2))
    else:
        target = t.button(before_title)
        if target is None:
            return False
        end = target.mapToGlobal(QtCore.QPoint(2, target.height() // 2))
    w.drag(g, w.center(g), end)
    return True


def group_menu(name, entry):
    g = header(name)
    ok = g is not None and w.right_click(g, w.center(g), entry)
    h.check("%s menu > %s" % (name, entry), ok)
    return ok


def group_menu_entries(name):
    g = header(name)
    return w.menu_texts(g, w.center(g)) if g is not None else []


# -- building the design (real input) ----
def side_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def side_xy():
    pl.click_square("XY_Plane")  # where the square shows (was -15, -12, 0)


def side_draw():
    sk = h.in_sketch()
    h.check("sketch on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -40, -40, -20, -20)


def side_finish():
    h.ribbon("Finish Sketch")


def side_extrude():
    h.fit()
    h.press("e")


def side_new_body():
    p = xpanel()
    if h.check("Extrude picked the square", p is not None and bool(p.profiles)):
        ui.choose(p.operation, "New Body")


def side_ok():
    arrows.type_distance("10")
    h.task_button("OK")


def boss_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def boss_top():
    h.click(V(20, 15, 10))


def boss_draw():
    sk = h.in_sketch()
    h.check("sketch on the top", sk is not None)
    if sk:
        h.draw_circle(sk, 20, 15, 5)


def boss_finish():
    h.ribbon("Finish Sketch")


def boss_extrude():
    h.fit()
    h.press("e")


def boss_ok():
    arrows.type_distance("5")
    h.task_button("OK")


def built():
    h.check(
        "the timeline: two sketches and extrudes per body",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Sketch 3", "Extrude 3"],
        t.titles(),
    )
    s["volumes"] = sorted([round(BOX + BOSS, 3), round(SIDE, 3)])
    h.check("the box with its boss, and the side body", volumes() == s["volumes"], volumes())
    t.click("Sketch 2")
    t.click("Extrude 2", QtCore.Qt.ShiftModifier)


def group_one():
    t.menu("Extrude 2", "Group Features")


def group_two():
    t.click("Sketch 3")
    t.click("Extrude 3", QtCore.Qt.ShiftModifier)
    t.menu("Extrude 3", "Group Features")


def grouped():
    h.check(
        "two groups",
        groups() == {"Group 1": ["Sketch 2", "Extrude 2"], "Group 2": ["Sketch 3", "Extrude 3"]},
        groups(),
    )
    h.check("both shown closed", header("Group 1") is not None and not header("Group 1").opened)
    h.shot("0-groups")


# -- P1: drag a group before an earlier step ----
def p1_drag():
    drag_header("Group 1", before_title="Sketch 1")


def p1_moved():
    h.check(
        "P1 the group's steps went first, in their order",
        t.titles() == ["Sketch 2", "Extrude 2", "Sketch 1", "Extrude 1", "Sketch 3", "Extrude 3"],
        t.titles(),
    )
    h.check("P1 still one group", groups().get("Group 1") == ["Sketch 2", "Extrude 2"], groups())
    h.check(
        "P1 the folder is shown first",
        header("Group 1") is not None and tl()._slots[0][0] is header("Group 1"),
    )
    h.check("P1 both bodies as they were", volumes() == s["volumes"], volumes())
    h.check("P1 nothing red", all(st[1] == "ok" for st in t.states().values()), t.states())
    h.shot("P1-group-moved")
    t.undo()


def p2_undone():
    h.check(
        "P2 Ctrl+Z: the group back after Extrude 1",
        t.titles()[:4] == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        t.titles(),
    )
    h.check("P2 bodies unchanged", volumes() == s["volumes"], volumes())
    t.redo()


def p2_redone():
    h.check("P2 Ctrl+Y: moved again", t.titles()[:2] == ["Sketch 2", "Extrude 2"], t.titles())


# -- P3: refused ----
def p3_drag():
    s["before"] = t.titles()
    drag_header("Group 2", before_title="Extrude 1")


def p3_refused():
    reason = tl().refusal()
    h.check(
        "P3 refused with the reason",
        "Sketch 3 uses Extrude 1" in reason and "Group 2" in reason,
        reason,
    )
    h.check("P3 nothing moved", t.titles() == s["before"], t.titles())


# -- P4: the marker inside a group ----
def p4_open():
    w.click(header("Group 2"))


def p4_marker():
    h.check("P4 Group 2 opened", header("Group 2") is not None and header("Group 2").opened)
    t.drag_marker(before_title="Extrude 3")


def p4_inside():
    g = header("Group 2")
    h.check("P4 the marker stands inside Group 2", g is not None and g.holds_marker)
    h.check("P4 Extrude 3 rolled back", t.states()["Extrude 3"][0] == "rolled_back", t.states())
    entries = dict(group_menu_entries("Group 2"))
    h.check("P4 Collapse Group is greyed", entries.get("Collapse Group") is False, entries)
    h.check("P4 Roll History Marker Here offered", entries.get("Roll History Marker Here"), entries)
    w.click(header("Group 2"))


def p4_stays_open():
    h.check(
        "P4 a click keeps it open (the marker is inside)",
        header("Group 2") is not None and header("Group 2").opened,
    )
    drag_header("Group 2", after_last=True)


def p4_refused():
    reason = tl().refusal()
    h.check("P4 dragging it is refused: the marker is inside", "marker is inside" in reason, reason)


# -- P5: Roll History Marker Here on the group ----
def p5_roll():
    group_menu("Group 2", "Roll History Marker Here")


def p5_rolled():
    h.check("P5 the marker at the end", tl()._timeline.at_end, tl()._timeline.marker)
    h.check("P5 the boss is back", volumes() == s["volumes"], volumes())
    w.click(header("Group 2"))


def p5_closed():
    h.check(
        "P5 now the folder closes", header("Group 2") is not None and not header("Group 2").opened
    )


# -- P6: Esc while dragging, rename, ungroup ----
def p6_esc_drag():
    g = header("Group 1")
    s["before"] = t.titles()
    start = w.center(g)
    w.move(g, start)
    QtTest.QTest.mousePress(g, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
    for dx in (5, 12, 30, 60):
        QtTest.QTest.mouseMove(g, QtCore.QPoint(start.x() + dx, start.y()))
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyClick(g, QtCore.Qt.Key_Escape)
    QtTest.QTest.mouseRelease(
        g, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(start.x() + 60, start.y())
    )
    QtWidgets.QApplication.processEvents()


def p6_nothing():
    h.check("P6 Esc: nothing moved", t.titles() == s["before"], t.titles())
    group_menu("Group 1", "Rename")


def p6_type_name():
    editor = t.rename_field()
    if h.check("P6 the group's name field", editor is not None):
        editor.selectAll()
        QtTest.QTest.keyClicks(editor, "Side body")
        QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
        QtWidgets.QApplication.processEvents()


def p6_renamed():
    h.check("P6 renamed", "Side body" in groups(), groups())
    group_menu("Group 2", "Ungroup")


def p6_ungrouped():
    h.check("P6 Group 2's folder went", header("Group 2") is None and "Group 2" not in groups())
    h.check("P6 its steps stay", t.titles()[-2:] == ["Sketch 3", "Extrude 3"], t.titles())
    t.undo()


def p6_back():
    h.check(
        "P6 Ctrl+Z: Group 2 again", groups().get("Group 2") == ["Sketch 3", "Extrude 3"], groups()
    )


# -- P7: save and open again ----
def p7_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-groups-"), "Groups.FCStd")
    s["path"] = path
    t.doc().saveAs(path)
    Gui.getDocument(t.doc().Name).Modified = False
    App.closeDocument(t.doc().Name)
    App.openDocument(path)


def p7_reopened():
    h.check(
        "P7 the order is kept",
        t.titles() == ["Sketch 2", "Extrude 2", "Sketch 1", "Extrude 1", "Sketch 3", "Extrude 3"],
        t.titles(),
    )
    h.check(
        "P7 the groups are kept",
        groups() == {"Side body": ["Sketch 2", "Extrude 2"], "Group 2": ["Sketch 3", "Extrude 3"]},
        groups(),
    )
    h.check("P7 the bodies as they were", volumes() == s["volumes"], volumes())
    h.check("P7 nothing red", all(st[1] == "ok" for st in t.states().values()), t.states())


STEPS = b.box_steps("Polish2Groups") + [
    side_sketch,
    side_xy,
    side_draw,
    side_finish,
    side_extrude,
    side_new_body,
    side_ok,
    boss_sketch,
    boss_top,
    boss_draw,
    boss_finish,
    boss_extrude,
    boss_ok,
    built,
    group_one,
    group_two,
    grouped,
    p1_drag,
    p1_moved,
    p2_undone,
    p2_redone,
    p3_drag,
    p3_refused,
    p4_open,
    p4_marker,
    p4_inside,
    p4_stays_open,
    p4_refused,
    p5_roll,
    p5_rolled,
    p5_closed,
    p6_esc_drag,
    p6_nothing,
    p6_type_name,
    p6_renamed,
    p6_ungrouped,
    p6_back,
    p7_save,
    p7_reopened,
]

h.run("polish2_timeline_groups", STEPS)
