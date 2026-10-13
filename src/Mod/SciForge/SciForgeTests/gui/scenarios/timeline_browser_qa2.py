# SPDX-License-Identifier: LGPL-2.1-or-later
"""The timeline on a part made of several features (QA, only real input).

Part: box 40 x 30 x 10, a hole r5 through the middle (sketch on the top face, E into
the part = Cut), an r2 round on the front top edge (F).

Path 6, several steps at once: Shift+click two steps, right-click, Suppress Features
        (Fusion offers it for a selection); the round after them keeps working.
        Unsuppress brings the hole back. No balloon, no Report-view line.
Path 7, suppress the first extrude (everything built on it goes off), unsuppress.
Path 8, rename with command letters in the name (F2, "Front edge round": F and E
        must go into the field, not start Fillet / Extrude), Esc in a second rename.
Path 9, Ctrl+click two steps, Delete key: the round after them keeps working; Ctrl+Z.
Path 10, a visible sketch after the marker is not drawn (it does not exist yet at the
        marker), and is drawn again at the end.
Path 11, save, close, reopen: same timeline; double-click the round, change it, OK,
        Ctrl+Z; drag the round before the hole's sketch (allowed), Ctrl+Z.

Numbers by hand: box 12000; hole r5 through 10 = 250 pi; a radius r round along the
40 mm front edge removes 40 r^2 (1 - pi/4).
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOX = 12000.0
HOLE = 250.0 * math.pi
FRONT_TOP = V(20, 0, 10)


def round_off(r):
    return 40.0 * b.spandrel(r)


FULL = BOX - HOLE - round_off(2)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


# -- the part ------------------------------------------------------------------------------
def hole_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def hole_pick_top():
    h.fit()
    h.click(V(30, 20, 10))


def hole_circle():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, 10))
        h.draw_circle(sk, x, y, 5)


def hole_finish():
    h.ribbon("Finish Sketch")


def hole_e():
    h.fit()
    h.press("e")


def hole_depth():
    p = xpanel()
    h.check("Extrude picked the circle", p is not None and len(p.profiles) == 1)
    if p is not None:
        ui.type_into(p.distance.widget, "-10")


def hole_ok():
    p = xpanel()
    h.check("into the part: Cut", p is not None and p.operation.currentText() == "Cut")
    h.task_button("OK")


def fillet_start():
    h.click_empty()
    h.fit()
    h.press("f")


def fillet_edge():
    h.click_edge(FRONT_TOP)


def fillet_radius():
    p = b.blend_panel()
    h.check("fillet dialog has the edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p is not None:
        ui.type_into(p.radius.widget, "2")


def fillet_ok():
    h.task_button("OK")


def part_made():
    h.check("box, hole, round", t.near(t.volume(), FULL), t.volume())
    h.check(
        "five steps",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Fillet 1"],
        t.titles(),
    )
    h.shot("1-part")


# -- Path 6: several steps at once -------------------------------------------------------------
def p6_select_two():
    t.click("Sketch 2")
    t.click("Extrude 2", QtCore.Qt.ShiftModifier)


def p6_menu():
    picked = t.tl().selected()
    h.check("Shift+click selects both", len(picked) == 2, picked)
    entries = dict(t.menu_entries("Extrude 2"))
    h.check(
        "Suppress Features offered for a selection",
        entries.get("Suppress Features") is True,
        entries,
    )


def p6_suppress():
    t.menu("Extrude 2", "Suppress Features")


def p6_suppressed():
    st = t.states()
    h.check(
        "both suppressed",
        st["Sketch 2"][2] and st["Extrude 2"][2],
        st,
    )
    h.check("the round keeps working", not st["Fillet 1"][2] and st["Fillet 1"][1] == "ok", st)
    h.check("box with the round, no hole", t.near(t.volume(), BOX - round_off(2)), t.volume())
    h.check(
        "a suppressed step is not shown yellow or red",
        st["Sketch 2"][1] == "ok" and st["Extrude 2"][1] == "ok",
        st,
    )
    h.shot("2-two-suppressed")


def p6_unsuppress():
    t.menu("Extrude 2", "Unsuppress Features")


def p6_back():
    st = t.states()
    h.check("both back", not st["Sketch 2"][2] and not st["Extrude 2"][2], st)
    h.check("whole part again", t.near(t.volume(), FULL), t.volume())
    h.check("nothing red or yellow", all(v[1] == "ok" for v in st.values()), st)


# -- Path 7: suppress the first extrude ------------------------------------------------------------
def p7_suppress_first():
    t.menu("Extrude 1", "Suppress Features")


def p7_all_off():
    st = t.states()
    h.check(
        "everything built on it goes off",
        all(st[k][2] for k in ("Extrude 1", "Sketch 2", "Extrude 2", "Fillet 1")),
        st,
    )
    h.check("nothing left", t.volume() < 1e-6, t.volume())
    h.check("no step red or yellow", all(v[1] == "ok" for v in st.values()), st)
    h.check("the hole sketch is not drawn", not t.shown(t.obj("Sketch 2")))
    h.shot("3-first-off")


def p7_unsuppress():
    t.menu("Extrude 1", "Unsuppress Features")


def p7_back():
    st = t.states()
    h.check("all back on", not any(v[2] for v in st.values()), st)
    h.check("whole part again", t.near(t.volume(), FULL), t.volume())
    h.check("nothing red or yellow", all(v[1] == "ok" for v in st.values()), st)


# -- Path 8: rename with command letters ----------------------------------------------------------------
def p8_rename():
    t.click("Fillet 1")
    w.key(t.button("Fillet 1"), QtCore.Qt.Key_F2)


def p8_type():
    field = t.rename_field()
    h.check("F2 opens the name field", field is not None and field.isVisible())
    if field is not None:
        w.key(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(field, "Front edge round")


def p8_enter():
    h.check("no command started by the letters", not t.dialog_open())
    field = t.rename_field()
    h.check(
        "the whole name is in the field",
        field is not None and field.text() == "Front edge round",
        field and field.text(),
    )
    if field is not None:
        w.key(field, QtCore.Qt.Key_Return)


def p8_renamed():
    h.check("renamed", "Front edge round" in t.titles(), t.titles())
    h.check("no dialog open", not t.dialog_open())


def p8_rename_esc():
    t.menu("Extrude 2", "Rename")


def p8_type_esc():
    field = t.rename_field()
    if h.check("name field open", field is not None):
        w.type_text(field, "zzz")
        w.key(field, QtCore.Qt.Key_Escape)


def p8_esc_kept():
    h.check("Esc keeps the old name", "Extrude 2" in t.titles(), t.titles())
    h.check("Esc did not close anything else", not t.dialog_open())


# -- Path 9: delete two steps with the Delete key ---------------------------------------------------------
def p9_select():
    t.click("Sketch 2")
    t.click("Extrude 2", QtCore.Qt.ControlModifier)


def p9_delete():
    picked = t.tl().selected()
    h.check("Ctrl+click selects both", len(picked) == 2, picked)
    w.key(t.button("Extrude 2"), QtCore.Qt.Key_Delete)


def p9_deleted():
    h.check(
        "both gone",
        t.titles() == ["Sketch 1", "Extrude 1", "Front edge round"],
        t.titles(),
    )
    i = t.item("Front edge round")
    h.check(
        "the round after them keeps working", i is not None and i.status == "ok", i and i.message
    )
    h.check("box with the round", t.near(t.volume(), BOX - round_off(2)), t.volume())
    h.shot("4-deleted")


def p9_undo():
    t.ctrl("z")


def p9_restored():
    h.check("Ctrl+Z brings both back", len(t.titles()) == 5, t.titles())
    h.check("whole part", t.near(t.volume(), FULL), t.volume())
    st = t.states()
    h.check("nothing red or yellow", all(v[1] == "ok" for v in st.values()), st)


# -- Path 10: a visible sketch after the marker ---------------------------------------------------------
def p10_show_sketch():
    t.click_eye(t.obj("Sketch 2").Label)


def p10_roll_back():
    h.check("the hole sketch is shown", t.shown(t.obj("Sketch 2")))
    t.drag_marker(before_title="Sketch 2")


def p10_rolled():
    h.check("rolled back to the box", t.near(t.volume(), BOX), t.volume())
    h.check(
        "a sketch after the marker is not drawn",
        not t.shown(t.obj("Sketch 2")),
    )
    h.shot("5-rolled-sketch")
    t.drag_marker(to_end=True)


def p10_end():
    h.check("at the end the sketch is drawn again", t.shown(t.obj("Sketch 2")))
    h.check("whole part", t.near(t.volume(), FULL), t.volume())
    t.click_eye(t.obj("Sketch 2").Label)


# -- Path 11: save, close, reopen ----------------------------------------------------------------------------
def p11_save():
    s["path"] = os.path.join(tempfile.mkdtemp(), "timeline_qa2.FCStd")
    s["titles"] = t.titles()
    t.doc().saveAs(s["path"])


def p11_close():
    App.closeDocument(t.doc().Name)


def p11_open():
    App.openDocument(s["path"])
    h.fit()


def p11_reopened():
    h.check("same timeline after reopening", t.titles() == s["titles"], (t.titles(), s["titles"]))
    h.check("marker at the end", t.tl()._timeline.at_end)
    h.check("whole part", t.near(t.volume(), FULL), t.volume())
    st = t.states()
    h.check("nothing red or yellow", all(v[1] == "ok" for v in st.values()), st)
    h.check("browser lists the body", any(l.startswith("Body") for l in t.labels()), t.labels())
    t.double_click("Front edge round")


def p11_editing():
    p = b.blend_panel()
    h.check("double-click opens the round", p is not None)
    if p is not None:
        ui.type_into(p.radius.widget, "1")


def p11_ok():
    h.task_button("OK")


def p11_edited():
    s["r1"] = BOX - HOLE - round_off(1)
    h.check("round now r1", t.near(t.volume(), s["r1"]), t.volume())
    t.ctrl("z")


def p11_undone():
    h.check("Ctrl+Z: r2 again", t.near(t.volume(), FULL), t.volume())


def p11_drag():
    t.drag_step("Front edge round", before_title="Sketch 2")


def p11_moved():
    titles = t.titles()
    h.check(
        "the round moved before the hole",
        titles == ["Sketch 1", "Extrude 1", "Front edge round", "Sketch 2", "Extrude 2"],
        (titles, t.tl().refusal()),
    )
    h.check("same part", t.near(t.volume(), FULL), t.volume())
    st = t.states()
    h.check("nothing red or yellow", all(v[1] == "ok" for v in st.values()), st)
    t.ctrl("z")


def p11_move_undone():
    h.check("Ctrl+Z puts it back", t.titles() == s["titles"], t.titles())
    h.check("same part", t.near(t.volume(), FULL), t.volume())


def end():
    t.no_popups("the end")
    h.shot("6-end")


STEPS = b.box_steps("TimelineQA2") + [
    hole_sketch,
    hole_pick_top,
    hole_circle,
    hole_finish,
    hole_e,
    hole_depth,
    hole_ok,
    fillet_start,
    fillet_edge,
    fillet_radius,
    fillet_ok,
    part_made,
    p6_select_two,
    p6_menu,
    p6_suppress,
    p6_suppressed,
    p6_unsuppress,
    p6_back,
    p7_suppress_first,
    p7_all_off,
    p7_unsuppress,
    p7_back,
    p8_rename,
    p8_type,
    p8_enter,
    p8_renamed,
    p8_rename_esc,
    p8_type_esc,
    p8_esc_kept,
    p9_select,
    p9_delete,
    p9_deleted,
    p9_undo,
    p9_restored,
    p10_show_sketch,
    p10_roll_back,
    p10_rolled,
    p10_end,
    p11_save,
    p11_close,
    p11_open,
    p11_reopened,
    p11_editing,
    p11_ok,
    p11_edited,
    p11_undone,
    p11_drag,
    p11_moved,
    p11_move_undone,
    end,
]

h.run("timeline_browser_qa2", t.watched(STEPS))
