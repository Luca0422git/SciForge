# SPDX-License-Identifier: LGPL-2.1-or-later
"""SOLID > Loft, part 2: Tangent Edges Merge, a rail that is an edge of another body, end
conditions with a rail and with a centerline, Closed, only real input.

Create Sketch on XY: a slot (lines y = +-5 from x -10 to 10, half circles r 5 at x +-10).
Offset Plane 30 above XY; its row selected in the browser, Create Sketch: the same slot on
it (the plane hidden with its eye).
Create Sketch on XY: a triangle (15, 0), (25, 5), (25, -5); Extrude it 30 as a New Body (a
prism whose upright edge at (15, 0) touches both slots). Create Sketch on XZ: the line (0, -5)
- (0, 35) (a centerline running on past both slots).
Path M1 (Merge): CREATE > Loft, click inside both slots: one side face per profile curve
        (Keep: 6 faces, 8356.19 mm^3). Tangent Edges Merge: the lines and arcs, joined
        smoothly, loft into one side face (3 faces). OK: "Loft 1".
Path M2 (undo / redo).
Path M3 (edit: a rail on another body, Direction ends): double-click Loft 1, Merge off;
        click the Rails box, then the prism's upright edge at (15, 0): it is taken (an edge
        of another body); the loft follows it (the same straight slot); First and Last
        Profile Direction (square off the profiles): still the straight slot (8356.19,
        OpenCASCADE measures spline sides to about 0.2 %); Takeoff Weight typed as the
        user parameter w (1.5): an expression on the loft, the same slot. OK.
Path M4 (a centerline with a Direction end): edit again, Guide Type Centerline, click the
        Centerline box, then the line where it runs above the slots: the profiles held square
        to it, the loft ends at the profiles, Direction at both ends: the straight slot again.
        Takeoff Weight typed as 2: the formula goes, the loft takes 2. OK.
Path M5 (Closed, Esc): edit again, Closed: the Last Profile row goes (the loop has no last
        end) and the dialog says a closed loft needs three profiles; Esc: unchanged."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sweep_loft_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
SLOT = (20 * 10 + 3.141592653589793 * 25) * 30
s = {}


def panel():
    return st.panel("loft")


def loft_body():
    from sciforge import loft

    feature = s.get("loft")
    return loft.owner_body(feature) if feature is not None else None


def loft_shape():
    body = loft_body()
    return body.Shape if body is not None else None


def faces():
    shape = loft_shape()
    return len(shape.Faces) if shape is not None else 0


def vol():
    shape = loft_shape()
    try:
        return shape.Volume if shape is not None and shape.Solids else 0.0
    except Exception:
        return 0.0


def wait_loft():
    """The open dialog's loft (its feature)."""
    from SciForgeTests.gui import surface_steps as ss

    p = panel()
    ss.settle()
    if p is not None and p.target is not None:
        s["loft"] = p.target
    return p


# -- the slots, the prism, the line --------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface2SolidLoft")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_slot1():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        bs.draw_slot(sk, -10, 0, 10, 0, 10)
        s["slot1"] = sk


def finish():
    h.ribbon("Finish Sketch")


def offset_plane():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    h.ribbon("Offset Plane")


def pick_xy_plane():
    h.click(V(12, -8, 0))


def plane_distance():
    from sciforge import construct_ui

    p = construct_ui.ConstructPanel.last
    if h.check("offset plane dialog", p is not None and p.field is not None):
        ui.type_into(p.field.widget, "30")


def plane_ok():
    h.task_button("OK")


def plane_made():
    planes = [o for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Plane"]
    h.check("a plane at z 30", len(planes) == 1 and st.near(planes[0].Placement.Base.z, 30.0))
    if planes:
        s["plane"] = planes[0]
    h.fit()
    h.click_empty()
    h.check("the plane's row clicked (selected)", tl.click_row(s["plane"].Label))


def pick_plane():
    h.ribbon("Create Sketch")  # on the selected plane


def draw_slot2():
    sk = h.in_sketch()
    h.check(
        "sketch open on the plane", sk is not None and sk.AttachmentSupport[0][0] is s.get("plane")
    )
    if sk:
        bs.draw_slot(sk, -10, 0, 10, 0, 10)
        s["slot2"] = sk


def hide_plane():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("plane eye clicked", tl.click_eye(s["plane"].Label))


def triangle_sketch():
    h.check("the plane is hidden", not s["plane"].ViewObject.Visibility)
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def draw_triangle():
    sk = h.in_sketch()
    h.check("triangle sketch open", sk is not None)
    if sk:
        st.add_lines(sk, [(15, 0), (25, 5), (25, -5)], closed=True)


def extrude_prism():
    h.check("left the triangle sketch", h.in_sketch() is None)
    h.fit()
    h.press("e")


def prism_values():
    from sciforge import taskui

    p = taskui.current()
    if not h.check("Extrude dialog", p is not None and hasattr(p, "operation")):
        return
    ui.type_into(p.distance.widget, "30")


def prism_new_body():
    from sciforge import taskui

    p = taskui.current()
    h.check("Operation New Body", ui.choose(p.operation, "New Body"))


def prism_ok():
    h.task_button("OK")


def prism_made():
    solids = [
        b for b in App.ActiveDocument.Objects if b.TypeId == "PartDesign::Body" and b.Shape.Solids
    ]
    h.check("a prism body", len(solids) == 1, [b.Label for b in solids])
    if solids:
        s["prism"] = solids[0]
        h.check("the prism is 50 x 30 = 1500", st.near(solids[0].Shape.Volume, 1500.0))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the XZ square shows


def draw_line():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(0, -5), (0, 35)])


def after_sketches():
    h.check("left the line sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()


# -- M1: Merge ---------------------------------------------------------------------------------
def m1_loft():
    st.menu("Loft")


def m1_slot1():
    p = panel()
    h.check("Loft dialog open", p is not None)
    h.check(
        "Tangent Edges Merge can be ticked, off",
        p is not None and p.merge.isEnabled() and not p.merge.isChecked(),
    )
    h.fit()
    h.click(V(-5, 2, 0))


def m1_slot2():
    p = panel()
    h.check("slot 1 is profile 1", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.click(V(-5, 2, 30))


def m1_keep():
    p = wait_loft()
    h.check("two profiles", p is not None and len(p.profiles) == 2, p and p.profiles)
    h.check("Keep: 6 faces", faces() == 6, faces())
    h.check("the straight slot", st.near(vol(), SLOT, 1e-6), vol())
    if p is not None:
        from SciForgeTests.gui import hole_steps

        hole_steps.click_checkbox(p.merge)


def m1_merged():
    wait_loft()
    h.check("Merge: one smooth side face + 2 caps", faces() == 3, faces())
    shape = loft_shape()
    h.check("a valid solid", shape is not None and shape.isValid() and len(shape.Solids) == 1)
    h.shot("1-merged")
    h.task_button("OK")


def m1_done():
    h.check("dialog closed", not Gui.Control.activeDialog())
    titles = tl.titles()
    h.check("Loft 1 in the timeline", "Loft 1" in titles, titles)
    h.check("still merged", faces() == 3, faces())


# -- M2: undo / redo -------------------------------------------------------------------------------
def m2_undo():
    tl.undo()


def m2_undone():
    h.check("undo takes the loft away", faces() == 0 or loft_body() is None, faces())


def m2_redo():
    tl.redo()


def m2_redone():
    from sciforge import loft

    found = [o for o in App.ActiveDocument.Objects if loft.is_loft(o)]
    h.check("redo brings it back", len(found) == 1, found)
    if found:
        s["loft"] = found[0]
    h.check("merged again", faces() == 3, faces())


# -- M3: a rail on another body, Direction ends ----------------------------------------------------
def m3_edit():
    h.check("double-clicked Loft 1", tl.double_click("Loft 1"))


def m3_merge_off():
    p = panel()
    h.check("edit dialog open", p is not None)
    if p is None:
        return
    h.check("Merge read back", p.merge.isChecked())
    from SciForgeTests.gui import hole_steps

    hole_steps.click_checkbox(p.merge)


def m3_rails_box():
    wait_loft()
    h.check("Keep again: 6 faces", faces() == 6, faces())
    p = panel()
    ui.click(p.fields["rails"].button)


def m3_click_edge():
    p = panel()
    h.check("the Rails box takes the clicks", p is not None and p.active == "rails", p and p.active)
    h.fit()
    h.check("clicked the prism's upright edge", h.click_edge(V(15, 0, 20)))


def m3_rail_taken():
    from sciforge import loft

    p = wait_loft()
    rails = list(p.rails) if p is not None else []
    h.check(
        "an edge of the other body is the rail",
        len(rails) == 1 and loft.owner_body(rails[0][0]) is s.get("prism"),
        rails,
    )
    h.check("no problem", not p.message.text(), p.message.text())
    h.check("the loft follows it: the straight slot", st.near(vol(), SLOT, 1e-4), vol())
    ui.choose(p.ends["start"]["combo"], "Direction")


def m3_last_direction():
    p = wait_loft()
    h.check("Direction with a rail is offered", p.ends["start"]["combo"].isEnabled())
    ui.choose(p.ends["end"]["combo"], "Direction")


def m3_ends():
    p = wait_loft()
    h.check("no problem with ends and a rail", not p.message.text(), p.message.text())
    h.check("Takeoff Angle shown", p.ends["start"]["angle"].widget.isVisible())
    h.check(
        "square off both slots along the rail: the straight slot",
        st.near(vol(), SLOT, 5e-3),
        vol(),
    )
    h.shot("2-rail-ends")
    from sciforge import parameters

    # Change Parameters (its own dialog) made this user parameter (a plain number)
    parameters.add_user(App.ActiveDocument, "w", "", "1.5")
    ui.type_into(p.ends["start"]["weight"].widget, "w")


def _weight_state(p):
    from sciforge.compat import QtWidgets

    field = p.ends["start"]["weight"]
    edit = field.widget.findChild(QtWidgets.QLineEdit)
    return (
        p.formulas,
        edit.text() if edit is not None else None,
        p.formula_inputs["start_weight"].raw,
        field.widget.isVisible(),
        p.message.text(),
    )


def m3_formula():
    p = wait_loft()
    engine = dict(s["loft"].ExpressionEngine) if s.get("loft") is not None else {}
    h.check("the weight takes a formula", "StartWeight" in engine, (engine, _weight_state(p)))
    h.check(
        "it evaluates to 1.5",
        p is not None and st.near(p.ends["start"]["weight"].value(), 1.5),
        p and p.ends["start"]["weight"].value(),
    )
    h.check("the same slot", st.near(vol(), SLOT, 5e-3), vol())
    h.task_button("OK")


def m3_done():
    h.check("dialog closed", not Gui.Control.activeDialog())
    engine = dict(s["loft"].ExpressionEngine)
    h.check("the formula is kept", "StartWeight" in engine, engine)
    h.check("the loft follows it", st.near(s["loft"].StartWeight, 1.5), s["loft"].StartWeight)
    h.check("kept", st.near(vol(), SLOT, 5e-3), vol())


# -- M4: a centerline with Direction ends ----------------------------------------------------------
def m4_edit():
    h.check("double-clicked Loft 1 again", tl.double_click("Loft 1"))


def m4_centerline():
    p = panel()
    h.check("edit dialog open", p is not None)
    if p is None:
        return
    h.check("Direction read back", p.options["start_condition"] == "direction", p.options)
    h.check("the rail read back", len(p.rails) == 1, p.rails)
    h.check(
        "the weight's formula read back",
        p.formulas.get("start_weight") == "w",
        (p.formulas, dict(p.target.ExpressionEngine)),
    )
    ui.choose(p.guide, "Centerline")


def m4_centerline_box():
    p = panel()
    h.check(
        "the Centerline box is shown", p is not None and p.fields["centerline"].widget.isVisible()
    )
    ui.click(p.fields["centerline"].button)


def m4_click_line():
    p = panel()
    h.check(
        "the Centerline box takes the clicks",
        p is not None and p.active == "centerline",
        p and p.active,
    )
    h.fit()
    h.check("clicked the line", h.click_edge(V(0, 0, 33)))


def m4_follows():
    p = wait_loft()
    h.check(
        "the line is the centerline", p is not None and len(p.centerline) == 1, p and p.centerline
    )
    h.check("no problem with ends and a centerline", not p.message.text(), p.message.text())
    h.check("the straight slot along it", st.near(vol(), SLOT, 5e-3), vol())
    ui.type_into(p.ends["start"]["weight"].widget, "2")


def m4_number():
    wait_loft()
    engine = dict(s["loft"].ExpressionEngine)
    h.check("a number typed over the formula drops it", "StartWeight" not in engine, engine)
    h.check("the loft takes the number", st.near(s["loft"].StartWeight, 2.0), s["loft"].StartWeight)
    h.check("still the straight slot", st.near(vol(), SLOT, 5e-3), vol())
    h.task_button("OK")


def m4_done():
    h.check("dialog closed", not Gui.Control.activeDialog())


# -- M5: Closed, Esc ---------------------------------------------------------------------------
def m5_edit():
    h.check("double-clicked Loft 1 once more", tl.double_click("Loft 1"))


def m5_closed():
    p = panel()
    h.check("edit dialog open", p is not None)
    if p is None:
        return
    from SciForgeTests.gui import hole_steps

    hole_steps.click_checkbox(p.closed)


def m5_refused():
    p = wait_loft()
    h.check("the Last Profile row goes", p is not None and not p.ends["end"]["combo"].isVisible())
    h.check("the First Profile row stays", p is not None and p.ends["start"]["combo"].isVisible())
    text = p.message.text() if p else ""
    h.check("the dialog says why", "three" in text or "centerline" in text, text)
    h.press(QtCore_key_escape())


def QtCore_key_escape():
    from PySide import QtCore

    return QtCore.Qt.Key_Escape


def m5_done():
    h.check("Esc closed the dialog", not Gui.Control.activeDialog())
    h.check("unchanged", st.near(vol(), SLOT, 5e-3), vol())


h.run(
    "surface2_solid_loft",
    [
        new_design,
        pick_xy,
        draw_slot1,
        finish,
        offset_plane,
        pick_xy_plane,
        plane_distance,
        plane_ok,
        plane_made,
        pick_plane,
        draw_slot2,
        finish,
        hide_plane,
        triangle_sketch,
        pick_xy,
        draw_triangle,
        finish,
        extrude_prism,
        prism_values,
        prism_new_body,
        prism_ok,
        prism_made,
        pick_xz,
        draw_line,
        finish,
        after_sketches,
        m1_loft,
        m1_slot1,
        m1_slot2,
        m1_keep,
        m1_merged,
        m1_done,
        m2_undo,
        m2_undone,
        m2_redo,
        m2_redone,
        m3_edit,
        m3_merge_off,
        m3_rails_box,
        m3_click_edge,
        m3_rail_taken,
        m3_last_direction,
        m3_ends,
        m3_formula,
        m3_done,
        m4_edit,
        m4_centerline,
        m4_centerline_box,
        m4_click_line,
        m4_follows,
        m4_number,
        m4_done,
        m5_edit,
        m5_closed,
        m5_refused,
        m5_done,
    ],
)
