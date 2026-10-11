# SPDX-License-Identifier: LGPL-2.1-or-later
"""The small buttons and keys of the CONSTRUCT and INSPECT dialogs, third QA round (only real
input). Each path is what Fusion does, checked on the design:

  K  Plane Through Three Points on three top corners (0,0,10), (40,0,10), (40,30,10): the top
     plane (z = 10). The x of the third box clicked: the preview goes, that box waits (blue);
     the corner (40,0,0) clicked instead: the front plane (y = 0). OK.
  E  Edited from the timeline: the x of the second box clicked, OK refused (the dialog stays
     and says what to click, no pop-up), Cancel: the plane is the front plane as before and
     the undo list is unchanged.
  X  Axis Through Two Points: the origin's dot and the corner (40, 30, 10): the axis runs
     through both. OK. Ctrl+Z takes the axis (and its hidden helper) away, Ctrl+Y brings it
     back where it was.
  C  Center of Mass with the box clicked (20, 15, 5); the x clicked: all visible bodies, the
     same centre (one body); OK. A second one, then Ctrl+Z inside its dialog: cancelled,
     nothing added.

Part: box 40 x 30 x 10 from the origin (real input).
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}


def doc():
    return App.ActiveDocument


def obj(key):
    return doc().getObject(st[key]) if st.get(key) else None


def helpers():
    from sciforge import construct

    return [o.Name for o in doc().Objects if construct.is_helper(o)]


def base_of(o):
    return o.getGlobalPlacement().Base


def unit_normal(o):
    n = s.normal_of(o)
    return V(abs(n.x), abs(n.y), abs(n.z))


def snapshot():
    return {
        "objects": sorted(o.Name for o in doc().Objects),
        "undo": list(doc().UndoNames),
    }


def coms():
    from sciforge import analysis

    return analysis.of_kind(doc(), analysis.COM_KIND)


# -- K: Plane Through Three Points, a box cleared with its x --------------------------------------
def k_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Plane Through Three Points")


def k_p1():
    h.fit()
    s.click_vertex(V(0, 0, 10))


def k_p2():
    s.click_vertex(V(40, 0, 10))


def k_p3():
    s.click_vertex(V(40, 30, 10))


def k_top():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("K three corners: a plane", d is not None, p and p.picks)
    if d is None:
        return
    h.check("K the top plane", s.near(unit_normal(d), V(0, 0, 1)), s.normal_of(d))
    h.check("K at z = 10", s.close(base_of(d).z, 10.0), base_of(d))
    di.click(p.boxes[2].clear)


def k_cleared():
    p = s.construct_panel()
    if p is None:
        h.check("K still open", False)
        return
    h.check("K the third box is empty", p.picks[2] is None, p.picks)
    h.check("K ...and waits (blue)", p.active == 2 and p.boxes[2].button.isChecked())
    h.check("K the preview is gone", p.datum is None and not s.datums(), s.datums())
    h.check("K no helper left", not helpers(), helpers())
    h.check("K it says what to click", "Click" in p.message.text(), p.message.text())
    s.click_vertex(V(40, 0, 0))


def k_front():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("K a plane again", d is not None)
    if d is None:
        return
    h.check("K the front plane now", s.near(unit_normal(d), V(0, 1, 0)), s.normal_of(d))
    h.check("K at y = 0", s.close(base_of(d).y, 0.0), base_of(d))
    h.task_button("OK")


def k_made():
    planes = s.datums("PartDesign::Plane")
    h.check("K Plane1 made", [o.Label for o in planes] == ["Plane1"], planes)
    h.check("K dialog closed", not Gui.Control.activeDialog())
    if planes:
        st["k"] = planes[0].Name
        st["k_place"] = planes[0].getGlobalPlacement()


# -- E: edited, a box cleared, OK refused, Cancel -------------------------------------------------
def e_edit():
    st["e"] = snapshot()
    s.double_click_timeline(obj("k"))


def e_clear():
    p = s.construct_panel()
    h.check("E the edit opens", p is not None and p.editing)
    if p is None:
        return
    h.check("E with its three corners", all(p.picks), p.picks)
    di.click(p.boxes[1].clear)


def e_ok():
    p = s.construct_panel()
    if p is not None:
        h.check("E the second box waits", p.picks[1] is None and p.active == 1, p.picks)
    h.task_button("OK")


def e_refused():
    p = s.construct_panel()
    h.check("E OK waits for the missing corner", p is not None)
    s.no_popups("OK with a box empty")
    if p is None:
        return
    h.check("E it says what to click", "Click" in p.message.text(), p.message.text())
    h.task_button("Cancel")


def e_cancelled():
    h.check("E Cancel closed it", not Gui.Control.activeDialog())
    plane = obj("k")
    h.check("E the plane is still there", plane is not None)
    if plane is not None:
        h.check(
            "E ...where it was",
            plane.getGlobalPlacement().isSame(st["k_place"], 1e-9),
            (plane.getGlobalPlacement(), st["k_place"]),
        )
        h.check("E ...on its three corners", len(helpers()) == 1, helpers())
    now = snapshot()
    h.check("E same objects", now["objects"] == st["e"]["objects"], now["objects"])
    h.check("E same undo list", now["undo"] == st["e"]["undo"], now["undo"])
    s.eye("Plane1")


# -- X: Axis Through Two Points from the origin's dot, Ctrl+Z / Ctrl+Y --------------------------
def x_start():
    h.click_empty()
    s.menu("CONSTRUCT", "Axis Through Two Points")


def x_origin():
    h.fit()
    p = s.construct_panel()
    h.check("X the origin's dot is drawn to click", p is not None and "point" in p.overlays)
    h.click(V(0, 0, 0))


def x_corner():
    p = s.construct_panel()
    if p is not None:
        h.check("X the origin taken", "Origin" in s.box_value(p, 0), s.box_value(p, 0))
    s.click_vertex(V(40, 30, 10))


def x_preview():
    p = s.construct_panel()
    d = p.datum if p else None
    h.check("X an axis", d is not None, p and p.picks)
    if d is None:
        return
    direction = d.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    want = V(40, 30, 10)
    want.normalize()
    h.check("X along origin -> corner", abs(abs(direction.dot(want)) - 1.0) < 1e-9, direction)
    h.check(
        "X through the origin",
        (base_of(d) - want * base_of(d).dot(want)).Length < 1e-9,
        base_of(d),
    )
    h.task_button("OK")


def x_made():
    axes = s.datums("PartDesign::Line")
    h.check("X Axis1 made", [o.Label for o in axes] == ["Axis1"], axes)
    if not axes:
        return
    st["x"] = axes[0].Name
    st["x_place"] = axes[0].getGlobalPlacement()
    st["x_helpers"] = len(helpers())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def x_undone():
    h.check("X Ctrl+Z: the axis is gone", obj("x") is None, s.datums())
    h.check("X ...and its helper", len(helpers()) == st.get("x_helpers", 0) - 1, helpers())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def x_redone():
    axis = obj("x")
    h.check("X Ctrl+Y: the axis is back", axis is not None)
    if axis is not None:
        h.check(
            "X ...where it was",
            axis.getGlobalPlacement().isSame(st["x_place"], 1e-9),
            axis.getGlobalPlacement(),
        )
    h.check("X ...with its helper", len(helpers()) == st.get("x_helpers", 0), helpers())
    s.eye("Axis1")


# -- C: Center of Mass, the x of its box; Ctrl+Z in a second one -----------------------------------
def c_start():
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def c_body():
    h.fit()
    h.click(V(30, 20, 10))


def c_picked():
    p = b.active_panel()
    if p is None or not hasattr(p, "coords"):
        h.check("C Center of Mass open", False)
        return
    h.check("C the box picked", len(p.picked) == 1, p.picked)
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("C its centre", got == ["20.000 mm", "15.000 mm", "5.000 mm"], got)
    di.click(p.box.clear)


def c_cleared():
    p = b.active_panel()
    if p is None or not hasattr(p, "coords"):
        h.check("C still open", False)
        return
    h.check("C nothing picked: all visible bodies", not p.picked, p.picked)
    h.check("C ...the box says so", "All visible" in p.box.button.text(), p.box.button.text())
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("C the same centre (one body)", got == ["20.000 mm", "15.000 mm", "5.000 mm"], got)
    h.task_button("OK")


def c_made():
    found = coms()
    h.check("C Center of Mass1 kept", [o.Label for o in found] == ["Center of Mass1"], found)
    if found:
        h.check("C of every visible body", bool(found[0].AllBodies), found[0].AllBodies)
    st["c"] = snapshot()
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def c_second():
    p = b.active_panel()
    h.check("C a second one opens", p is not None and hasattr(p, "coords"))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def c_undone():
    h.check("C Ctrl+Z in the dialog closes it", not Gui.Control.activeDialog())
    found = coms()
    h.check("C nothing added", [o.Label for o in found] == ["Center of Mass1"], found)
    now = snapshot()
    h.check("C same objects", now["objects"] == st["c"]["objects"], now["objects"])
    h.check("C same undo list", now["undo"] == st["c"]["undo"], now["undo"])
    s.no_popups("the end")
    h.shot("end")


STEPS = (
    b.box_steps("InspectQA8")
    + [k_start, k_p1, k_p2, k_p3, k_top, k_cleared, k_front, k_made]
    + [e_edit, e_clear, e_ok, e_refused, e_cancelled]
    + [x_start, x_origin, x_corner, x_preview, x_made, x_undone, x_redone]
    + [c_start, c_body, c_picked, c_cleared, c_made, c_second, c_undone]
)

h.run("inspect_qa8", ti.watched(STEPS))
