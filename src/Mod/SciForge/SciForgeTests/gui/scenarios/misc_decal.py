# SPDX-License-Identifier: LGPL-2.1-or-later
"""Decal (INSERT > Decal), only real input (docs/sciforge/parity/misc.md).

Bodies: a box 40 x 30 x 10 (extruded, its height the user parameter tall = 10) and a
cylinder r 10, 40 high at x 100. Picture: canvas.png, 80 x 40 pixels.

P1 INSERT > Decal with the picture: the dialog waits for a face; nothing made yet.
P2 Click the box's top face: a decal on the flat face, 24 x 12 mm (80 % of the face's smaller
   side), centred where clicked, drawn with the picture, in the browser's Decals folder and the
   timeline.
P3 Opacity 60 (see-through), X Distance 5 (moves 5 mm), Horizontal Flip (mirrored), Scale
   Plane XY 1.5 (36 x 18).
P4 The handles: dragging the X arrow moves it further, the curved handle turns it, the edge
   arrow scales it.
P5 OK; Ctrl+Z: no decal; Ctrl+Y: back and drawn.
P6 Double-click it in the timeline (Edit Decal): its values; Opacity 20, Cancel: still 60.
P7 INSERT > Decal, a click on the cylinder's side: a decal wrapped round the cylinder (every
   point 10 mm from the axis), its picture as wide along the surface as it is on paper.
P8 The box made taller (tall = 20): the decal is on the new top (z 20).
P9 Saved, closed, opened again: both decals there and drawn.
P10 Esc on a new decal: nothing left. Decal in a design without a body: refused with the reason.
P11 Delete on the browser row: gone; Ctrl+Z: back.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as t

V = App.Vector
TOP = V(20, 15, 10)
s = {}


def doc():
    return App.ActiveDocument


def decals():
    from sciforge import decal

    return decal.decals(doc()) if doc() is not None else []


def panel():
    from sciforge import decal_ui, taskui

    current = taskui.current()
    return current if isinstance(current, decal_ui.DecalPanel) else None


def size(obj):
    return (round(obj.BaseWidth * obj.ScaleX, 3), round(obj.BaseHeight * obj.ScaleY, 3))


def drawn(obj):
    try:
        return obj.ViewObject.Proxy.drawn()
    except Exception:
        return (0, 0, False)


def area(obj):
    from sciforge import decal

    return decal.covered_area(obj)


def first_flat():
    found = [d for d in decals() if d.Surface == "Plane"]
    return found[0] if found else None


def setup():
    from sciforge import commands, extrude, parameters, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("Decals")
    parameters.add_user(d, "tall", "mm", "10")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.setExpression("Length", "Parameters.tall")
    body.Tip = pad
    cyl_body = d.addObject("PartDesign::Body", "Body001")
    cyl = d.addObject("PartDesign::AdditiveCylinder", "Cylinder")
    cyl_body.addObject(cyl)
    cyl.Radius, cyl.Height = 10, 40
    cyl.Placement.Base = V(100, 0, 0)
    d.recompute()
    del extrude
    s["box"], s["cyl"] = body.Name, cyl_body.Name
    from sciforge import decal_ui

    decal_ui.FILE_PICKER = lambda kind: i.fixture("canvas.png")
    h.fit()


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    si.menu_item("INSERT", "Decal")


p1_open.wait_ms = 1500


def p1_waits():
    p = panel()
    h.check(
        "P1 the Decal dialog waits for a face",
        p is not None and "Click a face" in p.face_label.text(),
        p and p.face_label.text(),
    )
    h.check("P1 no decal yet", decals() == [])


# -- P2 ----------------------------------------------------------------------------------------
def p2_click():
    h.click(TOP)


p2_click.wait_ms = 1500


def p2_check():
    obj = first_flat()
    h.check("P2 a decal on the flat face", obj is not None, decals())
    if obj is None:
        return
    h.check("P2 24 x 12 mm", size(obj) == (24.0, 12.0), size(obj))
    h.check("P2 centred where clicked", (obj.Anchor.Base - TOP).Length < 0.5, obj.Anchor.Base)
    h.check("P2 it covers 288 mm²", m.near(area(obj), 288.0, 0.5), area(obj))
    points, tris, picture = drawn(obj)
    h.check(
        "P2 drawn with the picture", points > 0 and tris > 0 and picture, (points, tris, picture)
    )
    h.check("P2 just above the face", all(abs(p.z - 10) < 0.05 for p in obj.MeshPoints))
    h.check(
        "P2 the browser's Decals folder",
        "Decals" in t.labels() and obj.Label in t.labels(),
        t.labels(),
    )
    h.check("P2 a step in the timeline", m.timeline_title(obj) is not None, t.titles())
    p = panel()
    h.check("P2 the dialog names the face", p is not None and "Face" in p.face_label.text())
    h.check("P2 four handles", p is not None and len(p.handles) == 4, p and len(p.handles))
    h.shot("2-flat")


# -- P3 ----------------------------------------------------------------------------------------
def p3_values():
    p = panel()
    if p is None:
        return
    i.set_spin(p.opacity, 60)
    i.type_value(p.dx, "5")
    m.set_check(p.flip_h, True)
    i.set_spin(p.scale_xy, 1.5)


p3_values.wait_ms = 1200


def p3_check():
    obj = first_flat()
    h.check(
        "P3 60 % opaque: see-through",
        obj.Opacity == 60
        and m.near(obj.ViewObject.Proxy.material.transparency.getValues()[0], 0.4, 0.01),
    )
    h.check("P3 moved 5 mm", m.near(obj.XDistance, 5.0))
    h.check("P3 36 x 18", size(obj) == (36.0, 18.0), size(obj))
    left = obj.Anchor.Base.x + 5.0 - 18.0  # the click lands on a pixel near x 20
    h.check(
        "P3 it covers (40 - left) x 18 mm² (cut at the face's edge)",
        m.near(area(obj), (40.0 - left) * 18.0, 1.0),
        (area(obj), left),
    )
    h.check("P3 mirrored", obj.FlipHorizontal)
    xs = [p.x for p in obj.MeshPoints]
    h.check(
        "P3 from about x 7 to 43, cut at the face's edge (40)",
        m.near(min(xs), left, 0.05) and m.near(max(xs), 40.0, 0.05),
        (min(xs), max(xs)),
    )
    # mirrored: the picture's left edge (u 0) is on the right now
    right = [uv.x for p, uv in zip(obj.MeshPoints, obj.MeshUV) if p.x > 39.9]
    h.check(
        "P3 the picture's left side is on the right",
        right and min(right) > 0.0 and max(right) < 0.2,
        right,
    )


# -- P4 ----------------------------------------------------------------------------------------
def p4_drag_x():
    p = panel()
    if p is None or not p.handles:
        h.check("P4 handles shown", False)
        return
    h.fit()
    s["dx"] = first_flat().XDistance
    arrow = p.handle_by["x"]
    start = ai.arrow_point(arrow, 0.6)
    end = start + arrow.direction * 4.0
    h.drag(h.screen_point(start), h.screen_point(end))


p4_drag_x.wait_ms = 1200


def p4_drag_turn():
    obj = first_flat()
    h.check("P4 the X arrow moved it", obj.XDistance > s["dx"] + 1.0, (s["dx"], obj.XDistance))
    p = panel()
    if p is None or not p.handles:
        return
    turn = p.handle_by["angle"]
    now, target = turn.screen_points(30.0)
    h.drag(h.screen_point(now), h.screen_point(target), steps=16)


p4_drag_turn.wait_ms = 1200


def p4_drag_scale():
    obj = first_flat()
    h.check("P4 the curved handle turned it", abs(obj.ZAngle) > 5.0, obj.ZAngle)
    s["width"] = size(obj)[0]
    p = panel()
    if p is None or not p.handles:
        return
    arrow = p.handle_by["scale"]
    start = ai.arrow_point(arrow, 0.6)
    end = start + arrow.direction * 3.0
    h.drag(h.screen_point(start), h.screen_point(end))


p4_drag_scale.wait_ms = 1200


def p4_scaled():
    obj = first_flat()
    h.check("P4 the edge arrow scaled it", size(obj)[0] > s["width"] + 1.0, (s["width"], size(obj)))
    h.check("P4 in proportion", m.near(size(obj)[0] / size(obj)[1], 2.0, 0.01), size(obj))
    h.shot("4-handles")
    h.task_button("OK")


p4_scaled.wait_ms = 1200


# -- P5 ----------------------------------------------------------------------------------------
def p5_undo():
    h.check("P5 OK kept it", len(decals()) == 1 and panel() is None)
    s["angle"] = first_flat().ZAngle
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p5_undo.wait_ms = 1200


def p5_redo():
    h.check("P5 Ctrl+Z: no decal", decals() == [])
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


p5_redo.wait_ms = 1500


def p5_back():
    obj = first_flat()
    h.check("P5 Ctrl+Y: back", obj is not None and m.near(obj.ZAngle, s["angle"]))
    h.check("P5 and drawn", obj is not None and drawn(obj)[2], obj and drawn(obj))


# -- P6 ----------------------------------------------------------------------------------------
def p6_edit():
    t.double_click(m.timeline_title(first_flat()))


p6_edit.wait_ms = 1500


def p6_cancel():
    p = panel()
    h.check("P6 Edit Decal", p is not None and p.title == "Edit Decal", p)
    if p is None:
        return
    h.check("P6 its values", p.opacity.value() == 60, p.opacity.value())
    i.set_spin(p.opacity, 20)
    h.check("P6 20 shown at once", first_flat().Opacity == 20)
    h.task_button("Cancel")


p6_cancel.wait_ms = 1200


def p6_check():
    h.check("P6 Cancel: still 60", first_flat().Opacity == 60, first_flat().Opacity)


# -- P7 ----------------------------------------------------------------------------------------
def p7_open():
    si.menu_item("INSERT", "Decal")


p7_open.wait_ms = 1500


def p7_click():
    h.click(V(100, -10, 20))


p7_click.wait_ms = 1500


def p7_check():
    found = [d for d in decals() if d.Surface == "Cylinder"]
    h.check("P7 a decal on the cylinder", len(found) == 1, [(d.Label, d.Surface) for d in decals()])
    if not found:
        return
    obj = found[0]
    radii = [math.hypot(p.x - 100, p.y) for p in obj.MeshPoints]
    h.check(
        "P7 wrapped round it (10 mm from the axis)",
        radii and min(radii) > 9.95 and max(radii) < 10.1,
        (min(radii), max(radii)),
    )
    width, height = size(obj)
    h.check(
        "P7 as wide along the surface as on paper",
        m.near(area(obj), width * height, 0.03 * width * height),
        (area(obj), width * height),
    )
    zs = [p.z for p in obj.MeshPoints]
    h.check(
        "P7 upright: its height along the axis",
        m.near(max(zs) - min(zs), height, 0.05),
        (min(zs), max(zs), height),
    )
    h.shot("7-cylinder")
    h.task_button("OK")


# -- P8 ----------------------------------------------------------------------------------------
def p8_taller():
    d = doc()
    d.getObject("Parameters").tall = 20
    h.press(QtCore.Qt.Key_B, QtCore.Qt.ControlModifier)  # Compute All


p8_taller.wait_ms = 1500


def p8_check():
    obj = first_flat()
    h.check(
        "P8 the decal is on the new top (z 20)",
        obj is not None and all(abs(p.z - 20) < 0.05 for p in obj.MeshPoints),
        obj and obj.Anchor.Base,
    )
    h.check("P8 not red", obj is not None and "Invalid" not in obj.State)


# -- P9 ----------------------------------------------------------------------------------------
def p9_reopen():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-decal-"), "Decals.FCStd")
    doc().saveAs(path)
    s["path"] = path
    m.close_all()
    App.openDocument(path)


p9_reopen.wait_ms = 2500


def p9_check():
    found = decals()
    h.check("P9 both decals back", len(found) == 2, found)
    h.check(
        "P9 drawn with their pictures",
        all(drawn(o)[2] and drawn(o)[1] > 0 for o in found),
        [drawn(o) for o in found],
    )
    h.check(
        "P9 the pictures are inside the design", all(os.path.isfile(o.ImageFile) for o in found)
    )
    h.fit()


# -- P10 ---------------------------------------------------------------------------------------
def p10_escape():
    s["count"] = len(doc().Objects)
    si.menu_item("INSERT", "Decal")


p10_escape.wait_ms = 1500


def p10_click():
    h.click(V(20, 15, 20))


p10_click.wait_ms = 1500


def p10_esc():
    h.check("P10 a third decal while the dialog is open", len(decals()) == 3)
    h.press(QtCore.Qt.Key_Escape)


p10_esc.wait_ms = 1200


def p10_no_body():
    h.check("P10 Esc: nothing left", len(decals()) == 2 and len(doc().Objects) == s["count"])
    s["main"] = doc().Name
    App.newDocument("Empty")
    h.fit()
    si.menu_item("INSERT", "Decal")


p10_no_body.wait_ms = 1500


def p10_refused():
    h.check("P10 no dialog without a body", panel() is None)
    h.check("P10 the reason is said", "no body yet" in m.told(), m.told())
    App.closeDocument(doc().Name)
    App.setActiveDocument(s["main"])
    Gui.setActiveDocument(s["main"])


# -- P11 ---------------------------------------------------------------------------------------
def p11_delete():
    obj = first_flat()
    t.row_menu(obj.Label, "Delete")


p11_delete.wait_ms = 1200


def p11_undo():
    h.check("P11 deleted", first_flat() is None and len(decals()) == 1)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


p11_undo.wait_ms = 1200


def p11_back():
    h.check("P11 Ctrl+Z: back", first_flat() is not None and len(decals()) == 2)


def cleanup():
    from sciforge import decal_ui

    decal_ui.FILE_PICKER = None
    m.close_all()
    h.new_errors()


h.run(
    "misc_decal",
    [
        setup,
        p1_open,
        p1_waits,
        p2_click,
        p2_check,
        p3_values,
        p3_check,
        p4_drag_x,
        p4_drag_turn,
        p4_drag_scale,
        p4_scaled,
        p5_undo,
        p5_redo,
        p5_back,
        p6_edit,
        p6_cancel,
        p6_check,
        p7_open,
        p7_click,
        p7_check,
        p8_taller,
        p8_check,
        p9_reopen,
        p9_check,
        p10_escape,
        p10_click,
        p10_esc,
        p10_no_body,
        p10_refused,
        p11_delete,
        p11_undo,
        p11_back,
        cleanup,
    ],
)
