# SPDX-License-Identifier: LGPL-2.1-or-later
"""SOLID > CREATE > Text (Luca, 2026-10-16: "a text tool to add text to a face"); real input
only. In Fusion text is a sketch tool (Create Sketch on the face, then Text); this entry
does both: it waits for a face, opens a sketch there and the Text dialog in it.

A  Text from the SOLID tab's CREATE menu waits for a face (a dialog says so); Esc gives up
   (no sketch made).
B  Text again, a click on the top face of a 60 x 30 x 10 block: a sketch opens on that face
   with the Text dialog already open.
C  Two frame corners, "SF" 12 mm high, OK: the text is in the sketch.
D  Finish Sketch, E, -0.8: the letters are cut 0.8 deep into the top face.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
BLOCK = 60.0 * 30.0 * 10.0
DEPTH = 0.8
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def sketches():
    return [o for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"]


def top_view():
    h.view().viewTop()
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(90.0)
    except Exception:
        pass
    cam.position.setValue(30.0, 15.0, 100.0)
    QtWidgets.QApplication.processEvents()


def task_title():
    from sciforge import taskui

    current = taskui.current() if hasattr(taskui, "current") else None
    form = getattr(current, "form", None)
    return form.windowTitle() if form is not None else ""


def new_part():
    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("FaceText")
    from sciforge import commands

    body = commands.ensure_body()
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = 60, 30, 10
    d.recompute()
    h.check("setup: the block", near(h.solid_volume(), BLOCK), h.solid_volume())
    h.fit()


# -- A ------------------------------------------------------------------------------------------
def a_open():
    si.menu_item("CREATE", "Text")


def a_waits():
    h.check("A Text waits for a face", task_title() == "Text: pick a face", task_title())
    h.check("A no sketch yet", sketches() == [], sketches())
    h.press(QtCore.Qt.Key_Escape)


def a_cancelled():
    h.check("A Esc: nothing waits", task_title() == "", task_title())
    h.check("A Esc: no sketch made", sketches() == [], sketches())
    h.check("A Esc: no Text dialog", ti.dialog() is None)


# -- B ------------------------------------------------------------------------------------------
def b_open():
    si.menu_item("CREATE", "Text")


def b_pick_top():
    h.click(V(30, 15, 10))


b_pick_top.wait_ms = 1500


def b_sketch_and_dialog():
    sk = h.in_sketch()
    h.check("B a sketch opened", sk is not None)
    s["sketch"] = sk
    if sk is not None:
        z = sk.getGlobalPlacement().multVec(V(0, 0, 0)).z
        h.check("B on the top face (z 10)", near(z, 10.0), z)
    h.check("B the Text dialog is open", ti.dialog() is not None)
    h.shot("b-text-dialog")
    top_view()


def corner(x, y):
    return lambda: h.to_sketch(s["sketch"], V(x, y, 10))


# -- D ------------------------------------------------------------------------------------------
def d_finish():
    obj = s.get("text")
    h.check("C the text says SF", obj is not None and obj.ResolvedText == "SF")
    s["area"] = sum(f.Area for f in obj.Shape.Faces) if obj is not None else 0.0
    h.ribbon("Finish Sketch")


def d_extrude():
    h.check("D sketch closed", h.in_sketch() is None)
    h.fit()
    h.press("e")


def d_distance():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    h.check("D Extrude opened", panel is not None and not panel._closed)
    if panel is None:
        return
    if panel.profiles != [(s["text"], "")]:
        # a sketch on a face may hold the face's outline too: pick the letters
        x, y = ti.middle_of_first_letter(s["text"])
        ti.click_sketch(s["sketch"], x, y)
        QtWidgets.QApplication.processEvents()
    h.check("D the text is the profile", panel.profiles == [(s["text"], "")], panel.profiles)
    arrows.give_distance("-%g" % DEPTH)


def d_ok():
    h.task_button("OK")


def d_cut():
    expect = BLOCK - s["area"] * DEPTH
    h.check(
        "D the letters are cut 0.8 deep",
        near(h.solid_volume(), expect, 1e-5),
        (h.solid_volume(), expect),
    )
    b = h.body().Shape.BoundBox
    h.check("D nothing sticks out of the block", near(b.ZMax, 10.0), b.ZMax)
    h.shot("d-cut")


steps = [new_part, a_open, a_waits, a_cancelled, b_open, b_pick_top, b_sketch_and_dialog]
steps += ti.text_steps(s, corner(5, 5), corner(55, 25), "SF", 12)[1:]  # (the dialog is open)
steps += [d_finish, d_extrude, d_distance, d_ok, d_cut]
h.run("text_on_face", steps)
