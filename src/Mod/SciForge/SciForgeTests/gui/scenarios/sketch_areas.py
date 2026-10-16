# SPDX-License-Identifier: LGPL-2.1-or-later
"""Picking one closed area of a sketch with several (Luca: "if I have multiple closed off
areas of a sketch, I want to be able to select a specific part of the sketch"), only real
input. Fusion's behaviour:

After Finish Sketch (no command running):
- every closed area is shaded and lights up under the mouse; a click selects it
  (FreeCAD's sketch areas, "InternalFaceN", made because SciForge turns them on);
- E then extrudes exactly the clicked area; Ctrl+click adds a second one, E takes both;
- Q with two areas selected opens Extrude with both (it took only the first);
- the whole sketch selected in the browser + E: its areas (it took nothing);
- Q with only sketch areas and no solid says "click a sketch area", not "make a solid".

Inside the open sketch (no drawing tool running):
- the area under the mouse lights up; a click picks it (stronger blue), a second click
  drops it, Shift/Ctrl+click adds, Ctrl+click a picked one drops it;
- a plain click on a curve or on empty space, or Esc, drops the picked areas;
- E extrudes exactly the picked areas (both, or only B), Q too (as an Extrude).

Two squares on XY: A = 0..20 x 0..20, B = 30..50 x 0..20, so each area is 400 mm^2 and
the default 10 mm extrude of one is 4000 mm^3, of both 8000."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
CTRL, SHIFT = QtCore.Qt.ControlModifier, QtCore.Qt.ShiftModifier
A, B = V(10, 10, 0), V(40, 10, 0)  # the middles of the two squares
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def open_panel():
    p = panel()
    return p if p is not None and not p._closed and Gui.Control.activeDialog() else None


def area_name(point, sketch=None):
    """ "InternalFaceN" of the finished sketch's area around a global point. Read from the
    sketch as it is (SciForge's extrude.regions would turn the areas on by itself)."""
    from sciforge import profile_pick

    sketch = sketch or s["sketch"]
    shape = sketch.InternalShape
    if shape.isNull():
        return None
    placement = sketch.getGlobalPlacement()
    for i, face in enumerate(shape.Faces, start=1):
        face = face.copy()
        face.Placement = placement.multiply(face.Placement)
        if profile_pick.inside(face, point):
            return "InternalFace%d" % i
    return None


def profile_names():
    p = open_panel()
    return sorted(sub for _obj, sub in (p.profiles if p else []))


def selection():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def area_at(point):
    """Index of the open sketch's area around a global point."""
    from sciforge import sketch_areas_core as core

    x, y = h.to_sketch(s["sketch"], point)
    return core.region_at(session().areas.regions, x, y)


def picked():
    ses = session()
    return ses.areas.picked_indices() if ses is not None else None


def highlighted():
    """Points drawn in the picked-areas highlight of the open sketch."""
    ses = session()
    return ses.areas.picked_layer[0].point.getNum() if ses is not None else -1


def cancel():
    h.task_button("Cancel")


def step_button(name):
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.name == name:
            return button
    h.check("timeline has %r" % name, False, widget.titles())
    return None


# -- the sketch ---------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Areas")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk
    h.check("a new sketch makes FreeCAD's areas (MakeInternals)", sk.MakeInternals)
    h.draw_rectangle(sk, 0, 0, 20, 20)
    h.draw_rectangle(sk, 30, 0, 50, 20)


def finish():
    h.ribbon("Finish Sketch")


def finished():
    sk = s["sketch"]
    h.check("left the sketch", h.in_sketch() is None)
    faces = len(sk.InternalShape.Faces) if not sk.InternalShape.isNull() else 0
    h.check("the finished sketch has its two areas", faces == 2, faces)
    h.fit()
    s["A"], s["B"] = area_name(A), area_name(B)
    h.check("A and B are two areas", s["A"] and s["B"] and s["A"] != s["B"], (s["A"], s["B"]))
    h.move(h.screen_point(B))


# -- after Finish Sketch: FreeCAD's selection --------------------------------------------
def hover_b():
    pre = Gui.Selection.getPreselection()
    names = [n.split(".")[-1] for n in pre.SubElementNames if n]
    h.check("B lights up under the mouse", names == [s["B"]], (pre.ObjectName, names))
    h.click(B)


def b_selected():
    h.check(
        "a click inside B selects B", selection() == [(s["sketch"].Name, [s["B"]])], selection()
    )
    h.shot("1-b-selected")
    h.press("e")


def e_takes_b():
    p = open_panel()
    h.check("E opens Extrude", p is not None)
    h.check("E extrudes exactly B", profile_names() == [s["B"]], profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("B 10 mm: 4000", near(h.solid_volume(), 4000.0), h.solid_volume())
    cancel()


def click_a_ctrl_b():
    h.check("Cancel leaves no solid", near(h.solid_volume(), 0.0), h.solid_volume())
    h.click(A)
    h.click(B, CTRL)


def two_selected():
    names = sorted(sum((subs for _o, subs in selection()), []))
    h.check("Ctrl+click adds B to A", names == sorted([s["A"], s["B"]]), selection())
    h.press("e")


def e_takes_both():
    h.check("E extrudes A and B", profile_names() == sorted([s["A"], s["B"]]), profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("A + B 10 mm: 8000", near(h.solid_volume(), 8000.0), h.solid_volume())
    h.click(B)


def b_dropped_in_dialog():
    h.check("clicking B in the dialog drops it", profile_names() == [s["A"]], profile_names())
    h.check("A only: 4000", near(h.solid_volume(), 4000.0), h.solid_volume())
    cancel()


def select_two_for_q():
    h.fit()
    h.click(A)
    h.click(B, CTRL)


def press_q():
    names = sorted(sum((subs for _o, subs in selection()), []))
    h.check("A and B selected for Q", names == sorted([s["A"], s["B"]]), selection())
    s["extrude_before_q"] = panel()
    h.press("q")


def q_takes_both():
    p = open_panel()
    h.check("Q on sketch areas opens Extrude", p is not None and p is not s["extrude_before_q"])
    h.check("Q extrudes both areas", profile_names() == sorted([s["A"], s["B"]]), profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("A + B: 8000", near(h.solid_volume(), 8000.0), h.solid_volume())
    cancel()


def select_sketch_in_browser():
    h.fit()
    Gui.Selection.clearSelection()
    ti.click_row(s["sketch"].Label)


def whole_sketch_e():
    h.check("the whole sketch is selected", selection() == [(s["sketch"].Name, [])], selection())
    h.press("e")


def whole_sketch_taken():
    h.check(
        "E with the whole sketch selected takes its areas",
        profile_names() == sorted([s["A"], s["B"]]),
        profile_names(),
    )
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("both areas: 8000", near(h.solid_volume(), 8000.0), h.solid_volume())
    cancel()


def q_nothing_selected():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.press("q")


def q_hint():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    h.check("Q opens Press Pull", p is not None and not p._closed)
    if p is None:
        return
    h.check(
        "no 'make a solid' error: sketch areas can be used",
        p.message.text() == "",
        p.message.text(),
    )
    h.check("it says to click a sketch area", "sketch area" in p.what.text(), p.what.text())
    h.shot("2-q-hint")
    h.click(B)


def q_click_area():
    p = open_panel()
    h.check("clicking B in Press Pull extrudes B", profile_names() == [s["B"]], profile_names())
    cancel()


# -- inside the open sketch: SciForge's picks --------------------------------------------
def open_sketch():
    w.double_click(step_button(s["sketch"].Name))


def in_sketch_hover():
    h.check("the sketch is open again", h.in_sketch() is s["sketch"], h.in_sketch())
    for f in (3.0, 1.5, 0.5):
        h.move(h.screen_point(A + V(1.0, 0.6, 0) * f))
    h.move(h.screen_point(A))
    QtCore.QTimer.singleShot(120, hover_seen)


def hover_seen():
    ses = session()
    hov = ses.areas.hovered if ses else None
    s["hover_ok"] = hov is not None and hov == area_at(A)
    s["hover_drawn"] = ses.areas.hover_layer[0].point.getNum() if ses else 0


def in_sketch_click_a():
    h.check("A lights up under the mouse in the sketch", s.get("hover_ok"), s.get("hover_drawn"))
    h.check("the light-up is drawn", s.get("hover_drawn", 0) > 0, s.get("hover_drawn"))
    si.click(A)


def a_picked():
    h.check("a click inside A picks A", picked() == [area_at(A)], picked())
    h.check("the picked area is drawn in the picked blue", highlighted() > 0, highlighted())
    h.check("FreeCAD selects no curve", selection() == [], selection())
    h.shot("3-a-picked-in-sketch")
    si.click(A + V(3, 2, 0))


def a_dropped():
    h.check("clicking A again drops it", picked() == [], picked())
    h.check("nothing drawn as picked", highlighted() == 0, highlighted())
    si.click(A)


def shift_b():
    si.click_held(B, SHIFT)


def both_picked():
    h.check("Shift+click adds B", picked() == [area_at(A), area_at(B)], picked())
    si.click_held(B, CTRL)


def ctrl_drops_b():
    h.check("Ctrl+click on B drops it again", picked() == [area_at(A)], picked())
    si.click(V(10, 0, 0))  # A's bottom line


def curve_click_clears():
    h.check("a click on a curve drops the picked areas", picked() == [], picked())
    names = sum((subs for _o, subs in selection()), [])
    h.check("and selects the curve", any(n.startswith("Edge") for n in names), selection())
    si.click(A)


def empty_click():
    h.check("A picked again", picked() == [area_at(A)], picked())
    si.click(V(25, 30, 0))  # outside both squares


def empty_click_clears():
    h.check("a click on empty space drops the picked areas", picked() == [], picked())
    si.click(B)


def press_esc():
    h.check("B picked", picked() == [area_at(B)], picked())
    h.press(QtCore.Qt.Key_Escape)


def esc_clears():
    h.check("Esc drops the picked areas", picked() == [], picked())
    si.click(A)


def ctrl_b_then_e():
    si.click_held(B, CTRL)


def press_e_in_sketch():
    h.check("A and B picked", picked() == [area_at(A), area_at(B)], picked())
    h.press("e")


def e_in_sketch_takes_both():
    h.check("E left the sketch", h.in_sketch() is None)
    h.check(
        "E in the sketch extrudes the picked A and B",
        profile_names() == sorted([s["A"], s["B"]]),
        profile_names(),
    )
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("A + B: 8000", near(h.solid_volume(), 8000.0), h.solid_volume())
    cancel()


def reopen_for_b():
    h.check(
        "Cancel after E in the sketch leaves the sketch shown (Fusion: hidden only on OK)",
        s["sketch"].ViewObject.Visibility,
    )
    w.double_click(step_button(s["sketch"].Name))


def pick_only_b():
    h.check("the sketch is open again", h.in_sketch() is s["sketch"], h.in_sketch())
    si.click(B)


def e_only_b():
    h.check("only B picked", picked() == [area_at(B)], picked())
    h.press("e")


def b_only_extruded():
    h.check("E in the sketch extrudes only B", profile_names() == [s["B"]], profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.check("B only: 4000", near(h.solid_volume(), 4000.0), h.solid_volume())
    h.task_button("OK")


def reopen_for_q():
    h.check("B extruded", near(h.solid_volume(), 4000.0), h.solid_volume())
    w.double_click(step_button(s["sketch"].Name))


def pick_a_for_q():
    h.check("the sketch is open again", h.in_sketch() is s["sketch"], h.in_sketch())
    si.click(A)


def press_q_in_sketch():
    h.check("A picked", picked() == [area_at(A)], picked())
    s["extrude_before_q"] = panel()
    h.press("q")


def q_in_sketch_takes_a():
    p = open_panel()
    h.check(
        "Q in the sketch with A picked opens Extrude",
        p is not None and p is not s["extrude_before_q"],
    )
    h.check("on exactly A", profile_names() == [s["A"]], profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    p = panel()
    op = p.operation.currentText() if p is not None else None
    h.check("A touches no body: a new body of its own (Fusion)", op == "New Body", op)
    h.check("A + B: 8000 in all", near(all_volume(), 8000.0), all_volume())
    h.task_button("OK")


def all_volume():
    """The volume of every shown body (A away from B is a body of its own)."""
    total = 0.0
    for obj in App.ActiveDocument.Objects:
        if obj.TypeId == "PartDesign::Body" and obj.ViewObject.Visibility:
            if not obj.Shape.isNull():
                total += obj.Shape.Volume
    return total


def done():
    h.check("two extrudes: A and B, 8000", near(all_volume(), 8000.0), all_volume())
    h.fit()
    h.shot("4-end")


h.run(
    "sketch_areas",
    si.watched(
        [
            new_design,
            pick_xy,
            draw,
            finish,
            finished,
            hover_b,
            b_selected,
            e_takes_b,
            click_a_ctrl_b,
            two_selected,
            e_takes_both,
            b_dropped_in_dialog,
            select_two_for_q,
            press_q,
            q_takes_both,
            select_sketch_in_browser,
            whole_sketch_e,
            whole_sketch_taken,
            q_nothing_selected,
            q_hint,
            q_click_area,
            open_sketch,
            in_sketch_hover,
            in_sketch_click_a,
            a_picked,
            a_dropped,
            shift_b,
            both_picked,
            ctrl_drops_b,
            curve_click_clears,
            empty_click,
            empty_click_clears,
            press_esc,
            esc_clears,
            ctrl_b_then_e,
            press_e_in_sketch,
            e_in_sketch_takes_both,
            reopen_for_b,
            pick_only_b,
            e_only_b,
            b_only_extruded,
            reopen_for_q,
            pick_a_for_q,
            press_q_in_sketch,
            q_in_sketch_takes_a,
            done,
        ]
    ),
)
