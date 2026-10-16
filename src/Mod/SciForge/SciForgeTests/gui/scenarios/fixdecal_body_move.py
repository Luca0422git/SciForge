# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal stays stuck to its face when its body is moved with Move/Copy (Luca: "decals dont
follow their faces when moved"), only real input. docs/sciforge/parity/misc.md, Decal.

Bodies: a box 40 x 30 x 10 and a cylinder r 10, 40 high at x 100. Picture: canvas.png.

P1 INSERT > Decal, click the box's top: a flat decal. INSERT > Decal, click the cylinder's
   side: a decal wrapped round it.
P2 M, click the box, X Distance 30, Z Angle 90 (Free Move turns about the box's middle): the
   decal turns and moves with the top face while the dialog is open; OK: the same, not red.
P3 Ctrl+Z: the decal is back where it was; Ctrl+Y: moved again.
P4 Double-click the Move in the timeline, X Distance 50: the decal follows the edited move.
P5 M, click the cylinder, X Distance 60, Z Distance 15 and X Angle 90 (tipped over, out of
   the way): the wrapped decal stays wrapped round the cylinder (10 mm from its new axis),
   the same size.
P6 M, click the box, drag the X arrow: the decal follows the drag live; OK.
P7 M, click the box, Create Copy, Y Distance 60: the copy is a new body without the decal;
   the decal stays on the original, untouched.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h

V = App.Vector
st = {}


def setup():
    st.update(f.box_and_cylinder("DecalBodyMove"))


def p1_check():
    flat, wrapped = f.flat(), f.wrapped()
    h.check("P1 a flat decal and a wrapped one", flat is not None and wrapped is not None)
    if flat is None or wrapped is None:
        return
    st["flat0"] = f.snapshot(flat)
    st["wrap0"] = f.snapshot(wrapped)
    f.drawn_on_face("P1 flat", flat)
    f.drawn_on_face("P1 wrapped", wrapped)
    h.check(
        "P1 the flat decal is in the middle of the top",
        (st["flat0"]["centre"] - f.TOP).Length < 0.5,
        st["flat0"]["centre"],
    )
    h.shot("P1-decals")


def box():
    return App.ActiveDocument.getObject(st["box"])


def cyl():
    return App.ActiveDocument.getObject(st["cyl"])


def moves():
    return s.steps_of_kind("MoveCopy")


def field(p, name):
    return {
        "dx": p.distance_fields[0],
        "dy": p.distance_fields[1],
        "dz": p.distance_fields[2],
        "rx": p.angle_fields[0],
        "ry": p.angle_fields[1],
        "rz": p.angle_fields[2],
    }[name].widget


def open_move(point):
    def press():
        h.click_empty()
        h.fit()
        h.press("m")

    def click():
        p = s.panel()
        h.check("Move/Copy open", p is not None and p.title == "Move/Copy", p)
        h.click(point)

    press.wait_ms = 1200
    click.wait_ms = 1200
    return [press, click]


def movement(of_body):
    from sciforge import move

    found = [m for m in moves() if move.moved_body(m) is of_body and not move.is_copy(m)]
    place = App.Placement()
    for step in found:  # in timeline order: each one moves what the one before gave
        place = step.Movement.multiply(place)
    return place


# -- P2 ----------------------------------------------------------------------------------------
p2_press, p2_click = open_move(f.TOP)
p2_press.__name__, p2_click.__name__ = "p2_press_m", "p2_click_box"


def p2_type():
    p = s.panel()
    if not h.check("P2 the box is picked", p is not None and p.options["bodies"] == [box()]):
        return
    s.type_value(field(p, "dx"), "30")
    s.type_value(field(p, "rz"), "90")


p2_type.wait_ms = 1500


def p2_live():
    from sciforge import move

    p = s.panel()
    place = move.transform(p.options) if p is not None else App.Placement()
    st["p2_place"] = place
    f.follows("P2 while the dialog is open", f.flat(), st["flat0"], place)
    h.shot("P2-live")
    h.task_button("OK")


p2_live.wait_ms = 1200


def p2_ok():
    h.check("P2 one Move step", len(moves()) == 1, moves())
    place = movement(box())
    h.check("P2 the Move is X 30, Z Angle 90", place.isSame(st["p2_place"], 1e-9), place)
    f.follows("P2 after OK", f.flat(), st["flat0"], place)
    f.follows("P2 the cylinder's decal did not move", f.wrapped(), st["wrap0"], App.Placement())


# -- P3 ----------------------------------------------------------------------------------------
def p3_undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p3_undo.wait_ms = 1500


def p3_undone():
    h.check("P3 Ctrl+Z: no Move", not moves(), moves())
    f.follows("P3 Ctrl+Z", f.flat(), st["flat0"], App.Placement())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


p3_undone.wait_ms = 1500


def p3_redone():
    h.check("P3 Ctrl+Y: the Move is back", len(moves()) == 1, moves())
    f.follows("P3 Ctrl+Y", f.flat(), st["flat0"], movement(box()))


# -- P4 ----------------------------------------------------------------------------------------
def p4_edit():
    s.timeline_double_click(moves()[0])


p4_edit.wait_ms = 1500


def p4_type():
    p = s.panel()
    if h.check("P4 the Move's dialog", p is not None and p.editing, p):
        s.type_value(field(p, "dx"), "50")


p4_type.wait_ms = 1500


def p4_ok():
    h.task_button("OK")


p4_ok.wait_ms = 1200


def p4_check():
    place = movement(box())
    h.check("P4 the edited Move is X 50", abs(place.Base.x - st["p2_place"].Base.x - 20) < 1e-6)
    f.follows("P4 after editing the Move", f.flat(), st["flat0"], place)
    h.shot("P4-edited")


# -- P5 ----------------------------------------------------------------------------------------
p5_press, p5_click = open_move(f.SIDE)
p5_press.__name__, p5_click.__name__ = "p5_press_m", "p5_click_cylinder"


def p5_type():
    p = s.panel()
    if not h.check("P5 the cylinder is picked", p is not None and p.options["bodies"] == [cyl()]):
        return
    s.type_value(field(p, "dx"), "60")
    s.type_value(field(p, "dz"), "15")
    s.type_value(field(p, "rx"), "90")


p5_type.wait_ms = 1500


def p5_ok():
    h.task_button("OK")


p5_ok.wait_ms = 1200


def p5_check():
    place = movement(cyl())
    h.check("P5 the cylinder is tipped over", abs(abs(place.Rotation.multVec(V(0, 0, 1)).z)) < 1e-6)
    obj = f.wrapped()
    f.follows("P5 the wrapped decal", obj, st["wrap0"], place)
    axis_point = place.multVec(V(100, 0, 0))
    axis_dir = place.Rotation.multVec(V(0, 0, 1))
    radii = f.radii(obj, axis_point, axis_dir) if obj is not None else []
    h.check(
        "P5 still wrapped round it (10 mm from its new axis)",
        radii and min(radii) > 9.95 and max(radii) < 10.1,
        radii and (min(radii), max(radii)),
    )
    h.shot("P5-cylinder")


# -- P6 ----------------------------------------------------------------------------------------
def p6_press():
    st["before6"] = f.snapshot(f.flat())
    st["place6"] = movement(box())
    h.click_empty()
    h.fit()
    h.press("m")


p6_press.wait_ms = 1200


def p6_click():
    h.click(st["place6"].multVec(f.TOP))


p6_click.wait_ms = 1200


def p6_drag():
    p = s.panel()
    triad = getattr(p, "triad", None)
    if not h.check("P6 the manipulator", triad is not None and p.options["bodies"] == [box()]):
        return
    start = triad.center + V(1, 0, 0) * (0.75 * triad.size)
    h.drag(h.screen_point(start), h.screen_point(start + V(12, 0, 0)))


p6_drag.wait_ms = 1500


def p6_live():
    from sciforge import move

    p = s.panel()
    place = move.transform(p.options) if p is not None else App.Placement()
    h.check("P6 the drag moved the box", p is not None and p.options["dx"] > 3, p and p.options)
    # what the drag actually produced (CI's window differs by a pixel)
    f.follows("P6 during the drag", f.flat(), st["before6"], place)
    h.task_button("OK")


p6_live.wait_ms = 1200


def p6_check():
    f.follows("P6 after OK", f.flat(), st["flat0"], movement(box()))


# -- P7 ----------------------------------------------------------------------------------------
def p7_press():
    st["before7"] = f.snapshot(f.flat())
    st["bodies7"] = len(s.bodies())
    h.click_empty()
    h.fit()
    h.press("m")


p7_press.wait_ms = 1200


def p7_click():
    h.click(movement(box()).multVec(f.TOP))


p7_click.wait_ms = 1200


def p7_copy():
    p = s.panel()
    if not h.check("P7 the box is picked", p is not None and p.options["bodies"] == [box()]):
        return
    s.toggle(p.copy)
    s.type_value(field(p, "dy"), "60")


p7_copy.wait_ms = 1500


def p7_ok():
    h.task_button("OK")


p7_ok.wait_ms = 1500


def p7_check():
    h.check("P7 a copy", len(s.bodies()) == st["bodies7"] + 1, [b.Label for b in s.bodies()])
    h.check("P7 still two decals", len(f.decals()) == 2, f.decals())
    obj = f.flat()
    h.check("P7 the decal is on the original", obj is not None and obj.Body is box())
    f.follows("P7 the original's decal did not move", obj, st["before7"], App.Placement())
    h.shot("P7-copy")


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.new_errors()


h.run(
    "fixdecal_body_move",
    [setup]
    + f.decal_steps("p1_flat", f.TOP)
    + f.decal_steps("p1_wrapped", f.SIDE)
    + [
        p1_check,
        p2_press,
        p2_click,
        p2_type,
        p2_live,
        p2_ok,
        p3_undo,
        p3_undone,
        p3_redone,
        p4_edit,
        p4_type,
        p4_ok,
        p4_check,
        p5_press,
        p5_click,
        p5_type,
        p5_ok,
        p5_check,
        p6_press,
        p6_click,
        p6_drag,
        p6_live,
        p6_check,
        p7_press,
        p7_click,
        p7_copy,
        p7_ok,
        p7_check,
        cleanup,
    ],
)
