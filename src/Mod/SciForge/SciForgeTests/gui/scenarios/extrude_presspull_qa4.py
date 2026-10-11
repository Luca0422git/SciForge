# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull: tapers to an object, editing while a command is open, a New
Body turned into a Cut (QA, only real input).

Path 15, Press Pull the same face twice in a row (two steps in the timeline).
Path 16, a column To Object (the wall's top) with a taper (Fusion tapers every extent;
         FreeCAD's Pad ignores it, SciForge builds it), edited back to no taper from the
         timeline, Undo brings the taper back.
Path 17, double-click a timeline step while an Extrude with a preview is open: the
         open extrude is kept and the other step opens for editing.
Path 18, a New Body extrude edited into a Cut of the first body: the empty new body
         goes away and the next command works on the first body.
Path 19, double-click the timeline icon of the extrude being made while it still waits
         for its To Object pick: it is cancelled, no error.

Numbers by hand: base 40 x 30 x 10, wall 10 x 30 x 20 on its right end.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

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


def bodies():
    return doc().findObjects("PartDesign::Body")


def first_body():
    return doc().getObject("Body")


def vol1():
    b = first_body()
    return b.Shape.Volume if b is not None and not b.Shape.isNull() else 0.0


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def extrudes():
    from sciforge import extrude

    return [o for o in doc().Objects if extrude.is_extrude(o)]


def frustum(a, height, taper):
    """Square a x a growing by height * tan(taper) per side over `height`."""
    b = a + 2.0 * height * math.tan(math.radians(taper))
    return height / 3.0 * (a * a + b * b + a * b)


def step(fn, name):
    fn.__name__ = name
    return fn


def sketch_rect_on(tag, point, x0, y0, x1, y1):
    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(point)

    def draw():
        sk = h.in_sketch()
        h.check("sketch %s open" % tag, sk is not None)
        if sk:
            ax, ay = h.to_sketch(sk, V(x0, y0, point.z))
            bx, by = h.to_sketch(sk, V(x1, y1, point.z))
            h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def finish():
        h.ribbon("Finish Sketch")

    def after():
        h.check("left sketch %s" % tag, h.in_sketch() is None)
        h.fit()

    return [
        step(create, "sketch_%s_create" % tag),
        step(pick, "sketch_%s_pick" % tag),
        step(draw, "sketch_%s_draw" % tag),
        step(finish, "sketch_%s_finish" % tag),
        step(after, "sketch_%s_after" % tag),
    ]


def extrude_steps(tag, distance, want):
    def press():
        h.fit()
        h.press("e")

    def typed():
        p = xpanel()
        h.check("%s picked by itself" % tag, p.target is not None, p.message.text())
        ui.type_into(p.distance.widget, "%g" % distance)

    def ok():
        h.task_button("OK")

    def done():
        h.check("%s made" % tag, not dialog_open() and near(vol1(), want), (vol1(), want))

    return [
        step(press, "%s_e" % tag),
        step(typed, "%s_type" % tag),
        step(ok, "%s_ok" % tag),
        step(done, "%s_done" % tag),
    ]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QATaper")
    h.fit()


# -- Path 15: Press Pull the same face twice ------------------------------------------------
def p15_q():
    h.click_empty()
    h.press("q")


def p15_face():
    h.fit()
    h.click(V(15, 5, 10))  # in front: the wall hides the back of the base


def p15_type():
    p = ppanel()
    h.check("base top picked", p.target is not None and len(p.names) == 1, p.message.text())
    ui.type_into(p.field.widget, "2")


def p15_ok():
    h.check("base top +2 (900 mm^2)", near(vol1(), 18000.0 + 1800.0), vol1())
    h.task_button("OK")


def p15_again():
    h.check("kept", not dialog_open())
    h.click_empty()
    h.press("q")


def p15_face_again():
    h.fit()
    h.click(V(15, 5, 12))


def p15_type_again():
    p = ppanel()
    h.check("the moved face picked again", p.target is not None and len(p.names) == 1)
    ui.type_into(p.field.widget, "3")


def p15_ok_again():
    h.check("+3 more", near(vol1(), 19800.0 + 2700.0), vol1())
    h.task_button("OK")


def p15_done():
    from sciforge import presspull

    pps = [o for o in doc().Objects if presspull.is_press_pull(o)]
    h.check("two Press Pull steps", len(pps) == 2, [o.Name for o in pps])
    h.check("nothing in error", not broken(), broken())


# -- Path 16: a tapered column To Object ------------------------------------------------------
def p16_e():
    h.fit()
    h.press("e")


def p16_to_object():
    p = xpanel()
    h.check("column picked by itself", p.target is not None, p.message.text())
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))


def p16_click_wall():
    p = xpanel()
    h.check("To Object waits, no warning", "⚠" not in p.message.text(), p.message.text())
    h.check("and says what to click", p.info.text() != "", p.info.text())
    h.fit()
    h.click(V(35, 15, 30))


def p16_taper():
    p = xpanel()
    h.check("the wall top picked", p.options.get("extent_object") is not None, p.message.text())
    h.check("column up to the wall top: +1500", near(vol1(), 24000.0), vol1())
    h.check("the taper can be set with To Object", p.taper.widget.isEnabled())
    ui.type_into(p.taper.widget, "5")


def p16_tapered():
    p = xpanel()
    want = 22500.0 + frustum(10.0, 15.0, 5.0)
    h.check("tapered 5 degrees up to the wall top", near(vol1(), want, 1e-6), (vol1(), want))
    h.check("no warning", p.message.text() == "", p.message.text())
    h.shot("p16-taper-to-object")
    h.task_button("OK")


def p16_edit():
    h.check("kept", not dialog_open())
    s["taper_volume"] = vol1()
    titles = ui.timeline_titles()
    s["column"] = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("double-click %s" % s["column"], ui.double_click_timeline(s["column"]), titles)


def p16_editing():
    p = xpanel()
    h.check("editing the column", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("To Object back", p.extent.currentText() == "To Object", p.extent.currentText())
    h.check("its object back", p.fields["extent_object"].button.text() != "Select object")
    h.check("taper 5 back", near(p.taper.value(), 5.0), p.taper.value())
    ui.type_into(p.taper.widget, "0")


def p16_untapered():
    h.check("no taper: +1500 again", near(vol1(), 24000.0), vol1())
    h.task_button("OK")


def p16_undo():
    h.check("kept", not dialog_open() and near(vol1(), 24000.0))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p16_undone():
    h.check("Undo: the taper is back", near(vol1(), s["taper_volume"]), vol1())
    h.check("nothing in error", not broken(), broken())
    h.check("the part is drawn", first_body().Tip.ViewObject.Visibility)


# -- Path 17: double-click the timeline while Extrude is open ---------------------------------
def p17_e():
    h.click_empty()
    h.press("e")


def p17_face():
    h.fit()
    h.click(V(20, 5, 15))


def p17_preview():
    p = xpanel()
    h.check("face extrude preview", p.target is not None, p.message.text())
    s["count"] = len(extrudes())
    s["before_dblclick"] = vol1()
    h.check("double-click Extrude 1", ui.double_click_timeline("Extrude 1"), ui.timeline_titles())


def p17_editing_other():
    p = xpanel()
    h.check("the open extrude was kept", len(extrudes()) == s["count"], len(extrudes()))
    h.check("Extrude 1 opens for editing", p is not None and p.editing and not p._closed)
    h.press(QtCore.Qt.Key_Escape)


def p17_done():
    h.check("Esc closes the edit", not dialog_open())
    h.check("model as after the kept extrude", near(vol1(), s["before_dblclick"]), vol1())
    h.check("nothing in error", not broken(), broken())
    s["volume"] = vol1()


# -- Path 18: New Body edited into a Cut --------------------------------------------------------
def p18_new_body():
    p = xpanel()
    h.check("square on the wall picked", p.target is not None, p.message.text())
    h.check("choose New Body", ui.choose(p.operation, "New Body"))


def p18_ok():
    h.task_button("OK")


def p18_edit():
    from sciforge import commands

    h.check("two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    h.check("the new body is active", commands.active_body() is not first_body())
    titles = ui.timeline_titles()
    s["nb"] = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("double-click %s" % s["nb"], ui.double_click_timeline(s["nb"]), titles)


def p18_to_cut():
    p = xpanel()
    h.check("editing the New Body extrude", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("choose Operation: Cut", ui.choose(p.operation, "Cut"))
    ui.type_into(p.distance.widget, "-5")


def p18_cut_ok():
    h.check("one body while previewing the cut", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("6 x 20 x 5 cut from the wall", near(vol1(), s["volume"] - 600.0), vol1())
    h.task_button("OK")


def p18_after():
    h.check("one body", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("cut kept", near(vol1(), s["volume"] - 600.0), vol1())
    h.check("nothing in error", not broken(), broken())
    h.click_empty()
    h.press("e")


def p18_next_command():
    from sciforge import commands

    p = xpanel()
    h.check("the next Extrude opens", p is not None and not p._closed)
    h.check("on the first body", commands.active_body() is first_body())
    h.press(QtCore.Qt.Key_Escape)


def p18_done():
    h.check("closed", not dialog_open())
    h.shot("p18-end")


# -- Path 19: double-click the timeline icon of the extrude being made -------------------------
def p19_e():
    s["volume"] = vol1()
    s["count"] = len(extrudes())
    h.click_empty()
    h.press("e")


def p19_face():
    h.fit()
    h.click(V(20, 5, 25))


def p19_to_object():
    p = xpanel()
    h.check("face extrude preview", p.target is not None, p.message.text())
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))


def p19_double_click_own():
    titles = ui.timeline_titles()
    own = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("the unfinished extrude shows in the timeline", len(extrudes()) == s["count"] + 1)
    h.check("double-click its own icon %s" % own, ui.double_click_timeline(own), titles)


def p19_done():
    h.check("the unfinished extrude was cancelled (OK not possible)", not dialog_open())
    h.check("nothing added", len(extrudes()) == s["count"] and near(vol1(), s["volume"]))
    h.check("nothing in error", not broken(), broken())


h.run(
    "extrude_presspull_qa4",
    [
        new_design,
        *sketch_rect_on("base", V(12, -8, 0), 0, 0, 40, 30),
        *extrude_steps("base", 10, 12000.0),
        *sketch_rect_on("wall", V(35, 15, 10), 30, 0, 40, 30),
        *extrude_steps("wall", 20, 18000.0),
        p15_q,
        p15_face,
        p15_type,
        p15_ok,
        p15_again,
        p15_face_again,
        p15_type_again,
        p15_ok_again,
        p15_done,
        *sketch_rect_on("column", V(10, 15, 15), 5, 10, 15, 20),
        p16_e,
        p16_to_object,
        p16_click_wall,
        p16_taper,
        p16_tapered,
        p16_edit,
        p16_editing,
        p16_untapered,
        p16_undo,
        p16_undone,
        p17_e,
        p17_face,
        p17_preview,
        p17_editing_other,
        p17_done,
        *sketch_rect_on("cap", V(35, 15, 30), 32, 5, 38, 25),
        step(lambda: (h.fit(), h.press("e")), "p18_e"),
        p18_new_body,
        p18_ok,
        p18_edit,
        p18_to_cut,
        p18_cut_ok,
        p18_after,
        p18_next_command,
        p18_done,
        p19_e,
        p19_face,
        p19_to_object,
        p19_double_click_own,
        p19_done,
    ],
)
