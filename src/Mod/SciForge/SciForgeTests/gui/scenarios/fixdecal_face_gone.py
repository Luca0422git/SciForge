# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal whose face goes away is flagged, not left floating: its step is red with the
reason, the picture is not drawn; Edit Decal puts it on another face. Only real input.
docs/sciforge/parity/misc.md, Decal (Luca: "decals dont follow their faces when moved").

Body: a box 40 x 30 x 10 with a boss 10 x 10 x 10 on its top (x 15..25, y 10..20); a
cylinder r 10, 40 high at x 100 (Body001).

G1 INSERT > Decal, click the boss's front (y 10): a decal on it.
G2 Timeline right-click on the boss > Delete: the face is gone; the decal's step is red with
   the reason and the picture is not drawn (no picture floating in the air).
G3 Ctrl+Z: the boss and the decal on it are back; Ctrl+Y: gone again, red.
G4 Double-click the red decal: Edit Decal says the face is gone and waits; click the box's
   top: the decal is there, not red; OK.
G5 Ctrl+Z: red again; Ctrl+Y: on the top.
G6 Edit Decal, Select Face, click the cylinder's side: the decal moves onto the other body,
   wrapped round it; OK.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
BOSS_FRONT = V(20, 10, 15)
st = {}


def doc():
    return App.ActiveDocument


def decal():
    found = f.decals()
    return found[0] if found else None


def setup():
    found = f.box_and_cylinder("DecalFaceGone")
    d = doc()
    body = d.getObject(found["box"])
    boss = body.newObject("PartDesign::AdditiveBox", "Boss")
    boss.Length, boss.Width, boss.Height = 10, 10, 10
    boss.Placement.Base = V(15, 10, 10)
    body.Tip = boss
    d.recompute()
    st.update(found)
    st["boss"] = boss.Name
    h.fit()


def g1_check():
    obj = decal()
    h.check("G1 a decal on the boss", obj is not None, f.decals())
    if obj is None:
        return
    st["g1"] = f.snapshot(obj)
    f.drawn_on_face("G1", obj)
    c = f.centre(obj)
    h.check("G1 on the boss's front", f.near(c.y, 10.0, 1e-3) and c.z > 10.0, c)


# -- G2 ----------------------------------------------------------------------------------------
def g2_delete():
    title = m.timeline_title(doc().getObject(st["boss"]))
    h.check("G2 the boss in the timeline", title is not None, t.titles())
    t.menu(title, "Delete")


g2_delete.wait_ms = 2000


def g2_check():
    h.check("G2 the boss is deleted", doc().getObject(st["boss"]) is None)
    obj = decal()
    h.check("G2 the decal is kept", obj is not None)
    if obj is None:
        return
    h.check("G2 its step is red", f.red(obj), obj.State)
    h.check(
        "G2 with the reason",
        "face this decal was on is gone" in obj.getStatusString(),
        obj.getStatusString(),
    )
    points, tris, _picture = obj.ViewObject.Proxy.drawn()
    h.check("G2 no picture left floating", points == 0 and tris == 0, (points, tris))
    h.shot("G2-gone")
    h.new_errors()  # the red step is reported (expected)


# -- G3 ----------------------------------------------------------------------------------------
def g3_undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


g3_undo.wait_ms = 2000


def g3_undone():
    h.check("G3 Ctrl+Z: the boss is back", doc().getObject(st["boss"]) is not None)
    f.follows("G3 Ctrl+Z: the decal on it", decal(), st["g1"], App.Placement())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


g3_undone.wait_ms = 2000


def g3_redone():
    h.check("G3 Ctrl+Y: the boss is gone", doc().getObject(st["boss"]) is None)
    obj = decal()
    h.check("G3 Ctrl+Y: red again", obj is not None and f.red(obj), obj and obj.State)
    h.check(
        "G3 and not drawn",
        obj is not None and obj.ViewObject.Proxy.drawn()[0] == 0,
        obj and obj.ViewObject.Proxy.drawn(),
    )
    h.new_errors()


# -- G4 ----------------------------------------------------------------------------------------
def g4_edit():
    t.double_click(m.timeline_title(decal()))


g4_edit.wait_ms = 1500


def g4_waits():
    p = f.panel()
    h.check("G4 Edit Decal", p is not None and p.title == "Edit Decal", p)
    if p is None:
        return
    h.check(
        "G4 it says the face is gone and waits for one",
        "gone" in p.info.text() and "Click a face" in p.face_label.text(),
        (p.info.text(), p.face_label.text()),
    )
    h.click(f.TOP)


g4_waits.wait_ms = 1500


def g4_check():
    obj = decal()
    h.check("G4 on the box's top now", obj is not None and not f.red(obj), obj and obj.State)
    if obj is None:
        return
    c = f.centre(obj)
    h.check("G4 where the top was clicked", (c - f.TOP).Length < 0.5, c)
    f.drawn_on_face("G4", obj)
    p = f.panel()
    h.check("G4 the dialog names the face", p is not None and "Face" in p.face_label.text())
    st["g4"] = f.snapshot(obj)
    h.task_button("OK")


g4_check.wait_ms = 1200


def g4_ok():
    h.check("G4 OK closed the dialog", f.panel() is None)
    f.follows("G4 after OK", decal(), st["g4"], App.Placement())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


g4_ok.wait_ms = 2000


# -- G5 ----------------------------------------------------------------------------------------
def g5_undone():
    obj = decal()
    h.check("G5 Ctrl+Z: red again", obj is not None and f.red(obj), obj and obj.State)
    h.new_errors()
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


g5_undone.wait_ms = 2000


def g5_redone():
    f.follows("G5 Ctrl+Y: on the top", decal(), st["g4"], App.Placement())


# -- G6 ----------------------------------------------------------------------------------------
def g6_edit():
    t.double_click(m.timeline_title(decal()))


g6_edit.wait_ms = 1500


def g6_select():
    p = f.panel()
    if h.check("G6 Edit Decal", p is not None and p.face_button is not None, p):
        w.click(p.face_button)


g6_select.wait_ms = 800


def g6_click():
    p = f.panel()
    h.check(
        "G6 Select Face waits for a face",
        p is not None and "Click a face" in p.face_label.text(),
        p and p.face_label.text(),
    )
    h.click(f.SIDE)


g6_click.wait_ms = 1500


def g6_check():
    obj = decal()
    cyl = doc().getObject(st["cyl"])
    h.check(
        "G6 the decal is on the cylinder", obj is not None and obj.Body is cyl, obj and obj.Body
    )
    h.check("G6 wrapped round it", obj is not None and obj.Surface == "Cylinder")
    f.drawn_on_face("G6", obj)
    radii = f.radii(obj, V(100, 0, 0), V(0, 0, 1)) if obj is not None else []
    h.check(
        "G6 10 mm from the cylinder's axis",
        radii and min(radii) > 9.95 and max(radii) < 10.1,
        radii and (min(radii), max(radii)),
    )
    h.shot("G6-other-body")
    h.task_button("OK")


g6_check.wait_ms = 1200


def g6_ok():
    obj = decal()
    h.check("G6 OK kept it", f.panel() is None and obj is not None and not f.red(obj))


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.new_errors()


h.run(
    "fixdecal_face_gone",
    [setup]
    + f.decal_steps("g1", BOSS_FRONT)
    + [
        g1_check,
        g2_delete,
        g2_check,
        g3_undo,
        g3_undone,
        g3_redone,
        g4_edit,
        g4_waits,
        g4_check,
        g4_ok,
        g5_undone,
        g5_redone,
        g6_edit,
        g6_select,
        g6_click,
        g6_check,
        g6_ok,
        cleanup,
    ],
)
