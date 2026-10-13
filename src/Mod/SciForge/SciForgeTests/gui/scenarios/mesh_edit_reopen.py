# SPDX-License-Identifier: LGPL-2.1-or-later
"""A mesh body's history: Repair then Shell, saved, reopened, edited from the timeline, a step
deleted from the middle, saved with Ctrl+S and reopened; only real input.

A  Insert Mesh broken_box.stl (20 x 10 x 5, a hole, flipped and doubled faces); MESH > Repair
   with it picked, Preview, OK: "Repair 1", 1000 mm3.
B  MESH > Shell: Thickness 2 mm (the default); Thickness 3: the dialog says the wall does not
   fit (the body is 5 mm thin: under 2.50 mm), OK waits; Thickness 1 with Preview: 568 mm3
   (an 18 x 8 x 3 hollow inside), closed, two shells; OK: "Shell 1".
C  Save as mesh_reopen.FCStd, close, open it again: one mesh body, 568 mm3, drawn (a click on
   it picks it), no warning; the timeline Insert Mesh 1, Repair 1, Shell 1.
D  Timeline double-click Shell 1: Thickness 1 mm; 2 mm, OK: 904 mm3.
E  Timeline right-click Repair 1 > Delete: Shell 1 now reads the broken mesh, cannot shell it
   and says so in the timeline (Repair first); the body is the broken mesh, flagged in the
   browser. Ctrl+Z: Repair 1 back, 904 mm3.
F  Ctrl+S (the Save dialog: Enter), close, open again: 904 mm3, Shell 1 still 2 mm.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m
from SciForgeTests.gui import versions_input as vi

NAME = "broken_box"
OUT = os.path.join(i.OUT, "mesh_edit_reopen")
state = {}


def near(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol


def body():
    return m.body(NAME)


def shell_step():
    found = m.steps("MeshShell")
    return found[0] if found else None


# -- A ----------------------------------------------------------------------------------------
def a_repair():
    m.mesh_tab()
    h.fit()
    s.click_browser_row(NAME)
    h.ribbon("Repair")


a_repair.wait_ms = 1500


def a_preview():
    p = m.panel()
    h.check("Repair dialog with the body", p is not None and p.body is not None, p)
    m.tick(p.preview, True)


a_preview.wait_ms = 1500


def a_ok():
    h.task_button("OK")


a_ok.wait_ms = 1200


def a_done():
    b = body()
    h.check(
        "Repair 1, 1000 mm3",
        b is not None and b.SciForgeType == "MeshRepair" and near(m.volume(b), 1000.0),
        b and m.volume(b),
    )


# -- B ----------------------------------------------------------------------------------------
def b_open():
    s.click_browser_row(NAME)
    s.menu("MODIFY", "Shell")


b_open.wait_ms = 1500


def b_too_thick():
    p = m.panel()
    h.check("Shell dialog", p is not None and p.title == "Shell", p)
    if p is None:
        return
    h.check("Thickness 2 mm", near(p.thickness.value(), 2.0), p.thickness.value())
    m.tick(p.preview, True)
    m.type_field(p.thickness.widget, "3")


b_too_thick.wait_ms = 2000


def b_refused():
    p = m.panel()
    text = p.message.text()
    h.check("the wall does not fit, under 2.50 mm", "does not fit" in text and "2.50" in text, text)
    h.task_button("OK")


b_refused.wait_ms = 1200


def b_waits():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Shell", p)
    m.type_field(p.thickness.widget, "1")


b_waits.wait_ms = 2000


def b_check():
    step = shell_step()
    h.check("568 mm3", near(m.volume(step), 568.0), m.volume(step))
    info = m.analysis(step)
    h.check("closed, two shells", info["closed"] and info["shells"] == 2, info)
    h.check("no warning", m.panel().message.text() == "", m.panel().message.text())
    h.task_button("OK")


b_check.wait_ms = 1500


def b_done():
    b = body()
    h.check(
        "timeline: Shell 1",
        b is not None and m.timeline_title(b) == "Shell 1",
        b and m.timeline_title(b),
    )


# -- C ----------------------------------------------------------------------------------------
def c_save_reopen():
    os.makedirs(OUT, exist_ok=True)
    state["file"] = os.path.join(OUT, "mesh_reopen.FCStd")
    App.ActiveDocument.saveAs(state["file"])
    h.check("saved", os.path.isfile(state["file"]))
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(state["file"])
    m.mesh_tab()
    h.fit()


c_save_reopen.wait_ms = 3000


def c_check():
    b = body()
    h.check("one mesh body", b is not None and len(m.bodies()) == 1, m.browser_labels())
    if b is None:
        return
    h.check("568 mm3", near(m.volume(b), 568.0), m.volume(b))
    h.check(
        "still a step of its own kind",
        type(b.Proxy).__name__ == "MeshStep" and b.SciForgeType == "MeshShell",
        b.Proxy,
    )
    h.check(
        "drawn",
        b.ViewObject is not None
        and type(b.ViewObject.Proxy).__name__ == "MeshStepView"
        and b.ViewObject.DisplayMode == "Shaded",
        b.ViewObject and b.ViewObject.DisplayMode,
    )
    node = m.browser_node(NAME)
    h.check(
        "no warning",
        node is not None and node["status"] == "ok",
        node and (node["status"], node["tip"]),
    )
    titles = [m.timeline_title(o) for o in (b.Source.Source, b.Source, b)]
    h.check(
        "timeline Insert Mesh 1, Repair 1, Shell 1",
        titles == ["Insert Mesh 1", "Repair 1", "Shell 1"],
        titles,
    )
    m.click_body(b)


c_check.wait_ms = 1200


def c_picked():
    picked = [x.Object.Name for x in Gui.Selection.getSelectionEx()]
    h.check("a click on it picks it", body() is not None and body().Name in picked, picked)
    h.press(QtCore.Qt.Key_Escape)  # nothing picked any more


# -- D ----------------------------------------------------------------------------------------
def d_edit():
    s.timeline_double_click(shell_step())


d_edit.wait_ms = 2000


def d_dialog():
    p = m.panel()
    h.check("Edit Shell after reopen", p is not None and p.title == "Shell", p)
    if p is None:
        return
    h.check("Thickness 1 mm", near(p.thickness.value(), 1.0), p.thickness.value())
    m.type_field(p.thickness.widget, "2")


d_dialog.wait_ms = 2000


def d_ok():
    h.task_button("OK")


d_ok.wait_ms = 1500


def d_check():
    h.check("dialog closed", m.panel() is None)
    h.check("904 mm3", near(m.volume(body()), 904.0), m.volume(body()))


# -- E ----------------------------------------------------------------------------------------
def e_delete():
    hs.timeline_menu("Repair 1", "Delete")


e_delete.wait_ms = 2000


def e_check():
    h.check("no Repair step", not m.steps("MeshRepair"))
    step = shell_step()
    h.check(
        "Shell 1 reads the inserted mesh",
        step is not None and step.Source is not None and step.Source.TypeId == "Mesh::Feature",
        step and step.Source,
    )
    from sciforge import mesh

    why = mesh.problem(step)
    h.check("Shell 1 says why (Repair first)", "Repair" in why, why)
    h.check(
        "the body is the broken mesh",
        m.facets(body()) == 12 and not m.closed(body()),
        m.facets(body()),
    )
    node = m.browser_node(NAME)
    h.check(
        "the browser flags it",
        node is not None and node["status"] == "warning",
        node and node["status"],
    )
    h.check(
        "the inserted mesh stays hidden (Shell 1 uses it)",
        not m.shown(step.Source) if step is not None else False,
    )


def e_undo():
    i.undo()


e_undo.wait_ms = 2000


def e_check_undo():
    h.check("Ctrl+Z: Repair 1 back", len(m.steps("MeshRepair")) == 1)
    step = shell_step()
    h.check(
        "Shell 1 reads Repair 1 again",
        step is not None and getattr(step.Source, "SciForgeType", "") == "MeshRepair",
        step and step.Source,
    )
    h.check("904 mm3 again", near(m.volume(body()), 904.0), m.volume(body()))
    from sciforge import mesh

    h.check("no warning on Shell 1", mesh.problem(step) == "", mesh.problem(step))


# -- F ----------------------------------------------------------------------------------------
def f_save():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


f_save.wait_ms = 1500


def f_describe():
    h.check("the Save dialog asks for a description", vi.version_dialog() is not None)
    vi.accept_save()


f_describe.wait_ms = 1500


def f_reopen():
    h.check("saved", not Gui.ActiveDocument.Modified)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(state["file"])
    h.fit()


f_reopen.wait_ms = 3000


def f_check():
    b = body()
    h.check(
        "904 mm3 after reopening", b is not None and near(m.volume(b), 904.0), b and m.volume(b)
    )
    step = shell_step()
    h.check(
        "Shell 1 still 2 mm",
        step is not None and near(float(step.Thickness), 2.0),
        step and step.Thickness,
    )
    h.check("Repair 1 is there", len(m.steps("MeshRepair")) == 1)
    h.shot("end")


h.run(
    "mesh_edit_reopen",
    [i.new_design("MeshReopen")]
    + m.insert_file(m.broken_box_stl())
    + [a_repair, a_preview, a_ok, a_done]
    + [b_open, b_too_thick, b_refused, b_waits, b_check, b_done]
    + [c_save_reopen, c_check, c_picked]
    + [d_edit, d_dialog, d_ok, d_check, e_delete, e_check, e_undo, e_check_undo]
    + [f_save, f_describe, f_reopen, f_check],
)
