# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drag handles let go of the mouse when the button comes up, even when FreeCAD loses the
release. Luca: "sometimes when i click and drag arrows like when using the move tool or
when extruding, the arrow gets stuck on my cursor even after i release my mouse button".

Real input through the main window's QWindow, the path a hardware mouse takes
(drag_input.py). A slow part makes a preview recompute take about 0.7 s, like a heavy part.
The release gets lost four ways (sciforge/drag_guard.py); each case makes one happen:

  M1   Move: drag the X arrow 6 mm and let go at once, over the body. FreeCAD's selection
       keeps that release (it selects the face), so the arrow never hears of it.
  M2c  Move: drag the X arrow 30 mm, hold still until the moved body is under the mouse
       (it follows the arrow), let go.
  M4   Move: let go while the preview recomputes. FreeCAD's progress bar eats the release.
  M8   Move, Rotate about Z: drag the blue turn handle 40 degrees and let go over the body.
  H2b  Offset Plane: double-click the arrow at a person's pace with the part behind it.
       FreeCAD hands the second press to the scene only together with the release.
  H3   Offset Plane: let go of the arrow while the preview recomputes.
  P2   Press Pull: let go of the arrow (a Coin dragger) while the preview recomputes.
  E4   Extrude: the same with the distance arrow,
  E7   then click the arrow, type a new distance (the dialog makes new arrows) and drag
       again: it works, and the 3D view kept no pointer to the old arrow (FreeCAD used to
       crash on the next mouse move).

For each: within a few polls after the release the handle is not dragging, mouse moves
with no button down leave the value alone, and the handle's end-of-drag work ran (the
dialog holds the final value). Checks named "case ..." make sure the situation really
happened (the release was kept or eaten), so the scenario cannot pass without testing it.
A handle that stays stuck (no fix) is let go with a click on the background, like a person
would, so the next case starts clean.

Box 40 x 30 x 10 from the origin; the Move manipulator sits at its middle (20, 15, 5).
"""

import math
import time

import FreeCAD as App
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import drag_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as ins

V = App.Vector
X = V(1, 0, 0)
POLLS_MS = 450  # handles poll every 30 ms: "within a few polls"
SHOWN = 0.0051  # value boxes show two decimals
st = {}


def screen(point):
    return h.screen_point(point)


def settle(ms=350):
    """Let the handles' timers and the preview catch up."""
    QtTest.QTest.qWait(ms)
    d.wait_until(lambda: not d.recomputing(), 6000)
    QtTest.QTest.qWait(120)


def note(text):
    print("[SciForge] drag_release_lost: %s" % text, flush=True)


# -- what every case checks ------------------------------------------------------------------------
def start_case(handle):
    """Before the gesture: watch the handle's on_release and what reaches the 3D view."""
    st["spy"] = d.ReleaseSpy()
    if handle is not None:
        st["spy"].attach(handle)
    st["mark"] = d.spy().mark()
    st["info"] = {}
    st["under"] = None
    st["hover"] = []
    st["took"] = None


def case_kept(name):
    """The release landed on the part: FreeCAD's selection kept it from the handle."""
    h.check(
        "case %s: let go over the part" % name,
        st.get("under") is not None,
        "under the mouse at the release: %s" % (st.get("under"),),
    )
    seen = d.spy().since(st["mark"])
    h.check(
        "case %s: FreeCAD's selection kept the release (the view's callbacks saw no UP)" % name,
        "DOWN" in seen["coin"] and "UP" not in seen["coin"],
        seen,
    )


def case_eaten(name):
    """The release came during the preview recompute and FreeCAD's progress bar ate it."""
    info = st.get("info") or {}
    h.check(
        "case %s: let go while the preview recomputed" % name,
        info.get("fired") and info.get("recomputing at release"),
        info,
    )
    h.check(
        "case %s: FreeCAD's progress bar ate the release (the 3D view never got it)" % name,
        info.get("fired") and not info.get("3D view got the release", True),
        info,
    )
    h.check(
        "case %s: Qt knows the button is up" % name,
        info.get("fired") and not info.get("Qt left button down right after", True),
        info,
    )


def let_go(dragging):
    """Right after the release (after the recompute that ate it, if one did): give the
    handle a few polls to find out the drag is over."""
    st["took"] = d.wait_until(lambda: not dragging(), POLLS_MS)
    st["held"] = d.held()


def judge(name, dragging, value, final):
    """After the release: the drag ended within a few polls, button-less moves leave the
    value alone, on_release ran and final() (ok, detail) holds."""
    took = st.get("took")
    h.check(
        "%s: the handle let go within %d ms of the release" % (name, POLLS_MS),
        took is not None,
        "still dragging; Qt left button down: %s" % st.get("held"),
    )
    h.check("%s: Qt says no button is down" % name, not d.held())
    before = value()
    d.moves(st["hover"])
    settle()
    after = value()
    h.check(
        "%s: mouse moves with no button down leave the value alone" % name,
        before is not None and before == after,
        "before the moves %s, after %s; dragging now %s" % (before, after, dragging()),
    )
    h.check(
        "%s: the handle's end-of-drag work ran (on_release)" % name,
        st["spy"].count() > 0,
        "on_release calls: %d" % st["spy"].count(),
    )
    ok, detail = final()
    h.check("%s: the dialog holds the final value" % name, ok, detail)
    note("%s: let go after %s ms" % (name, took))


def unstick(dragging):
    """No fix: the handle may still be stuck. A click on the empty background lets go of it
    (as a person would), so the next case starts clean."""

    def unstick():
        try:
            stuck = dragging()
        except Exception:
            stuck = False
        if stuck:
            d.click(QtCore.QPoint(25, h.gl_widget().height() - 25))
            settle()
            note("the handle was still stuck: clicked the background")

    return unstick


def cancel():
    h.task_button("Cancel")


# -- start -----------------------------------------------------------------------------------------
def harness_check():
    """Every other scenario drags with widget-level QTest presses (harness.drag): those must
    hold Qt's left button down, or drag_guard would end their drags at once."""
    down, up = d.widget_press_holds_button()
    h.check(
        "a widget-level QTest press holds Qt's left button until its release",
        down and not up,
        (down, up),
    )


def add_slow():
    d.add_slow_part()
    d.spy()
    h.check("slow part made", App.ActiveDocument.getObject("SlowPart") is not None)


# -- Move ------------------------------------------------------------------------------------------
def move_panel():
    from sciforge import move_ui

    p = s.panel()
    return p if isinstance(p, move_ui.MovePanel) else None


def triad():
    p = move_panel()
    return getattr(p, "triad", None) if p is not None else None


def m_dragging():
    t = triad()
    return bool(t is not None and t.dragging())


def m_dx():
    p = move_panel()
    return None if p is None else round(p.options["dx"], 6)


def m_final():
    p = move_panel()
    if p is None:
        return False, "no Move dialog"
    dx = p.options["dx"]
    shown = p.distance_fields[0].value()
    box = s.bodies()[0].Shape.BoundBox
    ok = p._drag_start is None and abs(shown - dx) <= SHOWN and abs(box.XMin - dx) < 1e-3
    return ok, "X Distance %s, field %s, drag start %s, body XMin %s" % (
        dx,
        shown,
        p._drag_start,
        box.XMin,
    )


def m_open():
    h.click_empty()
    h.fit()
    h.press("m")


def m_pick_body():
    h.click(V(20, 15, 10))


def m_ready():
    d.spy()
    h.check("Move: the manipulator is shown", triad() is not None, move_panel())


def x_arrow_spot():
    """A pixel on the X arrow's shaft (the arrow is drawn over the body's middle)."""
    t = triad()
    if t is None:
        return None
    for f in (0.75, 0.85, 0.65, 0.55, 0.45, 0.95):
        p3 = t.center + X * (f * t.size)
        pos = screen(p3)
        if h.covered(pos) or not d.inside_view(pos):
            continue
        if t.handle_at(d.coin_pos(pos)) == ("move", 0):
            return p3, pos
    return None


def m_reopen():
    return [unstick(m_dragging), cancel, m_open, m_pick_body, m_ready]


def m1_drag():
    found = x_arrow_spot()
    if not h.check("M1: a spot on the X arrow", found is not None):
        return
    start_case(triad())
    p3, pos = found
    end3 = p3 + X * 6
    end = screen(end3)
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, end, i / 8.0) for i in range(1, 9)])
    st["under"] = d.under(end)
    d.release(end)
    let_go(m_dragging)
    st["hover"] = [screen(end3 + X * k) for k in (6, 12, 18)]


def m1_after():
    case_kept("M1")
    judge("M1", m_dragging, m_dx, m_final)


def m2c_drag():
    found = x_arrow_spot()
    if not h.check("M2c: a spot on the X arrow", found is not None):
        return
    start_case(triad())
    p3, pos = found
    end3 = None
    for along in (30, 25, 20, 15, 12):
        q = screen(p3 + X * along)
        if d.inside_view(q, 40) and not h.covered(q):
            end3 = p3 + X * along
            break
    if not h.check("M2c: room to drag the arrow out", end3 is not None):
        return
    end = screen(end3)
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, end, i / 12.0) for i in range(1, 13)])
    # hold still like a person until the preview moved the body under the mouse
    QtTest.QTest.qWait(600)
    d.wait_until(lambda: d.under(end) is not None, 3000)
    st["under"] = d.under(end)
    d.release(end)
    let_go(m_dragging)
    st["hover"] = [screen(end3 + X * k) for k in (-6, -12, -18)]


def m2c_after():
    case_kept("M2c")
    judge("M2c", m_dragging, m_dx, m_final)


def m4_drag():
    found = x_arrow_spot()
    if not h.check("M4: a spot on the X arrow", found is not None):
        return
    start_case(triad())
    p3, pos = found
    end3 = p3 + X * 10
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, screen(end3), i / 8.0) for i in range(1, 9)])
    st["info"] = d.release_during_recompute(screen(end3 + X * 2))
    let_go(m_dragging)
    st["hover"] = [screen(end3 + X * k) for k in (6, 12, 18)]


def m4_after():
    case_eaten("M4")
    judge("M4", m_dragging, m_dx, m_final)


m4_drag.wait_ms = 400


def m8_rotate():
    p = move_panel()
    if h.check("Move dialog open", p is not None):
        b.choose(p.move_type, "Rotate")


def m8_z_axis():
    p = move_panel()
    picker = getattr(p, "axis_picker", None)
    if h.check("Move: origin axes drawn", picker is not None):
        h.fit()
        _feature, start, end = picker.axes["Z_Axis"]
        h.click(start + (end - start) * 0.85)


def turn_handle():
    p = move_panel()
    return getattr(p, "turn_handle", None) if p is not None else None


def m8_dragging():
    t = turn_handle()
    return bool(t is not None and t.dragging())


def m8_angle():
    p = move_panel()
    return None if p is None else round(p.options["angle"], 6)


def m8_final():
    p = move_panel()
    t = turn_handle()
    if p is None or t is None:
        return False, "no Move dialog or turn handle"
    angle = p.options["angle"]
    shown = p.angle.value()
    ok = p._drag_start is None and abs(shown - angle) <= SHOWN and abs(t.angle() - angle) < 1e-6
    return ok, "Angle %s, field %s, handle %s" % (angle, shown, t.angle())


def m8_ready():
    h.check("Move: the turn handle is shown", turn_handle() is not None, move_panel())


def m8_drag():
    t = turn_handle()
    if not h.check("M8: turn handle", t is not None):
        return
    start_case(t)
    a0 = t.angle()
    points = [screen(t.point_at(a0 + a)) for a in range(0, 45, 5)]
    if not h.check("M8: the ball is under the mouse", t.hit(d.coin_pos(points[0]))):
        return
    d.move(points[0])
    d.press(points[0])
    d.moves(points[1:])
    st["under"] = d.under(points[-1])
    d.release(points[-1])
    let_go(m8_dragging)
    st["hover"] = [screen(t.point_at(a0 + a)) for a in (60, 70, 80)]


def m8_after():
    case_kept("M8")
    judge("M8", m8_dragging, m8_angle, m8_final)


# -- Offset Plane (handles3d.LinearHandle) ---------------------------------------------------------
def offset_handle():
    p = ins.construct_panel()
    return getattr(p, "handle", None) if p is not None else None


def o_dragging():
    hd = offset_handle()
    return bool(hd is not None and hd.dragging())


def o_distance():
    p = ins.construct_panel()
    return None if p is None else round(p.values["distance"], 6)


def o_final():
    p = ins.construct_panel()
    hd = offset_handle()
    if p is None or hd is None:
        return False, "no Offset Plane dialog or arrow"
    value = p.values["distance"]
    shown = p.distance.value()
    ok = abs(value - round(hd.value(), 3)) < 1e-6 and abs(shown - value) < 1e-6
    return ok, "Distance %s, field %s, arrow %s" % (value, shown, hd.value())


def o_open():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def o_pick_top():
    h.click(V(20, 15, 10))


def o_ready():
    d.spy()
    h.check("Offset Plane: the arrow is shown", offset_handle() is not None, ins.construct_panel())


def offset_spot(want_face):
    """A pixel on the arrow; want_face: with the part behind it (True), or anything (None)."""
    hd = offset_handle()
    if hd is None:
        return None
    for f in (0.3, 0.45, 0.6, 0.75, 0.15, 0.9):
        p3 = hd.base_point() + hd.direction * (hd.size * f)
        pos = screen(p3)
        if h.covered(pos) or not d.inside_view(pos) or not hd.hit(d.coin_pos(pos)):
            continue
        if want_face is None or (d.under(pos) is not None) == want_face:
            return p3, pos
    return None


def o_lower():
    """The double-click case needs the part behind the arrow: set the distance low enough
    that the arrow is drawn in front of the top face."""
    if offset_spot(True) is not None:
        return
    p = ins.construct_panel()
    if p is not None and p.distance is not None:
        s.type_value(p.distance.widget, "2")
        note("Offset Plane distance set to 2 so the part is behind the arrow")


def h2b_double_click():
    found = offset_spot(True)
    if not h.check("H2b: a spot on the arrow with the part behind it", found is not None):
        return
    hd = offset_handle()
    start_case(hd)
    p3, pos = found
    st["under"] = d.under(pos)
    d.move(pos)
    d.click(pos)
    st["second"] = time.time()
    QtTest.QTest.qWait(150)  # a person's double-click
    d.click(pos)
    let_go(o_dragging)
    st["hover"] = [screen(p3 + hd.direction * k) for k in (4, 8, 12)]


def h2b_after():
    case_kept("H2b")
    judge("H2b", o_dragging, o_distance, o_final)
    late = [t for t in st["spy"].calls if t >= st.get("second", 0) + 0.12]
    h.check(
        "H2b: the second click's drag ended too (on_release after it)",
        bool(late),
        [round(t - st.get("second", 0), 3) for t in st["spy"].calls],
    )


def h3_drag():
    found = offset_spot(None)
    if not h.check("H3: a spot on the arrow", found is not None):
        return
    hd = offset_handle()
    start_case(hd)
    p3, pos = found
    end3 = p3 + hd.direction * 6
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, screen(end3), i / 8.0) for i in range(1, 9)])
    st["info"] = d.release_during_recompute(screen(end3 + hd.direction * 2))
    let_go(o_dragging)
    st["hover"] = [screen(end3 + hd.direction * k) for k in (4, 8, 12)]


h3_drag.wait_ms = 400


def h3_after():
    case_eaten("H3")
    judge("H3", o_dragging, o_distance, o_final)


# -- Coin arrows (taskui.ArrowDragger): Press Pull and Extrude -------------------------------------
def coin_arrow():
    """The distance arrow of the open Press Pull or Extrude dialog (not kept anywhere here:
    the dialog alone decides when it goes)."""
    from sciforge import presspull_ui

    pp = presspull_ui.PressPullPanel.last
    if pp is not None and not pp._closed:
        return pp.dragger
    p = b.active_panel()
    return getattr(p, "dragger", None) if p is not None else None


def a_dragging():
    a = coin_arrow()
    return bool(a is not None and a.dragger.isActive.getValue())


def a_distance():
    a = coin_arrow()
    return None if a is None else round(a.distance(), 6)


def arrow_frame(a):
    place = a.root.getChild(0)
    origin = V(*place.translation.getValue().getValue())
    axis = V(*place.rotation.getValue().multVec(a.coin.SbVec3f(1, 0, 0)).getValue())
    return origin, axis


def arrow_spot():
    """(3D point, pixel, axis) on the arrow where Coin picks the dragger."""
    a = coin_arrow()
    if a is None:
        return None
    origin, axis = arrow_frame(a)
    for f in (0.6, 0.8, 0.4, 0.9, 0.3, -0.3, -0.6):
        p3 = origin + axis * (a.distance() + a.size * f)
        pos = screen(p3)
        if h.covered(pos) or not d.inside_view(pos):
            continue
        if d.picks_node(pos, a.dragger):
            return p3, pos, axis
    return None


def arrow_release_during_recompute(name):
    found = arrow_spot()
    if not h.check("%s: a spot on the arrow" % name, found is not None):
        return
    start_case(coin_arrow())
    p3, pos, axis = found
    end3 = p3 + axis * 5
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, screen(end3), i / 8.0) for i in range(1, 9)])
    st["info"] = d.release_during_recompute(screen(end3 + axis * 2))
    let_go(a_dragging)
    st["hover"] = [screen(end3 + axis * k) for k in (4, 8, 12)]


def pp_final():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    a = coin_arrow()
    if p is None or p._closed or a is None:
        return False, "no Press Pull dialog or arrow"
    shown = p.field.value()
    return abs(shown - round(a.distance(), 2)) < 1e-6, "field %s, arrow %s" % (shown, a.distance())


def ex_final():
    p = b.active_panel()
    a = coin_arrow()
    if p is None or a is None:
        return False, "no Extrude dialog or arrow"
    shown = p.distance.value()
    ok = math.isfinite(a.distance()) and abs(shown - round(a.distance(), 2)) < 1e-6
    return ok, "field %s, arrow %s" % (shown, a.distance())


def p_open():
    h.click_empty()
    h.fit()
    h.press("q")


def p_pick_top():
    h.click(V(30, 22, 10))


def p_ready():
    d.spy()
    h.check("Press Pull: the arrow is shown", coin_arrow() is not None)


def p2_drag():
    arrow_release_during_recompute("P2")


p2_drag.wait_ms = 400


def p2_after():
    case_eaten("P2")
    judge("P2", a_dragging, a_distance, pp_final)


def e_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def e_click_top():
    h.click(V(30, 25, 10))


def e_draw():
    sk = h.in_sketch()
    if h.check("sketch on the top face", sk is not None):
        x0, y0 = h.to_sketch(sk, V(12, 8, 10))
        x1, y1 = h.to_sketch(sk, V(28, 22, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def e_extrude():
    h.fit()
    h.press("e")


def e_ready():
    d.spy()
    h.check("Extrude: the distance arrow is shown", coin_arrow() is not None, b.active_panel())


def e4_drag():
    arrow_release_during_recompute("E4")


e4_drag.wait_ms = 400


def e4_after():
    case_eaten("E4")
    judge("E4", a_dragging, a_distance, ex_final)


def e7_click():
    """A click on the arrow (a person checking it lets go)."""
    found = arrow_spot()
    if not h.check("E7: a spot on the arrow", found is not None):
        return
    _p3, pos, _axis = found
    d.move(pos)
    d.click(pos)
    settle()
    h.check("E7: a click on the arrow leaves it let go", not a_dragging(), d.held())


def e7_type():
    p = b.active_panel()
    a = coin_arrow()
    if a is not None:
        a.replaced_by_typing = True  # a mark only: no reference to it is kept here
    a = None
    if h.check("E7: Extrude dialog open", p is not None and p.distance is not None):
        s.type_value(p.distance.widget, "12")


def e7_new_arrows():
    settle()
    arrow = coin_arrow()
    h.check(
        "case E7: the dialog made new arrows",
        arrow is not None and not getattr(arrow, "replaced_by_typing", False),
    )
    arrow = None
    h.check(
        "E7: the 3D view holds no old arrow (no Coin grabber left)",
        d.grabber_is_none(),
        "a node still grabs the view's mouse events",
    )
    # mouse moves over the whole view with no button down: FreeCAD crashed here when the
    # view still pointed at the removed arrow
    widget = h.gl_widget()
    w, hh = widget.width(), widget.height()
    d.moves(
        [QtCore.QPoint(int(w * (0.2 + 0.06 * i)), int(hh * (0.3 + 0.04 * i))) for i in range(10)]
    )
    settle()
    h.check("E7: FreeCAD is still running after the mouse moves", App.ActiveDocument is not None)


def e7_drag():
    found = arrow_spot()
    if not h.check("E7: a spot on the new arrow", found is not None):
        return
    start_case(coin_arrow())
    st["before"] = a_distance()
    p3, pos, axis = found
    end = screen(p3 + axis * 6)
    d.move(pos)
    d.press(pos)
    d.moves([d.lerp(pos, end, i / 8.0) for i in range(1, 9)])
    d.release(end)
    let_go(a_dragging)
    st["hover"] = [screen(p3 + axis * (6 + k)) for k in (4, 8, 12)]


def e7_after():
    judge("E7 next drag", a_dragging, a_distance, ex_final)
    after = a_distance()
    before = st.get("before")
    h.check(
        "E7: the next drag moved the arrow 6 mm (a real distance, not NaN)",
        before is not None
        and after is not None
        and math.isfinite(after)
        and abs(after - before - 6.0) < 1.0,
        (before, after),
    )


steps = [harness_check] + b.box_steps("DragReleaseLost") + [add_slow]
# Move
steps += [m_open, m_pick_body, m_ready, m1_drag, m1_after]
steps += m_reopen() + [m2c_drag, m2c_after]
steps += m_reopen() + [m4_drag, m4_after]
steps += m_reopen() + [m8_rotate, m8_z_axis, m8_ready, m8_drag, m8_after]
steps += [unstick(m8_dragging), cancel]
# Offset Plane
steps += [o_open, o_pick_top, o_ready, o_lower, h2b_double_click, h2b_after]
steps += [unstick(o_dragging), h3_drag, h3_after, unstick(o_dragging), cancel]
# Press Pull (a stuck Coin arrow is safe to Cancel; a click on it is what E7 tests)
steps += [p_open, p_pick_top, p_ready, p2_drag, p2_after, cancel]
# Extrude
steps += [e_sketch, e_click_top, e_draw, e_extrude, e_ready, e4_drag, e4_after]
steps += [e7_click, e7_type, e7_new_arrows, e7_drag, e7_after, cancel]

h.run("drag_release_lost", steps)
