# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Extrude like a Fusion user, only real input.

Create Sketch on XY: one open line from (0, 0) to (30, 0), Finish Sketch. SURFACE tab,
CREATE > Extrude with nothing selected: the dialog waits with the Profiles box lit and
nothing is built. Click the line: it is the profile (1 curve), the arrow shows at 0 and
OK waits ("Drag the arrow or type a distance"). Type 15: a 30 x 15 surface (area 450) in a
body of its own, a surface body (faces, no solid) with the surface icon in the browser,
the sketch body untouched. Drag the arrow out to about 25; type 20 in its value box. OK:
"Extrude 1" in the timeline, the sketch hidden. Undo / Redo. Double-click "Extrude 1",
Direction Symmetric (Half Length): area doubles to 1200; OK. Edit again, Taper Angle 10:
the band tilts (area 30 * 20 / cos 10 on each side); Esc: unchanged. Create Sketch +
Extrude with the SOLID tab afterwards goes into a new solid body, never into the surface.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfaceExtrude")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane")
    if sk:
        st.add_lines(sk, [(0, 0), (30, 0)])
        s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def surface_tab():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    st.tab("SURFACE")


def extrude_nothing_selected():
    h.check("nothing selected", not Gui.Selection.getSelectionEx())
    st.menu("CREATE", "Extrude")


def dialog_waits():
    p = st.panel()
    h.check("surface Extrude dialog open", p is not None and p.kind == "extrude")
    if p is None:
        return
    h.check("no pop-up", not h.popups(), h.popups())
    h.check("the Profiles box takes the clicks", p.active == "profile", p.active)
    h.check("nothing built yet", p.step is None and len(st.bodies()) == 1, st.bodies())
    h.check(
        "Fusion's choices",
        [p.rows["direction"][0].itemText(i) for i in range(3)]
        == ["One Side", "Two Sides", "Symmetric"]
        and [p.rows["extent"][0].itemText(i) for i in range(2)] == ["Distance", "To Object"]
        and [p.rows["operation"][0].itemText(i) for i in range(2)]
        == ["New Body", "New Component"],
    )
    h.check("Chain Selection on", p.rows["chain"][0].isChecked())
    h.shot("1-waiting")


def click_line():
    h.fit()
    h.check("clicked the line", h.click_edge(V(20, 0, 0)))


def profile_taken():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the line is the profile", len(p.picks["profile"]) == 1, p.picks["profile"])
    h.check("distance 0: nothing built", p.step is None, p.step)
    h.check("the arrow is there to drag", st.handle("distance") is not None, list(p.handles))
    h.check("OK waits for a distance", "distance" in st.message().lower(), st.message())


def ok_at_zero():
    st.ok()


def still_open():
    h.check("OK at 0 keeps the dialog open", st.panel() is not None)


def type_15():
    st.type_field("distance", "15")


def surface_15():
    st.settle()
    p = st.panel()
    body = st.step_body(p)
    h.check("a surface 30 x 15", body is not None and st.near(st.area(body), 450.0), st.area(body))
    h.check("no solid in it", body is not None and not body.Shape.Solids)
    from sciforge import surface, bodies

    s["sketch_body"] = bodies.body_of(s["sketch"])
    h.check("a body of its own", body is not None and body is not s["sketch_body"])
    h.check("it is a surface body", surface.is_surface_body(body))
    h.check("the sketch body is no surface body", not surface.is_surface_body(s["sketch_body"]))
    s["body"] = body
    h.shot("2-surface")


def drag_out():
    s["drag"] = st.drag_arrow("distance", 25.0)


drag_out.wait_ms = 2200


def dragged():
    st.settle()
    d = s.get("drag")
    h.check("the drag finished", d is not None and d.done, getattr(d, "error", None))
    value = st.panel().options["distance"] if st.panel() else 0
    h.check("the drag set the distance (about 25)", 18.0 < value < 32.0, value)
    h.check(
        "the surface followed the arrow",
        st.near(st.area(s["body"]), 30.0 * value, 1e-4),
        (st.area(s["body"]), value),
    )


def type_in_value_box():
    h.fit()  # the arrow went up past the top of the view: zoom out to see its box
    st.wait(300)
    box = ai.value_box("distance")
    h.check("a value box beside the arrow", box is not None)
    if box is not None:
        h.check("the value box is shown", box.isVisible())
        ai.type_in_box(box, "20", enter=False)
        h.check("the box has the keyboard", box.hasFocus(), ai.focus_name())
        h.check("20 typed in it", box.text() == "20", box.text())
        # a click elsewhere (here: the dialog's Distance field) keeps what was typed
        from SciForgeTests.gui import dialog_input as ui

        ui.click(st.panel().number_fields["distance"].widget)


def twenty():
    st.settle()
    h.check("value box 20 taken", st.near(st.area(s["body"]), 600.0), st.area(s["body"]))


def press_ok():
    st.ok()


def after_ok():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extrude 1 in the timeline", "Extrude 1" in titles, titles)
    h.check("the sketch is hidden", not s["sketch"].ViewObject.Visibility)
    icon = st.browser_icon_of(s["body"])
    h.check("browser: the surface icon", icon == "surface_body", icon)
    h.check("still 600", st.near(st.area(s["body"]), 600.0), st.area(s["body"]))
    h.shot("3-done")


def undo():
    st.undo()


def undone():
    h.check("undo takes the surface away", len(st.bodies()) == 1, st.bodies())


def redo():
    st.redo()


def redone():
    from sciforge import surface

    found = st.surface_bodies()
    h.check("redo brings it back", len(found) == 1 and st.near(st.area(found[0]), 600.0), found)
    if found:
        s["body"] = found[0]
    h.check("surface still a surface body", found and surface.is_surface_body(found[0]))


def edit_from_timeline():
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


def edit_open():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("the profile is shown picked", len(p.picks["profile"]) == 1, p.picks)
    h.check("distance read back", st.near(p.options["distance"], 20.0), p.options["distance"])


def symmetric():
    st.choose("direction", "Symmetric")


def symmetric_ok():
    st.settle()
    h.check("symmetric: 20 each way", st.near(st.area(s["body"]), 1200.0), st.area(s["body"]))
    st.ok()


def symmetric_done():
    h.check("dialog closed", st.panel() is None)
    b = s["body"].Shape.BoundBox
    h.check("from -20 to 20", st.near(b.ZMin, -20.0) and st.near(b.ZMax, 20.0), b)


def edit_again():
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


def taper():
    st.type_field("taper", "10")


def tapered():
    st.settle()
    expect = 2 * 30.0 * 20.0 / math.cos(math.radians(10))
    h.check("taper tilts the band", st.near(st.area(s["body"]), expect, 1e-5), st.area(s["body"]))


def escape():
    st.esc()


def escaped():
    h.check("Esc closed the dialog", st.panel() is None)
    h.check("unchanged after Esc", st.near(st.area(s["body"]), 1200.0), st.area(s["body"]))


def solid_tab_sketch():
    st.tab("SOLID")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy_again():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_square():
    sk = h.in_sketch()
    h.check("second sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 40, 0, 50, 10)
        s["sketch2"] = sk
        from sciforge import bodies, surface

        body = bodies.body_of(sk)
        h.check("the new sketch is not in the surface body", body is not s["body"])
        h.check("its body is no surface body", not surface.is_surface_body(body))


def finish_square():
    h.ribbon("Finish Sketch")


def solid_extrude():
    h.press("e")


def solid_distance():
    ai.give_distance("5")


def solid_ok():
    st.ok()


def solid_done():
    from sciforge import surface

    h.check("the surface is untouched", st.near(st.area(s["body"]), 1200.0), st.area(s["body"]))
    h.check("still a surface body", surface.is_surface_body(s["body"]))
    solids = [b for b in st.bodies() if b.Shape.Solids]
    h.check("a solid body of 500", len(solids) == 1 and st.near(st.volume(solids[0]), 500.0),
            [st.volume(b) for b in solids])


h.run(
    "surface_extrude",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_line,
        finish_sketch,
        surface_tab,
        extrude_nothing_selected,
        dialog_waits,
        click_line,
        profile_taken,
        ok_at_zero,
        still_open,
        type_15,
        surface_15,
        drag_out,
        dragged,
        type_in_value_box,
        twenty,
        press_ok,
        after_ok,
        undo,
        undone,
        redo,
        redone,
        edit_from_timeline,
        edit_open,
        symmetric,
        symmetric_ok,
        symmetric_done,
        edit_again,
        taper,
        tapered,
        escape,
        escaped,
        solid_tab_sketch,
        pick_xy_again,
        draw_square,
        finish_square,
        solid_extrude,
        solid_distance,
        solid_ok,
        solid_done,
    ],
)
