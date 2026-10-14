# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's radius sets: several rows in one Fillet step ("+" in the selection box), each with
its own edges and radius, one timeline step, one undo step, each set's arrow and value box
on the canvas. Only real input: F, clicks on edges, "+", typing, dragging set 1's arrow,
a value typed into set 2's value box, OK, Ctrl+Z / Ctrl+Y, double-click in the timeline,
picking a set's row, a radius too big for its set (the dialog says so, OK waits), Esc, save,
close, reopen and edit. Volumes by hand: a round of radius r on a 40 mm box edge removes
40 r^2 (1 - pi/4) (blend_steps)."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
BACK_TOP = V(20, 30, 10)


def two_sets(r1, r2):
    return b.BOX - 40 * b.spandrel(r1) - 40 * b.spandrel(r2)


def doc():
    return App.ActiveDocument


def start():
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def pick_first():
    p = b.blend_panel()
    h.check("Fillet dialog open with one set", p is not None and p.rows.count() == 1)
    h.check("the '+' of the selection box is there", p is not None and p.add_row_button.isVisible())
    h.click_edge(FRONT_TOP)


def first_picked():
    p = b.blend_panel()
    h.check("set 1 has the front edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "1")


def plus():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("set 1 previews r 1", b.close(v, b.BOX - 40 * b.spandrel(1)), v)
    h.check(
        "one set is still FreeCAD's own fillet",
        p is not None and p.target is not None and p.target.TypeId == "PartDesign::Fillet",
        p and p.target,
    )
    f2.press_plus(p)


def second_row():
    p = b.blend_panel()
    h.check("'+' adds set 2", p is not None and p.rows.count() == 2, p and f2.row_texts(p))
    h.check("set 2 is the current one, empty", p is not None and p.active == 1 and not p.refs)
    h.check("set 2 starts with set 1's radius", p is not None and abs(p.radius.value() - 1) < 1e-9)
    h.click_edge(BACK_TOP)


def second_picked():
    p = b.blend_panel()
    h.check("set 2 has the back edge", p is not None and p.refs and len(p.refs) == 1, p and p.refs)
    h.check("set 1 still has its edge", p is not None and len(p.groups[0]) == 1, p and p.groups)
    if p:
        b.type_into(p.radius.widget, "3")


def second_radius():
    p = b.blend_panel()
    v = h.solid_volume()
    h.check("two sets: r 1 and r 3 in one preview", b.close(v, two_sets(1, 3)), (v, two_sets(1, 3)))
    h.check(
        "two sets made it SciForge's fillet step",
        p is not None and f2.is_sets(p.target),
        p and p.target and p.target.TypeId,
    )
    h.check("one arrow per set", p is not None and len(p.arrows) == 2, p and len(p.arrows))
    boxes = ai.value_boxes()
    h.check("a value box beside each arrow", len(boxes) == 2, [x.text() for x in boxes])
    h.check(
        "the rows say what each set is",
        p is not None and "1 mm" in f2.row_texts(p)[0] and "3 mm" in f2.row_texts(p)[1],
        p and f2.row_texts(p),
    )
    h.check("one Fillet in the timeline", b.timeline_titles().count("Fillet 1") == 1)
    h.shot("1-two-sets")
    # drag set 1's arrow outwards
    index = [i for i, a in enumerate(p.arrows) if a[1].get("row") == 0]
    if not h.check("set 1 has an arrow", bool(index)):
        return
    s["arrow"] = index[0]
    start_pos, end_pos = b.arrow_screen(p, index[0], along=1.5)
    h.drag(start_pos, end_pos)


def dragged():
    p = b.blend_panel()
    r1 = p.spec["sets"][0]["radius"] if p else 0
    r2 = p.spec["sets"][1]["radius"] if p else 0
    h.check("dragging set 1's arrow grows set 1", r1 > 1.4, r1)
    h.check("set 2 keeps its radius", abs(r2 - 3) < 1e-9, r2)
    h.check("dragging set 1's arrow makes set 1 current", p is not None and p.active == 0)
    v = h.solid_volume()
    h.check("preview follows the drag", b.close(v, two_sets(r1, r2)), (v, two_sets(r1, r2)))
    s["r1"] = r1
    # type 2 into set 2's value box; Enter there finishes the command (Fusion)
    index = [i for i, a in enumerate(p.arrows) if a[1].get("row") == 1]
    box = ai.value_box("radius#%d" % index[0]) if index else None
    if h.check("set 2's value box", box is not None):
        ai.type_in_box(box, "2")


def after_ok():
    v = h.solid_volume()
    h.check(
        "set 2's value box set set 2 to 2 mm, Enter finished", b.close(v, two_sets(s["r1"], 2)), v
    )
    h.check("one step for both sets", len(f2.steps()) == 1 and f2.is_sets(f2.steps()[0]))
    h.check("timeline: one Fillet", b.timeline_titles().count("Fillet 1") == 1, b.timeline_titles())
    h.check("valid solid", h.body().Shape.isValid())
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    s["v"] = v
    h.shot("2-ok")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("one Ctrl+Z takes both sets away", b.close(h.solid_volume(), b.BOX) and not f2.steps())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y brings both back", b.close(h.solid_volume(), s["v"]) and len(f2.steps()) == 1)
    h.fit()
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("double-click edits the step", p is not None and not p.created)
    if p is None:
        return
    h.check("both sets are back in the list", p.rows.count() == 2, f2.row_texts(p))
    h.check(
        "each set has its edge and radius",
        [len(g) for g in p.groups] == [1, 1]
        and abs(p.spec["sets"][0]["radius"] - s["r1"]) < 1e-9
        and abs(p.spec["sets"][1]["radius"] - 2) < 1e-9,
        (p.groups, p.spec["sets"]),
    )
    f2.click_row(p, 1)


def edit_row():
    p = b.blend_panel()
    h.check("clicking set 2's row makes it current", p is not None and p.active == 1)
    h.check(
        "the Radius box shows set 2's radius", p is not None and abs(p.radius.value() - 2) < 1e-9
    )
    if p:
        b.type_into(p.radius.widget, "40")


def too_big():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check("a radius too big for set 2 is explained", "too big" in text or "fit" in text, text)
    h.check(
        "the preview keeps the last good result",
        b.close(h.solid_volume(), s["v"]),
        h.solid_volume(),
    )
    h.task_button("OK")


def ok_refused():
    p = b.blend_panel()
    h.check("OK waits while a set does not fit", p is not None)
    if p:
        b.type_into(p.radius.widget, "2.5")


def edit_ok():
    h.task_button("OK")


def edited():
    v = h.solid_volume()
    h.check("edited set 2 to 2.5", b.close(v, two_sets(s["r1"], 2.5)), v)
    h.check("still one step", len(f2.steps()) == 1)
    s["v"] = v


def esc_start():
    h.press("f")


def esc_pick():
    h.click_edge(V(40, 15, 0))


def esc_press():
    p = b.blend_panel()
    h.check("Esc path: an edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc: model unchanged", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("Esc: still one step", len(f2.steps()) == 1)


def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-fillet2-"), "sets.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path))
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    h.check("reopened: same part", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    steps = f2.steps()
    h.check("reopened: the step is there", len(steps) == 1 and f2.is_sets(steps[0]))
    if steps:
        steps[0].touch()
        doc().recompute()
        h.check(
            "reopened: it computes again",
            "Invalid" not in steps[0].State and b.close(h.solid_volume(), s["v"]),
            (steps[0].State, h.solid_volume()),
        )
    b.timeline_double_click("Fillet 1", click_first=True)


def reopened_edit():
    p = b.blend_panel()
    h.check("edit after reopening shows the two sets", p is not None and p.rows.count() == 2)
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("3-end")


h.run(
    "fillet2_sets",
    b.box_steps("Sets")
    + [
        start,
        pick_first,
        first_picked,
        plus,
        second_row,
        second_picked,
        second_radius,
        dragged,
        after_ok,
        undone,
        redone,
        edit_open,
        edit_row,
        too_big,
        ok_refused,
        edit_ok,
        edited,
        esc_start,
        esc_pick,
        esc_press,
        after_esc,
        save,
        reopen,
        reopened,
        reopened_edit,
        end,
    ],
)
