# SPDX-License-Identifier: LGPL-2.1-or-later
"""Editing an Extrude that acts on several bodies (R8 review), only real input.

Body1 = x 0..20 (20 x 20 x 10 = 4000), Body2 = x 30..50, 5 high (2000), made like Luca
makes them.

  A  A cut from Body1's top over x 10..40, y 5..15, 3 deep: it reaches Body1 only. Then a
     6 x 6 x 1 boss on Body2's top over x 36..42 (partly over the cut's footprint): 2036.
     Double-click the cut, 8 deep: it now reaches Body2 too ("2 bodies"). The cut is older
     than the boss, so Body2 = 2000 - 300 + 36 = 1736 (the cut acting after the boss gave
     1712: part of the boss was cut away). The timeline keeps its order.
  C  Double-click the cut, click the row, click Body1 (the sketch's own body), OK: the
     timeline titles stay exactly as they were (the step jumped to the end before), 4000 /
     1736; the marker dragged before the boss: Body2 = 1700 (the cut, no boss); to the end.
     C2: the same click takes Body1 back: 3200 / 1736, titles unchanged, marker as in C.
  B  Body2's eye off in the browser, double-click the cut: the row still lists both bodies;
     9 deep, OK, eye on: 3100 / 1636 (the hidden body kept its cut; it was dropped before).
  D  A new design: a 5 x 5 x 5 Body2 inside the footprint of a cut from Body1's top, Extent
     All: the row lists both and says Body2 goes; OK is taken (it was refused with "Body2:
     This cut would remove all of Body2."): Body2 is used up (hidden, out of the browser),
     the step is not red; Undo brings Body2 back, Redo takes it again. Deleting Body2's box
     step makes the cut red with a message that names Body2 once.
  E  Speed on a detailed part (a 120 x 120 plate with 144 holes, built by the golden-model
     builder): E, click the sketch area, type 5, 6 (Join), -5, -6 (Cut): each value answers
     at once and the preview is rebuilt quickly (3 s per value before); an arrow drag from
     the top into the plate turns the operation to Cut when let go.
"""

import time

import FreeCAD as App
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def body1():
    return s.bodies()[0]


def body2():
    return s.bodies()[1]


def vol(body):
    return s.volume(body)


def near(a, c):
    return s.close(a, c)


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def check_volumes(where, v1, v2):
    h.check("%s: Body1 = %g" % (where, v1), near(vol(body1()), v1), vol(body1()))
    h.check("%s: Body2 = %g" % (where, v2), near(vol(body2()), v2), vol(body2()))


def row(p):
    """(label shown, button text, names) of the dialog's bodies row, or None if hidden."""
    if p is None or not p.bodies_label.isVisible():
        return None
    return (p.bodies_label.text(), p.fields["bodies"].button.text(), p.bodies_names.text())


def both_names():
    return "%s, %s" % (body1().Label, body2().Label)


def step_status(name):
    """(status, message) the timeline shows for a step ("ok", "error", "warning"), found
    by its object name (the titles are renumbered when a step is deleted)."""
    for item in t.tl().items():
        if item.name == name:
            return item.status, item.message
    return None


def new_title(before):
    added = [x for x in t.titles() if x not in before]
    return added[0] if added else None


# -- A: an older cut edited to reach a body with a later step ---------------------------------
def a_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def a_pick_top():
    h.click(V(5, 18, 10))  # Body1's top


def a_draw():
    sk = h.in_sketch()
    if h.check("A: sketch on Body1's top", sk is not None):
        ax, ay = h.to_sketch(sk, V(10, 5, 10))
        bx, by = h.to_sketch(sk, V(40, 15, 10))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def a_finish():
    h.ribbon("Finish Sketch")


def a_extrude():
    state["before_cut"] = list(t.titles())
    h.fit()
    h.press("e")


def a_distance():
    p = xpanel()
    if h.check("A: extrude dialog open", p is not None and bool(p.profiles)):
        ui.type_into(p.distance.widget, "-3")


def a_preview():
    p = xpanel()
    h.check("A: Cut by itself", p is not None and p.operation.currentText() == "Cut", p and row(p))
    h.check(
        "A: 3 deep reaches Body1 only",
        row(p) == ("Bodies to Cut", "1 body", body1().Label),
        row(p),
    )
    h.task_button("OK")


def a_cut_made():
    state["cut"] = new_title(state["before_cut"])
    h.check("A: one new step", state["cut"] is not None, t.titles())
    check_volumes("A: cut 3 deep", 3700, 2000)


def a_boss_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def a_boss_pick():
    h.click(V(46, 18, 5))  # Body2's top


def a_boss_draw():
    sk = h.in_sketch()
    if h.check("A: sketch on Body2's top", sk is not None):
        ax, ay = h.to_sketch(sk, V(36, 7, 5))
        bx, by = h.to_sketch(sk, V(42, 13, 5))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def a_boss_finish():
    h.ribbon("Finish Sketch")


def a_boss_extrude():
    state["before_boss"] = list(t.titles())
    h.fit()
    h.press("e")


def a_boss_distance():
    p = xpanel()
    if h.check("A: boss dialog open", p is not None and bool(p.profiles)):
        ui.type_into(p.distance.widget, "1")


def a_boss_preview():
    p = xpanel()
    h.check(
        "A: the boss is a Join on Body2",
        p is not None
        and p.operation.currentText() == "Join"
        and row(p) == ("Bodies to Join", "1 body", body2().Label),
        p and (p.operation.currentText(), row(p)),
    )
    h.task_button("OK")


def a_boss_made():
    state["boss"] = new_title(state["before_boss"])
    h.check("A: the boss is a step", state["boss"] is not None, t.titles())
    check_volumes("A: boss", 3700, 2036)
    state["titles"] = list(t.titles())
    h.check(
        "A: the boss comes after the cut",
        state["titles"].index(state["cut"]) < state["titles"].index(state["boss"]),
        state["titles"],
    )


def a_edit():
    h.check("A: double-click the cut", ui.double_click_timeline(state["cut"]))


def a_editing():
    p = xpanel()
    if h.check("A: edit dialog open", p is not None and p.editing):
        ui.type_into(p.distance.widget, "-8")


def a_edit_preview():
    p = xpanel()
    h.check("A: 8 deep reaches both", row(p) == ("Bodies to Cut", "2 bodies", both_names()), row(p))
    check_volumes("A: preview 8 deep (the cut before the boss)", 3200, 1736)
    h.task_button("OK")


def a_edited():
    h.check("A: dialog closed", xpanel() is None)
    check_volumes("A: 8 deep, the boss kept (cut first, then the boss)", 3200, 1736)
    h.check("A: the timeline keeps its order", list(t.titles()) == state["titles"], t.titles())
    h.shot("A-edited")


# -- C: leaving the sketch's own body out (and taking it back) keeps the step's place -------------
def _toggle_body1(tag):
    """Steps: double-click the cut, click the row, click Body1 (its top, away from the cut)."""

    def edit():
        h.check("%s: double-click the cut" % tag, ui.double_click_timeline(state["cut"]))

    def click_row():
        p = xpanel()
        if h.check("%s: edit dialog open" % tag, p is not None and p.editing):
            b.click_widget(p.fields["bodies"].button)

    def click_body1():
        p = xpanel()
        h.check(
            "%s: the row takes the clicks" % tag,
            p is not None and p.active == "bodies",
            p and p.active,
        )
        h.click(V(4, 18, 10))

    for step in (edit, click_row, click_body1):
        step.__name__ = "%s_%s" % (tag.lower(), step.__name__)
    return [edit, click_row, click_body1]


def c_left_out():
    p = xpanel()
    r = row(p)
    h.check(
        "C: Body1 left out",
        r is not None and r[1] == "1 body" and r[2].startswith(body2().Label),
        r,
    )
    check_volumes("C: preview without Body1", 4000, 1736)
    h.task_button("OK")


def c_done():
    h.check("C: dialog closed", xpanel() is None)
    check_volumes("C: Body1 left out", 4000, 1736)
    h.check(
        "C: the timeline titles are unchanged (the step kept its place)",
        list(t.titles()) == state["titles"],
        (state["titles"], t.titles()),
    )
    t.drag_marker(before_title=state["boss"])


def c_rolled():
    check_volumes("C: marker before the boss (the cut acts first in Body2)", 4000, 1700)
    t.drag_marker(to_end=True)


def c_end():
    check_volumes("C: marker at the end", 4000, 1736)


def c2_taken_back():
    p = xpanel()
    r = row(p)
    h.check(
        "C2: Body1 taken back",
        r is not None
        and r[:2] == ("Bodies to Cut", "2 bodies")
        and r[2].splitlines()[0] == both_names(),
        r,
    )
    check_volumes("C2: preview with Body1", 3200, 1736)
    h.task_button("OK")


def c2_done():
    h.check("C2: dialog closed", xpanel() is None)
    check_volumes("C2: Body1 back", 3200, 1736)
    h.check(
        "C2: the timeline titles are unchanged",
        list(t.titles()) == state["titles"],
        (state["titles"], t.titles()),
    )
    t.drag_marker(before_title=state["boss"])


def c2_rolled():
    check_volumes("C2: marker before the boss", 3200, 1700)
    t.drag_marker(to_end=True)


def c2_end():
    check_volumes("C2: marker at the end", 3200, 1736)


# -- B: a hidden body keeps its cut through an edit -----------------------------------------------
def b_hide():
    h.check("B: Body2's eye clicked", t.click_eye(body2().Label))


def b_hidden():
    h.check("B: Body2 hidden", not s.shown(body2()))
    h.check("B: double-click the cut", ui.double_click_timeline(state["cut"]))


def b_editing():
    p = xpanel()
    if not h.check("B: edit dialog open", p is not None and p.editing):
        return
    h.check(
        "B: the row still lists the hidden body",
        row(p) == ("Bodies to Cut", "2 bodies", both_names()),
        row(p),
    )
    ui.type_into(p.distance.widget, "-9")


def b_ok():
    h.task_button("OK")


def b_show():
    h.check("B: dialog closed", xpanel() is None)
    h.check("B: Body2's eye clicked again", t.click_eye(body2().Label))


def b_kept():
    h.check("B: Body2 shown", s.shown(body2()))
    check_volumes("B: 9 deep, Body2 kept its cut while hidden", 3100, 1636)


# -- D: a body wholly inside the cut is used up -----------------------------------------------------
def d_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def d_pick_top():
    h.click(V(4, 18, 10))  # Body1's top


def d_draw():
    sk = h.in_sketch()
    if h.check("D: sketch on Body1's top", sk is not None):
        ax, ay = h.to_sketch(sk, V(10, 2, 10))
        bx, by = h.to_sketch(sk, V(40, 18, 10))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def d_finish():
    h.ribbon("Finish Sketch")


def d_extrude():
    state["before_d"] = list(t.titles())
    h.fit()
    h.press("e")


def d_distance():
    p = xpanel()
    if h.check("D: extrude dialog open", p is not None and bool(p.profiles)):
        ui.type_into(p.distance.widget, "-5")


def d_all():
    p = xpanel()
    if h.check("D: Cut by itself", p is not None and p.operation.currentText() == "Cut"):
        h.check("D: choose Extent: All", ui.choose(p.extent, "All"))


def d_preview():
    p = xpanel()
    r = row(p)
    h.check("D: row lists both", r is not None and r[:2] == ("Bodies to Cut", "2 bodies"), r)
    h.check(
        "D: the row says Body2 goes",
        r is not None and ("All of %s is inside the cut" % body2().Label) in r[2],
        r,
    )
    h.check("D: no warning", p is not None and p.message.text() == "", p and p.message.text())
    h.check("D: Body2 still shown while the dialog is open", s.shown(body2()))
    h.shot("D-preview")
    h.task_button("OK")


def d_done():
    h.check("D: OK taken (dialog closed)", xpanel() is None, xpanel() and xpanel().message.text())
    state["d_cut"] = new_title(state["before_d"])
    lead = t.obj(state["d_cut"]) if state["d_cut"] else None
    state["d_cut_name"] = lead.Name if lead is not None else None
    h.check("D: Body1 cut through", near(vol(body1()), 2400), vol(body1()))


def d_used_up():
    h.check("D: Body2 used up (hidden)", not s.shown(body2()))
    tree = s.browser()
    if tree is not None:
        h.check("D: Body2 out of the browser", tree.row(body2().Label) is None, tree.labels())
    status = step_status(state.get("d_cut_name"))
    h.check("D: the step is not red", status is not None and status[0] == "ok", status)
    s.undo()


def d_undone():
    h.check("D: undo: Body2 shown again", s.shown(body2()))
    check_volumes("D: undo", 4000, 125)
    s.redo()


def d_redone():
    h.check("D: redo: Body2 used up again", not s.shown(body2()))
    h.check("D: redo: Body1 cut", near(vol(body1()), 2400), vol(body1()))
    t.menu(state["box2"], "Delete")


def d_box_deleted():
    kind, reason = step_status(state.get("d_cut_name")) or ("", "")
    label = body2().Label
    h.check("D: the cut is red once Body2 has no solid", kind == "error", (kind, reason))
    h.check(
        "D: the message names Body2 once",
        reason.count(label) == 1 and not reason.startswith(label + ":"),
        reason,
    )
    s.undo()


def d_box_back():
    status = step_status(state.get("d_cut_name"))
    h.check(
        "D: undo the delete: the step is fine again",
        status is not None and status[0] == "ok",
        status,
    )


def d_box2_title():
    """Box 2's step title (its Extrude), for the delete in D."""
    titles = list(t.titles())
    extrudes = [x for x in titles if x.startswith("Extrude")]
    state["box2"] = extrudes[1] if len(extrudes) > 1 else None
    h.check("D: Body2's box step found", state["box2"] is not None, titles)


# -- E: speed on a detailed part ---------------------------------------------------------------------
def e_setup():
    import FreeCADGui as Gui

    from SciForgeTests.golden.builder import Builder

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Plate144")
    circles = []
    for i in range(12):
        for j in range(12):
            circles.append({"circle": [5 + i * 10, 5 + j * 10, 2]})
    doc = App.ActiveDocument
    builder = Builder(doc)
    for step in (
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 120, 120]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": circles},
        {"op": "extrude", "id": "h1", "profile": "s2", "distance": 10, "operation": "cut"},
        {
            "op": "sketch",
            "id": "s3",
            "plane": "XY",
            "offset": 10,
            "geometry": [{"rect": [20, 20, 100, 100]}],
        },
    ):
        builder.run(step)
    doc.recompute()
    state["plate"] = vol(s.bodies()[0])
    h.check("E: the plate has 150 faces", len(s.bodies()[0].Shape.Faces) == 150)
    h.click_empty()
    h.fit()


def _settled(p, limit=20.0):
    """Wait (processing events) until the dialog's preview is rebuilt; the seconds it took."""
    started = time.monotonic()
    while time.monotonic() - started < limit:
        QtWidgets.QApplication.processEvents()
        if p._closed or (not p.dirty and not p._timer.isActive()):
            break
        time.sleep(0.005)
    return time.monotonic() - started


def e_extrude():
    started = time.monotonic()
    h.press("e")
    state["open_key"] = time.monotonic() - started


def e_pick():
    p = xpanel()
    if not h.check("E: extrude dialog open", p is not None):
        return
    if p.target is None:
        h.click(V(60, 60, 10))  # the sketch area on the plate's top
    _settled(p)
    h.check("E: the sketch area picked", bool(p.profiles), p.profiles)


def _type_and_time(text):
    """Type a value like ui.type_into, timing the keys themselves (what the dialog does
    while the person types: it was 3 s per key on this plate) and the whole answer (the
    keys, Tab and the rebuilt preview)."""
    from PySide6 import QtTest

    p = xpanel()
    if p is None:
        return None
    widget = p.distance.widget
    QtTest.QTest.mouseClick(
        widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, widget.height() // 2)
    )
    QtWidgets.QApplication.processEvents()
    widget.setFocus()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtWidgets.QApplication.processEvents()
    started = time.monotonic()
    QtTest.QTest.keyClicks(widget, text)
    typed = time.monotonic() - started
    QtWidgets.QApplication.processEvents()
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Tab)
    total = time.monotonic() - started + _settled(p)
    return typed, total


def e_type(text, operation, label):
    def step():
        got = _type_and_time(text)
        p = xpanel()
        h.check(
            "E: %s: %s" % (text, operation),
            p is not None and p.operation.currentText() == operation,
            p and p.operation.currentText(),
        )
        if got is None:
            return
        typed, total = got
        h.check(
            "E: typing %s answers at once (%.2f s; 3 s before)" % (text, typed),
            typed < 0.3,
            typed,
        )
        h.check(
            "E: the preview for %s is rebuilt within 2.5 s (%.2f s; 4 s before)" % (text, total),
            total < 2.5,
            total,
        )

    step.__name__ = "e_type_" + label
    return step


def e_back_up():
    p = xpanel()
    if p is not None:
        ui.type_into(p.distance.widget, "5")
        _settled(p)
        h.check("E: 5 again: Join", p.operation.currentText() == "Join", p.operation.currentText())


def e_drag():
    p = xpanel()
    arrow = p.dragger if p is not None else None
    if not h.check("E: distance arrow shown", arrow is not None):
        return
    place = arrow.root.getChild(0)
    origin = place.translation.getValue().getValue()
    axis = place.rotation.getValue().multVec(arrow.coin.SbVec3f(1, 0, 0)).getValue()
    head = V(*origin) + V(*axis) * (arrow.distance() + arrow.size * 0.9)
    a = h.screen_point(head)
    started = time.monotonic()
    h.drag(a, QtCore.QPoint(a.x(), a.y() + 90), steps=16)  # down, into the plate
    state["drag"] = time.monotonic() - started


def e_dragged():
    p = xpanel()
    if p is None:
        return
    _settled(p)
    h.check(
        "E: the arrow dragged into the plate: Cut once let go",
        p.operation.currentText() == "Cut" and p.distance.value() < 0,
        (p.operation.currentText(), p.distance.value()),
    )
    h.check(
        "E: the drag answered quickly (%.2f s for 16 moves)" % state.get("drag", 0.0),
        state.get("drag", 99.0) < 8.0,
        state.get("drag"),
    )
    h.check(
        "E: the cut row lists the plate",
        row(p) is not None and row(p)[:2] == ("Bodies to Cut", "1 body"),
        row(p),
    )
    h.shot("E-dragged")
    h.press(QtCore.Qt.Key_Escape)


def e_closed():
    h.check("E: Esc closed the dialog", xpanel() is None)
    h.check("E: the plate is as it was", near(vol(s.bodies()[0]), state["plate"]))


h.run(
    "extrude_multibody_edit",
    [s.new_design("MultiBodyEdit")]
    + s.box_steps("box1", (0, 0, 20, 20), 10, V(6, -6, 0))
    + s.box_steps("box2", (30, 0, 50, 20), 5, V(6, -6, 0), new_body=True)
    + [
        a_sketch,
        a_pick_top,
        a_draw,
        a_finish,
        a_extrude,
        a_distance,
        a_preview,
        a_cut_made,
        a_boss_sketch,
        a_boss_pick,
        a_boss_draw,
        a_boss_finish,
        a_boss_extrude,
        a_boss_distance,
        a_boss_preview,
        a_boss_made,
        a_edit,
        a_editing,
        a_edit_preview,
        a_edited,
    ]
    + _toggle_body1("C")
    + [c_left_out, c_done, c_rolled, c_end]
    + _toggle_body1("C2")
    + [
        c2_taken_back,
        c2_done,
        c2_rolled,
        c2_end,
        b_hide,
        b_hidden,
        b_editing,
        b_ok,
        b_show,
        b_kept,
        s.new_design("UsedUp"),
    ]
    + s.box_steps("dbox1", (0, 0, 20, 20), 10, V(6, -6, 0))
    + s.box_steps("dbox2", (25, 5, 30, 10), 5, V(6, -6, 0), new_body=True)
    + [
        d_box2_title,
        d_sketch,
        d_pick_top,
        d_draw,
        d_finish,
        d_extrude,
        d_distance,
        d_all,
        d_preview,
        d_done,
        d_used_up,
        d_undone,
        d_redone,
        d_box_deleted,
        d_box_back,
        e_setup,
        e_extrude,
        e_pick,
        e_type("5", "Join", "5"),
        e_type("6", "Join", "6"),
        e_type("-5", "Cut", "minus5"),
        e_type("-6", "Cut", "minus6"),
        e_back_up,
        e_drag,
        e_dragged,
        e_closed,
    ],
)
