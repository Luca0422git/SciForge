# SPDX-License-Identifier: LGPL-2.1-or-later
"""The bodies the Extrude dialog's "Bodies to Cut" row lists light up in the 3D view while
the row is active (clicked), so you see which bodies the extrude changes. Only real input.

Body1 = x 0..20, Body2 = x 30..50 (20 x 20 x 10). A sketch at z 10 over x 10..40, y 5..15;
E, -5: Cut through both, "2 bodies", no highlight yet (the Profiles box takes the clicks).
Click the row: two see-through blue copies (one per body, over each body's box, clicks go
through them). Click Body2 away: one copy left (Body1's); click it back: two. Click the
Profiles box: the highlight goes. Click the row again: back. Cancel: nothing left in the
view. E again, -5, click the row, OK: nothing left either.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
state = {}


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def highlights():
    from sciforge import cut_preview

    return cut_preview.find_highlights()


def node_box(node):
    """The bounding box of a highlight node's points."""
    from pivy import coin

    for i in range(node.getNumChildren()):
        child = node.getChild(i)
        if child.isOfType(coin.SoCoordinate3.getClassTypeId()):
            box = App.BoundBox()
            for k in range(child.point.getNum()):
                x, y, z = child.point[k].getValue()
                box.add(App.Vector(x, y, z))
            return box
    return None


def covers(box, lo, hi, tol=1e-3):
    return box is not None and all(
        abs(getattr(box, k) - v) <= tol
        for k, v in zip(("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"), lo + hi)
    )


def boxes_of(nodes):
    return sorted(
        ((round(b.XMin, 3), round(b.XMax, 3)) for b in (node_box(n) for n in nodes) if b),
    )


def row(p):
    if p is None or not p.bodies_label.isVisible():
        return None
    return (p.bodies_label.text(), p.fields["bodies"].button.text())


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("BodiesHighlight")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    s1 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s1, 0, 0, 20, 20)
    extrude.make(body, s1, {"distance": 10.0})
    s2 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s2, 30, 0, 50, 20)
    extrude.make(body, s2, {"distance": 10.0, "operation": "new_body"})
    App.ActiveDocument.recompute()
    s3 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    s3.AttachmentOffset = App.Placement(V(0, 0, 10), App.Rotation())
    h.draw_rectangle(s3, 10, 5, 40, 15)
    App.ActiveDocument.recompute()
    state["sketch"] = s3
    h.fit()
    h.check("two boxes", len(s.bodies()) == 2 and all(s.close(s.volume(b), 4000) for b in s.bodies()),
            [s.volume(b) for b in s.bodies()])


def press_e():
    h.fit()
    h.press("e")


def type_minus_5():
    p = xpanel()
    h.check("E opens Extrude on the sketch across both", p is not None and len(p.profiles) == 1,
            p and p.profiles)
    if p is not None:
        ui.type_into(p.distance.widget, "-5")


def two_bodies_no_highlight():
    p = xpanel()
    h.check("Cut through both: 2 bodies", row(p) == ("Bodies to Cut", "2 bodies"), row(p))
    h.check("no highlight while the Profiles box takes the clicks", not highlights(),
            len(highlights()))
    if p is not None:
        bs.click_widget(p.fields["bodies"].button)


def row_active_highlighted():
    p = xpanel()
    h.check("the row takes the clicks", p is not None and p.active == "bodies", p and p.active)
    nodes = highlights()
    h.check("two blue copies, one per listed body", len(nodes) == 2, len(nodes))
    h.check("they cover the two boxes", boxes_of(nodes) == [(0.0, 20.0), (30.0, 50.0)],
            boxes_of(nodes))
    if nodes:
        from pivy import coin

        first = nodes[0].getChild(0)
        h.check("clicks go through them",
                first.isOfType(coin.SoPickStyle.getClassTypeId())
                and first.style.getValue() == coin.SoPickStyle.UNPICKABLE)
        material = None
        for i in range(nodes[0].getNumChildren()):
            child = nodes[0].getChild(i)
            if child.isOfType(coin.SoMaterial.getClassTypeId()):
                material = (tuple(child.diffuseColor[0].getValue()), child.transparency[0])
                break
        h.check("they are see-through blue", material is not None and material[0][2] > 0.8
                and material[0][0] < 0.4 and 0.2 < material[1] < 0.9, material)
    h.shot("1-highlighted")
    h.click(V(45, 10, 10))  # Body2's top, away from the cut: leave it out


def body2_left_out():
    p = xpanel()
    h.check("Body2 left out: 1 body", row(p) == ("Bodies to Cut", "1 body"), row(p))
    nodes = highlights()
    h.check("one blue copy left (Body1's)", boxes_of(nodes) == [(0.0, 20.0)], boxes_of(nodes))
    h.click(V(45, 10, 10))  # back


def body2_back():
    p = xpanel()
    h.check("Body2 back: 2 bodies", row(p) == ("Bodies to Cut", "2 bodies"), row(p))
    h.check("two blue copies again", len(highlights()) == 2, len(highlights()))
    if p is not None:
        bs.click_widget(p.fields["profiles"].button)  # leave the row


def row_left():
    p = xpanel()
    h.check("the Profiles box takes the clicks again", p is not None and p.active == "profiles",
            p and p.active)
    h.check("the highlight is gone when the row is left", not highlights(), len(highlights()))
    if p is not None:
        bs.click_widget(p.fields["bodies"].button)


def row_again():
    h.check("the row clicked again: the highlight is back", len(highlights()) == 2,
            len(highlights()))
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closed the dialog", xpanel() is None)
    h.check("no highlight left after Cancel", not highlights(), len(highlights()))
    h.check("both boxes whole", all(s.close(s.volume(b), 4000) for b in s.bodies()),
            [s.volume(b) for b in s.bodies()])


def e_again():
    h.fit()
    h.press("e")


def type_minus_5_again():
    p = xpanel()
    h.check("E again", p is not None and len(p.profiles) == 1, p and p.profiles)
    if p is not None:
        ui.type_into(p.distance.widget, "-5")


def row_then_ok():
    p = xpanel()
    if p is not None:
        bs.click_widget(p.fields["bodies"].button)
    h.check("highlighted before OK", len(highlights()) == 2, len(highlights()))
    h.task_button("OK")


def done():
    h.check("OK closed the dialog", xpanel() is None)
    h.check("no highlight left after OK", not highlights(), len(highlights()))
    h.check("both bodies cut: 3500 / 3500", all(s.close(s.volume(b), 3500) for b in s.bodies()),
            [s.volume(b) for b in s.bodies()])


h.run(
    "extrude_bodies_highlight",
    [
        setup,
        press_e,
        type_minus_5,
        two_bodies_no_highlight,
        row_active_highlighted,
        body2_left_out,
        body2_back,
        row_left,
        row_again,
        cancelled,
        e_again,
        type_minus_5_again,
        row_then_ok,
        done,
    ],
)
