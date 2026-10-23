# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shell Type Sharp where FreeCAD cannot build sharp walls (fix-shell-sharp), real input:
a half pipe R 20 x 60 (a D-shaped profile extruded along X), its flat bottom clicked from
below, then MODIFY > Shell. FreeCAD's Thickness with Join Intersection gives this part back
unshelled, "valid" and without an error (found by plastic-1). The dialog says why and OK
waits: Inside Sharp refused; Both Sharp refused (before the fix it made the whole part
again, a silent wrong result); OK refused. Shell Type Rounded: the open half pipe; OK.
Editing it from the timeline back to Sharp is refused the same way and Esc keeps the
rounded shell; Ctrl+Z / Ctrl+Y.
  base: pi * 20^2 / 2 * 60
  inside rounded wall t: pi * (400 - (20 - t)^2) / 2 * (60 - 2t) + pi * 400 / 2 * t * 2
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}
BOTTOM = V(30, 5, 0)
BASE = math.pi * 400 / 2 * 60
SHARP = "Sharp corners cannot be built here"


def rounded(t):
    return math.pi * (400 - (20 - t) ** 2) / 2 * (60 - 2 * t) + math.pi * 400 * t


def msg(p):
    return p.message.text() if p is not None else ""


def doc():
    return App.ActiveDocument


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    h.check("%s: valid solid" % where, h.body().Shape.isValid())


def setup():
    from sciforge import bodies, extrude

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("SharpPipe")
    body = bodies.new_body(d, "Pipe")
    sk = body.newObject("Sketcher::SketchObject", "Arch")
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, 0), App.Rotation(0.5, 0.5, 0.5, 0.5))  # YZ
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20), 0.0, math.pi))
    sk.addGeometry(Part.LineSegment(V(-20, 0, 0), V(20, 0, 0)))
    d.recompute()
    extrude.make(body, sk, {"distance": 60})
    d.recompute()
    bodies.set_active_body(body)
    h.fit()
    v = h.solid_volume()
    h.check("half pipe made (pi 20^2 / 2 x 60)", sd.close(v, BASE), v)


def pick_bottom():
    Gui.Selection.clearSelection()
    h.view().viewBottom()
    h.view().fitAll()
    h.click(BOTTOM)


def shell_with_bottom():
    h.check("the flat bottom is selected", len(sd.selected()) == 1, sd.selected())
    h.ribbon("Shell")


def sharp_refused():
    p = sd.shell_panel()
    h.check("Shell started with the bottom", p is not None and len(p.names()) == 1)
    h.check("Sharp by default", p is not None and p.shell_type.currentText() == "Sharp")
    h.check("Inside Sharp: the dialog says why", SHARP in msg(p), msg(p))
    h.check("and what to choose", "Rounded" in msg(p), msg(p))
    h.check("no wrong shell made", not sd.shells(), sd.shells())
    v = h.solid_volume()
    h.check("the part is as it was", sd.close(v, BASE), v)
    h.shot("1-sharp-refused")
    if p:
        sd.choose(p.direction, "Both")


def both_refused():
    p = sd.shell_panel()
    h.check("Both Sharp: the dialog says why", SHARP in msg(p), msg(p))
    h.check("Both Sharp: no unshelled 'shell' made", not sd.shells(), sd.shells())
    v = h.solid_volume()
    h.check("Both Sharp: the part is as it was", sd.close(v, BASE), v)
    h.task_button("OK")


def ok_refused():
    p = sd.shell_panel()
    h.check("OK waits", p is not None and bool(Gui.Control.activeDialog()))
    h.check("the reason is still shown", SHARP in msg(p), msg(p))
    h.check("nothing made", not sd.shells(), sd.shells())
    sd.no_popups("OK on Sharp")
    if p:
        sd.choose(p.direction, "Inside")
        sd.choose(p.shell_type, "Rounded")


def rounded_preview():
    p = sd.shell_panel()
    h.check("Rounded: no warning", msg(p) == "", msg(p))
    v = h.solid_volume()
    h.check("Rounded: the open half pipe, 1 mm wall", sd.close(v, rounded(1)), (v, rounded(1)))
    joins = [getattr(o, "Join", "") for o in sd.shells()]
    h.check("FreeCAD's shell with Join Arc", joins == ["Arc"], joins)
    h.task_button("OK")


def made():
    h.check("OK closed the dialog", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the rounded shell is kept", sd.close(v, rounded(1)), v)
    part_ok("made")
    s["undo"] = list(doc().UndoNames)
    titles = [t for t in sd.timeline_titles() if t.startswith("Shell")]
    h.check("one Shell in the timeline", len(titles) == 1, sd.timeline_titles())
    if titles:
        sd.timeline_double_click(titles[0])


def edit_open():
    p = sd.shell_panel()
    h.check("edit: the dialog opens", p is not None and p.editing)
    h.check("edit: Rounded", p is not None and p.shell_type.currentText() == "Rounded")
    if p:
        sd.choose(p.shell_type, "Sharp")


def edit_sharp():
    p = sd.shell_panel()
    h.check("edit to Sharp: the dialog says why", SHARP in msg(p), msg(p))
    v = h.solid_volume()
    h.check("edit to Sharp: the preview keeps the rounded shell", sd.close(v, rounded(1)), v)
    joins = [getattr(o, "Join", "") for o in sd.shells()]
    h.check("edit to Sharp: the step is not changed", joins == ["Arc"], joins)
    h.shot("2-edit-sharp-refused")
    h.task_button("OK")


def edit_ok_refused():
    p = sd.shell_panel()
    h.check("edit: OK waits", p is not None and bool(Gui.Control.activeDialog()))
    h.check("edit: the reason is still shown", SHARP in msg(p), msg(p))
    h.press(QtCore.Qt.Key_Escape)


def edit_esc():
    h.check("Esc closes", not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("Esc: the rounded shell as it was", sd.close(v, rounded(1)), v)
    joins = [getattr(o, "Join", "") for o in sd.shells()]
    h.check("Esc: still Join Arc", joins == ["Arc"], joins)
    h.check("Esc: no undo step added", list(doc().UndoNames) == s["undo"], doc().UndoNames)
    part_ok("Esc")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    v = h.solid_volume()
    h.check("Ctrl+Z: the half pipe again", sd.close(v, BASE), v)
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    v = h.solid_volume()
    h.check("Ctrl+Y: the rounded shell again", sd.close(v, rounded(1)), v)
    part_ok("Ctrl+Y")
    h.check("nothing in the Report view", not sd.report_errors(), sd.report_errors())


h.run(
    "shell_draft_qa_sharp",
    [
        setup,
        pick_bottom,
        shell_with_bottom,
        sharp_refused,
        both_refused,
        ok_refused,
        rounded_preview,
        made,
        edit_open,
        edit_sharp,
        edit_ok_refused,
        edit_esc,
        undone,
        redone,
    ],
)
