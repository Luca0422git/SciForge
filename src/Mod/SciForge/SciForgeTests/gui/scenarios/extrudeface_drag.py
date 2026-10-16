# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dragging the Extrude arrow over a face snaps to it (Fusion: "drag the arrow and click on the
face to snap to it"; parity/extrude-presspull.md). The arrow is dragged with the mouse button
held, moving on every 20 ms like a hand; looks are taken while the button is still down.
Only real input.

A plate 50 x 30 x 10 (x 10..60) with a tower 10 x 30 up to z 40 at its left; a 10 x 10
square sketched on the plate (x 30..40, y 10..20).

D1  E, drag the arrow and hold it over the tower's top: while the button is down the
    distance is 30 exactly, the dialog says "Up to the face: 30 mm" and the face is marked;
    let go: 30 stays, the arrow sits at 30, the mark goes.
D2  A plain click on the arrow (no drag) snaps to nothing: 30 stays.
D3  Drag the arrow up over empty space: no snap (a plain drag, no mark), not 30.
D4  Drag it onto the plate's bottom front corner (60, 0, 0): -10 ("Up to the point"), a cut
    by itself. Type 30 again.
D5  Two Sides: drag side two's arrow onto the same corner: side two 10. OK: lengths 30 and
    10, +3000 (side two runs inside the plate).
D6  E on a new square (x 45..55, y 10..20), drag over the tower's top and Esc while the
    dialog is open: nothing is made, no mark is left.

Hand-derived: plate 15000 + tower 12000 = 27000; the boss 100 mm^2 x 30 = 3000.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import extrudeface_steps as x
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
PARTS = 27000.0
TOWER_TOP = V(5, 20, 40)
CORNER = V(60, 0, 0)


def held_drag(key, handle_key, end_point, samples_key):
    """A drag of the arrow `handle_key` from its head to the screen point of `end_point`
    (a QPoint when given as one), looks taken all along."""
    p = x.panel()
    handle = p.draggers.get(handle_key) if p is not None else None
    if not h.check("%s an arrow to drag" % key, handle is not None, p and list(p.draggers)):
        return
    h.fit()
    start = h.screen_point(a.head_point(handle))
    end = end_point if isinstance(end_point, QtCore.QPoint) else h.screen_point(end_point)
    s[samples_key] = samples = []

    def sample(index):
        q = x.panel()
        if q is None:
            return
        field = q.distance if handle_key == "distance" else q.distance2
        samples.append(
            {
                "i": index,
                "held": bool(handle.dragger.isActive.getValue()),
                "value": field.value(),
                "info": q.info.text(),
                "marks": len(x.snap_marks()),
                "note": q.note,
                "message": q.message.text(),
                "pending": q._timer.isActive(),
            }
        )

    drag = s[key] = a.HeldDrag(start, end, moves=30, every_ms=20, hold_ms=300, sample=sample)
    drag.run()


def last_held(samples_key):
    held = [x_ for x_ in s.get(samples_key, []) if x_["held"]]
    return held[-1] if held else None


# -- D1 ---------------------------------------------------------------------------------------
def d1_opened():
    p = x.panel()
    h.check("D1 Extrude on the square", p is not None and len(p.profiles) == 1, p and p.profiles)


def d1_drag():
    held_drag("d1", "distance", TOWER_TOP, "d1_samples")


d1_drag.wait_ms = 30 * 20 + 300 + 1500


def d1_checks():
    drag = s.get("d1")
    h.check(
        "D1 the drag ran",
        drag is not None and drag.done and drag.pressed_on == "3D view",
        drag and (drag.error, drag.pressed_on),
    )
    held = last_held("d1_samples")
    h.check("D1 the arrow was held", held is not None, s.get("d1_samples", [])[:3])
    if held is not None:
        h.check("D1 held over the tower's top: 30 exactly", held["value"] == 30.0, held)
        h.check("D1 the dialog says so", held["info"] == "Up to the face: 30 mm", held)
        h.check("D1 the face is marked", held["marks"] == 1, held)
    early = [x_ for x_ in s.get("d1_samples", []) if x_["held"] and x_["value"] != 30.0]
    h.check(
        "D1 before reaching the face the arrow drags freely",
        bool(early),
        [x_["value"] for x_ in s.get("d1_samples", [])][:10],
    )
    p = x.panel()
    if p is None:
        return
    h.check("D1 let go: 30 stays", p.distance.value() == 30.0, p.distance.value())
    h.check(
        "D1 the arrow sits at 30", x.near(p.dragger.distance(), 30.0, 1e-9), p.dragger.distance()
    )
    h.check("D1 the mark goes", not x.snap_marks(), len(x.snap_marks()))
    h.check("D1 the boss reaches the tower's top", x.near(x.total(), PARTS + 3000.0), x.total())
    h.shot("D1-snapped")


# -- D2: a plain click on the arrow ---------------------------------------------------------
def d2_click_arrow():
    p = x.panel()
    if p is None or p.dragger is None:
        return
    h.fit()
    h.click(a.head_point(p.dragger))


def d2_unchanged():
    p = x.panel()
    if p is None:
        return
    h.check(
        "D2 a click on the arrow changes nothing", p.distance.value() == 30.0, p.distance.value()
    )
    h.check("D2 no mark", not x.snap_marks(), len(x.snap_marks()))


# -- D3: a plain drag over empty space ------------------------------------------------------
def d3_drag():
    p = x.panel()
    if p is None or p.dragger is None:
        h.check("D3 the arrow", False)
        return
    h.fit()
    start = h.screen_point(a.head_point(p.dragger))
    held_drag("d3", "distance", QtCore.QPoint(start.x() + 4, max(start.y() - 70, 20)), "d3_samples")


d3_drag.wait_ms = 30 * 20 + 300 + 1500


def d3_checks():
    held = last_held("d3_samples")
    h.check("D3 the arrow was held", held is not None, s.get("d3_samples", [])[:3])
    if held is not None:
        h.check("D3 over empty space: no mark", held["marks"] == 0, held)
        h.check("D3 no face's words", "Up to" not in held["info"], held)
    p = x.panel()
    if p is None:
        return
    h.check("D3 a plain drag moves it on", p.distance.value() > 30.5, p.distance.value())
    h.check(
        "D3 two decimals, like any drag",
        p.distance.value() == round(p.distance.value(), 2),
        p.distance.value(),
    )


# -- D4: a corner -----------------------------------------------------------------------------
def d4_drag():
    held_drag("d4", "distance", CORNER, "d4_samples")


d4_drag.wait_ms = 30 * 20 + 300 + 2000


def d4_checks():
    held = last_held("d4_samples")
    h.check("D4 the arrow was held", held is not None, s.get("d4_samples", [])[:3])
    if held is not None:
        h.check("D4 held over the corner: -10", held["value"] == -10.0, held)
        h.check("D4 the dialog says the point", held["info"] == "Up to the point: -10 mm", held)
        h.check("D4 the point is marked", held["marks"] == 1, held)
    p = x.panel()
    if p is None:
        return
    h.check("D4 let go: -10", p.distance.value() == -10.0, p.distance.value())
    h.check("D4 a cut by itself", p.operation.currentData() == "cut", p.operation.currentText())
    h.check("D4 cut through the plate", x.near(x.total(), PARTS - 1000.0), x.total())
    ui.type_into(p.distance.widget, "30")


# -- D5: Two Sides, side two's arrow ---------------------------------------------------------
def d5_two_sides():
    p = x.panel()
    if p is None:
        return
    h.check(
        "D5 typed 30 is a join again",
        p.operation.currentData() == "join" and x.near(x.total(), PARTS + 3000.0),
        (p.operation.currentText(), x.total()),
    )
    h.check("D5 Two Sides", ui.choose(p.direction, "Two Sides"))


def d5_drag():
    held_drag("d5", "distance2", CORNER, "d5_samples")


d5_drag.wait_ms = 30 * 20 + 300 + 2000


def d5_checks():
    held = last_held("d5_samples")
    h.check("D5 side two's arrow was held", held is not None, s.get("d5_samples", [])[:3])
    if held is not None:
        h.check("D5 held over the corner: side two 10", held["value"] == 10.0, held)
        h.check(
            "D5 the dialog says side two", held["info"] == "Side Two up to the point: 10 mm", held
        )
    p = x.panel()
    if p is None:
        return
    h.check("D5 let go: side two 10", p.distance2.value() == 10.0, p.distance2.value())
    h.check("D5 side one still 30", p.distance.value() == 30.0, p.distance.value())
    h.task_button("OK")


def d5_done():
    h.check("D5 closed", x.panel() is None and not Gui.Control.activeDialog())
    feature = x.last_extrude()
    h.check(
        "D5 lengths 30 and 10",
        x.length(feature) == 30.0 and x.length(feature, "Length2") == 10.0,
        (x.length(feature), x.length(feature, "Length2")),
    )
    h.check(
        "D5 +3000 (side two runs inside the plate)", x.near(x.total(), PARTS + 3000.0), x.total()
    )
    h.check("D5 no mark left", not x.snap_marks(), len(x.snap_marks()))


# -- D6: Esc --------------------------------------------------------------------------------
def d6_drag():
    p = x.panel()
    h.check(
        "D6 Extrude on the new square", p is not None and len(p.profiles) == 1, p and p.profiles
    )
    held_drag("d6", "distance", TOWER_TOP, "d6_samples")


d6_drag.wait_ms = 30 * 20 + 300 + 1500


def d6_escape():
    p = x.panel()
    h.check(
        "D6 snapped to 30", p is not None and p.distance.value() == 30.0, p and p.distance.value()
    )
    x.escape()


def d6_done():
    h.check("D6 Esc closed it", x.panel() is None and not Gui.Control.activeDialog())
    h.check("D6 nothing made", x.near(x.total(), PARTS + 3000.0), x.total())
    h.check("D6 no mark left", not x.snap_marks(), len(x.snap_marks()))
    h.shot("D6-end")


h.run(
    "extrudeface_drag",
    [
        x.new_design("ExtrudeFaceDrag"),
        *x.xy_block("plate", (10, 0, 60, 30), 10, 15000.0),
        *x.xy_block("tower", (0, 0, 10, 30), 40, PARTS),
        *x.face_sketch("square", V(50, 26, 10), (30, 10, 40, 20)),
        x.press_e("d1_e"),
        d1_opened,
        d1_drag,
        d1_checks,
        d2_click_arrow,
        d2_unchanged,
        d3_drag,
        d3_checks,
        d4_drag,
        d4_checks,
        d5_two_sides,
        d5_drag,
        d5_checks,
        d5_done,
        *x.face_sketch("square2", V(50, 26, 10), (45, 10, 55, 20)),
        x.press_e("d6_e"),
        d6_drag,
        d6_escape,
        d6_done,
    ],
)
