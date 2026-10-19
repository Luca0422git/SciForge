# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thin Extrude (Fusion's Extrude Type "Thin Extrude"), only real input.

Path T1, a 40 x 30 rectangle sketched on the top of a 50 x 40 x 5 plate: E picks it by itself,
         Type Thin Extrude, a wall 10 high: Side 1 (inside the outline) 1 mm by default,
         then 2 mm, Side 2 (outside), Center; Two Sides shows the side-two wall fields;
         OK: one timeline step, joined to the plate.
Path T2, the step edited from the timeline (everything comes back), 3 mm, OK; Ctrl+Z and
         Ctrl+Y.
Path T3, an open L of two sketch lines in front of the plate: E with nothing picked waits, Thin
         Extrude, a click on one line takes both (the L), a second click drops them, a
         third takes them back; 10 high: a New Body (it touches nothing), 1 then 2 mm.
Path T4, Thin Extrude turned off with the L picked: the curves are dropped with a word,
         Esc leaves the design as it was.

Numbers by hand: walls of a 40 x 30 outline, 10 high: Side 1 t inside (40x30 - (40-2t)x
(30-2t)), Side 2 t outside ((40+2t)x(30+2t) - 40x30), Center half each way. The L's
wall on the left of its first line (+X): 20 t + 10 t - t^2.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sweep_loft_steps as sl
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
PLATE = 50.0 * 40.0 * 5.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def bodies():
    return doc().findObjects("PartDesign::Body")


def plate_body():
    return doc().getObject("Body")


def vol(body=None):
    b = body if body is not None else plate_body()
    return b.Shape.Volume if b is not None and not b.Shape.isNull() else 0.0


def dialog_open():
    return bool(Gui.Control.activeDialog())


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def inside(t):
    return (1200.0 - (40 - 2 * t) * (30 - 2 * t)) * 10.0


def outside(t):
    return ((40 + 2 * t) * (30 + 2 * t) - 1200.0) * 10.0


def center(t):
    return ((40 + t) * (30 + t) - (40 - t) * (30 - t)) * 10.0


def l_wall(t):
    return (20 * t + 10 * t - t * t) * 10.0


def step(fn, name, wait_ms=None):
    fn.__name__ = name
    if wait_ms:
        fn.wait_ms = wait_ms
    return fn


# -- the plate -------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ThinExtrude")
    h.fit()


def plate_sketch():
    h.ribbon("Create Sketch")


def plate_pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def plate_draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 50, 40)


def plate_finish():
    h.ribbon("Finish Sketch")


def plate_e():
    h.fit()
    h.press("e")


def plate_distance():
    p = xpanel()
    h.check("the plate's area picked by itself", p is not None and len(p.profiles) == 1)
    arrows.type_distance("5")


def plate_ok():
    h.task_button("OK")


def plate_done():
    h.check("plate 50 x 40 x 5", near(vol(), PLATE), vol())


# -- Path T1: a thin extrude of a closed outline ------------------------------------------------
def t1_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def t1_pick_top():
    h.fit()
    h.click(V(25, 20, 5))


def t1_draw():
    sk = h.in_sketch()
    h.check("T1 sketch open on the plate's top", sk is not None)
    if sk:
        ax, ay = h.to_sketch(sk, V(5, 5, 5))
        bx, by = h.to_sketch(sk, V(45, 35, 5))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        s["rim"] = sk


def t1_finish():
    h.ribbon("Finish Sketch")


def t1_e():
    h.fit()
    h.press("e")


def t1_thin():
    p = xpanel()
    h.check("T1 the outline picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check(
        "T1 Type offers Extrude and Thin Extrude",
        [p.kind.itemText(i) for i in range(p.kind.count())] == ["Extrude", "Thin Extrude"],
    )
    h.check("T1 Wall fields hidden for a plain extrude", not p.wall_thickness.widget.isVisible())
    h.check("T1 choose Type: Thin Extrude", ui.choose(p.kind, "Thin Extrude"))


def t1_fields():
    p = xpanel()
    h.check("T1 Wall Location shown", p.wall_location.isVisible())
    h.check("T1 Wall Thickness shown", p.wall_thickness.widget.isVisible())
    h.check(
        "T1 Wall Location: Side 1, Center, Side 2",
        [p.wall_location.itemText(i) for i in range(p.wall_location.count())]
        == ["Side 1", "Center", "Side 2"],
    )
    h.check("T1 Side 1 by default", p.wall_location.currentText() == "Side 1")
    h.check("T1 1 mm by default", near(p.wall_thickness.value(), 1.0), p.wall_thickness.value())
    h.check("T1 the hint names curves", "curve" in p.profile_hint.text(), p.profile_hint.text())
    arrows.type_distance("10")


def t1_side1():
    p = xpanel()
    h.check("T1 Side 1, 1 mm: the wall inside the outline", near(vol(), PLATE + inside(1)), vol())
    h.check(
        "T1 joined to the plate", p.operation.currentText() == "Join", p.operation.currentText()
    )
    h.check("T1 one solid", len(plate_body().Shape.Solids) == 1)
    h.check("T1 no warning", "⚠" not in p.message.text(), p.message.text())
    h.shot("t1-side1")
    ui.type_into(p.wall_thickness.widget, "2")


def t1_two_mm():
    p = xpanel()
    h.check("T1 2 mm", near(vol(), PLATE + inside(2)), vol())
    h.check("T1 choose Wall Location: Side 2", ui.choose(p.wall_location, "Side 2"))


def t1_side2():
    p = xpanel()
    h.check("T1 Side 2: the wall outside the outline", near(vol(), PLATE + outside(2)), vol())
    h.check(
        "T1 Side 2 still joins the plate", p.operation.currentText() == "Join", p.message.text()
    )
    h.check("T1 choose Wall Location: Center", ui.choose(p.wall_location, "Center"))


def t1_center():
    p = xpanel()
    h.check("T1 Center: half each way", near(vol(), PLATE + center(2)), vol())
    h.check("T1 choose Direction: Two Sides", ui.choose(p.direction, "Two Sides"))


def t1_two_sides():
    p = xpanel()
    h.check("T1 side two has its own Wall Location", p.wall_location2.isVisible())
    h.check("T1 and Wall Thickness", p.wall_thickness2.widget.isVisible())
    h.check("T1 back to One Side", ui.choose(p.direction, "One Side"))


def t1_ok():
    p = xpanel()
    h.check("T1 one side again", p is not None and not p.wall_location2.isVisible())
    h.check("T1 still Center 2 mm", near(vol(), PLATE + center(2)), vol())
    h.task_button("OK")


def t1_done():
    h.check("T1 kept", not dialog_open())
    h.check("T1 one body", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("T1 the wall stays", near(vol(), PLATE + center(2)), vol())
    titles = ui.timeline_titles()
    h.check("T1 one more timeline step: Extrude 2", "Extrude 2" in titles, titles)
    h.check("T1 its sketch hidden", not s["rim"].ViewObject.Visibility)
    h.check("T1 nothing in error", not broken(), broken())
    h.fit()
    h.shot("t1-done")


# -- Path T2: edit from the timeline, undo / redo ---------------------------------------------
def t2_edit():
    h.check("T2 double-click Extrude 2", ui.double_click_timeline("Extrude 2"))


def t2_editing():
    p = xpanel()
    h.check("T2 editing", p is not None and p.editing)
    if p is None:
        return
    h.check("T2 Thin Extrude back", p.kind.currentText() == "Thin Extrude", p.kind.currentText())
    h.check("T2 Center back", p.wall_location.currentText() == "Center")
    h.check("T2 2 mm back", near(p.wall_thickness.value(), 2.0), p.wall_thickness.value())
    h.check("T2 10 back", near(p.distance.value(), 10.0), p.distance.value())
    ui.type_into(p.wall_thickness.widget, "3")


def t2_three():
    h.check("T2 3 mm", near(vol(), PLATE + center(3)), vol())
    h.task_button("OK")


def t2_undo():
    h.check("T2 kept", not dialog_open() and near(vol(), PLATE + center(3)), vol())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def t2_undone():
    h.check("T2 Ctrl+Z: 2 mm again", near(vol(), PLATE + center(2)), vol())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def t2_redone():
    h.check("T2 Ctrl+Y: 3 mm again", near(vol(), PLATE + center(3)), vol())
    h.check("T2 nothing in error", not broken(), broken())


# -- Path T3: an open L -----------------------------------------------------------------------
def t3_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def t3_pick_xy():
    h.fit()
    pl.click_square("XY_Plane")  # where the square shows (was 15, -20, 0)


def t3_draw():
    sk = h.in_sketch()
    h.check("T3 sketch open", sk is not None)
    if sk:
        ax, ay = h.to_sketch(sk, V(5, -25, 0))
        bx, by = h.to_sketch(sk, V(25, -25, 0))
        cx, cy = h.to_sketch(sk, V(25, -15, 0))
        sl.add_lines(sk, [(ax, ay), (bx, by), (cx, cy)])
        s["l"] = sk


def t3_finish():
    h.ribbon("Finish Sketch")


def t3_e():
    h.click_empty()
    h.fit()
    h.press("e")


def t3_waits():
    p = xpanel()
    h.check("T3 Extrude waits (the L has no area)", p is not None and not p.profiles)
    if p is None:
        return
    h.check("T3 choose Thin Extrude", ui.choose(p.kind, "Thin Extrude"))


def t3_click_line():
    h.fit()
    pl.click_on_plane(V(15, -25, 0))


def t3_both_lines():
    p = xpanel()
    names = sorted(sub for obj, sub in p.profiles) if p is not None else []
    h.check("T3 one click takes the whole L (2 curves)", names == ["Edge1", "Edge2"], names)
    h.check("T3 said in words", "2 curves" in p.profile.text(), p.profile.text())
    pl.click_on_plane(V(25, -20, 0))  # the other line: drops the L


def t3_dropped():
    p = xpanel()
    h.check("T3 a click on a picked line drops it", p is not None and not p.profiles, p.profiles)
    pl.click_on_plane(V(10, -25, 0))


def t3_again():
    p = xpanel()
    h.check("T3 picked again", p is not None and len(p.profiles) == 2, p.profiles)
    arrows.type_distance("10")


def t3_wall():
    p = xpanel()
    h.check(
        "T3 a New Body: the L touches nothing",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    new = [b for b in bodies() if b is not plate_body()]
    h.check("T3 the wall is a body of its own", len(new) == 1, [b.Label for b in bodies()])
    if new:
        h.check("T3 1 mm wall on the L's left", near(vol(new[0]), l_wall(1.0)), vol(new[0]))
        box = new[0].Shape.BoundBox
        h.check("T3 inside the L", near(box.YMin, -25.0) and near(box.XMax, 25.0), box)
    h.check("T3 the plate unchanged", near(vol(), PLATE + center(3)), vol())
    h.shot("t3-wall")
    ui.type_into(p.wall_thickness.widget, "2")


def t3_two_mm():
    new = [b for b in bodies() if b is not plate_body()]
    h.check("T3 2 mm", len(new) == 1 and near(vol(new[0]), l_wall(2.0)), [vol(b) for b in new])
    h.task_button("OK")


def t3_done():
    h.check("T3 kept", not dialog_open())
    h.check("T3 two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    titles = ui.timeline_titles()
    h.check("T3 Extrude 3 in the timeline", "Extrude 3" in titles, titles)
    h.check("T3 nothing in error", not broken(), broken())
    s["volumes"] = sorted(vol(b) for b in bodies())


# -- Path T4: Thin off drops the curves; Esc --------------------------------------------------
def t4_edit():
    h.check("T4 double-click Extrude 3", ui.double_click_timeline("Extrude 3"))


def t4_editing():
    p = xpanel()
    h.check("T4 editing the L wall", p is not None and p.editing and len(p.profiles) == 2)
    if p is None:
        return
    h.check("T4 choose Type: Extrude", ui.choose(p.kind, "Extrude"))


def t4_dropped():
    p = xpanel()
    h.check(
        "T4 the curves are dropped", p is not None and not p.profiles, p.profiles if p else None
    )
    h.check("T4 and the dialog says why", "thin extrude only" in p.message.text(), p.message.text())
    h.press(QtCore.Qt.Key_Escape)


def t4_done():
    h.check("T4 Esc closes the edit", not dialog_open())
    h.check(
        "T4 nothing changed",
        sorted(vol(b) for b in bodies()) == s["volumes"],
        (sorted(vol(b) for b in bodies()), s["volumes"]),
    )
    h.check("T4 nothing in error", not broken(), broken())
    h.fit()
    h.shot("t4-end")


h.run(
    "gaps_thin_extrude",
    tl.watched(
        [
            new_design,
            plate_sketch,
            plate_pick_xy,
            plate_draw,
            plate_finish,
            plate_e,
            plate_distance,
            plate_ok,
            plate_done,
            t1_sketch,
            t1_pick_top,
            t1_draw,
            t1_finish,
            t1_e,
            t1_thin,
            t1_fields,
            t1_side1,
            t1_two_mm,
            t1_side2,
            t1_center,
            t1_two_sides,
            t1_ok,
            t1_done,
            t2_edit,
            t2_editing,
            t2_three,
            t2_undo,
            t2_undone,
            t2_redone,
            t3_sketch,
            t3_pick_xy,
            t3_draw,
            t3_finish,
            t3_e,
            t3_waits,
            t3_click_line,
            t3_both_lines,
            t3_dropped,
            t3_again,
            t3_wall,
            t3_two_mm,
            t3_done,
            t4_edit,
            t4_editing,
            t4_dropped,
            t4_done,
        ]
    ),
)
