# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve Type To: as far as a plane, a corner of the part, wrong objects (QA, only real
input).

The part: Create Sketch on XY, R, a 40 x 30 rectangle from the origin, E, OK (10 high).

Path 23, To an origin plane: a 20 x 5 rectangle on XZ standing on the top front edge,
         Revolve about the Z axis (its drawn line), Type To. The preview goes away and the
         Object box waits; OK is refused and says what to click. The YZ square is clicked:
         a quarter turn, towards +Y (onto the block). OK. Edit from the timeline: To and
         "YZ Plane" are shown.
Path 24, To and back: in the edit Type Angle shows 90, 45 is typed, OK. Ctrl+Z gives the
         To revolve back (nothing broken), Ctrl+Y the 45 again, Ctrl+Z once more.
Path 25, To a corner that moves: a 10 x 4 rectangle on XZ at x 25..35 on the top, Revolve
         about Z, Type To, click the back right top corner of the block (40, 30, 10): the
         revolve turns 36.87 degrees. OK. The block's sketch is edited (its 30 becomes 40):
         the revolve follows the corner to 45 degrees.
Path 26, wrong objects while the Object box waits (editing path 25's revolve): a curved
         face, the top face (it does not contain the axis) and the front face (the profile
         is already there) are refused with a reason and change nothing; the YZ square then
         works (90 degrees); Esc keeps the revolve as it was.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
PI = math.pi
BLOCK = 12000.0
Q23 = 500.0 * PI  # quarter of a r20 h5 cylinder
s = {}


def doc():
    return App.ActiveDocument


def panel():
    return ri.panel()


def msg():
    p = panel()
    return p.message.text() if p is not None else ""


def dialog_open():
    return bool(Gui.Control.activeDialog())


def near(a, c, tol=1e-6):
    return ri.near(a, c, tol)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def vol():
    return h.solid_volume()


def invalid():
    return [o.Label for o in doc().Objects if "Invalid" in o.State]


def revolve_titles():
    return [t for t in b.timeline_titles() if t.startswith("Revolve")]


def sector(r1, r2, height, degrees):
    return PI * (r2 * r2 - r1 * r1) * height * degrees / 360.0


def turned(degrees):
    """What path 25's area adds turning `degrees` about Z (it sits on the block's top)."""
    face = s.get("face25")
    if face is None:
        return sector(25, 35, 4, degrees)
    return ri.pappus(face, V(0, 0, 0), V(0, 0, 1), degrees)


def sketch_click(point):
    """Click in a sketch on the XZ plane, the pointer coming in along the plane."""
    si.click(point, approach=V(1.0, 0, 0.6))


def click_vertex(point):
    """Click a corner of the part: like a person aiming until the corner lights up, try the
    pixels around it and click where a vertex is under the mouse."""
    widget = h.gl_widget()
    ratio = widget.devicePixelRatioF()
    centre = h.screen_point(point)
    best = None
    for radius in range(0, 6):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius or best is not None:
                    continue
                qx, qy = centre.x() + dx, centre.y() + dy
                info = h.view().getObjectInfo((qx * ratio, (widget.height() - qy) * ratio))
                if info and str(info.get("Component", "")).startswith("Vertex"):
                    best = QtCore.QPoint(qx, qy)
        if best is not None:
            break
    pos = best or centre
    h.move(pos)
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    return best is not None


def object_box():
    """Click the Object box (it then waits for clicks in the 3D view)."""
    p = panel()
    if p is not None:
        b.click_widget(p.fields["to"].button)


def to_text(p):
    return p.fields["to"].button.text() if p is not None else ""


# == the block =====================================================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveQATo")
    h.fit()
    h.ribbon("Create Sketch")


def block_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def block_rect():
    s["block_sk"] = h.in_sketch()
    h.press("r")


def block_corner():
    si.click(V(0, 0, 0))


def block_size():
    si.move_towards(V(12, 9, 0), V(0.8, 0.6, 0))
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("30")


def block_finish():
    esc()
    h.ribbon("Finish Sketch")


def block_extrude():
    h.fit()
    h.press("e")


def block_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.task_button("OK")


# == Path 23: To an origin plane =====================================================================
def p23_sketch():
    h.check("block 40 x 30 x 10", near(vol(), BLOCK), vol())
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p23_plane():
    pl.click_square("XZ_Plane")  # where the square shows (was -15, 0, 15)


def p23_rect():
    s["sk23"] = h.in_sketch()
    h.check("P23 sketch open", s["sk23"] is not None)
    h.press("r")


def p23_corner():
    sketch_click(V(0, 0, 10))


def p23_size():
    si.move_towards(V(8, 0, 13), V(0.8, 0, 0.6))
    si.type_text("20", enter=False)
    si.tab()
    si.type_text("5")


def p23_finish():
    esc()
    h.ribbon("Finish Sketch")


def p23_revolve():
    areas = ri.regions(s["sk23"])
    h.check("P23 one area", len(areas) == 1, areas)
    if areas:
        box = areas[0][1].BoundBox
        h.check(
            "P23 the rectangle is x 0..20, z 10..15 on XZ",
            [round(v, 6) for v in (box.XMin, box.XMax, box.YMin, box.ZMin, box.ZMax)]
            == [0, 20, 0, 10, 15],
            box,
        )
    h.fit()
    h.click_empty()
    h.ribbon("Revolve")


def p23_axis():
    p = panel()
    h.check("P23 the area is taken", p is not None and len(p.profiles) == 1)
    h.fit()
    h.click(V(0, 0, 40))  # the drawn Z axis, above the part


def p23_type_to():
    p = panel()
    h.check("P23 the Z axis is picked", p is not None and p.axis is not None, p and p.axis)
    if p is None:
        return
    h.check("P23 a full turn first", near(vol(), BLOCK + 4 * Q23), vol())
    b.choose(p.type, "To")


def p23_waits():
    p = panel()
    if p is None:
        h.check("P23 dialog open", False)
        return
    h.check("P23 the Object box is shown", p.fields["to"].widget.isVisible())
    h.check("P23 the Object box waits", p.active == "to", p.active)
    h.check("P23 no angle field for To", not p.angle.widget.isVisible())
    h.check("P23 no angle handle for To", not p.handles, list(p.handles))
    h.check("P23 the preview waits for the object", near(vol(), BLOCK), vol())
    h.check("P23 the dialog says what to click", "object to revolve to" in msg(), msg())
    squares = p.to_planes is not None and p.to_planes.shown
    h.check("P23 origin squares are offered", squares)
    roles = sorted(e[0].Role for e in p.to_planes.planes) if p.to_planes else []
    h.check("P23 only the planes through the axis", roles == ["XZ_Plane", "YZ_Plane"], roles)
    h.shot("p23-to-waits")
    h.task_button("OK")


def p23_ok_refused():
    h.check("P23 OK without the object keeps the dialog", dialog_open() and panel() is not None)
    h.check("P23 it says why", "object to revolve to" in msg(), msg())
    h.check("P23 no pop-up", not h.popups(), h.popups())
    h.fit()
    h.click(V(0, -15, 25))  # the YZ square, in front of the part's left


def p23_plane_picked():
    p = panel()
    if p is None:
        h.check("P23 dialog open", False)
        return
    target = p.options.get("to")
    role = getattr(target[0], "Role", "") if target else ""
    h.check("P23 the YZ plane is the object", role == "YZ_Plane", target)
    h.check("P23 the box names it", to_text(p) == "YZ Plane", to_text(p))
    h.check("P23 a quarter turn onto the block (+Y)", near(vol(), BLOCK + Q23), vol())
    h.check("P23 no warning", "⚠" not in msg(), msg())
    h.shot("p23-to-plane")
    h.task_button("OK")


def p23_done():
    h.check("P23 OK closed the dialog", not dialog_open())
    h.check("P23 kept", near(vol(), BLOCK + Q23), vol())
    h.check("P23 nothing broken", not invalid(), invalid())
    titles = revolve_titles()
    h.check("P23 one revolve in the timeline", len(titles) == 1, b.timeline_titles())
    s["t23"] = titles[-1] if titles else "Revolve 1"
    b.timeline_double_click(s["t23"], click_first=True)


def p23_editing():
    p = panel()
    h.check("P23 editing", p is not None and p.editing)
    if p is None:
        return
    h.check("P23 Type To is shown", p.type.currentText() == "To", p.type.currentText())
    h.check("P23 the object is shown", to_text(p) == "YZ Plane", to_text(p))
    h.check("P23 no warning", "⚠" not in msg(), msg())


# == Path 24: To and back, undo / redo ===============================================================
def p24_angle():
    p = panel()
    if p is not None:
        b.choose(p.type, "Angle")


def p24_type():
    p = panel()
    if p is None:
        h.check("P24 dialog open", False)
        return
    h.check("P24 Angle shows the angle To gave", near(p.angle.value(), 90.0), p.angle.value())
    h.check("P24 the same quarter", near(vol(), BLOCK + Q23), vol())
    h.check("P24 the Object box is hidden", not p.fields["to"].widget.isVisible())
    ui.type_into(p.angle.widget, "45")


def p24_ok():
    h.check("P24 45 degrees", near(vol(), BLOCK + Q23 / 2), vol())
    h.check("P24 no warning", "⚠" not in msg(), msg())
    h.task_button("OK")


def p24_done():
    h.check("P24 kept", not dialog_open() and near(vol(), BLOCK + Q23 / 2), vol())
    h.check("P24 nothing broken", not invalid(), invalid())
    from sciforge import revolve

    rev = ti.obj(s["t23"])
    h.check("P24 the angle no longer follows a plane", rev is not None and not rev.ExpressionEngine)
    h.check("P24 Angle is stored", rev is not None and revolve.read(rev)[2]["type"] == "angle")
    ti.ctrl("z")


def p24_undone():
    h.check("P24 Ctrl+Z: the To revolve again", near(vol(), BLOCK + Q23), vol())
    h.check("P24 nothing broken", not invalid(), invalid())
    ti.ctrl("y")


def p24_redone():
    h.check("P24 Ctrl+Y: 45 again", near(vol(), BLOCK + Q23 / 2), vol())
    h.check("P24 nothing broken", not invalid(), invalid())
    ti.ctrl("z")


def p24_back():
    h.check("P24 Ctrl+Z: To again", near(vol(), BLOCK + Q23), vol())
    h.check("P24 nothing broken", not invalid(), invalid())
    from sciforge import revolve

    rev = ti.obj(s["t23"])
    h.check("P24 To is stored", rev is not None and revolve.read(rev)[2]["type"] == "to")


# == Path 25: To a corner that moves ================================================================
def p25_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p25_plane():
    pl.click_square("XZ_Plane")  # where the square shows (was -15, 0, 15)


def p25_rect():
    s["sk25"] = h.in_sketch()
    h.check("P25 sketch open", s["sk25"] is not None)
    h.press("r")


def p25_corner():
    # on the block's top front edge: the corner snaps onto it (exactly on the top face; the
    # x the mouse gives is a few thousandths off 25, which the checks allow)
    sketch_click(V(25, 0, 10))


def p25_size():
    si.move_towards(V(30, 0, 13), V(0.8, 0, 0.6))
    si.type_text("10", enter=False)
    si.tab()
    si.type_text("4")


def p25_finish():
    esc()
    h.ribbon("Finish Sketch")


def p25_revolve():
    areas = ri.regions(s["sk25"])
    h.check("P25 one area", len(areas) == 1, areas)
    if areas:
        box = areas[0][1].BoundBox
        got = (box.XMin, box.XLength, box.ZMin, box.ZMax)
        h.check(
            "P25 the rectangle is 10 x 4 at x 25, z 10..14",
            all(abs(a - c) < 0.05 for a, c in zip(got, (25, 10, 10, 14)))
            and abs(box.ZMin - 10) < 1e-9,
            box,
        )
        s["face25"] = areas[0][1]
    s["v25"] = vol()
    h.fit()
    h.click_empty()
    h.ribbon("Revolve")


def p25_axis():
    h.fit()
    h.click(V(0, 0, 40))


def p25_type_to():
    p = panel()
    h.check("P25 the Z axis", p is not None and p.axis is not None, p and p.axis)
    if p is not None:
        b.choose(p.type, "To")


def p25_corner_click():
    p = panel()
    h.check("P25 the Object box waits", p is not None and p.active == "to", p and p.active)
    h.fit()
    s["hit25"] = click_vertex(V(40, 30, 10))


def p25_picked():
    p = panel()
    if p is None:
        h.check("P25 dialog open", False)
        return
    h.check("P25 a corner was under the mouse", s["hit25"], h.state.get("last_click"))
    target = p.options.get("to")
    h.check("P25 the corner is the object", bool(target and target[1].startswith("Vertex")), target)
    h.check("P25 the box names it", to_text(p) == "Corner of Body", to_text(p))
    want = s["v25"] + turned(math.degrees(math.atan2(30, 40)))
    h.check("P25 turned 36.87 degrees, to the corner", near(vol(), want), (vol(), want))
    h.check("P25 no warning", "⚠" not in msg(), msg())
    h.shot("p25-to-corner")
    h.task_button("OK")


def p25_done():
    h.check("P25 kept", not dialog_open())
    h.check("P25 nothing broken", not invalid(), invalid())
    titles = revolve_titles()
    s["t25"] = titles[-1] if titles else "Revolve 2"
    si.browser_double_click(s["block_sk"].Label)


def p25_dimension():
    sk = s["block_sk"]
    h.check("P25 editing the block's sketch", h.in_sketch() is sk)
    index = None
    for i, c in enumerate(sk.Constraints):
        if c.Type in ("Distance", "DistanceX", "DistanceY") and c.Driving and near(c.Value, 30.0):
            index = i
    h.check("P25 the 30 dimension", index is not None, sk.Constraints)
    if index is None:
        return
    point = si.dimension_label(sk, index)
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def p25_type40():
    from sciforge import sketch_mode

    sess = sketch_mode.current()
    h.check("P25 the dimension box", sess is not None and sess.editor is not None)
    si.type_text("40")


def p25_sketch_done():
    h.ribbon("Finish Sketch")


def p25_followed():
    h.check("P25 sketch closed", h.in_sketch() is None)
    want = 16000.0 + Q23 + turned(45.0)
    h.check("P25 the revolve followed the corner to 45 degrees", near(vol(), want), (vol(), want))
    rev = ti.obj(s["t25"])
    angle = rev.Angle.Value if rev is not None else None
    h.check("P25 its angle is 45", angle is not None and near(angle, 45.0), angle)
    h.check("P25 nothing broken", not invalid(), invalid())
    h.shot("p25-followed")
    s["v26"] = vol()


# == Path 26: wrong objects ========================================================================
def p26_edit():
    h.fit()
    b.timeline_double_click(s["t25"], click_first=True)


def p26_box():
    p = panel()
    h.check("P26 editing the corner revolve", p is not None and p.editing)
    if p is None:
        return
    h.check("P26 Type To is shown", p.type.currentText() == "To")
    h.check("P26 the corner is shown", to_text(p) == "Corner of Body", to_text(p))
    object_box()


def p26_curved():
    p = panel()
    h.check("P26 the Object box waits", p is not None and p.active == "to", p and p.active)
    h.fit()
    a = math.radians(20)
    h.click(V(20 * math.cos(a), 20 * math.sin(a), 12.5))  # the round of path 23


def p26_curved_refused():
    p = panel()
    if p is None:
        h.check("P26 dialog open", False)
        return
    h.check(
        "P26 a curved face is refused", "flat face" in msg(), (msg(), h.state.get("last_click"))
    )
    h.check("P26 the corner is kept", to_text(p) == "Corner of Body", to_text(p))
    h.check("P26 unchanged", near(vol(), s["v26"]), vol())
    h.click(V(30, 36, 10))  # the top face of the block


def p26_top_refused():
    p = panel()
    if p is None:
        h.check("P26 dialog open", False)
        return
    h.check("P26 the top face is refused", "contains the axis" in msg(), msg())
    h.check("P26 still waits", p.active == "to", p.active)
    h.check("P26 unchanged", near(vol(), s["v26"]), vol())
    h.click(V(38, 0, 3))  # the front face, where the profile is


def p26_front_refused():
    p = panel()
    if p is None:
        h.check("P26 dialog open", False)
        return
    h.check("P26 the front face is refused", "already" in msg(), msg())
    h.check("P26 unchanged", near(vol(), s["v26"]), vol())
    h.shot("p26-refused")
    h.click(V(0, -15, 25))  # the YZ square


def p26_plane():
    p = panel()
    if p is None:
        h.check("P26 dialog open", False)
        return
    h.check("P26 the YZ plane now", to_text(p) == "YZ Plane", to_text(p))
    want = 16000.0 + Q23 + turned(90.0)
    h.check("P26 a quarter turn", near(vol(), want), (vol(), want))
    h.check("P26 no warning", "⚠" not in msg(), msg())
    esc()


def p26_cancelled():
    h.check("P26 Esc closed the dialog", not dialog_open())
    h.check("P26 Esc kept the corner revolve", near(vol(), s["v26"]), vol())
    h.check("P26 nothing broken", not invalid(), invalid())
    from sciforge import revolve

    rev = ti.obj(s["t25"])
    target = revolve.read(rev)[2].get("to") if rev is not None else None
    h.check("P26 still to the corner", bool(target and target[1].startswith("Vertex")), target)


STEPS = [
    new_design,
    block_plane,
    block_rect,
    block_corner,
    block_size,
    block_finish,
    block_extrude,
    block_ok,
    p23_sketch,
    p23_plane,
    p23_rect,
    p23_corner,
    p23_size,
    p23_finish,
    p23_revolve,
    p23_axis,
    p23_type_to,
    p23_waits,
    p23_ok_refused,
    p23_plane_picked,
    p23_done,
    p23_editing,
    p24_angle,
    p24_type,
    p24_ok,
    p24_done,
    p24_undone,
    p24_redone,
    p24_back,
    p25_sketch,
    p25_plane,
    p25_rect,
    p25_corner,
    p25_size,
    p25_finish,
    p25_revolve,
    p25_axis,
    p25_type_to,
    p25_corner_click,
    p25_picked,
    p25_done,
    p25_dimension,
    p25_type40,
    p25_sketch_done,
    p25_followed,
    p26_edit,
    p26_box,
    p26_curved,
    p26_curved_refused,
    p26_top_refused,
    p26_front_refused,
    p26_plane,
    p26_cancelled,
]

h.run("revolve_qa_to", ti.watched(STEPS))
