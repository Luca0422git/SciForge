# SPDX-License-Identifier: LGPL-2.1-or-later
"""The INSPECT analyses with components (real input): New Component (Component1), a box
40 x 30 x 10 made in it, the root activated again and a box 20 x 20 x 5 at x = 60 made
there. Component1 is then lifted 20 mm (its placement). Zebra Analysis on Component1's
body: the stripes are drawn where that body is (inside its screen outline), not where it
would be without the component's placement; the root body keeps its own look. Display
Component Colors (Shift+N): each component in a colour of its own (Component1's body and
the root body differ), the menu entry ticked, the zebra still shown on its body; Shift+N
again: the bodies' own look. Display Component Colors from the INSPECT menu, then off."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s

V = App.Vector
st = {}


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Components")
    st["doc"] = App.ActiveDocument.Label
    h.fit()
    h.ribbon("New Component")


def component_ok():
    h.task_button("OK")


def sketch_1():
    h.fit()
    h.ribbon("Create Sketch")


def plane_1():
    h.click(V(12, -8, 0))


def rect_1():
    sk = h.in_sketch()
    h.check("a sketch in Component1", sk is not None and cs.container_label(sk) == "Component1")
    if sk is not None:
        h.draw_rectangle(sk, 0, 0, 40, 30)


def finish_1():
    h.ribbon("Finish Sketch")


def extrude_1():
    h.fit()
    h.press("e")


def distance_1():
    h.check("extrude dialog", ai.give_distance("10"))


def ok_1():
    h.task_button("OK")


def made_1():
    body = h.body()
    h.check("Body1 in Component1", body is not None and cs.container_label(body) == "Component1")
    st["b1"] = body.Name if body is not None else ""
    cs.click_radio(st["doc"])


def sketch_2():
    h.check("the root is active", cs.active_label() is None)
    h.fit()
    h.ribbon("Create Sketch")


def plane_2():
    h.click(V(12, -8, 0))


def rect_2():
    sk = h.in_sketch()
    if sk is not None:
        h.draw_rectangle(sk, 60, 0, 80, 20)


def finish_2():
    h.ribbon("Finish Sketch")


def extrude_2():
    h.fit()
    h.press("e")


def distance_2():
    h.check("extrude dialog", ai.give_distance("5"))


def ok_2():
    h.task_button("OK")


def made_2():
    body = h.body()
    h.check("a root body", body is not None and cs.container_label(body) is None)
    st["b2"] = body.Name if body is not None else ""
    part = cs.component("Component1")
    part.Placement = App.Placement(V(0, 0, 20), App.Rotation())  # lifted 20 mm
    App.ActiveDocument.recompute()
    h.fit()


def b1():
    return App.ActiveDocument.getObject(st["b1"])


def b2():
    return App.ActiveDocument.getObject(st["b2"])


def global_rect(body):
    """The screen rectangle of a body where it really is (its component's placement)."""
    from sciforge import surface_analysis as sa

    shape = body.Shape.transformed(sa.parent_placement(body).toMatrix())

    class Shim:
        Shape = shape

    return a.part_rect(Shim)


def zebra_start():
    a.inspect("Zebra Analysis")


def zebra_pick():
    h.click(V(20, 15, 30))  # Component1's body's top, lifted


def zebra_there():
    objs = a.analyses("ZebraAnalysis")
    h.check(
        "Zebra1 on Component1's body",
        len(objs) == 1 and objs[0].Targets[0][0] is b1(),
        objs and objs[0].Targets,
    )
    counts = a.colors(global_rect(b1()))
    h.check(
        "stripes where the lifted body is",
        a.share(counts, "black") > 0.1 and a.share(counts, "white") > 0.1,
        counts,
    )
    low = a.colors(global_rect(b2()))
    h.check("the root body keeps its own look", a.share(low, "white") < 0.02, low)
    h.shot("1-zebra-component")
    h.task_button("OK")


def colours_on():
    h.press(QtCore.Qt.Key_N, QtCore.Qt.ShiftModifier)


def coloured():
    from sciforge import component_colors_ui

    h.check("Shift+N: component colours on", component_colors_ui.is_on())
    one = a.color_at(V(10, 10, 30))
    two = a.color_at(V(70, 10, 5))
    h.check(
        "the root body is coloured (not grey)",
        a.classify(*two) not in ("grey", "white", "black"),
        two,
    )
    st["root"] = two
    stripes = a.colors(global_rect(b1()))
    h.check("the zebra still shows on its body", a.share(stripes, "black") > 0.1, stripes)
    h.shot("2-colours")
    h.check(
        "Component1's body shows the zebra, not its colour",
        a.classify(*one) in ("black", "white"),
        one,
    )
    a.open_analysis_folder()
    s.eye("Zebra1")


def zebra_hidden():
    one = a.color_at(V(10, 10, 30))
    two = a.color_at(V(70, 10, 5))
    h.check(
        "Component1's body coloured now", a.classify(*one) not in ("grey", "white", "black"), one
    )
    h.check("in a colour of its own", a.classify(*one) != a.classify(*two), (one, two))
    h.check("the INSPECT entry is ticked", menu_ticked())
    h.press(QtCore.Qt.Key_N, QtCore.Qt.ShiftModifier)


def menu_ticked():
    from SciForgeTests.gui import sketch_input as si

    group = si._group_widget("INSPECT")
    if group is None:
        return None
    menu = group.menu
    menu.aboutToShow.emit()
    for action in menu.actions():
        if action.text().split("\t")[0] == "Display Component Colors":
            return action.isChecked()
    return None


def colours_off():
    from sciforge import component_colors_ui

    h.check("Shift+N again: off", not component_colors_ui.is_on())
    h.check("the bodies' own look", a.classify(*a.color_at(V(70, 10, 5))) == "grey")
    h.check("the model's faces are back", a.model_faces_shown(b1()) and a.model_faces_shown(b2()))
    a.inspect("Display Component Colors")


def from_menu():
    from sciforge import component_colors_ui

    h.check("INSPECT > Display Component Colors: on", component_colors_ui.is_on())
    a.inspect("Display Component Colors")


def menu_off():
    from sciforge import component_colors_ui

    h.check("and off again", not component_colors_ui.is_on())


h.run(
    "inspect_analysis_components",
    [
        new_design,
        component_ok,
        sketch_1,
        plane_1,
        rect_1,
        finish_1,
        extrude_1,
        distance_1,
        ok_1,
        made_1,
        sketch_2,
        plane_2,
        rect_2,
        finish_2,
        extrude_2,
        distance_2,
        ok_2,
        made_2,
        zebra_start,
        zebra_pick,
        zebra_there,
        colours_on,
        coloured,
        zebra_hidden,
        colours_off,
        from_menu,
        menu_off,
    ],
)
