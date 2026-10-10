# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude's object options and operations, only real input.

A 40 x 30 x 10 base with a 10 x 30 x 20 wall on its right end. A 10 x 10 square sketched
on the base's top face is extruded:
  - To Object: click the wall's top face -> the column stops at the wall's height;
  - Start: Object (the wall's top) with -20 -> the same column, built downwards;
  - Cut with All, then Flip -> a square hole through the base;
  - Intersect -> only the 10 x 10 x 10 piece of the base inside the extrusion is kept;
  - Join 5, OK.
Then a New Body extrude on the top face: a second body, which becomes the active one;
Undo removes it again.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def bodies():
    return App.ActiveDocument.findObjects("PartDesign::Body")


def sketch_rect_on(point, x0, y0, x1, y1):
    """Steps: Create Sketch, click the face at `point`, draw a rectangle given in global
    x/y (the face is horizontal), Finish Sketch."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(point)

    def draw():
        sk = h.in_sketch()
        h.check("sketch open on the face at %s" % (point,), sk is not None)
        if sk:
            ax, ay = h.to_sketch(sk, V(x0, y0, point.z))
            bx, by = h.to_sketch(sk, V(x1, y1, point.z))
            h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def finish():
        h.ribbon("Finish Sketch")

    create.__name__ = "create_sketch_at_%d_%d" % (point.x, point.y)
    return [create, pick, draw, finish]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Objects")
    h.fit()


def create_base_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_base():
    sk = h.in_sketch()
    h.check("base sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_base():
    h.ribbon("Finish Sketch")


def extrude_base():
    h.fit()
    h.press("e")


def base_ok():
    h.check("base picked by itself", panel().target is not None)
    h.task_button("OK")


def base_done():
    h.check("base 40 x 30 x 10", near(h.solid_volume(), 12000.0), h.solid_volume())


def extrude_wall():
    h.fit()
    h.press("e")


def wall_height():
    p = panel()
    h.check("wall sketch picked by itself", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "20")


def wall_ok():
    h.task_button("OK")


def wall_done():
    h.check("wall adds 10 x 30 x 20", near(h.solid_volume(), 18000.0), h.solid_volume())


def extrude_column():
    h.fit()
    h.press("e")


def column_to_object():
    p = panel()
    h.check("column profile picked by itself", p.target is not None, p.message.text())
    h.check(
        "Join while going up out of the part",
        p.operation.currentText() == "Join",
        p.operation.currentText(),
    )
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))
    h.check("the Object box takes the next click", p.active == "extent_object", p.active)


def click_wall_top():
    h.fit()
    h.click(V(35, 15, 30))


def column_to_wall():
    p = panel()
    h.check(
        "To Object: the wall's top face",
        p.options.get("extent_object") is not None,
        p.message.text(),
    )
    h.check(
        "column reaches the wall's height: +10 x 10 x 20",
        near(h.solid_volume(), 20000.0),
        h.solid_volume(),
    )
    h.check("the target is linked, not copied", p.target.Type == "UpToFace", p.target.Type)
    h.shot("1-to-object")
    h.check("choose Extent: Distance", ui.choose(p.extent, "Distance"))


def start_from_object():
    p = panel()
    h.check("back to 10: +1000", near(h.solid_volume(), 19000.0), h.solid_volume())
    h.check("choose Start: Object", ui.choose(p.start, "Object"))
    h.check("the start Object box takes the next click", p.active == "start_object", p.active)


def click_wall_top_again():
    h.fit()
    h.click(V(35, 15, 30))


def start_picked():
    p = panel()
    h.check("start object picked", p.options.get("start_object") is not None, p.message.text())
    ui.type_into(p.distance.widget, "-20")


def start_object_down():
    h.check(
        "from the wall's height down 20: the same column",
        near(h.solid_volume(), 20000.0),
        h.solid_volume(),
    )
    h.check("choose Start: Profile Plane", ui.choose(panel().start, "Profile Plane"))


def cut_all():
    p = panel()
    ui.type_into(p.distance.widget, "10")
    h.check("choose Operation: Cut", ui.choose(p.operation, "Cut"))
    h.check("choose Extent: All", ui.choose(p.extent, "All"))


def flip():
    p = panel()
    h.check("Flip shown for All", p.flip.isVisible())
    ui.click(p.flip)


def through_hole():
    p = panel()
    h.check(
        "cut through all, downwards: a 10 x 10 hole",
        near(h.solid_volume(), 17000.0),
        (h.solid_volume(), p.message.text()),
    )
    h.check("no error shown", p.message.text() == "", p.message.text())
    h.shot("2-cut-all")
    h.check("choose Operation: Intersect", ui.choose(p.operation, "Intersect"))


def intersected():
    p = panel()
    h.check(
        "Intersect keeps the 10 x 10 x 10 inside the extrusion",
        near(h.solid_volume(), 1000.0),
        (h.solid_volume(), p.message.text()),
    )
    h.shot("3-intersect")
    h.check("choose Operation: Join", ui.choose(p.operation, "Join"))


def join_again():
    p = panel()
    h.check("choose Extent: Distance", ui.choose(p.extent, "Distance"))


def join_5():
    p = panel()
    ui.click(p.flip) if p.flip.isChecked() and p.flip.isVisible() else None
    ui.type_into(p.distance.widget, "5")


def column_ok():
    h.check(
        "join 5 up: +500",
        near(h.solid_volume(), 18500.0),
        (h.solid_volume(), panel().message.text()),
    )
    h.task_button("OK")


def column_done():
    h.check("column kept", near(h.solid_volume(), 18500.0), h.solid_volume())
    s["first_body"] = h.body()
    s["first_volume"] = h.solid_volume()


def extrude_new_body():
    h.fit()
    h.press("e")


def choose_new_body():
    p = panel()
    h.check("block profile picked by itself", p.target is not None, p.message.text())
    h.check("choose Operation: New Body", ui.choose(p.operation, "New Body"))


def new_body_ok():
    h.check("two bodies while previewing", len(bodies()) == 2, [b.Label for b in bodies()])
    h.task_button("OK")


def new_body_done():
    from sciforge import commands

    h.check("two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    active = commands.active_body()
    h.check(
        "the new body is the active one",
        active is not None and active is not s["first_body"],
        active and active.Label,
    )
    if active is not None:
        h.check("new body: 10 x 6 x 10", near(active.Shape.Volume, 600.0), active.Shape.Volume)
    h.check(
        "the first body is unchanged",
        near(s["first_body"].Shape.Volume, s["first_volume"]),
        s["first_body"].Shape.Volume,
    )
    h.shot("4-new-body")


def undo_new_body():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the new body", len(bodies()) == 1, [b.Label for b in bodies()])
    h.check("first body still there", near(s["first_body"].Shape.Volume, s["first_volume"]))


h.run(
    "extrude_objects",
    [
        new_design,
        create_base_sketch,
        pick_xy,
        draw_base,
        finish_base,
        extrude_base,
        base_ok,
        base_done,
        *sketch_rect_on(V(35, 15, 10), 30, 0, 40, 30),
        extrude_wall,
        wall_height,
        wall_ok,
        wall_done,
        *sketch_rect_on(V(10, 15, 10), 5, 10, 15, 20),
        extrude_column,
        column_to_object,
        click_wall_top,
        column_to_wall,
        start_from_object,
        click_wall_top_again,
        start_picked,
        start_object_down,
        cut_all,
        flip,
        through_hole,
        intersected,
        join_again,
        join_5,
        column_ok,
        column_done,
        *sketch_rect_on(V(21, 5, 10), 16, 2, 26, 8),  # in front of the wall, not behind it
        extrude_new_body,
        choose_new_body,
        new_body_ok,
        new_body_done,
        undo_new_body,
        undone,
    ],
)
