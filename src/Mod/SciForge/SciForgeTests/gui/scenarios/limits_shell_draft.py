# SPDX-License-Identifier: LGPL-2.1-or-later
"""A shell wall or draft angle past what fits stops at the largest one that works (Luca,
2026-10-21; Fusion refuses it, this is Luca's decision). Only real input.

Shell, box 40 x 30 x 10 with the top taken away: the inside arrow dragged far (button held,
slowly) stops at the thickest wall (just under 10 mm: the bottom), the preview shows it,
the note says "Largest that fits here: ...", no error, one search for the whole drag;
dragged back the wall follows and the note goes; 50 typed is held at the limit with "50 mm
does not fit: limited to ..."; OK at once.

Draft, a second box, fixed plane XY, the front face: the angle handle turned far stops at
the steepest angle that works (the preview is the box with that face drafted); 80 typed is
held there; an angle from a formula (parameter steep = 80°) is not rewritten: the dialog
explains it with the steepest angle, OK waits; 5 typed, OK."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
TOP = V(20, 15, 10)
FRONT = V(20, 0, 5)


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def msg(p):
    return p.message.text() if p is not None else ""


def tan(deg):
    return math.tan(math.radians(deg))


def one_face(deg):
    return sd.BOX - 40 * 100.0 * tan(deg) / 2.0


def held(start, end, name, value):
    """A slow drag with the button held; value() is sampled after every move."""
    s["samples"] = []

    def sample(_index):
        try:
            s["samples"].append(value())
        except Exception:
            pass

    s["drag"] = a.HeldDrag(start, end, moves=30, every_ms=40, hold_ms=400, sample=sample)
    s["drag"].run()


# -- Shell -------------------------------------------------------------------------------------
def shell_start():
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def click_top():
    h.fit()
    h.click(TOP)


def top_picked():
    p = sd.shell_panel()
    h.check("Shell: the top face taken away", p is not None and len(p.names()) == 1)
    h.check("its arrow", p is not None and len(p.arrows) == 1, p and len(p.arrows))
    v = h.solid_volume()
    h.check("preview: 1 mm walls", sd.close(v, sd.open_top(1)), v)


def shell_drag_far():
    p = sd.shell_panel()
    if p is None or not p.arrows:
        h.check("Shell arrow to drag", False)
        return
    dragger, _spot, _origin, direction = p.arrows[0]
    head = a.head_point(dragger)
    s["searches"] = p.limits.searches
    held(
        h.screen_point(head),
        h.screen_point(head + direction * 40.0),
        "shell",
        lambda: sd.shell_panel().options["inside"],
    )


def shell_dragged_far():
    p = sd.shell_panel()
    if p is None:
        h.check("Shell dialog open after the drag", False)
        return
    t = p.inside.value()
    s["t"] = t
    h.check("the wall stopped just under 10 mm (the bottom)", 9.0 < t < 10.0, t)
    h.check("no error", msg(p) == "", msg(p))
    h.check("the note", note(p) == "Largest that fits here: %.2f mm" % t, note(p))
    v = h.solid_volume()
    h.check("the preview shows that wall", sd.close(v, sd.open_top(t)), (v, sd.open_top(t)))
    h.check(
        "worked out once for the whole drag",
        p.limits.searches - s["searches"] == 1,
        p.limits.searches - s["searches"],
    )
    after = s["samples"][[abs(x - t) < 1e-9 for x in s["samples"]].index(True) :] if any(
        abs(x - t) < 1e-9 for x in s["samples"]
    ) else []
    h.check("held there while dragged on", after and max(after) <= t + 1e-9, s["samples"][-6:])
    h.check(
        "the arrow stopped at the limit",
        abs(p.arrows[0][0].distance() - t) < 1e-6,
        (p.arrows[0][0].distance(), t),
    )
    h.check("nothing in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("1-shell-held")


shell_dragged_far.wait_ms = 3000


def shell_drag_back():
    p = sd.shell_panel()
    if p is None or not p.arrows:
        return
    dragger, _spot, _origin, direction = p.arrows[0]
    head = a.head_point(dragger)
    held(
        h.screen_point(head),
        h.screen_point(head - direction * 5.0),
        "shell back",
        lambda: sd.shell_panel().options["inside"],
    )


def shell_dragged_back():
    p = sd.shell_panel()
    t = p.inside.value() if p else 0
    h.check("dragged back, the wall follows below the limit", 1.0 < t < s["t"] - 1.0, t)
    h.check("the note went", note(p) == "", note(p))
    h.check("no error", msg(p) == "", msg(p))
    v = h.solid_volume()
    h.check("the preview follows", sd.close(v, sd.open_top(t)), (v, sd.open_top(t)))


shell_dragged_back.wait_ms = 1500


def shell_type_50():
    p = sd.shell_panel()
    if p:
        sd.type_into(p.inside.widget, "50")


def shell_typed_50():
    p = sd.shell_panel()
    text = note(p)
    h.check(
        "50 is held at the thickest wall, and said",
        text == "50 mm does not fit: limited to %.2f mm" % s["t"],
        text,
    )
    h.check("no error", msg(p) == "", msg(p))
    v = h.solid_volume()
    h.check("the preview has the thickest wall", sd.close(v, sd.open_top(s["t"])), v)
    h.task_button("OK")


shell_typed_50.wait_ms = 1500


def shell_made():
    h.check("OK worked at once", sd.shell_panel() is None and not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the part has the thickest wall", sd.close(v, sd.open_top(s["t"])), v)
    h.check("valid solid", h.body().Shape.isValid())
    h.shot("2-shell-made")


# -- Draft -------------------------------------------------------------------------------------
def draft_start():
    Gui.Selection.clearSelection()
    sd.modify_menu("Draft")


def click_xy():
    h.fit()
    pl.click_square("XY_Plane")


def click_front():
    h.fit()
    h.click(FRONT)


def front_picked():
    p = sd.draft_panel()
    h.check("Draft: the front face", p is not None and len(p.names()) == 1, p and p.names())
    h.check("the angle handle", p is not None and p.handle is not None)
    v = h.solid_volume()
    h.check("preview: 1 deg", sd.close(v, one_face(1)), v)


def draft_turn_far():
    p = sd.draft_panel()
    if p is None or p.handle is None:
        h.check("Draft handle to turn", False)
        return
    h.fit()
    here, there = p.handle.screen_points(85.0)
    s["searches"] = p.limits.searches
    held(
        h.screen_point(here),
        h.screen_point(there),
        "draft",
        lambda: sd.draft_panel().options["angle"],
    )


def draft_turned_far():
    p = sd.draft_panel()
    if p is None:
        h.check("Draft dialog open after the drag", False)
        return
    deg = p.angle.value()
    s["deg"] = deg
    h.check("the angle stopped at the steepest that works", 30.0 < deg < 85.0, deg)
    h.check("no error", msg(p) == "", msg(p))
    h.check("the note", note(p) == "Largest that fits here: %.1f°" % deg, note(p))
    v = h.solid_volume()
    h.check("the preview has that draft", sd.close(v, one_face(deg)), (v, one_face(deg)))
    h.check(
        "worked out once for the whole drag",
        p.limits.searches - s["searches"] == 1,
        p.limits.searches - s["searches"],
    )
    h.check(
        "the handle stopped at the limit",
        abs(p.handle.angle() - deg) < 0.05,
        (p.handle.angle(), deg),
    )
    h.check("nothing in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("3-draft-held")


draft_turned_far.wait_ms = 5000


def draft_type_80():
    p = sd.draft_panel()
    if p:
        sd.type_into(p.angle.widget, "80")


def draft_typed_80():
    p = sd.draft_panel()
    text = note(p)
    h.check(
        "80 is held at the steepest angle, and said",
        text == "80° does not fit: limited to %.1f°" % s["deg"],
        text,
    )
    h.check("no error", msg(p) == "", msg(p))
    if p:
        QtTest.QTest.keyClick(p.angle.widget, QtCore.Qt.Key_Tab)  # leave the box


draft_typed_80.wait_ms = 1500


def draft_box_left():
    p = sd.draft_panel()
    h.check(
        "the box shows the limit once it is left",
        p is not None and abs(p.angle.value() - s["deg"]) < 1e-9,
        p and p.angle.widget.text(),
    )
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "steep", "deg", "80")


def draft_formula():
    p = sd.draft_panel()
    if p:
        ui.type_into(p.angle.widget, "steep")  # and Tab: the formula is taken


def draft_formula_explained():
    p = sd.draft_panel()
    text = msg(p)
    h.check(
        "the formula is kept",
        p is not None and p.formula == "steep",
        p and (p.formula, p.formula_error, p.options.get("angle"), p.angle.widget.text(), text),
    )
    h.check("it is explained", text.startswith("⚠"), text)
    h.check(
        "with the steepest angle that works",
        "Largest that fits here: %.1f°" % s["deg"] in text,
        text,
    )
    h.task_button("OK")


draft_formula_explained.wait_ms = 3000


def draft_formula_ok_waits():
    p = sd.draft_panel()
    h.check("OK waits", p is not None and Gui.Control.activeDialog())
    if p:
        ui.type_into(p.angle.widget, "5")  # a plain number (and Tab) drops the formula


def draft_ok():
    p = sd.draft_panel()
    h.check("5 deg: no message", p is not None and msg(p) == "" and note(p) == "", msg(p))
    h.task_button("OK")


def draft_made():
    h.check("Draft closed", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the part has a 5 deg draft", sd.close(v, one_face(5)), v)


h.run(
    "limits_shell_draft",
    sd.box_steps("LimitsShell")
    + [
        shell_start,
        click_top,
        top_picked,
        shell_drag_far,
        shell_dragged_far,
        shell_drag_back,
        shell_dragged_back,
        shell_type_50,
        shell_typed_50,
        shell_made,
    ]
    + sd.box_steps("LimitsDraft")
    + [
        draft_start,
        click_xy,
        click_front,
        front_picked,
        draft_turn_far,
        draft_turned_far,
        draft_type_80,
        draft_typed_80,
        draft_box_left,
        draft_formula,
        draft_formula_explained,
        draft_formula_ok_waits,
        draft_ok,
        draft_made,
    ],
)
