# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull's Offset Type (Fusion: Automatic, Modify Existing Feature, New Offset), only
real input.

Part: the 40 x 30 x 10 box (blend_steps.box_steps: Sketch 1, Extrude 1).

Path T1, Q with nothing selected: Offset Type lists Automatic (chosen), Modify Existing
        Feature, New Offset. Choose Modify Existing Feature, click the top face, type 5: the
        box is 15 high because Extrude 1 is now 15 long; the dialog says Extrude 1 changes.
        OK: no new step in the timeline. Ctrl+Z: Extrude 1 is 10 again; Ctrl+Y: 15.
Path T2, Q, click the top face, New Offset, type 5: a Press Pull step pulls the top to 20.
        OK: one Press Pull in the timeline, Extrude 1 still 15.
Path T3, Q, Modify Existing Feature, click the top face (put there by the Press Pull), type 2:
        the Press Pull's distance becomes 7, the box 22 high; OK: still one Press Pull.
Path T4, Q, Modify Existing Feature, click the front face (a side of Extrude 1, not its end):
        the dialog says no feature can be changed to move it and to use New Offset; OK waits;
        Esc: nothing changed.

Volumes: 40 x 30 x h = 1200 h.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}


def panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return None if p is None or p._closed else p


def extrude1():
    found = [
        o for o in h.body().Group if o.TypeId in ("PartDesign::Pad", "PartDesign::FeaturePython")
    ]
    found = [o for o in found if getattr(o, "Length", None) is not None]
    return found[0] if found else None


def length():
    e = extrude1()
    return e.Length.Value if e is not None else None


def press_pulls():
    return [o for o in h.body().Group if getattr(o, "SciForgeType", "") == "PressPull"]


def high(z):
    return 1200.0 * z


def start_q():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("q")


# -- T1 -------------------------------------------------------------------------------------------
def offset_types():
    p = panel()
    if not h.check("Q opens Press Pull", p is not None):
        return
    s["titles"] = sd.timeline_titles()
    labels = [p.offset_type.itemText(i) for i in range(p.offset_type.count())]
    want = ["Automatic", "Modify Existing Feature", "New Offset"]
    h.check("Offset Type: Automatic, Modify Existing Feature, New Offset", labels == want, labels)
    h.check("Automatic first", p.offset_type.currentText() == "Automatic")
    h.check("Offset Type shows", p.offset_type.isVisible())
    h.check("choose Modify Existing Feature", ui.choose(p.offset_type, "Modify Existing Feature"))


def click_top():
    h.click(V(20, 15, 10))


def modify_picked():
    p = panel()
    if p is None:
        return
    h.check("the top face picked", len(p.names) == 1, (p.names, p.message.text()))
    h.check("the dialog says Extrude 1 changes", "Extrude 1" in p.what.text(), p.what.text())
    ui.type_into(p.field.widget, "5")


def lengthened():
    v = h.solid_volume()
    h.check("Extrude 1 is 15 long: 15 high", m.close(v, high(15)), v)
    h.check("Extrude 1's distance is 15", abs(length() - 15.0) < 1e-9, length())
    h.check("no Press Pull step made", not press_pulls(), press_pulls())
    h.shot("1-modify")
    h.task_button("OK")


def after_modify():
    h.check("dialog closed", m.no_dialog())
    h.check("kept", m.close(h.solid_volume(), high(15)), h.solid_volume())
    titles = sd.timeline_titles()
    h.check("no new step in the timeline", s.setdefault("titles", titles) == titles, titles)
    h.check("no Press Pull in it", not [x for x in titles if "Press" in x], titles)
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())


def undo():
    m.undo()


def after_undo():
    h.check("Ctrl+Z: Extrude 1 is 10 again", abs(length() - 10.0) < 1e-9, length())
    h.check("10 high", m.close(h.solid_volume(), high(10)), h.solid_volume())


def redo():
    m.redo()


def after_redo():
    h.check("Ctrl+Y: 15", abs(length() - 15.0) < 1e-9, length())
    h.check("15 high", m.close(h.solid_volume(), high(15)), h.solid_volume())


# -- T2 -------------------------------------------------------------------------------------------
def click_top_15():
    h.click(V(20, 15, 15))


def new_offset():
    p = panel()
    if p is None:
        return
    h.check("the top face picked", len(p.names) == 1, (p.names, p.message.text()))
    h.check("choose New Offset", ui.choose(p.offset_type, "New Offset"))
    ui.type_into(p.field.widget, "5")


def pulled():
    v = h.solid_volume()
    h.check("a Press Pull step: 20 high", m.close(v, high(20)), v)
    h.check("Extrude 1 still 15", abs(length() - 15.0) < 1e-9, length())
    h.task_button("OK")


def after_new():
    h.check("dialog closed", m.no_dialog())
    h.check("one Press Pull step", len(press_pulls()) == 1, press_pulls())
    titles = sd.timeline_titles()
    h.check("the timeline shows one more step", len(titles) == len(s["titles"]) + 1, titles)


# -- T3 -------------------------------------------------------------------------------------------
def modify_again():
    p = panel()
    if h.check("Press Pull open", p is not None):
        h.check(
            "choose Modify Existing Feature", ui.choose(p.offset_type, "Modify Existing Feature")
        )


def click_top_20():
    h.click(V(20, 15, 20))


def offset_modify():
    p = panel()
    if p is None:
        return
    h.check("the top face picked", len(p.names) == 1, (p.names, p.message.text()))
    h.check("the dialog names the Press Pull", "Press Pull" in p.what.text(), p.what.text())
    ui.type_into(p.field.widget, "2")


def offset_changed():
    v = h.solid_volume()
    h.check("the Press Pull pulls 7: 22 high", m.close(v, high(22)), v)
    h.task_button("OK")


def after_offset():
    h.check("dialog closed", m.no_dialog())
    found = press_pulls()
    h.check("still one Press Pull", len(found) == 1, found)
    h.check("its distance is 7", found and abs(found[0].Distance.Value - 7.0) < 1e-9)
    h.check("kept", m.close(h.solid_volume(), high(22)), h.solid_volume())


# -- T4 -------------------------------------------------------------------------------------------
def modify_side():
    p = panel()
    if h.check("Press Pull open", p is not None):
        h.check(
            "choose Modify Existing Feature", ui.choose(p.offset_type, "Modify Existing Feature")
        )


def click_front():
    h.click(V(20, 0, 5))


def refused():
    p = panel()
    if p is None:
        return
    text = p.message.text()
    h.check("the reason is shown", "New Offset" in text, text)
    h.check("nothing changed", m.close(h.solid_volume(), high(22)), h.solid_volume())
    h.shot("2-refused")
    h.task_button("OK")


def ok_waits():
    h.check("OK waits", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("Esc closes it", m.no_dialog())
    h.check("nothing changed", m.close(h.solid_volume(), high(22)), h.solid_volume())
    h.check("Extrude 1 still 15", abs(length() - 15.0) < 1e-9, length())
    h.check("still one Press Pull", len(press_pulls()) == 1, press_pulls())
    h.check("no errors in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-end")


h.run(
    "modify2_presspull_type",
    sd.box_steps("Modify2PressPull")
    + [
        start_q,
        offset_types,
        click_top,
        modify_picked,
        lengthened,
        after_modify,
        undo,
        after_undo,
        redo,
        after_redo,
        start_q,
        click_top_15,
        new_offset,
        pulled,
        after_new,
        start_q,
        modify_again,
        click_top_20,
        offset_modify,
        offset_changed,
        after_offset,
        start_q,
        modify_side,
        click_front,
        refused,
        ok_waits,
        end,
    ],
)
