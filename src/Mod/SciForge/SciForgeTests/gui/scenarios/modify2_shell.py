# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell of two bodies in one step (Fusion's Shell takes faces of several bodies), only real
input, then the same Shell edited, undone, saved and opened again.

Part: Body1 the 40 x 30 x 10 box (blend_steps.box_steps); Body2 a 20 x 30 x 10 box at x = 50
(Create Sketch on XY, a rectangle, E, 10, OK: it touches nothing, so it is a new body).

Path S1, Shell with nothing selected: click Body1's top face, then Body2's top face: one Shell
        takes both away, 1 mm inside walls in both bodies (the second body gets its hidden
        follower step). Type 2: both walls 2 mm. OK: one "Shell 1" in the timeline.
Path S2, Ctrl+Z: both bodies solid again, in one undo step; Ctrl+Y: both shelled.
Path S3, the Shell edited from the timeline: it shows both bodies' faces; Body2's top clicked
        again is dropped: Body2 is solid again in the preview; OK: no follower left. Ctrl+Z
        brings the two-body Shell back.
Path S4, save, close, open again: both bodies still shelled, the Shell opens for editing with
        the other body in it; Cancel changes nothing.
Path S5, the Shell deleted from the timeline: its step in Body2 goes with it.

Volumes: an open-topped box a x b x c with an inside wall t: a b c - (a-2t)(b-2t)(c-t).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
s = {}
TOP1 = V(20, 15, 10)
TOP2 = V(60, 15, 10)


def open_box(a, bb, c, t):
    return a * bb * c - (a - 2 * t) * (bb - 2 * t) * (c - t)


def panel():
    return m.panel_of("shell_ui", "ShellPanel")


def body2():
    name = s.get("b2")
    return App.ActiveDocument.getObject(name) if name else None


def body1():
    name = s.get("b1")
    return App.ActiveDocument.getObject(name) if name else None


def volumes():
    return m.body_volume(body1()), m.body_volume(body2())


# -- the second body -----------------------------------------------------------------------------
def second_sketch():
    s["b1"] = h.body().Name
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def second_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def second_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 50, 0, 70, 30)


def second_finish():
    h.ribbon("Finish Sketch")


def second_extrude():
    h.fit()
    h.press("e")


def second_distance():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None) if p else None
    if h.check("Extrude open", field is not None):
        b.type_into(field, "10")


def second_ok():
    h.task_button("OK")


def two_bodies():
    found = m.bodies_list()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    others = [x for x in found if x.Name != s["b1"]]
    if others:
        s["b2"] = others[0].Name
    v1, v2 = volumes()
    h.check("Body1 40 x 30 x 10", m.close(v1, 12000.0), v1)
    h.check("Body2 20 x 30 x 10", m.close(v2, 6000.0), v2)
    h.fit()


# -- S1 -------------------------------------------------------------------------------------------
def shell_start():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.ribbon("Shell")


def click_top1():
    p = panel()
    h.check("Shell dialog waits", p is not None and not p.has_picks())
    h.fit()
    h.click(TOP1)


def click_top2():
    p = panel()
    h.check("Body1's top face picked", p is not None and len(p.names()) == 1, p and p.names())
    h.click(TOP2)


def both_picked():
    p = panel()
    if p is None:
        return
    h.check("Body2 joined the same Shell", len(p.members) == 1 and p.members[0].body is body2())
    h.check("its top face picked", len(p.member_names(p.members[0])) == 1)
    h.check(
        "the box says the other body",
        "other bod" in p.selection.button.text(),
        p.selection.button.text(),
    )
    v1, v2 = volumes()
    h.check("Body1: 1 mm wall", m.close(v1, open_box(40, 30, 10, 1)), v1)
    h.check("Body2: 1 mm wall", m.close(v2, open_box(20, 30, 10, 1)), v2)
    h.shot("1-two-bodies")
    sd.type_into(p.inside.widget, "2")


def two_mm():
    v1, v2 = volumes()
    h.check("Body1: 2 mm wall", m.close(v1, open_box(40, 30, 10, 2)), v1)
    h.check("Body2: 2 mm wall", m.close(v2, open_box(20, 30, 10, 2)), v2)
    h.task_button("OK")


def after_ok():
    h.check("dialog closed", m.no_dialog())
    titles = sd.timeline_titles()
    h.check(
        "one Shell step in the timeline",
        titles.count("Shell 1") == 1 and "Shell 2" not in titles,
        titles,
    )
    h.check("Body2 has the hidden follower step", len(m.followers()) == 1, m.followers())
    v1, v2 = volumes()
    h.check(
        "kept: both shelled 2 mm",
        m.close(v1, open_box(40, 30, 10, 2)) and m.close(v2, open_box(20, 30, 10, 2)),
        (v1, v2),
    )
    h.check("both valid", body1().Shape.isValid() and body2().Shape.isValid())
    s["shelled"] = (v1, v2)
    h.check("no leftover selection", not Gui.Selection.getSelectionEx(), m.selected_names())


# -- S2 -------------------------------------------------------------------------------------------
def undo():
    m.undo()


def after_undo():
    v1, v2 = volumes()
    h.check("Ctrl+Z: both solid again", m.close(v1, 12000.0) and m.close(v2, 6000.0), (v1, v2))
    h.check("no follower left", not m.followers(), m.followers())


def redo():
    m.redo()


def after_redo():
    v1, v2 = volumes()
    h.check(
        "Ctrl+Y: both shelled",
        m.close(v1, s["shelled"][0]) and m.close(v2, s["shelled"][1]),
        (v1, v2),
    )
    h.fit()


# -- S3 -------------------------------------------------------------------------------------------
def edit():
    sd.timeline_double_click("Shell 1")


def edit_open():
    p = panel()
    h.check("the Shell dialog opens on the step", p is not None and p.editing)
    if p is None:
        return
    h.check("it shows Body2 too", len(p.members) == 1 and p.members[0].body is body2())
    h.check("2 mm", abs(p.inside.value() - 2.0) < 1e-9, p.inside.value())
    h.shot("2-edit")
    h.fit()
    h.click(TOP2)


def dropped():
    p = panel()
    if p is None:
        return
    h.check("Body2 dropped from the Shell", not p.members, p.members)
    v1, v2 = volumes()
    h.check("preview: Body2 solid again", m.close(v2, 6000.0), v2)
    h.check("Body1 still shelled", m.close(v1, s["shelled"][0]), v1)
    h.task_button("OK")


def after_edit():
    h.check("dialog closed", m.no_dialog())
    h.check("Body2's follower is gone", not m.followers(), m.followers())
    v1, v2 = volumes()
    h.check(
        "Body2 solid, Body1 shelled", m.close(v2, 6000.0) and m.close(v1, s["shelled"][0]), (v1, v2)
    )


def edit_undone():
    v1, v2 = volumes()
    h.check("Ctrl+Z: both shelled again", m.close(v2, s["shelled"][1]), (v1, v2))
    h.check("the follower is back", len(m.followers()) == 1, m.followers())


# -- S4 -------------------------------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-modify2-"), "two_shells.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    found = m.bodies_list()
    by_label = {x.Label: x for x in found}
    s["b1"] = found[0].Name if found else None
    s["b2"] = found[1].Name if len(found) > 1 else None
    h.check("two bodies after reopening", len(found) == 2, list(by_label))
    v1, v2 = volumes()
    h.check(
        "both still shelled",
        m.close(v1, s["shelled"][0]) and m.close(v2, s["shelled"][1]),
        (v1, v2),
    )
    h.check(
        "one Shell in the timeline",
        sd.timeline_titles().count("Shell 1") == 1,
        sd.timeline_titles(),
    )
    sd.timeline_double_click("Shell 1")


def reopened_edit():
    p = panel()
    h.check("the Shell opens for editing after reopening", p is not None and p.editing)
    h.check("with Body2 in it", p is not None and len(p.members) == 1)
    h.task_button("Cancel")


def reopened_cancel():
    h.check("dialog closed", m.no_dialog())
    v1, v2 = volumes()
    h.check(
        "Cancel changes nothing",
        m.close(v1, s["shelled"][0]) and m.close(v2, s["shelled"][1]),
        (v1, v2),
    )


# -- S5 -------------------------------------------------------------------------------------------
def delete_shell():
    ti.menu("Shell 1", "Delete")


def after_delete():
    QtCore.QCoreApplication.processEvents()
    v1, v2 = volumes()
    h.check(
        "deleting the Shell: both solid", m.close(v1, 12000.0) and m.close(v2, 6000.0), (v1, v2)
    )
    h.check("its step in Body2 went with it", not m.followers(), m.followers())
    h.check("no Shell in the timeline", "Shell 1" not in sd.timeline_titles(), sd.timeline_titles())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-end")


h.run(
    "modify2_shell",
    sd.box_steps("Modify2Shell")
    + [
        second_sketch,
        second_plane,
        second_draw,
        second_finish,
        second_extrude,
        second_distance,
        second_ok,
        two_bodies,
        shell_start,
        click_top1,
        click_top2,
        both_picked,
        two_mm,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        dropped,
        after_edit,
        undo,
        edit_undone,
        save,
        close,
        reopen,
        reopened,
        reopened_edit,
        reopened_cancel,
        delete_shell,
        after_delete,
    ],
)
