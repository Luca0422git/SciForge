# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear: refusals with a clear message, a parameter driving the teeth, a cut into a part
from its selected face, New Component, and Ctrl+Z / Ctrl+Y. Only real input.

1. A user parameter n = 20 (Change Parameters made it). Gear, XY, centre on the origin.
   Number of Teeth 3: the dialog says a spur gear needs at least 6 and OK stays open.
   Hole Diameter 60, Root Fillet Radius 3, Backlash 3: each is held at the largest value
   that works and the dialog says so (Luca's decision of 2026-10-21; they were refused:
   "too big ... at most 41", "does not fit ... at most", "come to a point").
   Then hole 10, fillet 0.5, backlash 0, Number of Teeth "n": 20 teeth, the formula is
   listed. OK. n = 26 in Change Parameters: the gear follows.
2. A Box 60 x 60 x 10 beside it; click its top face, Gear: the face is taken at once;
   centre on the box's middle; Operation Cut, Thickness -4: the teeth are cut into the
   block. OK. Ctrl+Z puts the block back whole, Ctrl+Y cuts it again.
3. Gear on XY far away, Operation New Component: its body lies in a component of its own.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
s = {}


def area(**options):
    from sciforge import gear_core

    return gear_core.area(options)


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def doc():
    return App.ActiveDocument


def panel():
    return pi.panel("GearPanel")


def message():
    p = panel()
    return p.message.text() if p is not None else ""


# -- 1. refusals and a parameter ------------------------------------------------------------------
def new_design():
    from sciforge import parameters

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("GearRefuse")
    parameters.add_user(doc(), "n", "", "20")  # as Change Parameters makes it
    doc().recompute()
    h.fit()
    pi.menu("Gear")


def plane():
    pl.click_on_plane(V(15, -15, 0))


def centre():
    pl.click_on_plane(V(0, 0, 0))


centre.wait_ms = 2000


def three_teeth():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    s["good"] = area() * 10.0
    h.check("the default gear", near(vol(), s["good"]), vol())
    ui.type_into(p.teeth.widget, "3")


three_teeth.wait_ms = 1500


def too_few():
    text = message()
    h.check("says why: at least 6 teeth", "at least 6 teeth" in text, text)
    h.check("the last good gear stays", near(vol(), s["good"]), vol())
    h.task_button("OK")


too_few.wait_ms = 1500


def ok_refused():
    h.check("OK refused: the dialog stays", panel() is not None)
    h.check("still says why", "at least 6 teeth" in message(), message())
    p = panel()
    ui.type_into(p.teeth.widget, "24")


ok_refused.wait_ms = 1000


def big_hole():
    h.check("24 teeth again: no message", message() == "", message())
    ui.type_into(panel().hole.widget, "60")


big_hole.wait_ms = 1500


def note():
    p = panel()
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def hole_refused():
    p = panel()
    hole = p.options.get("hole") if p is not None else 0
    h.check("hole: held at the largest, 41 mm", near(hole, 41.0), hole)
    h.check("and said", note() == "60 mm does not fit: limited to 41.00 mm", note())
    h.check("no error", message() == "", message())
    h.shot("1-hole-refused")
    ui.type_into(panel().hole.widget, "10")


hole_refused.wait_ms = 1500


def big_fillet():
    h.check("hole 10: no message", message() == "", message())
    ui.type_into(panel().fillet.widget, "3")


big_fillet.wait_ms = 1500


def fillet_refused():
    from sciforge import gear_core

    p = panel()
    fillet = p.options.get("fillet") if p is not None else 0
    most = gear_core.max_fillet(dict(p.options, fillet=0.0)) if p is not None else 0
    h.check("fillet: held at the largest that fits", 0.5 < fillet <= most + 1e-9, (fillet, most))
    h.check("and said", note() == "3 mm does not fit: limited to %.2f mm" % fillet, note())
    h.check("no error", message() == "", message())
    ui.type_into(panel().fillet.widget, "0.5")


fillet_refused.wait_ms = 1500


def big_backlash():
    ui.type_into(panel().backlash.widget, "3")


big_backlash.wait_ms = 1500


def backlash_refused():
    p = panel()
    backlash = p.options.get("backlash") if p is not None else 0
    h.check("backlash: held before the teeth come to a point", 0.0 < backlash < 3.0, backlash)
    h.check("and said", note() == "3 mm does not fit: limited to %.2f mm" % backlash, note())
    h.check("no error", message() == "", message())
    ui.type_into(panel().backlash.widget, "0")


backlash_refused.wait_ms = 1500


def teeth_formula():
    h.check("no message", message() == "", message())
    ui.type_into(panel().teeth.widget, "n")


teeth_formula.wait_ms = 1500


def formula_taken():
    p = panel()
    h.check("n = 20 teeth", near(p.teeth.value(), 20.0), p.teeth.value())
    h.check("the gear follows", near(vol(), area(teeth=20) * 10.0), vol())
    h.check("the formula is listed", "n" in p.formulas.text(), p.formulas.text())
    h.task_button("OK")


formula_taken.wait_ms = 2000


def formula_kept():
    from sciforge import gear, parameters

    h.check("dialog closed", pi.no_dialog())
    feature = [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Gear"][0]
    profile = gear.profile_of(feature)
    h.check(
        "Teeth follows n",
        profile is not None and "Teeth" in dict(profile.ExpressionEngine),
        profile and profile.ExpressionEngine,
    )
    parameters.set_user(doc(), "n", "26")  # in Change Parameters
    doc().recompute()


def parameter_changed():
    s["gear"] = area(teeth=26) * 10.0
    h.check("n = 26: the gear follows", near(vol(), s["gear"]), vol())
    h.fit()


parameter_changed.wait_ms = 1500


# -- 2. a gear cut into a block -------------------------------------------------------------------
def box_start():
    h.click_empty()
    pi.menu("Box")


def box_plane():
    pl.click_on_plane(V(30, -30, 0))  # a corner of the XY square the parts leave free


def box_corner():
    pl.click_on_plane(V(60, -30, 0))


def box_corner2():
    pl.click_on_plane(V(120, 30, 0))


box_corner2.wait_ms = 1200


def box_height():
    p = pi.panel("BoxPanel")
    if p is not None:
        ui.type_into(p.height.widget, "10")


def box_ok():
    h.task_button("OK")


def box_done():
    h.check("block 60 x 60 x 10", near(vol() - s["gear"], 36000.0), vol() - s["gear"])
    s["before"] = vol()
    h.fit()


box_done.wait_ms = 1500


def select_top():
    h.click(V(105, 15, 10))


def cut_start():
    h.check("block top selected", bool(Gui.Selection.getSelectionEx()))
    pi.menu("Gear")


def cut_centre():
    p = panel()
    h.check("the face is taken at once", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(90, 0, 10))


cut_centre.wait_ms = 2000


def cut_operation():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    h.check("a New Body first (Fusion's sample)", p.operation.currentText() == "New Body")
    h.check("Cut", ui.choose(p.operation, "Cut"))


cut_operation.wait_ms = 1500


def cut_values():
    p = panel()
    ui.type_into(p.teeth.widget, "16")


cut_values.wait_ms = 1500


def cut_hole():
    ui.type_into(panel().hole.widget, "0")


cut_hole.wait_ms = 1500


def cut_depth():
    ui.type_into(panel().thickness.widget, "-4")


cut_depth.wait_ms = 1500


def cut_check():
    s["cut"] = area(teeth=16, hole=0) * 4.0
    removed = s["before"] - vol()
    h.check(
        "the gear is cut 4 deep into the block", near(removed, s["cut"], 1e-5), (removed, s["cut"])
    )
    h.check("no message", message() == "", message())
    h.fit()
    h.shot("2-cut")
    h.task_button("OK")


cut_check.wait_ms = 2000


def cut_kept():
    h.check("a Pocket", len(pi.steps_of("Pocket")) == 1)
    h.check("cut kept", near(s["before"] - vol(), s["cut"], 1e-5), vol())
    h.click_empty()
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def ctrl_z():
    h.check("Ctrl+Z: the block is whole again", near(vol(), s["before"]), vol())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


ctrl_z.wait_ms = 1500


def ctrl_y():
    h.check("Ctrl+Y: cut again", near(s["before"] - vol(), s["cut"], 1e-5), vol())
    s["volume"] = vol()
    pi.menu("Gear")


ctrl_y.wait_ms = 1500


# -- 3. New Component -----------------------------------------------------------------------------
def comp_plane():
    pl.click_on_plane(V(-40, -40, 0))  # a corner of the XY square the parts leave free


def comp_centre():
    pl.click_on_plane(V(0, -80, 0))


comp_centre.wait_ms = 2000


def comp_operation():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    h.check("New Component", ui.choose(p.operation, "New Component"))


comp_operation.wait_ms = 1500


def comp_ok():
    p = panel()
    expected = area(teeth=16, hole=0) * 4.0  # the last gear's values come back
    h.check("thickness remembered: -4", p is not None and near(p.thickness.value(), -4.0))
    h.check("the new gear", near(vol() - s["volume"], expected, 1e-5), vol() - s["volume"])
    h.task_button("OK")


comp_ok.wait_ms = 2000


def comp_kept():
    from sciforge import components

    feature = [o for o in doc().Objects if getattr(o, "SciForgeType", "") == "Gear"][-1]
    body = feature.getParentGeoFeatureGroup()
    part = components.container_of(body) if body is not None else None
    h.check("its body is in a new component", part is not None, body and body.Label)
    h.fit()
    h.shot("3-end")


h.run(
    "gear_refuse",
    [
        new_design,
        plane,
        centre,
        three_teeth,
        too_few,
        ok_refused,
        big_hole,
        hole_refused,
        big_fillet,
        fillet_refused,
        big_backlash,
        backlash_refused,
        teeth_formula,
        formula_taken,
        formula_kept,
        parameter_changed,
        box_start,
        box_plane,
        box_corner,
        box_corner2,
        box_height,
        box_ok,
        box_done,
        select_top,
        cut_start,
        cut_centre,
        cut_operation,
        cut_values,
        cut_hole,
        cut_depth,
        cut_check,
        cut_kept,
        ctrl_z,
        ctrl_y,
        comp_plane,
        comp_centre,
        comp_operation,
        comp_ok,
        comp_kept,
    ],
)
