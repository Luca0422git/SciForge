# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > MODIFY > Direct Edit on a sphere STL (r 10, 2208 triangles); only real input.

A  Insert Mesh sphere.stl; pick it in the browser, MODIFY > Direct Edit: the Faces box waits,
   Selection is Paint, Select Back Faces off, nothing changed yet.
B  Brush 3 mm: a click on the top paints faces there; Ctrl+click takes them off; a paint
   stroke (drag) over the top takes more than the click did; Del deletes them: one hole, the
   edit is listed.
C  Selection Window: a box round the face that looks at you takes faces facing you only;
   Select Back Faces on takes more (the far side too); off again, the box again; Create Face
   Group: the body has two face groups, the faces stay picked.
D  Clear; Window click on a face of the group: one face; Alt+G: the whole group; Move: the
   arrow shows, Distance 3: the body reaches 3 mm further towards you (the move is shown,
   not yet an edit); Apply Move: three edits.
E  Shift+Up grows the pick; Smoothness 0.8, Smooth: the bump comes back towards the sphere;
   Remove Last Edit: the bump is back; Smooth again: four edits.
F  Clear, Del: refused ("Pick the faces first"), nothing changes.
G  Finish Direct Edit: one timeline step "Mesh Base Feature 1", the body keeps its name, the
   browser flags its hole. Undo: the sphere as it was (2208 faces); Redo: the step is back.
"""

from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m
from SciForgeTests.gui import meshinspect2_steps as e

V = i.V
NAME = "sphere"
TOP = V(0.0, 0.0, 10.0)
state = {}


def sphere_file():
    return m.write_stl("sphere.stl", m.sphere_triangles(10.0, 24))


def step():
    found = m.steps("MeshDirectEdit")
    return found[-1] if found else None


def body():
    return m.body(NAME)


# -- A ----------------------------------------------------------------------------------------
def a_open():
    state["faces"] = m.facets(body())
    m.mesh_tab()
    h.fit()
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Direct Edit")


a_open.wait_ms = 1500


def a_waits():
    p = e.direct_panel()
    h.check("Direct Edit dialog", p is not None and p.title == "Direct Edit", m.panel())
    if p is None:
        return
    h.check("the sphere taken", p.body is not None and p.body.Label == NAME, p.body)
    h.check("the Faces box waits", p.active == "faces", p.active)
    h.check("Selection: Paint", p.selection_type() == "Paint", p.selection_type())
    h.check("Select Back Faces off", not p.back_faces.isChecked())
    h.check("nothing changed yet", m.facets(step()) == state["faces"], m.facets(step()))
    h.check("no edit yet", e.edits(p) == 0, e.edits(p))
    h.shot("dialog")
    m.type_field(p.brush, "3")


a_waits.wait_ms = 800


# -- B ----------------------------------------------------------------------------------------
def b_click():
    h.click(TOP)


b_click.wait_ms = 1200


def b_clicked():
    p = e.direct_panel()
    state["click"] = len(p.selected)
    h.check("a click on the pole paints faces", state["click"] >= 3, state["click"])
    h.check("they are marked", p.marks is not None)
    h.check(
        "the Faces box says it", "face" in p.faces_field.button.text(), p.faces_field.button.text()
    )
    h.click(TOP, modifiers=QtCore.Qt.ControlModifier)


b_clicked.wait_ms = 1200


def b_unpainted():
    p = e.direct_panel()
    h.check("Ctrl+click took them off", p.selected == [], len(p.selected))
    # a stroke over the upper left of the sphere (well away from where C and D work)
    state["stroke_ends"] = (e.on_sphere(-0.75, 0.45), e.on_sphere(-0.55, 0.6))
    e.drag_screen(*state["stroke_ends"])


b_unpainted.wait_ms = 1500


def b_stroke():
    p = e.direct_panel()
    state["stroke"] = len(p.selected)
    a, z = state["stroke_ends"]
    st = p.work()[0]
    near_a = min((V(*c) - a).Length for c in st.centres(p.selected)) if p.selected else None
    near_z = min((V(*c) - z).Length for c in st.centres(p.selected)) if p.selected else None
    h.check(
        "the stroke paints faces all along its way",
        state["stroke"] >= 6 and near_a < 2.0 and near_z < 2.0,
        (state["stroke"], near_a, near_z),
    )
    e.key(QtCore.Qt.Key_Delete)


b_stroke.wait_ms = 2000


def b_deleted():
    p = e.direct_panel()
    st = step()
    h.check(
        "Del deleted them",
        m.facets(st) == state["faces"] - state["stroke"],
        (m.facets(st), state["faces"], state["stroke"]),
    )
    h.check("one hole", m.analysis(st)["holes"] == 1, m.analysis(st))
    h.check("one edit listed", e.edits(p) == 1, e.edits(p))
    h.check(
        "the edit says Delete",
        p.edit_list.count() and "Delete" in p.edit_list.item(0).text(),
        p.edit_list.count() and p.edit_list.item(0).text(),
    )
    h.check("the pick is cleared", p.selected == [], len(p.selected))
    e.choose(p, "selection", "Window")


b_deleted.wait_ms = 800


# -- C ----------------------------------------------------------------------------------------
def c_box():
    e.drag_box(e.on_sphere(), 40)


c_box.wait_ms = 1500


def c_front_only():
    p = e.direct_panel()
    state["box"] = list(p.selected)
    h.check("the box takes faces", len(state["box"]) >= 6, len(state["box"]))
    h.check("only faces facing you", e.facing_all(p, state["box"]))
    e.press_button(p, "clear")
    i.set_check(p.back_faces, True)


c_front_only.wait_ms = 800


def c_back_box():
    e.drag_box(e.on_sphere(), 40)


c_back_box.wait_ms = 1500


def c_with_back():
    p = e.direct_panel()
    h.check(
        "Select Back Faces takes the far side too",
        len(p.selected) > len(state["box"]) and not e.facing_all(p, p.selected),
        (len(p.selected), len(state["box"])),
    )
    e.press_button(p, "clear")
    i.set_check(p.back_faces, False)


c_with_back.wait_ms = 800


def c_box_again():
    e.drag_box(e.on_sphere(), 40)


c_box_again.wait_ms = 1500


def c_group():
    p = e.direct_panel()
    h.check("the same faces again", sorted(p.selected) == sorted(state["box"]), len(p.selected))
    e.press_button(p, "group")


c_group.wait_ms = 1500


def c_grouped():
    p = e.direct_panel()
    st = step()
    groups = list(st.FaceGroups)
    h.check("two face groups", len(set(groups)) == 2, sorted(set(groups)))
    h.check(
        "the group is the boxed faces",
        groups.count(max(groups or [0])) == len(state["box"]),
        (groups.count(max(groups or [0])), len(state["box"])),
    )
    h.check("the faces stay picked", len(p.selected) == len(state["box"]), len(p.selected))
    h.check("two edits", e.edits(p) == 2, e.edits(p))
    e.press_button(p, "clear")


c_grouped.wait_ms = 800


# -- D ----------------------------------------------------------------------------------------
def d_click_one():
    h.click(e.on_sphere())


d_click_one.wait_ms = 1200


def d_one():
    p = e.direct_panel()
    h.check("a Window click takes one face", len(p.selected) == 1, len(p.selected))
    e.key(QtCore.Qt.Key_G, QtCore.Qt.AltModifier)


d_one.wait_ms = 1000


def d_group():
    p = e.direct_panel()
    h.check(
        "Alt+G: the whole face group",
        sorted(p.selected) == sorted(state["box"]),
        (len(p.selected), len(state["box"])),
    )
    state["front"] = e.front_extent(step())
    e.press_button(p, "move")


d_group.wait_ms = 1200


def d_arrow():
    p = e.direct_panel()
    h.check("Move: the arrow shows", p.move_handle is not None)
    m.type_field(p.distance, "3")


d_arrow.wait_ms = 2000


def d_moved():
    p = e.direct_panel()
    front = e.front_extent(step())
    h.check(
        "the group moved 3 mm towards you",
        abs(front - state["front"] - 3.0) < 0.35,
        (front, state["front"]),
    )
    h.check("not yet an edit", e.edits(p) == 2, e.edits(p))
    e.press_button(p, "apply_move")


d_moved.wait_ms = 1500


def d_applied():
    p = e.direct_panel()
    h.check("three edits", e.edits(p) == 3, e.edits(p))
    h.check("the arrow is gone", p.move_handle is None)
    state["moved"] = e.front_extent(step())
    h.check("the move stays", abs(state["moved"] - state["front"] - 3.0) < 0.35, state["moved"])
    e.key(QtCore.Qt.Key_Up, QtCore.Qt.ShiftModifier)


d_applied.wait_ms = 1000


# -- E ----------------------------------------------------------------------------------------
def e_grown():
    p = e.direct_panel()
    h.check("Shift+Up grows the pick", len(p.selected) > len(state["box"]), len(p.selected))
    e.set_double(p.smoothness, 0.8)
    e.press_button(p, "smooth")


e_grown.wait_ms = 2500


def e_smoothed():
    p = e.direct_panel()
    front = e.front_extent(step())
    state["smoothed"] = front
    h.check(
        "Smooth: the bump comes back",
        front < state["moved"] - 0.5,
        (front, state["moved"], step().StepInfo),
    )
    h.check("four edits", e.edits(p) == 4, e.edits(p))
    e.press_button(p, "remove_last")


e_smoothed.wait_ms = 2000


def e_removed():
    p = e.direct_panel()
    front = e.front_extent(step())
    h.check("Remove Last Edit: the bump is back", abs(front - state["moved"]) < 1e-6, front)
    h.check("three edits again", e.edits(p) == 3, e.edits(p))
    h.check("the pick was cleared", p.selected == [], len(p.selected))
    e.drag_box(e.on_sphere(), 70)


e_removed.wait_ms = 2000


def e_smooth_again():
    p = e.direct_panel()
    h.check("faces picked again", len(p.selected) > 10, len(p.selected))
    e.press_button(p, "smooth")


e_smooth_again.wait_ms = 2500


def e_four():
    p = e.direct_panel()
    h.check("four edits", e.edits(p) == 4, e.edits(p))
    h.check("smoothed again", e.front_extent(step()) < state["moved"] - 0.3, e.front_extent(step()))
    e.press_button(p, "clear")


e_four.wait_ms = 800


# -- F ----------------------------------------------------------------------------------------
def f_delete_nothing():
    state["before_f"] = m.facets(step())
    e.key(QtCore.Qt.Key_Delete)


f_delete_nothing.wait_ms = 1000


def f_refused():
    p = e.direct_panel()
    text = p.message.text()
    h.check("Del with nothing picked says why", "Pick the faces first" in text, text)
    h.check("nothing changed", m.facets(step()) == state["before_f"], m.facets(step()))
    h.check("still four edits", e.edits(p) == 4, e.edits(p))
    e.press_button(p, "finish")


f_refused.wait_ms = 2000


# -- G ----------------------------------------------------------------------------------------
def g_done():
    h.check("dialog closed", m.panel() is None, m.panel())
    st = step()
    h.check("one Direct Edit step", len(m.steps("MeshDirectEdit")) == 1)
    h.check("it is the body", body() is st, (body(), st))
    h.check(
        "timeline: Mesh Base Feature 1",
        st is not None and m.timeline_title(st) == "Mesh Base Feature 1",
        st and m.timeline_title(st),
    )
    h.check("four edits kept", st is not None and len(st.Edits) == 4, st and len(st.Edits))
    node = m.browser_node(NAME)
    h.check(
        "the browser flags the hole",
        node is not None and node["status"] == "warning",
        node and (node["status"], node["tip"]),
    )
    state["after"] = m.facets(st)
    s.undo()


g_done.wait_ms = 2000


def g_undone():
    h.check("Undo: no Direct Edit step", m.steps("MeshDirectEdit") == [], m.steps("MeshDirectEdit"))
    h.check("the sphere as it was", m.facets(body()) == state["faces"], m.facets(body()))
    h.check("closed again", m.closed(body()))
    s.redo()


g_undone.wait_ms = 2000


def g_redone():
    st = step()
    h.check("Redo: the step is back", st is not None and body() is st, (st, body()))
    h.check("as it was made", m.facets(st) == state["after"], m.facets(st))
    h.shot("end")


h.run(
    "meshinspect2_direct",
    [i.new_design("MeshDirect")]
    + m.insert_file(sphere_file())
    + [a_open, a_waits]
    + [b_click, b_clicked, b_unpainted, b_stroke, b_deleted]
    + [c_box, c_front_only, c_back_box, c_with_back, c_box_again, c_group, c_grouped]
    + [d_click_one, d_one, d_group, d_arrow, d_moved, d_applied]
    + [e_grown, e_smoothed, e_removed, e_smooth_again, e_four]
    + [f_delete_nothing, f_refused]
    + [g_done, g_undone, g_redone],
)
