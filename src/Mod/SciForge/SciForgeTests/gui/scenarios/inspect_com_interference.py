# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Center of Mass and Interference with real input.

Part (real input): body 1 is a box 40 x 30 x 10 from the origin; body 2 a 20 x 20 square
sketched on its top face at x = 30 .. 50, y = 20 .. 40 and extruded 5 down as a New Body
(z = 5 .. 10). Hand-derived values:
  body 2: 20 * 20 * 5 = 2000, centre (40, 30, 7.5)
  centre of mass of both (one material): (12000 * (20, 15, 5) + 2000 * (40, 30, 7.5)) / 14000
    = (22.857, 17.143, 5.357); of body 1 alone: (20, 15, 5)
  interference of the two: x 30 .. 40, y 20 .. 30, z 5 .. 10 = 10 * 10 * 5 = 500
Paths: nothing selected (all visible bodies), a body clicked, OK, the Analysis folder,
undo / redo, edited again from the browser, Cancel; a second one with nothing picked follows
the design: body 2 hidden (centre of body 1), shown again, its extrude edited to 10 deep
(body 2 4000, centre (40, 30, 5): both (25, 18.75, 5)), undo; Interference: two bodies
clicked, Compute, Include Coincident Faces, OK, edited again, Esc."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}


def bodies():
    return App.ActiveDocument.findObjects("PartDesign::Body")


def kinds(kind):
    from sciforge import analysis

    return analysis.of_kind(App.ActiveDocument, kind)


# -- body 2 ------------------------------------------------------------------------------------------
def sketch_top():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(10, 10, 10))


def square():
    sk = h.in_sketch()
    h.check("sketch on the top face", sk is not None)
    if sk:
        x0, y0 = h.to_sketch(sk, V(30, 20, 10))
        x1, y1 = h.to_sketch(sk, V(50, 40, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def new_body():
    panel = b.active_panel()
    h.check("Extrude open", panel is not None and hasattr(panel, "operation"))
    if panel is None:
        return
    h.check("New Body chosen", di.choose(panel.operation, "New Body"))


def down_5():
    panel = b.active_panel()
    s.type_into(panel.distance.widget, "-5")


def extrude_ok():
    h.task_button("OK")


def two_bodies():
    found = bodies()
    h.check("two bodies", len(found) == 2, [o.Label for o in found])
    if len(found) == 2:
        st["b1"], st["b2"] = found[0].Name, found[1].Name
        h.check("body 2 is 2000", s.close(found[1].Shape.Volume, 2000.0), found[1].Shape.Volume)
        h.check("body 1 still 12000", s.close(found[0].Shape.Volume, 12000.0))
    h.click_empty()
    h.fit()


# -- Center of Mass ------------------------------------------------------------------------------------
def com_start():
    s.menu("INSPECT", "Center of Mass")


def com_all():
    from sciforge import com_ui

    p = b.active_panel()
    h.check("Center of Mass open", isinstance(p, com_ui.CenterOfMassPanel))
    if not isinstance(p, com_ui.CenterOfMassPanel):
        return
    h.check("all visible bodies", p.box.button.text() == "All visible bodies", p.box.button.text())
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("centre of both", got == ["22.857 mm", "17.143 mm", "5.357 mm"], got)
    h.check("marker shown", p.target is not None and p.target.ViewObject.Visibility)
    h.shot("1-com-all")


def com_click_body1():
    h.click(V(5, 5, 10))


def com_body1():
    p = b.active_panel()
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("body 1 picked: its centre", got == ["20.000 mm", "15.000 mm", "5.000 mm"], got)
    h.check("the box names it", p.box.button.text() == App.ActiveDocument.getObject(st["b1"]).Label)
    sel = s.selection()
    h.check("the whole body lights up", sel == [(st["b1"], [])], sel)
    h.task_button("OK")


def com_kept():
    from sciforge import analysis

    found = kinds(analysis.COM_KIND)
    h.check(
        "Center of Mass1 kept",
        [o.Label for o in found] == ["Center of Mass1"],
        [o.Label for o in found],
    )
    if found:
        st["com"] = found[0].Name
        h.check("at (20, 15, 5)", s.near(found[0].Position, V(20, 15, 5), 1e-9), found[0].Position)
    from SciForgeTests.gui import timeline_input as ti

    h.check("in the Analysis folder", "Analysis" in ti.labels(), ti.labels())
    h.check("not a timeline step", s.timeline_title_of(found[0]) is None if found else False)
    s.undo()


def com_undone():
    from sciforge import analysis

    h.check("Undo removes it", not kinds(analysis.COM_KIND))
    s.redo()


def com_redone():
    from sciforge import analysis

    h.check("Redo brings it back", len(kinds(analysis.COM_KIND)) == 1)
    s.expand_folder("Analysis")


def com_select_row():
    from SciForgeTests.gui import timeline_input as ti

    h.click_empty()
    ti.click_row("Center of Mass1")


def com_edit():
    h.check(
        "selected in the browser",
        [x.ObjectName for x in Gui.Selection.getSelectionEx()] == [st["com"]],
        s.selection(),
    )
    s.menu("INSPECT", "Center of Mass")


def com_edit_dialog():
    from sciforge import com_ui

    p = b.active_panel()
    h.check("it opens to edit", isinstance(p, com_ui.CenterOfMassPanel) and p.editing)
    if not isinstance(p, com_ui.CenterOfMassPanel):
        return
    h.check("with body 1", [o.Name for o in p.picked] == [st["b1"]], [o.Name for o in p.picked])
    h.click(V(45, 35, 10))


def com_edit_both():
    p = b.active_panel()
    got = [p.coords[a].text() for a in "XYZ"]
    h.check("body 2 added: centre of both", got == ["22.857 mm", "17.143 mm", "5.357 mm"], got)
    h.task_button("Cancel")


def com_cancelled():
    obj = App.ActiveDocument.getObject(st["com"])
    h.check("Cancel keeps the old centre", s.near(obj.Position, V(20, 15, 5), 1e-9), obj.Position)
    h.check("still one", len(kinds(obj.SciForgeType)) == 1)


# -- a Center of Mass of all visible bodies follows the design -----------------------------------
BOTH = V(320000.0 / 14000, 240000.0 / 14000, 75000.0 / 14000)


def com2():
    obj = App.ActiveDocument.getObject(st.get("com2", ""))
    return obj


def com_all_start():
    h.click_empty()
    s.menu("INSPECT", "Center of Mass")


def com_all_ok():
    p = b.active_panel()
    text = p.box.button.text() if p is not None and hasattr(p, "box") else None
    h.check("nothing picked: all visible bodies", text == "All visible bodies", text)
    h.task_button("OK")


def com_all_kept():
    from sciforge import analysis

    found = [o for o in kinds(analysis.COM_KIND) if o.Name != st["com"]]
    h.check("Center of Mass2 kept", [o.Label for o in found] == ["Center of Mass2"], found)
    if not found:
        return
    st["com2"] = found[0].Name
    h.check("no bodies stored (all visible)", not found[0].Bodies, found[0].Bodies)
    h.check("at the centre of both", s.near(found[0].Position, BOTH, 1e-9), found[0].Position)
    s.eye(App.ActiveDocument.getObject(st["b2"]).Label)


def com_follows_hidden():
    h.check("body 2 hidden", not App.ActiveDocument.getObject(st["b2"]).ViewObject.Visibility)
    h.check(
        "body 2 hidden: the centre of body 1 alone",
        com2() is not None and s.near(com2().Position, V(20, 15, 5), 1e-9),
        com2() and com2().Position,
    )
    s.eye(App.ActiveDocument.getObject(st["b2"]).Label)


def com_follows_shown():
    h.check(
        "body 2 shown again: the centre of both",
        com2() is not None and s.near(com2().Position, BOTH, 1e-9),
        com2() and com2().Position,
    )
    h.click_empty()
    s.double_click_timeline(App.ActiveDocument.getObject(st["b2"]).Tip)


def com_edit_extrude():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    h.check("body 2's extrude opens to edit", field is not None, p)
    if field is not None:
        s.type_into(field, "-10")


def com_extrude_ok():
    h.task_button("OK")


def com_follows_edit():
    """Body 2 now 20 x 20 x 10 (4000, centre (40, 30, 5)): both (25, 18.75, 5)."""
    v = App.ActiveDocument.getObject(st["b2"]).Shape.Volume
    h.check("body 2 is 4000", s.close(v, 4000.0), v)
    h.check(
        "the all-bodies centre moved: (25, 18.75, 5)",
        com2() is not None and s.near(com2().Position, V(25, 18.75, 5), 1e-9),
        com2() and com2().Position,
    )
    first = App.ActiveDocument.getObject(st["com"])
    h.check("body 1's centre stays", s.near(first.Position, V(20, 15, 5), 1e-9), first.Position)
    bad = [o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State]
    h.check("nothing broken", not bad, bad)
    h.shot("2-com-follows")
    s.undo()


def com_follows_undo():
    v = App.ActiveDocument.getObject(st["b2"]).Shape.Volume
    h.check("Undo: body 2 is 2000 again", s.close(v, 2000.0), v)
    h.check(
        "Undo: the centre of both again",
        com2() is not None and s.near(com2().Position, BOTH, 1e-9),
        com2() and com2().Position,
    )


# -- Interference -----------------------------------------------------------------------------------------
def int_start():
    h.click_empty()
    s.menu("INSPECT", "Interference")


def int_waits():
    from sciforge import interference_ui

    p = b.active_panel()
    h.check("Interference open", isinstance(p, interference_ui.InterferencePanel))
    if isinstance(p, interference_ui.InterferencePanel):
        h.check("asks for bodies", "two or more bodies" in p.message.text(), p.message.text())
    h.click(V(5, 5, 10))


def int_second():
    h.click(V(45, 35, 10))


def int_compute():
    p = b.active_panel()
    h.check("two bodies picked", len(p.picked) == 2, p.picked)
    di.click(p.compute)


def int_result():
    p = b.active_panel()
    rows = p.rows()
    h.check("one interference", len(rows) == 1, rows)
    if rows:
        h.check("500 shared", rows[0][3] == "500.000 mm^3", rows)
    h.check("shown in red", p.target is not None and s.close(p.target.Overlap.Volume, 500.0))
    h.shot("2-interference")
    hs.click_checkbox(p.coincident)


def int_coincident():
    p = b.active_panel()
    h.check("Include Coincident Faces ticked", p.coincident.isChecked())
    di.click(p.compute)


def int_coincident_result():
    p = b.active_panel()
    rows = p.rows()
    h.check("still the one overlap", len(rows) == 1 and rows[0][3] == "500.000 mm^3", rows)
    h.task_button("OK")


def int_kept():
    from sciforge import analysis

    found = kinds(analysis.INTERFERENCE_KIND)
    h.check(
        "Interference1 kept",
        [o.Label for o in found] == ["Interference1"],
        [o.Label for o in found],
    )
    if found:
        st["int"] = found[0].Name
        h.check("its result stored", analysis.results(found[0])[0][2] > 499.99)
    h.check("both bodies unchanged", s.close(sum(o.Shape.Volume for o in bodies()), 14000.0))


def int_select_row():
    from SciForgeTests.gui import timeline_input as ti

    h.click_empty()
    ti.click_row("Interference1")


def int_edit():
    s.menu("INSPECT", "Interference")


def int_edit_dialog():
    from sciforge import interference_ui

    p = b.active_panel()
    h.check(
        "Interference opens to edit", isinstance(p, interference_ui.InterferencePanel) and p.editing
    )
    if isinstance(p, interference_ui.InterferencePanel):
        h.check("with its results", len(p.rows()) == 1, p.rows())
    s.press_escape()


def esc_closed():
    h.check("Esc closes", not Gui.Control.activeDialog())
    from sciforge import analysis

    h.check("still one interference", len(kinds(analysis.INTERFERENCE_KIND)) == 1)
    h.check("no pop-ups", not h.popups(), h.popups())
    h.shot("3-end")


h.run(
    "inspect_com_interference",
    b.box_steps("InspectCOM")
    + [
        sketch_top,
        click_top,
        square,
        finish,
        extrude,
        new_body,
        down_5,
        extrude_ok,
        two_bodies,
        com_start,
        com_all,
        com_click_body1,
        com_body1,
        com_kept,
        com_undone,
        com_redone,
        com_select_row,
        com_edit,
        com_edit_dialog,
        com_edit_both,
        com_cancelled,
        com_all_start,
        com_all_ok,
        com_all_kept,
        com_follows_hidden,
        com_follows_shown,
        com_edit_extrude,
        com_extrude_ok,
        com_follows_edit,
        com_follows_undo,
        int_start,
        int_waits,
        int_second,
        int_compute,
        int_result,
        int_coincident,
        int_coincident_result,
        int_kept,
        int_select_row,
        int_edit,
        int_edit_dialog,
        esc_closed,
    ],
)
