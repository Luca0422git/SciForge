# SPDX-License-Identifier: LGPL-2.1-or-later
"""A sketch on a face of another body goes into that body (Fusion: Extrude then joins
the body that was clicked).

Two blocks in two bodies, the first body active. Create Sketch, click the top of the
second block: the sketch is made in the second body, which becomes active. A circle
r 5 on it, E, OK: the boss joins the second block, the first block is untouched.
(Before, the sketch went into the active first body, reached out of it, and the
extrude was added to the wrong body.)

Hand-derived: block A 40*30*10 = 12000; block B 20*20*10 = 4000;
boss pi*r^2*10 with the clicked radius r (about 5)."""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("OtherBody")
    a = commands.ensure_body()
    sk = sketch_ui.create_sketch(a, (sketch_ui.origin_planes(a)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(a, sk, {"distance": 10.0})
    b = doc.addObject("PartDesign::Body", "Body001")
    sk = sketch_ui.create_sketch(b, (sketch_ui.origin_planes(b)["XY_Plane"], ""))
    h.draw_rectangle(sk, 60, 0, 80, 20)
    extrude.make(b, sk, {"distance": 10.0})
    doc.recompute()
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", a)
    s["a"], s["b"] = a, b
    h.fit()
    h.check("first body active", h.body() is a, h.body())


def create_sketch():
    h.ribbon("Create Sketch")


def click_second_block():
    hit = h.click(V(70, 10, 10))
    names = [o.Name for o in s["b"].Group]
    h.check("the click hits the second block", hit and hit[0] in names, hit)


def sketch_in_second_body():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.check("sketch is in the second body", sk in s["b"].Group, sk.getParentGeoFeatureGroup())
        h.check("sketch is not in the first body", sk not in s["a"].Group)
    h.check("second body is active", h.body() is s["b"], h.body())
    h.check("no pop-up", not h.popups(), h.popups())


def circle_key():
    h.press("c")


def circle_centre():
    si.click(V(70, 10, 10))


def circle_radius():
    si.click(V(75, 10, 10))


def e_from_sketch():
    h.press(QtCore.Qt.Key_Escape)
    circles = si.circles(s["sk"], construction=False)
    h.check("one circle", len(circles) == 1, s["sk"].Geometry)
    # Clicked, so the radius is 5 to the nearest pixel (about 0.1 mm at this zoom).
    s["r"] = circles[0][1].Radius if circles else 0.0
    h.check("radius about 5", abs(s["r"] - 5.0) < 0.2, s["r"])
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def joined_second_body():
    a, b = s["a"].Shape.Volume, s["b"].Shape.Volume
    h.check("first block untouched", si.near(a, 12000.0, 1e-6), a)
    boss = math.pi * s["r"] ** 2 * 10.0
    h.check("boss joined the second block", si.near(b, 4000.0 + boss, 1e-6), (b, boss))
    h.check(
        "nothing in error", not [o.Name for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    )
    h.fit()
    h.shot("1-joined")


h.run(
    "sketch_other_body",
    [
        setup,
        create_sketch,
        click_second_block,
        sketch_in_second_body,
        circle_key,
        circle_centre,
        circle_radius,
        e_from_sketch,
        extrude_ok,
        joined_second_body,
    ],
)
