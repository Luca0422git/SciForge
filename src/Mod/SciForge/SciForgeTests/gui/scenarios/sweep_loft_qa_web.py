# SPDX-License-Identifier: LGPL-2.1-or-later
"""Web the way a Fusion user really uses it, trying to break it (QA, only real input).

A tray made like a Fusion user makes one: a 40 x 40 rectangle on XY (R, typed sizes),
Extrude 10, MODIFY > Shell with the top face taken away, 2 thick. A sketch on the rim with
two lines typed 20 long (one at 0 degrees, one at 90 degrees) crossing over the cavity.

Path 1, picking and dropping: CREATE > Web, nothing selected: the Curves box waits. Click
        the first line: one plate, carried on to the walls (Extend Curves) and down to the
        floor (To Next). Click the second: the cross. Click the first again on top of its
        own preview: it is dropped. Click it again: the cross is back.
Path 2, values while the preview runs: Extend Curves off (only the drawn 20 long lines),
        on again; Flip Direction (it would grow up into the air: the dialog says so, OK
        waits), back; One Side and Flip Side (the same volume); Depth 4; Enter over the 3D
        view is OK. Ctrl+Z / Ctrl+Y.
Path 3, Esc in the middle of picking and Ctrl+Z in an edit: the lines' sketch shown
        again with its eye; Web, click a line where it lies on the first web's top edge
        (the line is taken), Esc: nothing changes, no undo step. Double-click Web 1, Thickness 3, Ctrl+Z in the
        dialog: the edit is cancelled, the web stays as it was.

Hand-derived: the tray is 40 * 40 * 10 - 36 * 36 * 8 = 5632. A plate L long, t thick and h
high adds L t h; two crossing plates share a t x t x h post. Extended, each plate runs wall
to wall, L = 36, whatever the drawn line's place.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sweep_loft_steps as st
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
TRAY = 40.0 * 40.0 * 10.0 - 36.0 * 36.0 * 8.0
TOP = 10.0
s = {}


def panel():
    return st.panel("web")


def msg():
    return st.message("web")


def near(a, c, tol=1e-6):
    return st.near(a, c, tol)


def vol():
    return h.solid_volume()


def plate(length, t, height):
    return length * t * height


def cross(length, t, height):
    return 2.0 * length * t * height - t * t * height


def line_mid(index):
    a, c = s["lines"][index]
    return (a + c) * 0.5


# == the tray =====================================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("WebQA")
    h.fit()
    h.ribbon("Create Sketch")


def t_xy():
    h.click(V(12, -8, 0))


def t_rect_key():
    s["st"] = h.in_sketch()
    h.check("sketch open on XY", s["st"] is not None)
    h.press("r")


def t_corner():
    si.click(V(0, 0, 0))


def t_size():
    si.move_towards(V(15, 12, 0), V(0.7, 0.7, 0))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("40")


def t_finish():
    st.esc()
    h.ribbon("Finish Sketch")


def t_extrude():
    h.fit()
    h.press("e")


def t_distance():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("Extrude opens", p is not None and not p._closed)
    if p is not None:
        ui.type_into(p.distance.widget, "10")


def t_extrude_ok():
    h.task_button("OK")


def t_shell():
    h.check("a 40 x 40 x 10 box", near(vol(), 16000.0), vol())
    h.fit()
    h.click_empty()
    h.ribbon("Shell")


def t_top():
    h.click(V(30, 25, TOP))


def t_thickness():
    from sciforge import shell_ui

    p = shell_ui.ShellPanel.last
    h.check("Shell opens with the top face", p is not None and len(p.names()) == 1, p and p.names())
    if p is not None:
        ui.type_into(p.inside.widget, "2")


def t_shell_ok():
    h.task_button("OK")


def t_sketch():
    h.check("the tray", near(vol(), TRAY), (vol(), TRAY))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def t_rim():
    h.click(V(1.0, 20, TOP))


def t_line1_key():
    s["sw"] = h.in_sketch()
    h.check("sketch on the rim", s["sw"] is not None)
    h.press("l")


def t_line1_start():
    si.click(V(10, 20, TOP))


def t_line1_typed():
    si.move_towards(V(15, 20.3, TOP), V(1, 0, 0))
    si.type_text("20", enter=False)
    si.tab()
    si.type_text("0")


def t_line2_key():
    st.esc()
    st.esc()
    h.press("l")


def t_line2_start():
    si.click(V(20, 10, TOP))


def t_line2_typed():
    si.move_towards(V(20.3, 15, TOP), V(0, 1, 0))
    si.type_text("20", enter=False)
    si.tab()
    si.type_text("90")


def t_finish2():
    st.esc()
    st.esc()
    lines = si.lines(s["sw"])
    h.check("two lines", len(lines) == 2, s["sw"].Geometry)
    g = s["sw"].getGlobalPlacement()
    s["lines"] = [(g.multVec(l.StartPoint), g.multVec(l.EndPoint)) for _i, l in lines]
    ok = len(lines) == 2 and all(abs((a - c).Length - 20.0) < 1e-6 for a, c in s["lines"])
    h.check("both 20 long", ok, s["lines"])
    h.ribbon("Finish Sketch")


# == Path 1: picking and dropping =================================================================
def p1_web():
    h.fit()
    h.click_empty()
    s["undo1"] = st.undo_counts()[0]
    st.menu("Web")


def p1_open():
    p = panel()
    h.check("P1 Web opens", p is not None and p.kind == "web")
    if p is None:
        return
    h.check("P1 nothing is taken", not p.refs, p.refs)
    h.check("P1 Extend Curves on", p.extend.isChecked())
    h.click_edge(line_mid(0))


def p1_one():
    p = panel()
    h.check("P1 the first line", p is not None and len(p.refs) == 1, p and p.refs)
    v = TRAY + plate(36.0, 2.0, 8.0)
    h.check("P1 one plate, wall to wall, down to the floor", near(vol(), v, 1e-6), (vol(), v))
    h.click_edge(line_mid(1) + V(0, 4, 0))


def p1_cross():
    p = panel()
    h.check("P1 the second line", p is not None and len(p.refs) == 2, p and p.refs)
    v = TRAY + cross(36.0, 2.0, 8.0)
    h.check("P1 the cross", near(vol(), v, 1e-6), (vol(), v))
    h.click_edge(line_mid(0) + V(4, 0, 0))


def p1_dropped():
    p = panel()
    h.check(
        "P1 clicking the first line again drops it",
        p is not None and len(p.refs) == 1,
        p and p.refs,
    )
    h.check(
        "P1 the line left is the second one",
        p is not None and len(p.refs) == 1 and p.refs[0][1] == "Edge2",
        p and p.refs,
    )
    v = TRAY + plate(36.0, 2.0, 8.0)
    h.check("P1 one plate left", near(vol(), v, 1e-6), (vol(), v))
    h.check("P1 no message", msg() == "", msg())
    h.click_edge(line_mid(0) + V(-4, 0, 0))


def p1_back():
    p = panel()
    h.check("P1 the first line again", p is not None and len(p.refs) == 2, p and p.refs)
    v = TRAY + cross(36.0, 2.0, 8.0)
    h.check("P1 the cross again", near(vol(), v, 1e-6), (vol(), v))
    hole_steps.click_checkbox(p.extend)


# == Path 2: values while the preview runs ========================================================
def p2_short():
    v = TRAY + cross(20.0, 2.0, 8.0)
    h.check("P2 Extend Curves off: the drawn 20 long cross", near(vol(), v, 1e-6), (vol(), v))
    hole_steps.click_checkbox(panel().extend)


def p2_extended():
    v = TRAY + cross(36.0, 2.0, 8.0)
    h.check("P2 Extend Curves on again", near(vol(), v, 1e-6), (vol(), v))
    hole_steps.click_checkbox(panel().flip)


def p2_flipped():
    h.check(
        "P2 Flip Direction: the dialog says why",
        "reach" in msg().lower() or "away" in msg().lower(),
        msg(),
    )
    h.check("P2 the preview stays", near(vol(), TRAY + cross(36.0, 2.0, 8.0), 1e-6), vol())
    h.task_button("OK")


def p2_flip_ok():
    h.check("P2 OK keeps the dialog", panel() is not None)
    hole_steps.click_checkbox(panel().flip)


def p2_unflipped():
    h.check("P2 no message", msg() == "", msg())
    b.choose(panel().side, "One Side")


def p2_one_side():
    v = TRAY + cross(36.0, 2.0, 8.0)
    h.check("P2 One Side: the same volume", near(vol(), v, 1e-6), (vol(), v))
    hole_steps.click_checkbox(panel().flip_side)


def p2_flip_side():
    v = TRAY + cross(36.0, 2.0, 8.0)
    h.check("P2 Flip Side: the same volume", near(vol(), v, 1e-6), (vol(), v))
    h.check("P2 no message", msg() == "", msg())
    b.choose(panel().depth_type, "Depth")


def p2_depth():
    ui.type_into(panel().depth.widget, "4")


# The web's preview is rebuilt on the shelled tray after the value is typed: in the full
# local run on a busy machine 0.7 s was not enough (the check read the volume before it).
p2_depth.wait_ms = 1500


def p2_depth4():
    v = TRAY + cross(36.0, 2.0, 4.0)
    h.check("P2 Depth 4", near(vol(), v, 1e-6), (vol(), v))
    s["v2"] = v
    h.fit()
    h.press(QtCore.Qt.Key_Return)


def p2_done():
    h.check("P2 Enter over the 3D view is OK", not st.dialog_open())
    h.check("P2 kept", near(vol(), s["v2"], 1e-6), vol())
    h.check("P2 one undo step", st.undo_counts()[0] == s["undo1"] + 1, st.undo_counts())
    h.check("P2 Web 1 in the timeline", "Web 1" in st.timeline_titles(), st.timeline_titles())
    h.shot("p2-web")
    st.ctrl("z")


def p2_undone():
    h.check("P2 Ctrl+Z: the tray", near(vol(), TRAY, 1e-6), vol())
    st.ctrl("y")


def p2_redone():
    h.check("P2 Ctrl+Y: the web", near(vol(), s["v2"], 1e-6), vol())
    h.fit()
    h.click_empty()
    # the lines' sketch was hidden when the web used it: shown again with its eye
    h.check("P3 the sketch's eye clicked", ti.click_eye(s["sw"].Label))


def p3_web():
    h.check("P3 the sketch is shown", s["sw"].ViewObject.Visibility)
    s["counts3"] = st.undo_counts()
    st.menu("Web")


def p3_open():
    p = panel()
    h.check("P3 Web opens", p is not None)
    a, c = s["lines"][0]
    # the sketch line lies on the top edge of the first web: the line is what is meant
    h.click_edge(a + (c - a) * 0.15)


def p3_one():
    p = panel()
    h.check("P3 one line picked", p is not None and len(p.refs) == 1, p and p.refs)
    st.esc()


def p3_esc():
    h.check("P3 Esc closes it", not st.dialog_open())
    h.check("P3 nothing changed", near(vol(), s["v2"], 1e-6), vol())
    h.check("P3 no undo step", st.undo_counts() == s["counts3"], (st.undo_counts(), s["counts3"]))
    h.check("P3 the sketch is still shown (it was shown before)", s["sw"].ViewObject.Visibility)
    h.check("P3 one web", len(st.features("web")) == 1, st.features("web"))
    st.edit_in_timeline("Web 1")


def p3_edit():
    p = panel()
    h.check("P3 the Web dialog edits it", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "P3 the edit shows Depth 4",
        p.depth_type.currentText() == "Depth" and near(p.depth.value(), 4.0),
    )
    h.check("P3 the edit shows its two lines", len(p.refs) == 2, p.refs)
    ui.type_into(p.thickness.widget, "3")


def p3_three():
    # One Side 3 thick: the plates still end at the 2 mm walls (they must not poke out)
    v = TRAY + cross(36.0, 3.0, 4.0)
    h.check("P3 thickness 3 previews", near(vol(), v, 1e-6), (vol(), v))
    st.ctrl("z")


def p3_cancelled():
    h.check("P3 Ctrl+Z in the dialog cancels the edit", not st.dialog_open())
    h.check("P3 the web as it was", near(vol(), s["v2"], 1e-6), vol())
    h.check("P3 the body is shown", st.shown(h.body()))
    h.check("P3 no pop-up", not h.popups(), h.popups())
    h.shot("p3-done")


h.run(
    "sweep_loft_qa_web",
    si.watched(
        [
            new_design,
            t_xy,
            t_rect_key,
            t_corner,
            t_size,
            t_finish,
            t_extrude,
            t_distance,
            t_extrude_ok,
            t_shell,
            t_top,
            t_thickness,
            t_shell_ok,
            t_sketch,
            t_rim,
            t_line1_key,
            t_line1_start,
            t_line1_typed,
            t_line2_key,
            t_line2_start,
            t_line2_typed,
            t_finish2,
            p1_web,
            p1_open,
            p1_one,
            p1_cross,
            p1_dropped,
            p1_back,
            p2_short,
            p2_extended,
            p2_flipped,
            p2_flip_ok,
            p2_unflipped,
            p2_one_side,
            p2_flip_side,
            p2_depth,
            p2_depth4,
            p2_done,
            p2_undone,
            p2_redone,
            p3_web,
            p3_open,
            p3_one,
            p3_esc,
            p3_edit,
            p3_three,
            p3_cancelled,
        ]
    ),
)
