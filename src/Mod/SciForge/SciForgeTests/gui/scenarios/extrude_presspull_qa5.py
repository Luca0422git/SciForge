# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull next to the rest of the application (QA, only real input).

Path 20, typing values like a person: "1 in" (the i of "in" is also a shortcut key),
         "2*5" (an expression).
Path 21, Undo from the application bar with a preview on the screen: the dialog closes
         as cancelled, nothing half-made stays.
Path 22, Ctrl+S with the dialog open: the extrude is finished first (OK), then saved, so
         the file never holds a half-made preview. With nothing to OK it is cancelled.
Path 23, two designs open: a click in the other design is not a pick for the dialog.
Path 24, the design closed under an open dialog (its tab closed, changes discarded):
         the dialog goes away quietly and the next command works.
"""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def ppanel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def extrudes(d=None):
    from sciforge import extrude

    return [o for o in (d or doc()).Objects if extrude.is_extrude(o)]


def vol(d):
    b = d.getObject("Body")
    return b.Shape.Volume if b is not None and not b.Shape.isNull() else 0.0


def broken(d=None):
    return [o.Label for o in (d or doc()).Objects if "Invalid" in o.State or "Error" in o.State]


def step(fn, name):
    fn.__name__ = name
    return fn


def block_steps(tag, name):
    """A new design with a 40 x 30 x 10 block made with real input."""

    def new():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        s[tag] = App.ActiveDocument
        h.fit()
        h.ribbon("Create Sketch")

    def pick():
        h.click(V(12, -8, 0))

    def draw():
        sk = h.in_sketch()
        h.check("%s: sketch open" % tag, sk is not None)
        if sk:
            h.draw_rectangle(sk, 0, 0, 40, 30)

    def finish():
        h.ribbon("Finish Sketch")

    def e():
        h.fit()
        h.press("e")

    def ok():
        h.task_button("OK")

    def done():
        h.check("%s: block" % tag, near(vol(s[tag]), 12000.0), vol(s[tag]))
        h.fit()

    return [
        step(new, "%s_new" % tag),
        step(pick, "%s_pick" % tag),
        step(draw, "%s_draw" % tag),
        step(finish, "%s_finish" % tag),
        step(e, "%s_e" % tag),
        step(ok, "%s_ok" % tag),
        step(done, "%s_done" % tag),
    ]


def start_face_extrude():
    h.click_empty()
    h.press("e")


def pick_top():
    h.fit()
    h.click(V(30, 25, 10))


# -- Path 20: typing values ------------------------------------------------------------------
def p20_inch():
    p = xpanel()
    h.check("face extrude preview", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "1 in")


def p20_inch_done():
    p = xpanel()
    h.check("'1 in' is 25.4 mm", near(p.distance.value(), 25.4), p.distance.value())
    h.check("typing 'in' started no other command", p is not None and not p._closed)
    h.check("the preview follows", near(vol(s["a"]), 12000.0 + 1200.0 * 25.4), vol(s["a"]))
    ui.type_into(p.distance.widget, "2*5")


def p20_expression():
    p = xpanel()
    h.check("'2*5' is 10 mm", near(p.distance.value(), 10.0), p.distance.value())
    h.check("the preview follows", near(vol(s["a"]), 24000.0), vol(s["a"]))


# -- Path 21: Undo from the application bar with a preview on ---------------------------------
def p21_undo_button():
    s["count"] = len(extrudes())
    h.check("Undo button in the application bar", ui.quick_access("Undo"))


def p21_after():
    h.check("the dialog closed as cancelled", not dialog_open())
    h.check("the preview went away", len(extrudes()) == s["count"] - 1, len(extrudes()))
    h.check("the block is as before", near(vol(s["a"]), 12000.0), vol(s["a"]))
    h.check("nothing in error", not broken(), broken())
    shown = h.body().Tip.ViewObject.Visibility
    h.check("the block is drawn", shown)


# -- Path 22: Ctrl+S with the dialog open ---------------------------------------------------------
def p22_save_as():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-qa-"), "qa_save.FCStd")
    doc().saveAs(path)
    s["path"] = path
    h.check("saved once", os.path.isfile(path))
    start_face_extrude()


def p22_type():
    p = xpanel()
    h.check("face extrude preview", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "5")


def p22_ctrl_s():
    s["mtime"] = os.path.getmtime(s["path"])
    h.fit()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p22_saved():
    h.check("Ctrl+S finished the extrude (OK)", not dialog_open())
    h.check("the extrude is kept", near(vol(s["a"]), 18000.0), vol(s["a"]))
    h.check("and the design saved", not Gui.ActiveDocument.Modified)
    h.check("the file was written", os.path.getmtime(s["path"]) > s["mtime"])
    h.check("no pop-up", not h.popups(), h.popups())
    App.closeDocument(doc().Name)
    App.openDocument(s["path"])
    s["a"] = App.ActiveDocument
    h.fit()


def p22_reopened():
    h.check("the saved file has the finished extrude", near(vol(s["a"]), 18000.0), vol(s["a"]))
    h.check("nothing half-made in the file", not broken(), broken())
    start_face_extrude()


def p22_nothing_yet():
    p = xpanel()
    h.check("Extrude waits (nothing picked)", p is not None and p.target is None)
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p22_cancelled_saved():
    h.check("Ctrl+S with nothing to OK cancels the dialog", not dialog_open())
    h.check("design unchanged", near(vol(s["a"]), 18000.0), vol(s["a"]))
    h.check("no pop-up", not h.popups(), h.popups())


# -- Path 23: two designs open ---------------------------------------------------------------
def tab_bar():
    area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    return area.findChild(QtWidgets.QTabBar) if area is not None else None


def click_tab(label_start):
    bar = tab_bar()
    if bar is None:
        h.check("document tabs exist", False)
        return False
    for i in range(bar.count()):
        if bar.tabText(i).startswith(label_start):
            w.click(bar, bar.tabRect(i).center())
            QtWidgets.QApplication.processEvents()
            return True
    h.check("a tab %r" % label_start, False, [bar.tabText(i) for i in range(bar.count())])
    return False


def p23_extrude_in_b():
    h.check("design B is active", doc() is s["b"], doc().Name)
    start_face_extrude()


def p23_pick_in_b():
    h.fit()
    h.click(V(30, 25, 10))


def p23_switch_to_a():
    p = xpanel()
    h.check("B: face extrude preview", p.target is not None, p.message.text())
    s["b_volume"] = vol(s["b"])
    s["a_volume"] = vol(s["a"])
    click_tab("qa_save")


def p23_click_in_a():
    h.check("design A shown", doc() is s["a"], doc().Name)
    h.fit()
    h.click(V(5, 5, 15))


def p23_not_picked():
    p = xpanel()
    h.check("a click in design A is no pick for B's dialog", len(p.profiles) == 1, p.profiles)
    h.check("design A untouched", near(vol(s["a"]), s["a_volume"]), vol(s["a"]))
    h.check("nothing in error", not broken(s["a"]) and not broken(s["b"]))
    click_tab("QAB")


def p23_back():
    h.check("design B again", doc() is s["b"], doc().Name)
    h.task_button("OK")


def p23_done():
    h.check("B's extrude kept", not dialog_open() and vol(s["b"]) > 12000.5, vol(s["b"]))


# -- Path 24: the design closed under an open dialog -----------------------------------------
def p24_start():
    start_face_extrude()


def p24_preview():
    h.fit()
    h.click(V(30, 25, 20))


def p24_close():
    p = xpanel()
    h.check("B: another face extrude preview", p.target is not None, p.message.text())
    # The tab's close button asks to save; "Discard" closes the design like this.
    App.closeDocument(s["b"].Name)


def p24_closed():
    h.check("the dialog went away with its design", not dialog_open())
    h.check("design A still there", App.ActiveDocument is not None)
    h.fit()
    start_face_extrude()


def p24_next():
    p = xpanel()
    h.check("Extrude works in design A", p is not None and not p._closed)
    h.press(QtCore.Qt.Key_Escape)


def p24_done():
    h.check("closed", not dialog_open())
    h.shot("p24-end")


h.run(
    "extrude_presspull_qa5",
    [
        *block_steps("a", "QAA"),
        step(start_face_extrude, "p20_e"),
        step(pick_top, "p20_pick"),
        p20_inch,
        p20_inch_done,
        p20_expression,
        p21_undo_button,
        p21_after,
        p22_save_as,
        step(pick_top, "p22_pick"),
        p22_type,
        p22_ctrl_s,
        p22_saved,
        p22_reopened,
        p22_nothing_yet,
        p22_cancelled_saved,
        *block_steps("b", "QAB"),
        p23_extrude_in_b,
        p23_pick_in_b,
        p23_switch_to_a,
        p23_click_in_a,
        p23_not_picked,
        p23_back,
        p23_done,
        p24_start,
        p24_preview,
        p24_close,
        p24_closed,
        p24_next,
        p24_done,
    ],
)
