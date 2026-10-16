# SPDX-License-Identifier: LGPL-2.1-or-later
"""Web like a Fusion user, only real input.

A tray: a 40 x 40 square on XY, Extrude 10; a sketch on its top with a 36 x 36 square,
Extrude -8 (Cut by itself): walls 2 thick, floor 2 thick. A sketch on the rim with a cross of
two lines, 20 long, short of the walls. CREATE > Web: click both lines: the cross grows down
to the floor and, with Extend Curves, out to the walls. Extend Curves off: only the 20 long
cross. On again. Depth 4. Flip Direction: the web would grow up into the air, away from the
part: the dialog says so. Back; To Next; OK. Undo / redo. Edit from the timeline: thickness
3, OK. Second use: a line at y 10 on the rim, clicked before CREATE > Web: it is taken and
becomes a plate across the cavity, OK. Esc cancels a third Web (nothing selected).

Hand-derived: tray 40*40*10 - 36*36*8 = 5632. A web plate L long, t thick, h high adds
L t h; the two plates of the cross share a t x t x h post: extended (L = 36, the cavity) and
To Next (h = 8, down to the floor): 2 * 36 * 2 * 8 - 2 * 2 * 8 = 1120; not extended (L = 20):
608; Depth 4: 2 * 36 * 2 * 4 - 2 * 2 * 4 = 560; thickness 3: 2 * 36 * 3 * 8 - 3 * 3 * 8. The
second plate, 36 * 2 * 8, crosses the 3 thick one: less 3 * 2 * 8.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import hole_steps
from SciForgeTests.gui import sweep_loft_steps as st

V = App.Vector
TRAY = 40.0 * 40.0 * 10.0 - 36.0 * 36.0 * 8.0
SECOND = 36.0 * 2.0 * 8.0 - 3.0 * 2.0 * 8.0


def cross(length, t, height):
    return 2 * length * t * height - t * t * height


s = {}


def panel():
    return st.panel("web")


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Web")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw_base():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, -20, -20, 20, 20)


def finish_base():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def _extrude_field():
    from sciforge import taskui

    p = taskui.current()
    return getattr(getattr(p, "distance", None), "widget", None)


def extrude_distance():
    field = _extrude_field()
    h.check("extrude dialog", field is not None)
    if field is not None:
        ui.type_into(field, "10")


def extrude_ok():
    h.task_button("OK")


def top_sketch():
    h.check("block", st.near(h.solid_volume(), 16000.0), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def pick_top():
    h.click(V(10, -10, 10))


def draw_pocket():
    sk = h.in_sketch()
    h.check("sketch on the top", sk is not None)
    if sk:
        x0, y0 = h.to_sketch(sk, V(-18, -18, 10))
        x1, y1 = h.to_sketch(sk, V(18, 18, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def finish_pocket():
    h.ribbon("Finish Sketch")


def cut():
    h.fit()
    h.press("e")


def cut_distance():
    field = _extrude_field()
    if field is not None:
        ui.type_into(field, "-8")


def cut_ok():
    h.task_button("OK")


def tray():
    h.check("tray", st.near(h.solid_volume(), TRAY), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def pick_rim():
    h.click(V(19, -10, 10))


def draw_cross():
    sk = h.in_sketch()
    h.check("sketch on the rim", sk is not None)
    if sk:
        a = h.to_sketch(sk, V(-10, 0, 10))
        b = h.to_sketch(sk, V(10, 0, 10))
        c = h.to_sketch(sk, V(0, -10, 10))
        d = h.to_sketch(sk, V(0, 10, 10))
        st.add_lines(sk, [a, b])
        st.add_lines(sk, [c, d])
        s["cross"] = sk


def finish_cross():
    h.ribbon("Finish Sketch")


def web_start():
    h.fit()
    h.click_empty()
    st.menu("Web")


def click_first():
    p = panel()
    h.check("Web dialog open", p is not None and p.kind == "web")
    if p is None:
        return
    h.check("Extend Curves shown and on", p.extend.isVisible() and p.extend.isChecked())
    h.fit()
    h.check("clicked line 1", h.click_edge(V(6, 0, 10)))


def click_second():
    p = panel()
    h.check("one line", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("clicked line 2", h.click_edge(V(0, -6, 10)))


def webbed():
    p = panel()
    h.check("two lines", p is not None and len(p.refs) == 2, p and p.refs)
    want = TRAY + cross(36, 2, 8)
    h.check(
        "cross down to the floor, out to the walls",
        st.near(h.solid_volume(), want),
        (h.solid_volume(), want),
    )
    h.check("SciForge's Web", p.target is not None and p.target.SciForgeType == "Web")
    h.fit()
    h.shot("1-web")
    hole_steps.click_checkbox(p.extend)


def not_extended():
    want = TRAY + cross(20, 2, 8)
    h.check(
        "Extend Curves off: the 20 long cross",
        st.near(h.solid_volume(), want),
        (h.solid_volume(), want),
    )
    hole_steps.click_checkbox(panel().extend)


def extended_again():
    h.check("extended again", st.near(h.solid_volume(), TRAY + cross(36, 2, 8)), h.solid_volume())
    h.check("choose Depth", ui.choose(panel().depth_type, "Depth"))


def depth_box():
    ui.type_into(panel().depth.widget, "4")


def depth4():
    p = panel()
    h.check("depth 4", st.near(h.solid_volume(), TRAY + cross(36, 2, 4)), h.solid_volume())
    h.check("depth arrow shown", "depth" in p.arrows, list(p.arrows))
    hole_steps.click_checkbox(p.flip)


def flipped():
    p = panel()
    h.check("dialog stays open", p is not None)
    if p is None:
        return
    h.check("the dialog says why", "does not touch" in p.message.text(), p.message.text())
    h.check(
        "the last good web stays",
        st.near(h.solid_volume(), TRAY + cross(36, 2, 4)),
        h.solid_volume(),
    )
    hole_steps.click_checkbox(p.flip)


def unflipped():
    p = panel()
    h.check("message gone", p.message.text() == "", p.message.text())
    h.check("choose To Next", ui.choose(p.depth_type, "To Next"))


def web_ok():
    h.check(
        "to the floor again", st.near(h.solid_volume(), TRAY + cross(36, 2, 8)), h.solid_volume()
    )
    h.task_button("OK")


def kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), TRAY + cross(36, 2, 8)), h.solid_volume())
    h.check("Web 1 in the timeline", "Web 1" in st.timeline_titles(), st.timeline_titles())
    h.check("the cross sketch is hidden", not s["cross"].ViewObject.Visibility)


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the web", st.near(h.solid_volume(), TRAY), h.solid_volume())


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check(
        "Redo brings it back", st.near(h.solid_volume(), TRAY + cross(36, 2, 8)), h.solid_volume()
    )


def edit():
    h.check("double-click Web 1", st.edit_in_timeline("Web 1"))


def editing():
    p = panel()
    h.check("editing the web", p is not None and p.editing and p.kind == "web")
    if p is None:
        return
    h.check("edit shows both lines", len(p.refs) == 2, p.refs)
    ui.type_into(p.thickness.widget, "3")


def edit_ok():
    h.check("thickness 3", st.near(h.solid_volume(), TRAY + cross(36, 3, 8)), h.solid_volume())
    h.task_button("OK")


def edited():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("kept", st.near(h.solid_volume(), TRAY + cross(36, 3, 8)), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def pick_rim_2():
    h.click(V(19, -10, 10))


def draw_second():
    sk = h.in_sketch()
    h.check("second sketch on the rim", sk is not None)
    if sk:
        st.add_lines(sk, [h.to_sketch(sk, V(-10, 10, 10)), h.to_sketch(sk, V(10, 10, 10))])


def finish_second():
    h.ribbon("Finish Sketch")


def select_second():
    h.fit()
    h.click_empty()
    h.check("clicked the new line before the command", h.click_edge(V(5, 10, 10)))


def web_again():
    st.menu("Web")


def second_web():
    p = panel()
    h.check("second Web dialog", p is not None and not p.editing)
    if p is None:
        return
    h.check("the selected line is taken", len(p.refs) == 1, p.refs)
    want = TRAY + cross(36, 3, 8) + SECOND
    h.check("a plate across the cavity", st.near(h.solid_volume(), want), (h.solid_volume(), want))
    h.task_button("OK")


def second_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("Web 2 in the timeline", "Web 2" in st.timeline_titles(), st.timeline_titles())
    h.check("two webs", len(st.features("web")) == 2, st.features("web"))
    s["volume"] = h.solid_volume()
    h.click_empty()
    st.menu("Web")


def esc_now():
    p = panel()
    h.check("dialog open", p is not None)
    h.check("nothing selected: the Curves box waits", p is not None and not p.refs, p and p.refs)
    h.press(QtCore.Qt.Key_Escape)


def after_esc():
    h.check("Esc closes the dialog", not Gui.Control.activeDialog())
    h.check("Esc changes nothing", st.near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check("still two webs", len(st.features("web")) == 2, st.features("web"))


h.run(
    "sweep_loft_web",
    [
        new_design,
        pick_xy,
        draw_base,
        finish_base,
        extrude,
        extrude_distance,
        extrude_ok,
        top_sketch,
        pick_top,
        draw_pocket,
        finish_pocket,
        cut,
        cut_distance,
        cut_ok,
        tray,
        pick_rim,
        draw_cross,
        finish_cross,
        web_start,
        click_first,
        click_second,
        webbed,
        not_extended,
        extended_again,
        depth_box,
        depth4,
        flipped,
        unflipped,
        web_ok,
        kept,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        edit_ok,
        edited,
        pick_rim_2,
        draw_second,
        finish_second,
        select_second,
        web_again,
        second_web,
        second_kept,
        esc_now,
        after_esc,
    ],
)
