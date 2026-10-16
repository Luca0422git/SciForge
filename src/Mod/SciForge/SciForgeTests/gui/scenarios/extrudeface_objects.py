# SPDX-License-Identifier: LGPL-2.1-or-later
"""A click on a curved face ends the extrude on it with To Object (Fusion's extent for a face
the extrusion cannot end on at one height), Symmetric refuses it with a reason, and a click
on a face of a body in a moved component reaches it, with New Body. Only real input
(parity/extrude-presspull.md), except the component's move (set like Move sets it).

A rod (r 5, along y from -25 to 25, axis at x 30, z 30) over a plate 50 x 40 x 10
(x 10..60, y -20..20), each its own body.

O1  A 6 x 6 square on the plate under the rod (x 27..33, y -3..3). E, Symmetric, click the
    rod: refused ("symmetric ... One Side"), nothing changes. One Side, click the rod:
    Extent To Object with the rod's face (To Selected Face), the dialog says "Ends on the
    curved face (To Object)"; New Body; the column ends on the rod's underside. OK. Undo,
    Redo.
O2  A block 10 x 20 x 22 (x 65..75) made with New Component, the component moved up 5 (its
    top at z 27). The design active again, a 10 x 10 square on the plate (x 45..55, y -5..5),
    E, New Body, click the block's top: Distance 17 (27 - 10), +1700 in a new body. OK.

Hand-derived: rod 25 pi x 50 = 3926.99; plate 20000; column 6 (20 x 6 - int_-3^3
sqrt(25 - u^2) du) = 6 (120 - 28.0875277) = 551.474834; block 4400; O2 1700.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import extrudeface_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
s = {}
ROD = 25.0 * math.pi * 50.0
PLATE = 20000.0
COLUMN = 6.0 * (120.0 - 28.0875277)
BLOCK = 4400.0
ROD_POINT = V(30 + 5 * math.cos(math.radians(45)), 15, 30 + 5 * math.sin(math.radians(45)))
XY_CLICK = V(-10, -25, 0)


def near(a, b, tol=1e-5):
    return x.near(a, b, tol)


# -- the rod and the plate ---------------------------------------------------------------------
def rod_sketch():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ExtrudeFaceObjects")
    s["doc"] = App.ActiveDocument.Label
    h.fit()
    h.ribbon("Create Sketch")


def rod_plane():
    pl.click_square("XZ_Plane")  # where the square shows (was 12, 0, 8)


def rod_circle():
    sk = h.in_sketch()
    h.check("rod: sketch open on XZ", sk is not None and "XZ" in sk.AttachmentSupport[0][0].Name)
    if sk is not None:
        cx, cy = h.to_sketch(sk, V(30, 0, 30))
        h.draw_circle(sk, cx, cy, 5)


def rod_finish():
    h.ribbon("Finish Sketch")


def rod_symmetric():
    p = x.panel()
    if h.check("rod: the circle is picked", p is not None and len(p.profiles) == 1):
        h.check("rod: Symmetric", ui.choose(p.direction, "Symmetric"))
        ui.type_into(p.distance.widget, "25")


def rod_ok():
    h.task_button("OK")


def rod_made():
    h.check("rod: volume", near(x.union_volume(), ROD), x.union_volume())
    h.fit()


def plate_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def plate_plane():
    h.click(XY_CLICK)


def plate_draw():
    sk = h.in_sketch()
    h.check("plate: sketch open on XY", sk is not None and "XY" in sk.AttachmentSupport[0][0].Name)
    if sk is not None:
        h.draw_rectangle(sk, 10, -20, 60, 20)


def plate_distance():
    p = x.panel()
    if h.check("plate: Extrude open", p is not None):
        ui.type_into(p.distance.widget, "10")


def plate_made():
    h.check("plate: volume", near(x.union_volume(), ROD + PLATE), x.union_volume())
    h.fit()


# -- O1: the rod's curved face ------------------------------------------------------------------
def o1_e():
    h.click_empty()
    h.fit()
    h.press("e")


def o1_symmetric():
    p = x.panel()
    if not h.check("O1 Extrude open", p is not None):
        return
    if not p.profiles:
        h.click(V(30, 0, 10))  # the square under the rod, if it was not taken by itself
    h.check("O1 Symmetric", ui.choose(p.direction, "Symmetric"))


def o1_click_rod_symmetric():
    p = x.panel()
    h.check(
        "O1 the square is the profile", p is not None and len(p.profiles) == 1, p and p.profiles
    )
    h.fit()
    h.click(ROD_POINT)


def o1_refused():
    p = x.panel()
    if p is None:
        return
    h.check(
        "O1 Symmetric cannot end on the curved face: says why",
        "symmetric" in p.message.text() and "One Side" in p.message.text(),
        p.message.text(),
    )
    h.check(
        "O1 nothing changes",
        p.extent.currentData() == "distance" and p.distance.value() == 0.0,
        (p.extent.currentText(), p.distance.value()),
    )
    h.check("O1 One Side", ui.choose(p.direction, "One Side"))


def o1_click_rod():
    h.fit()
    h.click(ROD_POINT)


def o1_to_object():
    p = x.panel()
    if p is None:
        return
    h.check("O1 Extent To Object", p.extent.currentData() == "to_object", p.extent.currentText())
    ref = p.options.get("extent_object")
    h.check(
        "O1 the rod's face is the object",
        ref is not None
        and ref[1].startswith("Face")
        and ref[0].Shape.getElement(ref[1]).Surface.TypeId == "Part::GeomCylinder",
        ref and (ref[0].Name, ref[1]),
    )
    h.check(
        "O1 the dialog says so",
        p.info.text() == "Ends on the curved face (To Object)",
        p.info.text(),
    )
    h.check(
        "O1 Extend: To Selected Face",
        p.extend.isVisible() and p.extend.currentText() == "To Selected Face",
        p.extend.currentText(),
    )
    h.check("O1 New Body", ui.choose(p.operation, "New Body"))


def o1_built():
    p = x.panel()
    want = ROD + PLATE + COLUMN
    h.check(
        "O1 the column ends on the rod's underside",
        near(x.union_volume(), want),
        (x.union_volume(), want, p and p.message.text()),
    )
    h.shot("O1-to-the-rod")
    h.task_button("OK")


def o1_done():
    h.check("O1 closed", x.panel() is None and not Gui.Control.activeDialog())
    h.check("O1 kept", near(x.union_volume(), ROD + PLATE + COLUMN), x.union_volume())
    h.check("O1 three bodies", len(x.bodies()) == 3, [b.Label for b in x.bodies()])
    h.check("Undo button", ui.quick_access("Undo"))


def o1_undone():
    h.check("O1 Undo takes the column away", near(x.union_volume(), ROD + PLATE), x.union_volume())
    h.check("Redo button", ui.quick_access("Redo"))


def o1_redone():
    h.check(
        "O1 Redo brings it back", near(x.union_volume(), ROD + PLATE + COLUMN), x.union_volume()
    )
    h.fit()


# -- O2: a block in a moved component, New Body -------------------------------------------------
def block_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def block_plane():
    pl.click_square("XY_Plane")  # where the square shows (was -8, -8, 0)


def block_draw():
    sk = h.in_sketch()
    h.check("block: sketch open on XY", sk is not None and "XY" in sk.AttachmentSupport[0][0].Name)
    if sk is not None:
        h.draw_rectangle(sk, 65, -10, 75, 10)


def block_finish():
    h.ribbon("Finish Sketch")


def block_options():
    p = x.panel()
    if not h.check("block: Extrude open", p is not None):
        return
    h.check("block: the rectangle is picked", len(p.profiles) == 1, p.profiles)
    h.check("block: New Component", ui.choose(p.operation, "New Component"))
    ui.type_into(p.distance.widget, "22")


def block_made():
    part = cs.component("Component1")
    h.check("block: Component1", part is not None, [c.Label for c in cs.components()])
    if part is not None:
        # Moved up 5, as Move moves a component (its placement).
        part.Placement = App.Placement(V(0, 0, 5), App.Rotation())
        App.ActiveDocument.recompute()
    want = ROD + PLATE + COLUMN + BLOCK
    h.check("block: volume", near(x.union_volume(), want), (x.union_volume(), want))
    cs.click_radio(s["doc"])  # the design active again


def o2_sketch():
    h.check("O2 the design is active", cs.active_label() is None, cs.active_label())
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def o2_face():
    h.click(V(15, -15, 10))  # the plate's top


def o2_draw():
    sk = h.in_sketch()
    h.check("O2 sketch open", sk is not None)
    if sk is not None:
        a = h.to_sketch(sk, V(45, -5, 10))
        b = h.to_sketch(sk, V(55, 5, 10))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def o2_finish():
    h.ribbon("Finish Sketch")


def o2_new_body():
    p = x.panel()
    if not h.check("O2 Extrude open", p is not None):
        return
    if not p.profiles:
        h.fit()
        h.click(V(50, 0, 10))
    h.check("O2 New Body", ui.choose(p.operation, "New Body"))


def o2_click_block():
    p = x.panel()
    h.check(
        "O2 the square is the profile", p is not None and len(p.profiles) == 1, p and p.profiles
    )
    s["bodies"] = len(x.bodies())
    h.fit()
    h.click(V(70, 0, 27))


def o2_reached():
    p = x.panel()
    if p is None:
        return
    h.check(
        "O2 Distance 17 (to z 27, the moved component's top)",
        near(p.distance.value(), 17.0, 1e-9),
        p.distance.value(),
    )
    h.check("O2 says so", p.info.text() == "Up to the face: 17 mm", p.info.text())
    h.check("O2 still New Body", p.operation.currentData() == "new_body", p.operation.currentText())
    want = ROD + PLATE + COLUMN + BLOCK + 1700.0
    h.check("O2 +1700", near(x.union_volume(), want), (x.union_volume(), want))
    h.task_button("OK")


def o2_done():
    h.check(
        "O2 a new body", len(x.bodies()) == s.get("bodies", 0) + 1, [b.Label for b in x.bodies()]
    )
    from sciforge import bodies as sb

    newest = x.bodies()[-1]
    top = sb.global_shape(newest).BoundBox.ZMax if not newest.Shape.isNull() else None
    h.check(
        "O2 the new body ends at the block's top (z 27)", top is not None and near(top, 27.0), top
    )
    h.check("O2 no snap mark left", not x.snap_marks(), len(x.snap_marks()))
    h.shot("O2-end")


h.run(
    "extrudeface_objects",
    [
        rod_sketch,
        rod_plane,
        rod_circle,
        rod_finish,
        x.press_e("rod_e"),
        rod_symmetric,
        rod_ok,
        rod_made,
        plate_sketch,
        plate_plane,
        plate_draw,
        x.named("plate_finish", rod_finish),
        x.press_e("plate_e"),
        plate_distance,
        x.named("plate_ok", rod_ok),
        plate_made,
        *x.face_sketch("o1", V(50, 15, 10), (27, -3, 33, 3)),
        o1_e,
        o1_symmetric,
        o1_click_rod_symmetric,
        o1_refused,
        o1_click_rod,
        o1_to_object,
        o1_built,
        o1_done,
        o1_undone,
        o1_redone,
        block_sketch,
        block_plane,
        block_draw,
        block_finish,
        x.press_e("block_e"),
        block_options,
        x.named("block_ok", rod_ok),
        block_made,
        o2_sketch,
        o2_face,
        o2_draw,
        o2_finish,
        x.press_e("o2_e"),
        o2_new_body,
        o2_click_block,
        o2_reached,
        o2_done,
    ],
)
