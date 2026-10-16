# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal stays on its face when later steps change the face: Press Pull (flat and round),
an edited extrude distance, a face that grows, undo / redo, Esc; only real input.
docs/sciforge/parity/misc.md, Decal (Luca: "decals dont follow their faces when moved").

Box: a sketch 40 x 30 extruded 10 (Extrude 1). Cylinder r 10, 40 high at x 100.

F1 Decals on the box's top and on the cylinder's side.
F2 Q, click the top, 5, OK: the top is pushed up 5 and the decal with it (z 15), unchanged.
F3 Q, click the cylinder's side, 2: the cylinder is 12 thick now; the wrapped decal stays
   wrapped round it (12 mm from the axis), as long along the surface as before.
F4 Double-click Extrude 1, distance 20, OK: the top (still pushed 5) is at 25, the decal too.
F5 Ctrl+Z: the decal is back at 15; Ctrl+Y: at 25.
F6 Q, click the box's right side, 8: the top grows to x 48; the decal stays where it was.
F7 Q, click the top, 10: the decal rises with the preview (z 35); Esc: back at 25.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h

V = App.Vector
st = {}


def pp_panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def new_design():
    s.new_design("DecalFaceChange")()
    f.use_picture()


def add_cylinder():
    d = App.ActiveDocument
    cyl_body = d.addObject("PartDesign::Body", "Body001")
    cyl = d.addObject("PartDesign::AdditiveCylinder", "Cylinder")
    cyl_body.addObject(cyl)
    cyl.Radius, cyl.Height = 10, 40
    cyl.Placement.Base = V(100, 0, 0)
    d.recompute()
    st["cyl"] = cyl_body.Name
    h.fit()


def f1_check():
    flat, wrapped = f.flat(), f.wrapped()
    h.check("F1 two decals", flat is not None and wrapped is not None, f.decals())
    if flat is None or wrapped is None:
        return
    st["flat"] = f.snapshot(flat)
    st["wrap"] = f.snapshot(wrapped)
    st["wrap_len"] = wrapped.BaseWidth * wrapped.ScaleX


def press_pull(tag, point, distance):
    def start():
        h.click_empty()
        h.fit()
        h.press("q")

    def click():
        h.check("%s: Press Pull open" % tag, pp_panel() is not None)
        h.click(point)

    def type_():
        p = pp_panel()
        if h.check("%s: the face picked" % tag, p is not None and p.target is not None, p):
            ui.type_into(p.field.widget, distance)

    start.wait_ms = 1200
    click.wait_ms = 1200
    type_.wait_ms = 1500
    steps = [start, click, type_]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__.strip("_"))
    return steps


def ok():
    h.task_button("OK")


# -- F2 ----------------------------------------------------------------------------------------
def f2_live():
    f.follows("F2 while pushing", f.flat(), st["flat"], App.Placement(V(0, 0, 5), App.Rotation()))
    ok()


f2_live.wait_ms = 1500


def f2_check():
    h.check("F2 Press Pull closed", pp_panel() is None)
    f.follows("F2 after OK (z 15)", f.flat(), st["flat"], App.Placement(V(0, 0, 5), App.Rotation()))
    f.follows("F2 the cylinder's decal did not move", f.wrapped(), st["wrap"], App.Placement())
    h.shot("F2-pushed")


# -- F3 ----------------------------------------------------------------------------------------
def f3_live():
    obj = f.wrapped()
    radii = f.radii(obj, V(100, 0, 0), V(0, 0, 1)) if obj is not None else []
    h.check(
        "F3 wrapped round the thicker cylinder (12 mm from its axis)",
        radii and min(radii) > 11.95 and max(radii) < 12.1,
        radii and (min(radii), max(radii)),
    )
    ok()


f3_live.wait_ms = 1500


def f3_check():
    obj = f.wrapped()
    h.check(
        "F3 the cylinder is 12 thick",
        obj is not None and f.near(obj.Radius, 12.0),
        obj and obj.Radius,
    )
    f.drawn_on_face("F3", obj)
    h.check(
        "F3 as long along the surface as before (the picture keeps its size)",
        f.near(f.area(obj), st["wrap"]["area"], 0.03 * st["wrap"]["area"]),
        (f.area(obj), st["wrap"]["area"]),
    )
    c = f.centre(obj)
    before = st["wrap"]["centre"]
    out = V(before.x - 100.0, before.y, 0).normalize()  # the way its middle faced (about -Y)
    want = V(100.0, 0, before.z) + out * 12.0
    h.check(
        "F3 its middle still faces the same way, at the same height, 12 from the axis",
        (c - want).Length < 1e-3,
        (c, want),
    )
    h.shot("F3-thicker")


# -- F4 ----------------------------------------------------------------------------------------
def f4_edit():
    h.fit()
    b.timeline_double_click("Extrude 1")


f4_edit.wait_ms = 1500


def f4_type():
    p = s.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("F4 the Extrude dialog", field is not None, p):
        s.type_value(field, "20")


f4_type.wait_ms = 1500


def f4_ok():
    h.task_button("OK")


f4_ok.wait_ms = 1500


def f4_check():
    box = f.flat().Body if f.flat() is not None else None
    top = box.Shape.BoundBox.ZMax if box is not None else None
    h.check("F4 the top is at 25 now", f.near(top, 25.0, 1e-6), top)
    f.follows(
        "F4 the decal is on it (z 25)",
        f.flat(),
        st["flat"],
        App.Placement(V(0, 0, 15), App.Rotation()),
    )
    h.shot("F4-extrude")


# -- F5 ----------------------------------------------------------------------------------------
def f5_undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


f5_undo.wait_ms = 1500


def f5_undone():
    f.follows("F5 Ctrl+Z (z 15)", f.flat(), st["flat"], App.Placement(V(0, 0, 5), App.Rotation()))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


f5_undone.wait_ms = 1500


def f5_redone():
    f.follows("F5 Ctrl+Y (z 25)", f.flat(), st["flat"], App.Placement(V(0, 0, 15), App.Rotation()))
    st["f5"] = f.snapshot(f.flat())


# -- F6 ----------------------------------------------------------------------------------------
def f6_check():
    box = f.flat().Body if f.flat() is not None else None
    right = box.Shape.BoundBox.XMax if box is not None else None
    h.check("F6 the box reaches x 48", f.near(right, 48.0, 1e-6), right)
    f.follows("F6 the decal stayed where it was", f.flat(), st["f5"], App.Placement())
    ok()


f6_check.wait_ms = 1500


def f6_ok():
    f.follows("F6 after OK", f.flat(), st["f5"], App.Placement())
    h.shot("F6-grown")


# -- F7 ----------------------------------------------------------------------------------------
def f7_live():
    f.follows(
        "F7 the decal rises with the preview",
        f.flat(),
        st["f5"],
        App.Placement(V(0, 0, 10), App.Rotation()),
    )
    h.press(QtCore.Qt.Key_Escape)


f7_live.wait_ms = 1500


def f7_check():
    h.check("F7 Esc closed Press Pull", not Gui.Control.activeDialog())
    f.follows("F7 Esc: back at 25", f.flat(), st["f5"], App.Placement())


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.new_errors()


h.run(
    "fixdecal_face_change",
    [new_design]
    + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + [add_cylinder]
    + f.decal_steps("f1_flat", f.TOP)
    + f.decal_steps("f1_wrapped", f.SIDE)
    + [f1_check]
    + press_pull("f2", f.TOP, "5")
    + [f2_live, f2_check]
    + press_pull("f3", f.SIDE, "2")
    + [f3_live, f3_check, f4_edit, f4_type, f4_ok, f4_check, f5_undo, f5_undone, f5_redone]
    + press_pull("f6", V(40, 15, 12), "8")
    + [f6_check, f6_ok]
    + press_pull("f7", V(20, 15, 25), "10")
    + [f7_live, f7_check, cleanup],
)
