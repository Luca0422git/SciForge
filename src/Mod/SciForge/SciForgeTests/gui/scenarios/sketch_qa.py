# SPDX-License-Identifier: LGPL-2.1-or-later
"""The sketch workspace used the way Fusion users use it, the awkward ways included.
Only real input (keys, clicks, typing, the ribbon, the timeline, right clicks).

A  Typed lengths: L, click the origin, type 40, Tab, 0, Enter, then 25, Tab, 90, Enter;
   the lines join end to end; two clicks close the shape. Finish, E, OK: 40 x 25 x 10.
H  Edit it from the timeline twice, Ctrl+Z / Ctrl+Y right after Finish Sketch (one press
   each, like Fusion), save, close, reopen, edit again: the part follows every time.
I  Break the profile (delete a line) and finish: no error, no pop-up, a plain message
   next to the mouse; one Ctrl+Z brings the part back.
B  The dimension box refuses 0, a negative size, text and a mass, keeps the box open with
   the reason, takes 6+4; a dimension on a size already set becomes a driven dimension
   (the sketch is not over-constrained).
C  Esc in the middle: after the first rectangle corner, while Offset waits for a curve,
   while Project runs. Nothing is drawn, the sketch stays open.
D  Switching tools mid-way: L, one click, C (the half line goes), a circle typed 20 wide,
   E while the circle tool still runs: the sketch finishes and Extrude takes the circle.
E  Right click in a sketch: the sketch's marking menu (Line, Finish Sketch... not Hole or
   Press Pull). Del deletes one sketch line, Ctrl+Z brings it back, M moves sketch curves.
F  X with nothing selected: new lines are construction (the palette shows it, a message
   says it); the next sketch starts with normal lines again.
G  Sketch fillet: click a corner, the radius box opens, type 4.

Hand-derived volumes: A 40*25*10 = 10000; H 50*25*10 = 12500, 45*25*10 = 11250;
D pi*10^2*10 = 3141.59...; G (30*20 - (4^2 - pi*4^2/4)) * 10 = 5965.66...
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
X, Y = V(1, 0, 0), V(0, 1, 0)
s = {}


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def editor():
    sess = session()
    return sess.editor if sess is not None else None


def invalid_objects():
    return [
        o.Label for o in App.ActiveDocument.Objects if "Invalid" in o.State or "Error" in o.State
    ]


def length(g):
    return (g.EndPoint - g.StartPoint).Length


def esc():
    h.press(QtCore.Qt.Key_Escape)


def new_doc(name):
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument(name)
    h.fit()


# == A: a rectangle from typed lengths ==========================================
def a_new():
    new_doc("SketchQA1")


def a_create():
    h.ribbon("Create Sketch")


def a_pick():
    h.click(V(12, -8, 0))


def a_line():
    s["sk"] = h.in_sketch()
    h.check("A: sketch open on XY", s["sk"] is not None)
    h.press("l")


def a_first():
    si.click(V(0, 0, 0))


def a_type_40():
    si.move_towards(V(15, 0.3, 0), X)
    si.type_text("40", enter=False)
    si.tab()
    si.type_text("0")


def a_after_40():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("A: typed 40 at 0 deg: one line", len(lines) == 1, sk.Geometry)
    if lines:
        g = lines[0][1]
        h.check("A: from the origin, 40 long, along X", si.vnear(g.EndPoint, V(40, 0, 0)), g)
    dims = [c for c in sk.Constraints if c.Type == "Distance" and c.Driving]
    h.check(
        "A: the typed length is a dimension (Fusion)",
        any(si.near(c.Value, 40.0) for c in dims),
        [(c.Type, c.Value) for c in sk.Constraints],
    )
    h.check("A: the line tool goes on from the end", si.drawing())
    h.shot("A1-typed")
    si.move_towards(V(40.3, 15, 0), Y)


def a_type_25():
    si.type_text("25", enter=False)
    si.tab()
    si.type_text("90")


def a_after_25():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("A: second line", len(lines) == 2, sk.Geometry)
    if len(lines) == 2:
        g = lines[1][1]
        h.check(
            "A: the second line starts where the first ends, 25 up",
            si.vnear(g.StartPoint, V(40, 0, 0)) and si.vnear(g.EndPoint, V(40, 25, 0)),
            g,
        )
        joined = [
            c
            for c in sk.Constraints
            if c.Type == "Coincident" and {c.First, c.Second} == {lines[0][0], lines[1][0]}
        ]
        h.check("A: the two lines are joined (coincident)", bool(joined), sk.Constraints)


def a_third():
    si.click(V(0, 25, 0))


def a_close():
    si.click(V(0, 0, 0))


def a_closed():
    sk = s["sk"]
    lines = si.lines(sk)
    h.check("A: 4 lines", len(lines) == 4, len(lines))
    h.check("A: the shape is closed: one profile", session().shading.count == 1)
    h.check("A: solves (not over-constrained)", sk.solve() == 0)
    h.check(
        "A: no redundant or conflicting constraint",
        not sk.RedundantConstraints and not sk.ConflictingConstraints,
        (sk.RedundantConstraints, sk.ConflictingConstraints),
    )
    h.check("A: no pop-up", not h.popups(), h.popups())
    h.shot("A2-closed")


def a_finish():
    esc()
    h.ribbon("Finish Sketch")


def a_extrude():
    h.check("A: sketch finished", h.in_sketch() is None)
    h.fit()
    h.press("e")


def a_ok():
    h.task_button("OK")


def a_volume():
    v = h.solid_volume()
    h.check("A: 40 x 25 x 10 = 10000", si.near(v, 10000.0, 1e-6), v)


# == H: edit twice, undo/redo after Finish, save and reopen =====================
def _dim(value):
    sk = h.in_sketch()
    for i, c in enumerate(sk.Constraints):
        if c.Type in ("Distance", "DistanceX") and c.Driving and si.near(c.Value, value, 1e-6):
            return i
    return None


def _double_click_dim(value):
    sk = h.in_sketch()
    index = _dim(value)
    h.check("dimension %g found" % value, index is not None, sk.Constraints)
    if index is None:
        return
    point = si.dimension_label(sk, index)
    h.move(h.screen_point(point + V(2, 1, 0)))
    h.move(h.screen_point(point))
    h.double_click(point)


def h_edit():
    si.timeline_double_click("Sketch 1")


def h_dbl():
    h.check("H: editing from the timeline", h.in_sketch() is s["sk"])
    _double_click_dim(40.0)


def h_type():
    h.check("H: the dimension box is open", editor() is not None)
    h.check("H: no pop-up", not h.popups(), h.popups())
    si.type_text("50")


def h_finish():
    h.ribbon("Finish Sketch")


def h_updated():
    v = h.solid_volume()
    h.check("H: 50 x 25 x 10", si.near(v, 12500.0, 1e-6), v)
    s["undo"] = list(App.ActiveDocument.UndoNames)


def h_undo():
    h.press("z", QtCore.Qt.ControlModifier)


def h_undone():
    v = h.solid_volume()
    h.check("H: ONE Ctrl+Z after Finish Sketch takes the change back", si.near(v, 10000.0), v)
    h.check("H: not in the sketch after undo", h.in_sketch() is None)
    h.press("y", QtCore.Qt.ControlModifier)


def h_redone():
    v = h.solid_volume()
    h.check("H: ONE Ctrl+Y does it again", si.near(v, 12500.0, 1e-6), v)
    h.check("H: undo list as before", list(App.ActiveDocument.UndoNames) == s["undo"])
    si.timeline_double_click("Sketch 1")


def h_second_edit():
    h.check("H: second edit from the timeline", h.in_sketch() is s["sk"])
    h.check("H: palette there again", si.palette() is not None and si.palette().isVisible())
    h.ribbon("Finish Sketch")


def h_nothing_changed():
    v = h.solid_volume()
    h.check("H: finishing without a change keeps the part", si.near(v, 12500.0, 1e-6), v)
    h.check("H: no feature broken", not invalid_objects(), invalid_objects())


def h_save_reopen():
    doc = App.ActiveDocument
    folder = tempfile.mkdtemp(prefix="sciforge-qa-")
    path = os.path.join(folder, "sketch_qa.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    App.openDocument(path)
    s["sk"] = [o for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"][0]


def h_reopened():
    h.fit()
    v = h.solid_volume()
    h.check("H: reopened file has the part", si.near(v, 12500.0, 1e-6), v)
    si.timeline_double_click("Sketch 1")


def h_edit_reopened():
    h.check("H: edit after reopening", h.in_sketch() is s["sk"])
    h.check("H: Fusion sketch mode after reopening", session() is not None)
    h.check("H: palette after reopening", si.palette() is not None)
    _double_click_dim(50.0)


def h_type_45():
    h.check("H: box after reopening", editor() is not None)
    si.type_text("45")


def h_finish_reopened():
    h.ribbon("Finish Sketch")


def h_after_reopen():
    v = h.solid_volume()
    h.check("H: 45 x 25 x 10 after reopening", si.near(v, 11250.0, 1e-6), v)
    h.shot("H-reopened-edited")


# == I: a broken profile ========================================================
def i_edit():
    si.timeline_double_click("Sketch 1")


def i_select():
    h.check("I: editing", h.in_sketch() is s["sk"])
    si.click(V(45, 12, 0))  # the right line


def i_delete():
    s["geo"] = len(s["sk"].Geometry)
    h.press(QtCore.Qt.Key_Delete)


# Deleting a line of the profile on purpose: FreeCAD notes that the Extrude lost its
# profile (kept in its message list, no balloon); that is expected here.
BROKEN = ("Sub shape not found", "InternalFace")
i_delete.notes_ok = BROKEN


def i_finish():
    h.check("I: Del deleted the line", len(s["sk"].Geometry) == s["geo"] - 1, s["sk"].Geometry)
    h.ribbon("Finish Sketch")


i_finish.notes_ok = BROKEN


def i_told():
    h.check("I: sketch closed", h.in_sketch() is None)
    h.check(
        "I: the message says what happened",
        "cannot be rebuilt" in si.tooltip(),
        si.tooltip(),
    )
    h.check("I: no pop-up", not h.popups(), h.popups())
    h.check("I: no balloon", not si.balloons(), si.balloons())
    h.shot("I-broken")
    h.press("z", QtCore.Qt.ControlModifier)


def i_back():
    v = h.solid_volume()
    h.check("I: one Ctrl+Z brings the part back", si.near(v, 11250.0, 1e-6), v)
    h.check("I: nothing broken after undo", not invalid_objects(), invalid_objects())
    h.check("I: the line is back", len(si.lines(s["sk"])) == 4, s["sk"].Geometry)


# == B: the dimension box refuses impossible values ===============================
def b_new():
    new_doc("SketchQA2")
    h.ribbon("Create Sketch")


def b_pick():
    h.click(V(12, -8, 0))


def b_circle():
    s["sk"] = h.in_sketch()
    h.check("B: sketch open", s["sk"] is not None)
    h.press("c")


def b_centre():
    si.click(V(10, 10, 0))


def b_radius():
    si.click(V(15, 10, 0))


def b_dim():
    esc()
    h.press("d")


def b_pick_circle():
    c = si.circles(s["sk"], construction=False)[0][1]
    s["c"] = c
    si.click(c.Center + V(c.Radius * math.cos(1.0), c.Radius * math.sin(1.0), 0))


def b_place():
    # away from every other curve (a placing click on a curve or an axis picks it instead)
    si.click(s["c"].Center + V(9, -2, 0))


def _box_says(what, needle):
    ed = editor()
    h.check("B: %s: the box stays open" % what, ed is not None)
    if ed is not None:
        text = ed.message.text()
        h.check("B: %s: the box says why" % what, needle in text, text)


def b_zero():
    h.check("B: dimension box for the circle", editor() is not None)
    s["d0"] = s["sk"].Geometry[0].Radius
    si.type_text("0")


def b_zero_check():
    _box_says("0", "more than 0")
    h.check(
        "B: 0 did not collapse the circle",
        si.near(s["sk"].Geometry[0].Radius, s["d0"]),
        s["sk"].Geometry[0],
    )
    si.type_text("-3")


def b_negative_check():
    _box_says("-3", "more than 0")
    si.type_text("abc")


def b_text_check():
    _box_says("abc", "Not a value")
    si.type_text("3 kg")


def b_unit_check():
    _box_says("3 kg", "length")
    si.type_text("6+4")


def b_expression_check():
    h.check("B: 6+4 accepted, the box closed", editor() is None)
    c = s["sk"].Geometry[0]
    h.check("B: diameter 10", si.near(c.Radius, 5.0, 1e-6), c)
    h.check("B: no error in the solver", s["sk"].solve() == 0)


def b_again():
    esc()
    esc()
    s["count"] = len(s["sk"].Constraints)
    h.press("d")


def b_again_pick():
    c = s["sk"].Geometry[0]
    si.click(c.Center + V(c.Radius * math.cos(2.5), c.Radius * math.sin(2.5), 0))


def b_again_place():
    si.click(s["sk"].Geometry[0].Center + V(7, 9, 0))


def b_driven():
    sk = s["sk"]
    h.check("B: a dimension was added", len(sk.Constraints) == s["count"] + 1, sk.Constraints)
    new = sk.Constraints[-1]
    h.check("B: on a size already set it is a driven dimension", not new.Driving, new)
    h.check("B: no value box for a driven dimension", editor() is None)
    h.check("B: a message says so", "driven" in si.tooltip(), si.tooltip())
    h.check(
        "B: the sketch is not over-constrained",
        sk.solve() == 0 and not sk.RedundantConstraints,
        sk.RedundantConstraints,
    )
    h.shot("B-driven")


# == C: Esc in the middle of things =================================================
def c_rect():
    esc()
    esc()
    s["geo"] = len(s["sk"].Geometry)
    h.press("r")


def c_first_corner():
    si.click(V(-30, -20, 0))


def c_esc():
    h.check("C: rectangle tool running", si.drawing())
    esc()


def c_after_esc():
    h.check("C: Esc after one corner draws nothing", len(s["sk"].Geometry) == s["geo"])
    h.check("C: Esc stops the tool", not si.drawing())
    h.check("C: the sketch stays open", h.in_sketch() is s["sk"])
    h.press("o")


def c_offset_waits():
    from sciforge import sketch_tools_ui

    h.check("C: Offset with nothing selected waits", sketch_tools_ui._WaitForCurve.current)
    h.check("C: no pop-up", not h.popups(), h.popups())
    esc()


def c_offset_stopped():
    from sciforge import sketch_tools_ui

    h.check("C: Esc stops Offset waiting", sketch_tools_ui._WaitForCurve.current is None)
    c = s["sk"].Geometry[0]
    si.click(c.Center + V(0, c.Radius, 0))


def c_click_after():
    h.check(
        "C: a click after Esc only selects (no offset)",
        len(s["sk"].Geometry) == s["geo"],
        s["sk"].Geometry,
    )
    esc()
    esc()
    s["ext"] = len(s["sk"].ExternalGeo)
    h.press("p")


def c_project_running():
    h.check("C: Project runs", si.drawing())
    esc()


def c_project_stopped():
    h.check("C: Esc stops Project", not si.drawing())
    h.check("C: nothing projected", len(s["sk"].ExternalGeo) == s["ext"])
    h.check("C: still in the sketch", h.in_sketch() is s["sk"])
    h.ribbon("Finish Sketch")


# == D: switching tools in the middle, E with a tool running ==========================
def d_new():
    h.check("C: finished", h.in_sketch() is None)
    new_doc("SketchQA3")
    h.ribbon("Create Sketch")


def d_pick():
    h.click(V(12, -8, 0))


def d_line():
    s["sk"] = h.in_sketch()
    h.press("l")


def d_one_click():
    si.click(V(-20, -10, 0))


def d_c():
    h.press("c")


def d_c_running():
    h.check("D: C ends the line tool: no half line", not si.lines(s["sk"]), s["sk"].Geometry)
    h.check("D: the circle tool runs", si.drawing())
    si.click(V(20, 15, 0))


def d_type_diameter():
    si.move_towards(V(26, 15.3, 0), X)
    si.type_text("20")


def d_circle():
    circles = si.circles(s["sk"], construction=False)
    h.check("D: one circle", len(circles) == 1, s["sk"].Geometry)
    if circles:
        h.check("D: typed diameter 20", si.near(circles[0][1].Radius, 10.0, 1e-6), circles)
    h.check("D: the circle tool still runs", si.drawing())
    h.press("e")


def d_extrude():
    from sciforge import extrude_ui

    h.check("D: E finished the sketch", h.in_sketch() is None)
    panel = extrude_ui.ExtrudePanel.last
    h.check(
        "D: Extrude took the circle",
        panel is not None and not panel._closed and len(panel.profiles) == 1,
        panel.profiles if panel else None,
    )
    h.task_button("OK")


def d_volume():
    v = h.solid_volume()
    h.check("D: cylinder pi*10^2*10", si.near(v, math.pi * 1000.0, 1e-6), v)
    h.fit()


# == E: the sketch's marking menu, Del, M ===========================================
def e_sketch():
    h.ribbon("Create Sketch")


def e_top():
    h.click(V(20, 15, 10))  # the top of the cylinder


def e_rect():
    s["sk"] = h.in_sketch()
    h.check("E: sketch on the cylinder's top", s["sk"] is not None)
    h.press("r")


def e_rect_a():
    si.click(V(14, 10, 10))


def e_rect_b():
    si.click(V(26, 20, 10))


def e_right_click():
    esc()
    esc()
    h.click(V(45, 45, 10), button=QtCore.Qt.RightButton)


def e_menu():
    labels = si.marking_labels()
    h.check("E: right click opens the marking menu", si.marking_menu() is not None)
    h.check("E: it is the sketch menu", "Finish Sketch" in labels and "Line" in labels, labels)
    h.check(
        "E: no part commands in a sketch",
        not {"Hole", "Press Pull", "Create Sketch"} & set(labels),
        labels,
    )
    h.shot("E-marking-menu")
    si.marking_slot("Line")


def e_line_running():
    from sciforge import recent

    h.check("E: Line from the marking menu runs", si.drawing())
    h.check("E: Repeat would repeat Line", recent.last()[0] == "SciForge_SketchLine")
    esc()
    esc()


def _side(pick):
    """Global middle point of the rectangle side `pick` chooses ("right" or "top")."""
    sk = s["sk"]
    lines = [g for _, g in si.lines(sk)]
    if pick == "right":
        g = max(lines, key=lambda g: g.StartPoint.x + g.EndPoint.x)
    else:
        g = max(lines, key=lambda g: g.StartPoint.y + g.EndPoint.y)
    return sk.getGlobalPlacement().multVec((g.StartPoint + g.EndPoint) * 0.5)


def e_select_line():
    s["geo"] = len(s["sk"].Geometry)
    si.click(_side("right"))


def e_del():
    h.press(QtCore.Qt.Key_Delete)


def e_deleted():
    h.check("E: Del deleted one sketch line", len(s["sk"].Geometry) == s["geo"] - 1)
    h.check("E: the sketch stays open", h.in_sketch() is s["sk"])
    h.press("z", QtCore.Qt.ControlModifier)


def e_undone():
    h.check("E: Ctrl+Z in the sketch brings it back", len(s["sk"].Geometry) == s["geo"])
    h.check("E: still in the sketch", h.in_sketch() is s["sk"])
    si.click(_side("top"))


def e_m():
    h.press("m")


def e_moving():
    from sciforge import recent

    h.check("E: M starts the sketch's Move/Copy", si.drawing())
    h.check("E: (the sketch command)", recent.last()[0] == "SciForge_SketchMove", recent.last())
    h.check("E: no pop-up", not h.popups(), h.popups())
    esc()
    esc()


def e_right_again():
    h.click(V(45, 45, 10), button=QtCore.Qt.RightButton)


def e_finish_from_menu():
    si.marking_slot("Finish Sketch")


def e_finished():
    h.check("E: Finish Sketch from the marking menu", h.in_sketch() is None)
    v = h.solid_volume()
    h.check("E: the cylinder is unchanged", si.near(v, math.pi * 1000.0, 1e-6), v)


# == F: construction mode ==========================================================
def f_new():
    new_doc("SketchQA4")
    h.ribbon("Create Sketch")


def f_pick():
    h.click(V(12, -8, 0))


def f_x():
    s["sk"] = h.in_sketch()
    h.press("x")


def _linetype():
    from PySide import QtWidgets

    pal = si.palette()
    return pal.findChild(QtWidgets.QToolButton, "SciForgePaletteConstruction") if pal else None


def f_x_shown():
    button = _linetype()
    h.check("F: palette Linetype shows construction", button is not None and button.isChecked())
    h.check("F: a message says new lines are construction", "construction" in si.tooltip())
    h.shot("F-construction")
    h.press("l")


def f_line_a():
    si.click(V(0, 0, 0))


def f_line_b():
    si.click(V(20, 0, 0))


def f_line_check():
    esc()
    sk = s["sk"]
    lines = si.lines(sk, construction=True)
    h.check("F: the line is construction", len(lines) == 1, sk.Geometry)
    h.ribbon("Finish Sketch")


def f_next():
    h.ribbon("Create Sketch")


def f_next_pick():
    h.click(V(12, -8, 0))


def f_next_open():
    s["sk2"] = h.in_sketch()
    button = _linetype()
    h.check(
        "F: the next sketch starts with normal lines",
        button is not None and not button.isChecked(),
    )
    h.press("l")


def f_next_a():
    si.click(V(0, 10, 0))


def f_next_b():
    si.click(V(20, 10, 0))


def f_next_check():
    esc()
    lines = si.lines(s["sk2"])
    h.check("F: normal line drawn", len(lines) == 1, s["sk2"].Geometry)
    h.ribbon("Finish Sketch")


# == G: sketch fillet with a typed radius =============================================
def g_new():
    new_doc("SketchQA5")
    h.ribbon("Create Sketch")


def g_pick():
    h.click(V(12, -8, 0))


def g_rect():
    s["sk"] = h.in_sketch()
    h.press("r")


def g_corner():
    si.click(V(0, 0, 0))


def g_size():
    si.move_towards(V(12, 9, 0), V(1, 1, 0) * 0.7)
    si.type_text("30", enter=False)
    si.tab()
    si.type_text("20")


def g_rect_check():
    esc()
    xs, ys = [], []
    for _, g in si.lines(s["sk"]):
        xs += [g.StartPoint.x, g.EndPoint.x]
        ys += [g.StartPoint.y, g.EndPoint.y]
    ok = xs and si.near(max(xs) - min(xs), 30.0) and si.near(max(ys) - min(ys), 20.0)
    h.check("G: typed rectangle 30 x 20", ok, (xs, ys))
    si.menu_item("MODIFY", "Fillet")


def g_click_corner():
    si.click(V(30, 20, 0))


def g_box():
    arcs = [g for g in s["sk"].Geometry if g.TypeId == "Part::GeomArcOfCircle"]
    h.check("G: the corner is rounded", len(arcs) == 1, s["sk"].Geometry)
    h.check("G: the radius box opens (Fusion asks for the radius)", editor() is not None)
    h.shot("G-fillet-box")
    si.type_text("4")


def g_radius():
    sk = s["sk"]
    arcs = [g for g in sk.Geometry if g.TypeId == "Part::GeomArcOfCircle"]
    h.check("G: radius 4", arcs and si.near(arcs[0].Radius, 4.0, 1e-6), arcs)
    radius = [c for c in sk.Constraints if c.Type == "Radius" and c.Driving]
    h.check("G: a radius dimension", len(radius) == 1 and si.near(radius[0].Value, 4.0), radius)
    h.check("G: solves", sk.solve() == 0)
    esc()
    esc()
    h.ribbon("Finish Sketch")


def g_extrude():
    h.fit()
    h.press("e")


def g_ok():
    h.task_button("OK")


def g_volume():
    v = h.solid_volume()
    expected = (600.0 - (16.0 - math.pi * 4.0)) * 10.0
    h.check("G: plate with one rounded corner", si.near(v, expected, 1e-6), (v, expected))
    h.shot("G-part")


h.run(
    "sketch_qa",
    si.watched(
        [
            # A
            a_new,
            a_create,
            a_pick,
            a_line,
            a_first,
            a_type_40,
            a_after_40,
            a_type_25,
            a_after_25,
            a_third,
            a_close,
            a_closed,
            a_finish,
            a_extrude,
            a_ok,
            a_volume,
            # H
            h_edit,
            h_dbl,
            h_type,
            h_finish,
            h_updated,
            h_undo,
            h_undone,
            h_redone,
            h_second_edit,
            h_nothing_changed,
            h_save_reopen,
            h_reopened,
            h_edit_reopened,
            h_type_45,
            h_finish_reopened,
            h_after_reopen,
            # I
            i_edit,
            i_select,
            i_delete,
            i_finish,
            i_told,
            i_back,
            # B
            b_new,
            b_pick,
            b_circle,
            b_centre,
            b_radius,
            b_dim,
            b_pick_circle,
            b_place,
            b_zero,
            b_zero_check,
            b_negative_check,
            b_text_check,
            b_unit_check,
            b_expression_check,
            b_again,
            b_again_pick,
            b_again_place,
            b_driven,
            # C
            c_rect,
            c_first_corner,
            c_esc,
            c_after_esc,
            c_offset_waits,
            c_offset_stopped,
            c_click_after,
            c_project_running,
            c_project_stopped,
            # D
            d_new,
            d_pick,
            d_line,
            d_one_click,
            d_c,
            d_c_running,
            d_type_diameter,
            d_circle,
            d_extrude,
            d_volume,
            # E
            e_sketch,
            e_top,
            e_rect,
            e_rect_a,
            e_rect_b,
            e_right_click,
            e_menu,
            e_line_running,
            e_select_line,
            e_del,
            e_deleted,
            e_undone,
            e_m,
            e_moving,
            e_right_again,
            e_finish_from_menu,
            e_finished,
            # F
            f_new,
            f_pick,
            f_x,
            f_x_shown,
            f_line_a,
            f_line_b,
            f_line_check,
            f_next,
            f_next_pick,
            f_next_open,
            f_next_a,
            f_next_b,
            f_next_check,
            # G
            g_new,
            g_pick,
            g_rect,
            g_corner,
            g_size,
            g_rect_check,
            g_click_corner,
            g_box,
            g_radius,
            g_extrude,
            g_ok,
            g_volume,
        ]
    ),
)
