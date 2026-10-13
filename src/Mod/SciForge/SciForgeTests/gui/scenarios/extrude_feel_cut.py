# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cuts show in red while the dialog is open (Luca's R7), and Press Pull feels like the
Extrude dialog (R2, R3, R5), only real input.

Box 40 x 30 x 10 (sketch, Finish, E, type 10, OK). A 10 x 10 square sketched on its top
face (x 10..20, y 5..15), Finish Sketch.
R7  E, type -6: Cut, and the removed volume shows as one red see-through node over the
    part (exactly the pocket: 10..20 x 5..15 x 4..10), clicks go through it, the blue of
    the picked profile is faded meanwhile, the features keep their own colours. Type 5
    (Join): the red goes. Drag the arrow down into the part with the button held: red
    again while dragging. Type -5: the arrow's head is now under the sketch, which stays
    in view (R6); it can still be grabbed and dragged (the profile stays picked).
    Cancel: no red left, the scene is as before E, the part too.
    E, -6, OK: the pocket is made, no red left. Undo; E, -6, Ctrl+Z: no red left.
Press Pull on the top face:
R5  it starts at 0; OK at 0 keeps the dialog open and makes no step. Type 5, then 0 and
    Enter at once (in the dialog's field, then in the value box): the dialog stays open and
    still says why a moment later (the preview rebuild that followed wiped the message).
R3  a value box next to its arrow shows the dialog's distance.
R2  dragging the arrow down with the button held: the part follows while the button is
    still down, and the material pushed away shows in red (R7).
R7  type -3: the red slab is the top 3 mm of the box.
R3  click the box, type 5, Enter: 40 x 30 x 15, done (Enter = OK), no box and no red left.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
BOX = 12000.0
POCKET = 10.0 * 10.0 * 6.0


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def ppanel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def box_near(box, lo, hi, tol=1e-3):
    return box is not None and all(
        abs(getattr(box, k) - v) <= tol
        for k, v in zip(("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"), lo + hi)
    )


def not_red(obj):
    """The feature's own colour is not the preview's red."""
    try:
        color = obj.ViewObject.ShapeAppearance[0].DiffuseColor
    except Exception:
        return True
    return not (color[0] > 0.8 and color[1] < 0.3 and color[2] < 0.3)


def press_pulls():
    from sciforge import presspull

    return [o for o in App.ActiveDocument.Objects if presspull.is_press_pull(o)]


# -- a box and a square on its top face -------------------------------------------------------
def sketch_on_top():
    h.check("box 40 x 30 x 10", near(h.solid_volume(), BOX), h.solid_volume())
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 22, 10))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is not None:
        x0, y0 = h.to_sketch(sk, V(10, 5, 10))
        x1, y1 = h.to_sketch(sk, V(20, 15, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        s["square"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def press_e():
    h.fit()
    s["children"] = a.scene_children()
    h.press("e")


def opened():
    p = xpanel()
    h.check("E opens Extrude on the square", p is not None and len(p.profiles) == 1,
            p and p.profiles)
    h.check("no red at 0", not a.cut_nodes(), len(a.cut_nodes()))


# -- R7: a cut in red ----------------------------------------------------------------------------
def type_minus_6():
    ui.type_into(xpanel().distance.widget, "-6")


def cut_red():
    p = xpanel()
    h.check("into the part: Cut", p.operation.currentData() == "cut", p.operation.currentText())
    h.check("the pocket: 12000 - 600", near(h.solid_volume(), BOX - POCKET), h.solid_volume())
    nodes = a.cut_nodes()
    h.check("R7: one red preview node", len(nodes) == 1, len(nodes))
    if nodes:
        node = nodes[0]
        material = a.red_material(node)
        h.check("R7: it is red", material and material[0][0] > 0.8 and material[0][1] < 0.3,
                material)
        h.check("R7: see-through", material and 0.1 < material[1] < 0.9, material)
        box = a.node_box(node)
        h.check("R7: it is the removed volume (the pocket)",
                box_near(box, (10, 5, 4), (20, 15, 10)), box)
        from pivy import coin

        first = node.getChild(0)
        h.check("R7: clicks go through it",
                first.isOfType(coin.SoPickStyle.getClassTypeId())
                and first.style.getValue() == coin.SoPickStyle.UNPICKABLE)
    h.check("R7: the picked profile's blue is faded meanwhile",
            p.picker is not None and p.picker.dimmed)
    h.check("R7: the features keep their own colour", not_red(p.target) and not_red(h.body()))
    h.shot("1-cut-red")


def type_5():
    ui.type_into(xpanel().distance.widget, "5")


def join_not_red():
    p = xpanel()
    h.check("out of the part: Join", p.operation.currentData() == "join", p.operation.currentText())
    h.check("R7: no red for a join", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("R7: the profile's blue is back", p.picker is not None and not p.picker.dimmed)


def drag_into_part():
    p = xpanel()
    s["samples"] = samples = []
    start = h.screen_point(a.head_point(p.dragger))
    end = QtCore.QPoint(start.x(), start.y() + 120)

    def sample(index):
        q = xpanel()
        if q is None:
            return
        samples.append(
            {
                "i": index,
                "active": bool(q.dragger and q.dragger.dragger.isActive.getValue()),
                "cut": q.operation.currentData() == "cut",
                "red": len(a.cut_nodes()),
                "volume": round(h.solid_volume(), 3),
            }
        )

    s["drag"] = drag = a.HeldDrag(start, end, moves=40, every_ms=20, hold_ms=300, sample=sample)
    drag.run()


drag_into_part.wait_ms = 40 * 20 + 300 + 1200


def dragged_red():
    drag, samples = s.get("drag"), s.get("samples", [])
    h.check("the held drag ran", drag is not None and drag.done, drag and drag.error)
    held = [x for x in samples if x["active"]]
    h.check("the arrow was grabbed", len(held) > 10, len(held))
    h.check("R2+R7: red shows while the button is still down",
            any(x["red"] == 1 and x["cut"] for x in held), held[-5:])
    h.check("never more than one red node", bool(samples) and all(x["red"] <= 1 for x in samples))
    p = xpanel()
    h.check("dragged into the part: Cut", p.operation.currentData() == "cut",
            (p.operation.currentText(), p.distance.value()))
    h.check("R7: red after the release", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.shot("2-dragged-red")
    ui.type_into(p.distance.widget, "-5")


def regrab_in_pocket():
    """The arrow of a 5 mm cut has its head just under the profile's sketch, which stays in
    view until OK (R6): it must still be grabbed, not the sketch area behind it."""
    p = xpanel()
    s["regrab_before"] = p.distance.value()
    d = p.dragger
    head = d.origin + d.direction * (d.distance() + 0.9 * d.size)
    h.check("the arrow head is under the sketch plane", head.z < 10.0, head)
    start = h.screen_point(head)
    h.drag(start, QtCore.QPoint(start.x(), start.y() - 50))


def regrabbed():
    p = xpanel()
    h.check("R6: grabbing the arrow under the kept sketch keeps the profile picked",
            len(p.profiles) == 1, p.profiles)
    h.check("R6: and drags the arrow", p.distance.value() > s["regrab_before"] + 0.5,
            (p.distance.value(), s["regrab_before"]))


def cancel():
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes Extrude", xpanel() is None)
    h.check("R7: no red left after Cancel", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("R7: the scene is as before E", a.scene_children() == s["children"],
            (a.scene_children(), s["children"]))
    h.check("the box is untouched", near(h.solid_volume(), BOX), h.solid_volume())
    h.check("the sketch is still visible (R6)", s["square"].ViewObject.Visibility)


def e_again():
    h.press("e")


def ok_cut():
    p = xpanel()
    h.check("E picks the square again", p is not None and len(p.profiles) == 1)
    ui.type_into(p.distance.widget, "-6")


def ok_cut_red():
    h.check("R7: red before OK", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.task_button("OK")


def after_ok():
    h.check("OK made the pocket", near(h.solid_volume(), BOX - POCKET), h.solid_volume())
    h.check("R7: no red left after OK", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("R7: the scene is as before E", a.scene_children() == s["children"],
            (a.scene_children(), s["children"]))
    tip = h.body().Tip
    h.check("R7: no red colour left on the pocket", not_red(tip) and not_red(h.body()),
            tip.Name)
    h.check("R6: OK hides the sketch", not s["square"].ViewObject.Visibility)


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def e_after_undo():
    h.check("undone: the box again", near(h.solid_volume(), BOX), h.solid_volume())
    h.press("e")


def type_minus_6_again():
    ui.type_into(xpanel().distance.widget, "-6")


def ctrl_z():
    h.check("R7: red shown", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone_dialog():
    h.check("Ctrl+Z cancels the dialog", xpanel() is None and not Gui.Control.activeDialog())
    h.check("R7: no red left after Ctrl+Z", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("the box is untouched", near(h.solid_volume(), BOX), h.solid_volume())
    h.check("no value box left", not a.value_boxes(visible_only=False))
    h.fit()


# -- Press Pull ----------------------------------------------------------------------------------
def press_q():
    h.press("q")


def click_top_face():
    h.click(V(32, 25, 10))  # away from the square: the face, not the sketch area


def pp_opened():
    p = ppanel()
    if not h.check("Press Pull took the top face", p is not None and p.mode == "faces",
                   p and p.message.text()):
        return
    h.check("R5: Press Pull starts at 0", near(p.field.value(), 0.0), p.field.value())
    boxes = a.value_boxes()
    h.check("R3: a value box next to the arrow", len(boxes) == 1, len(boxes))
    if boxes and p.dragger is not None:
        h.check("R3: it shows the dialog's distance", boxes[0].text() == p.field.widget.text(),
                (boxes[0].text(), p.field.widget.text()))
        ok, detail = a.box_near(boxes[0], p.dragger)
        h.check("R3: at the arrow's tip", ok, detail)
    h.shot("3-pp-opened")
    h.task_button("OK")


def pp_ok_at_zero():
    p = ppanel()
    h.check("R5: OK at 0 keeps Press Pull open", p is not None)
    if p is not None:
        h.check("R5: it says why", "zero" in p.message.text(), p.message.text())
    body = h.body()
    zero_steps = [o.Name for o in body.Group if o in press_pulls() and abs(o.Distance.Value) < 1e-9
                  and o is not (p.target if p else None)]
    h.check("R5: no empty step was made", not zero_steps, zero_steps)


def type_enter(widget, text):
    """Click a dialog field, select what is there, type `text` and press Enter at once."""
    QtTest.QTest.mouseClick(
        widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, widget.height() // 2)
    )
    QtWidgets.QApplication.processEvents()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(widget, text)
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def pp_type_5():
    ui.type_into(ppanel().field.widget, "5")


def pp_zero_enter_field():
    h.check("5 typed: 40 x 30 x 15", near(h.solid_volume(), 1200.0 * 15), h.solid_volume())
    type_enter(ppanel().field.widget, "0")


pp_zero_enter_field.wait_ms = 1000  # well past the preview's next rebuild


def zero_still_said(where):
    p = ppanel()
    h.check("R5: 0 + Enter in %s keeps Press Pull open" % where, p is not None)
    if p is None:
        return None
    h.check("R5: a moment later it still says why (%s)" % where, "zero" in p.message.text(),
            repr(p.message.text()))
    h.check("the preview is back at 0 (%s)" % where, near(h.solid_volume(), BOX),
            h.solid_volume())
    zero_steps = [o.Name for o in press_pulls() if o is not p.target]
    h.check("R5: no step was made (%s)" % where, not zero_steps, zero_steps)
    return p


def pp_zero_said_field():
    p = zero_still_said("the field")
    if p is not None:
        ui.type_into(p.field.widget, "5")


def pp_zero_enter_box():
    h.check("5 typed again: 40 x 30 x 15", near(h.solid_volume(), 1200.0 * 15), h.solid_volume())
    boxes = a.value_boxes()
    if h.check("the value box is there", len(boxes) == 1, len(boxes)):
        a.type_in_box(boxes[0], "0", enter=True)


pp_zero_enter_box.wait_ms = 1000


def pp_zero_said_box():
    zero_still_said("the value box")


def pp_drag_down():
    p = ppanel()
    s["pp_samples"] = samples = []
    start = h.screen_point(a.head_point(p.dragger))
    end = QtCore.QPoint(start.x(), start.y() + 70)

    def sample(index):
        q = ppanel()
        if q is None:
            return
        boxes = a.value_boxes()
        samples.append(
            {
                "i": index,
                "active": bool(q.dragger and q.dragger.dragger.isActive.getValue()),
                "volume": round(h.solid_volume(), 3),
                "field": q.field.value(),
                "red": len(a.cut_nodes()),
                "box": boxes[0].text() if boxes else None,
                "field_text": q.field.widget.text(),
            }
        )

    s["pp_drag"] = drag = a.HeldDrag(start, end, moves=40, every_ms=20, hold_ms=300, sample=sample)
    drag.run()


pp_drag_down.wait_ms = 40 * 20 + 300 + 1200


def pp_dragged():
    drag, samples = s.get("pp_drag"), s.get("pp_samples", [])
    h.check("the held drag ran", drag is not None and drag.done, drag and drag.error)
    held = [x for x in samples if x["active"]]
    h.check("the Press Pull arrow was grabbed", len(held) > 10, len(held))
    volumes = sorted({x["volume"] for x in held if x["i"] > 0})
    h.check("R2: the part follows while the button is still down", len(volumes) >= 3,
            volumes[:20])
    h.check("R7: material pushed away shows red during the drag",
            any(x["red"] == 1 and x["field"] < 0 for x in held), held[-3:])
    h.check("R3: the box shows the dialog's value during the drag",
            bool(held) and all(x["box"] == x["field_text"] for x in held),
            [(x["box"], x["field_text"]) for x in held if x["box"] != x["field_text"]][:5])
    p = ppanel()
    h.check("pushed in", p is not None and p.field.value() < -0.5, p and p.field.value())
    ui.type_into(p.field.widget, "-3")


def pp_red_slab():
    h.check("pushed 3 in: 40 x 30 x 7", near(h.solid_volume(), 1200.0 * 7), h.solid_volume())
    nodes = a.cut_nodes()
    h.check("R7: one red node for the material pushed away", len(nodes) == 1, len(nodes))
    if nodes:
        box = a.node_box(nodes[0])
        h.check("R7: it is the top 3 mm of the box", box_near(box, (0, 0, 7), (40, 30, 10)), box)
    h.check("R7: the Press Pull keeps its own colour", not_red(ppanel().target))
    h.shot("4-pp-red")


def pp_type_in_box():
    boxes = a.value_boxes()
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    a.type_in_box(boxes[0], "5", enter=True)


pp_type_in_box.wait_ms = 1200


def pp_done():
    h.check("R3: Enter in the box finishes Press Pull", ppanel() is None and
            not Gui.Control.activeDialog())
    h.check("R3: 5 typed in the box: 40 x 30 x 15", near(h.solid_volume(), 1200.0 * 15),
            h.solid_volume())
    steps = press_pulls()
    h.check("one Press Pull step of 5 mm", len(steps) == 1 and near(steps[0].Distance.Value, 5.0),
            [(o.Name, o.Distance.Value) for o in steps])
    h.check("no value box left", not a.value_boxes(visible_only=False))
    h.check("R7: no red left", not a.cut_nodes(), len(a.cut_nodes()))


h.run(
    "extrude_feel_cut",
    bs.box_steps("FeelCut")
    + [
        sketch_on_top,
        click_top,
        draw_square,
        finish_sketch,
        press_e,
        opened,
        type_minus_6,
        cut_red,
        type_5,
        join_not_red,
        drag_into_part,
        dragged_red,
        regrab_in_pocket,
        regrabbed,
        cancel,
        cancelled,
        e_again,
        ok_cut,
        ok_cut_red,
        after_ok,
        undo,
        e_after_undo,
        type_minus_6_again,
        ctrl_z,
        undone_dialog,
        press_q,
        click_top_face,
        pp_opened,
        pp_ok_at_zero,
        pp_type_5,
        pp_zero_enter_field,
        pp_zero_said_field,
        pp_zero_enter_box,
        pp_zero_said_box,
        pp_drag_down,
        pp_dragged,
        pp_red_slab,
        pp_type_in_box,
        pp_done,
    ],
)
