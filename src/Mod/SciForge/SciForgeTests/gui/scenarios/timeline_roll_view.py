# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rolling the timeline marker back must change what the 3D view shows: the later
features disappear, and a click on the part lands on the step at the marker. (Before,
the view kept showing the last step, so a click could hit a rolled-back feature and a
sketch attached there failed; found by the extrude QA, flaky in the full suite.)"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Roll")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 40, 30)
    s["first"] = extrude.make(body, base, {"distance": 10.0})
    App.ActiveDocument.recompute()
    top = [i + 1 for i, f in enumerate(s["first"].Shape.Faces) if abs(f.CenterOfMass.z - 10) < 1e-6]
    boss = sketch_ui.create_sketch(body, (s["first"], "Face%d" % top[0]))
    x, y = h.to_sketch(boss, V(10, 10, 10))
    h.draw_rectangle(boss, x, y, x + 20, y + 10)
    s["second"] = extrude.make(body, boss, {"distance": 5.0})
    App.ActiveDocument.recompute()
    h.fit()


def roll_back():
    from sciforge import timeline_ui

    tl = timeline_ui._dock.widget()
    tl.refresh()
    first = None
    for b in tl._buttons:
        if b.item.name == s["first"].Name:
            first = b
    h.check("timeline shows the first extrude", first is not None, tl.titles())
    if first is not None:
        w.right_click(first, w.center(first), "Roll History Marker Here")


def rolled():
    h.check("tip is the first extrude", h.body().Tip is s["first"], h.body().Tip)
    h.check("the rolled-back extrude is hidden", not s["second"].ViewObject.Visibility)
    h.check("the first extrude is shown", s["first"].ViewObject.Visibility)
    h.fit()


def click_top():
    hit = h.click(V(30, 25, 10))  # on the first extrude's top, beside where the boss was
    h.check(
        "a click on the part hits the step at the marker", hit and hit[0] == s["first"].Name, hit
    )


h.run("timeline_roll_view", [setup, roll_back, rolled, click_top])
