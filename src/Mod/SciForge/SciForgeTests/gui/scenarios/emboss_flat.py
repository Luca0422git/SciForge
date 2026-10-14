# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss on a flat face, the refusals, Cancel, and a face curved in two directions;
real input only. Fusion's behaviour (Autodesk help "Emboss a solid body", "Reference:
Emboss"; an Autodesk forum answer: Emboss does not wrap onto a sphere):

F1  OK before any profile is refused, and says why; the dialog stays.
F2  a text and a closed sketch curve (a circle) are both profiles; OK before the faces
    is refused, and says why.
F3  a click on the top face: the preview raises the letters and the disc; Depth 0.6
    adds exactly (their area) x 0.6 (a flat face: straight walls).
F4  Deboss sinks them: the same volume removed.
F5  Rotation Angle 90 swings the circle off the face: the dialog says so plainly and
    makes nothing; 180 puts it back on: the same volume.
F6  Esc (Cancel) leaves the part as it was: no Emboss step.
F7  a ball: the profile cannot be unrolled onto it; Emboss lays it on along the sketch's
    direction and says so in the dialog; OK makes the step.
"""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
DEPTH = 0.6
DISC = (48.0, 15.0, 4.0)  # the circle: centre x, y and radius (sketch = top view)
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import emboss_ui

    p = emboss_ui.EmbossPanel.last
    return p if p is not None and not p._closed and Gui.Control.activeDialog() else None


def computing():
    """FreeCAD shows the wait cursor while a long shape operation runs; it lets the
    window repaint meanwhile (and the next scenario step start), but ignores the keys."""
    cursor = QtWidgets.QApplication.overrideCursor()
    return cursor is not None and cursor.shape() == QtCore.Qt.WaitCursor


def settle(timeout_ms=15000):
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(60)
        p = panel()
        if p is None:
            return
        busy = (
            p._timer.isActive()
            or getattr(p, "_pending", False)
            or App.ActiveDocument.Recomputing
            or computing()
        )
        if not busy:
            return


def volume():
    return s["body"].Shape.Volume


def embosses():
    return [o for o in App.ActiveDocument.Objects if getattr(o, "SciForgeType", "") == "Emboss"]


def add_sketch(body, z, name="Sketch"):
    sketch = body.newObject("Sketcher::SketchObject", name)
    sketch.MapMode = "Deactivated"
    sketch.Placement = App.Placement(V(0, 0, z), App.Rotation())
    sketch.MakeInternals = True
    return sketch


def add_text(sketch, content, corner, width, height, size):
    from sciforge import text

    spec = text.default_spec()
    spec.update(
        text=content,
        height=size,
        corner=corner,
        width=width,
        frame_height=height,
        font=text.default_family(),
        h_align="center",
        v_align="middle",
    )
    return text.make(sketch, spec)


def new_part():
    """A 60 x 30 x 10 block; a sketch 5 mm above it holding the text "SF" and a circle."""
    import Part

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("EmbossFlat")
    from sciforge import commands

    body = commands.ensure_body()
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = 60, 30, 10
    doc.recompute()
    sketch = add_sketch(body, 15.0)
    x, y, r = DISC
    sketch.addGeometry(Part.Circle(V(x, y, 0), V(0, 0, 1), r))
    doc.openTransaction("setup")
    obj = add_text(sketch, "SF", (8.0, 8.0), 24.0, 14.0, 10.0)
    doc.recompute()
    doc.commitTransaction()
    s.update(doc=doc, body=body, sketch=sketch, text=obj)
    s["area"] = sum(f.Area for f in obj.Shape.Faces) + math.pi * r * r
    s["v0"] = volume()
    s["box"] = body.Shape.copy()
    h.view().viewTop()
    h.view().fitAll()
    h.check("setup: the text has letters", s["area"] > 30, s["area"])


# -- F1 -----------------------------------------------------------------------------------------
def f1_open():
    si.menu_item("CREATE", "Emboss")


def f1_ok_too_soon():
    p = panel()
    h.check("F1 the Emboss dialog opened", p is not None)
    h.task_button("OK")


def f1_refused():
    p = panel()
    h.check("F1 OK with nothing picked keeps the dialog", p is not None)
    if p is None:
        return
    h.check("F1 and says why", "profile" in p.message.text().lower(), p.message.text())
    h.check("F1 nothing made", embosses() == [] and near(volume(), s["v0"]))


# -- F2 -----------------------------------------------------------------------------------------
def f2_pick_text():
    ti.click_sketch(s["sketch"], *ti.middle_of_first_letter(s["text"]))


def f2_profiles_again():
    p = panel()
    h.check("F2 the text is a profile", p.profiles == [(s["text"], "")], p.profiles)
    ui.click(p.fields["profiles"].button)


def f2_pick_circle():
    ti.click_sketch(s["sketch"], DISC[0], DISC[1])


def f2_ok_without_faces():
    p = panel()
    h.check("F2 the circle is a profile too", len(p.profiles) == 2, p.profiles)
    h.task_button("OK")


def f2_refused():
    p = panel()
    h.check("F2 OK without faces keeps the dialog", p is not None)
    if p is None:
        return
    h.check("F2 and says why", "faces" in p.message.text().lower(), p.message.text())
    ui.click(p.fields["faces"].button)


# -- F3 -----------------------------------------------------------------------------------------
def f3_pick_face():
    h.click(V(30, 26, 10))  # the top face, clear of the profiles


def f3_preview():
    settle()
    p = panel()
    h.check("F3 the top face is picked", p is not None and len(p.face_names) == 1)
    h.check("F3 the preview raised the profiles", volume() > s["v0"] + 1.0, volume())
    ui.type_into(p.depth.widget, "%g" % DEPTH)


def f3_check():
    settle()
    got = volume() - s["v0"]
    want = s["area"] * DEPTH
    h.check("F3 a flat face: exactly area x 0.6 added", near(got, want, 1e-6), (got, want))
    p = panel()
    tool = p.target.Shape.cut(s["box"]) if p is not None and p.target is not None else None
    kinds = sorted({f.Surface.TypeId for f in tool.Faces}) if tool is not None else []
    h.check(
        "F3 the circle stays a true circle (a cylinder wall)", "Part::GeomCylinder" in kinds, kinds
    )
    p = panel()
    wrap = p._wrap() if p is not None else None
    h.check("F3 laid flat on the face", wrap is not None and wrap.kind == "plane")
    h.check("F3 no note (nothing to say)", p is not None and not p.note.text(), p.note.text())
    b = s["body"].Shape.BoundBox
    h.check("F3 standing 0.6 above the top", near(b.ZMax, 10.0 + DEPTH, 1e-6), b.ZMax)
    h.shot("f3-emboss")
    ui.choose(p.effect, "Deboss")


# -- F4 -----------------------------------------------------------------------------------------
def f4_check():
    settle()
    got = volume() - s["v0"]
    want = -s["area"] * DEPTH
    h.check("F4 Deboss: exactly area x 0.6 removed", near(got, want, 1e-6), (got, want))
    s["deboss"] = got
    ui.type_into(panel().angle.widget, "90")


# -- F5 -----------------------------------------------------------------------------------------
def f5_off_the_face():
    settle()
    p = panel()
    msg = p.message.text() if p is not None else ""
    h.check("F5 turned 90: the circle leaves the face, and the dialog says so", "edge" in msg, msg)
    h.check("F5 the part is not changed by it", near(volume(), s["v0"], 1e-9), volume())
    ui.type_into(p.angle.widget, "180")


def f5_back_on():
    settle()
    p = panel()
    h.check("F5 turned 180: no problem", p is not None and not p.message.text(), p.message.text())
    got = volume() - s["v0"]
    h.check("F5 the same volume", near(got, s["deboss"], 1e-6), (got, s["deboss"]))
    h.shot("f5-turned")


# -- F6 -----------------------------------------------------------------------------------------
def f6_cancel():
    h.press(QtCore.Qt.Key_Escape)


def f6_cancelled():
    h.check("F6 Esc closed the dialog", panel() is None)
    h.check("F6 the part as it was", near(volume(), s["v0"], 1e-9), volume())
    h.check("F6 no Emboss step", embosses() == [], embosses())
    titles = ui.timeline_titles()
    h.check("F6 none on the timeline", not any(t.startswith("Emboss") for t in titles), titles)


# -- F7 the ball --------------------------------------------------------------------------------
def f7_ball():
    App.closeDocument(s["doc"].Name)
    doc = App.newDocument("EmbossBall")
    from sciforge import commands

    body = commands.ensure_body()
    ball = body.newObject("PartDesign::AdditiveSphere", "Sphere")
    ball.Radius = 20
    doc.recompute()
    sketch = add_sketch(body, 30.0)
    doc.openTransaction("setup")
    obj = add_text(sketch, "HI", (-8.0, -5.0), 16.0, 10.0, 8.0)
    doc.recompute()
    doc.commitTransaction()
    s.update(doc=doc, body=body, sketch=sketch, text=obj)
    s["v0"] = volume()
    h.view().viewTop()
    h.view().fitAll()
    si.menu_item("CREATE", "Emboss")


def f7_pick_text():
    ti.click_sketch(s["sketch"], *ti.middle_of_first_letter(s["text"]))


def f7_pick_ball():
    h.click(V(11, -11, math.sqrt(400.0 - 242.0)))


def f7_depth():
    ui.type_into(panel().depth.widget, "0.5")


def wait_idle():
    """A step that comes back until FreeCAD is done computing. A long shape operation
    lets Qt run the next step from inside it, where the keys are ignored and waiting in
    place would hold the computation up."""
    p = panel()
    busy = App.ActiveDocument.Recomputing or computing()
    if p is not None:
        busy = busy or p._timer.isActive() or getattr(p, "_pending", False)
    if busy:
        h.state["queue"].insert(0, wait_idle)


wait_idle.wait_ms = 250


def f7_projected():
    settle()
    p = panel()
    h.check("F7 the ball's face is picked", p is not None and len(p.face_names) == 1)
    if p is None:
        return
    wrap = p._wrap()
    h.check("F7 a face curved two ways", wrap is not None and wrap.kind == "other")
    note = p.note.text()
    h.check("F7 the dialog says the profile is projected", "projected" in note, note)
    h.check("F7 and that Fusion would not wrap it", "Fusion" in note, note)
    h.check("F7 no error", not p.message.text(), p.message.text())
    h.check("F7 the letters stand out", volume() > s["v0"] + 1.0, (volume(), s["v0"]))
    h.check("F7 0.5 deep", abs(p.depth.value() - 0.5) < 1e-9, p.depth.widget.text())
    h.shot("f7-ball")
    h.task_button("OK")


def f7_made():
    h.check("F7 OK made the step", len(embosses()) == 1 and panel() is None, embosses())
    b = s["body"].Shape.BoundBox
    h.check("F7 the letters rise above the ball", b.ZMax > 20.0 + 0.4, b.ZMax)
    from sciforge import parameters

    rows = [
        r
        for r in parameters.model_parameters(App.ActiveDocument)
        if r["owner"].startswith("Emboss")
    ]
    labels = [r["label"] for r in rows]
    h.check("F7 its depth is a model parameter (Change Parameters)", "Depth" in labels, labels)
    depth = next((r["value"] for r in rows if r["label"] == "Depth"), None)
    h.check("F7 0.5 mm there", depth is not None and abs(depth - 0.5) < 1e-9, depth)


for step in (f3_preview, f3_check, f4_check, f5_off_the_face, f5_back_on, f7_projected):
    step.wait_ms = 1500

h.run(
    "emboss_flat",
    [
        new_part,
        f1_open,
        f1_ok_too_soon,
        f1_refused,
        f2_pick_text,
        f2_profiles_again,
        f2_pick_circle,
        f2_ok_without_faces,
        f2_refused,
        f3_pick_face,
        f3_preview,
        f3_check,
        f4_check,
        f5_off_the_face,
        f5_back_on,
        f6_cancel,
        f6_cancelled,
        f7_ball,
        f7_pick_text,
        f7_pick_ball,
        wait_idle,
        f7_depth,
        wait_idle,
        f7_projected,
        f7_made,
    ],
)
