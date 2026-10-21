# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSERT > Hardware... like a person, only real input, on a 40 x 30 x 10 box.

A  INSERT > Hardware...: the dialog waits for a place (Socket head cap screw ISO 4762,
   M3, 10 mm, Make the hole too and Head sunk in ticked). Click the top face at (12, 8):
   a new component "M3x10 ISO 4762" with the screw appears at once, and the box gets a
   counterbored clearance hole there (measured on the box's shape: 3.4 through, 6.5 x 3.4
   counterbore); the screw's head sits on the counterbore's floor. OK.
B  Undo (application bar) removes the screw's component and the hole together; Redo brings
   both back.
C  Type Heat-set insert, click (30, 20): an M3 insert flush in a 4.0 x 6.7 hole. OK.
D  Type Magnet (6 x 3 first), click (30, 8): a 6.2 x 3 pocket, the magnet flush. OK.
E  Double-click the Hardware step of the screw in the timeline: the dialog shows it as
   left; Length 16 mm: the screw grows, the component is renamed "M3x16 ISO 4762", the
   hole stays. OK.
F  Hardware..., Heat-set insert, click the rim of the magnet's pocket (a hole that is there
   already): the insert goes on that hole's axis, "Make the hole too" goes off by itself
   and the size is read off the hole (6.2 wide: the M5 insert's 6.4 hole is the nearest),
   like Fusion's Insert Fastener with Size Automatic. Cancel: nothing changes.
Expected sizes come from the ISO tables (sciforge/hardware_core.py, unit tested).
"""

import math

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}
BOX = 12000.0
PI = math.pi
SCREW_HOLE = PI * 1.7**2 * 10 + PI * (3.25**2 - 1.7**2) * 3.4
INSERT_HOLE = PI * 2.0**2 * 6.7
MAGNET_HOLE = PI * 3.1**2 * 3.0


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


def panel():
    from sciforge import hardware_ui

    p = hardware_ui.HardwarePanel.last
    return p if p is not None and not p._closed else None


def block():
    return state.get("block")


def block_volume():
    body = block()
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def parts():
    from sciforge import hardware

    return hardware.steps(App.ActiveDocument)


def component_labels():
    from sciforge import components

    return [c.Label for c in components.list_components(App.ActiveDocument)]


def holes():
    body = block()
    return [o for o in body.Group if o.TypeId == "PartDesign::Hole"] if body else []


def centre(feature):
    """Where the part was placed (its component's origin: the hole's axis on the face). A
    click lands within a pixel of the point aimed at, so sizes are checked around this."""
    from sciforge import hardware

    return hardware.component_of(feature).getGlobalPlacement().Base


def round_faces_at(point):
    """{radius: (z min, z max)} of the box's cylindrical faces on the axis through point."""
    x, y = point.x, point.y
    found = {}
    for face in block().Shape.Faces:
        surface = face.Surface
        if surface.TypeId != "Part::GeomCylinder":
            continue
        centre = surface.Center
        if abs(centre.x - x) > 1e-6 or abs(centre.y - y) > 1e-6:
            continue
        box = face.BoundBox
        found[round(surface.Radius, 6)] = (round(box.ZMin, 6), round(box.ZMax, 6))
    return found


def global_box(feature):
    """The part's box in the design, x and y measured from where it was placed."""
    from sciforge import hardware

    shape = feature.Shape.copy()
    shape.transformShape(hardware.component_of(feature).getGlobalPlacement().toMatrix())
    b_ = shape.BoundBox
    c = centre(feature)
    return [
        round(v, 4)
        for v in (b_.XMin - c.x, b_.YMin - c.y, b_.ZMin, b_.XMax - c.x, b_.YMax - c.y, b_.ZMax)
    ]


def near_point(a, b, tol=0.5):
    return abs(a.x - b.x) <= tol and abs(a.y - b.y) <= tol and abs(a.z - b.z) <= 1e-6


def core_kind(feature):
    from sciforge import hardware

    return hardware.load_meta(feature).get("options", {}).get("kind")


def open_hardware():
    h.click_empty()
    s.menu("INSERT", "Hardware...")


# -- A ---------------------------------------------------------------------------------------------
def a_start():
    state["block"] = h.body()
    h.check("box made", close(block_volume(), BOX), block_volume())
    open_hardware()


def a_waits():
    p = panel()
    h.check("Hardware dialog open", p is not None and p.title == "Hardware")
    s.no_popups("Hardware...")
    if p is None:
        return
    types = [p.kind.itemText(i) for i in range(p.kind.count())]
    h.check("types", types == ["Screw", "Nut", "Washer", "Heat-set insert", "Magnet"], types)
    h.check("socket head first", p.standard.currentText().startswith("Socket head"))
    h.check("M3, 10 mm", (p.size.currentText(), p.length.currentText()) == ("M3", "10 mm"))
    h.check("make the hole ticked", p.make_hole.isChecked())
    h.check("head sunk in ticked", p.sink.isChecked())
    h.check("nothing made yet", p.target is None and not parts())
    h.check("Place on waits", p.place.button.isChecked())
    h.check("name M3x10 ISO 4762", p.name.text() == "M3x10 ISO 4762", p.name.text())
    h.shot("1-waiting")
    h.fit()
    h.click(V(12, 8, 10))


a_waits.wait_ms = 2500


def a_placed():
    p = panel()
    h.check("the screw is made at once", p is not None and p.target is not None)
    h.check("one part", len(parts()) == 1, len(parts()))
    h.check("component M3x10 ISO 4762", "M3x10 ISO 4762" in component_labels(), component_labels())
    h.check("one hole in the box", len(holes()) == 1, len(holes()))
    v = block_volume()
    h.check("counterbored clearance hole", close(v, BOX - SCREW_HOLE), (v, BOX - SCREW_HOLE))
    if parts():
        c = centre(parts()[0])
        h.check("the screw is where the click was", near_point(c, V(12, 8, 10)), c)
        faces = round_faces_at(c)
        h.check("clearance 3.4 from the bottom to the counterbore", faces.get(1.7) == (0.0, 6.6), faces)
        h.check("counterbore 6.5 x 3.4", faces.get(3.25) == (6.6, 10.0), faces)
        box = global_box(parts()[0])
        h.check(
            "head on the counterbore's floor", box == [-2.75, -2.75, -3.4, 2.75, 2.75, 9.6], box
        )
    h.check("hole info", "counterbore 6.5 x 3.4" in p.hole_info.text(), p and p.hole_info.text())
    h.fit()
    h.shot("2-screw")
    h.task_button("OK")


a_placed.wait_ms = 2000


def a_kept():
    h.check("dialog closed", panel() is None)
    h.check("kept", close(block_volume(), BOX - SCREW_HOLE), block_volume())
    titles = ui.timeline_titles()
    h.check("Hardware step in the timeline", any(t.startswith("Hardware") for t in titles), titles)
    h.check("Hole step in the timeline", any(t.startswith("Hole") for t in titles), titles)
    state["titles"] = titles
    s.undo()


a_kept.wait_ms = 1500


# -- B ---------------------------------------------------------------------------------------------
def b_undone():
    h.check("Undo: no screw", not parts(), len(parts()))
    h.check("Undo: no component", "M3x10 ISO 4762" not in component_labels(), component_labels())
    h.check("Undo: no hole", not holes() and close(block_volume(), BOX), block_volume())
    s.redo()


b_undone.wait_ms = 1500


def b_redone():
    h.check("Redo: the screw", len(parts()) == 1)
    h.check("Redo: its component", "M3x10 ISO 4762" in component_labels(), component_labels())
    h.check("Redo: the hole", close(block_volume(), BOX - SCREW_HOLE), block_volume())
    state["screw"] = parts()[0].Name if parts() else None
    open_hardware()


b_redone.wait_ms = 1500


# -- C ---------------------------------------------------------------------------------------------
def c_insert_type():
    p = panel()
    h.check("dialog again", p is not None)
    if p is not None:
        h.check("Heat-set insert", ui.choose(p.kind, "Heat-set insert"))


def c_click():
    p = panel()
    h.check("M3 insert", p is not None and p.size.currentText() == "M3", p and p.size.currentText())
    h.check("no length for an insert", p is not None and not p.length.isVisible())
    h.click(V(30, 20, 10))


c_click.wait_ms = 2500


def c_placed():
    v = block_volume()
    want = BOX - SCREW_HOLE - INSERT_HOLE
    h.check("insert hole 4.0 x 6.7", close(v, want), (v, want))
    new = [o for o in parts() if o.Name != state.get("screw")]
    if new:
        c = centre(new[0])
        h.check("the insert is where the click was", near_point(c, V(30, 20, 10)), c)
        faces = round_faces_at(c)
        h.check("hole 4.0 wide, 6.7 deep", faces.get(2.0) == (3.3, 10.0), faces)
        box = global_box(new[0])
        h.check("insert flush with the face", box == [-2.3, -2.3, 4.3, 2.3, 2.3, 10.0], box)
    h.check("component M3 Heat-set insert", "M3 Heat-set insert" in component_labels())
    h.shot("3-insert")
    h.task_button("OK")


c_placed.wait_ms = 2000


# -- D ---------------------------------------------------------------------------------------------
def d_magnet():
    h.check("insert kept", panel() is None and len(parts()) == 2, len(parts()))
    open_hardware()


def d_type():
    p = panel()
    if p is not None:
        h.check("Magnet", ui.choose(p.kind, "Magnet"))


def d_click():
    p = panel()
    h.check("6 x 3 first", p is not None and p.size.currentText() == "6 x 3 mm")
    h.check("clearance shown", p is not None and p.clearance.widget.isVisible())
    h.click(V(30, 8, 10))


d_click.wait_ms = 2500


def d_placed():
    v = block_volume()
    want = BOX - SCREW_HOLE - INSERT_HOLE - MAGNET_HOLE
    h.check("magnet pocket 6.2 x 3", close(v, want), (v, want))
    magnets = [o for o in parts() if core_kind(o) == "magnet"]
    if h.check("one magnet", len(magnets) == 1, len(magnets)):
        c = centre(magnets[0])
        state["pocket"] = c
        h.check("the magnet is where the click was", near_point(c, V(30, 8, 10)), c)
        faces = round_faces_at(c)
        h.check("pocket 6.2 wide, 3 deep", faces.get(3.1) == (7.0, 10.0), faces)
        box = global_box(magnets[0])
        h.check("magnet flush with the face", box == [-3.0, -3.0, 7.0, 3.0, 3.0, 10.0], box)
    h.check("component Magnet 6x3", "Magnet 6x3" in component_labels(), component_labels())
    h.shot("4-magnet")
    h.task_button("OK")


d_placed.wait_ms = 2000


# -- E ---------------------------------------------------------------------------------------------
def e_edit():
    h.check("three parts", panel() is None and len(parts()) == 3, len(parts()))
    doc = App.ActiveDocument
    screw = doc.getObject(state.get("screw") or "")
    state["screw_volume"] = screw.Shape.Volume if screw is not None else 0.0
    if screw is not None:
        s.timeline_double_click(screw)


e_edit.wait_ms = 2000


def e_editing():
    p = panel()
    h.check("editing the screw", p is not None and p.editing)
    if p is None:
        return
    shown = (p.standard.currentText(), p.size.currentText(), p.length.currentText())
    h.check("shows it as left", shown == ("Socket head cap screw (ISO 4762)", "M3", "10 mm"), shown)
    h.check("its hole is on", p.make_hole.isChecked())
    h.check("Length 16 mm", ui.choose(p.length, "16 mm"))


def e_longer():
    doc = App.ActiveDocument
    screw = doc.getObject(state.get("screw") or "")
    from sciforge import hardware_core

    want = hardware_core.volume({"standard": "iso4762", "size": "3", "length": 16})
    have = screw.Shape.Volume if screw is not None else 0.0
    h.check("the screw grows to 16", close(have, want), (have, want))
    h.check("renamed M3x16 ISO 4762", "M3x16 ISO 4762" in component_labels(), component_labels())
    # the insert's and the magnet's holes (made later) wait while the screw is edited (Fusion)
    want_box = BOX - SCREW_HOLE
    h.check("the hole stays (through all)", close(block_volume(), want_box), block_volume())
    if screw is not None:
        box = global_box(screw)
        h.check("still on the counterbore's floor", box[2] == -9.4 and box[5] == 9.6, box)
    h.shot("5-edited")
    h.task_button("OK")


e_longer.wait_ms = 2000


def e_kept():
    h.check("edit kept", panel() is None and "M3x16 ISO 4762" in component_labels())
    h.check("still three parts and three holes", len(parts()) == 3 and len(holes()) == 3)
    want_box = BOX - SCREW_HOLE - INSERT_HOLE - MAGNET_HOLE
    h.check("all three holes after OK", close(block_volume(), want_box), block_volume())
    state["count"] = len(App.ActiveDocument.Objects)
    state["volume"] = block_volume()
    open_hardware()


# -- F ---------------------------------------------------------------------------------------------
def f_type():
    p = panel()
    if p is not None:
        h.check("Heat-set insert again", ui.choose(p.kind, "Heat-set insert"))


def f_rim():
    # the rim of the magnet's pocket: a 6.2 round edge on the top face
    h.check("click the pocket's rim", h.click_edge(V(30 + 3.1, 8, 10)), h.state.get("last_click"))


f_rim.wait_ms = 2500


def f_on_rim():
    p = panel()
    h.check("placed on the rim", p is not None and p.target is not None)
    if p is None:
        return
    h.check("no second hole for a hole that is there", not p.make_hole.isChecked())
    h.check("size read off the hole: M5", p.size.currentText() == "M5", p.size.currentText())
    h.check("box unchanged", close(block_volume(), state["volume"]), block_volume())
    new = p.target
    pocket = state.get("pocket")
    if new is not None and pocket is not None:
        c = centre(new)
        h.check("on the pocket's axis", (c - pocket).Length < 1e-6, (c, pocket))
    h.shot("6-rim")
    h.task_button("Cancel")


f_on_rim.wait_ms = 2000


def f_cancelled():
    h.check("Cancel closes", panel() is None)
    h.check("Cancel changes nothing", len(App.ActiveDocument.Objects) == state["count"])
    h.check("box as it was", close(block_volume(), state["volume"]), block_volume())
    h.fit()
    h.shot("7-end")


h.run(
    "hardware_insert",
    b.box_steps("Hardware")
    + [
        a_start,
        a_waits,
        a_placed,
        a_kept,
        b_undone,
        b_redone,
        c_insert_type,
        c_click,
        c_placed,
        d_magnet,
        d_type,
        d_click,
        d_placed,
        e_edit,
        e_editing,
        e_longer,
        e_kept,
        f_type,
        f_rim,
        f_on_rim,
        f_cancelled,
    ],
)
