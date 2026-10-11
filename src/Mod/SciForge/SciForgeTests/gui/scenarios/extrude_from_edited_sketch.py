# SPDX-License-Identifier: LGPL-2.1-or-later
"""E while editing a sketch extrudes that sketch (Fusion), also when an extrude already
uses it.

Sketch A (40 x 30 on XY) is extruded 10. Sketch B (a circle r 5 on XZ) is newer and
unused. Double-click sketch A in the timeline, E: the Extrude dialog starts with sketch
A's area, not sketch B's. Type -4 (the other way, below XY), OK: the block grows to
40 x 30 x 14. (Before, Extrude took "the newest unused sketch": sketch B.)

Hand-derived: 40*30*10 = 12000; 40*30*14 = 16800."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def tl():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()
    QtWidgets.QApplication.processEvents()
    return widget


def step_button(name):
    for b in tl()._buttons:
        if b.item.name == name:
            return b
    h.check("timeline has %r" % name, False, tl().titles())
    return None


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("EditedSketch")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    a = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(a, 0, 0, 40, 30)
    extrude.make(body, a, {"distance": 10.0})
    b = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    h.draw_circle(b, 80, 20, 5)
    App.ActiveDocument.recompute()
    s["a"], s["b"] = a, b
    h.fit()
    h.check("block 40 x 30 x 10", near(h.solid_volume(), 12000.0), h.solid_volume())


def edit_sketch_a():
    w.double_click(step_button(s["a"].Name))


def press_e():
    h.check("sketch A is open", h.in_sketch() is s["a"], h.in_sketch())
    h.press("e")


def extrude_takes_a():
    p = panel()
    h.check("E left the sketch", h.in_sketch() is None)
    h.check("Extrude started", p is not None and not p._closed)
    sketches = [obj.Name for obj, _ in (p.profiles if p else [])]
    h.check("profile is sketch A's area", sketches == [s["a"].Name], sketches)
    h.check("not the newer unused sketch B", s["b"].Name not in sketches, sketches)


def type_minus_4():
    ui.type_into(panel().distance.widget, "-4")


def ok():
    h.task_button("OK")


def grown():
    h.check("block grew to 40 x 30 x 14", near(h.solid_volume(), 16800.0), h.solid_volume())
    h.check(
        "nothing in error",
        not [o.Name for o in App.ActiveDocument.Objects if "Invalid" in o.State],
    )
    h.fit()


h.run(
    "extrude_from_edited_sketch",
    [setup, edit_sketch_a, press_e, extrude_takes_a, type_minus_4, ok, grown],
)
