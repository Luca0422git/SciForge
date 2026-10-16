# SPDX-License-Identifier: LGPL-2.1-or-later
"""An Extrude through several bodies (Luca's R8: "if extruding through multiple objects,
show 'objects being edited'"), only real input.

Two boxes made like Luca makes them: Body1 = x 0..20, Body2 = x 30..50 (each 20 x 20 x 10 =
4000). Body2's sketch is on the XY plane away from Body1: the operation turns to New Body
by itself, as in Fusion.

  A  Sketch on Body1's top across the gap into Body2 (x 10..40, y 5..15), E, -5: the
     operation turns to Cut by itself (the middle of the profile is over the gap), the
     "Bodies to Cut" row says "2 bodies" and "Body1, Body2", both bodies are cut (3500 /
     3500).
  B  Click the row, click Body2: it is left out (4000, "1 body"); click it again: back
     (3500). The same with Body1, the sketch's own body (the cut then lives in Body2).
     Extent All: 3000 / 3000. OK: exactly one new timeline step; Undo / Redo.
  C  Double-click the step: the row lists both bodies; Extent Distance, -8: 3200 / 3200.
  D  Marker dragged before the step: 4000 / 4000; to the end: 3200 / 3200. Suppress and
     Unsuppress from the step's menu; Undo / Redo.
  E  Save, close, open: 3200 / 3200 and still one step; edit to -3: 3700 / 3700.
  F  Timeline Delete: both boxes whole again, no hidden steps left behind.
  H  Q (Press Pull) on the sketch area across both tops turns into Extrude with the same
     row (-5: Cut, "2 bodies"). Cut picked by hand and 5 (up, away from both): the dialog
     says the cut goes through no body, the operation stays Cut, OK is refused; Esc.
  G  Sketch on the XY plane under both boxes, E, -5 (down, away from them): Join by itself,
     "Bodies to Join: 2 bodies"; OK: the bodies merge into one (9500, one solid), the other
     is used up (hidden, out of the browser); Undo brings it back.
"""

import os
import tempfile

import FreeCAD as App

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
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


def followers():
    from sciforge import extrude_bodies

    doc = App.ActiveDocument
    return [o for o in doc.Objects if extrude_bodies.is_follower(o)] if doc else []


def check_volumes(where, v1, v2):
    h.check("%s: Body1 = %g" % (where, v1), near(vol(body1()), v1), vol(body1()))
    h.check("%s: Body2 = %g" % (where, v2), near(vol(body2()), v2), vol(body2()))


def row(p):
    """(label shown, button text, names) of the dialog's bodies row, or None if hidden."""
    if p is None or not p.bodies_label.isVisible():
        return None
    return (p.bodies_label.text(), p.fields["bodies"].button.text(), p.bodies_names.text())


def lead():
    from sciforge import extrude

    found = [o for o in App.ActiveDocument.Objects if extrude.is_extrude(o)]
    return found[-1] if found else None


# -- the two boxes ------------------------------------------------------------------------
def box2_sketch():
    state["n"] = len(s.bodies())
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def box2_pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def box2_draw():
    sk = h.in_sketch()
    if h.check("box 2: sketch open on XY", sk is not None):
        h.draw_rectangle(sk, 30, 0, 50, 20)


def box2_finish():
    h.ribbon("Finish Sketch")


def box2_extrude():
    h.fit()
    h.press("e")


def box2_distance():
    p = xpanel()
    if h.check("box 2: extrude dialog open", p is not None):
        ui.type_into(p.distance.widget, "10")


def box2_new_body_by_itself():
    p = xpanel()
    h.check(
        "box 2 away from Body1: New Body by itself (Fusion)",
        p is not None and p.operation.currentText() == "New Body",
        p and p.operation.currentText(),
    )
    h.check("no bodies row for New Body", row(p) is None, row(p))
    h.task_button("OK")


def box2_made():
    h.check("a second body", len(s.bodies()) == state["n"] + 1, [x.Label for x in s.bodies()])
    check_volumes("two boxes", 4000, 4000)
    h.check("Body1 one solid", len(body1().Shape.Solids) == 1, len(body1().Shape.Solids))


# -- A: a cut across both -------------------------------------------------------------------
def a_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def a_pick_top():
    h.click(V(5, 10, 10))  # Body1's top face


def a_draw():
    sk = h.in_sketch()
    if h.check("sketch on Body1's top", sk is not None):
        ax, ay = h.to_sketch(sk, V(10, 5, 10))
        bx, by = h.to_sketch(sk, V(40, 15, 10))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
        state["cross"] = sk.Name


def a_finish():
    h.ribbon("Finish Sketch")


def a_extrude():
    state["titles"] = list(t.titles())
    h.fit()
    h.press("e")


def a_distance():
    p = xpanel()
    if h.check("extrude dialog open", p is not None):
        h.check("the sketch's area picked by itself", bool(p.profiles), p.profiles)
        ui.type_into(p.distance.widget, "-5")


def a_preview():
    p = xpanel()
    h.check(
        "Cut by itself (the profile starts inside both bodies)",
        p is not None and p.operation.currentText() == "Cut",
        p and p.operation.currentText(),
    )
    names = "%s, %s" % (body1().Label, body2().Label)
    h.check(
        "row: Bodies to Cut, 2 bodies, both names",
        row(p) == ("Bodies to Cut", "2 bodies", names),
        row(p),
    )
    check_volumes("cut preview", 3500, 3500)
    h.shot("A-cut-preview")


# -- B: leave Body2 out and take it back; All; OK; undo / redo ----------------------------
def b_click_row():
    p = xpanel()
    if p is not None:
        b.click_widget(p.fields["bodies"].button)


def b_row_active():
    p = xpanel()
    h.check("the row takes the clicks", p is not None and p.active == "bodies", p and p.active)
    h.check(
        "the row says what a click does",
        p is not None and "click a body" in p.bodies_names.text().lower(),
        p and p.bodies_names.text(),
    )
    h.click(V(45, 10, 10))  # Body2's top, away from the cut


def b_left_out():
    p = xpanel()
    r = row(p)
    h.check("Body2 left out: 1 body", r is not None and r[1] == "1 body", r)
    h.check(
        "Body2 left out: only Body1 named",
        r is not None and r[2].splitlines()[0] == body1().Label,
        r,
    )
    check_volumes("Body2 left out", 3500, 4000)
    h.shot("B-left-out")
    h.click(V(45, 10, 10))


def b_taken_back():
    p = xpanel()
    h.check("Body2 back: 2 bodies", row(p) is not None and row(p)[1] == "2 bodies", row(p))
    check_volumes("Body2 back", 3500, 3500)
    h.click(V(4, 17, 10))  # Body1's top (the sketch's own body), away from the cut


def b_body1_out():
    p = xpanel()
    r = row(p)
    h.check("Body1 left out: 1 body", r is not None and r[1] == "1 body", r)
    h.check(
        "Body1 left out: only Body2 named",
        r is not None and r[2].splitlines()[0] == body2().Label,
        r,
    )
    check_volumes("the sketch's own body left out", 4000, 3500)
    h.click(V(4, 17, 10))


def b_body1_back():
    p = xpanel()
    h.check("Body1 back: 2 bodies", row(p) is not None and row(p)[1] == "2 bodies", row(p))
    check_volumes("Body1 back", 3500, 3500)
    if p is not None:
        h.check("choose Extent: All", ui.choose(p.extent, "All"))


def b_all():
    check_volumes("Extent All", 3000, 3000)
    h.task_button("OK")


def b_done():
    h.check("dialog closed", xpanel() is None)
    check_volumes("after OK", 3000, 3000)
    after = list(t.titles())
    added = [x for x in after if x not in state["titles"]]
    h.check("exactly one new timeline step", len(after) == len(state["titles"]) + 1, added)
    state["title"] = added[0] if added else None
    h.check("one hidden step in Body2", len(followers()) == 1, [f.Label for f in followers()])
    h.check(
        "the hidden step is not in the timeline",
        not any("follower" in x.lower() or "(Body" in x for x in after),
        after,
    )
    s.undo()


def b_undone():
    check_volumes("undo", 4000, 4000)
    h.check("undo: no hidden step left", not followers(), [f.Label for f in followers()])
    s.redo()


def b_redone():
    check_volumes("redo", 3000, 3000)
    h.check("redo: the hidden step is back", len(followers()) == 1)


# -- C: edit ----------------------------------------------------------------------------------
def c_edit():
    h.check("double-click the step", ui.double_click_timeline(state["title"] or "?"))


def c_editing():
    p = xpanel()
    if not h.check("edit dialog open", p is not None and p.editing):
        return
    names = "%s, %s" % (body1().Label, body2().Label)
    h.check("edit: the row lists both", row(p) == ("Bodies to Cut", "2 bodies", names), row(p))
    h.check("choose Extent: Distance", ui.choose(p.extent, "Distance"))


def c_distance():
    p = xpanel()
    if p is not None:
        ui.type_into(p.distance.widget, "-8")


def c_preview():
    check_volumes("edit -8", 3200, 3200)
    h.task_button("OK")


def c_done():
    check_volumes("edit kept", 3200, 3200)
    h.check("still one hidden step", len(followers()) == 1)


# -- D: marker, suppress ----------------------------------------------------------------------
def d_marker_before():
    t.drag_marker(before_title=state["title"])


def d_rolled_back():
    check_volumes("marker before the step", 4000, 4000)
    t.drag_marker(to_end=True)


def d_rolled_forward():
    check_volumes("marker at the end", 3200, 3200)
    t.menu(state["title"], "Suppress Features")


def d_suppressed():
    check_volumes("suppressed", 4000, 4000)
    t.menu(state["title"], "Unsuppress Features")


def d_unsuppressed():
    check_volumes("unsuppressed", 3200, 3200)
    s.undo()


def d_undo():
    check_volumes("undo unsuppress", 4000, 4000)
    s.redo()


def d_redo():
    check_volumes("redo unsuppress", 3200, 3200)


# -- E: save, close, open ------------------------------------------------------------------------
def e_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-r8-"), "two_bodies.FCStd")
    state["path"] = path
    state["count"] = len(t.titles())
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def e_close():
    App.closeDocument(App.ActiveDocument.Name)


def e_open():
    App.openDocument(state["path"])
    h.fit()


def e_reopened():
    check_volumes("reopened", 3200, 3200)
    h.check("reopened: same timeline", len(t.titles()) == state["count"], t.titles())
    h.check("reopened: one hidden step", len(followers()) == 1)
    h.check("double-click the step", ui.double_click_timeline(state["title"]))


def e_editing():
    p = xpanel()
    if not h.check("edit after reopening", p is not None and p.editing):
        return
    h.check("reopened: the row lists both", row(p) is not None and row(p)[1] == "2 bodies", row(p))
    ui.type_into(p.distance.widget, "-3")


def e_preview():
    check_volumes("edit -3 after reopening", 3700, 3700)
    h.task_button("OK")


def e_done():
    check_volumes("kept", 3700, 3700)


# -- F: delete ---------------------------------------------------------------------------------
def f_delete():
    t.menu(state["title"], "Delete")


def f_deleted():
    check_volumes("deleted", 4000, 4000)
    h.check("no hidden step left behind", not followers(), [f.Label for f in followers()])
    h.check("the step is gone", state["title"] not in t.titles(), t.titles())


# -- H: Press Pull on the sketch area -------------------------------------------------------------
def h_press_pull():
    h.click_empty()
    h.fit()
    h.press("q")


def h_click_area():
    h.fit()
    h.click(V(25, 10, 10))  # the sketch area over the gap


def h_became_extrude():
    p = xpanel()
    if h.check("Press Pull on the area starts Extrude", p is not None and bool(p.profiles)):
        ui.type_into(p.distance.widget, "-5")


def h_row():
    p = xpanel()
    names = "%s, %s" % (body1().Label, body2().Label)
    h.check(
        "Press Pull's extrude: the same row", row(p) == ("Bodies to Cut", "2 bodies", names), row(p)
    )
    check_volumes("Press Pull preview", 3500, 3500)
    if p is not None:
        h.check("Cut picked by hand", ui.choose(p.operation, "Cut"))


def h_up():
    p = xpanel()
    if p is not None:
        ui.type_into(p.distance.widget, "5")  # up, away from both bodies


def h_nothing_in_the_way():
    p = xpanel()
    h.check(
        "a cut that reaches no body says so",
        p is not None and "does not go through any body" in p.message.text(),
        p and p.message.text(),
    )
    h.check("the operation stays Cut", p is not None and p.operation.currentText() == "Cut", p)
    h.check(
        "the row says no body",
        row(p) is not None and row(p)[2] == "The extrusion goes through no body.",
        row(p),
    )
    check_volumes("nothing cut", 4000, 4000)
    h.task_button("OK")


def h_ok_refused():
    p = xpanel()
    h.check("OK refused while the cut reaches no body", p is not None and not p._closed)
    h.press(Qt_Escape())


def h_cancelled():
    h.check("Esc closed it", xpanel() is None)
    check_volumes("cancelled", 4000, 4000)
    h.check("cancelled: no hidden step", not followers())


def Qt_Escape():
    from PySide import QtCore

    return QtCore.Qt.Key_Escape


# -- G: a join that merges both -----------------------------------------------------------------
def g_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def g_pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def g_draw():
    sk = h.in_sketch()
    if h.check("sketch on XY under the boxes", sk is not None):
        ax, ay = h.to_sketch(sk, V(10, 5, 0))
        bx, by = h.to_sketch(sk, V(40, 15, 0))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def g_finish():
    h.ribbon("Finish Sketch")


def g_extrude():
    h.fit()
    h.press("e")


def g_distance():
    p = xpanel()
    if h.check("extrude dialog open (join)", p is not None):
        ui.type_into(p.distance.widget, "-5")


def g_preview():
    p = xpanel()
    h.check(
        "Join by itself (it only touches the boxes)",
        p is not None and p.operation.currentText() == "Join",
        p and p.operation.currentText(),
    )
    h.check(
        "row: Bodies to Join, 2 bodies",
        row(p) is not None and row(p)[:2] == ("Bodies to Join", "2 bodies"),
        row(p),
    )
    merged = [x for x in s.bodies() if near(vol(x), 9500)]
    h.check("preview: one body of 9500", len(merged) == 1, [vol(x) for x in s.bodies()])
    h.shot("G-join-preview")
    h.task_button("OK")


def g_merged():
    shown = [x for x in s.bodies() if s.shown(x)]
    h.check("one body left shown", len(shown) == 1, [x.Label for x in shown])
    if shown:
        h.check("merged: 9500", near(vol(shown[0]), 9500), vol(shown[0]))
        h.check("merged: one solid", len(shown[0].Shape.Solids) == 1, len(shown[0].Shape.Solids))
    hidden = [x for x in s.bodies() if not s.shown(x)]
    h.check("the other body used up (hidden)", len(hidden) == 1, [x.Label for x in hidden])
    tree = s.browser()
    if hidden and tree is not None:
        h.check("used-up body out of the browser", tree.row(hidden[0].Label) is None, tree.labels())
    state["hidden"] = hidden[0].Name if hidden else None
    s.undo()


def g_undone():
    check_volumes("join undone", 4000, 4000)


def g_undone_view():
    h.check(
        "both bodies shown again",
        all(s.shown(x) for x in s.bodies()),
        [s.shown(x) for x in s.bodies()],
    )


h.run(
    "extrude_multibody",
    [s.new_design("MultiBody")]
    + s.box_steps("box1", (0, 0, 20, 20), 10, V(6, -6, 0))
    + [
        box2_sketch,
        box2_pick_xy,
        box2_draw,
        box2_finish,
        box2_extrude,
        box2_distance,
        box2_new_body_by_itself,
        box2_made,
        a_sketch,
        a_pick_top,
        a_draw,
        a_finish,
        a_extrude,
        a_distance,
        a_preview,
        b_click_row,
        b_row_active,
        b_left_out,
        b_taken_back,
        b_body1_out,
        b_body1_back,
        b_all,
        b_done,
        b_undone,
        b_redone,
        c_edit,
        c_editing,
        c_distance,
        c_preview,
        c_done,
        d_marker_before,
        d_rolled_back,
        d_rolled_forward,
        d_suppressed,
        d_unsuppressed,
        d_undo,
        d_redo,
        e_save,
        e_close,
        e_open,
        e_reopened,
        e_editing,
        e_preview,
        e_done,
        f_delete,
        f_deleted,
        h_press_pull,
        h_click_area,
        h_became_extrude,
        h_row,
        h_up,
        h_nothing_in_the_way,
        h_ok_refused,
        h_cancelled,
        g_sketch,
        g_pick_xy,
        g_draw,
        g_finish,
        g_extrude,
        g_distance,
        g_preview,
        g_merged,
        g_undone,
        g_undone_view,
    ],
)
