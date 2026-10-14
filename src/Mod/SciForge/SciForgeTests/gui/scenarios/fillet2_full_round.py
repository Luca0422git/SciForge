# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Full Round Fillet: Type Full Round Fillet, click the end face of a rib (its two
side faces are found by themselves): it becomes a half round of half the rib's width.
"+" adds a second full round (the end of the cross bar). A face that is not between two
parallel side faces is refused with the reason. OK, Ctrl+Z / Ctrl+Y, edit from the timeline,
Cancel. Only real input.

The part: a T, extruded 10 mm from a sketch: a cross bar 40 x 8 and a rib 4 wide, 22 long.
A full round of a face w wide removes h (w * w/2 - pi (w/2)^2 / 2) over its height h."""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import fillet2_steps as f2
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
OUTLINE = [
    V(0, 22, 0),
    V(18, 22, 0),
    V(18, 0, 0),
    V(22, 0, 0),
    V(22, 22, 0),
    V(40, 22, 0),
    V(40, 30, 0),
    V(0, 30, 0),
]
RIB_END = V(20, 0, 5)
BAR_END = V(40, 26, 5)
TOP = V(10, 26, 10)


def profile(sketch):
    import Part

    for a, c in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        sketch.addGeometry(Part.LineSegment(a, c))
    App.ActiveDocument.recompute()


def half_round(width, height=10.0):
    r = width / 2.0
    return height * (width * r - math.pi * r * r / 2.0)


def radii():
    return sorted(
        round(f.Surface.Radius, 6)
        for f in h.body().Shape.Faces
        if type(f.Surface).__name__ == "Cylinder"
    )


def start():
    s["v0"] = h.solid_volume()
    Gui.Selection.clearSelection()
    h.fit()
    h.press("f")


def full_round_type():
    p = b.blend_panel()
    if p:
        b.choose(p.type, "Full Round Fillet")


def click_rib_end():
    p = b.blend_panel()
    if p:
        h.check(
            "Full Round: no radius box, the size comes from the faces",
            not p.radius.widget.isVisible() and p.round_info.isVisible(),
        )
    h.click(RIB_END)


def rib_rounded():
    p = b.blend_panel()
    h.check(
        "the rib's end and its two side faces are picked",
        p is not None and len(p.refs) == 3 and p.refs[1].startswith("Face"),
        p and p.refs,
    )
    v = h.solid_volume()
    expect = s["v0"] - half_round(4)
    h.check("the rib's end is a half round (r 2)", b.close(v, expect), (v, expect))
    h.check("one half cylinder of radius 2", radii() == [2.0], radii())
    h.check("the dialog says the radius", p is not None and "2.00 mm" in p.round_info.text())
    h.shot("1-rib")
    if p:
        f2.press_plus(p)


def click_bar_end():
    p = b.blend_panel()
    h.check("a second full round row", p is not None and p.rows.count() == 2 and p.active == 1)
    h.click(BAR_END)


def both():
    v = h.solid_volume()
    expect = s["v0"] - half_round(4) - half_round(8)
    h.check("two full rounds in one step", b.close(v, expect), (v, expect))
    h.check("radii 2 and 4", radii() == [2.0, 4.0], radii())
    f2.press_plus(b.blend_panel())


def click_top():
    h.click(TOP)


def top_refused():
    p = b.blend_panel()
    text = p.help.text() if p else ""
    h.check(
        "the top face is refused: it is not between two side faces of its width",
        "Full Round" in text or "side faces" in text,
        text,
    )
    h.check("the third row stays empty", p is not None and not p.groups[2], p and p.groups)
    h.task_button("OK")


def after_ok():
    v = h.solid_volume()
    expect = s["v0"] - half_round(4) - half_round(8)
    h.check("kept", b.close(v, expect), v)
    steps = f2.steps()
    h.check(
        "one Full Round step with two rounds",
        len(steps) == 1
        and f2.spec_of(steps[0])["mode"] == "full_round"
        and [r["count"] for r in f2.spec_of(steps[0])["sets"] if r["count"]] == [3, 3],
        steps and f2.spec_of(steps[0]),
    )
    h.check("valid solid", h.body().Shape.isValid())
    s["v"] = v
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("Ctrl+Z", b.close(h.solid_volume(), s["v0"]) and not f2.steps())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Ctrl+Y", b.close(h.solid_volume(), s["v"]))
    h.fit()
    b.timeline_double_click("Fillet 1", click_first=True)


def edit_open():
    p = b.blend_panel()
    h.check("edit opens Full Round", p is not None and p.type.currentText() == "Full Round Fillet")
    if p is None:
        return
    h.check("both rounds listed", len([g for g in p.groups if g]) == 2, p.groups)
    f2.click_row(p, 0)


def drop_first():
    p = b.blend_panel()
    if p:
        b.click_widget(p.clear_button)


def dropped():
    v = h.solid_volume()
    expect = s["v0"] - half_round(8)
    h.check("✕ drops the rib's round (preview)", b.close(v, expect), (v, expect))
    h.press(QtCore.Qt.Key_Escape)


def end():
    h.check("Esc keeps both rounds", b.close(h.solid_volume(), s["v"]))
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("no kernel errors", not f2.report_errors(), f2.report_errors())
    h.shot("2-end")


h.run(
    "fillet2_full_round",
    b.box_steps("FullRound", profile=profile)
    + [
        start,
        full_round_type,
        click_rib_end,
        rib_rounded,
        click_bar_end,
        both,
        click_top,
        top_refused,
        after_ok,
        undone,
        redone,
        edit_open,
        drop_first,
        dropped,
        end,
    ],
)
