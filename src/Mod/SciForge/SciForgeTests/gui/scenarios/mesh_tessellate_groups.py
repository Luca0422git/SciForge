# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Tessellate a solid, Reverse Normal, Generate Face Groups and Separate by face group;
only real input.

A  A 40 x 30 x 10 solid box (sketch, extrude).
B  MESH > Tessellate: the dialog waits for a body; click the box: Refinement Medium (Fusion's),
   Preview off; Preview: 12 triangles (the number shown), 6 face groups (one per face of the
   solid), closed, 12000 mm3. Maximum Edge Length 5 mm: Refinement turns to Custom, more
   triangles, still 12000 mm3. OK: "Tessellate 1", a mesh body named like the solid; the
   solid is converted (no longer listed).
C  Ctrl+Z: the solid back; Ctrl+Y: the mesh body again.
D  An inside-out STL (every face points in): the browser flags it; pick it, MESH > Reverse
   Normal: no face groups, so every face turns: 1000 mm3, closed; OK: "Reverse Normal 1", the
   flag gone.
E  PREPARE > Generate Face Groups on it: Method Fast, Angle Threshold 25 deg; Preview: 6 face
   groups; OK: "Generate Face Groups 1".
F  Reverse Normal again: the Face Groups box waits; click the top: 1 face group, only its
   faces turn (the body is not closed any more, the dialog says so); Cancel: as it was.
G  Separate, Separate Type Select Face Groups, click the top: two pieces, the top (2
   faces) and the rest (10); OK: "Separate 1".
"""

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

V = i.V
state = {}


def inside_out_file():
    tris = [(a, c, b) for a, b, c in m.box_triangles(60, 0, 0, 80, 10, 5)]
    return m.write_stl("inside_out.stl", tris)


def groups_of(obj):
    from sciforge import mesh_core

    return mesh_core.group_count(list(getattr(obj, "FaceGroups", []) or []))


def near(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol


def top_normals_down(obj):
    """How many faces on the top (z = 5) point down."""
    return sum(
        1
        for f in obj.Mesh.Facets
        if abs(sum(p[2] for p in f.Points) / 3.0 - 5.0) < 1e-6 and f.Normal.z < -0.99
    )


# -- B ----------------------------------------------------------------------------------------
def b_open():
    solids = s.bodies()
    state["solid"] = solids[0].Name if solids else ""
    state["solid_label"] = solids[0].Label if solids else ""
    m.mesh_tab()
    h.fit()
    h.ribbon("Tessellate")


b_open.wait_ms = 1500


def b_waits():
    p = m.panel()
    h.check("Tessellate dialog", p is not None and p.title == "Tessellate", p)
    if p is None:
        return
    h.check("no step yet", not m.steps("Tessellate"))
    h.check("Refinement Medium", p.refinement.currentText() == "Medium")
    h.check("Preview off", not p.preview.isChecked())
    h.click(V(20.0, 15.0, 10.0))


b_waits.wait_ms = 1500


def b_taken():
    p = m.panel()
    h.check(
        "the box taken",
        p.body is not None and p.body.Name == state["solid"],
        p.body and p.body.Name,
    )
    h.check("Preview off: no count yet", p.triangles.text() == "", p.triangles.text())
    m.tick(p.preview, True)


b_taken.wait_ms = 2500


def b_preview():
    p = m.panel()
    step = m.steps("Tessellate")[0]
    h.check("12 triangles", m.facets(step) == 12, m.facets(step))
    h.check("the number is shown", p.triangles.text() == "12", p.triangles.text())
    h.check("6 face groups", groups_of(step) == 6, groups_of(step))
    h.check("closed", m.closed(step))
    h.check("12000 mm3", near(m.volume(step), 12000.0), m.volume(step))
    m.type_field(p.max_edge.widget, "5")


b_preview.wait_ms = 3000


def b_custom():
    p = m.panel()
    step = m.steps("Tessellate")[0]
    h.check(
        "Refinement turned to Custom",
        p.refinement.currentText() == "Custom",
        p.refinement.currentText(),
    )
    h.check("more triangles", m.facets(step) > 12, m.facets(step))
    h.check("the number follows", p.triangles.text() == str(m.facets(step)), p.triangles.text())
    h.check(
        "still closed, 12000 mm3", m.closed(step) and near(m.volume(step), 12000.0), m.volume(step)
    )
    h.check("still 6 face groups", groups_of(step) == 6, groups_of(step))
    state["fine"] = m.facets(step)
    h.task_button("OK")


b_custom.wait_ms = 1500


def b_done():
    h.check("dialog closed", m.panel() is None)
    mesh_body = m.body(state["solid_label"])
    h.check(
        "a mesh body named like the solid",
        mesh_body is not None and mesh_body.SciForgeType == "Tessellate",
        m.browser_labels(),
    )
    if mesh_body is not None:
        h.check(
            "timeline: Tessellate 1",
            m.timeline_title(mesh_body) == "Tessellate 1",
            m.timeline_title(mesh_body),
        )
    solid = m.doc().getObject(state["solid"])
    h.check("the solid is converted (hidden)", solid is not None and not m.shown(solid))
    from sciforge import bodies, commands

    active = bodies.active_body()
    h.check(
        "the hidden solid is not the active body",
        active is None or active.Name != state["solid"],
        active and active.Name,
    )
    found = commands.find_body()
    h.check(
        "new work would not go into it",
        found is None or found.Name != state["solid"],
        found and found.Name,
    )
    h.check(
        "the browser lists one body",
        m.browser_labels().count(state["solid_label"]) == 1,
        m.browser_labels(),
    )


# -- C ----------------------------------------------------------------------------------------
def c_undo():
    i.undo()


c_undo.wait_ms = 1500


def c_check_undo():
    h.check("Ctrl+Z: no Tessellate", not m.steps("Tessellate"))
    solid = m.doc().getObject(state["solid"])
    h.check("the solid shown again", solid is not None and m.shown(solid))


def c_redo():
    i.redo()


c_redo.wait_ms = 1500


def c_check_redo():
    mesh_body = m.body(state["solid_label"])
    h.check(
        "Ctrl+Y: the mesh body again",
        mesh_body is not None and m.facets(mesh_body) == state["fine"],
        mesh_body and m.facets(mesh_body),
    )


# -- D ----------------------------------------------------------------------------------------
def d_flagged():
    b = m.body("inside_out")
    h.check("the inside-out box is a body", b is not None, m.browser_labels())
    node = m.browser_node("inside_out")
    h.check(
        "the browser flags it (inside out)",
        node is not None and node["status"] == "warning" and "Inside out" in node["tip"],
        node and (node["status"], node["tip"]),
    )
    h.check(
        "its volume is negative", b is not None and m.signed_volume(b) < 0, b and m.signed_volume(b)
    )
    s.click_browser_row("inside_out")
    s.menu("MODIFY", "Reverse Normal")


d_flagged.wait_ms = 2000


def d_dialog():
    p = m.panel()
    h.check("Reverse Normal dialog", p is not None and p.title == "Reverse Normal", p)
    if p is None:
        return
    h.check("the picked body was taken", p.body is not None and p.body.Label == "inside_out")
    h.check(
        "no face groups: All faces",
        p.groups_field.button.text() == "All faces" and not p.groups_field.widget.isEnabled(),
        p.groups_field.button.text(),
    )
    step = m.steps("MeshReverseNormal")[0]
    h.check(
        "every face turned: +1000 mm3", near(m.signed_volume(step), 1000.0), m.signed_volume(step)
    )
    h.check("closed", m.closed(step))
    h.task_button("OK")


d_dialog.wait_ms = 1500


def d_done():
    h.check("dialog closed", m.panel() is None)
    b = m.body("inside_out")
    h.check(
        "timeline: Reverse Normal 1",
        b is not None and m.timeline_title(b) == "Reverse Normal 1",
        b and m.timeline_title(b),
    )
    node = m.browser_node("inside_out")
    h.check(
        "the flag is gone",
        node is not None and node["status"] == "ok",
        node and (node["status"], node["tip"]),
    )


# -- E ----------------------------------------------------------------------------------------
def e_open():
    s.click_browser_row("inside_out")
    h.ribbon("Generate Face Groups")


e_open.wait_ms = 1500


def e_dialog():
    p = m.panel()
    h.check("Generate Face Groups dialog", p is not None and p.title == "Generate Face Groups", p)
    if p is None:
        return
    h.check("Method Fast", p.method.currentText() == "Fast")
    h.check("Angle Threshold 25 deg", abs(p.angle.value() - 25.0) < 0.05, p.angle.value())
    m.tick(p.preview, True)


e_dialog.wait_ms = 2000


def e_check():
    step = m.steps("MeshFaceGroups")[0]
    h.check("6 face groups", groups_of(step) == 6, groups_of(step))
    h.check(
        "the info line says so", "6 face groups" in m.panel().info.text(), m.panel().info.text()
    )
    h.task_button("OK")


e_check.wait_ms = 1500


def e_done():
    b = m.body("inside_out")
    h.check(
        "timeline: Generate Face Groups 1",
        b is not None and m.timeline_title(b) == "Generate Face Groups 1",
        b and m.timeline_title(b),
    )
    h.check("the body keeps 6 face groups", b is not None and groups_of(b) == 6)


# -- F ----------------------------------------------------------------------------------------
def f_open():
    s.click_browser_row("inside_out")
    s.menu("MODIFY", "Reverse Normal")


f_open.wait_ms = 1500


def f_waits():
    p = m.panel()
    h.check("Reverse Normal dialog", p is not None and p.title == "Reverse Normal", p)
    if p is None:
        return
    h.check("the Face Groups box waits", p.active == "groups", p.active)
    m.click_body(m.steps("MeshReverseNormal")[-1])


f_waits.wait_ms = 2000


def f_check():
    p = m.panel()
    h.check(
        "1 face group", p.groups_field.button.text() == "1 face group", p.groups_field.button.text()
    )
    step = m.steps("MeshReverseNormal")[-1]  # the new one
    h.check(
        "only the top turned (2 faces point down)",
        top_normals_down(step) == 2,
        top_normals_down(step),
    )
    h.check("not closed any more", not m.closed(step), m.analysis(step))
    h.check("the dialog says so", "flipped" in p.info.text(), p.info.text())
    h.task_button("Cancel")


f_check.wait_ms = 1500


def f_done():
    h.check("dialog closed", m.panel() is None)
    h.check("one Reverse Normal step", len(m.steps("MeshReverseNormal")) == 1)
    b = m.body("inside_out")
    h.check(
        "the body as it was (closed)",
        b is not None and m.closed(b) and top_normals_down(b) == 0,
        b and m.analysis(b),
    )


# -- G ----------------------------------------------------------------------------------------
def g_open():
    s.click_browser_row("inside_out")
    s.menu("MODIFY", "Separate")


g_open.wait_ms = 1500


def g_type():
    p = m.panel()
    h.check("Separate dialog", p is not None and p.title == "Separate", p)
    if p is None:
        return
    m.choose(p.separate_type, "Select Face Groups")


g_type.wait_ms = 1500


def g_click():
    p = m.panel()
    h.check("the Face Groups box waits", p.active == "groups", p.active)
    h.check(
        "the dialog says to pick them", "Pick the face groups" in p.message.text(), p.message.text()
    )
    m.click_body(m.steps("MeshSeparate")[0].Source)


g_click.wait_ms = 2500


def g_check():
    from sciforge import mesh

    p = m.panel()
    h.check(
        "1 face group", p.groups_field.button.text() == "1 face group", p.groups_field.button.text()
    )
    pieces = mesh.pieces_of(m.steps("MeshSeparate")[0])
    h.check("two pieces", len(pieces) == 2, pieces)
    if len(pieces) == 2:
        h.check(
            "the top (2 faces) and the rest (10)",
            [m.facets(x) for x in pieces] == [2, 10],
            [m.facets(x) for x in pieces],
        )
    h.task_button("OK")


g_check.wait_ms = 1500


def g_done():
    h.check("dialog closed", m.panel() is None)
    step = m.steps("MeshSeparate")
    h.check(
        "timeline: Separate 1",
        bool(step) and m.timeline_title(step[0]) == "Separate 1",
        step and m.timeline_title(step[0]),
    )
    labels = sorted(x.Label for x in m.bodies())
    h.check("the pieces listed", "inside_out" in labels and "inside_out (2)" in labels, labels)
    h.shot("end")


h.run(
    "mesh_tessellate_groups",
    [i.new_design("MeshTessellate")]
    + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [b_open, b_waits, b_taken, b_preview, b_custom, b_done]
    + [c_undo, c_check_undo, c_redo, c_check_redo]
    + m.insert_file(inside_out_file())
    + [d_flagged, d_dialog, d_done, e_open, e_dialog, e_check, e_done]
    + [f_open, f_waits, f_check, f_done, g_open, g_type, g_click, g_check, g_done],
)
