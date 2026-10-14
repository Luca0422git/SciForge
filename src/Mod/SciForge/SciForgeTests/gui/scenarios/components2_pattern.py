# SPDX-License-Identifier: LGPL-2.1-or-later
"""Patterns of components (Pattern Type: Components), only real input.

Setup: a 20 x 10 x 10 block at x 20..40, y -5..5 made into the component "Spoke" (2000),
and a root body "Hub" (r 10 cylinder... a 10 x 10 box at x -5..5, y 60..70) that is in no
component.

  A  Circular Pattern (CREATE menu), Pattern Type Components; click the root body: refused
     (it is in no component); click Spoke: picked. Axis box, click the Z axis: Quantity 6
     makes 5 copies Spoke:2..Spoke:6 around Z (60 degrees apart, 2000 each); the browser
     reads Spoke:1..Spoke:6. OK: one Circular Pattern step in the timeline.
  B  Undo: the copies go; Redo: back.
  C  Double-click the pattern in the timeline: Pattern Type reads Components, Quantity 6;
     Quantity 4, OK: 3 copies (90 degrees apart).
  D  Extrude 1 (Spoke's) to 20 high: every copy follows (4000 each).
  E  The history marker before the pattern: the copies are hidden (and gone from the
     browser); the marker to the end: back.
  F  Rectangular Pattern of Spoke along the X axis, Quantity 3, Distance 100 (Spacing...
     Extent: the copies at x +50 and +100); OK; then Delete it from the timeline: its copies
     go with it; Undo brings them back.
  G  Save, close, reopen: the circular pattern's copies are still instances of Spoke.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
BLOCK = 2000.0


def spoke():
    return c.part("Spoke")


def copies_of(step=None):
    from sciforge import component_pattern, instances

    found = [p for p in c.doc().Objects if instances.is_instance(p)]
    if step is not None:
        return component_pattern.copies(step)
    return found


def pattern_steps():
    from sciforge import component_pattern

    return [o for o in c.doc().Objects if component_pattern.is_component_pattern(o)]


def centre_angles(parts):
    out = []
    for p in parts:
        box = c.shape(p).BoundBox
        out.append(round(math.degrees(math.atan2(box.Center.y, box.Center.x)) % 360.0, 3))
    return sorted(out)


def new_design():
    s.new_design("Components2Pattern")()


def setup_component():
    found = cs.bodies()
    h.check("two bodies", len(found) == 2, [x.Label for x in found])
    state["b1"], state["hub"] = found[0].Name, found[1].Name
    state["l1"] = found[0].Label
    t.row_menu(state["l1"], "Create Components from Bodies")


def setup_rename():
    cs.rename_row(state["l1"], "Spoke")


def setup_done():
    h.check("Spoke exists", spoke() is not None, c.labels())
    c.box_is("Spoke at x 20..40", spoke(), [20, -5, 0, 40, 5, 10])


# -- A --------------------------------------------------------------------------------------------
def a_open():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    ps.menu("Circular Pattern")


def a_type():
    p = ps.panel()
    if h.check("Circular Pattern open", p is not None and p.kind == "circular", p):
        index = p.pattern_type.findText("Components")
        item = p.pattern_type.model().item(index)
        h.check("Components can be chosen", item is not None and item.isEnabled())
        b.choose(p.pattern_type, "Components")


def a_click_hub():
    h.click(V(0, 65, 10))


def a_refused():
    p = ps.panel()
    if h.check("dialog open", p is not None):
        h.check("nothing picked", p.options["objects"] == [], p.options["objects"])
        h.check("says it is in no component", "no component" in p.message.text(), p.message.text())


def a_click_spoke():
    h.click(V(30, 0, 10))


def a_axis_box():
    p = ps.panel()
    h.check("Spoke picked", p is not None and p.options["objects"] == [(spoke(), "")], p.options)
    ps.click_box("axis")


def a_click_z():
    p = ps.panel()
    h.check("origin axes drawn", p is not None and p.axis_picker is not None)
    h.fit()
    h.click(V(0, 0, 22))


def a_quantity():
    p = ps.panel()
    axis = p.options["axis"] if p else None
    h.check("the Z axis is the axis", axis is not None and axis[0].Role == "Z_Axis", axis)
    ps.type_quantity(p.quantity, 6)


def a_preview():
    made = copies_of()
    h.check("5 copies", len(made) == 5, [x.Label for x in made])
    labels = sorted(x.Label for x in made)
    h.check("named Spoke:2..Spoke:6", labels == ["Spoke:%d" % n for n in range(2, 7)], labels)
    h.check(
        "every 60 degrees",
        centre_angles(made) == [60.0, 120.0, 180.0, 240.0, 300.0],
        centre_angles(made),
    )
    h.check("each 2000", all(c.close(c.volume(x), BLOCK) for x in made))
    h.shot("A-preview")


def a_ok():
    h.task_button("OK")


def a_done():
    h.check("dialog closed", ps.panel() is None)
    steps = pattern_steps()
    h.check("one pattern step", len(steps) == 1, steps)
    if steps:
        state["circ"] = steps[0].Name
        title = c.timeline_title(steps[0])
        h.check("timeline: Circular Pattern 1", title == "Circular Pattern 1", title)
    labels = c.browser_labels()
    h.check(
        "browser: Spoke:1 .. Spoke:6",
        {"Spoke:%d" % n for n in range(1, 7)} <= set(labels),
        labels,
    )


# -- B --------------------------------------------------------------------------------------------
def b_undo():
    s.undo()


def b_undone():
    h.check("Undo: no copies", not copies_of(), [x.Label for x in copies_of()])
    h.check("Undo: no pattern step", not pattern_steps())


def b_redo():
    s.redo()


def b_redone():
    h.check("Redo: 5 copies", len(copies_of()) == 5, [x.Label for x in copies_of()])


# -- C --------------------------------------------------------------------------------------------
def c_edit():
    b.timeline_double_click("Circular Pattern 1")


def c_change():
    p = ps.panel()
    if not h.check("edit dialog", p is not None and p.editing, p):
        return
    h.check("Pattern Type Components", p.pattern_type.currentText() == "Components")
    h.check("Quantity 6", p.quantity.value() == 6, p.quantity.value())
    ps.type_quantity(p.quantity, 4)


def c_ok():
    h.task_button("OK")


def c_done():
    made = copies_of()
    h.check("3 copies", len(made) == 3, [x.Label for x in made])
    h.check("every 90 degrees", centre_angles(made) == [90.0, 180.0, 270.0], centre_angles(made))


# -- D --------------------------------------------------------------------------------------------
def d_edit():
    b.timeline_double_click("Extrude 1")


def d_type():
    from SciForgeTests.gui import bodies_steps

    p = c.panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("extrude dialog open", field is not None, p):
        bodies_steps.type_value(field, "20")


def d_ok():
    h.task_button("OK")


def d_follow():
    made = copies_of()
    h.check("Spoke 4000", c.close(c.volume(spoke()), 2 * BLOCK), c.volume(spoke()))
    h.check("every copy follows", all(c.close(c.volume(x), 2 * BLOCK) for x in made))
    h.shot("D-follow")


# -- E --------------------------------------------------------------------------------------------
def e_roll():
    t.drag_marker(before_title="Circular Pattern 1")


def e_rolled():
    made = copies_of()
    h.check("the copies are hidden", all(not t.shown(x) for x in made), [t.shown(x) for x in made])
    labels = c.browser_labels()
    h.check("and gone from the browser", not any(":" in x and "Spoke" in x for x in labels), labels)
    h.check("Spoke itself stays", t.shown(spoke()))


def e_end():
    t.drag_marker(to_end=True)


def e_back():
    made = copies_of()
    h.check("shown again", all(t.shown(x) for x in made), [t.shown(x) for x in made])


# -- F --------------------------------------------------------------------------------------------
def f_open():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    ps.menu("Rectangular Pattern")


def f_type():
    p = ps.panel()
    if h.check("Rectangular Pattern open", p is not None and p.kind == "rectangular", p):
        b.choose(p.pattern_type, "Components")


def f_pick():
    t.click_row("Spoke:1")


def f_direction_box():
    p = ps.panel()
    h.check("Spoke picked from its row", p is not None and p.options["objects"] == [(spoke(), "")])
    ps.click_box("direction")


def f_click_x():
    h.fit()
    h.click(V(-30, 0, 0))


def f_values():
    p = ps.panel()
    d = p.options["direction"] if p else None
    h.check("the X axis is direction 1", d is not None and d[0].Role == "X_Axis", d)
    ps.type_quantity(p.quantity, 3)
    ps.type_value(p.distance_field.widget, "100")


def f_preview():
    from sciforge import component_pattern

    p = ps.panel()
    step = p.target if p is not None else None
    made = component_pattern.copies(step) if step is not None else []
    h.check("2 more copies", len(made) == 2, [x.Label for x in made])
    xs = sorted(round(c.box_of(x)[0], 3) for x in made)
    h.check("at x 70 and 120 (extent 100)", xs == [70.0, 120.0], xs)


def f_ok():
    h.task_button("OK")


def f_delete():
    steps = [x for x in pattern_steps() if x.Name != state.get("circ")]
    if h.check("a second pattern step", len(steps) == 1, steps):
        state["rect"] = steps[0].Name
        t.menu(c.timeline_title(steps[0]), "Delete")


def f_deleted():
    h.check("its copies went with it", len(copies_of()) == 3, [x.Label for x in copies_of()])


def f_undo():
    s.undo()


def f_undone():
    h.check("Undo: 5 copies again", len(copies_of()) == 5, [x.Label for x in copies_of()])


# -- G --------------------------------------------------------------------------------------------
def g_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "components2_pattern.FCStd")
    App.ActiveDocument.saveAs(state["path"])
    App.closeDocument(App.ActiveDocument.Name)


def g_open():
    App.openDocument(state["path"])
    h.fit()


def g_reopened():
    from sciforge import instances

    made = copies_of(c.doc().getObject(state["circ"]))
    h.check("3 copies of the circular pattern", len(made) == 3, [x.Label for x in made])
    h.check("still instances of Spoke", all(instances.source_of(x) is spoke() for x in made))
    h.check("still 4000 each", all(c.close(c.volume(x), 2 * BLOCK) for x in made))


h.run(
    "components2_pattern",
    t.watched(
        [new_design]
        + s.box_steps("spoke", (20, -5, 40, 5), 10, V(12, -8, 0))
        + s.box_steps("hub", (-5, 60, 5, 70), 10, V(12, -8, 0), new_body=True)
        + [
            setup_component,
            setup_rename,
            setup_done,
            a_open,
            a_type,
            a_click_hub,
            a_refused,
            a_click_spoke,
            a_axis_box,
            a_click_z,
            a_quantity,
            a_preview,
            a_ok,
            a_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_edit,
            c_change,
            c_ok,
            c_done,
            d_edit,
            d_type,
            d_ok,
            d_follow,
            e_roll,
            e_rolled,
            e_end,
            e_back,
            f_open,
            f_type,
            f_pick,
            f_direction_box,
            f_click_x,
            f_values,
            f_preview,
            f_ok,
            f_delete,
            f_deleted,
            f_undo,
            f_undone,
            g_save_close,
            g_open,
            g_reopened,
        ]
    ),
)
