# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rib like a Fusion user, only real input.

An L bracket: a sketch on XZ, the L outline (legs 40 long, 5 thick), Extrude 20 (it goes
to y -20). A sketch on XZ again with a line from (5, 25) to (25, 5) across the inside
corner. CREATE > Rib: click the line: To Next fills the corner triangle (a gusset), 2 thick
about the sketch plane. Thickness 4; One Side (into the bracket's side); Flip Side would
turn it out of the side face, where only edges touch the part: the dialog says why; back;
Symmetric and 2 again; Depth Options Depth, 5: a strip along the line; drag the
blue depth arrow; To Next again; OK. Undo / redo. Edit from the timeline: thickness 3, OK.
Flip Direction in an edit says why it cannot be built (nothing to reach on that side) and
Cancel keeps the rib. Esc cancels a new Rib.

Hand-derived: L area 40 * 5 + 35 * 5 = 375, times 20 = 7500. The gusset triangle has legs 20
(from the corner (5, 5) to the line): area 200, times the thickness. Depth d: a strip 20
sqrt(2) long and d wide; where it runs into the legs (only on the half of the thickness
inside the bracket, y < 0) two triangles of area d^2 / 2 each are already material, less the
tips that poke out past the 5 thick legs once d > 5 sqrt(2).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
L = 7500.0
TRI = 200.0
STRIP = 20.0 * math.sqrt(2.0)
s = {}


def panel():
    return st.panel("rib")


def depth_volume(d, t=2.0):
    """The strip d deep; on the half of the thickness inside the bracket its ends overlap the
    5 thick legs in two right triangles of area d^2 / 2, less the corners that poke out past
    the legs' outer faces once d > 5 sqrt(2)."""
    over = max(0.0, d - 5.0 * math.sqrt(2.0))
    return L + STRIP * d * t - (d * d - over * over) * (t / 2.0)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Rib")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    h.click(V(12, 0, 8))


def draw_l():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(0, 0), (40, 0), (40, 5), (5, 5), (5, 40), (0, 40)], closed=True)


def finish_l():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_distance():
    from sciforge import taskui

    p = taskui.current()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("extrude dialog", field is not None)
    if field is not None:
        ui.type_into(field, "20")


def extrude_ok():
    h.task_button("OK")


def bracket():
    h.check("L bracket", st.near(h.solid_volume(), L), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz_2():
    h.click(V(20, 0, 20))


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(5, 25), (25, 5)])
        s["line"] = sk


def finish_line():
    h.ribbon("Finish Sketch")


def rib_start():
    h.fit()
    h.click_empty()
    st.menu("Rib")


def dialog_open():
    p = panel()
    h.check("Rib dialog open", p is not None and p.kind == "rib")
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check(
        "Fusion's fields",
        [p.side.itemText(i) for i in range(p.side.count())] == ["Symmetric", "One Side"]
        and [p.depth_type.itemText(i) for i in range(p.depth_type.count())] == ["To Next", "Depth"]
        and p.flip.isVisible()
        and p.thickness.widget.isVisible(),
    )
    h.check("no Extend Curves for a rib", not p.extend.isVisible())
    h.check("no Depth box for To Next", not p.depth.widget.isVisible())
    h.fit()
    h.check("clicked the line", h.click_edge(V(15, 0, 15)))


def gusset():
    p = panel()
    h.check("line picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("SciForge's Rib", p.target is not None and p.target.SciForgeType == "Rib")
    h.check("gusset: triangle x 2", st.near(h.solid_volume(), L + TRI * 2), h.solid_volume())
    h.check("thickness arrow shown", "thickness" in p.arrows, list(p.arrows))
    h.check("no message", p.message.text() == "", p.message.text())
    h.fit()
    h.shot("1-gusset")
    ui.type_into(p.thickness.widget, "4")


def thick4():
    p = panel()
    h.check("thickness 4", st.near(h.solid_volume(), L + TRI * 4), h.solid_volume())
    bb = st.bbox(h.body().Shape)
    h.check("symmetric: 2 out of the bracket's face", st.near(bb[4], 2.0), bb)
    h.check("choose One Side", ui.choose(p.side, "One Side"))


def one_side():
    p = panel()
    h.check("Flip Side shown", p.flip_side.isVisible())
    h.check("one side: same volume", st.near(h.solid_volume(), L + TRI * 4), h.solid_volume())
    bb = st.bbox(h.body().Shape)
    h.check("one side goes into the bracket's side", st.near(bb[4], 0.0), bb)
    hole_steps.click_checkbox(p.flip_side)


def flipped_side():
    p = panel()
    h.check("dialog stays open", p is not None)
    if p is None:
        return
    h.check(
        "Flip Side out of the face: only an edge would touch, the dialog says why",
        "separate piece" in p.message.text(),
        p.message.text(),
    )
    h.check("the last good rib stays", st.near(h.solid_volume(), L + TRI * 4), h.solid_volume())
    hole_steps.click_checkbox(p.flip_side)


def unflipped_side():
    p = panel()
    h.check("message gone", p.message.text() == "", p.message.text())
    bb = st.bbox(h.body().Shape)
    h.check("back into the bracket's side", st.near(bb[4], 0.0), bb)
    h.check("choose Symmetric", ui.choose(p.side, "Symmetric"))


def symmetric_again():
    ui.type_into(panel().thickness.widget, "2")


def thin_again():
    p = panel()
    h.check("back to 2", st.near(h.solid_volume(), L + TRI * 2), h.solid_volume())
    h.check("choose Depth", ui.choose(p.depth_type, "Depth"))


def depth_box():
    p = panel()
    h.check("Depth box shown", p.depth.widget.isVisible())
    ui.type_into(p.depth.widget, "5")


def depth5():
    p = panel()
    h.check(
        "a strip 5 deep",
        st.near(h.solid_volume(), depth_volume(5.0)),
        (h.solid_volume(), depth_volume(5.0)),
    )
    h.check("depth arrow shown", "depth" in p.arrows, list(p.arrows))
    h.shot("2-depth")


def drag_depth():
    p = panel()
    arrow = p.arrows.get("depth")
    if arrow is None:
        h.check("depth arrow", False)
        return
    mid, grow, across, size = p._frame()
    origin = mid + across * (1.0 + 0.4 * size)
    s["depth_before"] = p.depth.value()
    hole_steps.drag_arrow(origin, grow, arrow.distance(), 3.0)


drag_depth.wait_ms = 1500


def dragged():
    p = panel()
    d = p.depth.value()
    h.check("dragging the arrow made it deeper", d > s.get("depth_before", 5.0) + 0.5, d)
    h.check(
        "volume follows the depth",
        st.near(h.solid_volume(), depth_volume(d), 1e-5),
        (h.solid_volume(), depth_volume(d), d),
    )
    h.check("choose To Next", ui.choose(p.depth_type, "To Next"))


def to_next_ok():
    h.check("gusset again", st.near(h.solid_volume(), L + TRI * 2), h.solid_volume())
    h.task_button("OK")


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), L + TRI * 2), h.solid_volume())
    h.check("Rib 1 in the timeline", "Rib 1" in st.timeline_titles(), st.timeline_titles())
    h.check("the line sketch is hidden", not s["line"].ViewObject.Visibility)


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the rib (one step)", st.near(h.solid_volume(), L), h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings it back", st.near(h.solid_volume(), L + TRI * 2), h.solid_volume())


def edit():
    h.check("double-click Rib 1", st.edit_in_timeline("Rib 1"))


def editing():
    p = panel()
    h.check("editing the rib", p is not None and p.editing and p.kind == "rib")
    if p is None:
        return
    h.check("edit shows the line", len(p.refs) == 1, p.refs)
    h.check("edit shows thickness 2", st.near(p.thickness.value(), 2.0), p.thickness.value())
    ui.type_into(p.thickness.widget, "3")


def edit_ok():
    h.check("thickness 3", st.near(h.solid_volume(), L + TRI * 3), h.solid_volume())
    h.task_button("OK")


def edited():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), L + TRI * 3), h.solid_volume())
    s["volume"] = h.solid_volume()


def edit_flip():
    h.check("double-click Rib 1", st.edit_in_timeline("Rib 1"))


def flip_direction():
    p = panel()
    h.check("editing", p is not None and p.editing)
    if p is not None:
        hole_steps.click_checkbox(p.flip)


def flip_refused():
    p = panel()
    h.check("dialog stays open", p is not None)
    if p is None:
        return
    h.check("the dialog says why", "does not reach" in p.message.text(), p.message.text())
    h.check("the rib stays as it was", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.task_button("Cancel")


def flip_cancelled():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("Cancel keeps the rib", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    st.menu("Rib")


def esc_now():
    h.check("dialog open", panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc changes nothing", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("one rib", len(st.features("rib")) == 1, st.features("rib"))


h.run(
    "sweep_loft_rib",
    [
        new_design,
        pick_xz,
        draw_l,
        finish_l,
        extrude,
        extrude_distance,
        extrude_ok,
        bracket,
        pick_xz_2,
        draw_line,
        finish_line,
        rib_start,
        dialog_open,
        gusset,
        thick4,
        one_side,
        flipped_side,
        unflipped_side,
        symmetric_again,
        thin_again,
        depth_box,
        depth5,
        drag_depth,
        dragged,
        to_next_ok,
        kept,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        edit_ok,
        edited,
        edit_flip,
        flip_direction,
        flip_refused,
        flip_cancelled,
        esc_now,
        after_esc,
    ],
)
