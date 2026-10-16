# SPDX-License-Identifier: LGPL-2.1-or-later
"""Combine with New Component, Split Body with several tools, and Move/Copy of a body inside a
moved component, only real input.

Design 1: Body1 = 0..40 x 0..30 x 10 (12000); Body2 = 30..60 x 10..20 x 10 (3000), New Body;
they overlap in 30..40 x 10..20 x 10 (1000).

  A  Combine: click Body1 (target), Body2 (tool), tick New Component: the joined result
     (14000) is the body of a new component "Component1"; Body1 and Body2 are used up.
     OK: the timeline has the Component step and the Combine.
  B  Undo: no component, the two bodies back; Redo: the component again.
  C  Edit the Combine (timeline): New Component reads ticked; untick it: the component goes
     and the result joins Body1 (14000); Cancel: the component is back.
Design 2: a box -20..20 x -15..15 x 10 (12000).
  D  Split Body: click the box, the YZ square, click the Splitting Tool(s) box (the squares
     again), the XZ square: "2 tools", four bodies of 3000; OK: one Split Body step.
  E  Undo: one body of 12000; Redo: four again.
  F  Edit the split: the box reads "2 tools"; show the squares, click the XZ square again:
     it is dropped, two bodies of 6000 (x < 0, x > 0); OK.
  G  Create Components from Bodies on the x > 0 half, Move the component (X Distance 100,
     not captured), then Move/Copy its body with Create Copy, Y Distance 50: the copy is in
     the same component, at x 100..120, y 35..65 (not moved twice) and nothing complains.
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def combines():
    return s.steps_of_kind("Combine")


def splits():
    return s.steps_of_kind("SplitBody")


def new_design():
    s.new_design("Components2Bodies")()


def setup():
    found = cs.bodies()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    state["b1"], state["b2"] = found[0].Name, found[1].Name
    state["comps0"] = c.labels()


# -- A --------------------------------------------------------------------------------------------
def a_open():
    h.click_empty()
    h.fit()
    h.ribbon("Combine")


def a_target():
    h.click(V(10, 5, 10))


def a_tool():
    h.click(V(55, 15, 10))


def a_new_component():
    p = s.panel()
    if h.check("Combine open", p is not None and p.title == "Combine", p):
        h.check("New Component offered", p.new_component.isVisible())
        s.toggle(p.new_component)


def a_preview():
    from sciforge import combine, components

    p = s.panel()
    feature = p.target if p is not None else None
    made = combine.created_body(feature) if feature is not None else None
    part = components.container_of(made) if made is not None else None
    h.check("a new component holds the result", part is not None, c.labels())
    h.check("its body 14000", made is not None and c.close(c.volume(made), 14000), c.volume(made))
    h.check("New Body greyed while New Component is on", p.new_body.isEnabled() is False)
    h.shot("A-preview")


def a_ok():
    h.task_button("OK")


def a_done():
    from sciforge import combine, components

    h.check("dialog closed", s.panel() is None)
    h.check("one Combine", len(combines()) == 1, combines())
    made = combine.created_body(combines()[0]) if combines() else None
    part = components.container_of(made) if made is not None else None
    h.check("the result in Component1", part is not None and part.Label == "Component1", part)
    b1 = App.ActiveDocument.getObject(state["b1"])
    b2 = App.ActiveDocument.getObject(state["b2"])
    h.check("Body1 used up (hidden)", not s.shown(b1))
    h.check("Body2 used up (hidden)", not s.shown(b2))
    titles = t.titles()
    h.check("the timeline has the component", "Component1" in titles, titles)


# -- B --------------------------------------------------------------------------------------------
def b_undo():
    s.undo()


def b_undone():
    h.check("Undo: no Component1", c.part("Component1") is None, c.labels())
    h.check("Undo: Body1 shown", s.shown(App.ActiveDocument.getObject(state["b1"])))


def b_redo():
    s.redo()


def b_redone():
    h.check("Redo: Component1 back", c.part("Component1") is not None, c.labels())


# -- C --------------------------------------------------------------------------------------------
def c_edit():
    s.timeline_double_click(combines()[0])


def c_untick():
    p = s.panel()
    if h.check("edit dialog", p is not None and p.editing, p):
        h.check("New Component reads ticked", p.new_component.isChecked())
        s.toggle(p.new_component)


def c_preview():
    b1 = App.ActiveDocument.getObject(state["b1"])
    h.check("the component goes", c.part("Component1") is None, c.labels())
    h.check("the result joins Body1", c.close(c.volume(b1), 14000), c.volume(b1))


def c_cancel():
    h.task_button("Cancel")


def c_back():
    h.check("Cancel: Component1 back", c.part("Component1") is not None, c.labels())
    b1 = App.ActiveDocument.getObject(state["b1"])
    h.check("Cancel: Body1 as it was", c.close(c.volume(b1), 12000), c.volume(b1))


# -- D --------------------------------------------------------------------------------------------
def d_new_design():
    s.new_design("Components2Split")()


def d_open():
    h.click_empty()
    h.fit()
    h.ribbon("Split Body")


def d_click_body():
    h.click(V(-10, -5, 10))


def d_click_yz():
    pl.click_square("YZ_Plane")  # where the square shows (was 0, -24, 20)


def d_show_squares():
    p = s.panel()
    if h.check("Split Body open", p is not None, p):
        h.check("one tool", len(p.options["tools"]) == 1, p.options["tools"])
    s.click_box("tool")


def d_click_xz():
    p = s.panel()
    h.check("the squares again", p is not None and p.plane_picker is not None)
    pl.click_square("XZ_Plane")  # where the square shows (was 15, 0, 18)


def d_preview():
    p = s.panel()
    found = s.bodies()
    h.check("two tools", p is not None and len(p.options["tools"]) == 2, p and p.options["tools"])
    h.check("the box says 2 tools", p is not None and p.fields["tool"].button.text() == "2 tools")
    h.check("four bodies", len(found) == 4, [x.Label for x in found])
    h.check(
        "3000 each", all(c.close(s.volume(x), 3000) for x in found), [s.volume(x) for x in found]
    )
    h.shot("D-preview")


def d_ok():
    h.task_button("OK")


def d_done():
    h.check("dialog closed", s.panel() is None)
    h.check("one Split Body step", len(splits()) == 1, splits())
    h.check("four bodies", len(s.bodies()) == 4, [x.Label for x in s.bodies()])


# -- E --------------------------------------------------------------------------------------------
def e_undo():
    s.undo()


def e_undone():
    h.check("Undo: one body of 12000", len(s.bodies()) == 1, [x.Label for x in s.bodies()])


def e_redo():
    s.redo()


def e_redone():
    h.check("Redo: four bodies", len(s.bodies()) == 4, [x.Label for x in s.bodies()])


# -- F --------------------------------------------------------------------------------------------
def f_edit():
    h.fit()
    s.timeline_double_click(splits()[0])


def f_show_squares():
    p = s.panel()
    if h.check("edit dialog", p is not None and p.editing, p):
        h.check("2 tools read back", len(p.options["tools"]) == 2, p.options["tools"])
    s.click_box("tool")


def f_click_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 8, 0, 12)


def f_preview():
    found = s.bodies()
    h.check("XZ dropped: two bodies", len(found) == 2, [x.Label for x in found])
    h.check("6000 each", all(c.close(s.volume(x), 6000) for x in found))


def f_ok():
    h.task_button("OK")


# -- G --------------------------------------------------------------------------------------------
def g_component():
    found = s.bodies()
    right = [x for x in found if c.box_of(x)[0] > -1e-6]
    if h.check("the x > 0 half", len(right) == 1, [c.box_of(x) for x in found]):
        state["half"] = right[0].Name
        state["half_label"] = right[0].Label
        t.row_menu(right[0].Label, "Create Components from Bodies")


def g_move_open():
    h.click_empty()
    t.click_row(state["half_label"])  # the component is named after the body


def g_press_m():
    h.press("m")


def g_move_component():
    p = c.component_panel()
    if h.check("component Move open", p is not None, c.panel()):
        c.type_value(p, "dx", "100")


def g_ok():
    h.task_button("OK")


def g_moved():
    half = App.ActiveDocument.getObject(state["half"])
    c.box_is("the component moved 100", half, [100, -15, 0, 120, 15, 10])
    state["copies0"] = len(s.bodies())


def g_copy_open():
    h.click_empty()
    h.fit()
    h.press("m")


def g_copy_pick():
    h.click(V(110, 0, 10))


def g_copy_values():
    p = s.panel()
    half = App.ActiveDocument.getObject(state["half"])
    if h.check("bodies Move open", p is not None and p.object_type == "bodies", p):
        h.check("the half picked", p.options["bodies"] == [half], p.options["bodies"])
        b_choose = c.choose(p.move_type, "Translate")
        if b_choose:
            c.type_value(p, "dy", "50")
        s.toggle(p.copy)


def g_copy_ok():
    h.task_button("OK")


def g_copied():
    from sciforge import components

    found = s.bodies()
    h.check("one more body", len(found) == state["copies0"] + 1, [x.Label for x in found])
    new = found[-1]
    half = App.ActiveDocument.getObject(state["half"])
    h.check(
        "the copy is in the same component",
        components.container_of(new) is components.container_of(half),
    )
    c.box_is("at x 100..120, y 35..65 (not moved twice)", new, [100, 35, 0, 120, 65, 10])
    h.shot("G-copy")


h.run(
    "components2_bodies",
    t.watched(
        [new_design]
        + s.box_steps("body1", (0, 0, 40, 30), 10, V(6, -6, 0))
        + s.box_steps("body2", (30, 10, 60, 20), 10, V(6, -6, 0), new_body=True)
        + [
            setup,
            a_open,
            a_target,
            a_tool,
            a_new_component,
            a_preview,
            a_ok,
            a_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_edit,
            c_untick,
            c_preview,
            c_cancel,
            c_back,
            d_new_design,
        ]
        + s.box_steps("box", (-20, -15, 20, 15), 10, V(5, -24, 0))
        + [
            d_open,
            d_click_body,
            d_click_yz,
            d_show_squares,
            d_click_xz,
            d_preview,
            d_ok,
            d_done,
            e_undo,
            e_undone,
            e_redo,
            e_redone,
            f_edit,
            f_show_squares,
            f_click_xz,
            f_preview,
            f_ok,
            g_component,
            g_move_open,
            g_press_m,
            g_move_component,
            g_ok,
            g_moved,
            g_copy_open,
            g_copy_pick,
            g_copy_values,
            g_copy_ok,
            g_copied,
        ]
    ),
)
