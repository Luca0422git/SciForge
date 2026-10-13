# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull: what an independent review of tonight's Extrude work found
(start at 0, the value box next to the arrow, the red cut, Q in a sketch). Real input.

Box 40 x 30 x 10, a 10 x 10 square sketched on its top face.
R3  E with nothing selected takes the square (the only area of the sketch just finished):
    its arrows and value box show at 0. Click the square: it is dropped, and the arrows and
    the box go with it.
R2  Click the square again, type -5: a cut, in red. Click the box, type 0, Enter: Extrude
    stays open and says why, the preview is gone and so is its red.
R4  Start: Offset with the distance still at 0: the two arrows sit on one spot; their two
    value boxes do not cover each other. The same for Two Sides with both sides at 0.
R5  One Side, -5. Click the box, type 30 (no Enter), click the top face beside the square:
    30 is taken, and that click is not a pick (the face is not added as a profile).
R1  Create Sketch on the top face, Q with nothing picked in it: Press Pull opens. Esc: the
    sketch is still shown and the undo list is as before. Again: Q, the top face, 2, OK:
    Press Pull is an undo step of its own; one Undo takes it back and nothing else.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
BOX = 12000.0
# Inside the square on the top face, left of its middle: at distance 0 the arrow stands on the
# middle (a click there grabs the arrow), and the value box sits to its right.
SQUARE = V(11.5, 18, 10)
BESIDE = V(33, 24, 10)  # the top face, away from the square
s = {}


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


def overlap(b1, b2):
    return b1.geometry().intersects(b2.geometry())


# -- the box and the square on top ----------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ExtrudeReview")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_box():
    sk = h.in_sketch()
    if h.check("sketch open on XY", sk is not None):
        h.draw_rectangle(sk, 0, 0, 40, 30)
    h.ribbon("Finish Sketch")


def extrude_box():
    h.fit()
    h.press("e")
    a.type_distance("10")


def box_ok():
    h.task_button("OK")


def top_sketch():
    h.check("box 40 x 30 x 10", near(h.solid_volume(), BOX), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def pick_top():
    h.click(V(30, 20, 10))


def draw_square():
    sk = h.in_sketch()
    if h.check("sketch open on the top face", sk is not None):
        x0, y0 = h.to_sketch(sk, V(10, 10, 10))
        x1, y1 = h.to_sketch(sk, V(20, 20, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        s["square"] = sk
    h.ribbon("Finish Sketch")


# -- R3: the last profile dropped at 0 takes its arrows and box along ----------------------------
def e_nothing_selected():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.fit()
    h.press("e")


def click_square():
    p = xpanel()
    # The square is the only area of the sketch just finished: E takes it by itself.
    h.check("E takes the new sketch's only area", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.check("its arrows show at 0", p is not None and bool(p.draggers), p and sorted(p.draggers))
    h.check("its value box shows", len(a.value_boxes()) == 1, len(a.value_boxes()))
    h.click(SQUARE)


def square_dropped():
    p = xpanel()
    h.check("clicking it drops it", p is not None and not p.profiles, p and p.profiles)
    h.check("the arrows went with it", p is not None and not p.draggers, p and sorted(p.draggers))
    h.check("so did the value box", not a.value_boxes(), len(a.value_boxes()))
    h.shot("R3-dropped")
    h.click(SQUARE)


# -- R2: 0 + Enter after a cut leaves no red -------------------------------------------------------
def cut_5():
    p = xpanel()
    h.check("picked again", p is not None and len(p.profiles) == 1, p and p.profiles)
    a.give_distance("-5")


def cut_shown():
    p = xpanel()
    op = p.operation.currentText() if p is not None else None
    h.check("into the part: Cut", op == "Cut", op)
    h.check("the cut shows in red", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.check("cut preview: box less 10 x 10 x 5", near(h.solid_volume(), BOX - 500.0), h.solid_volume())
    boxes = a.value_boxes()
    if h.check("the value box is there", len(boxes) == 1, len(boxes)):
        a.type_in_box(boxes[0], "0", enter=True)


cut_shown.wait_ms = 1200


def zero_refused():
    p = xpanel()
    h.check("0 + Enter keeps Extrude open", p is not None)
    h.check("and says why", p is not None and "zero" in p.message.text(), p and p.message.text())
    h.check("no red left over the part", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("the part is whole again", near(h.solid_volume(), BOX), h.solid_volume())
    h.shot("R2-zero")
    if p is not None:
        h.check("Start: Offset", ui.choose(p.start, "Offset"))


# -- R4: two arrows on one spot keep their boxes apart -------------------------------------------
def offset_boxes():
    p = xpanel()
    h.check(
        "offset and distance arrows",
        p is not None and {"offset", "distance"} <= set(p.draggers),
        p and sorted(p.draggers),
    )
    boxes = a.value_boxes()
    h.check("two value boxes", len(boxes) == 2, len(boxes))
    if len(boxes) == 2:
        h.check(
            "at distance 0 the two boxes do not cover each other",
            not overlap(boxes[0], boxes[1]),
            [b.geometry().getRect() for b in boxes],
        )
    h.shot("R4-offset")
    if p is not None:
        h.check("Start: Profile Plane", ui.choose(p.start, "Profile Plane"))
        h.check("Two Sides", ui.choose(p.direction, "Two Sides"))


def two_sides_boxes():
    p = xpanel()
    h.check(
        "two distance arrows",
        p is not None and {"distance", "distance2"} <= set(p.draggers),
        p and sorted(p.draggers),
    )
    boxes = a.value_boxes()
    h.check("two value boxes", len(boxes) == 2, len(boxes))
    if len(boxes) == 2:
        h.check(
            "both sides at 0: the two boxes do not cover each other",
            not overlap(boxes[0], boxes[1]),
            [b.geometry().getRect() for b in boxes],
        )
    h.shot("R4-two-sides")
    if p is not None:
        h.check("One Side", ui.choose(p.direction, "One Side"))
        a.give_distance("-5")


# -- R5: the click that leaves the box is not a pick ---------------------------------------------
def type_30():
    p = xpanel()
    h.check("one profile before", p is not None and len(p.profiles) == 1, p and p.profiles)
    boxes = a.value_boxes()
    if h.check("the value box is there", len(boxes) == 1, len(boxes)):
        a.type_in_box(boxes[0], "30", enter=False)
        h.check("the box has the keyboard", boxes[0].hasFocus(), a.focus_name())
    h.click(BESIDE)


type_30.wait_ms = 1200


def click_was_not_a_pick():
    p = xpanel()
    h.check("leaving the box took 30", p is not None and near(abs(p.distance.value()), 30.0), p and p.distance.value())
    h.check(
        "the click that left the box added no profile",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    )
    h.check("and no complaint about it", p is not None and "belongs" not in p.message.text(), p and p.message.text())
    h.shot("R5-left-box")
    h.task_button("Cancel")


# -- R1: Q in a sketch with nothing picked, then Esc ----------------------------------------------
def q_sketch():
    h.check("Cancel: the part as it was", near(h.solid_volume(), BOX), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


def q_pick_top():
    h.click(BESIDE)


def q_in_sketch():
    sk = h.in_sketch()
    h.check("a sketch open on the top face", sk is not None)
    s["q_sketch"] = sk
    s["undo_before"] = len(App.ActiveDocument.UndoNames)
    h.press("q")


def q_opened():
    h.check("the sketch closed", h.in_sketch() is None)
    h.check("Q opened Press Pull", ppanel() is not None)
    s["undo_open"] = list(App.ActiveDocument.UndoNames)
    h.press(QtCore.Qt.Key_Escape)


def q_cancelled():
    sk = s.get("q_sketch")
    h.check("Esc closed Press Pull", ppanel() is None and not Gui.Control.activeDialog())
    h.check(
        "the sketch is still there and shown",
        sk is not None and App.ActiveDocument.getObject(sk.Name) is not None and sk.ViewObject.Visibility,
    )
    names = list(App.ActiveDocument.UndoNames)
    h.check("Esc changed nothing in the undo list", names == s.get("undo_open"), (s.get("undo_open"), names))
    h.shot("R1-q-esc")
    h.fit()
    h.ribbon("Create Sketch")


def q2_pick_top():
    h.click(BESIDE)


def q2_in_sketch():
    h.check("another sketch open on the top face", h.in_sketch() is not None)
    h.press("q")


def q2_pull_face():
    h.check("Q opened Press Pull", ppanel() is not None)
    h.click(BESIDE)


def q2_type():
    p = ppanel()
    h.check("Press Pull took the top face", p is not None and len(p.names) == 1, p and p.names)
    if p is not None:
        ui.type_into(p.field.widget, "2")


def q2_ok():
    h.check("pulled up 2: 40 x 30 x 12", near(h.solid_volume(), BOX + 2400.0), h.solid_volume())
    h.task_button("OK")


def q2_undo_steps():
    names = list(App.ActiveDocument.UndoNames)
    h.check("Press Pull is an undo step of its own", names[:1] == ["Press Pull"], names)
    from SciForgeTests.gui import dialog_input

    h.check("Undo button", dialog_input.quick_access("Undo"))


def q2_undone():
    h.check("one Undo takes the Press Pull back", near(h.solid_volume(), BOX), h.solid_volume())
    sketches = [o for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"]
    h.check("and nothing of the sketch: all 4 sketches still there", len(sketches) == 4, len(sketches))


h.run(
    "extrude_review_fixes",
    [
        new_design,
        pick_xy,
        draw_box,
        extrude_box,
        box_ok,
        top_sketch,
        pick_top,
        draw_square,
        e_nothing_selected,
        click_square,
        square_dropped,
        cut_5,
        cut_shown,
        zero_refused,
        offset_boxes,
        two_sides_boxes,
        type_30,
        click_was_not_a_pick,
        q_sketch,
        q_pick_top,
        q_in_sketch,
        q_opened,
        q_cancelled,
        q2_pick_top,
        q2_in_sketch,
        q2_pull_face,
        q2_type,
        q2_ok,
        q2_undo_steps,
        q2_undone,
    ],
)
