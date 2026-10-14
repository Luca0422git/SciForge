# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's joint origin Mode: Between Two Faces and Two Edge Intersection, in the Joint
Origin and Joint dialogs, with real clicks (docs/sciforge/parity/joints.md, "Position modes").

Plate = 0..40 x 0..30 x 10 with its front-right upright edge rounded (Fillet 8 mm), Block =
50..70 x 0..10 x 20.

  M1 ASSEMBLE > Joint Origin, Mode Between Two Faces: a click on the rounded face is refused
     (it needs a flat face); Plane 1 = the plate's top face, Plane 2 = its bottom face (seen
     from below); the snap box waits; a click on the top face near its centre puts the joint
     origin on the plane halfway between (z = 5), Z along the top face's normal. OK: "Joint
     Origin 1".
  M2 J: component 1 = the block's top face centre (Simple); component 2 Mode Two Edge
     Intersection: Edge 1 = the plate's top front edge, Edge 2 = its top right edge: the
     joint origin is where they meet when extended (40, 0, 10), the corner the round took
     away; the block lands there upside down (30..50 x -5..5 x 10..30). OK: "Rigid 1".
  M3 Edit Rigid 1 from the timeline: the dialog shows Two Edge Intersection with both edges;
     Offset Z 5 lifts the block; OK. Ctrl+Z undoes the edit, Ctrl+Y again.
  M4 Two parallel edges are refused (they never meet).
  M5 Save, close, reopen: the joint origin and the joint keep their places and modes.
"""

import os
import tempfile

from PySide import QtWidgets

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import joints_steps as j
from SciForgeTests.gui import timeline_input as t

V = App.Vector
Z = App.Vector(0, 0, 1)
state = {}
ROUND = 8.0
ON_CORNER = [30, -5, 10, 50, 5, 30]  # the block upside down on the virtual corner (40, 0, 10)


def jm():
    return j.joints_module()


def doc():
    return App.ActiveDocument


def joint():
    found = j.joint_list()
    return found[0] if found else None


def origin():
    found = jm().joint_origins(doc())
    return found[0] if found else None


def origin_global(obj):
    return obj.getGlobalPlacement()


# -- the rounded corner -------------------------------------------------------------------------
def fillet_open():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def fillet_edge():
    h.click_edge(V(40, 0, 5))


def fillet_radius():
    p = b.blend_panel()
    if h.check("Fillet open with an edge", p is not None and len(p.refs) == 1, p and p.refs):
        b.type_into(p.radius.widget, "%g" % ROUND)


fillet_radius.wait_ms = 1500


def fillet_ok():
    h.task_button("OK")


def fillet_done():
    plate = j.plate()
    rounds = [f for f in plate.Shape.Faces if f.Surface.TypeId == "Part::GeomCylinder"]
    h.check("the plate's corner is rounded", len(rounds) == 1, len(rounds))


fillet_done.wait_ms = 1500


# -- M1 Joint Origin, Between Two Faces -------------------------------------------------------
def m1_open():
    h.fit()
    j.menu("Joint Origin")


def m1_mode():
    p = j.panel()
    h.check("Joint Origin open", p is not None and p.title == "Joint Origin", p and p.title)
    h.check("Mode shows Simple first", p.slots["snap"].combo.currentData() == "simple")
    b.choose(p.slots["snap"].combo, "Between Two Faces")


def m1_waits_plane1():
    p = j.panel()
    h.check("Plane 1 box waits", p.active == "snap_a", p.active)
    h.check("Plane 1 / Plane 2 shown", p.fields["snap_a"].widget.isVisible())
    h.check("the hint asks for two faces", "two flat faces" in p.info.text(), p.info.text())
    h.click(V(40 - ROUND * 0.29, ROUND * 0.29, 5))  # on the rounded face


def m1_refused():
    p = j.panel()
    h.check("a rounded face is refused", "flat face" in p.message.text(), p.message.text())
    h.check("Plane 1 still waits", p.active == "snap_a" and p.slots["snap"].picks[0] is None)
    h.click(V(15, 20, 10))  # the top face


def m1_plane2():
    p = j.panel()
    h.check("Plane 1 taken, Plane 2 waits", p.active == "snap_b", p.active)
    h.view().viewBottom()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()
    h.click(V(15, 20, 0))  # the bottom face, seen from below


def m1_snap():
    p = j.panel()
    h.check("both faces taken", p.slot_of("snap").ready(), p.slots["snap"].picks)
    h.check("the snap box waits", p.active == "snap", p.active)
    h.fit()
    j.hover(V(20, 15, 10))


def m1_hover():
    p = j.panel()
    hov = p.hover
    hot = hov.hot if hov is not None else None
    h.check(
        "the hover's snaps lie on the plane between the faces",
        hov is not None
        and hov.candidates
        and all(abs(c["point"].z - 5) < 1e-6 for c in hov.candidates),
        [tuple(round(x, 3) for x in c["point"]) for c in (hov.candidates if hov else [])],
    )
    h.check("a snap is lit", hot is not None)
    h.click(V(20, 15, 10))


def m1_placed():
    o = origin()
    h.check("Joint Origin 1 made", o is not None and o.Label == "Joint Origin 1", o)
    if o is None:
        return
    plc = origin_global(o)
    top = [f for f in j.plate().Shape.Faces if abs(f.CenterOfMass.z - 10) < 1e-6]
    centre = top[0].CenterOfMass if top else V(20, 15, 10)
    h.check("halfway between the faces (z = 5)", abs(plc.Base.z - 5) < 1e-6, plc.Base)
    h.check(
        "under the top face's centre",
        abs(plc.Base.x - centre.x) < 1e-6 and abs(plc.Base.y - centre.y) < 1e-6,
        (plc.Base, centre),
    )
    h.check("Z along the top face's normal", plc.Rotation.multVec(Z).dot(Z) > 1 - 1e-9)
    state["origin"] = App.Placement(plc)


def m1_ok():
    j.ok()


def m1_done():
    j.no_dialog("Joint Origin OK")
    h.check("in the timeline", "Joint Origin 1" in t.titles(), t.titles())


# -- M2 a joint on Two Edge Intersection ------------------------------------------------------
def m2_comp2_mode():
    p = j.panel()
    h.check("component 2 waits", p is not None and p.active == "comp2", p and p.active)
    b.choose(p.slots["comp2"].combo, "Two Edge Intersection")


def m2_edge1():
    p = j.panel()
    h.check("Edge 1 waits", p.active == "comp2_a", p.active)
    h.check("no snap box in this mode", not p.fields["comp2"].widget.isVisible())
    h.check("the hint asks for two edges", "two edges" in p.info.text(), p.info.text())
    h.click_edge(V(15, 0, 10))  # the top front edge


def m2_edge2():
    p = j.panel()
    h.check("Edge 2 waits", p.active == "comp2_b", p.active)
    h.click_edge(V(40, 26, 10))  # the top right edge


m2_edge2.wait_ms = 1500


def m2_joined():
    p = j.panel()
    h.check("component 2 is the edge intersection", p.snaps["comp2"] is not None)
    snap = p.snaps["comp2"] or {}
    h.check(
        "at the corner the round took away",
        snap.get("point") is not None and (snap["point"] - V(40, 0, 10)).Length < 1e-6,
        snap.get("point"),
    )
    j.block_box("the block landed there upside down", ON_CORNER, 1e-4)


def m2_ok():
    j.ok()


def m2_done():
    j.no_dialog("Joint OK")
    jt = joint()
    h.check("Rigid 1 made", jt is not None and jt.Label == "Rigid 1", jt and jt.Label)
    rec = jm()._json(jt, jm().PROPS["snap2"])
    h.check(
        "its record keeps the two edges",
        rec.get("kind") == "twoedges" and len(rec.get("edges", [])) == 2,
        rec,
    )


# -- M3 edit from the timeline --------------------------------------------------------------
def m3_edit():
    state["undos"] = doc().UndoCount
    t.double_click("Rigid 1")


def m3_shown():
    p = j.panel()
    h.check("Edit Joint open", p is not None and p.title == "Joint", p and p.title)
    slot = p.slots["comp2"]
    h.check("component 2 shows Two Edge Intersection", slot.mode == "twoedges", slot.mode)
    h.check("both edges listed", slot.ready() and "Edge" in p.fields["comp2_a"].button.text())
    s.type_value(p.offset_fields["z"].widget, "5")


m3_shown.wait_ms = 1500


def m3_lifted():
    box = list(ON_CORNER)
    box[2] += 5
    box[5] += 5
    j.block_box("Offset Z 5 lifts the block", box, 1e-4)


def m3_ok():
    j.ok()


def m3_undo():
    j.no_dialog("edit OK")
    h.check(
        "the edit is one undo step",
        doc().UndoCount == state["undos"] + 1,
        (state["undos"], doc().UndoCount),
    )
    s.undo()


def m3_undone():
    j.block_box("Ctrl+Z: back on the corner", ON_CORNER, 1e-4)


def m3_redo():
    s.redo()


def m3_redone():
    box = list(ON_CORNER)
    box[2] += 5
    box[5] += 5
    j.block_box("Ctrl+Y: lifted again", box, 1e-4)


# -- M4 parallel edges -----------------------------------------------------------------------
def m4_open():
    h.fit()
    j.menu("Joint Origin")


def m4_mode():
    p = j.panel()
    b.choose(p.slots["snap"].combo, "Two Edge Intersection")


def m4_edge1():
    h.click_edge(V(15, 0, 10))  # the top front edge


def m4_edge2():
    h.click_edge(V(15, 0, 0))  # the bottom front edge: parallel


m4_edge2.wait_ms = 1500


def m4_refused():
    p = j.panel()
    h.check("parallel edges are refused", "parallel" in p.message.text(), p.message.text())
    h.check("nothing made", len(jm().joint_origins(doc())) == 1)


def m4_cancel():
    j.cancel()


# -- M5 save / reopen --------------------------------------------------------------------------
def m5_save_close():
    j.no_dialog("Cancel")
    state["block"] = App.Placement(j.block().Placement)
    state["path"] = os.path.join(tempfile.mkdtemp(), "joints2_modes.FCStd")
    doc().saveAs(state["path"])
    App.closeDocument(doc().Name)


def m5_open():
    App.openDocument(state["path"])
    h.fit()


def m5_reopened():
    o = origin()
    h.check("the joint origin is back", o is not None)
    if o is not None:
        h.check(
            "still halfway between the faces",
            origin_global(o).isSame(state["origin"], 1e-6),
            origin_global(o),
        )
    jt = joint()
    h.check("the joint is back", jt is not None and jt.Label == "Rigid 1")
    h.check("the block did not move", j.block().Placement.isSame(state["block"], 1e-6))
    h.check("the joint is satisfied", jt is not None and jm().satisfied(jt))
    h.check("the solver agrees", jm().solve(doc()) == 0)
    h.check("the block still did not move", j.block().Placement.isSame(state["block"], 1e-6))


steps = [s.new_design("JointsModes")]
steps += s.box_steps("plate", j.PLATE, j.PLATE_HEIGHT, V(12, -8, 0))
steps += [fillet_open, fillet_edge, fillet_radius, fillet_ok, fillet_done]
steps += s.box_steps("block", j.BLOCK, j.BLOCK_HEIGHT, V(12, -8, 0), new_body=True)
steps += [m1_open, m1_mode, m1_waits_plane1, m1_refused, m1_plane2, m1_snap, m1_hover]
steps += [m1_placed, m1_ok, m1_done]
steps += [j.pick_pair("m2")[0], j.pick_pair("m2")[1]]
steps += [m2_comp2_mode, m2_edge1, m2_edge2, m2_joined, m2_ok, m2_done]
steps += [m3_edit, m3_shown, m3_lifted, m3_ok, m3_undo, m3_undone, m3_redo, m3_redone]
steps += [m4_open, m4_mode, m4_edge1, m4_edge2, m4_refused, m4_cancel]
steps += [m5_save_close, m5_open, m5_reopened]

h.run("joints2_modes", steps)
