# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss text around a cylinder (Fusion's everyday Emboss: a label on a round part), real
input only. Fusion's behaviour (Autodesk help "Emboss a solid body"):

E1  SOLID > CREATE > Emboss opens the dialog; it waits for sketch profiles.
E2  a click on a letter picks the whole text as one profile; the dialog then waits for
    the faces.
E3  a click on the cylinder's side picks the face; the preview raises the letters.
E4  Depth 0.6: the letters are wrapped round like a label (no stretch), so the volume
    added is exactly the letters' area x 0.6 x (1 + 0.6 / (2 R)).
E5  Effect Deboss sinks them instead: area x 0.6 x (1 - 0.6 / (2 R)) removed.
E6  Horizontal Distance moves the text round the cylinder: the same volume.
E7  OK: one timeline step "Emboss", the sketch and its text hidden.
E8  double-click the step: the dialog comes back with every value; Depth 1 + OK changes it.
E9  Ctrl+Z takes the change back (one step), again takes the emboss away; Ctrl+Y twice
    brings both back.
"""

import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
R = 20.0
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import emboss_ui

    p = emboss_ui.EmbossPanel.last
    return p if p is not None and not p._closed and Gui.Control.activeDialog() else None


def settle(timeout_ms=8000):
    """Let the preview catch up (its timer done, no recompute running)."""
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(60)
        p = panel()
        if p is None:
            return
        busy = (
            p._timer.isActive() or getattr(p, "_pending", False) or App.ActiveDocument.Recomputing
        )
        if not busy:
            return


def volume():
    return h.solid_volume()


def new_part():
    """A cylinder R 20 x 40 standing on XY, and a text sketched on a plane 3 mm in front of
    it (facing the viewer, -Y), like a sketch on a plane tangent to the part."""
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("EmbossCyl")
    from sciforge import commands, text

    body = commands.ensure_body()
    cyl = body.newObject("PartDesign::AdditiveCylinder", "Cylinder")
    cyl.Radius = R
    cyl.Height = 40
    doc.recompute()
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.MapMode = "Deactivated"
    sketch.Placement = App.Placement(V(0, -R - 3, 0), App.Rotation(V(1, 0, 0), 90))
    sketch.MakeInternals = True
    doc.recompute()
    spec = text.default_spec()
    spec.update(
        text="LUCA",
        height=8.0,
        corner=(-12.0, 16.0),
        width=24.0,
        frame_height=9.0,
        font=text.default_family(),
        h_align="center",
        v_align="middle",
    )
    doc.openTransaction("setup")
    obj = text.make(sketch, spec)
    doc.recompute()
    doc.commitTransaction()
    s.update(doc=doc, body=body, sketch=sketch, text=obj)
    s["area"] = sum(f.Area for f in obj.Shape.Faces)
    s["v0"] = body.Shape.Volume
    h.view().viewFront()
    h.view().fitAll()
    h.check("setup: the text has letters", s["area"] > 10, s["area"])


def e1_open():
    si.menu_item("CREATE", "Emboss")


def e1_waits():
    p = panel()
    h.check("E1 the Emboss dialog opened", p is not None)
    if p is None:
        return
    h.check("E1 it waits for sketch profiles", p.active == "profiles", p.active)
    h.shot("e1-open")


def e2_pick_text():
    x0, y0, x1, y1 = ti.letters_box(s["text"])
    first = ti.middle_of_first_letter(s["text"])
    s["letter"] = first
    ti.click_sketch(s["sketch"], *first)


def e2_picked():
    p = panel()
    h.check(
        "E2 the whole text is one profile",
        p is not None and p.profiles == [(s["text"], "")],
        p and p.profiles,
    )
    h.check("E2 now it waits for the faces", p is not None and p.active == "faces", p and p.active)


def e3_pick_face():
    # the cylinder's side, right of the text (clear of the letters)
    import math

    a = math.radians(-40.0)
    h.click(V(R * math.cos(a), R * math.sin(a), 32.0))


def e3_preview():
    settle()
    p = panel()
    h.check(
        "E3 the side face is picked", p is not None and len(p.face_names) == 1, p and p.face_names
    )
    h.check("E3 the preview raised the letters", volume() > s["v0"] + 1.0, (volume(), s["v0"]))
    h.check("E3 no problem shown", p is not None and not p.message.text(), p and p.message.text())


def e4_depth():
    ui.type_into(panel().depth.widget, "0.6")


def e4_check():
    settle()
    d = 0.6
    want = s["area"] * d * (1.0 + d / (2.0 * R))
    got = volume() - s["v0"]
    h.check(
        "E4 wrapped like a label: area x 0.6 x (1 + 0.6/2R)", near(got, want, 2e-4), (got, want)
    )
    p = panel()
    wrap = p._wrap() if p is not None else None
    h.check(
        "E4 wrapped onto the cylinder",
        wrap is not None and wrap.kind == "cylinder",
        wrap and wrap.kind,
    )
    h.check("E4 the depth arrow is shown", p is not None and "depth" in p.handles, p and p.handles)
    h.shot("e4-emboss")


def e5_deboss():
    ui.choose(panel().effect, "Deboss")


def e5_check():
    settle()
    d = 0.6
    want = -s["area"] * d * (1.0 - d / (2.0 * R))
    got = volume() - s["v0"]
    h.check(
        "E5 Deboss sinks the letters: area x 0.6 x (1 - 0.6/2R) removed",
        near(got, want, 2e-4),
        (got, want),
    )
    s["deboss"] = got


def e6_move():
    ui.type_into(panel().h.widget, "10")


def e6_check():
    settle()
    got = volume() - s["v0"]
    h.check(
        "E6 moved round the cylinder: the same volume",
        near(got, s["deboss"], 2e-4),
        (got, s["deboss"]),
    )
    p = panel()
    h.check(
        "E6 the distance is on the step",
        p is not None and p.target is not None and near(p.target.HorizontalDistance.Value, 10.0),
        p and p.target and p.target.HorizontalDistance,
    )


def e7_ok():
    h.task_button("OK")


def e7_check():
    h.check("E7 the dialog closed", panel() is None)
    titles = ui.timeline_titles()
    s["step"] = next((t for t in titles if t.startswith("Emboss")), None)
    h.check("E7 one timeline step Emboss", s["step"] is not None, titles)
    h.check("E7 the sketch is hidden", not s["sketch"].ViewObject.Visibility)
    QtTest.QTest.qWait(100)
    h.check("E7 and its text", not s["text"].ViewObject.Visibility)
    h.check("E7 one undo step", s["doc"].UndoNames[0] == "Emboss", s["doc"].UndoNames[:3])
    s["after_ok"] = volume()


def e8_edit():
    ui.double_click_timeline(s["step"])


def e8_dialog():
    p = panel()
    h.check("E8 the dialog came back", p is not None)
    if p is None:
        return
    h.check("E8 with Deboss", p.effect.currentData() == "deboss")
    h.check("E8 with the depth", near(p.depth.value(), 0.6))
    h.check("E8 with the distance", near(p.h.value(), 10.0))
    h.check(
        "E8 with the text and the face",
        p.profiles == [(s["text"], "")] and len(p.face_names) == 1,
        (p.profiles, p.face_names),
    )
    ui.type_into(p.depth.widget, "1")


def e8_ok():
    settle()
    h.task_button("OK")


def e8_check():
    d = 1.0
    want = -s["area"] * d * (1.0 - d / (2.0 * R))
    got = volume() - s["v0"]
    h.check("E8 the change took (depth 1)", near(got, want, 2e-4), (got, want))
    h.press("z", QtCore.Qt.ControlModifier)


def e9_undo_once():
    got = volume()
    h.check("E9 Ctrl+Z took the change back", near(got, s["after_ok"], 1e-6), (got, s["after_ok"]))
    h.press("z", QtCore.Qt.ControlModifier)


def e9_undo_twice():
    got = volume()
    h.check("E9 Ctrl+Z again took the emboss away", near(got, s["v0"], 1e-9), (got, s["v0"]))
    h.press("y", QtCore.Qt.ControlModifier)


def e9_redo_once():
    h.press("y", QtCore.Qt.ControlModifier)


def e9_redone():
    d = 1.0
    want = -s["area"] * d * (1.0 - d / (2.0 * R))
    got = volume() - s["v0"]
    h.check("E9 Ctrl+Y twice brought both back", near(got, want, 2e-4), (got, want))
    h.shot("e9-done")


for step in (e3_preview, e4_check, e5_check, e6_check, e8_ok):
    step.wait_ms = 1500

h.run(
    "emboss_cylinder",
    [
        new_part,
        e1_open,
        e1_waits,
        e2_pick_text,
        e2_picked,
        e3_pick_face,
        e3_preview,
        e4_depth,
        e4_check,
        e5_deboss,
        e5_check,
        e6_move,
        e6_check,
        e7_ok,
        e7_check,
        e8_edit,
        e8_dialog,
        e8_ok,
        e8_check,
        e9_undo_once,
        e9_undo_twice,
        e9_redo_once,
        e9_redone,
    ],
)
