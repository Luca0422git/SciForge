# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rest the way a Fusion user does it, real input only: a curved cover (a half cylinder
R 20 x 60 shelled 2 mm, open at the bottom) and a 20 x 12 rectangle sketched 2 mm above its
crown. PLASTIC tab > Rest with nothing picked (the dialog waits), click inside the
rectangle: the preview makes a flat 20 x 12 face at z 22 on a pedestal (volume by hand in
plastic_steps.rest_volume), type a thicker wall, Flip (the profile then lies over nothing:
said in the dialog, OK waits), flip back, OK, Ctrl+Z / Ctrl+Y, edit by double-clicking the
timeline and Esc, save and reopen."""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps

V = App.Vector
s = {}


def setup():
    from sciforge import bodies, extrude, shelling

    ps.clear_library_prefs()
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("PlasticRest")
    body = bodies.new_body(doc, "Cover")
    sk = body.newObject("Sketcher::SketchObject", "Arch")
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, 0), App.Rotation(0.5, 0.5, 0.5, 0.5))  # YZ
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20), 0.0, math.pi))
    sk.addGeometry(Part.LineSegment(V(-20, 0, 0), V(20, 0, 0)))
    doc.recompute()
    ext = extrude.make(body, sk, {"distance": 60})
    doc.recompute()
    bottom = ps.face_named(ext, V(0, 0, -1), 0)
    # (Shell Type Rounded: FreeCAD's sharp join leaves this half pipe unshelled, with no
    # error: a Shell finding noted in docs/sciforge/sessions/plastic-1.md)
    shelling.make(body, ext, [bottom], {"inside": 2.0, "shell_type": "rounded"})
    doc.recompute()
    rest_sketch = ps.rect_sketch(body, 22, 20, -6, 40, 6, "Landing")
    rest_sketch.Label = "Landing"
    doc.recompute()
    s.update(body=body.Name)
    s["v0"] = ps.volume(body)
    want = math.pi * (400 - 324) / 2 * 56 + math.pi * 400 / 2 * 2 * 2
    h.check(
        "cover made (half pipe R20/R18 x 56 + two 2 mm ends)",
        ps.near(s["v0"], want, 1e-6),
        (s["v0"], want),
    )
    bodies.set_active_body(body)
    h.fit()
    ps.plastic_tab()


def body():
    return App.ActiveDocument.getObject(s["body"])


def start():
    Gui.Selection.clearSelection()
    h.ribbon("Rest")


def waiting():
    p = ps.rest_panel()
    h.check("Rest dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("nothing picked", p.refs == [] and p.target is None)
    h.check("box says Select profile", p.field.button.text() == "Select profile")
    h.check("no error while waiting", p.message.text() == "", p.message.text())
    h.check("thickness from the (default) rule, 2 mm", abs(p.thickness.value() - 2.0) < 1e-9)
    h.check("draft from the rule, 1 deg", abs(p.draft.value() - 1.0) < 1e-9)
    h.shot("1-waiting")


def zero_draft():
    p = ps.rest_panel()
    ps.type_into(p.draft.widget, "0")


def click_profile():
    h.fit()
    h.click(V(30, 0, 22))


def previewed():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("the profile picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("the body found", p and p.body_label.text() == "Cover", p and p.body_label.text())
    v = ps.volume(body())
    want = s["v0"] + ps.rest_volume(2.0)
    h.check("pedestal by hand (+%.2f)" % ps.rest_volume(2.0), ps.near(v, want, 0.05), (v, want))
    flat = [
        f
        for f in body().Shape.Faces
        if abs(f.BoundBox.ZMin - 22) < 1e-6 and abs(f.BoundBox.ZMax - 22) < 1e-6
    ]
    h.check(
        "one flat 20 x 12 face at z 22",
        len(flat) == 1 and ps.near(flat[0].Area, 240.0, 1e-6),
        [f.Area for f in flat],
    )
    h.check("one valid solid", body().Shape.isValid() and len(body().Shape.Solids) == 1)
    h.check("thickness arrow shown", p and p.arrow is not None)
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    s["v1"] = v
    h.shot("2-preview")


def body_box():
    p = ps.rest_panel()
    ps.click(p.body_field.button)


def pick_cover():
    p = ps.rest_panel()
    h.check("the Body box takes the clicks", p and p.active_box == "body")
    ps.click_row("Cover")


def cover_picked():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("the Body box names the body", p and p.body_field.button.text() == "Cover")
    h.check("the profile box takes the clicks again", p and p.active_box == "profile")
    h.check("same rest on the picked body", ps.near(ps.volume(body()), s["v1"], 1e-6))
    ps.click(p.body_field.clear)


def body_auto():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("cleared: Auto", p and p.body_field.button.text() == "Auto" and p.picked_body is None)
    h.check("still the same rest", ps.near(ps.volume(body()), s["v1"], 1e-6))


def thicker():
    p = ps.rest_panel()
    ps.type_into(p.thickness.widget, "3")


def thick():
    p = ps.rest_panel()
    ps.settle(p)
    v = ps.volume(body())
    h.check("a 3 mm wall adds more", v > s["v1"] + 10, (v, s["v1"]))
    h.check("still one valid solid", body().Shape.isValid() and len(body().Shape.Solids) == 1)
    h.check("the typed value drops the rule link", p and not p.options["links"].get("thickness"))


def flip():
    p = ps.rest_panel()
    ps.check_box(p.flip)


def flipped():
    p = ps.rest_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check(
        "flipped: the profile lies over nothing (said)", "does not lie over the body" in text, text
    )


def ok_refused():
    ps.ok()


def still_open():
    h.check("OK waits", ps.rest_panel() is not None)


def unflip():
    p = ps.rest_panel()
    ps.check_box(p.flip)


def ok():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("no message", p and p.message.text() == "", p and p.message.text())
    ps.ok()


def done():
    h.check("dialog closed", ps.rest_panel() is None)
    titles = ps.timeline_titles()
    h.check("a Rest step in the timeline", "Rest 1" in titles, titles)
    s["v2"] = ps.volume(body())
    h.check("kept", s["v2"] > s["v1"], s["v2"])
    h.shot("3-done")


def undo():
    ps.undo()


def undone():
    h.check("Ctrl+Z: as before", ps.near(ps.volume(body()), s["v0"], 1e-6), ps.volume(body()))


def redo():
    ps.redo()


def redone():
    h.check("Ctrl+Y: the rest again", ps.near(ps.volume(body()), s["v2"], 1e-6), ps.volume(body()))


def edit():
    ps.double_click_timeline("Rest 1")


def editing():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("edit dialog with the profile", p is not None and len(p.refs) == 1)
    h.check("edit shows 3 mm", p and abs(p.thickness.value() - 3.0) < 1e-9)
    ps.type_into(p.thickness.widget, "2")


def edit_esc():
    p = ps.rest_panel()
    ps.settle(p)
    ps.esc()


def edit_dropped():
    h.check(
        "Esc: the edit is dropped", ps.near(ps.volume(body()), s["v2"], 1e-6), ps.volume(body())
    )


def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sf-plastic-"), "PlasticRest.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)


def reopen():
    App.closeDocument(App.ActiveDocument.Name)
    doc = App.openDocument(s["path"])
    doc.recompute()
    h.fit()


def reopened():
    doc = App.ActiveDocument
    b = doc.getObject(s["body"])
    h.check("reopened: same volume", ps.near(ps.volume(b), s["v2"], 1e-6), ps.volume(b))
    steps = [o for o in doc.Objects if getattr(o, "SciForgeType", "") == "Rest"]
    h.check("reopened: the rest step valid", len(steps) == 1 and "Invalid" not in steps[0].State)


h.run(
    "plastic_rest",
    [
        setup,
        start,
        waiting,
        zero_draft,
        click_profile,
        previewed,
        body_box,
        pick_cover,
        cover_picked,
        body_auto,
        thicker,
        thick,
        flip,
        flipped,
        ok_refused,
        still_open,
        unflip,
        ok,
        done,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        edit_esc,
        edit_dropped,
        save,
        reopen,
        reopened,
    ],
)
