# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet and Chamfer on real multi-step parts, the way Fusion users build them (QA, only
real input except where noted).

Path 8, a part built step by step: fillet the box, Create Sketch on the top face, extrude a
        boss, fillet its top edge (Enter), Press Pull that round (it stays the same fillet),
        a pocket cut into the side with Extrude, a chamfer on the pocket's mouth; then the
        first Extrude is made taller from the timeline and every later step follows.
Path 9, history edits around fillets: an earlier fillet edited to round one more edge (that
        trims the edge a later fillet rounds), the timeline marker rolled back and a fillet
        inserted before two later ones; both later fillets keep their edges, nothing in the
        Report view (before: "Invalid edge link", the later fillets broke).
Path 10, a body made of two separate solids (two rectangles extruded together, like a
        Fusion body with two lumps): a fillet on one of them works (before: "would cut the
        part into pieces").
Path 11, parameters: a radius typed as a formula ("r*2") follows the parameter; a typo is
        explained and OK waits; a plain number typed later drops the formula. (The
        parameter itself is set up and changed by code: the Change Parameters dialog has
        its own tests.)

Numbers by hand (see blend_steps): rounds on straight edges, Pappus' rule on the boss.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
RIGHT_TOP = V(40, 15, 10)
BACK_TOP = V(20, 30, 10)
LEFT_TOP = V(0, 15, 10)
R = 5.0  # boss radius
C = (20.0, 16.0)  # boss centre on the top face


def step(fn, name):
    fn.__name__ = name
    return fn


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def picks():
    p = b.blend_panel()
    return list(p.refs) if p else None


def boss_round(r):
    """Volume a round of radius r takes off the boss's top edge (Pappus)."""
    return b.spandrel(r) * 2 * math.pi * (R - b.xbar(r))


def broken():
    return [o.Name for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def x_extrude():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def sketch_steps(tag, point, draw):
    """Create Sketch, click the face at `point`, draw(sketch), Finish Sketch."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(point)

    def drawing():
        sk = h.in_sketch()
        h.check("sketch %s open" % tag, sk is not None)
        if sk:
            draw(sk)

    def finish():
        h.ribbon("Finish Sketch")

    def after():
        h.check("left sketch %s" % tag, h.in_sketch() is None)
        h.fit()

    return [
        step(create, "sketch_%s_create" % tag),
        step(pick, "sketch_%s_pick" % tag),
        step(drawing, "sketch_%s_draw" % tag),
        step(finish, "sketch_%s_finish" % tag),
        step(after, "sketch_%s_after" % tag),
    ]


def extrude_steps(tag, distance):
    """E, type the distance, OK (the sketch just finished is the profile)."""

    def press_e():
        h.press("e")

    def distance_typed():
        p = x_extrude()
        h.check("Extrude %s open" % tag, p is not None and dialog_open())
        if p is not None:
            ui.type_into(p.distance.widget, distance)

    def ok():
        h.task_button("OK")

    def done():
        h.check("Extrude %s done" % tag, not dialog_open())
        h.fit()

    return [
        step(press_e, "extrude_%s_e" % tag),
        step(distance_typed, "extrude_%s_distance" % tag),
        step(ok, "extrude_%s_ok" % tag),
        step(done, "extrude_%s_done" % tag),
    ]


# -- Path 8: a part built step by step, then its first step changed ---------------------------
def p8_f():
    h.click_empty()
    h.press("f")


def p8_pick():
    h.fit()
    h.click_edge(FRONT_TOP)


def p8_radius():
    p = b.blend_panel()
    h.check("P8 front edge picked", p is not None and len(p.refs) == 1, picks())
    if p:
        ui.type_into(p.radius.widget, "2")


def p8_ok():
    h.task_button("OK")


def p8_fillet1():
    s["v"] = b.BOX - 40 * b.spandrel(2)
    h.check("P8 Fillet 1 (r 2)", b.close(h.solid_volume(), s["v"]), h.solid_volume())


def draw_boss(sk):
    x, y = h.to_sketch(sk, V(C[0], C[1], 10))
    h.draw_circle(sk, x, y, R)


def p8_boss_made():
    s["v"] += math.pi * R * R * 5
    h.check("P8 boss on the rounded box", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.click_empty()
    h.press("f")


def on_boss(radius, z, angle=-60.0):
    """A point at `radius` from the boss's axis, at height z, on the side facing the camera
    (away from the circle's seam at 0 degrees, which a person does not aim at)."""
    a = math.radians(angle)
    return V(C[0] + radius * math.cos(a), C[1] + radius * math.sin(a), z)


def p8_boss_edge():
    h.fit()
    h.click_edge(on_boss(R, 15))


def p8_boss_radius():
    p = b.blend_panel()
    h.check("P8 the boss's top edge picked", p is not None and len(p.refs) == 1, picks())
    if p:
        b.type_into(p.radius.widget, "1")
        b.press_enter(p.radius.widget)


def p8_boss_fillet():
    h.check("P8 Enter finished the fillet", not dialog_open())
    v = s["v"] - boss_round(1)
    h.check("P8 boss round r 1 (Pappus)", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.check("P8 two fillets", len(b.blends()) == 2, b.blends())
    h.shot("p8-boss")
    h.fit()
    # the middle of the round, 45 degrees up
    k = math.sqrt(0.5)
    h.click(on_boss(R - 1 + k, 14 + k))


def p8_press_q():
    sel = [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]
    h.check("P8 the round face is selected", len(sel) == 1 and sel[0][1], sel)
    h.press("q")


def p8_pp_value():
    fields = b.task_spinboxes()
    if h.check("P8 Press Pull shows a size field", fields, fields):
        ui.type_into(fields[0], "2")


def p8_pp_ok():
    h.task_button("OK")


def p8_pp_done():
    v = s["v"] - boss_round(2)
    h.check("P8 Press Pull made the boss round r 2", b.close(h.solid_volume(), v), h.solid_volume())
    h.check("P8 still two fillets (the same step)", len(b.blends()) == 2, b.blends())
    s["v"] = v


def draw_pocket(sk):
    ax, ay = h.to_sketch(sk, V(40, 10, 2))
    bx, by = h.to_sketch(sk, V(40, 20, 6))
    h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def p8_pocket_made():
    s["v"] -= 200.0
    h.check("P8 pocket 10 x 4 x 5 cut", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.click_empty()
    h.ribbon("Chamfer")


def p8_pocket_edge():
    h.fit()
    h.click_edge(V(40, 15, 6))


def p8_chamfer_size():
    p = b.blend_panel()
    h.check("P8 the pocket's top edge picked", p is not None and len(p.refs) == 1, picks())
    if p:
        ui.type_into(p.distance.widget, "0.5")


def p8_chamfer_ok():
    v = s["v"] - 10 * 0.5 * 0.5 / 2
    h.check("P8 chamfer 0.5 preview", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.task_button("OK")


def p8_chamfer_done():
    s["v"] -= 10 * 0.5 * 0.5 / 2
    h.check("P8 chamfer kept", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.shot("p8-part")
    h.fit()
    b.timeline_double_click("Extrude 1")


def p8_edit_base():
    p = x_extrude()
    h.check("P8 editing the first Extrude", p is not None and p.editing and dialog_open())
    if p is not None:
        ui.type_into(p.distance.widget, "12")


def p8_edit_base_ok():
    h.task_button("OK")


def p8_followed():
    h.check("P8 edit kept", not dialog_open())
    v = s["v"] + 40 * 30 * 2
    h.check(
        "P8 every later step follows the taller box (+2400)",
        b.close(h.solid_volume(), v),
        (h.solid_volume(), v),
    )
    h.check("P8 nothing broken in the timeline", not broken(), broken())
    bb = h.body().Shape.BoundBox
    h.check("P8 the boss moved up with the top face", b.close(bb.ZMax, 17.0), bb)
    h.check("P8 valid solid", h.body().Shape.isValid())
    h.shot("p8-taller")


# -- Path 9: history edits around fillets --------------------------------------------------------
def fillet_steps(tag, point, radius):
    def start():
        h.click_empty()
        h.press("f")

    def pick():
        h.fit()
        h.click_edge(point)

    def size():
        p = b.blend_panel()
        h.check("%s edge picked" % tag, p is not None and len(p.refs) == 1, picks())
        if p:
            ui.type_into(p.radius.widget, radius)

    def ok():
        h.task_button("OK")

    def done():
        h.check("%s done" % tag, not dialog_open())

    return [
        step(start, "%s_f" % tag),
        step(pick, "%s_pick" % tag),
        step(size, "%s_size" % tag),
        step(ok, "%s_ok" % tag),
        step(done, "%s_done" % tag),
    ]


def p9_two_fillets():
    v = b.BOX - 40 * b.spandrel(2) - 40 * b.spandrel(1)
    h.check("P9 front r 2 and back r 1", b.close(h.solid_volume(), v), h.solid_volume())
    s["v"] = v
    s["fillets"] = [f.Name for f in b.blends()]
    h.fit()
    b.timeline_double_click("Fillet 1")


def p9_editing():
    p = b.blend_panel()
    h.check("P9 editing Fillet 1", p is not None and not p.created)
    h.click_edge(RIGHT_TOP)


def p9_added():
    p = b.blend_panel()
    h.check("P9 the right edge added", p is not None and len(p.refs) == 2, picks())
    h.check(
        "P9 the dialog reports no broken later step",
        p and "⚠" not in p.message.text(),
        p and p.message.text(),
    )
    h.task_button("OK")


def p9_edit_done():
    h.check("P9 edit kept", not dialog_open())
    h.check("P9 the later fillet still works", not broken(), broken())
    v = h.solid_volume()
    expect = s["v"] - 30 * b.spandrel(2)
    h.check("P9 one more round of r 2 (corners aside)", abs(v - expect) < 2.0, (v, expect))
    fl = doc().getObject(s["fillets"][1])
    h.check(
        "P9 the later fillet still rounds the back edge",
        fl.Shape.isValid() and fl.Shape.Volume < v + 1e-6,
    )
    h.check("P9 two fillets", len(b.blends()) == 2)
    s["v"] = v
    h.shot("p9-edited")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p9_edit_undone():
    v = b.BOX - 40 * b.spandrel(2) - 40 * b.spandrel(1)
    h.check("P9 Ctrl+Z takes the edit back", b.close(h.solid_volume(), v), h.solid_volume())
    h.check("P9 and both fillets work", not broken(), broken())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def p9_edit_redone():
    h.check("P9 Ctrl+Y brings the edit back", b.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P9 the later fillet still works after the redo", not broken(), broken())


def timeline_button_of(name):
    from sciforge import timeline_ui

    tl = timeline_ui._dock.widget()
    tl.refresh()
    for button in tl._buttons:
        if button.item.name == name:
            return button
    return None


def p9_roll_back():
    button = timeline_button_of(doc().getObject("Extrude").Name)
    if h.check("P9 timeline shows the first extrude", button is not None):
        w.right_click(button, w.center(button), "Roll History Marker Here")


def p9_rolled():
    h.check("P9 the marker is on the extrude", h.body().Tip.Name == "Extrude", h.body().Tip.Name)
    h.fit()
    h.press("f")


def p9_insert_pick():
    h.fit()
    h.click_edge(LEFT_TOP)


def p9_insert_size():
    p = b.blend_panel()
    h.check(
        "P9 the left edge picked on the rolled-back part",
        p is not None and len(p.refs) == 1,
        picks(),
    )
    if p:
        ui.type_into(p.radius.widget, "1")


def p9_insert_ok():
    h.task_button("OK")


def p9_inserted():
    h.check("P9 inserted", not dialog_open())
    names = [o.Name for o in h.body().Group if o.TypeId == "PartDesign::Fillet"]
    new = [n for n in names if n not in s["fillets"]]
    h.check("P9 a new fillet", len(new) == 1, names)
    h.check(
        "P9 it sits before the two later fillets", names and names[0] == (new or [None])[0], names
    )
    h.check("P9 the later fillets keep working", not broken(), broken())
    s["new"] = new[0] if new else None
    button = timeline_button_of(s["fillets"][1])
    if h.check("P9 timeline shows the last fillet", button is not None):
        w.right_click(button, w.center(button), "Roll History Marker Here")


def p9_at_end():
    h.check("P9 the marker is at the end", h.body().Tip.Name == s["fillets"][1], h.body().Tip.Name)
    v = h.solid_volume()
    # The new r 1 round's ends are tangent to the front and back edges, so the later
    # fillets' tangent chains now run on round its corner and down the vertical edges
    # (Fusion's Tangent Chain does the same): at least the r 1 round itself comes off.
    expect = s["v"] - 30 * b.spandrel(1)
    h.check(
        "P9 the whole part: one more round of r 1 (and the chains around it)",
        expect - 15.0 < v < expect + 0.5,
        (v, expect),
    )
    h.check("P9 nothing broken", not broken(), broken())
    h.check("P9 valid solid", h.body().Shape.isValid())
    h.check("P9 the last step is shown", h.body().Tip.ViewObject.isVisible())
    h.shot("p9-end")


# -- Path 10: a body with two separate solids ------------------------------------------------------
def p10_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("FilletLumps")
    h.fit()


def draw_two(sk):
    h.draw_rectangle(sk, 0, 0, 10, 10)
    h.draw_rectangle(sk, 20, 0, 30, 10)


def p10_e():
    h.press("e")


def p10_first():
    h.fit()
    h.click(V(5, 5, 0))


def p10_second():
    h.click(V(25, 5, 0))


def p10_height():
    p = x_extrude()
    h.check("P10 both areas picked", p is not None and len(p.profiles) == 2, p and p.profiles)
    if p:
        ui.type_into(p.distance.widget, "10")


def p10_ok():
    h.task_button("OK")


def p10_two_lumps():
    shape = h.body().Shape
    h.check("P10 one body, two solids", len(shape.Solids) == 2, len(shape.Solids))
    h.check("P10 2 x 1000", b.close(shape.Volume, 2000.0), shape.Volume)
    h.fit()
    h.click_empty()
    h.press("f")


def p10_pick():
    h.fit()
    h.click_edge(V(5, 0, 10))


def p10_preview():
    p = b.blend_panel()
    h.check("P10 the edge picked", p is not None and len(p.refs) == 1, picks())
    text = p.message.text() if p else ""
    h.check("P10 no 'pieces' error on a two-solid body", "⚠" not in text, text)
    v = 2000.0 - 10 * b.spandrel(1)
    h.check("P10 preview r 1", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.task_button("OK")


def p10_done():
    h.check("P10 OK closed the dialog", not dialog_open())
    h.check("P10 one fillet", len(b.blends()) == 1, b.blends())
    shape = h.body().Shape
    h.check("P10 still two solids", len(shape.Solids) == 2, len(shape.Solids))
    s["v"] = shape.Volume


# -- Path 11: a radius from a parameter ------------------------------------------------------------
def p11_parameter():
    """Set-up by code (as if made earlier with Change Parameters): r = 1.5 mm."""
    from sciforge import parameters

    parameters.add_user(doc(), "r", "mm", "1.5")
    doc().recompute()
    h.press("f")


def p11_pick():
    h.fit()
    h.click_edge(V(25, 0, 10))


def p11_formula():
    p = b.blend_panel()
    h.check("P11 an edge of the second solid picked", p is not None and len(p.refs) == 1, picks())
    if p:
        ui.type_into(p.radius.widget, "r*2")


def p11_formula_preview():
    p = b.blend_panel()
    if p is None:
        return
    h.check(
        "P11 the box shows the value of r*2", abs(p.radius.value() - 3.0) < 1e-9, p.radius.value()
    )
    h.check("P11 the formula is shown", "r*2" in p.formulas.text(), p.formulas.text())
    v = s["v"] - 10 * b.spandrel(3)
    h.check("P11 preview r 3", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    b.no_popups("a formula typed in the radius box")
    h.shot("p11-formula")
    h.task_button("OK")


def p11_kept():
    fl = b.blends()[-1]
    expr = dict(fl.ExpressionEngine).get("Radius", "")
    h.check("P11 the fillet's radius follows r", "r" in expr and "2" in expr, fl.ExpressionEngine)
    from sciforge import parameters

    parameters.set_user(doc(), "r", "1")
    doc().recompute()


def p11_followed():
    v = s["v"] - 10 * b.spandrel(2)
    h.check("P11 r = 1: the round is r 2 now", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.fit()
    b.timeline_double_click("Fillet 2")


def p11_editing():
    p = b.blend_panel()
    h.check("P11 editing the formula fillet", p is not None and not p.created)
    if p is None:
        return
    h.check(
        "P11 its formula is shown", "r*2" in p.formulas.text().replace(" ", ""), p.formulas.text()
    )
    h.check("P11 its value is shown", abs(p.radius.value() - 2.0) < 1e-9, p.radius.value())
    ui.type_into(p.radius.widget, "foo+")


def p11_typo():
    p = b.blend_panel()
    text = p.message.text() if p else ""
    h.check("P11 a typo is explained in the dialog", "⚠" in text and "foo" in text, text)
    b.no_popups("a typo in the radius box")
    h.task_button("OK")


def p11_typo_refused():
    h.check("P11 OK waits while the box holds no value", dialog_open() and b.blend_panel())
    p = b.blend_panel()
    if p:
        ui.type_into(p.radius.widget, "2.5")


def p11_number():
    p = b.blend_panel()
    if p is None:
        return
    h.check("P11 a plain number drops the formula", "r" not in p.formulas.text(), p.formulas.text())
    h.check("P11 no message left", "⚠" not in p.message.text(), p.message.text())
    h.task_button("OK")


def p11_done():
    fl = b.blends()[-1]
    h.check("P11 no formula on the fillet any more", "Radius" not in dict(fl.ExpressionEngine))
    v = s["v"] - 10 * b.spandrel(2.5)
    h.check("P11 r 2.5", b.close(h.solid_volume(), v), (h.solid_volume(), v))
    h.check("P11 valid", h.body().Shape.isValid() and not broken())


h.run(
    "fillet_qa_part",
    b.box_steps("FilletPart")
    + [p8_f, p8_pick, p8_radius, p8_ok, p8_fillet1]
    + sketch_steps("boss", V(30, 25, 10), draw_boss)
    + extrude_steps("boss", "5")
    + [
        p8_boss_made,
        p8_boss_edge,
        p8_boss_radius,
        p8_boss_fillet,
        p8_press_q,
        p8_pp_value,
        p8_pp_ok,
        p8_pp_done,
    ]
    + sketch_steps("pocket", V(40, 25, 4), draw_pocket)
    + extrude_steps("pocket", "-5")
    + [
        p8_pocket_made,
        p8_pocket_edge,
        p8_chamfer_size,
        p8_chamfer_ok,
        p8_chamfer_done,
        p8_edit_base,
        p8_edit_base_ok,
        p8_followed,
    ]
    + b.box_steps("FilletInsert")
    + fillet_steps("P9a", FRONT_TOP, "2")
    + fillet_steps("P9b", BACK_TOP, "1")
    + [
        p9_two_fillets,
        p9_editing,
        p9_added,
        p9_edit_done,
        p9_edit_undone,
        p9_edit_redone,
        p9_roll_back,
        p9_rolled,
        p9_insert_pick,
        p9_insert_size,
        p9_insert_ok,
        p9_inserted,
        p9_at_end,
        p10_new,
    ]
    + sketch_steps("lumps", V(12, -8, 0), draw_two)
    + [
        p10_e,
        p10_first,
        p10_second,
        p10_height,
        p10_ok,
        p10_two_lumps,
        p10_pick,
        p10_preview,
        p10_done,
        p11_parameter,
        p11_pick,
        p11_formula,
        p11_formula_preview,
        p11_kept,
        p11_followed,
        p11_editing,
        p11_typo,
        p11_typo_refused,
        p11_number,
        p11_done,
    ],
)
