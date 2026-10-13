# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Reduce, Remesh and Smooth on a sphere STL (r 10, 2208 triangles); only real input.

A  MESH > Reduce with the sphere picked first (the dialog takes it): Reduce Target Tolerance
   (Fusion's), Preview off; Proportion 25 % with Preview: 552 faces, still closed.
B  Face Count 300: exactly 300 faces; OK: "Reduce 1" in the timeline, one body.
C  MESH > Remesh on the reduced body: Density 0.5, Adaptive, Preview: more faces than 300,
   closed, the volume within 2 % of the reduced body's; Uniform: closed, more faces than 300.
   OK: "Remesh 1".
D  MESH > Smooth: Smoothness 0.5 with Preview: the faces stay, the volume shrinks a little
   (less than 3 %); OK: "Smooth 1".
E  Timeline double-click Reduce 1: the dialog with Face Count 300; 600, OK: the steps after it
   are worked out again (the remesh and the smooth follow, still closed).
F  Ctrl+Z: Reduce 1 back at 300 faces; Ctrl+Y: 600.
G  A refusal: Reduce again with Face Count above the faces the body has: the dialog says to
   ask for fewer, OK waits; Cancel.
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

SPHERE = 4.0 / 3.0 * 3.141592653589793 * 1000.0
NAME = "sphere"
state = {}


def sphere_file():
    return m.write_stl("sphere.stl", m.sphere_triangles(10.0, 24))


def body():
    return m.body(NAME)


def step(kind):
    found = m.steps(kind)
    return found[0] if found else None


# -- A ----------------------------------------------------------------------------------------
def a_info():
    b = body()
    h.check("the sphere is a mesh body", b is not None, m.browser_labels())
    state["faces"] = m.facets(b)
    state["volume"] = m.volume(b)
    h.check("2208 triangles", state["faces"] == 2208, state["faces"])
    h.check("closed", m.closed(b))


def a_open():
    m.mesh_tab()
    h.fit()
    s.click_browser_row(NAME)  # picked first: the dialog takes it
    h.ribbon("Reduce")


a_open.wait_ms = 1500


def a_dialog():
    p = m.panel()
    h.check("Reduce dialog", p is not None and p.title == "Reduce", p)
    if p is None:
        return
    h.check(
        "the sphere was taken", p.body is not None and p.body.Label == NAME, p.body and p.body.Label
    )
    h.check("Reduce Target Tolerance", p.reduce_target.currentText() == "Tolerance")
    h.check("Preview off", not p.preview.isChecked())
    m.choose(p.reduce_target, "Proportion")
    m.set_spin(p.proportion, 25)
    m.tick(p.preview, True)


a_dialog.wait_ms = 2000


def a_check():
    st = step("MeshReduce")
    h.check("25 %: 552 faces", m.facets(st) == 552, m.facets(st))
    h.check("closed", m.closed(st))
    h.check("the info line tells the count", "552" in m.panel().info.text(), m.panel().info.text())


# -- B ----------------------------------------------------------------------------------------
def b_face_count():
    p = m.panel()
    m.choose(p.reduce_target, "Face Count")
    m.set_spin(p.face_count, 300)


b_face_count.wait_ms = 2000


def b_check():
    st = step("MeshReduce")
    h.check("Face Count 300: 300 faces", m.facets(st) == 300, m.facets(st))
    h.check("closed", m.closed(st))
    h.task_button("OK")


b_check.wait_ms = 1500


def b_done():
    h.check("dialog closed", m.panel() is None)
    b = body()
    h.check(
        "one body, the Reduce step", b is not None and b.SciForgeType == "MeshReduce", b and b.Name
    )
    h.check("timeline: Reduce 1", m.timeline_title(b) == "Reduce 1", m.timeline_title(b))
    state["reduced"] = m.volume(b)


# -- C ----------------------------------------------------------------------------------------
def c_open():
    s.click_browser_row(NAME)
    h.ribbon("Remesh")


c_open.wait_ms = 1500


def c_adaptive():
    p = m.panel()
    h.check("Remesh dialog", p is not None and p.title == "Remesh", p)
    h.check(
        "Remesh Type Adaptive, Density 0.25",
        p.remesh_type.currentText() == "Adaptive" and abs(p.density.value() - 0.25) < 1e-9,
        (p.remesh_type.currentText(), p.density.value()),
    )
    m.set_spin(p.density, 0.5)
    m.tick(p.preview, True)


c_adaptive.wait_ms = 4000


def c_check_adaptive():
    st = step("MeshRemesh")
    faces = m.facets(st)
    h.check("Adaptive: more faces than 300", faces > 300, faces)
    h.check("closed", m.closed(st))
    h.check(
        "the shape kept (volume within 2 % of the reduced body's)",
        abs(m.volume(st) - state["reduced"]) < 0.02 * SPHERE,
        (m.volume(st), state["reduced"]),
    )
    state["adaptive"] = faces
    m.choose(m.panel().remesh_type, "Uniform")


c_check_adaptive.wait_ms = 5000


def c_check_uniform():
    st = step("MeshRemesh")
    faces = m.facets(st)
    h.check("Uniform: closed", m.closed(st), m.analysis(st))
    h.check("Uniform: more faces than 300", faces > 300, faces)
    h.check(
        "Uniform: the shape kept (volume within 3 %)",
        abs(m.volume(st) - state["reduced"]) < 0.03 * SPHERE,
        (m.volume(st), state["reduced"]),
    )
    h.task_button("OK")


c_check_uniform.wait_ms = 2000


def c_done():
    b = body()
    h.check("the body is the Remesh step", b is not None and b.SciForgeType == "MeshRemesh")
    h.check(
        "timeline: Remesh 1",
        b is not None and m.timeline_title(b) == "Remesh 1",
        b and m.timeline_title(b),
    )


# -- D ----------------------------------------------------------------------------------------
def d_open():
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Smooth")


d_open.wait_ms = 1500


def d_preview():
    p = m.panel()
    h.check("Smooth dialog", p is not None and p.title == "Smooth", p)
    if p is None:
        return
    h.check("Smoothness 0.02 (Fusion's)", abs(p.smoothness.value() - 0.02) < 1e-9)
    state["before_smooth"] = m.volume(body())
    state["faces_before_smooth"] = m.facets(body())
    m.set_spin(p.smoothness, 0.5)
    m.tick(p.preview, True)


d_preview.wait_ms = 2500


def d_check():
    st = step("MeshSmooth")
    h.check("the faces stay", m.facets(st) == state["faces_before_smooth"], m.facets(st))
    before = state["before_smooth"]
    after = m.volume(st)
    h.check(
        "smoothed: a little smaller (under 3 %)", before * 0.97 < after < before, (before, after)
    )
    h.task_button("OK")


d_check.wait_ms = 1500


def d_done():
    b = body()
    h.check(
        "timeline: Smooth 1",
        b is not None and m.timeline_title(b) == "Smooth 1",
        b and m.timeline_title(b),
    )


# -- E ----------------------------------------------------------------------------------------
def e_edit():
    s.timeline_double_click(step("MeshReduce"))


e_edit.wait_ms = 2000


def e_dialog():
    p = m.panel()
    h.check("Reduce edit dialog", p is not None and p.title == "Reduce", p)
    if p is None:
        return
    h.check("Face Count 300", int(p.face_count.value()) == 300, p.face_count.value())
    m.set_spin(p.face_count, 600)
    h.task_button("OK")


e_dialog.wait_ms = 6000


def e_check():
    h.check("dialog closed", m.panel() is None)
    h.check(
        "Reduce 1 now 600 faces", m.facets(step("MeshReduce")) == 600, m.facets(step("MeshReduce"))
    )
    b = body()
    h.check(
        "the later steps followed (still the smooth body, closed)",
        b is not None and b.SciForgeType == "MeshSmooth" and m.closed(b),
        b and b.Name,
    )
    h.check(
        "no step lost its body",
        not any(getattr(o, "SciForgeWarning", "") for o in m.mesh_objects()),
        [(o.Name, getattr(o, "SciForgeWarning", "")) for o in m.mesh_objects()],
    )


# -- F ----------------------------------------------------------------------------------------
def f_undo():
    i.undo()


f_undo.wait_ms = 5000


def f_check_undo():
    h.check(
        "Ctrl+Z: 300 faces again", m.facets(step("MeshReduce")) == 300, m.facets(step("MeshReduce"))
    )


def f_redo():
    i.redo()


f_redo.wait_ms = 5000


def f_check_redo():
    h.check("Ctrl+Y: 600 faces", m.facets(step("MeshReduce")) == 600, m.facets(step("MeshReduce")))


# -- G ----------------------------------------------------------------------------------------
def g_open():
    s.click_browser_row(NAME)
    h.ribbon("Reduce")


g_open.wait_ms = 1500


def g_too_many():
    p = m.panel()
    m.choose(p.reduce_target, "Face Count")
    m.set_spin(p.face_count, 100000)
    m.tick(p.preview, True)


g_too_many.wait_ms = 2000


def g_refused():
    p = m.panel()
    text = p.message.text() if p else ""
    h.check("the dialog says to ask for fewer faces", "fewer" in text, text)
    h.task_button("OK")


g_refused.wait_ms = 1200


def g_waits():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Reduce", p)
    h.task_button("Cancel")


g_waits.wait_ms = 1500


def g_check():
    h.check("dialog closed", m.panel() is None)
    h.check("one Reduce step", len(m.steps("MeshReduce")) == 1, m.steps("MeshReduce"))
    b = body()
    h.check(
        "the body unchanged (the smooth step)", b is not None and b.SciForgeType == "MeshSmooth"
    )
    h.shot("end")


h.run(
    "mesh_reduce_remesh",
    [i.new_design("MeshReduce")]
    + m.insert_file(sphere_file())
    + [
        a_info,
        a_open,
        a_dialog,
        a_check,
        b_face_count,
        b_check,
        b_done,
        c_open,
        c_adaptive,
        c_check_adaptive,
        c_check_uniform,
        c_done,
        d_open,
        d_preview,
        d_check,
        d_done,
        e_edit,
        e_dialog,
        e_check,
        f_undo,
        f_check_undo,
        f_redo,
        f_check_redo,
        g_open,
        g_too_many,
        g_refused,
        g_waits,
        g_check,
    ],
)
_ = App
