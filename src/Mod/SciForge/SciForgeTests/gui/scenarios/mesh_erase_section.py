# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Erase and Fill, Delete Faces and Create Mesh Section Sketch on a sphere STL (r 10,
2208 triangles); only real input.

A  Insert Mesh sphere.stl.
B  Pick it, MESH > Erase and Fill: the Faces box waits, nothing changes yet; a click on the
   top of the sphere takes the faces within the Brush Size (marked); Type Uniform (Fusion's):
   closed, about the same volume. Ctrl+click on the same place takes them off (the body as
   it was); a click again and Type Minimal: closed, fewer faces than Uniform. OK: "Erase And
   Fill 1".
C  MESH > Delete Faces, click the top: a hole (not closed, the dialog says so); OK: "Delete
   Faces 1", the browser flags the body. Repair (Stitch and Remove, Preview): closed again;
   OK.
D  CREATE > Create Mesh Section Sketch: click the sphere, then the XY square: a circle-like
   section is drawn and counted; Distance 5 (typed): still one closed line; OK: a sketch
   "Mesh Section sphere" 5 mm up, its lines fixed, closed, about 2 pi x 8.66 long.
E  The same dialog with the plane moved off the body (Distance 20): it says the plane does
   not cut the body, OK waits; Cancel: no new sketch.
"""

import math

from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

V = i.V
NAME = "sphere"
SPHERE_POINT = V(0.0, 0.0, 10.0)  # the top of the sphere
state = {}


def sphere_file():
    return m.write_stl("sphere.stl", m.sphere_triangles(10.0, 24))


def near(a, b, tol):
    return a is not None and abs(a - b) <= tol


def step(kind):
    found = m.steps(kind)
    return found[-1] if found else None


def sketches():
    return [o for o in m.doc().Objects if o.TypeId == "Sketcher::SketchObject"]


# -- B ----------------------------------------------------------------------------------------
def b_open():
    b = m.body(NAME)
    state["faces"] = m.facets(b)
    state["volume"] = m.volume(b)
    m.mesh_tab()
    h.fit()
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Erase and Fill")


b_open.wait_ms = 1500


def b_waits():
    p = m.panel()
    h.check("Erase and Fill dialog", p is not None and p.title == "Erase and Fill", p)
    if p is None:
        return
    h.check("the sphere taken", p.body is not None and p.body.Label == NAME)
    h.check("the Faces box waits", p.active == "faces", p.active)
    h.check("Type Uniform", p.fill.currentText() == "Uniform")
    h.check(
        "nothing changed yet",
        m.facets(step("MeshEraseFill")) == state["faces"],
        m.facets(step("MeshEraseFill")),
    )
    m.click_body(m.body(NAME), SPHERE_POINT)


b_waits.wait_ms = 2500


def b_uniform():
    p = m.panel()
    h.check("faces picked", p.picked_faces != [], p.faces_field.button.text())
    state["picked"] = len(p.picked_faces)
    h.check("marked on the body", p.marks is not None)
    st = step("MeshEraseFill")
    h.check("Uniform: closed", m.closed(st), m.analysis(st))
    h.check(
        "about the same volume (1 %)",
        near(m.volume(st), state["volume"], 0.01 * 4189.0),
        (m.volume(st), state["volume"]),
    )
    state["uniform"] = m.facets(st)


def b_untick():
    """Ctrl+click on the same place takes the faces off."""
    h.click(SPHERE_POINT, modifiers=QtCore.Qt.ControlModifier)


b_untick.wait_ms = 2500


def b_none():
    p = m.panel()
    h.check("Ctrl+click took them off", p.picked_faces == [], len(p.picked_faces))
    h.check(
        "the body as it was",
        m.facets(step("MeshEraseFill")) == state["faces"],
        m.facets(step("MeshEraseFill")),
    )
    m.click_body(m.body(NAME), SPHERE_POINT)


b_none.wait_ms = 2500


def b_minimal():
    p = m.panel()
    h.check("picked again", len(p.picked_faces) == state["picked"], len(p.picked_faces))
    m.choose(p.fill, "Minimal")


b_minimal.wait_ms = 2500


def b_check_minimal():
    st = step("MeshEraseFill")
    h.check("Minimal: closed", m.closed(st), m.analysis(st))
    h.check(
        "Minimal: fewer faces than Uniform",
        m.facets(st) < state["uniform"],
        (m.facets(st), state["uniform"]),
    )
    h.task_button("OK")


b_check_minimal.wait_ms = 1500


def b_done():
    h.check("dialog closed", m.panel() is None)
    b = m.body(NAME)
    h.check(
        "timeline: Erase And Fill 1",
        b is not None and m.timeline_title(b) == "Erase And Fill 1",
        b and m.timeline_title(b),
    )


# -- C ----------------------------------------------------------------------------------------
def c_open():
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Delete Faces")


c_open.wait_ms = 1500


def c_click():
    p = m.panel()
    h.check("Delete Faces dialog", p is not None and p.title == "Delete Faces", p)
    m.click_body(m.body(NAME), SPHERE_POINT)


c_click.wait_ms = 2500


def c_check():
    p = m.panel()
    st = step("MeshDeleteFaces")
    h.check("a hole", m.analysis(st)["holes"] == 1, m.analysis(st))
    h.check("the dialog says so", "1 hole" in p.info.text(), p.info.text())
    h.task_button("OK")


c_check.wait_ms = 1500


def c_done():
    b = m.body(NAME)
    h.check(
        "timeline: Delete Faces 1",
        b is not None and m.timeline_title(b) == "Delete Faces 1",
        b and m.timeline_title(b),
    )
    node = m.browser_node(NAME)
    h.check(
        "the browser flags it",
        node is not None and node["status"] == "warning" and "1 hole" in node["tip"],
        node and (node["status"], node["tip"]),
    )
    s.click_browser_row(NAME)
    h.ribbon("Repair")


c_done.wait_ms = 1500


def c_repair():
    p = m.panel()
    h.check("Repair dialog", p is not None and p.title == "Repair", p)
    m.tick(p.preview, True)


c_repair.wait_ms = 2000


def c_repaired():
    st = step("MeshRepair")
    h.check("closed again", m.closed(st), m.analysis(st))
    h.task_button("OK")


c_repaired.wait_ms = 1500


# -- D ----------------------------------------------------------------------------------------
def d_open():
    state["sketches"] = len(sketches())
    h.fit()
    s.menu("CREATE", "Create Mesh Section Sketch")


d_open.wait_ms = 1500


def d_body():
    p = m.panel()
    h.check(
        "Create Mesh Section Sketch dialog",
        p is not None and p.title == "Create Mesh Section Sketch",
        p,
    )
    if p is None:
        return
    h.check("the body box waits", p.active == "body", p.active)
    m.click_body(m.body(NAME), SPHERE_POINT)


d_body.wait_ms = 1500


def d_plane():
    p = m.panel()
    h.check(
        "the sphere taken", p.body is not None and p.body.Label == NAME, p.body and p.body.Label
    )
    h.check(
        "the Plane box waits, the squares shown",
        p.active == "plane" and p.squares is not None,
        p.active,
    )
    h.click(p.squares.point_on("XY", 0.9, 0.9))


d_plane.wait_ms = 2000


def d_section():
    p = m.panel()
    h.check(
        "XY picked",
        p.frame is not None and "XY" in p.plane_field.button.text(),
        p.plane_field.button.text(),
    )
    h.check("one section line", p.lines is not None and len(p.lines) == 1, p.lines and len(p.lines))
    h.check("counted in the dialog", "1 section line" in p.info.text(), p.info.text())
    m.type_field(p.distance, "5")


d_section.wait_ms = 2000


def d_moved():
    p = m.panel()
    h.check("still one line", p.lines is not None and len(p.lines) == 1, p.lines and len(p.lines))
    if p.lines:
        h.check("at z = 5", all(abs(pt[2] - 5.0) < 1e-6 for pt in p.lines[0]), p.lines[0][:2])
    h.task_button("OK")


d_moved.wait_ms = 2000


def d_done():
    h.check("dialog closed", m.panel() is None)
    made = sketches()
    h.check("a new sketch", len(made) == state["sketches"] + 1, [x.Label for x in made])
    if len(made) != state["sketches"] + 1:
        return
    sk = made[-1]
    h.check("named Mesh Section sphere", sk.Label == "Mesh Section sphere", sk.Label)
    h.check(
        "5 mm up", abs(sk.getGlobalPlacement().Base.z - 5.0) < 1e-6, sk.getGlobalPlacement().Base
    )
    h.check(
        "its lines fixed",
        sk.ConstraintCount == sk.GeometryCount and all(c.Type == "Block" for c in sk.Constraints),
        (sk.ConstraintCount, sk.GeometryCount),
    )
    wires = sk.Shape.Wires
    h.check("one closed line", len(wires) == 1 and wires[0].isClosed(), len(wires))
    radius = math.sqrt(100.0 - 25.0)
    if wires:
        h.check(
            "about 2 pi x 8.66 long (2 %)",
            near(wires[0].Length, 2 * math.pi * radius, 0.02 * 2 * math.pi * radius),
            wires[0].Length,
        )


# -- E ----------------------------------------------------------------------------------------
def e_open():
    s.menu("CREATE", "Create Mesh Section Sketch")


e_open.wait_ms = 1500


def e_pick():
    m.click_body(m.body(NAME), SPHERE_POINT)


e_pick.wait_ms = 1500


def e_plane():
    p = m.panel()
    h.click(p.squares.point_on("XY", 0.9, 0.9))


e_plane.wait_ms = 2000


def e_off():
    m.type_field(m.panel().distance, "20")


e_off.wait_ms = 2000


def e_refused():
    p = m.panel()
    text = p.message.text()
    h.check("the dialog says the plane does not cut the body", "does not cut" in text, text)
    h.task_button("OK")


e_refused.wait_ms = 1200


def e_waits():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Create Mesh Section Sketch", p)
    h.task_button("Cancel")


e_waits.wait_ms = 1500


def e_check():
    h.check("dialog closed", m.panel() is None)
    h.check("no new sketch", len(sketches()) == state["sketches"] + 1, len(sketches()))
    h.shot("end")


h.run(
    "mesh_erase_section",
    [i.new_design("MeshErase")]
    + m.insert_file(sphere_file())
    + [b_open, b_waits, b_uniform, b_untick, b_none, b_minimal, b_check_minimal, b_done]
    + [c_open, c_click, c_check, c_done, c_repair, c_repaired]
    + [d_open, d_body, d_plane, d_section, d_moved, d_done]
    + [e_open, e_pick, e_plane, e_off, e_refused, e_waits, e_check],
)
