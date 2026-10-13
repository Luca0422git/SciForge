# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert Mesh and Convert Mesh (INSERT menu, MESH tab), only real input.

Fixture: box_20x10x5.stl, a 20 x 10 x 5 mm box of 12 triangles (1000 mm3).

A  INSERT > Insert Mesh with the STL: the Insert Mesh dialog; a mesh body "box_20x10x5" in
   the browser's Bodies folder and "Insert Mesh 1" in the timeline; "12 triangles" shown.
B  Unit Type Centimeter: 200 x 100 x 50. Flip Up Direction: 10 up (Y -> Z), -50..0 in Y.
   Millimeter and flip off again: 20 x 10 x 5.
C  Center: placed at (-10, -5, -2.5). Move to Ground: (-10, -5, 0). X Distance 30: (30, -5, 0).
D  The manipulator's Z arrow dragged up: Z Distance grows.
E  OK: the dialog closes, the mesh body stays. Ctrl+Z: gone. Ctrl+Y: back.
F  Timeline double-click "Insert Mesh 1": the dialog again; Unit Type Inch: 508 wide; Cancel:
   20 wide again.
G  MESH tab > Convert Mesh: the dialog waits; click the mesh body: a solid body
   "box_20x10x5 (solid)" of 1000 mm3 with 6 faces (Prismatic); Method Faceted: 12 faces;
   Prismatic again; OK: the mesh body is hidden, the new body active, "Convert Mesh 1".
H  Ctrl+Z: the body is gone and the mesh shown again; Ctrl+Y: back.
"""

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
state = {}


def mesh():
    found = i.mesh_bodies()
    return found[0] if found else None


# -- A ----------------------------------------------------------------------------------------
def a_open():
    i.use_file(i.fixture("box_20x10x5.stl"))
    h.fit()
    h.ribbon("Insert Mesh")


def a_dialog():
    p = i.panel()
    h.check("Insert Mesh dialog", p is not None and p.title == "Insert Mesh", p)
    s.no_popups("Insert Mesh")
    m = mesh()
    h.check("a mesh body", m is not None and m.Label == "box_20x10x5", m and m.Label)
    if m is not None:
        h.check("20 x 10 x 5 in mm", i.bbox(m) == (0, 0, 0, 20, 10, 5), i.bbox(m))
        h.check("in the browser's Bodies folder", i.browser_has("box_20x10x5"), i.browser_labels())
        h.check(
            "timeline: Insert Mesh 1 (shown with the file's name)",
            i.timeline_kind_title(m) == "Insert Mesh 1" and s.timeline_title_of(m) == "box_20x10x5",
            (i.timeline_kind_title(m), s.timeline_title_of(m)),
        )
    if p is not None:
        h.check("12 triangles shown", "12 triangles" in p.info.text(), p.info.text())
        h.check(
            "Unit Type is Millimeter", p.unit.currentText() == "Millimeter", p.unit.currentText()
        )


# -- B ----------------------------------------------------------------------------------------
def b_centimeter():
    p = i.panel()
    if p is not None:
        b.choose(p.unit, "Centimeter")


def b_check_cm():
    m = mesh()
    h.check(
        "centimeter: 200 x 100 x 50",
        m is not None and i.bbox(m) == (0, 0, 0, 200, 100, 50),
        m and i.bbox(m),
    )


def b_flip():
    p = i.panel()
    if p is not None:
        i.set_check(p.flip, True)


def b_check_flip():
    m = mesh()
    h.check(
        "flip up: Y -> Z", m is not None and i.bbox(m) == (0, -50, 0, 200, 0, 100), m and i.bbox(m)
    )


def b_back():
    p = i.panel()
    if p is not None:
        b.choose(p.unit, "Millimeter")
        i.set_check(p.flip, False)


def b_check_back():
    m = mesh()
    h.check(
        "mm, no flip: 20 x 10 x 5",
        m is not None and i.bbox(m) == (0, 0, 0, 20, 10, 5),
        m and i.bbox(m),
    )


# -- C ----------------------------------------------------------------------------------------
def c_center():
    p = i.panel()
    if p is not None:
        p.center()


def c_check_center():
    m = mesh()
    base = tuple(round(v, 3) for v in m.Placement.Base) if m else None
    h.check("Center: (-10, -5, -2.5)", base == (-10, -5, -2.5), base)
    p = i.panel()
    if p is not None:
        h.check("X Distance field shows -10", abs(p.x.value() + 10) < 1e-6, p.x.value())


def c_ground():
    p = i.panel()
    if p is not None:
        p.move_to_ground()


def c_check_ground():
    m = mesh()
    base = tuple(round(v, 3) for v in m.Placement.Base) if m else None
    h.check("Move to Ground: (-10, -5, 0)", base == (-10, -5, 0), base)


def c_type_x():
    p = i.panel()
    if p is not None:
        i.type_value(p.x, "30")


def c_check_x():
    m = mesh()
    base = tuple(round(v, 3) for v in m.Placement.Base) if m else None
    h.check("X Distance 30: (30, -5, 0)", base == (30, -5, 0), base)


# -- D ----------------------------------------------------------------------------------------
def d_drag_z():
    p = i.panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator shown", triad is not None):
        return
    state["z_before"] = mesh().Placement.Base.z
    start = triad.center + V(0, 0, 1) * (0.75 * triad.size)  # on the arrow, past the balls
    h.drag(h.screen_point(start), h.screen_point(start + V(0, 0, 8)))


d_drag_z.wait_ms = 1200


def d_check_drag():
    m = mesh()
    p = i.panel()
    h.check(
        "Z Distance grew with the drag (about 8)",
        m is not None and m.Placement.Base.z > state.get("z_before", 0) + 3.0,
        (state.get("z_before"), m and m.Placement.Base.z),
    )
    if p is not None and m is not None:
        # the field shows two decimals, like Fusion's
        h.check("the Z field follows", abs(p.z.value() - m.Placement.Base.z) < 0.011, p.z.value())


# -- E ----------------------------------------------------------------------------------------
def e_ok():
    h.task_button("OK")


def e_check():
    h.check("dialog closed", i.panel() is None)
    h.check("mesh body kept", mesh() is not None)
    state["base"] = tuple(mesh().Placement.Base) if mesh() else None


def e_undo():
    i.undo()


def e_check_undo():
    h.check("Ctrl+Z: no mesh body", mesh() is None, i.mesh_bodies())


def e_redo():
    i.redo()


def e_check_redo():
    m = mesh()
    h.check("Ctrl+Y: the mesh body again", m is not None)
    if m is not None:
        h.check(
            "same place",
            tuple(m.Placement.Base) == state["base"],
            (tuple(m.Placement.Base), state["base"]),
        )


# -- F ----------------------------------------------------------------------------------------
def f_edit():
    s.timeline_double_click(mesh())


def f_dialog():
    p = i.panel()
    h.check("edit dialog", p is not None and p.title == "Insert Mesh", p)
    if p is not None:
        h.check("Unit Type Millimeter", p.unit.currentText() == "Millimeter")
        b.choose(p.unit, "Inch")


def f_check_inch():
    m = mesh()
    box = i.bbox(m) if m else None
    h.check("inch: 508 wide", box is not None and abs(box[3] - box[0] - 508) < 1e-6, box)


def f_cancel():
    h.task_button("Cancel")


def f_check_cancel():
    m = mesh()
    box = i.bbox(m) if m else None
    h.check("Cancel: 20 wide again", box is not None and abs(box[3] - box[0] - 20) < 1e-6, box)
    h.check("dialog closed", i.panel() is None)


# -- G ----------------------------------------------------------------------------------------
def g_mesh_tab():
    i.ribbon_tab("MESH")


def g_convert():
    h.fit()
    h.ribbon("Convert Mesh")


def g_waits():
    p = i.panel()
    h.check("Convert Mesh dialog waits", p is not None and p.title == "Convert Mesh", p)
    s.no_popups("Convert Mesh")
    h.check("no body made yet", len(s.bodies()) == 0, len(s.bodies()))


def g_click_mesh():
    h.click(i.mesh_click_point(mesh()))


g_click_mesh.wait_ms = 1500


def g_converted():
    bodies = s.bodies()
    h.check("a solid body", len(bodies) == 1, len(bodies))
    if bodies:
        body = bodies[0]
        h.check("named after the mesh", body.Label == "box_20x10x5 (solid)", body.Label)
        h.check("1000 mm3", i.close(s.volume(body), i.BOX_VOLUME), s.volume(body))
        h.check("prismatic: 6 faces", len(body.Shape.Faces) == 6, len(body.Shape.Faces))
        state["body"] = body.Name
    p = i.panel()
    if p is not None:
        h.check(
            "Body box names the mesh", "box_20x10x5" in p.field.button.text(), p.field.button.text()
        )


def g_faceted():
    p = i.panel()
    if p is not None:
        b.choose(p.method, "Faceted")


g_faceted.wait_ms = 1200


def g_check_faceted():
    bodies = s.bodies()
    h.check(
        "faceted: 12 faces",
        bodies and len(bodies[0].Shape.Faces) == 12,
        bodies and len(bodies[0].Shape.Faces),
    )


def g_prismatic():
    p = i.panel()
    if p is not None:
        b.choose(p.method, "Prismatic")


g_prismatic.wait_ms = 1200


def g_ok():
    h.task_button("OK")


def g_check_ok():
    h.check("dialog closed", i.panel() is None)
    bodies = s.bodies()
    h.check("the body stays", len(bodies) == 1 and len(bodies[0].Shape.Faces) == 6)
    m = mesh()
    h.check("mesh body hidden", m is not None and not s.shown(m))
    active = h.body()
    h.check("the new body is active", bodies and active is bodies[0], active and active.Label)
    if bodies:
        h.check(
            "timeline: Convert Mesh 1",
            i.timeline_kind_title(bodies[0].Tip) == "Convert Mesh 1",
            i.timeline_kind_title(bodies[0].Tip),
        )


# -- H ----------------------------------------------------------------------------------------
def h_undo():
    i.undo()


def h_check_undo():
    h.check("Ctrl+Z: body gone", len(s.bodies()) == 0, len(s.bodies()))
    m = mesh()
    h.check("mesh shown again", m is not None and s.shown(m))


def h_redo():
    i.redo()


def h_check_redo():
    bodies = s.bodies()
    h.check(
        "Ctrl+Y: body back with 1000 mm3", bodies and i.close(s.volume(bodies[0]), i.BOX_VOLUME)
    )
    i.no_file()
    h.shot("end")


h.run(
    "insert_mesh",
    [
        i.new_design("InsertMesh"),
        a_open,
        a_dialog,
        b_centimeter,
        b_check_cm,
        b_flip,
        b_check_flip,
        b_back,
        b_check_back,
        c_center,
        c_check_center,
        c_ground,
        c_check_ground,
        c_type_x,
        c_check_x,
        d_drag_z,
        d_check_drag,
        e_ok,
        e_check,
        e_undo,
        e_check_undo,
        e_redo,
        e_check_redo,
        f_edit,
        f_dialog,
        f_check_inch,
        f_cancel,
        f_check_cancel,
        g_mesh_tab,
        g_convert,
        g_waits,
        g_click_mesh,
        g_converted,
        g_faceted,
        g_check_faceted,
        g_prismatic,
        g_ok,
        g_check_ok,
        h_undo,
        h_check_undo,
        h_redo,
        h_check_redo,
    ],
)
