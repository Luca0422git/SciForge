# SPDX-License-Identifier: LGPL-2.1-or-later
"""A Join that touches nothing makes a new body (Fusion never leaves a separate piece in a
body), and the primitives' fifth operation New Component, only real input.

A 40 x 30 x 10 block (Create Sketch on XY, Extrude 10, OK).

Path J1, Extrude: a 20 x 20 rectangle sketched on XY away from the block (x 60..80, y 40..60),
         E, Operation Join picked by hand, 8: the bodies row says it touches no body and a
         new body is made; the preview is a body of its own, the block as it was. OK. Undo:
         gone; Redo: back.
Path J2, Revolve: a 10 x 5 rectangle on XY (x 50..60, y -15..-10) and a construction line
         at y = -20, Revolve, the line clicked as the axis: a tube that touches nothing, New
         Body by itself; Join picked by hand: still a body of its own, no message. OK. Its
         timeline edit reads New Body (what was made); Esc.
Path J3, Box from the block's selected top face, corners (10, 5) and (20, 15): Join by itself
         (on the part); New Component picked: Component1 appears with a body holding the
         10 x 10 x 10 box, the block as it was. OK: Component1 is active. Undo: the component
         is gone; Redo: back.
Path J4, Box on the top face again, New Component (Component2 appears), then New Body: the
         body moves out (no Component2), then Esc: nothing left.

Volumes: block 12000; J1 20*20*8 = 3200; J2 tube pi (10^2 - 5^2) 10 = 750 pi; J3 1000."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as t

V = App.Vector
PI = math.pi
BLOCK = 12000.0
st = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def block():
    return App.ActiveDocument.getObject(st["block"]) if st.get("block") else None


def block_volume():
    return s.volume(block())


def others():
    """The bodies besides the block, oldest first."""
    return [b for b in s.bodies() if b is not block()]


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def rpanel():
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last
    return p if p is not None and not p._closed else None


def bpanel():
    return pi.panel("BoxPanel")


def block_made():
    bodies = s.bodies()
    h.check("one body: the block", len(bodies) == 1 and near(s.volume(bodies[0]), BLOCK))
    if bodies:
        st["block"] = bodies[0].Name


# -- J1: Extrude, Join picked by hand, away from the block ---------------------------------------
def j1_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def j1_plane():
    h.click(V(12, -8, 0))


def j1_draw():
    sk = h.in_sketch()
    h.check("J1 sketch open on XY", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, 60, 40, 80, 60)


def j1_finish():
    h.ribbon("Finish Sketch")


def j1_extrude():
    h.fit()
    h.press("e")


def j1_join():
    p = xpanel()
    if not h.check("J1 Extrude open", p is not None):
        return
    h.check("J1 the rectangle is taken by itself", len(p.profiles) == 1, p.profiles)
    h.check("J1 choose Join", ui.choose(p.operation, "Join"))


def j1_distance():
    h.check("J1 distance typed", ai.give_distance("8"))


j1_distance.wait_ms = 1500


def j1_preview():
    p = xpanel()
    if p is None:
        return
    h.check("J1 still Join (picked)", p.operation.currentText() == "Join")
    row = p.bodies_names.text()
    h.check("J1 the bodies row says a new body is made", "Touches no body" in row, row)
    rest = others()
    h.check(
        "J1 a body of its own: 3200, the block as it was",
        len(rest) == 1 and near(s.volume(rest[0]), 3200.0) and near(block_volume(), BLOCK),
        ([s.volume(b) for b in rest], block_volume()),
    )
    h.check("J1 no message", p.message.text() == "", p.message.text())
    h.shot("j1-join-away")


def j1_ok():
    h.task_button("OK")


def j1_made():
    h.check("J1 dialog closed", not Gui.Control.activeDialog())
    rest = others()
    h.check("J1 two bodies", len(rest) == 1 and near(s.volume(rest[0]), 3200.0), len(rest))
    h.check("J1 the block as it was", near(block_volume(), BLOCK), block_volume())
    if rest:
        st["post"] = rest[0].Name


def j1_undo():
    t.undo()


def j1_undone():
    h.check("J1 Undo: one body again", others() == [], [b.Label for b in others()])
    t.redo()


def j1_redone():
    rest = others()
    h.check(
        "J1 Redo: the new body is back",
        len(rest) == 1 and near(s.volume(rest[0]), 3200.0),
        [s.volume(b) for b in rest],
    )


# -- J2: Revolve, Join picked by hand, a tube touching nothing ------------------------------------
def j2_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def j2_plane():
    h.fit()
    h.click(V(12, -8, 0))


def j2_draw():
    import Part

    sk = h.in_sketch()
    h.check("J2 sketch on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane")
    if sk is not None:
        h.draw_rectangle(sk, 50, -15, 60, -10)
        sk.addGeometry(Part.LineSegment(V(45, -20, 0), V(65, -20, 0)), True)  # construction
        App.ActiveDocument.recompute()
        st["ring_sketch"] = sk.Name
        st["count"] = len(s.bodies())


def j2_finish():
    h.ribbon("Finish Sketch")


def j2_revolve():
    h.fit()
    h.ribbon("Revolve")


def j2_axis():
    p = rpanel()
    h.check("J2 Revolve open, the rectangle taken", p is not None and len(p.profiles) == 1)
    h.fit()
    h.click(V(63, -20, 0))


def j2_auto():
    p = rpanel()
    if p is None:
        return
    sketch = App.ActiveDocument.getObject(st["ring_sketch"])
    h.check(
        "J2 the construction line is the axis",
        p.axis is not None and p.axis[0] is sketch,
        p.axis,
    )
    h.check(
        "J2 touches nothing: New Body by itself",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    h.check("J2 choose Join", ui.choose(p.operation, "Join"))


j2_auto.wait_ms = 1500


def j2_join():
    p = rpanel()
    if p is None:
        return
    h.check("J2 Join stays picked", p.operation.currentText() == "Join")
    h.check(
        "J2 still a body of its own (Fusion: never a second lump)",
        len(s.bodies()) == st["count"] + 1,
        [b.Label for b in s.bodies()],
    )
    ring = s.bodies()[-1]
    h.check("J2 the tube: 750 pi", near(s.volume(ring), 750 * PI), s.volume(ring))
    h.check("J2 the block as it was", near(block_volume(), BLOCK), block_volume())
    h.check("J2 no message", p.message.text() == "", p.message.text())
    h.shot("j2-revolve-join-away")


def j2_ok():
    h.task_button("OK")


def j2_made():
    h.check("J2 dialog closed", not Gui.Control.activeDialog())
    h.check("J2 one more body", len(s.bodies()) == st["count"] + 1, len(s.bodies()))
    ring = s.bodies()[-1]
    h.check("J2 kept: 750 pi", near(s.volume(ring), 750 * PI), s.volume(ring))
    st["ring"] = ring.Name


def j2_edit():
    titles = [x for x in t.titles() if x.startswith("Revolve")]
    h.check("J2 the revolve is in the timeline", len(titles) == 1, t.titles())
    if titles:
        t.double_click(titles[0])


def j2_edit_reads():
    p = rpanel()
    if not h.check("J2 the edit dialog is open", p is not None):
        return
    h.check(
        "J2 it reads New Body (what was made)",
        p.operation.currentText() == "New Body",
        p.operation.currentText(),
    )
    h.press(QtCore.Qt.Key_Escape)


def j2_after_edit():
    h.check("J2 Esc closed it", not Gui.Control.activeDialog())
    ring = App.ActiveDocument.getObject(st["ring"])
    h.check("J2 the tube unchanged", near(s.volume(ring), 750 * PI), s.volume(ring))


# -- J3: Box with New Component ------------------------------------------------------------------
def j3_select_top():
    h.click_empty()
    h.fit()
    h.click(V(30, 22, 10))


def j3_box():
    h.check("J3 the block's top selected", bool(Gui.Selection.getSelectionEx()))
    st["count"] = len(s.bodies())
    pi.menu("Box")


def j3_corner_a():
    p = bpanel()
    h.check("J3 the face is taken at once", p is not None and p.state == "place", p and p.state)
    h.click(V(10, 5, 10))


def j3_corner_b():
    h.click(V(20, 15, 10))


j3_corner_b.wait_ms = 1200


def j3_join_first():
    p = bpanel()
    if p is None:
        return
    h.check(
        "J3 on the part: Join by itself",
        p.operation.currentText() == "Join",
        p.operation.currentText(),
    )
    labels = [p.operation.itemText(i) for i in range(p.operation.count())]
    h.check(
        "J3 Fusion's five operations",
        labels == ["Join", "Cut", "Intersect", "New Body", "New Component"],
        labels,
    )
    h.check("J3 choose New Component", ui.choose(p.operation, "New Component"))


j3_join_first.wait_ms = 1500


def j3_preview():
    p = bpanel()
    if p is None:
        return
    part = cs.component("Component1")
    h.check("J3 Component1 appears", part is not None, [c.Label for c in cs.components()])
    inside = [b for b in s.bodies() if cs.container_label(b) == "Component1"]
    h.check(
        "J3 a body in it holding the box: 1000",
        len(inside) == 1 and near(s.volume(inside[0]), 1000.0),
        [s.volume(b) for b in inside],
    )
    h.check("J3 the block as it was", near(block_volume(), BLOCK), block_volume())
    h.check("J3 no message", p.message.text() == "", p.message.text())
    h.shot("j3-new-component")


def j3_ok():
    h.task_button("OK")


def j3_made():
    h.check("J3 dialog closed", pi.no_dialog())
    inside = [b for b in s.bodies() if cs.container_label(b) == "Component1"]
    h.check("J3 kept in Component1", len(inside) == 1, [b.Label for b in s.bodies()])
    h.check("J3 Component1 is active", cs.active_label() == "Component1", cs.active_label())
    h.check(
        "J3 the timeline shows the box",
        any(x.startswith("Box") for x in t.titles()),
        t.titles(),
    )
    h.check("J3 the block as it was", near(block_volume(), BLOCK), block_volume())


def j3_undo():
    t.undo()


def j3_undone():
    h.check("J3 Undo: Component1 is gone", cs.component("Component1") is None)
    h.check("J3 Undo: its body too", len(s.bodies()) == st["count"], len(s.bodies()))
    t.redo()


def j3_redone():
    h.check("J3 Redo: Component1 is back", cs.component("Component1") is not None)
    inside = [b for b in s.bodies() if cs.container_label(b) == "Component1"]
    h.check(
        "J3 Redo: with the box",
        len(inside) == 1 and near(s.volume(inside[0]), 1000.0),
        [s.volume(b) for b in inside],
    )


# -- J4: New Component, then New Body, then Esc ---------------------------------------------
def j4_select_top():
    h.click_empty()
    h.fit()
    h.click(V(30, 22, 10))


def j4_box():
    st["count"] = len(s.bodies())
    st["objects"] = len(App.ActiveDocument.Objects)
    pi.menu("Box")


def j4_corner_a():
    h.click(V(25, 5, 10))


def j4_corner_b():
    h.click(V(35, 15, 10))


j4_corner_b.wait_ms = 1200


def j4_new_component():
    p = bpanel()
    if h.check("J4 Box placed", p is not None and p.state == "ready", p and p.state):
        h.check("J4 choose New Component", ui.choose(p.operation, "New Component"))


j4_new_component.wait_ms = 1500


def j4_component():
    h.check("J4 Component2 appears", cs.component("Component2") is not None)
    p = bpanel()
    if p is not None:
        h.check("J4 choose New Body", ui.choose(p.operation, "New Body"))


j4_component.wait_ms = 1500


def j4_new_body():
    h.check(
        "J4 New Body: the body leaves the component (Component2 gone)",
        cs.component("Component2") is None,
        [c.Label for c in cs.components()],
    )
    new = [b for b in s.bodies() if near(s.volume(b), 1000.0) and cs.container_label(b) is None]
    h.check("J4 a body of 1000 beside the block", len(new) == 1, [b.Label for b in s.bodies()])
    h.press(QtCore.Qt.Key_Escape)


def j4_esc():
    h.check("J4 Esc closed it", pi.no_dialog())
    h.check("J4 nothing left", len(s.bodies()) == st["count"], len(s.bodies()))
    h.check("J4 no new objects", len(App.ActiveDocument.Objects) == st["objects"])
    h.check("J4 one component", [c.Label for c in cs.components()] == ["Component1"])
    h.check("J4 the block as it was", near(block_volume(), BLOCK), block_volume())
    h.fit()
    h.shot("j4-end")


h.run(
    "gaps_join_new_body",
    t.watched(
        [s.new_design("GapsJoinNewBody")]
        + s.box_steps("block", (0, 0, 40, 30), 10, V(12, -8, 0))
        + [
            block_made,
            j1_sketch,
            j1_plane,
            j1_draw,
            j1_finish,
            j1_extrude,
            j1_join,
            j1_distance,
            j1_preview,
            j1_ok,
            j1_made,
            j1_undo,
            j1_undone,
            j1_redone,
            j2_sketch,
            j2_plane,
            j2_draw,
            j2_finish,
            j2_revolve,
            j2_axis,
            j2_auto,
            j2_join,
            j2_ok,
            j2_made,
            j2_edit,
            j2_edit_reads,
            j2_after_edit,
            j3_select_top,
            j3_box,
            j3_corner_a,
            j3_corner_b,
            j3_join_first,
            j3_preview,
            j3_ok,
            j3_made,
            j3_undo,
            j3_undone,
            j3_redone,
            j4_select_top,
            j4_box,
            j4_corner_a,
            j4_corner_b,
            j4_new_component,
            j4_component,
            j4_new_body,
            j4_esc,
        ]
    ),
)
