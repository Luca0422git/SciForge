# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sweep with a guide rail, a twist and Orientation Parallel. Only real input.

Sketch on XY: a 10 x 10 square centred on the origin. Sketch on XZ: the path, a line up the
Z axis from 0 to 40, and the rail, a line from (5, 0) to (15, 40) that leans away from it.
CREATE > Sweep: the square is taken by itself; click the path; Type Path + Guide Rail: the
Guide Rail box waits; click the rail. Profile Scaling Scale: the square grows evenly with
the rail (3 times wider at the top); Stretch: it grows only towards the rail; None: the rail
only turns it. Type Single Path, Twist 45: the square turns an eighth of a turn on the way
up. Orientation Parallel: the twist field is greyed (it needs Perpendicular). OK. Edit from
the timeline, back to Perpendicular with a 90 degree twist, then Cancel: the part stays as
it was.

Hand-derived: Scale is a frustum of a square pyramid, h (A0 + A1 + sqrt(A0 A1)) / 3 with
A0 = 100, A1 = 900; Stretch is a wedge, 40 * 10 * (10 + 30) / 2; None and Parallel are a
prism, 10 * 10 * 40; a twist keeps every horizontal section a 10 x 10 square, so the volume
stays 4000, and after 45 degrees the top square's corners point along the X and Y axes, so
the part reaches x = 5 sqrt(2).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
SCALE = 40.0 * (100.0 + 900.0 + 300.0) / 3.0
STRETCH = 40.0 * 10.0 * (10.0 + 30.0) / 2.0
PRISM = 4000.0
s = {}


def panel():
    return st.panel("sweep")


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SweepRail")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -5, -5, 5, 5)


def finish_square():
    h.ribbon("Finish Sketch")


def path_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 12, 0, 8)


def draw_path_and_rail():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (0, 40)])
        st.add_lines(sk, [(5, 0), (15, 40)])
        s["curves"] = sk


def finish_curves():
    h.ribbon("Finish Sketch")


def sweep_start():
    h.fit()
    h.click_empty()
    st.menu("Sweep")


def click_path():
    p = panel()
    h.check("the square is taken", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.fit()
    h.check("clicked the path", h.click_edge(V(0, 0, 32)))


def path_taken():
    p = panel()
    h.check("only the path line (the rail is not joined to it)", len(p.path) == 1, p.path)
    h.check("prism preview", st.near(h.solid_volume(), PRISM), h.solid_volume())
    h.check("choose Path + Guide Rail", ui.choose(p.type, "Path + Guide Rail"))


def rail_box():
    p = panel()
    h.check(
        "the Guide Rail box is shown and waits",
        p.fields["rail"].widget.isVisible() and p.active == "rail",
        p.active,
    )
    h.check("Profile Scaling shown", p.scaling.isVisible())
    h.check(
        "no Taper or Twist with a rail",
        not p.taper.widget.isVisible() and not p.twist.widget.isVisible(),
    )
    h.check("no preview until the rail is picked", h.solid_volume() == 0.0, h.solid_volume())
    h.fit()
    h.check("clicked the rail", h.click_edge(V(12.5, 0, 30)))


def scaled():
    p = panel()
    h.check("rail picked", len(p.rail) == 1, p.rail)
    h.check("Scale by default", p.scaling.currentText() == "Scale", p.scaling.currentText())
    h.check("Scale: pyramid frustum", st.near(h.solid_volume(), SCALE), (h.solid_volume(), SCALE))
    h.check(
        "3 times wider at the top",
        st.bbox(h.body().Shape) == [-15, -15, 0, 15, 15, 40],
        st.bbox(h.body().Shape),
    )
    h.fit()
    h.shot("1-scale")
    h.check("choose Stretch", ui.choose(p.scaling, "Stretch"))


def stretched():
    h.check("Stretch: wedge", st.near(h.solid_volume(), STRETCH), (h.solid_volume(), STRETCH))
    h.check(
        "wider only towards the rail",
        st.bbox(h.body().Shape) == [-15, -5, 0, 15, 5, 40],
        st.bbox(h.body().Shape),
    )
    h.shot("2-stretch")
    h.check("choose None", ui.choose(panel().scaling, "None"))


def not_scaled():
    h.check("None: the square stays 10 x 10", st.near(h.solid_volume(), PRISM), h.solid_volume())
    h.check("choose Single Path", ui.choose(panel().type, "Single Path"))


def single_again():
    p = panel()
    h.check("Twist shown again", p.twist.widget.isVisible() and p.twist.widget.isEnabled())
    ui.type_into(p.twist.widget, "45")


def twisted():
    h.check("twist keeps the volume", st.near(h.solid_volume(), PRISM, 1e-5), h.solid_volume())
    bb = st.bbox(h.body().Shape)
    h.check("the top corners turned 45 degrees", st.near(bb[3], 5 * math.sqrt(2), 1e-4), bb)
    h.fit()
    h.shot("3-twist")
    h.check("choose Parallel", ui.choose(panel().orientation, "Parallel"))


def parallel():
    p = panel()
    h.check("Parallel greys the twist", not p.twist.widget.isEnabled())
    h.check("parallel: a straight prism", st.near(h.solid_volume(), PRISM), h.solid_volume())
    h.check("no twist", st.bbox(h.body().Shape) == [-5, -5, 0, 5, 5, 40], st.bbox(h.body().Shape))
    h.task_button("OK")


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), PRISM), h.solid_volume())
    h.check("the curves sketch is hidden", not s["curves"].ViewObject.Visibility)
    s["volume"] = h.solid_volume()


def edit():
    h.check("double-click Sweep 1", st.edit_in_timeline("Sweep 1"))


def edit_perpendicular():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "edit shows Parallel",
        p.orientation.currentText() == "Parallel",
        p.orientation.currentText(),
    )
    h.check("its sketch is shown while editing", s["curves"].ViewObject.Visibility)
    h.check("choose Perpendicular", ui.choose(p.orientation, "Perpendicular"))


def edit_twist():
    ui.type_into(panel().twist.widget, "90")


def edit_cancel():
    bb = st.bbox(h.body().Shape)
    h.check("preview twists", bb[3] > 5.0 + 1e-3 or st.near(h.solid_volume(), PRISM, 1e-5), bb)
    h.task_button("Cancel")


def cancelled():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check(
        "Cancel keeps the part as it was", st.near(h.solid_volume(), s["volume"]), h.solid_volume()
    )
    h.check(
        "no twist after Cancel",
        st.bbox(h.body().Shape) == [-5, -5, 0, 5, 5, 40],
        st.bbox(h.body().Shape),
    )
    h.check("the sketch hides again", not s["curves"].ViewObject.Visibility)
    h.check("still one sweep", len(st.features("sweep")) == 1, st.features("sweep"))


h.run(
    "sweep_loft_sweep_rail",
    [
        new_design,
        pick_xy,
        draw_square,
        finish_square,
        path_sketch,
        pick_xz,
        draw_path_and_rail,
        finish_curves,
        sweep_start,
        click_path,
        path_taken,
        rail_box,
        scaled,
        stretched,
        not_scaled,
        single_again,
        twisted,
        parallel,
        kept,
        edit,
        edit_perpendicular,
        edit_twist,
        edit_cancel,
        cancelled,
    ],
)
