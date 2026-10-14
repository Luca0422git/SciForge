# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole Tap Types Taper Tapped and Clearance by fastener (wave 4, modeling-2), real input
only, on a 40 x 30 x 20 box:

1. H, click the top face. Hole Tap Type Taper Tapped: the Thread Type is NPT, the Size
   1/8-27 NPT; the diameter is the pipe thread's minor diameter at the opening (8.737) and
   cannot be typed; Depth 12, Drill Point Flat. The hole's wall is a cone: its half angle
   is measured on the model (atan(1/32) = 1.79 degrees, 1 in 16 on the diameter); the
   thread is drawn as a cosmetic thread. OK.
2. H, click the top face again. Clearance, ISO, size 6, Fit Normal, Extents All: the hole
   measures 6.6 (ISO 273). Hole Type Counterbore: the fasteners offered are the socket head
   and hex head screws; the counterbore is the socket head's (11 x 6.4, DIN 974-1). Fastener
   Type Hex Head Screw: the counterbore grows to 18 x 4.4. Close fit: 6.4. OK.
3. Edit the taper hole from the timeline: its options come back; Size 1/4-18 NPT, OK.
4. Ctrl+Z takes the edit back, Ctrl+Y redoes it.
5. Save, close, reopen: the taper hole is still a taper hole with its size, the clearance
   hole keeps its fastener; edit, Cancel.
6. Thread Type BSPT in an open dialog: Rc sizes; Esc leaves the model unchanged.

Hand-derived (sciforge/hole_tables.py has the standards): a taper hole of depth t from the
minor diameter D at the opening is a cone frustum pi t/3 (R^2 + R r + r^2), R = D/2,
r = R - t/32; a clearance hole of d through 20 is pi d^2/4 20; a counterbore D x c on it
adds pi (D^2 - d^2)/4 c.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs

V = App.Vector
s = {}
BOX = 24000.0


def tables():
    from sciforge import hole_tables

    return hole_tables


def frustum(depth, d):
    r1 = d / 2.0
    r2 = r1 - depth / 32.0
    return math.pi * depth / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)


def drawn():
    from sciforge import thread_ui

    return thread_ui.CosmeticThreads.count(App.ActiveDocument.Name)


def panel():
    return hs.hole_panel()


def doc():
    return App.ActiveDocument


def cone_half_angle(hole_obj):
    """The half angle (degrees) of the conical face the hole made, measured on the model."""
    for face in hole_obj.Shape.Faces:
        if face.Surface.TypeId == "Part::GeomCone":
            return math.degrees(abs(face.Surface.SemiAngle))
    return None


def hole_radius(hole_obj, near):
    """The radius of the hole's cylinder whose axis passes nearest `near` (measured)."""
    best = None
    for face in hole_obj.Shape.Faces:
        if face.Surface.TypeId != "Part::GeomCylinder":
            continue
        centre = face.Surface.Center
        gap = math.hypot(centre.x - near.x, centre.y - near.y)
        if (
            best is None
            or gap < best[0]
            or (abs(gap - best[0]) < 1e-6 and face.Surface.Radius < best[1])
        ):
            best = (gap, face.Surface.Radius)
    return best[1] if best else None


# -- 1. Taper Tapped (NPT) ------------------------------------------------------------------
def start_hole():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Hole")


def click_top_left():
    h.click(V(12, 12, 20))


def taper():
    p = panel()
    h.check("1 hole placed", p is not None and p.target is not None, hs.message(p))
    if p:
        hs.type_into(p.pos_x.widget, "12")
        hs.type_into(p.pos_y.widget, "12")
        b.choose(p.tap_type, "Taper Tapped")


def taper_fields():
    p = panel()
    if p is None:
        return
    t = tables().taper_thread("npt", "1/8")
    h.check(
        "1 Thread Type NPT, Size 1/8-27 NPT",
        p.taper_kind.currentData() == "npt" and p.taper_size.currentText() == "1/8-27 NPT",
        (p.taper_kind.currentText(), p.taper_size.currentText()),
    )
    h.check(
        "1 the thread size fields of a straight thread are hidden",
        not p.designation.isVisible() and not p.thread_class.isVisible() and not p.size.isVisible(),
    )
    h.check(
        "1 the diameter is the minor diameter at the opening",
        abs(p.diameter.value() - t.minor) < 0.006,
        (p.diameter.value(), t.minor),
    )
    h.check("1 and is set by the size", not p.diameter.widget.isEnabled())
    b.choose(p.drill_point, "Flat")
    hs.type_into(p.depth.widget, "12")


def taper_built():
    p = panel()
    t = tables().taper_thread("npt", "1/8")
    v = h.solid_volume()
    expect = BOX - frustum(12, t.minor)
    h.check("1 NPT 1/8 taper hole volume", hs.close(v, expect), (v, expect))
    angle = cone_half_angle(p.target) if p and p.target else None
    h.check(
        "1 the taper measured on the model: 1.79 deg (1 in 16)",
        angle is not None and abs(angle - math.degrees(math.atan(1.0 / 32.0))) < 1e-6,
        angle,
    )
    h.check("1 the pipe thread is drawn as a cosmetic thread", drawn() == 1, drawn())
    h.shot("1-npt")
    s["v1"] = v
    h.task_button("OK")


def taper_ok():
    h.check("1 OK closed the dialog", panel() is None)
    holes = hs.holes()
    h.check("1 one hole", len(holes) == 1, holes)
    if holes:
        h.check("1 FreeCAD's hole is tapered", holes[0].Tapered, holes[0].Tapered)
    h.check("1 the part kept it", hs.close(h.solid_volume(), s["v1"]), h.solid_volume())


# -- 2. Clearance by fastener -----------------------------------------------------------------
def click_top_right():
    h.fit()
    h.click(V(28, 18, 20))


def clearance():
    p = panel()
    h.check("2 second hole placed", p is not None and p.target is not None, hs.message(p))
    if p is None:
        return
    hs.type_into(p.pos_x.widget, "28")
    hs.type_into(p.pos_y.widget, "18")
    b.choose(p.tap_type, "Clearance")
    b.choose(p.extent, "All")


def clearance_fields():
    p = panel()
    if p is None:
        return
    h.check("2 Fastener Type shown", p.fastener.isVisible())
    h.check("2 a simple hole offers every fastener", p.fastener.count() == 3, p.fastener.count())
    b.choose(p.standard, "ISO Metric profile")
    b.choose(p.size, "6")
    b.choose(p.fit, "Normal")


def normal_fit():
    p = panel()
    if p is None:
        return
    h.check(
        "2 M6 normal fit: 6.6 in the dialog",
        abs(p.diameter.value() - 6.6) < 1e-9,
        p.diameter.value(),
    )
    r = hole_radius(p.target, V(28, 18, 0))
    h.check("2 M6 normal fit: 6.6 measured on the model", r and abs(2 * r - 6.6) < 1e-9, r)
    expect = s["v1"] - hs.cylinder(6.6, 20)
    h.check("2 clearance hole volume", hs.close(h.solid_volume(), expect), h.solid_volume())
    b.choose(p.hole_type, "Counterbore")


def counterbore():
    p = panel()
    if p is None:
        return
    keys = [p.fastener.itemData(i) for i in range(p.fastener.count())]
    h.check("2 a counterbore holds socket and hex heads", keys == ["socket_head", "hex_head"], keys)
    h.check(
        "2 the socket head's counterbore: 11 x 6.4",
        abs(p.cbore_diameter.value() - 11.0) < 1e-9 and abs(p.cbore_depth.value() - 6.4) < 1e-9,
        (p.cbore_diameter.value(), p.cbore_depth.value()),
    )
    expect = s["v1"] - hs.cylinder(6.6, 20) - (hs.cylinder(11, 6.4) - hs.cylinder(6.6, 6.4))
    h.check("2 counterbored volume", hs.close(h.solid_volume(), expect), h.solid_volume())
    h.shot("2-socket-cbore")
    b.choose(p.fastener, "Hex Head Screw (ISO 4017)")


def hex_head():
    p = panel()
    if p is None:
        return
    h.check(
        "2 a hex head needs 18 x 4.4",
        abs(p.cbore_diameter.value() - 18.0) < 1e-9 and abs(p.cbore_depth.value() - 4.4) < 1e-9,
        (p.cbore_diameter.value(), p.cbore_depth.value()),
    )
    b.choose(p.fit, "Close")


def close_fit():
    p = panel()
    if p is None:
        return
    r = hole_radius(p.target, V(28, 18, 0))
    h.check("2 close fit: 6.4 measured", r and abs(2 * r - 6.4) < 1e-9, r)
    expect = s["v1"] - hs.cylinder(6.4, 20) - (hs.cylinder(18, 4.4) - hs.cylinder(6.4, 4.4))
    h.check("2 hex counterbore, close fit", hs.close(h.solid_volume(), expect), h.solid_volume())
    s["v2"] = h.solid_volume()
    h.task_button("OK")


def clearance_ok():
    h.check("2 OK closed the dialog", panel() is None)
    h.check("2 two holes", len(hs.holes()) == 2, hs.holes())
    h.check("2 kept", hs.close(h.solid_volume(), s["v2"]), h.solid_volume())


# -- 3. Edit from the timeline --------------------------------------------------------------
def edit_taper():
    h.fit()
    b.timeline_double_click("Hole 1", click_first=True)


def edit_open():
    p = panel()
    h.check("3 editing Hole 1", p is not None and p.editing)
    if p is None:
        return
    h.check("3 Taper Tapped comes back", p.tap_type.currentText() == "Taper Tapped")
    h.check("3 with its size", p.taper_size.currentData() == "1/8", p.taper_size.currentText())
    b.choose(p.taper_size, "1/4-18 NPT")


def edit_size():
    p = panel()
    t = tables().taper_thread("npt", "1/4")
    if p:
        h.check(
            "3 the diameter follows the size",
            abs(p.diameter.value() - t.minor) < 0.006,
            (p.diameter.value(), t.minor),
        )
    expect = s["v2"] + frustum(12, tables().taper_thread("npt", "1/8").minor) - frustum(12, t.minor)
    s["v3"] = expect
    h.check("3 1/4 NPT volume", hs.close(h.solid_volume(), expect), (h.solid_volume(), expect))
    h.task_button("OK")


def edited():
    h.check("3 OK closed the edit", panel() is None)
    h.check("3 the edit stays", hs.close(h.solid_volume(), s["v3"]), h.solid_volume())


# -- 4. Undo / redo -------------------------------------------------------------------------
def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def after_undo():
    h.check("4 Ctrl+Z takes the edit back", hs.close(h.solid_volume(), s["v2"]), h.solid_volume())
    meta = hs.holes()[0] if hs.holes() else None
    from sciforge import hole

    h.check(
        "4 and the size is 1/8 again",
        meta is not None and hole.read(meta)["taper_size"] == "1/8",
        meta and hole.read(meta)["taper_size"],
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def after_redo():
    h.check("4 Ctrl+Y redoes it", hs.close(h.solid_volume(), s["v3"]), h.solid_volume())


# -- 5. Save, close, reopen ---------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-m2-holes-"), "m2_holes.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("5 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import hole

    h.check("5 same part after reopening", hs.close(h.solid_volume(), s["v3"]), h.solid_volume())
    holes = sorted(hs.holes(), key=lambda o: o.ID)
    h.check("5 two holes", len(holes) == 2, holes)
    if len(holes) == 2:
        first, second = hole.read(holes[0]), hole.read(holes[1])
        h.check(
            "5 the taper hole reads back",
            first["tap_type"] == "taper" and first["taper_size"] == "1/4",
            (first["tap_type"], first["taper_size"]),
        )
        h.check(
            "5 the clearance hole keeps its fastener",
            second["tap_type"] == "clearance" and second["fastener"] == "hex_head",
            (second["tap_type"], second["fastener"]),
        )
    b.timeline_double_click("Hole 2", click_first=True)


def reopened_edit():
    p = panel()
    h.check("5 editing Hole 2 after reopening", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "5 Clearance, Hex Head, 6, Close",
        p.tap_type.currentText() == "Clearance"
        and p.fastener.currentData() == "hex_head"
        and p.size.currentText() == "6"
        and p.fit.currentText() == "Close",
        (p.tap_type.currentText(), p.fastener.currentText(), p.size.currentText()),
    )
    h.task_button("Cancel")


def after_cancel():
    h.check("5 Cancel changed nothing", hs.close(h.solid_volume(), s["v3"]), h.solid_volume())


# -- 6. BSPT in a new dialog, Esc ------------------------------------------------------------
def new_hole():
    start_hole()


def click_again():
    h.fit()
    h.click(V(30, 8, 20))


def bspt():
    p = panel()
    h.check("6 a third hole is previewed", p is not None and p.target is not None)
    if p is None:
        return
    b.choose(p.tap_type, "Taper Tapped")
    b.choose(p.taper_kind, "ISO Taper Pipe Thread (BSPT, Rc)")


def bspt_sizes():
    p = panel()
    if p is None:
        return
    labels = [p.taper_size.itemText(i) for i in range(p.taper_size.count())]
    h.check(
        "6 BSPT sizes are Rc sizes", labels and all(x.startswith("Rc ") for x in labels), labels
    )
    t = tables().taper_thread("bspt", p.taper_size.currentData())
    h.check(
        "6 its minor diameter",
        t is not None and abs(p.diameter.value() - t.minor) < 0.006,
        p.diameter.value(),
    )
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("6 Esc closed the dialog", panel() is None)
    h.check("6 still two holes", len(hs.holes()) == 2, hs.holes())
    h.check("6 the part is unchanged", hs.close(h.solid_volume(), s["v3"]), h.solid_volume())
    h.check("valid solid", h.body().Shape.isValid())
    hs.no_popups("taper and clearance holes")


taper_fields.wait_ms = 800
normal_fit.wait_ms = 800
counterbore.wait_ms = 800
hex_head.wait_ms = 800
close_fit.wait_ms = 800
edit_size.wait_ms = 800
bspt_sizes.wait_ms = 800

h.run(
    "modeling2_holes",
    b.box_steps("M2Holes", height=20)
    + [
        start_hole,
        click_top_left,
        taper,
        taper_fields,
        taper_built,
        taper_ok,
        start_hole,
        click_top_right,
        clearance,
        clearance_fields,
        normal_fit,
        counterbore,
        hex_head,
        close_fit,
        clearance_ok,
        edit_taper,
        edit_open,
        edit_size,
        edited,
        undo,
        after_undo,
        redo,
        after_redo,
        save,
        reopen,
        reopened,
        reopened_edit,
        after_cancel,
        new_hole,
        click_again,
        bspt,
        bspt_sizes,
        after_esc,
    ],
)
