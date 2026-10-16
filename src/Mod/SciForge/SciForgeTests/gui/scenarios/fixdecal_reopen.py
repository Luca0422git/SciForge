# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal that followed its body is still stuck to it after save / reopen, and goes on
following it; a decal saved by the earlier SciForge (no face remembered) is brought up to
date when opened. Only real input for the moves. docs/sciforge/parity/misc.md, Decal.

Bodies: a box 40 x 30 x 10 and a cylinder r 10, 40 high at x 100.

R1 Decals on the box's top and the cylinder's side; M, click the box, X Distance 30, OK.
R2 Saved, closed, opened again: both decals drawn where their faces are, not red, nothing
   to recompute.
R3 M, click the box, Y Distance 20, OK: the decal follows (what it remembers of its face
   came back with the file); Ctrl+Z / Ctrl+Y.
R4 A design saved by the earlier SciForge (its decals remembered no face and no body
   placement): opened, the decals are brought up to date and drawn; M, click the box,
   Z Angle 90, OK: the decal follows.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h

V = App.Vector
st = {}


def doc():
    return App.ActiveDocument


def box():
    return doc().getObject(st["box"])


def moves():
    return s.steps_of_kind("MoveCopy")


def field(p, name):
    return {
        "dx": p.distance_fields[0],
        "dy": p.distance_fields[1],
        "rz": p.angle_fields[2],
    }[name].widget


def movement():
    from sciforge import move

    place = App.Placement()
    for step in moves():
        if move.moved_body(step) is box() and not move.is_copy(step):
            place = step.Movement.multiply(place)
    return place


def move_steps(tag, value_key, value):
    """Steps: M, click the box's top (where it is now), type the value, OK."""

    def press():
        st[tag] = f.snapshot(f.flat())
        st[tag + "_place"] = movement()
        h.click_empty()
        h.fit()
        h.press("m")

    def click():
        h.click(movement().multVec(f.TOP))

    def type_():
        p = s.panel()
        if h.check("%s: the box picked" % tag, p is not None and p.options["bodies"] == [box()]):
            s.type_value(field(p, value_key), value)

    def ok():
        h.task_button("OK")

    def check():
        place = movement().multiply(st[tag + "_place"].inverse())
        h.check("%s: the box moved" % tag, not place.isIdentity(), place)
        f.follows("%s: the decal followed" % tag, f.flat(), st[tag], place)

    press.wait_ms = 1200
    click.wait_ms = 1200
    type_.wait_ms = 1500
    ok.wait_ms = 1500
    steps = [press, click, type_, ok, check]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__.strip("_"))
    return steps


def save_reopen(tag, before=None):
    def save():
        if before is not None:
            before()
        path = os.path.join(tempfile.mkdtemp(prefix="sciforge-fixdecal-"), "Decals.FCStd")
        doc().saveAs(path)
        st["path"] = path
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        App.openDocument(path)

    save.wait_ms = 2500
    save.__name__ = "%s_save_reopen" % tag
    return save


def setup():
    st.update(f.box_and_cylinder("DecalReopen"))


def r1_check():
    st["wrap"] = f.snapshot(f.wrapped())


# -- R2 ----------------------------------------------------------------------------------------
def r2_check():
    found = f.decals()
    h.check("R2 both decals back", len(found) == 2, found)
    st["box"] = f.flat().Body.Name if f.flat() is not None else st["box"]
    f.follows("R2 the box's decal where the moved box is", f.flat(), st["r1"], st["r1_moved"])
    f.follows("R2 the cylinder's decal", f.wrapped(), st["wrap"], App.Placement())
    h.check(
        "R2 nothing to recompute",
        all("Touched" not in o.State for o in found),
        [(o.Label, o.State) for o in found],
    )
    h.check("R2 the face is remembered", all(o.FaceRecord for o in found))
    h.fit()


def r1_moved():
    st["r1_moved"] = movement()


# -- R4 ----------------------------------------------------------------------------------------
def make_old():
    """What the earlier SciForge saved: no remembered face, no body placement."""
    for obj in f.decals():
        obj.FaceRecord = ""
        if "BodyPlace" in obj.PropertiesList:
            obj.removeProperty("BodyPlace")


def r4_check():
    found = f.decals()
    h.check("R4 both decals back", len(found) == 2, found)
    h.check(
        "R4 brought up to date: the face and the body's placement remembered",
        all(o.FaceRecord and "BodyPlace" in o.PropertiesList for o in found),
        [(o.Label, bool(o.FaceRecord), "BodyPlace" in o.PropertiesList) for o in found],
    )
    for obj in found:
        f.drawn_on_face("R4 %s" % obj.Label, obj)
    h.fit()


def r3_undo():
    st["r3_redo"] = f.snapshot(f.flat())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


r3_undo.wait_ms = 1500


def r3_undone():
    f.follows("R3 Ctrl+Z", f.flat(), st["r3"], App.Placement())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


r3_undone.wait_ms = 1500


def r3_redone():
    f.follows("R3 Ctrl+Y", f.flat(), st["r3_redo"], App.Placement())


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    Gui.updateGui()
    h.new_errors()


h.run(
    "fixdecal_reopen",
    [setup]
    + f.decal_steps("r1_flat", f.TOP)
    + f.decal_steps("r1_wrapped", f.SIDE)
    + [r1_check]
    + move_steps("r1", "dx", "30")
    + [r1_moved, save_reopen("r2"), r2_check]
    + move_steps("r3", "dy", "20")
    + [r3_undo, r3_undone, r3_redone, save_reopen("r4", make_old), r4_check]
    + move_steps("r4", "rz", "90")
    + [cleanup],
)
