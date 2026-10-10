# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude with Fusion's profiles, only real input.

A rectangle with a circle inside is two profiles (the ring and the disc). E with
nothing selected waits; clicking the ring extrudes the ring, clicking the disc adds
it, clicking the ring again drops it, clicking it once more brings it back. Type a
distance, drag the arrow, OK. Undo and redo. Double-click the extrude in the
timeline: every option is back, change the distance, OK. A face extrude cancelled
leaves the part untouched; a second extrude on the top face works.

Expected numbers are worked out by hand: 40 x 30 rectangle, circle r5.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
RING = 1200.0 - 25.0 * math.pi  # mm^2
DISC = 25.0 * math.pi


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def extrudes():
    from sciforge import extrude

    return [o for o in App.ActiveDocument.Objects if extrude.is_extrude(o)]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Regions")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.check("no pop-up on Create Sketch", not h.popups(), h.popups())
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)
        h.draw_circle(sk, 20, 15, 5)
        s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def after_finish():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()


def extrude_nothing_selected():
    h.press("e")


def waiting_for_profiles():
    p = panel()
    h.check("E opens the Extrude dialog", p is not None and not p._closed)
    h.check("no pop-up on Extrude", not h.popups(), h.popups())
    regions = len(p.picker.regions) if p and p.picker else 0
    h.check("the sketch shows two profiles (ring and disc)", regions == 2, regions)
    h.check("two profiles: nothing is picked by itself", p is not None and p.target is None)
    h.shot("1-profiles")
    h.fit()


def click_ring():
    h.click(V(5, 5, 0))


def ring_extruded():
    p = panel()
    h.check("clicking the ring starts the extrude", p.target is not None, p.message.text())
    h.check("one profile picked", len(p.profiles) == 1, p.profiles)
    h.check("ring 10 mm: (1200 - 25 pi) * 10", near(h.solid_volume(), RING * 10), h.solid_volume())
    h.shot("2-ring")
    h.fit()


def click_disc():
    h.click(V(20, 15, 0))


def both_extruded():
    p = panel()
    h.check("clicking the disc adds it", len(p.profiles) == 2, p.profiles)
    h.check("ring + disc = full block 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.fit()


def click_ring_again():
    h.click(V(5, 5, 0))


def disc_only():
    p = panel()
    h.check("clicking the ring again drops it", len(p.profiles) == 1, p.profiles)
    h.check("disc only: 25 pi * 10", near(h.solid_volume(), DISC * 10), h.solid_volume())
    h.shot("3-disc-only")
    h.fit()


def click_ring_back():
    h.click(V(5, 5, 0))


def type_distance():
    p = panel()
    h.check("ring back in", len(p.profiles) == 2, p.profiles)
    ui.type_into(p.distance.widget, "15")


def typed_15():
    h.check("typed 15: 40 x 30 x 15", near(h.solid_volume(), 18000.0), h.solid_volume())
    h.fit()


def drag_arrow():
    p = panel()
    h.check("distance arrow shown", p.dragger is not None)
    if p.dragger is None:
        return
    s["before_drag"] = p.distance.value()
    head = V(20, 15, p.dragger.distance() + p.dragger.size * 0.9)
    # The disc's arrow sits at the region's inner point; use the arrow's own origin.
    origin = p.dragger.root.getChild(0).translation.getValue()
    head = V(origin[0], origin[1], origin[2] + p.dragger.distance() + p.dragger.size * 0.9)
    a = h.screen_point(head)
    h.drag(a, QtCore.QPoint(a.x(), a.y() - 40))


def dragged():
    p = panel()
    h.check(
        "dragging the arrow up makes it longer",
        p.distance.value() > s["before_drag"] + 0.5,
        (p.distance.value(), s["before_drag"]),
    )
    ui.type_into(p.distance.widget, "15")


def ok_first():
    h.check("preview has no error", panel().message.text() == "", panel().message.text())
    h.task_button("OK")


def after_ok():
    from sciforge import commands

    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("OK keeps 40 x 30 x 15", near(h.solid_volume(), 18000.0), h.solid_volume())
    h.check("refined: 6 faces", len(h.body().Shape.Faces) == 6, len(h.body().Shape.Faces))
    h.check("one extrude feature", len(extrudes()) == 1, [o.Name for o in extrudes()])
    h.check("the sketch is hidden after the extrude", not s["sketch"].ViewObject.Visibility)
    h.check("still one body", len(App.ActiveDocument.findObjects("PartDesign::Body")) == 1)
    h.check("the body is active", commands.active_body() is not None)
    h.shot("4-ok")


def undo():
    h.check("Undo button in the application bar", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the whole extrude (one step)", h.solid_volume() < 1e-6, h.solid_volume())
    h.check("no extrude left after undo", not extrudes(), [o.Name for o in extrudes()])


def redo():
    h.check("Redo button in the application bar", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", near(h.solid_volume(), 18000.0), h.solid_volume())
    h.fit()


def edit_from_timeline():
    titles = ui.timeline_titles()
    h.check("timeline shows Extrude 1", "Extrude 1" in titles, titles)
    h.check("double-click on Extrude 1", ui.double_click_timeline("Extrude 1"), titles)


def editing():
    p = panel()
    h.check(
        "the Extrude dialog opens on the feature", p is not None and p.editing and not p._closed
    )
    if not (p and p.editing):
        return
    h.check("both profiles are back", len(p.profiles) == 2, p.profiles)
    h.check("distance 15 is back", near(p.distance.value(), 15.0), p.distance.value())
    h.check(
        "operation shown",
        p.operation.currentText() in ("New Body", "Join"),
        p.operation.currentText(),
    )
    h.check(
        "every option is offered",
        all(
            w.count() >= n
            for w, n in ((p.start, 3), (p.direction, 3), (p.extent, 3), (p.operation, 4))
        ),
    )
    ui.type_into(p.distance.widget, "20")


def edit_ok():
    h.check("edit preview 40 x 30 x 20", near(h.solid_volume(), 24000.0), h.solid_volume())
    h.task_button("OK")


def after_edit():
    h.check("edit kept: 24000", near(h.solid_volume(), 24000.0), h.solid_volume())
    h.check("still one extrude after the edit", len(extrudes()) == 1, [o.Name for o in extrudes()])
    h.fit()


def cancel_case():
    s["before_cancel"] = h.solid_volume()
    s["features"] = len(h.body().Group)
    h.press("e")


def cancel_pick_face():
    h.fit()
    top = h.body().Shape.BoundBox.ZMax
    h.click(V(30, 25, top))


def cancel_type():
    p = panel()
    h.check("a click on the top face starts a face extrude", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "5")


def cancel_now():
    h.check("face preview grows the part", h.solid_volume() > s["before_cancel"] + 1.0)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the part as it was", near(h.solid_volume(), s["before_cancel"]))
    h.check("Cancel removes the unfinished extrude", len(h.body().Group) == s["features"])
    h.fit()


def second_extrude():
    h.press("e")


def second_pick():
    h.fit()
    top = h.body().Shape.BoundBox.ZMax
    h.click(V(30, 25, top))


def second_type():
    p = panel()
    h.check("second extrude picked the top face", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "5")


def second_ok():
    h.task_button("OK")


def after_second():
    h.check("second extrude adds 40 x 30 x 5", near(h.solid_volume(), 30000.0), h.solid_volume())
    h.check("part visible", h.body_visible())
    h.check("two extrudes", len(extrudes()) == 2, [o.Name for o in extrudes()])
    h.shot("5-end")


h.run(
    "extrude_regions",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw,
        finish_sketch,
        after_finish,
        extrude_nothing_selected,
        waiting_for_profiles,
        click_ring,
        ring_extruded,
        click_disc,
        both_extruded,
        click_ring_again,
        disc_only,
        click_ring_back,
        type_distance,
        typed_15,
        drag_arrow,
        dragged,
        ok_first,
        after_ok,
        undo,
        undone,
        redo,
        redone,
        edit_from_timeline,
        editing,
        edit_ok,
        after_edit,
        cancel_case,
        cancel_pick_face,
        cancel_type,
        cancel_now,
        after_cancel,
        second_extrude,
        second_pick,
        second_type,
        second_ok,
        after_second,
    ],
)
