# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketching on the part, the way Luca does it in Fusion, and editing the first sketch
later (the part must follow, with no error anywhere).

1. Sketch on XY, line chain 40 x 30, Finish, E, OK: a 40 x 30 x 10 block.
2. Create Sketch, click the top face: the sketch sits on it, the camera looks at it.
   C: a circle r 5, then E straight from the sketch (Fusion: E finishes the sketch
   and starts Extrude with it), OK: a boss on top.
3. Create Sketch on the top face again. P: click an edge of the part and the top face:
   they are projected (purple) and form profiles. Finish Sketch (the step that
   used to fail).
4. Double-click the first sketch in the browser, D on the 40 line, type 50, Finish:
   block and boss update, sketches on the face follow.

Hand-derived: block 40*30*10 = 12000; boss pi*5^2*10 = 785.398...; after the edit
the block is 50*30*10 = 15000.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
BOSS = math.pi * 5.0**2 * 10.0


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchFace")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy_plane():
    h.click(V(12, -8, 0))


def line_key():
    s["sk1"] = h.in_sketch()
    h.check("first sketch open", s["sk1"] is not None)
    h.press("l")


def p1():
    si.click(V(0, 0, 0))


def p2():
    si.click(V(40, 0, 0))


def p3():
    si.click(V(40, 30, 0))


def p4():
    si.click(V(0, 30, 0))


def p5():
    si.click(V(0, 0, 0))


def finish_1():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def extrude_1():
    h.check("left sketch 1", h.in_sketch() is None)
    h.fit()
    h.press("e")


def extrude_1_ok():
    h.task_button("OK")


def block():
    v = h.solid_volume()
    h.check("block 40 x 30 x 10", si.near(v, 12000.0, 1e-6), v)
    s["top"] = h.body().Shape.BoundBox.ZMax
    h.fit()


def sketch_on_top():
    h.ribbon("Create Sketch")


def click_top_face():
    h.click(V(30, 22, s["top"]))


def on_face():
    sk = h.in_sketch()
    s["sk2"] = sk
    h.check("sketch open on the top face", sk is not None)
    if sk is not None:
        support = sk.AttachmentSupport
        h.check("attached to a face", support and support[0][1][0].startswith("Face"), support)
        h.check(
            "camera looks at the face",
            si.vnear(h.view().getViewDirection(), V(0, 0, -1), 1e-6),
            h.view().getViewDirection(),
        )
    h.check("no pop-up", not h.popups(), h.popups())


def circle_key():
    h.press("c")


def circle_centre():
    si.click(V(20, 15, s["top"]))


def circle_radius():
    si.click(V(25, 15, s["top"]))


def circle_drawn():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk2"]
    circles = si.circles(sk, construction=False)
    h.check("circle on the face", len(circles) == 1, sk.Geometry)
    if circles:
        h.check("radius 5", si.near(circles[0][1].Radius, 5.0, 1e-6), circles[0][1])


def e_in_sketch():
    h.press("e")  # straight from the sketch


def e_started():
    from sciforge import extrude_ui

    h.check("E left the sketch", h.in_sketch() is None)
    panel = extrude_ui.ExtrudePanel.last
    h.check("Extrude started with the sketch", panel is not None and panel.target is not None)
    h.task_button("OK")


def boss():
    v = h.solid_volume()
    h.check("boss added: 12000 + pi*25*10", si.near(v, 12000.0 + BOSS, 1e-6), v)
    h.check("part visible", h.body_visible())
    h.fit()


def sketch_on_top_again():
    h.click_empty()
    h.ribbon("Create Sketch")


def click_top_face_again():
    h.click(V(35, 25, s["top"]))


def project_key():
    s["sk3"] = h.in_sketch()
    h.check("third sketch on the face", s["sk3"] is not None)
    s["ext"] = len(s["sk3"].ExternalGeo) if s["sk3"] is not None else 0
    h.press("p")


def project_edge():
    si.click(V(20, 0, s["top"]), V(0.0, 1.0, 0))  # the front top edge


def project_face():
    si.click(V(35, 25, s["top"]))  # the top face (all its edges)


def projected():
    sk = s["sk3"]
    added = len(sk.ExternalGeo) - s["ext"]
    h.check("P projected the edge and the face's edges", added >= 2, added)
    from sciforge import sketch_mode

    h.check(
        "projected edges make profiles",
        sketch_mode.current().shading.count >= 1,
        sketch_mode.current().shading.count,
    )
    h.check("no pop-up", not h.popups(), h.popups())
    s["ext"] = len(sk.ExternalGeo)
    h.shot("1-projected")


def finish_on_face():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def finished_on_face():
    h.check("Finish Sketch on a face sketch: closed", h.in_sketch() is None)
    h.check("part still there", si.near(h.solid_volume(), 12000.0 + BOSS, 1e-6))
    for sk in (s["sk2"], s["sk3"]):
        h.check("%s valid" % sk.Label, "Invalid" not in sk.State, sk.State)
    h.fit()


def edit_first_sketch():
    si.browser_double_click(s["sk1"].Label)


def editing_first():
    h.check("double-click in the browser edits the first sketch", h.in_sketch() is s["sk1"])
    h.press("d")


def dim_line():
    si.click(V(20, 0, 0))


def dim_place():
    si.click(V(20, -8, 0))


def dim_value():
    si.type_text("50")


def finish_edit():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def part_updated():
    h.check("left the sketch", h.in_sketch() is None)
    v = h.solid_volume()
    h.check("block 50 x 30 x 10 plus the boss", si.near(v, 15000.0 + BOSS, 1e-6), v)
    for obj in App.ActiveDocument.Objects:
        h.check("%s has no error" % obj.Label, "Invalid" not in obj.State, obj.State)
    h.check("part visible", h.body_visible())
    h.shot("2-edited")


h.run(
    "sketch_face",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy_plane,
            line_key,
            p1,
            p2,
            p3,
            p4,
            p5,
            finish_1,
            extrude_1,
            extrude_1_ok,
            block,
            sketch_on_top,
            click_top_face,
            on_face,
            circle_key,
            circle_centre,
            circle_radius,
            circle_drawn,
            e_in_sketch,
            e_started,
            boss,
            sketch_on_top_again,
            click_top_face_again,
            project_key,
            project_edge,
            project_face,
            projected,
            finish_on_face,
            finished_on_face,
            edit_first_sketch,
            editing_first,
            dim_line,
            dim_place,
            dim_value,
            finish_edit,
            part_updated,
        ]
    ),
)
