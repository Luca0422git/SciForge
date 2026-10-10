# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet on a plate with a round boss, only real input: start F with nothing selected
and click the boss's Extrude in the timeline (its top edge and its foot, an inside
corner, are picked), OK; then a Chamfer where a click on empty space keeps the pick and
pressing E (another command) finishes it; then edit the *earlier* fillet from the
timeline: the part rolls back to it while editing and the later chamfer comes back
after OK. Geometry checked with Pappus' rule (see blend_steps)."""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
R = 5.0  # boss radius
PLATE = 40 * 30 * 5
BOSS = math.pi * R * R * 5


def boss_rounds(r):
    """The top round removes A * 2 pi (R - x), the foot round adds A * 2 pi (R + x)."""
    return b.spandrel(r) * 2 * math.pi * 2 * b.xbar(r)


def sketch_on_top():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_top():
    h.fit()
    h.click(V(30, 25, 5))


def draw_boss():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk:
        x, y = h.to_sketch(sk, V(20, 15, 5))
        h.draw_circle(sk, x, y, R)


def finish_boss_sketch():
    h.ribbon("Finish Sketch")


def extrude_boss():
    h.fit()
    h.press("e")


def boss_height():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if field is not None:
        b.type_into(field, "5")


def boss_ok():
    h.task_button("OK")


def boss_made():
    v = h.solid_volume()
    h.check("plate with a boss (V = 6000 + 125 pi)", b.close(v, PLATE + BOSS), v)
    h.fit()


def fillet_start():
    h.click_empty()
    h.press("f")


def click_boss_in_timeline():
    button = b.timeline_button("Extrude 2")
    if h.check("timeline shows Extrude 2", button is not None, b.timeline_titles()):
        b.click_widget(button)


def feature_picked():
    p = b.blend_panel()
    h.check("the boss's two edges are picked", p is not None and len(p.refs) == 2, p and p.refs)
    v = h.solid_volume()
    expect = PLATE + BOSS + boss_rounds(1.0)
    h.check("preview: top rounded, foot filled (r 1)", b.close(v, expect), (v, expect))
    h.shot("1-feature-picked")
    h.task_button("OK")


def after_fillet():
    v = h.solid_volume()
    expect = PLATE + BOSS + boss_rounds(1.0)
    h.check("boss fillet kept", b.close(v, expect), (v, expect))
    h.check("10 faces", len(h.body().Shape.Faces) == 10, len(h.body().Shape.Faces))
    s["v"] = v
    h.fit()


def chamfer_start():
    h.ribbon("Chamfer")


def chamfer_edge():
    h.fit()
    h.click(V(20, 0, 5))


def click_empty_space():
    h.click_empty()


def pick_kept():
    p = b.blend_panel()
    h.check("clicking empty space keeps the pick", p is not None and len(p.refs) == 1, p and p.refs)
    v = h.solid_volume()
    h.check("chamfer 1 preview on the front edge", b.close(v, s["v"] - 40 * 0.5), v)


def press_e():
    h.press("e")


def chamfer_finished():
    v = h.solid_volume()
    h.check("starting Extrude finished the chamfer (kept)", b.close(v, s["v"] - 40 * 0.5), v)
    h.check("chamfer in the timeline", "Chamfer 1" in b.timeline_titles(), b.timeline_titles())
    h.check("Extrude dialog is open now", b.blend_panel() is None and Gui.Control.activeDialog())
    h.task_button("Cancel")


def edit_fillet():
    s["v"] = h.solid_volume()
    h.fit()
    b.timeline_double_click("Fillet 1")


def rolled_back():
    p = b.blend_panel()
    h.check("editing Fillet 1", p is not None and p.target is not None and not p.created)
    h.check(
        "the part shows Fillet 1 (later chamfer rolled back while editing)",
        b.close(h.body().Shape.Volume, s["v"])
        and p is not None
        and p.target.ViewObject.Visibility
        and not b.blends()[1].ViewObject.Visibility,
    )
    h.check("both boss edges shown picked", p is not None and len(p.refs) == 2, p and p.refs)
    h.shot("2-edit-earlier")
    if p:
        b.type_into(p.radius.widget, "0.5")


def edit_ok():
    h.task_button("OK")


def after_edit():
    v = h.solid_volume()
    expect = PLATE + BOSS + boss_rounds(0.5) - 40 * 0.5
    h.check("fillet now r 0.5 and the later chamfer still there", b.close(v, expect), (v, expect))
    fillet, chamfer = b.blends()
    h.check(
        "the body shows its last step again",
        chamfer.ViewObject.Visibility
        and not fillet.ViewObject.Visibility
        and h.body().Tip is chamfer,
    )
    h.check("valid solid", h.body().Shape.isValid())
    h.check(
        "no kernel errors in the Report view",
        not b.report_has_kernel_errors(),
        b.report_has_kernel_errors(),
    )
    h.shot("3-end")


h.run(
    "fillet_features",
    b.box_steps("FilletFeatures", height=5)
    + [
        sketch_on_top,
        pick_top,
        draw_boss,
        finish_boss_sketch,
        extrude_boss,
        boss_height,
        boss_ok,
        boss_made,
        fillet_start,
        click_boss_in_timeline,
        feature_picked,
        after_fillet,
        chamfer_start,
        chamfer_edge,
        click_empty_space,
        pick_kept,
        press_e,
        chamfer_finished,
        edit_fillet,
        rolled_back,
        edit_ok,
        after_edit,
    ],
)
