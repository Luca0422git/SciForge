# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Extrude dialog feels like Fusion's (Luca's requests R2, R3, R5, R6), only real input.

R5  E on a sketch just finished starts at 0: no shape pops out, the arrow is there to
    drag (also at 0), the dialog says what to do. OK and Enter at 0 keep the dialog
    open and make nothing. Typing 0 again removes the preview (none is left standing).
R3  a value box sits next to the arrow and shows exactly the dialog's distance (with
    units), also while the arrow is dragged and for Symmetric's whole length; it never
    takes the keyboard by itself. Click it, type 15, Tab: 15. Type "width*2" (a
    parameter), Enter: the extrude follows the parameter and is done (Enter = OK, like
    the dialog's field). No box is left over the view afterwards.
R2  the arrow dragged with the mouse button held down, moving on every 20 ms: the part
    grows while the button is still down, not only once the mouse stops.
R6  the sketch stays visible after E, while dragging and with the preview shown; OK
    hides it, Undo shows it again, Redo hides it. E pressed inside an open sketch keeps
    that sketch visible too, and Cancel leaves it visible.
Two Sides: side two starts at 0, the preview keeps side one; OK says side two needs a
    distance; typing one for side two adds it.

Hand-derived: 40 x 30 rectangle = 1200 mm^2 per mm of height.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
AREA = 1200.0


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def extrudes():
    from sciforge import extrude

    return [o for o in App.ActiveDocument.Objects if extrude.is_extrude(o)]


def sketch_shown(key="sketch"):
    try:
        return bool(s[key].ViewObject.Visibility)
    except Exception:
        return None


def zero_hint():
    from sciforge import extrude_ui

    return extrude_ui.ZERO_HINT


# -- a sketch -----------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ExtrudeFeel")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, 0, 40, 30)
        s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def press_e():
    h.check("left the sketch", h.in_sketch() is None)
    h.check("the sketch is visible after Finish Sketch", sketch_shown() is True)
    h.fit()
    h.press("e")


# -- R5 / R3 / R6 at the start --------------------------------------------------------------
def opened_at_zero():
    p = panel()
    if not h.check("E opens the Extrude dialog", p is not None):
        return
    h.check("the sketch's one area is picked", len(p.profiles) == 1, p.profiles)
    h.check("R5: the distance starts at 0", near(p.distance.value(), 0.0), p.distance.value())
    h.check("R5: nothing pops out (no preview at 0)", p.target is None, p.target)
    h.check("R5: no solid yet", h.solid_volume() < 1e-6, h.solid_volume())
    h.check("R5: the arrow is there to drag at 0", "distance" in p.draggers, list(p.draggers))
    h.check("R5: the dialog says what to do", p.info.text() == zero_hint(), p.info.text())
    h.check("R5: no warning at 0", p.message.text() == "", p.message.text())
    h.check("R6: the sketch stays visible after E", sketch_shown() is True)
    boxes = a.value_boxes(arrows_only=True)
    h.check("R3: one value box next to the arrow", len(boxes) == 1, len(boxes))
    if boxes and p.dragger is not None:
        box = boxes[0]
        h.check(
            "R3: the box shows the dialog's distance",
            box.text() == p.distance.widget.text(),
            (box.text(), p.distance.widget.text()),
        )
        h.check("R3: with units", box.text().endswith("mm"), box.text())
        ok, detail = a.box_near(box, p.dragger)
        h.check("R3: the box sits at the arrow's tip", ok, detail)
        h.check("R3: the box does not take the keyboard", not box.hasFocus(), a.focus_name())
    h.shot("1-start-at-zero")


def ok_at_zero():
    h.task_button("OK")


def still_open_after_ok():
    p = panel()
    h.check("R5: OK at 0 keeps the dialog open", p is not None and Gui.Control.activeDialog())
    if p is not None:
        h.check("R5: it says why", "zero" in p.message.text(), p.message.text())
    h.check("R5: OK at 0 makes nothing", not extrudes(), [o.Name for o in extrudes()])
    h.check("R5: still no solid", h.solid_volume() < 1e-6, h.solid_volume())


def enter_at_zero():
    h.press(QtCore.Qt.Key_Return)  # over the 3D view: Fusion's Enter = OK


def still_open_after_enter():
    h.check("R5: Enter at 0 keeps the dialog open", panel() is not None)
    h.check("R5: Enter at 0 makes nothing", not extrudes(), [o.Name for o in extrudes()])


# -- R2 / R3: a drag with the button held -----------------------------------------------------
def live_drag():
    p = panel()
    if p is None or p.dragger is None:
        h.check("an arrow to drag", False)
        return
    s["samples"] = samples = []
    start = h.screen_point(a.head_point(p.dragger))
    end = QtCore.QPoint(start.x(), start.y() - 110)

    def sample(index):
        q = panel()
        if q is None:
            return
        boxes = a.value_boxes(arrows_only=True)
        box = boxes[0] if boxes else None
        samples.append(
            {
                "i": index,
                "active": bool(q.dragger and q.dragger.dragger.isActive.getValue()),
                "volume": round(h.solid_volume(), 3),
                "field": q.distance.value(),
                "field_text": q.distance.widget.text(),
                "box_text": box.text() if box else None,
                "box_y": box.geometry().center().y() if box else None,
                "sketch": sketch_shown(),
            }
        )

    drag = s["drag"] = a.HeldDrag(start, end, moves=50, every_ms=20, hold_ms=300, sample=sample)
    drag.run()


live_drag.wait_ms = 50 * 20 + 300 + 1200


def live_checks():
    drag, samples = s.get("drag"), s.get("samples", [])
    h.check("the held drag ran to the end", drag is not None and drag.done, drag and drag.error)
    held = [x for x in samples if x["active"]]
    h.check("R2: the arrow was grabbed (button held)", len(held) > 10, len(held))
    moving = [x for x in held if x["i"] > 0]
    volumes = sorted({x["volume"] for x in moving if x["volume"] > 0})
    h.check(
        "R2: the part grows while the button is still down",
        len(volumes) >= 3,
        "distinct volumes while moving: %s" % volumes[:20],
    )
    if moving:
        last = moving[-1]
        h.check(
            "R2: the preview keeps up with the arrow while moving",
            last["volume"] > 0 and abs(last["volume"] / AREA - last["field"]) < 0.35 * last["field"],
            last,
        )
    h.check(
        "R3: the box shows the dialog's value all along the drag",
        bool(held) and all(x["box_text"] == x["field_text"] for x in held),
        [(x["box_text"], x["field_text"]) for x in held if x["box_text"] != x["field_text"]][:5],
    )
    ys = [x["box_y"] for x in held if x["box_y"] is not None]
    h.check("R3: the box moves up with the arrow", ys and ys[-1] < ys[0] - 20, ys[:3] + ys[-3:])
    h.check(
        "R6: the sketch stays visible during the drag",
        bool(samples) and all(x["sketch"] for x in samples),
        [x["sketch"] for x in samples][:5],
    )
    p = panel()
    if p is None:
        return
    value = p.distance.value()
    h.check("the drag pulled it out", value > 2.0, value)
    h.check(
        "after release the part is the dialog's distance",
        near(h.solid_volume(), AREA * value, 1e-6),
        (h.solid_volume(), value),
    )
    boxes = a.value_boxes(arrows_only=True)
    h.check(
        "R3: the box still shows the dialog's value",
        boxes and boxes[0].text() == p.distance.widget.text(),
        boxes and (boxes[0].text(), p.distance.widget.text()),
    )
    h.check("R6: the sketch is visible with the preview shown", sketch_shown() is True)
    h.check("R3: the box did not take the keyboard", a.focus_name() != a.BOX_NAME, a.focus_name())
    h.shot("2-dragged")


def type_zero():
    ui.type_into(panel().distance.widget, "0")


def zero_again():
    p = panel()
    h.check("R5: typing 0 removes the preview", p.target is None and h.solid_volume() < 1e-6,
            (p.target, h.solid_volume()))
    h.check("R5: the arrow stays at 0", "distance" in p.draggers, list(p.draggers))
    h.check("R5: the hint is back, no warning", p.info.text() == zero_hint() and
            p.message.text() == "", (p.info.text(), p.message.text()))
    boxes = a.value_boxes(arrows_only=True)
    h.check("R3: the box shows 0", boxes and boxes[0].text() == p.distance.widget.text(),
            boxes and boxes[0].text())


# -- Symmetric whole length: the box shows the total ---------------------------------------------
def symmetric():
    p = panel()
    h.check("Direction: Symmetric", bs.choose(p.direction, "Symmetric"))


def whole_length():
    p = panel()
    h.check("Measurement: Whole Length", bs.choose(p.measurement, "Whole Length"))


def type_20():
    ui.type_into(panel().distance.widget, "20")


def symmetric_shown():
    p = panel()
    h.check("symmetric 20 whole: 40 x 30 x 20", near(h.solid_volume(), AREA * 20), h.solid_volume())
    h.check("the arrow sits at half (10)", p.dragger and near(p.dragger.distance(), 10.0),
            p.dragger and p.dragger.distance())
    boxes = a.value_boxes(arrows_only=True)
    h.check("R3: the box shows the whole length (the dialog's 20)",
            boxes and boxes[0].text() == p.distance.widget.text() and "20" in boxes[0].text(),
            boxes and boxes[0].text())


# -- Two Sides: side two starts at 0 -------------------------------------------------------------
def two_sides():
    h.check("Direction: Two Sides", bs.choose(panel().direction, "Two Sides"))


def two_sides_shown():
    p = panel()
    h.check("side two starts at 0", near(p.distance2.value(), 0.0), p.distance2.value())
    h.check("side one alone is shown meanwhile (20 up)", near(h.solid_volume(), AREA * 20),
            h.solid_volume())
    h.check("side two's arrow is there", "distance2" in p.draggers, list(p.draggers))
    h.check("two value boxes (one per arrow)", len(a.value_boxes(arrows_only=True)) == 2, len(a.value_boxes(arrows_only=True)))
    h.task_button("OK")


def two_sides_ok_refused():
    p = panel()
    h.check("OK with side two at 0 keeps the dialog open", p is not None)
    if p is not None:
        h.check("it says side two needs a distance", "side two" in p.message.text(),
                p.message.text())
        ui.type_into(p.distance2.widget, "5")


def two_sides_built():
    h.check("side two typed 5: 40 x 30 x 25", near(h.solid_volume(), AREA * 25), h.solid_volume())
    h.check("still no step made", not [o for o in extrudes() if o is not panel().target])


def one_side_again():
    h.check("Direction: One Side", bs.choose(panel().direction, "One Side"))


# -- R3: typing in the box ------------------------------------------------------------------------
def box_type_15():
    p = panel()
    h.check("one side 20: 24000", near(h.solid_volume(), AREA * 20), h.solid_volume())
    boxes = a.value_boxes(arrows_only=True)
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    a.type_in_box(boxes[0], "15", enter=False)
    h.check("R3: clicking the box gives it the keyboard", boxes[0].hasFocus(), a.focus_name())
    bs.click_widget(p.distance.widget)  # a click elsewhere keeps what was typed in the box


def typed_15():
    p = panel()
    h.check("R3: 15 typed in the box is the distance", near(p.distance.value(), 15.0),
            p.distance.value())
    h.check("R3: the part follows: 18000", near(h.solid_volume(), AREA * 15), h.solid_volume())
    h.check("the dialog is still open (no Enter yet)", panel() is not None)


def box_type_formula():
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "width", "mm", "12")  # in Change Parameters
    boxes = a.value_boxes(arrows_only=True)
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    s["feature"] = panel().target
    a.type_in_box(boxes[0], "width*2", enter=True)


box_type_formula.wait_ms = 1200


def formula_done():
    h.check("R3: Enter in the box finishes the extrude (OK)", panel() is None and
            not Gui.Control.activeDialog())
    h.check("R3: width*2 = 24: 40 x 30 x 24", near(h.solid_volume(), AREA * 24), h.solid_volume())
    feats = extrudes()
    h.check("one extrude", len(feats) == 1, [o.Name for o in feats])
    if feats:
        engine = dict(feats[0].ExpressionEngine)
        h.check("R3: the distance follows the parameter width",
                any("width" in v for v in engine.values()), engine)
    h.check("R3: no value box left over the view", not a.value_boxes(visible_only=False),
            len(a.value_boxes(visible_only=False)))
    h.check("R6: OK hides the sketch", sketch_shown() is False)
    h.shot("3-done")


def undo():
    h.check("Undo button", ui.quick_access("Undo"))


def undone():
    h.check("Undo removes the extrude", not extrudes() and h.solid_volume() < 1e-6,
            h.solid_volume())
    h.check("R6: Undo shows the sketch again", sketch_shown() is True)


def redo():
    h.check("Redo button", ui.quick_access("Redo"))


def redone():
    h.check("Redo brings the extrude back", near(h.solid_volume(), AREA * 24), h.solid_volume())
    h.check("R6: Redo hides the sketch again", sketch_shown() is False)
    s["top"] = h.body().Shape.BoundBox.ZMax
    h.fit()


# -- E inside an open sketch ------------------------------------------------------------------------
def sketch_on_top():
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 22, s["top"]))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is not None:
        x0, y0 = h.to_sketch(sk, V(10, 5, s["top"]))
        x1, y1 = h.to_sketch(sk, V(20, 15, s["top"]))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        s["square"] = sk
    s["volume"] = h.solid_volume()


def e_in_sketch():
    h.press("e")  # straight from the open sketch


def from_sketch_opened():
    p = panel()
    h.check("E in the sketch opens Extrude", p is not None and h.in_sketch() is None)
    if p is None:
        return
    h.check("R5: starts at 0 here too", near(p.distance.value(), 0.0) and p.target is None,
            (p.distance.value(), p.target))
    h.check("R6: the sketch E was pressed in stays visible", sketch_shown("square") is True)
    h.check("R3: the value box is there", len(a.value_boxes(arrows_only=True)) == 1, len(a.value_boxes(arrows_only=True)))
    ui.type_into(p.distance.widget, "5")


def from_sketch_preview():
    h.check("5 up: the boss shows", near(h.solid_volume(), s["volume"] + 500.0), h.solid_volume())
    h.check("R6: still visible with the preview", sketch_shown("square") is True)
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closes the dialog", panel() is None and not Gui.Control.activeDialog())
    h.check("Cancel leaves the part as it was", near(h.solid_volume(), s["volume"]),
            h.solid_volume())
    h.check("R6: Cancel leaves the sketch visible", sketch_shown("square") is True)
    h.check("no value box left after Cancel", not a.value_boxes(visible_only=False))


h.run(
    "extrude_feel",
    [
        new_design,
        pick_xy,
        draw,
        finish_sketch,
        press_e,
        opened_at_zero,
        ok_at_zero,
        still_open_after_ok,
        enter_at_zero,
        still_open_after_enter,
        live_drag,
        live_checks,
        type_zero,
        zero_again,
        symmetric,
        whole_length,
        type_20,
        symmetric_shown,
        two_sides,
        two_sides_shown,
        two_sides_ok_refused,
        two_sides_built,
        one_side_again,
        box_type_15,
        typed_15,
        box_type_formula,
        formula_done,
        undo,
        undone,
        redo,
        redone,
        sketch_on_top,
        click_top,
        draw_square,
        e_in_sketch,
        from_sketch_opened,
        from_sketch_preview,
        cancelled,
    ],
)
