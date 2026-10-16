# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mirror the way a Fusion user does it, only real input:

1. A plate 40 x 30 x 10 centred on the origin with a boss r 3 x 6 at (10, 5) on top.
2. Mirror from the ribbon with nothing selected: waits. Click the boss's step in the
   timeline, click the Mirror Plane box (the three origin squares appear), click the YZ
   square in front of the part: the boss is mirrored to (-10, 5). OK (FreeCAD's Mirrored).
   Ctrl+Z / Ctrl+Y.
3. Double-click Mirror 1 in the timeline, click the Mirror Plane box, click the XZ square:
   the copy moves to (10, -5). OK.
4. Mirror again, Pattern Type Bodies: click the part, Operation New Body (Fusion's), the
   Mirror Plane is the plate's right face: a new body, the mirror image of the first (x 20 to
   60). OK. Ctrl+Z removes the new body, Ctrl+Y brings it back.
5. Edit Mirror 2: Operation Join: the copy joins the first body (one body, twice the
   volume). OK.
6. Cancel and Esc change nothing.

Hand-derived: plate 12000; boss pi 3^2 6.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
BOSS = math.pi * 9.0 * 6.0
PART = 12000.0 + BOSS


def plate(sk):
    h.draw_rectangle(sk, -20, -15, 20, 15)


def boss_centres():
    return ps.circle_centres(h.body().Shape, 3.0, z=16)


def ribbon_mirror():
    Gui.Selection.clearSelection()
    s["v0"] = h.solid_volume()
    h.ribbon("Mirror")


def waiting():
    p = ps.panel()
    h.check("Mirror dialog open", p is not None and p.kind == "mirror")
    if p is None:
        return
    h.check("Objects box active, nothing picked", p.fields["objects"].button.isChecked())
    h.check("no Operation for features", not p.operation.isVisible())
    h.check("model unchanged", ps.close(h.solid_volume(), s["v0"]))
    ps.no_popups("Mirror with nothing selected")
    h.shot("1-waiting")


def click_boss_step():
    ps.timeline_click("Extrude 2")


def click_plane_box():
    p = ps.panel()
    h.check("boss picked", p and len(p.options["objects"]) == 1, p and p.options["objects"])
    ps.click_box("plane")


def planes_shown():
    p = ps.panel()
    h.check("origin squares drawn", p and p.plane_picker is not None)
    h.shot("2-planes")
    h.fit()


def click_yz():
    h.click(V(0, -8, -8))  # the YZ square below the plate (24 mm squares)


def mirrored_yz():
    p = ps.panel()
    plane = p.options["plane"] if p else None
    h.check("the YZ plane is the mirror plane", plane and plane[0].Role == "YZ_Plane", plane)
    h.check("box shows YZ Plane", p and p.fields["plane"].button.text() == "YZ Plane")
    h.check("squares gone", p and p.plane_picker is None)
    h.check("the boss behind the square was not taken", p and len(p.options["objects"]) == 1)
    v = h.solid_volume()
    h.check("preview: two bosses", ps.close(v, PART + BOSS), v)
    h.check("copy at (-10, 5)", boss_centres() == [(-10, 5), (10, 5)], boss_centres())
    h.shot("3-preview")
    h.task_button("OK")


def after_ok():
    found = ps.patterns("mirror")
    h.check(
        "one Mirror (FreeCAD's Mirrored), the end of the timeline",
        len(found) == 1 and found[0].TypeId == "PartDesign::Mirrored" and h.body().Tip is found[0],
        found,
    )
    h.check("timeline shows Mirror 1", "Mirror 1" in ps.timeline_titles(), ps.timeline_titles())
    h.check("valid solid", h.body().Shape.isValid())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("Ctrl+Z: one boss again", ps.close(h.solid_volume(), PART) and not ps.patterns())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check(
        "Ctrl+Y: two bosses", ps.close(h.solid_volume(), PART + BOSS) and len(ps.patterns()) == 1
    )
    h.fit()


def edit():
    ps.timeline_double_click("Mirror 1")


def edit_open():
    p = ps.panel()
    h.check("Mirror dialog on the mirror", p is not None and p.editing)
    h.check("the plane is shown", p and p.fields["plane"].button.text() == "YZ Plane")
    ps.click_box("plane")


def click_xz():
    h.fit()
    h.click(V(-6, 0, 11))  # the XZ square standing above the plate


def mirrored_xz():
    p = ps.panel()
    plane = p.options["plane"] if p else None
    h.check("now the XZ plane", plane and plane[0].Role == "XZ_Plane", plane)
    h.check("copy at (10, -5)", boss_centres() == [(10, -5), (10, 5)], boss_centres())
    h.task_button("OK")


def after_edit():
    h.check(
        "still one mirror, two bosses",
        len(ps.patterns()) == 1 and ps.close(h.solid_volume(), PART + BOSS),
    )
    s["v"] = h.solid_volume()


# -- bodies -----------------------------------------------------------------------------------
def body_mirror():
    Gui.Selection.clearSelection()
    h.ribbon("Mirror")


def choose_bodies():
    b.choose(ps.panel().pattern_type, "Bodies")


def click_part():
    p = ps.panel()
    h.check(
        "Operation shown for bodies, New Body",
        p.operation.isVisible() and p.operation.currentText() == "New Body",
    )
    h.fit()
    h.click(V(-10, -8, 10))


def body_picked():
    p = ps.panel()
    objs = p.options["objects"] if p else []
    h.check(
        "the body is the object", len(objs) == 1 and objs[0][0].TypeId == "PartDesign::Body", objs
    )
    ps.click_box("plane")


def click_right_face():
    h.fit()
    h.click(V(20, -6, 5))


def new_body_preview():
    p = ps.panel()
    plane = p.options["plane"] if p else None
    h.check("the right face is the plane", plane and plane[1].startswith("Face"), plane)
    found = ps.bodies()
    h.check("a second body", len(found) == 2, [x.Label for x in found])
    if len(found) == 2:
        new = [x for x in found if x is not h.body()]
        new = new[0] if new else found[1]
        bb = new.Shape.BoundBox
        h.check("its volume is the part's", ps.close(new.Shape.Volume, s["v"]), new.Shape.Volume)
        h.check(
            "it is the mirror image: x 20 to 60",
            ps.close(bb.XMin, 20) and ps.close(bb.XMax, 60),
            bb,
        )
    h.shot("4-new-body")
    h.task_button("OK")


def after_body_ok():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("two bodies", len(ps.bodies()) == 2)
    h.check("Mirror 2 in the timeline", "Mirror 2" in ps.timeline_titles(), ps.timeline_titles())
    first = App.ActiveDocument.getObject("Body")
    h.check("the first body is unchanged", ps.close(first.Shape.Volume, s["v"]), first.Shape.Volume)
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def body_undo():
    h.check("Ctrl+Z removes the new body", len(ps.bodies()) == 1, [x.Label for x in ps.bodies()])
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def body_redo():
    h.check("Ctrl+Y brings it back", len(ps.bodies()) == 2)
    h.fit()


def edit_body_mirror():
    ps.timeline_double_click("Mirror 2")


def choose_join():
    p = ps.panel()
    h.check(
        "the dialog shows Bodies / New Body",
        p and p.pattern_type.currentText() == "Bodies" and p.operation.currentText() == "New Body",
    )
    b.choose(p.operation, "Join")


def joined():
    found = ps.bodies()
    h.check("one body again", len(found) == 1, [x.Label for x in found])
    v = App.ActiveDocument.getObject("Body").Shape.Volume
    h.check("the copy joined the body: twice the volume", ps.close(v, 2 * s["v"]), v)
    h.task_button("OK")


def after_join():
    body = App.ActiveDocument.getObject("Body")
    h.check("one solid", len(body.Shape.Solids) == 1, len(body.Shape.Solids))
    h.check(
        "x -20 to 60",
        ps.close(body.Shape.BoundBox.XMax, 60) and ps.close(body.Shape.BoundBox.XMin, -20),
    )
    h.check("two mirrors", len(ps.patterns("mirror")) == 2)
    s["v"] = body.Shape.Volume
    h.shot("5-joined")


def cancel_start():
    h.ribbon("Mirror")


def cancel_pick():
    ps.timeline_click("Extrude 2")


def cancel_box():
    ps.click_box("plane")


def cancel_plane():
    h.fit()
    h.click(V(0, -8, -8))  # the YZ square below the plate (24 mm squares)


def cancel_now():
    p = ps.panel()
    h.check("a preview is shown", p is not None and p.target is not None)
    h.task_button("Cancel")


def after_cancel():
    h.check(
        "Cancel: unchanged", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns("mirror")) == 2
    )
    h.check("closed", not Gui.Control.activeDialog())


def esc_start():
    h.ribbon("Mirror")


def esc():
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check(
        "Esc: closed, unchanged",
        not Gui.Control.activeDialog() and ps.close(h.solid_volume(), s["v"]),
    )


h.run(
    "patterns_mirror",
    b.box_steps("PatternMirror", profile=plate)
    + ps.make_boss("boss", (10, 5), 3.0, 6.0, click=V(-10, -8, 10))
    + [
        ribbon_mirror,
        waiting,
        click_boss_step,
        click_plane_box,
        planes_shown,
        click_yz,
        mirrored_yz,
        after_ok,
        after_undo,
        after_redo,
        edit,
        edit_open,
        click_xz,
        mirrored_xz,
        after_edit,
        body_mirror,
        choose_bodies,
        click_part,
        body_picked,
        click_right_face,
        new_body_preview,
        after_body_ok,
        body_undo,
        body_redo,
        edit_body_mirror,
        choose_join,
        joined,
        after_join,
        cancel_start,
        cancel_pick,
        cancel_box,
        cancel_plane,
        cancel_now,
        after_cancel,
        esc_start,
        esc,
        after_esc,
    ],
)
