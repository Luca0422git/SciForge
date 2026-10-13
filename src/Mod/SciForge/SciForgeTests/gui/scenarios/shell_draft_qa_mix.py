# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell, Scale and the timeline on a part made of several steps (QA, only real input).
A 40 x 30 x 10 box with a 10 x 10 x 5 boss on top (Create Sketch on the top face, E).

Path 1, the history marker dragged back to just before the boss's Extrude (after its
        sketch), Shell taking the bottom away (the person turns the part to see it):
        the shell goes in at the marker; the marker back to the end: the boss sits on the
        shelled box.
Path 2, the shell edited from the timeline (1 mm): the boss follows.
Path 3, Scale Non Uniform (Z 2) at the end, the part picked in the browser first.
Path 4, the shell deleted from the timeline: the boss and the scale stay; Ctrl+Z brings
        the shell back.
Path 5, the shell suppressed and unsuppressed from the timeline.
Path 6, the design saved, then Ctrl+S while a second Scale (0.5) previews: the scale is
        kept (like starting any command) and the file holds it, nothing left unsaved.
Path 7, a cup for the printer: a circle r 10, E 20, Shell taking the top away (1 mm); the
        arrow sits on the round rim; Tangent Chain keeps the flat top alone.

Volumes by hand: open box (bottom away) 12000 - (40-2t)(30-2t)(10-t); boss 500; a scale
by (1, 1, 2) doubles the volume; a cup pi (10^2 20 - 9^2 19).
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
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as tl
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
BOSS = 500.0


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def msg(p):
    return p.message.text() if p is not None else ""


def open_bottom(t):
    return sd.BOX - (40 - 2 * t) * (30 - 2 * t) * (10 - t)


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())
    h.check("%s: nothing left see-through" % where, not b.see_through(), b.see_through())


# -- the boss -----------------------------------------------------------------------------------
def boss_sketch():
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def boss_face():
    h.fit()
    h.click(V(30, 22, 10))


def boss_draw():
    sk = h.in_sketch()
    if not h.check("a sketch on the top", sk is not None):
        return
    x0, y0 = h.to_sketch(sk, V(15, 10, 10))
    x1, y1 = h.to_sketch(sk, V(25, 20, 10))
    h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def boss_finish():
    h.ribbon("Finish Sketch")


def boss_e():
    h.fit()
    h.press("e")


def boss_distance():
    p = b.active_panel()
    if p is not None and getattr(p, "distance", None) is not None:
        ui.type_into(p.distance.widget, "5")


def boss_ok():
    h.task_button("OK")


def boss_made():
    h.check("box and boss", sd.close(h.solid_volume(), sd.BOX + BOSS), h.solid_volume())
    s["titles"] = sd.timeline_titles()
    h.check("the boss is Extrude 2", "Extrude 2" in s["titles"], s["titles"])


# -- Path 1: the shell inserted at the rolled-back marker -------------------------------------
def p1_roll():
    tl.drag_marker(before_title="Extrude 2")


def p1_rolled():
    h.check("P1 rolled back: just the box", sd.close(h.solid_volume(), sd.BOX), h.solid_volume())
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def p1_bottom():
    p = sd.shell_panel()
    h.check("P1 Shell starts on the rolled-back part", p is not None and p.base is not None, msg(p))
    h.check("P1 no message", msg(p) == "", msg(p))
    h.view().viewBottom()  # the person turns the part over to reach its bottom
    h.view().fitAll()
    h.click(V(20, 15, 0))
    h.fit()


def p1_type():
    p = sd.shell_panel()
    h.check("P1 the bottom picked", p is not None and len(p.names()) == 1, p and p.names())
    if p:
        ui.type_into(p.inside.widget, "2")


def p1_ok():
    v = h.solid_volume()
    h.check("P1 the box shelled", sd.close(v, open_bottom(2)), (v, open_bottom(2)))
    h.task_button("OK")


def p1_inserted():
    titles = sd.timeline_titles()
    h.check(
        "P1 the shell sits before the boss",
        "Shell 1" in titles and titles.index("Shell 1") < titles.index("Extrude 2"),
        titles,
    )
    tl.drag_marker(to_end=True)


def p1_end():
    v = h.solid_volume()
    expect = open_bottom(2) + BOSS
    h.check("P1 at the end: the boss on the shelled box", sd.close(v, expect), (v, expect))
    part_ok("P1")
    h.shot("p1-inserted")


# -- Path 2: the shell edited ---------------------------------------------------------------
def p2_edit():
    h.fit()
    b.timeline_double_click("Shell 1", click_first=True)


def p2_type():
    p = sd.shell_panel()
    h.check("P2 editing the shell", p is not None and p.editing)
    h.check("P2 its bottom face shown", p is not None and len(p.names()) == 1)
    if p:
        ui.type_into(p.inside.widget, "1")


def p2_ok():
    v = h.solid_volume()
    h.check("P2 the preview has the boss", sd.close(v, open_bottom(1) + BOSS), v)
    h.task_button("OK")


def p2_done():
    v = h.solid_volume()
    h.check("P2 1 mm walls, the boss kept", sd.close(v, open_bottom(1) + BOSS), v)
    part_ok("P2")
    s["v2"] = v


# -- Path 3: Scale with the body picked in the browser -----------------------------------------
def p3_pick():
    Gui.Selection.clearSelection()
    sd.click_browser_row("Body")


def p3_scale():
    h.ribbon("Scale")


def p3_type():
    p = sd.scale_panel()
    h.check("P3 the body is taken", p is not None and p.base is not None)
    if p:
        ui.choose(p.scale_type, "Non Uniform")
        ui.type_into(p.axis_fields["z"].widget, "2")


def p3_ok():
    h.check("P3 twice as high", sd.close(h.solid_volume(), 2 * s["v2"], 1e-5), h.solid_volume())
    h.task_button("OK")


def p3_done():
    h.check("P3 kept", sd.close(h.solid_volume(), 2 * s["v2"], 1e-5), h.solid_volume())
    part_ok("P3")
    s["v3"] = h.solid_volume()


# -- Path 4: delete the shell, Ctrl+Z ----------------------------------------------------------
def p4_delete():
    tl.menu("Shell 1", "Delete")


def p4_deleted():
    sd.no_popups("deleting the shell")
    v = h.solid_volume()
    h.check(
        "P4 no shell: the solid box and boss, scaled", sd.close(v, 2 * (sd.BOX + BOSS), 1e-5), v
    )
    h.check("P4 Shell 1 gone", "Shell 1" not in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P4")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p4_undone():
    h.check("P4 Ctrl+Z: the shell is back", sd.close(h.solid_volume(), s["v3"], 1e-5))
    h.check("P4 Shell 1 again", "Shell 1" in sd.timeline_titles(), sd.timeline_titles())
    part_ok("P4 undo")


# -- Path 5: suppress the shell ---------------------------------------------------------------
def p5_suppress():
    tl.menu("Shell 1", "Suppress Features")


def p5_suppressed():
    v = h.solid_volume()
    h.check("P5 suppressed: solid again", sd.close(v, 2 * (sd.BOX + BOSS), 1e-5), v)
    tl.menu("Shell 1", "Unsuppress Features")


def p5_back():
    h.check("P5 unsuppressed: hollow again", sd.close(h.solid_volume(), s["v3"], 1e-5))
    part_ok("P5")
    h.check("P5 nothing in the Report view", not sd.report_errors(), sd.report_errors())
    h.shot("p5-end")


# -- Path 6: Ctrl+S while a dialog is open --------------------------------------------------------
def p6_save_first():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-mix-qa-"), "mix_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("P6 saved", os.path.isfile(path), path)
    Gui.Selection.clearSelection()
    h.ribbon("Scale")


def p6_body():
    h.fit()
    h.click(V(40, 15, 10))


def p6_type():
    p = sd.scale_panel()
    h.check("P6 the body is taken", p is not None and p.base is not None)
    if p:
        ui.type_into(p.factor.widget, "0.5")


def p6_ctrl_s():
    h.check("P6 previewed", sd.close(h.solid_volume(), s["v3"] / 8, 1e-5), h.solid_volume())
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def p6_describe():
    """Fusion's Save asks for a version description on a saved design; Enter skips it."""
    h.check("P6 the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def p6_saved():
    h.check("P6 Ctrl+S finished the dialog first", not dialog_open())
    h.check("P6 the scale was kept", sd.close(h.solid_volume(), s["v3"] / 8, 1e-5))
    h.check("P6 Scale 2 in the timeline", "Scale 2" in sd.timeline_titles(), sd.timeline_titles())
    h.check("P6 nothing left unsaved", not doc().isTouched() and not b.modified())
    sd.no_popups("Ctrl+S with Scale open")
    part_ok("P6")


# -- Path 7: a cup -------------------------------------------------------------------------------
def p7_cup():
    h.check("P7 a cylinder r 10 x 20", sd.close(h.solid_volume(), math.pi * 2000), h.solid_volume())
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def p7_top():
    h.fit()
    h.click(V(3, 2, 20))


def p7_picked():
    p = sd.shell_panel()
    h.check("P7 just the flat top (its edge is sharp)", p is not None and len(p.names()) == 1)
    h.check("P7 an arrow on the round rim", p is not None and len(p.arrows) == 1)
    v = h.solid_volume()
    expect = math.pi * (100 * 20 - 81 * 19)
    h.check("P7 a cup with 1 mm walls", sd.close(v, expect), (v, expect, msg(p)))
    h.check("P7 no message", msg(p) == "", msg(p))
    h.shot("p7-cup")
    h.task_button("OK")


def p7_done():
    h.check("P7 kept", sd.close(h.solid_volume(), math.pi * (100 * 20 - 81 * 19)))
    part_ok("P7")
    h.check("P7 nothing in the Report view", not sd.report_errors(), sd.report_errors())


def circle(sketch):
    h.draw_circle(sketch, 0, 0, 10)


h.run(
    "shell_draft_qa_mix",
    tl.watched(
        sd.box_steps("MixQA")
        + [
            boss_sketch,
            boss_face,
            boss_draw,
            boss_finish,
            boss_e,
            boss_distance,
            boss_ok,
            boss_made,
            p1_roll,
            p1_rolled,
            p1_bottom,
            p1_type,
            p1_ok,
            p1_inserted,
            p1_end,
            p2_edit,
            p2_type,
            p2_ok,
            p2_done,
            p3_pick,
            p3_scale,
            p3_type,
            p3_ok,
            p3_done,
            p4_delete,
            p4_deleted,
            p4_undone,
            p5_suppress,
            p5_suppressed,
            p5_back,
            p6_save_first,
            p6_body,
            p6_type,
            p6_ctrl_s,
            p6_describe,
            p6_saved,
        ]
        + b.box_steps("CupQA", height=20, profile=circle)
        + [p7_cup, p7_top, p7_picked, p7_done]
    ),
)
