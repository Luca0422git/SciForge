# SPDX-License-Identifier: LGPL-2.1-or-later
"""Face groups and the history marker on a mesh box (20 x 20 x 10, every side a 4 x 4 grid:
192 triangles); only real input.

A  Insert Mesh gbox.stl; PREPARE > Generate Face Groups, OK: six face groups (the sides).
B  PREPARE > Create Face Group: OK with nothing picked is refused; Brush 3 mm, a click in the
   middle of the top: a few faces; OK: seven face groups, "Create Face Group 1".
C  PREPARE > Combine Face Groups: the patch on the top and the right side do not touch:
   refused with the reason, OK waits; a click on the patch drops it, a click on the rest of
   the top takes the top: six face groups; OK: "Combine Face Groups 1".
D  The history marker dragged before Combine Face Groups 1: that step is rolled back (hidden,
   not listed), the body shows as Create Face Group 1 left it (seven groups).
E  MODIFY > Direct Edit at the marker: paint the middle of the front side, Del, Finish: the
   step goes in at the marker (before Combine Face Groups 1, which stays rolled back).
F  The marker dragged to the end: Combine Face Groups 1 now builds on the Direct Edit: the
   body has its hole and six face groups.
G  Undo: the Direct Edit is gone, Combine Face Groups 1 reads Create Face Group 1 again (no
   hole); Redo: the hole is back.
H  Saved, closed, opened again: one mesh body, the hole, six face groups, the steps in order.
"""

import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m
from SciForgeTests.gui import meshinspect2_steps as e
from SciForgeTests.gui import timeline_input as t

V = i.V
NAME = "gbox"
TOP = V(10.0, 10.0, 10.0)  # the middle of the top
TOP_EDGE = V(2.5, 2.5, 10.0)  # the top near a corner (outside the patch)
RIGHT = V(20.0, 10.0, 5.0)
FRONT = V(10.0, 0.0, 5.0)
OUT = os.path.join(i.OUT, "meshinspect2_groups")
state = {}


def box_file():
    return m.write_stl("gbox.stl", e.grid_box_triangles())


def body():
    return m.body(NAME)


def last(kind):
    found = m.steps(kind)
    return found[-1] if found else None


def groups_of(obj):
    return len(set(getattr(obj, "FaceGroups", []) or [])) if obj is not None else 0


def holes(obj):
    return m.analysis(obj)["holes"] if obj is not None else None


def title(obj):
    return m.timeline_title(obj) if obj is not None else None


# -- A ----------------------------------------------------------------------------------------
def a_open():
    m.mesh_tab()
    h.fit()
    state["faces"] = m.facets(body())
    s.click_browser_row(NAME)
    s.menu("PREPARE", "Generate Face Groups")


a_open.wait_ms = 1500


def a_ok():
    p = m.panel()
    h.check("Generate Face Groups dialog", p is not None and p.title == "Generate Face Groups", p)
    h.task_button("OK")


a_ok.wait_ms = 2000


def a_done():
    h.check("192 faces", state["faces"] == 192, state["faces"])
    h.check("six face groups", groups_of(body()) == 6, groups_of(body()))
    s.click_browser_row(NAME)
    s.menu("PREPARE", "Create Face Group")


a_done.wait_ms = 1500


# -- B ----------------------------------------------------------------------------------------
def b_refused():
    p = m.panel()
    h.check("Create Face Group dialog", p is not None and p.title == "Create Face Group", p)
    if p is None:
        return
    h.check("the Faces box waits", p.active == "faces", p.active)
    h.task_button("OK")


b_refused.wait_ms = 1200


def b_says():
    p = m.panel()
    h.check("OK with nothing picked waits", p is not None and p.title == "Create Face Group", p)
    h.check(
        "and says why",
        p is not None and "Pick the faces" in p.message.text(),
        p and p.message.text(),
    )
    m.type_field(p.brush, "3")
    m.click_body(body(), TOP)


b_says.wait_ms = 2000


def b_picked():
    p = m.panel()
    state["patch"] = len(p.picked_faces)
    h.check("a few faces picked", 2 <= state["patch"] <= 12, state["patch"])
    h.check("seven groups in the preview", groups_of(last("MeshCreateFaceGroup")) == 7)
    h.task_button("OK")


b_picked.wait_ms = 1500


def b_done():
    h.check("dialog closed", m.panel() is None)
    st = last("MeshCreateFaceGroup")
    h.check("timeline: Create Face Group 1", title(st) == "Create Face Group 1", title(st))
    h.check("the body has seven face groups", groups_of(body()) == 7, groups_of(body()))
    s.click_browser_row(NAME)
    s.menu("PREPARE", "Combine Face Groups")


b_done.wait_ms = 1500


# -- C ----------------------------------------------------------------------------------------
def c_patch():
    p = m.panel()
    h.check("Combine Face Groups dialog", p is not None and p.title == "Combine Face Groups", p)
    if p is None:
        return
    h.check("the Face Groups box waits", p.active == "groups", p.active)
    m.click_body(body(), TOP)


c_patch.wait_ms = 1200


def c_right():
    m.click_body(body(), RIGHT)


c_right.wait_ms = 2000


def c_refused():
    p = m.panel()
    h.check("two groups picked", len(p.chosen) == 2, p.chosen)
    text = p.message.text()
    h.check("groups that do not touch are refused", "do not touch" in text, text)
    h.task_button("OK")


c_refused.wait_ms = 1500


def c_waits():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Combine Face Groups", p)
    m.click_body(body(), TOP)  # drops the patch


c_waits.wait_ms = 1200


def c_dropped():
    p = m.panel()
    h.check("a click on the patch dropped it", len(p.chosen) == 1, p.chosen)
    m.click_body(body(), TOP_EDGE)


c_dropped.wait_ms = 2000


def c_combined():
    p = m.panel()
    h.check("top and right picked", len(p.chosen) == 2, p.chosen)
    h.check("no message", p.message.text() == "", p.message.text())
    st = last("MeshCombineFaceGroups")
    h.check("six face groups in the preview", groups_of(st) == 6, groups_of(st))
    h.task_button("OK")


c_combined.wait_ms = 1500


def c_done():
    st = last("MeshCombineFaceGroups")
    h.check("timeline: Combine Face Groups 1", title(st) == "Combine Face Groups 1", title(st))
    h.check("the body is that step", body() is st, (body(), st))
    h.check("six face groups", groups_of(body()) == 6, groups_of(body()))
    t.drag_marker("Combine Face Groups 1")


c_done.wait_ms = 2000


# -- D ----------------------------------------------------------------------------------------
def d_rolled():
    states = t.states()
    h.check(
        "Combine Face Groups 1 is rolled back",
        states.get("Combine Face Groups 1", ("",))[0] == "rolled_back",
        states,
    )
    h.check(
        "Create Face Group 1 is done",
        states.get("Create Face Group 1", ("",))[0] == "done",
        states,
    )
    combine = last("MeshCombineFaceGroups")
    create = last("MeshCreateFaceGroup")
    h.check("the body is Create Face Group 1 again", body() is create, (body(), create))
    h.check("seven face groups at the marker", groups_of(body()) == 7, groups_of(body()))
    h.check("Combine Face Groups 1 hidden", not m.shown(combine))
    h.check("Create Face Group 1 shown", m.shown(create))
    h.check(
        "the browser lists one body",
        [lab for lab in m.browser_labels() if lab.startswith(NAME)] == [NAME],
        m.browser_labels(),
    )
    h.fit()
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Direct Edit")


d_rolled.wait_ms = 1500


# -- E ----------------------------------------------------------------------------------------
def e_paint():
    p = e.direct_panel()
    h.check("Direct Edit at the marker", p is not None and p.body is last("MeshCreateFaceGroup"))
    if p is None:
        return
    m.type_field(p.brush, "3")
    h.click(FRONT)


e_paint.wait_ms = 1500


def e_delete():
    p = e.direct_panel()
    state["deleted"] = len(p.selected)
    h.check("faces painted on the front", state["deleted"] >= 2, state["deleted"])
    e.key(QtCore.Qt.Key_Delete)


e_delete.wait_ms = 1500


def e_finish():
    p = e.direct_panel()
    h.check("one edit", e.edits(p) == 1, e.edits(p))
    e.press_button(p, "finish")


e_finish.wait_ms = 2000


def e_placed():
    h.check("dialog closed", m.panel() is None)
    titles = t.titles()
    h.check("the new step is in the timeline", "Mesh Base Feature 1" in titles, titles)
    if "Mesh Base Feature 1" in titles and "Combine Face Groups 1" in titles:
        h.check(
            "it went in at the marker (before Combine Face Groups 1)",
            titles.index("Mesh Base Feature 1") < titles.index("Combine Face Groups 1"),
            titles,
        )
    states = t.states()
    h.check(
        "the new step is done",
        states.get("Mesh Base Feature 1", ("",))[0] == "done",
        states,
    )
    h.check(
        "Combine Face Groups 1 still rolled back",
        states.get("Combine Face Groups 1", ("",))[0] == "rolled_back",
        states,
    )
    combine = last("MeshCombineFaceGroups")
    edit = last("MeshDirectEdit")
    h.check(
        "Combine Face Groups 1 now builds on it",
        combine is not None and combine.Source is edit,
        combine and combine.Source,
    )
    h.check("the body at the marker has the hole", holes(body()) == 1, holes(body()))
    t.drag_marker(to_end=True)


e_placed.wait_ms = 2000


# -- F ----------------------------------------------------------------------------------------
def f_end():
    states = t.states()
    h.check("everything done", all(v[0] == "done" for v in states.values()), states)
    combine = last("MeshCombineFaceGroups")
    h.check("the body is Combine Face Groups 1", body() is combine, (body(), combine))
    h.check("with the hole", holes(body()) == 1, holes(body()))
    h.check("and six face groups", groups_of(body()) == 6, groups_of(body()))
    h.check("Combine Face Groups 1 shown", m.shown(combine))
    h.check("the Direct Edit hidden (used up)", not m.shown(last("MeshDirectEdit")))
    s.undo()


f_end.wait_ms = 2500


# -- G ----------------------------------------------------------------------------------------
def g_undone():
    h.check("Undo: no Direct Edit", m.steps("MeshDirectEdit") == [], m.steps("MeshDirectEdit"))
    combine = last("MeshCombineFaceGroups")
    h.check(
        "Combine Face Groups 1 reads Create Face Group 1 again",
        combine is not None and combine.Source is last("MeshCreateFaceGroup"),
        combine and combine.Source,
    )
    h.check("no hole", holes(body()) == 0, holes(body()))
    h.check("six face groups", groups_of(body()) == 6, groups_of(body()))
    s.redo()


g_undone.wait_ms = 2500


def g_redone():
    h.check("Redo: the Direct Edit is back", len(m.steps("MeshDirectEdit")) == 1)
    h.check("the hole is back", holes(body()) == 1, holes(body()))


g_redone.wait_ms = 1000


# -- H ----------------------------------------------------------------------------------------
def h_save_reopen():
    os.makedirs(OUT, exist_ok=True)
    state["file"] = os.path.join(OUT, "groups_reopen.FCStd")
    App.ActiveDocument.saveAs(state["file"])
    h.check("saved", os.path.isfile(state["file"]))
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(state["file"])
    h.fit()


h_save_reopen.wait_ms = 3000


def h_check():
    h.check("one mesh body", len(m.bodies()) == 1, [o.Label for o in m.bodies()])
    b = body()
    h.check("the hole", holes(b) == 1, holes(b))
    h.check("six face groups", groups_of(b) == 6, groups_of(b))
    titles = t.titles()
    wanted = [
        "Generate Face Groups 1",
        "Create Face Group 1",
        "Mesh Base Feature 1",
        "Combine Face Groups 1",
    ]
    h.check(
        "the steps in order",
        [x for x in titles if x in wanted] == wanted,
        titles,
    )
    h.shot("end")


h.run(
    "meshinspect2_groups",
    [i.new_design("MeshGroups")]
    + m.insert_file(box_file())
    + [a_open, a_ok, a_done]
    + [b_refused, b_says, b_picked, b_done]
    + [c_patch, c_right, c_refused, c_waits, c_dropped, c_combined, c_done]
    + [d_rolled]
    + [e_paint, e_delete, e_finish, e_placed]
    + [f_end, g_undone, g_redone]
    + [h_save_reopen, h_check],
)
