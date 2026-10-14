# SPDX-License-Identifier: LGPL-2.1-or-later
"""Primitives QA on a part made of several features, mixed with Create Sketch, Extrude and
Press Pull before and after (only real input).

P5. A 40 x 30 x 10 block (Create Sketch, rectangle, E). Top face selected, Cylinder: a
    hole d6, Height -10 typed (Cut by itself). Top face selected again (it now belongs to
    the hole's step), Box: Fusion hangs the box on the face of the block, not on the
    unrelated hole ("Face of Extrude 1"); 10 x 10, Height 5, Join. Q: the box's top
    pulled up 5. Extrude 1 edited to 20: the hole, the box and the pull ride up with the
    top. Cylinder 1 deleted in the timeline: the box stays where it is, no error. Ctrl+Z,
    Ctrl+Y. Create Sketch on the pulled top, a circle r3, E 4. Box 1 edited to Height 8:
    the pull and the boss on it follow. Ctrl+Z. Box 1 edited again, its Plane box clicked,
    the block's top clicked (the box made that face smaller): taken, nothing moves; Esc.
P6. Problems said in the dialog, never in the Report view: a Box away from the part
    (New Body by itself) switched to Cut (it touches nothing: said, OK waits), Join (Fusion
    makes it a body of its own, no message), Intersect (nothing in common: said, OK
    waits); New Body: fine; Esc leaves nothing. A Box round the whole part switched to
    Cut: it would take everything, said, OK waits; Esc.
P7. Picks in the wrong order: Box, an edge of the part clicked (not a plane; the XY
    square lies behind it): said, still waiting; the side of the boss (curved): said;
    then the block's top: placing. Esc.

Hand-derived volumes (pi = PI): block 12000, hole r3 h10 = 90 pi, box 10 x 10 x 5 = 500,
pull +500; block at 20: 24000; boss r3 h4 = 36 pi; box height 8 + pull 5 = 1300.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
s = {}


def doc():
    return App.ActiveDocument


def near(a, b_, tol=1e-6):
    return pi.near(a, b_, tol)


def vol():
    return pi.total_volume()


def msg(p):
    return p.message.text() if p is not None else ""


def step(fn, name):
    fn.__name__ = name
    return fn


def presspull():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def top_z():
    return pi.bbox(h.body().Shape)[5]


# == P5: a part made of several features ================================================
def p5_select_top():
    h.click(V(10, 10, 10))


def p5_cylinder():
    h.check("P5 the top face is selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Cylinder")


def p5_centre():
    p = pi.panel("CylinderPanel")
    h.check("P5 the face is taken", p is not None and p.state == "place", p and p.state)
    h.click(V(10, 10, 10))


def p5_circle():
    h.click(V(13, 10, 10))


p5_circle.wait_ms = 1500


def p5_depth():
    p = pi.panel("CylinderPanel")
    if p is not None:
        ui.type_into(p.height.widget, "-10")


p5_depth.wait_ms = 1500


def p5_hole():
    p = pi.panel("CylinderPanel")
    h.check(
        "P5 a hole: Cut by itself",
        p is not None and p.operation.currentText() == "Cut",
        p and p.operation.currentText(),
    )
    h.check("P5 block minus the hole", near(vol(), 12000.0 - 90.0 * PI), vol())
    h.task_button("OK")


def p5_select_top_again():
    h.check("P5 the hole is kept", pi.no_dialog())
    h.click(V(30, 20, 10))


def p5_box():
    pi.menu("Box")


def p5_box_face():
    p = pi.panel("BoxPanel")
    h.check("P5 the face is taken", p is not None and p.state == "place", p and p.state)
    text = p.plane_field.button.text() if p is not None else ""
    h.check("P5 on the block's face, not the hole's", text == "Face of Extrude 1", text)
    h.click(V(25, 15, 10))


def p5_box_c2():
    h.click(V(35, 25, 10))


p5_box_c2.wait_ms = 1500


def p5_box_height():
    p = pi.panel("BoxPanel")
    if p is not None:
        ui.type_into(p.height.widget, "5")


p5_box_height.wait_ms = 1500


def p5_box_ok():
    p = pi.panel("BoxPanel")
    h.check(
        "P5 the box joins the block",
        p is not None and p.operation.currentText() == "Join",
        p and p.operation.currentText(),
    )
    h.check("P5 + 10 x 10 x 5", near(vol(), 12500.0 - 90.0 * PI), vol())
    if p is not None and p.target is not None:
        support = p.target.AttachmentSupport
        s["support"] = support[0][0].Name if support else None
    h.task_button("OK")


def p5_box_kept():
    h.check("P5 the box is kept", pi.no_dialog())
    pad = ti.obj("Extrude 1")
    h.check(
        "P5 the box hangs on Extrude 1's face",
        pad is not None and s.get("support") == pad.Name,
        (s.get("support"), pad and pad.Name),
    )
    h.press("q")


def p5_pull_face():
    h.click(V(30, 20, 15))


def p5_pull_distance():
    p = presspull()
    h.check("P5 Press Pull open", p is not None)
    if p is not None:
        ui.type_into(p.field.widget, "5")


p5_pull_distance.wait_ms = 1500


def p5_pull_ok():
    h.check("P5 pulled 5", near(vol(), 13000.0 - 90.0 * PI), vol())
    h.task_button("OK")


def p5_edit_block():
    h.check("P5 Press Pull kept", pi.no_dialog())
    h.check("P5 double-click Extrude 1", ti.double_click("Extrude 1"), ti.titles())


def p5_block_20():
    p = extrude_panel()
    h.check("P5 editing Extrude 1", p is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "20")


p5_block_20.wait_ms = 1500


def p5_block_ok():
    h.task_button("OK")


p5_block_ok.wait_ms = 1500


def p5_rode_up():
    h.check("P5 the edit closed", pi.no_dialog())
    h.check("P5 the hole, the box and the pull rode up", near(vol(), 25000.0 - 90.0 * PI), vol())
    h.check("P5 the pulled top at 30", near(top_z(), 30.0, 1e-3), top_z())
    ti.menu("Cylinder 1", "Delete")


p5_rode_up.wait_ms = 1500


def p5_deleted():
    h.check("P5 the hole is gone, the box stays", near(vol(), 25000.0), vol())
    h.check("P5 the pulled top still at 30", near(top_z(), 30.0, 1e-3), top_z())
    h.check(
        "P5 timeline",
        ti.titles()[-3:] == ["Extrude 1", "Box 1", "Press Pull 1"]
        or "Cylinder 1" not in ti.titles(),
        ti.titles(),
    )
    h.press("z", QtCore.Qt.ControlModifier)


p5_deleted.wait_ms = 1500


def p5_undone():
    h.check("P5 Ctrl+Z: the hole is back", near(vol(), 25000.0 - 90.0 * PI), vol())
    h.press("y", QtCore.Qt.ControlModifier)


p5_undone.wait_ms = 1500


def p5_redone():
    h.check("P5 Ctrl+Y: deleted again", near(vol(), 25000.0), vol())
    h.fit()


def p5_boss_circle(sk):
    x, y = h.to_sketch(sk, V(30, 20, 30))
    h.draw_circle(sk, x, y, 3)


def p5_boss_e():
    h.press("e")


def p5_boss_distance():
    p = extrude_panel()
    h.check("P5 Extrude open for the boss", p is not None)
    if p is not None:
        ui.type_into(p.distance.widget, "4")


p5_boss_distance.wait_ms = 1500


def p5_boss_ok():
    h.task_button("OK")


p5_boss_ok.wait_ms = 1500


def p5_boss_done():
    h.check("P5 the boss on the pulled top", near(vol(), 25000.0 + 36.0 * PI), vol())
    h.check("P5 its top at 34", near(top_z(), 34.0, 1e-3), top_z())
    h.check("P5 double-click Box 1", ti.double_click("Box 1"), ti.titles())


def p5_box_8():
    p = pi.panel("BoxPanel")
    h.check("P5 editing Box 1", p is not None and p.editing)
    if p is not None:
        h.check("P5 it shows Height 5", near(p.height.value(), 5.0), p.height.value())
        ui.type_into(p.height.widget, "8")


p5_box_8.wait_ms = 1500


def p5_box_8_ok():
    h.task_button("OK")


p5_box_8_ok.wait_ms = 1500


def p5_followed():
    h.check("P5 the edit closed", pi.no_dialog())
    h.check(
        "P5 the pull and the boss follow the taller box",
        near(vol(), 24000.0 + 1300.0 + 36.0 * PI),
        vol(),
    )
    h.check("P5 the boss's top at 37", near(top_z(), 37.0, 1e-3), top_z())
    h.shot("p5")
    h.press("z", QtCore.Qt.ControlModifier)


p5_followed.wait_ms = 1500


def p5_back():
    h.check("P5 Ctrl+Z: Height 5 again", near(vol(), 25000.0 + 36.0 * PI), vol())
    h.check("P5 top at 34 again", near(top_z(), 34.0, 1e-3), top_z())
    s["vol"] = vol()
    h.fit()


def p5_replane():
    h.check("P5 double-click Box 1 once more", ti.double_click("Box 1"), ti.titles())


def p5_plane_box():
    p = pi.panel("BoxPanel")
    h.check("P5 editing Box 1 again", p is not None and p.editing)
    if p is not None:
        ui.click(p.plane_field.button)


p5_plane_box.wait_ms = 1500


def p5_click_block_top():
    p = pi.panel("BoxPanel")
    h.check(
        "P5 the Plane box waits for a pick", p is not None and p.state == "replane", p and p.state
    )
    h.click(V(5, 5, 20))  # the block's top, which the box itself made smaller


def p5_replaned():
    p = pi.panel("BoxPanel")
    h.check("P5 the block's top is taken", p is not None and p.state == "ready", p and p.state)
    h.check("P5 no message", msg(p) == "", msg(p))
    text = p.plane_field.button.text() if p is not None else ""
    h.check("P5 on Extrude 1's face", text == "Face of Extrude 1", text)
    h.check("P5 the part unchanged", near(vol(), s["vol"]), vol())
    h.press(QtCore.Qt.Key_Escape)


p5_replaned.wait_ms = 1500


def p5_replane_esc():
    h.check("P5 Esc closed it", pi.no_dialog())
    h.check("P5 the part as it was", near(vol(), s["vol"]), vol())


# == P6: problems said in the dialog ======================================================
def p6_box():
    h.click_empty()
    pi.menu("Box")


def p6_plane():
    h.click(V(40, -30, 0))


def p6_c1():
    p = pi.panel("BoxPanel")
    h.check("P6 placing on XY", p is not None and p.state == "place", p and p.state)
    h.click(V(45, -35, 0))


def p6_c2():
    h.click(V(55, -25, 0))


p6_c2.wait_ms = 1500


def p6_cut():
    p = pi.panel("BoxPanel")
    h.check(
        "P6 away from the part: New Body",
        p is not None and p.operation.currentText() == "New Body",
        p and p.operation.currentText(),
    )
    if p is not None:
        ui.choose(p.operation, "Cut")


p6_cut.wait_ms = 1500


def p6_cut_said():
    p = pi.panel("BoxPanel")
    h.check("P6 a Cut that touches nothing is said", "does not touch" in msg(p), msg(p))
    h.check("P6 the part unchanged", near(vol(), s["vol"]), vol())
    h.task_button("OK")


def p6_cut_waits():
    p = pi.panel("BoxPanel")
    h.check("P6 OK waits", p is not None)
    if p is not None:
        ui.choose(p.operation, "Join")


p6_cut_waits.wait_ms = 1500


def p6_join_said():
    p = pi.panel("BoxPanel")
    # Fusion: a Join that touches no body makes a new body (never a separate piece).
    h.check("P6 a Join away from the part: no message", msg(p) == "", msg(p))
    h.check("P6 it is a body of its own", len(pi.bodies()) == 2, [o.Name for o in pi.bodies()])
    h.check("P6 the box joins nothing: 1000 more", near(vol(), s["vol"] + 1000.0), vol())


def p6_join_waits():
    p = pi.panel("BoxPanel")
    h.check("P6 the dialog is still open", p is not None)
    if p is not None:
        ui.choose(p.operation, "Intersect")


p6_join_waits.wait_ms = 1500


def p6_intersect_said():
    p = pi.panel("BoxPanel")
    h.check(
        "P6 an Intersect with nothing in common is said",
        "overlap" in msg(p) or "nothing" in msg(p).lower(),
        msg(p),
    )
    h.task_button("OK")


def p6_intersect_waits():
    p = pi.panel("BoxPanel")
    h.check("P6 OK waits", p is not None)
    if p is not None:
        ui.choose(p.operation, "New Body")


p6_intersect_waits.wait_ms = 1500


def p6_new_body():
    p = pi.panel("BoxPanel")
    h.check("P6 New Body: no message", msg(p) == "", msg(p))
    h.check("P6 a new body of 1000", near(vol(), s["vol"] + 1000.0), vol())
    h.press(QtCore.Qt.Key_Escape)


p6_new_body.wait_ms = 1200


def p6_esc():
    h.check("P6 Esc closed it", pi.no_dialog())
    h.check("P6 nothing left", near(vol(), s["vol"]), vol())
    h.check("P6 one body", len(pi.bodies()) == 1, [o.Name for o in pi.bodies()])
    pi.menu("Box")


def p6_all_plane():
    h.click(V(40, -30, 0))


def p6_all_c1():
    h.click(V(-10, -10, 0))


def p6_all_c2():
    h.click(V(50, 40, 0))


p6_all_c2.wait_ms = 1500


def p6_all_cut():
    p = pi.panel("BoxPanel")
    h.check("P6 a box round the part", p is not None and p.target is not None)
    if p is not None:
        ui.choose(p.operation, "Cut")


p6_all_cut.wait_ms = 1500


def p6_all_said():
    p = pi.panel("BoxPanel")
    h.check("P6 a Cut taking everything is said", "whole body" in msg(p), msg(p))
    h.task_button("OK")


def p6_all_waits():
    h.check("P6 OK waits", pi.panel("BoxPanel") is not None)
    h.press(QtCore.Qt.Key_Escape)


p6_all_waits.wait_ms = 1200


def p6_all_esc():
    h.check("P6 Esc closed it", pi.no_dialog())
    h.check("P6 the part as it was", near(vol(), s["vol"]), vol())
    h.check("P6 no pop-up", not h.popups(), h.popups())


# == P7: picks in the wrong order ===========================================================
def p7_box():
    h.click_empty()
    pi.menu("Box")


def p7_edge():
    h.click_edge(V(40, 10, 20))  # the block's top right edge (the XY square behind it)


def p7_edge_said():
    p = pi.panel("BoxPanel")
    h.check(
        "P7 an edge is no plane: still waiting", p is not None and p.state == "plane", p and p.state
    )
    h.check("P7 said in the dialog", "flat face or a plane" in msg(p), msg(p))
    h.click(V(30, 17, 32))  # the boss's side (a curved face)


def p7_curved_said():
    p = pi.panel("BoxPanel")
    h.check("P7 a curved face: still waiting", p is not None and p.state == "plane", p and p.state)
    h.check("P7 said in the dialog", "flat" in msg(p), msg(p))
    h.click(V(5, 5, 20))  # the block's top


def p7_placing():
    p = pi.panel("BoxPanel")
    h.check("P7 the top is taken", p is not None and p.state == "place", p and p.state)
    h.check("P7 the message went", msg(p) == "", msg(p))
    h.press(QtCore.Qt.Key_Escape)


p7_placing.wait_ms = 1200


def p7_done():
    h.check("P7 Esc closed it", pi.no_dialog())
    h.check("P7 the part as it was", near(vol(), s["vol"]), vol())
    h.shot("p7")


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


h.run(
    "primitives_qa_part",
    b.box_steps("PrimQAPart", height=10)
    + [
        p5_select_top,
        p5_cylinder,
        p5_centre,
        p5_circle,
        p5_depth,
        p5_hole,
        p5_select_top_again,
        p5_box,
        p5_box_face,
        p5_box_c2,
        p5_box_height,
        p5_box_ok,
        p5_box_kept,
        p5_pull_face,
        p5_pull_distance,
        p5_pull_ok,
        p5_edit_block,
        p5_block_20,
        p5_block_ok,
        p5_rode_up,
        p5_deleted,
        p5_undone,
        p5_redone,
    ]
    + sketch_steps("boss", V(30, 20, 30), p5_boss_circle)
    + [
        p5_boss_e,
        p5_boss_distance,
        p5_boss_ok,
        p5_boss_done,
        p5_box_8,
        p5_box_8_ok,
        p5_followed,
        p5_back,
        p5_replane,
        p5_plane_box,
        p5_click_block_top,
        p5_replaned,
        p5_replane_esc,
        p6_box,
        p6_plane,
        p6_c1,
        p6_c2,
        p6_cut,
        p6_cut_said,
        p6_cut_waits,
        p6_join_said,
        p6_join_waits,
        p6_intersect_said,
        p6_intersect_waits,
        p6_new_body,
        p6_esc,
        p6_all_plane,
        p6_all_c1,
        p6_all_c2,
        p6_all_cut,
        p6_all_said,
        p6_all_waits,
        p6_all_esc,
        p7_box,
        p7_edge,
        p7_edge_said,
        p7_curved_said,
        p7_placing,
        p7_done,
    ],
)
