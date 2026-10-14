# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep values typed as a parameter or a formula (wave 4, modeling-2): Fusion takes a
formula in every value field, and the value then follows the parameter.

User parameters (Change Parameters, set up here): share = 0.5 (a plain number), lean = 5 deg.
Create Sketch on XY: a circle r2. Create Sketch on XZ: a line up 30 (the path). CREATE >
Sweep: the circle is taken, click the path. Type "share" in Distance: half the tube (15 mm),
the formula is listed under the fields. Type "lean / 5" in Taper Angle (1 degree). OK: the
sweep carries both as expressions. share = 0.25: the tube is 7.5 mm long now. Edit it from the
timeline: the formulas are listed again; type 0.5 over Distance (a plain number): the formula
goes, OK. Undo: the formula is back (7.5 mm); Redo. Save, close, reopen.

Hand-derived: a circle r2 swept d along a straight 30 mm path is a cone frustum (taper t):
r = 2, R = 2 + 30 d tan t, V = pi h (r^2 + r R + R^2) / 3 with h = 30 d.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
PI = math.pi
s = {}


def frustum(share, taper_deg):
    height = 30.0 * share
    r = 2.0
    big = r + height * math.tan(math.radians(taper_deg))
    return PI * height * (r * r + r * big + big * big) / 3.0


def panel():
    return st.panel("sweep")


def doc():
    return App.ActiveDocument


def sweep_feature():
    found = st.features("sweep")
    return found[0] if found else None


# -- setup ----------------------------------------------------------------------------------------
def new_design():
    from sciforge import parameters

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SweepFormula")
    parameters.add_user(doc(), "share", "", "0.5")
    parameters.add_user(doc(), "lean", "deg", "5")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch on XY", sk is not None)
    if sk:
        h.draw_circle(sk, 0, 0, 2)


def finish():
    h.ribbon("Finish Sketch")


def path_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(12, 0, 8))


def draw_path():
    sk = h.in_sketch()
    h.check("sketch on XZ", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (0, 30)])


def sweep():
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def click_path():
    p = panel()
    h.check("the sweep dialog takes the circle", p is not None and len(p.profiles) == 1)
    h.fit()
    h.check("clicked the path", h.click_edge(V(0, 0, 22)))


def type_share():
    p = panel()
    if p is None:
        return
    h.check("the whole tube first", st.near(h.solid_volume(), frustum(1.0, 0)), h.solid_volume())
    ui.type_into(p.distance, "share")


def share_taken():
    p = panel()
    if p is None:
        return
    h.check(
        "Distance follows share: half", st.near(h.solid_volume(), frustum(0.5, 0)), h.solid_volume()
    )
    h.check("the box shows 0.5", st.near(p.distance.value(), 0.5), p.distance.value())
    h.check(
        "the formula is listed under the fields",
        "Distance = share" in p.formulas.text() and p.formulas.isVisible(),
        p.formulas.text(),
    )
    h.check("no warning", "⚠" not in p.message.text(), p.message.text())
    ui.type_into(p.taper.widget, "lean / 5")


def taper_taken():
    p = panel()
    if p is None:
        return
    h.check(
        "Taper follows lean / 5 (1 degree)",
        st.near(h.solid_volume(), frustum(0.5, 1.0), 1e-5),
        (h.solid_volume(), frustum(0.5, 1.0)),
    )
    h.check(
        "both formulas listed", "Taper Angle = lean / 5" in p.formulas.text(), p.formulas.text()
    )
    h.task_button("OK")


def after_ok():
    f = sweep_feature()
    h.check("OK closed the dialog", panel() is None)
    engine = dict(f.ExpressionEngine) if f is not None else {}
    h.check("Distance carries the formula", "share" in engine.get("Distance", ""), engine)
    h.check("Taper carries the formula", "lean" in engine.get("TaperAngle", ""), engine)
    from sciforge import parameters

    parameters.set_user(doc(), "share", "0.25")
    doc().recompute()


def follows():
    h.check(
        "share = 0.25: the sweep follows (7.5 mm)",
        st.near(h.solid_volume(), frustum(0.25, 1.0), 1e-5),
        (h.solid_volume(), frustum(0.25, 1.0)),
    )
    s["title"] = [t for t in st.timeline_titles() if t.startswith("Sweep")]


def edit():
    h.check("double-click the sweep", st.edit_in_timeline(s["title"][0] if s["title"] else "?"))


def editing():
    p = panel()
    h.check("editing the sweep", p is not None and p.editing)
    if p is None:
        return
    h.check("the box shows 0.25", st.near(p.distance.value(), 0.25), p.distance.value())
    h.check("the formulas come back", "Distance = share" in p.formulas.text(), p.formulas.text())
    ui.type_into(p.distance, "0.5")


def plain_number():
    p = panel()
    if p is None:
        return
    h.check(
        "a plain number drops the formula", "Distance" not in p.formulas.text(), p.formulas.text()
    )
    h.check("half again", st.near(h.solid_volume(), frustum(0.5, 1.0), 1e-5), h.solid_volume())
    h.task_button("OK")


def edited():
    f = sweep_feature()
    engine = dict(f.ExpressionEngine) if f is not None else {}
    h.check("no Distance formula any more", "Distance" not in engine, engine)
    h.check("the taper formula stays", "TaperAngle" in engine, engine)


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    f = sweep_feature()
    engine = dict(f.ExpressionEngine) if f is not None else {}
    h.check("Ctrl+Z: the formula is back", "share" in engine.get("Distance", ""), engine)
    h.check(
        "Ctrl+Z: 7.5 mm again",
        st.near(h.solid_volume(), frustum(0.25, 1.0), 1e-5),
        h.solid_volume(),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check(
        "Ctrl+Y: half again", st.near(h.solid_volume(), frustum(0.5, 1.0), 1e-5), h.solid_volume()
    )


def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-m2-sweep-"), "m2_sweep.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    f = sweep_feature()
    engine = dict(f.ExpressionEngine) if f is not None else {}
    h.check(
        "reopened: same sweep", st.near(h.solid_volume(), frustum(0.5, 1.0), 1e-5), h.solid_volume()
    )
    h.check(
        "reopened: the taper still follows lean", "lean" in engine.get("TaperAngle", ""), engine
    )


type_share.wait_ms = 800
share_taken.wait_ms = 1200
taper_taken.wait_ms = 1200
plain_number.wait_ms = 1200

h.run(
    "modeling2_sweep_formula",
    [
        new_design,
        pick_xy,
        draw_circle,
        finish,
        path_sketch,
        pick_xz,
        draw_path,
        finish,
        sweep,
        click_path,
        type_share,
        share_taken,
        taper_taken,
        after_ok,
        follows,
        edit,
        editing,
        plain_number,
        edited,
        undo,
        undone,
        redo,
        redone,
        save,
        reopen,
        reopened,
    ],
)
