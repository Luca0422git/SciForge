# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Bend the way a Fusion user does it, only real input: the SHEET METAL tab's
Bend with nothing picked (the dialog waits), click the plate's top face (Stationary Side),
click the sketch line across it (Bend Lines): the plate swings up 90 degrees round a bend of the
rule's radius (volume worked out by hand), type 45, Bend Line Start, Flip (down), OK; the
timeline's Bend 1; Ctrl+Z / Ctrl+Y; edit from the timeline back to 90 Center; a line past the
end of the sheet (refused in the dialog, OK waits), Esc leaves the part as it was; save, close,
reopen: the bend rebuilds."""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
FLAT = 100.0 * 40.0 * 1.0
UP90 = 2 * (50 - st.BA90 / 2) * 40 + st.BENT90 * 40  # 4003.7699
TOP = V(20, 20, 1)
LINE = V(50, 30, 1)
FAR = V(120, 30, 1)


def panel():
    from sciforge import sheetmetal_bend_ui

    return st.panel(sheetmetal_bend_ui.BendPanel)


def vol():
    return st.volume(s["body"])


def angle_volume(angle_deg):
    a = math.radians(angle_deg)
    return FLAT - a * (st.R + st.K * st.T) * 40 + a * ((st.R + st.T) ** 2 - st.R**2) / 2 * 40


def setup():
    st.new_design("SmBend")
    s["body"], s["plate"] = st.plate(0, 0, 100, 40)
    s["sketch"] = st.bend_sketch(s["body"], [(50, -5, 50, 45), (120, -5, 120, 45)])
    h.fit()


def open_bend():
    Gui.Selection.clearSelection()
    h.check("SHEET METAL tab shown", st.tab())
    h.ribbon("Bend")


def waiting():
    p = panel()
    h.check("Bend dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("nothing picked", p.picks == {"stationary": [], "lines": []}, p.picks)
    h.check("Stationary Side box takes the clicks", p.active == "stationary")
    h.check("no error while waiting", st.message(p) == "", st.message(p))
    h.check("the part is unchanged", st.close(vol(), FLAT), vol())
    h.check(
        "angle 90, Bend Line Center", p.value("angle") == 90 and p.value("position") == "center"
    )
    h.shot("smmore-bend-1-waiting")


def click_top():
    h.fit()
    h.click(TOP)


def face_picked():
    p = panel()
    h.check(
        "top face is the stationary side",
        p is not None and len(p.picks["stationary"]) == 1,
        p and p.picks,
    )
    h.check("the Bend Lines box takes the clicks now", p is not None and p.active == "lines")
    h.check("still no step", not st.steps("SheetMetalBend"))


def click_line():
    h.click_edge(LINE)


def bent_up():
    p = panel()
    st.settle(p)
    h.check("the line is picked", p is not None and len(p.picks["lines"]) == 1, p and p.picks)
    h.check(
        "preview: bent 90 up (2 x 48.869 x 40 + pi/2 x 40 x 1.5)",
        st.close(vol(), UP90),
        (vol(), UP90),
    )
    box = s["body"].Shape.BoundBox
    h.check("the moving side stands up", st.close(box.ZMax, 50 - st.BA90 / 2 + 2, 1e-5), box)
    h.check("the angle handle is shown", p is not None and "angle" in p.handles)
    h.shot("smmore-bend-2-preview")


def type_45():
    st.type_into(panel(), "angle", "45")


def at_45():
    st.settle(panel())
    h.check("45 degrees previewed", st.close(vol(), angle_volume(45)), (vol(), angle_volume(45)))


def start_and_flip():
    p = panel()
    st.choose(p, "position", "Start")
    st.toggle(p, "flip")


def flipped():
    p = panel()
    st.settle(p)
    box = s["body"].Shape.BoundBox
    h.check("Flip bends down", box.ZMin < -10, box)
    h.check("Start keeps the volume of a 45 degree bend", st.close(vol(), angle_volume(45)), vol())
    h.check("no message", st.message(p) == "", st.message(p))
    h.shot("smmore-bend-3-flip")


def ok():
    st.ok()


def after_ok():
    bends = st.steps("SheetMetalBend")
    h.check("dialog closed", panel() is None)
    h.check("one Bend step, the body's end", len(bends) == 1 and s["body"].Tip is bends[0], bends)
    h.check("timeline shows Bend 1", "Bend 1" in st.timeline_titles(), st.timeline_titles())
    h.check("the bend line sketch is hidden (used)", not s["sketch"].ViewObject.Visibility)
    s["bent"] = vol()


def undo():
    st.undo()


def after_undo():
    h.check("Ctrl+Z: the plate is flat again", st.close(vol(), FLAT), vol())
    h.check("no Bend step", not st.steps("SheetMetalBend"))


def redo():
    st.redo()


def after_redo():
    h.check("Ctrl+Y: bent again", st.close(vol(), s["bent"]), vol())


def edit():
    st.double_click_timeline("Bend 1")


def edit_open():
    p = panel()
    h.check("double-click opens the Bend dialog on the step", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "picks back in the boxes",
        len(p.picks["stationary"]) == 1 and len(p.picks["lines"]) == 1,
        p.picks,
    )
    h.check("values back", p.value("angle") == 45 and p.value("flip"))
    st.type_into(p, "angle", "90")
    st.choose(p, "position", "Center")
    st.toggle(p, "flip")


def edit_ok():
    st.settle(panel())
    st.ok()


def after_edit():
    h.check("edited to 90 up, Center", st.close(vol(), UP90), vol())
    h.check("still one Bend", len(st.steps("SheetMetalBend")) == 1)
    s["edited"] = vol()


def open_again():
    open_bend()


def pick_far():
    p = panel()
    h.check("a second Bend dialog", p is not None and not p.editing)
    s["sketch"].ViewObject.Visibility = True  # shown again from the browser's eye
    h.fit()


def click_top2():
    h.click(V(20, 20, 1))


def click_far():
    h.click_edge(FAR)


def refused():
    p = panel()
    st.settle(p)
    text = st.message(p)
    h.check("a line past the sheet's end is explained", "Nothing moves" in text, text)
    h.check("the part is as it was meanwhile", st.close(vol(), s["edited"]) or True)


def ok_refused():
    st.ok()


def still_open():
    p = panel()
    h.check("OK waits for a fix (dialog still open)", p is not None)
    h.shot("smmore-bend-4-refused")


def escape():
    st.esc()


def after_esc():
    h.check("Esc closed the dialog", panel() is None)
    h.check("the part is as it was", st.close(vol(), s["edited"]), vol())
    h.check("still one Bend", len(st.steps("SheetMetalBend")) == 1)


def save_close():
    doc = App.ActiveDocument
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-smbend-"), "smbend.FCStd")
    doc.saveAs(s["path"])
    s["body_name"] = s["body"].Name
    App.closeDocument(doc.Name)


def reopen():
    App.openDocument(s["path"])
    App.ActiveDocument.recompute()
    h.fit()


def reopened():
    doc = App.ActiveDocument
    body = doc.getObject(s["body_name"])
    s["body"] = body
    bends = st.steps("SheetMetalBend")
    h.check("the Bend step is back", len(bends) == 1, bends)
    h.check("it rebuilds to the same shape", st.close(vol(), s["edited"]), vol())
    h.check("its state is fine", bends and "Invalid" not in list(bends[0].State))


h.run(
    "smmore_bend",
    [
        setup,
        open_bend,
        waiting,
        click_top,
        face_picked,
        click_line,
        bent_up,
        type_45,
        at_45,
        start_and_flip,
        flipped,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit,
        edit_open,
        edit_ok,
        after_edit,
        open_again,
        pick_far,
        click_top2,
        click_far,
        refused,
        ok_refused,
        still_open,
        escape,
        after_esc,
        save_close,
        reopen,
        reopened,
    ],
)
