# SPDX-License-Identifier: LGPL-2.1-or-later
"""Direct Edit again: Free Form selection, the palette's expand / invert / shrink, Reverse
Normal and Erase and Fill of single faces, editing the step from the timeline (Remove Last
Edit and Cancel keep it as it was), Esc, and the edits after saving and opening the design
again; a sphere STL (r 10, 2208 triangles), only real input.

A  MODIFY > Direct Edit, Selection Free Form: drawing round the face that looks at you takes
   faces facing you; Alt+C (Expand To Connected): every face of the sphere; Alt+N (Invert):
   none; Alt+N again: all; Clear.
B  Paint (brush 4 mm) the front, Shift+Down (Shrink): fewer; Reverse Normal: those faces are
   turned over (the sphere has faces pointing the other way now).
C  Paint the upper right, Erase and Fill Type Minimal: the gap is closed (no hole), fewer
   faces. Finish Direct Edit: "Mesh Base Feature 1" with two edits.
D  Double-click it in the timeline: the dialog lists the two edits; Remove Last Edit: the
   body shows one; Cancel: two edits, the body as before.
E  Double-click again: paint the lower left, Del, OK: three edits, one hole.
F  A new Direct Edit on the body: paint, Del, then Esc: no new step, the body as it was.
G  Saved, closed, opened again: the step keeps its three edits and its faces; the timeline's
   double-click lists them.
"""

import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m
from SciForgeTests.gui import meshinspect2_steps as e

NAME = "rsphere"
OUT = os.path.join(i.OUT, "meshinspect2_reedit")
state = {}


def sphere_file():
    return m.write_stl("rsphere.stl", m.sphere_triangles(10.0, 24))


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


def a_free_form():
    p = e.direct_panel()
    h.check("Direct Edit dialog", p is not None, m.panel())
    if p is None:
        return
    e.choose(p, "selection", "Free Form")
    h.check("Free Form chosen", p.selection_type() == "Free Form", p.selection_type())
    h.check("the brush is off for it", not p.brush.widget.isEnabled())


a_free_form.wait_ms = 800


def a_lasso():
    e.lasso(e.on_sphere(), 45)


a_lasso.wait_ms = 1500


def a_lassoed():
    p = e.direct_panel()
    state["lasso"] = len(p.selected)
    h.check("Free Form takes faces", state["lasso"] >= 4, state["lasso"])
    h.check("facing you", e.facing_all(p, p.selected))
    e.key(QtCore.Qt.Key_C, QtCore.Qt.AltModifier)


a_lassoed.wait_ms = 1200


def a_connected():
    p = e.direct_panel()
    h.check("Alt+C: every face of the sphere", len(p.selected) == state["faces"], len(p.selected))
    e.key(QtCore.Qt.Key_N, QtCore.Qt.AltModifier)


a_connected.wait_ms = 1200


def a_inverted():
    p = e.direct_panel()
    h.check("Alt+N: none", p.selected == [], len(p.selected))
    e.key(QtCore.Qt.Key_N, QtCore.Qt.AltModifier)


a_inverted.wait_ms = 1200


def a_all():
    p = e.direct_panel()
    h.check("Alt+N again: all", len(p.selected) == state["faces"], len(p.selected))
    e.press_button(p, "clear")
    e.choose(p, "selection", "Paint")
    m.type_field(p.brush, "4")


a_all.wait_ms = 800


# -- B ----------------------------------------------------------------------------------------
def b_paint():
    h.click(e.on_sphere())


b_paint.wait_ms = 1200


def b_shrink():
    p = e.direct_panel()
    state["painted"] = len(p.selected)
    h.check("painted", state["painted"] >= 6, state["painted"])
    e.key(QtCore.Qt.Key_Down, QtCore.Qt.ShiftModifier)


b_shrink.wait_ms = 1200


def b_reverse():
    p = e.direct_panel()
    state["shrunk"] = len(p.selected)
    h.check(
        "Shift+Down: fewer",
        0 < state["shrunk"] < state["painted"],
        (state["shrunk"], state["painted"]),
    )
    e.press_button(p, "reverse")


b_reverse.wait_ms = 1500


def b_reversed():
    p = e.direct_panel()
    info = m.analysis(step())
    h.check("faces turned over", info.get("flipped", 0) > 0, info)
    h.check("same faces", m.facets(step()) == state["faces"], m.facets(step()))
    h.check("one edit", e.edits(p) == 1, e.edits(p))
    e.press_button(p, "clear")


b_reversed.wait_ms = 800


# -- C ----------------------------------------------------------------------------------------
def c_paint():
    h.click(e.on_sphere(0.55, 0.45))


c_paint.wait_ms = 1200


def c_fill():
    p = e.direct_panel()
    h.check("painted the upper right", len(p.selected) >= 3, len(p.selected))
    e.choose(p, "fill", "Minimal")
    e.press_button(p, "erase_fill")


c_fill.wait_ms = 2000


def c_filled():
    p = e.direct_panel()
    st = step()
    h.check("the gap is closed", m.analysis(st)["holes"] == 0, m.analysis(st))
    h.check("fewer faces (Minimal)", m.facets(st) < state["faces"], m.facets(st))
    h.check("two edits", e.edits(p) == 2, e.edits(p))
    state["after_c"] = m.facets(st)
    e.press_button(p, "finish")


c_filled.wait_ms = 2000


def c_done():
    st = step()
    h.check("dialog closed", m.panel() is None)
    h.check(
        "timeline: Mesh Base Feature 1",
        st is not None and m.timeline_title(st) == "Mesh Base Feature 1",
        st and m.timeline_title(st),
    )
    h.check("two edits kept", st is not None and len(st.Edits) == 2, st and list(st.Edits))
    s.timeline_double_click(st)


c_done.wait_ms = 2000


# -- D ----------------------------------------------------------------------------------------
def d_listed():
    p = e.direct_panel()
    h.check("the step opens again", p is not None and p.editing, m.panel())
    if p is None:
        return
    h.check("its two edits listed", e.edits(p) == 2, e.edits(p))
    h.check("Erase and Fill last", "Erase and Fill" in p.edit_list.item(1).text())
    e.press_button(p, "remove_last")


d_listed.wait_ms = 2000


def d_removed():
    p = e.direct_panel()
    h.check("one edit left", e.edits(p) == 1, e.edits(p))
    h.check("the body shows it", m.facets(step()) == state["faces"], m.facets(step()))
    h.task_button("Cancel")


d_removed.wait_ms = 2000


def d_cancelled():
    st = step()
    h.check("Cancel: dialog closed", m.panel() is None)
    h.check("still two edits", len(st.Edits) == 2, list(st.Edits))
    h.check("the body as before", m.facets(st) == state["after_c"], m.facets(st))
    s.timeline_double_click(st)


d_cancelled.wait_ms = 2000


# -- E ----------------------------------------------------------------------------------------
def e_paint():
    p = e.direct_panel()
    h.check("opened again", p is not None and e.edits(p) == 2, p and e.edits(p))
    h.click(e.on_sphere(-0.5, -0.45))


e_paint.wait_ms = 1200


def e_delete():
    p = e.direct_panel()
    h.check("painted the lower left", len(p.selected) >= 3, len(p.selected))
    e.key(QtCore.Qt.Key_Delete)


e_delete.wait_ms = 1500


def e_ok():
    p = e.direct_panel()
    h.check("three edits", e.edits(p) == 3, e.edits(p))
    h.task_button("OK")


e_ok.wait_ms = 2000


def e_kept():
    st = step()
    h.check("OK: dialog closed", m.panel() is None)
    h.check("three edits kept", len(st.Edits) == 3, list(st.Edits))
    h.check("one hole", m.analysis(st)["holes"] == 1, m.analysis(st))
    h.check("still one Direct Edit step", len(m.steps("MeshDirectEdit")) == 1)
    state["after_e"] = m.facets(st)
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Direct Edit")


e_kept.wait_ms = 1500


# -- F ----------------------------------------------------------------------------------------
def f_paint():
    p = e.direct_panel()
    h.check("a new Direct Edit", p is not None and not p.editing, m.panel())
    h.click(e.on_sphere(0.3, -0.3))


f_paint.wait_ms = 1200


def f_delete():
    e.key(QtCore.Qt.Key_Delete)


f_delete.wait_ms = 1500


def f_escape():
    p = e.direct_panel()
    h.check("its edit is shown", p is not None and e.edits(p) == 1, p and e.edits(p))
    h.press(QtCore.Qt.Key_Escape)


f_escape.wait_ms = 2000


def f_gone():
    h.check("Esc: dialog closed", m.panel() is None, m.panel())
    h.check("no new step", len(m.steps("MeshDirectEdit")) == 1, m.steps("MeshDirectEdit"))
    h.check("the body as it was", m.facets(body()) == state["after_e"], m.facets(body()))
    h.check("the body is the first step", body() is step(), (body(), step()))


f_gone.wait_ms = 800


# -- G ----------------------------------------------------------------------------------------
def g_save_reopen():
    os.makedirs(OUT, exist_ok=True)
    state["file"] = os.path.join(OUT, "reedit.FCStd")
    App.ActiveDocument.saveAs(state["file"])
    h.check("saved", os.path.isfile(state["file"]))
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(state["file"])
    h.fit()


g_save_reopen.wait_ms = 3000


def g_check():
    st = step()
    h.check("the step is there", st is not None)
    if st is None:
        return
    h.check("three edits after reopening", len(st.Edits) == 3, list(st.Edits))
    h.check("the same faces", m.facets(st) == state["after_e"], m.facets(st))
    h.check("it is the body", body() is st, body())
    s.timeline_double_click(st)


g_check.wait_ms = 2000


def g_listed():
    p = e.direct_panel()
    h.check("the dialog lists the three edits", p is not None and e.edits(p) == 3, p and e.edits(p))
    h.task_button("Cancel")


g_listed.wait_ms = 1500


def g_end():
    h.check("closed", m.panel() is None)
    h.shot("end")


h.run(
    "meshinspect2_reedit",
    [i.new_design("MeshReedit")]
    + m.insert_file(sphere_file())
    + [a_open, a_free_form, a_lasso, a_lassoed, a_connected, a_inverted, a_all]
    + [b_paint, b_shrink, b_reverse, b_reversed]
    + [c_paint, c_fill, c_filled, c_done]
    + [d_listed, d_removed, d_cancelled]
    + [e_paint, e_delete, e_ok, e_kept]
    + [f_paint, f_delete, f_escape, f_gone]
    + [g_save_reopen, g_check, g_listed, g_end],
)
