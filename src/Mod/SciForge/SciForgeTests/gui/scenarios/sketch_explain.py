# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch constraints that explain themselves (sketch_explain.py), with real input only.

A  Fully constrained, visible: R, click the origin, click (40, 20): a rectangle; the Sketch
   Palette says "2 left to define", no padlock in the browser or the timeline. Sketch
   Dimension on the bottom line, type 40; on the right line, type 20: the palette says
   "Fully constrained" and the sketch's browser row and timeline icon get the padlock
   (they look different, and their tooltips say so).
B  A conflict from FreeCAD's own tool: Equal, click the bottom line, then the right line.
   Fusion refuses it: no Equal is added, the message beside the pointer names the 40 mm and
   the 20 mm dimensions, and those two are highlighted (selected) in the sketch; Esc (the
   next key) ends the highlight.
C  A repeat: Parallel, click the bottom then the top line: not added, "the Horizontal on
   Line ... and the Horizontal on Line ... already make it so".
D  SciForge's own pick tool: Collinear, click the bottom then the top line: refused, the
   hint names the 20 mm dimension, highlighted.
E  A dimension on a size already set: Sketch Dimension on the top line: a driven
   dimension; the message names the 40 mm dimension, highlighted.
F  A value that does not fit: the left line carries a second, driving 20 mm (a sketch made
   before SciForge refused repeats); double-click it, type 25: the box stays open, says it
   conflicts with the 20 mm dimension, which is highlighted; the value stays 20.
G  Finish Sketch: the padlock stays on the timeline icon and the browser row.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = st.s


def sk():
    return st.sketch()


def explain():
    from sciforge import sketch_explain

    return sketch_explain


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


def freedom_text():
    pal = si.palette()
    label = pal.findChild(QtWidgets.QLabel, "SciForgePaletteFreedom") if pal else None
    return label.text() if label is not None else None


def browser_item():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    tree.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    return tree, tree.item_for("sketch:" + sk().Name)


def browser_locked():
    from sciforge.browser_ui import ROLE_NODE

    _tree, item = browser_item()
    node = item.data(1, ROLE_NODE) if item is not None else None
    return bool(node and node.get("locked")), (item.toolTip(1) if item is not None else "")


def browser_icon_image():
    """The pixels of the sketch row's icon corner (where the padlock goes)."""
    tree, item = browser_item()
    if item is None:
        return None
    rect = tree.visualItemRect(item)
    tree.scrollToItem(item)
    return tree.viewport().grab(QtCore.QRect(rect.left(), rect.top(), 80, rect.height())).toImage()


def timeline_button():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    return widget.button(sk().Name)


def line_at(y, vertical=False, x=None):
    """Index of the rectangle's horizontal line at height y (or vertical line at x)."""
    for i, g in si.lines(sk()):
        a, b = g.StartPoint, g.EndPoint
        if not vertical and abs(a.y - y) < 1e-6 and abs(b.y - y) < 1e-6:
            return i
        if vertical and abs(a.x - x) < 1e-6 and abs(b.x - x) < 1e-6:
            return i
    return None


def dims(value):
    return [
        i
        for i, c in enumerate(sk().Constraints)
        if c.Type in ("Distance", "DistanceX", "DistanceY")
        and c.Driving
        and abs(abs(c.Value) - value) < 1e-6
    ]


def selected_constraints():
    found = []
    for sel in Gui.Selection.getSelectionEx():
        for name in sel.SubElementNames:
            name = name.rsplit(".", 1)[-1]
            if name.startswith("Constraint"):
                found.append(int(name[len("Constraint") :]) - 1)
    return sorted(found)


def esc():
    st.esc()


def rings_on(indices, where):
    """A red ring is drawn over each of these dimensions' values in the 3D view."""
    from sciforge import sketch_mode

    session = sketch_mode.current()
    rings = explain().highlight_rings()
    labels = [session.label_pixel(i) for i in indices]
    near = [
        any(abs(x - p.x()) <= 3 and abs(y - p.y()) <= 3 for x, y in rings)
        for p in labels
        if p is not None
    ]
    h.check(
        "%s: a ring on each one's value in the view" % where,
        len(near) == len(indices) and all(near),
        (rings, [(p.x(), p.y()) for p in labels if p is not None]),
    )


# == A: fully constrained, visible ========================================================
def a_rect():
    h.press("r")


def a_corner():
    st.click(V(0, 0, 0))


def a_opposite():
    st.click(V(40, 20, 0))


def a_rect_check():
    esc()
    h.check("A: a rectangle (4 lines)", len(si.lines(sk())) == 4, sk().Geometry)
    s["bottom"] = line_at(0.0)
    s["right"] = line_at(None, vertical=True, x=sk().Geometry[s["bottom"]].EndPoint.x)
    h.check("A: the rectangle sits on the origin", sk().DoF == 2, sk().DoF)


a_rect_check.wait_ms = 900


def a_not_locked():
    text = freedom_text()
    h.check("A: the palette says 2 left to define", text == "2 left to define", text)
    locked, tip = browser_locked()
    h.check("A: no padlock in the browser yet", not locked, tip)
    button = timeline_button()
    h.check("A: the sketch is in the timeline", button is not None)
    h.check(
        "A: no padlock on its timeline icon yet",
        button is not None and button.property("locked") == "false",
    )
    s["browser_before"] = browser_icon_image()
    s["timeline_before"] = button.grab().toImage() if button is not None else None


def a_dim_width():
    h.press("d")


def a_pick_bottom():
    st.click(V(20, 0, 0))


def a_place_bottom():
    st.click(V(20, -8, 0))


def a_type_40():
    si.type_text("40")


def a_dim_height():
    esc()
    h.press("d")


def a_pick_right():
    x = sk().Geometry[s["right"]].StartPoint.x
    st.click(V(x, 10, 0))


def a_place_right():
    x = sk().Geometry[s["right"]].StartPoint.x
    st.click(V(x + 8, 10, 0))


def a_type_20():
    si.type_text("20")


def a_locked():
    esc()
    h.check("A: the width is 40 and the height 20", len(dims(40)) == 1 and len(dims(20)) == 1)
    h.check("A: nothing left to move", sk().DoF == 0 and sk().solve() == 0, sk().DoF)


a_locked.wait_ms = 900


def a_padlock():
    text = freedom_text()
    h.check("A: the palette says Fully constrained", text == "Fully constrained", text)
    locked, tip = browser_locked()
    h.check("A: the padlock in the browser", locked, tip)
    h.check("A: the browser row's tooltip says so", "Fully constrained" in tip, tip)
    after = browser_icon_image()
    h.check(
        "A: the browser row looks different (the padlock is drawn)",
        after is not None and s.get("browser_before") is not None and after != s["browser_before"],
    )
    button = timeline_button()
    h.check(
        "A: the padlock on the timeline icon",
        button is not None and button.property("locked") == "true",
        button and button.property("locked"),
    )
    h.check(
        "A: the timeline tooltip says so",
        button is not None and "Fully constrained" in button.toolTip(),
        button and button.toolTip(),
    )
    h.check(
        "A: the timeline icon looks different",
        button is not None and button.grab().toImage() != s.get("timeline_before"),
    )
    h.shot("A-padlock")


# == B: a conflict from FreeCAD's own tool =================================================
def b_equal():
    s["count"] = len(sk().Constraints)
    si.menu_item("CONSTRAINTS", "Equal")


def b_pick_bottom():
    st.click(V(10, 0, 0))


def b_pick_right():
    x = sk().Geometry[s["right"]].StartPoint.x
    st.click(V(x, 6, 0))


def b_check():
    cons = sk().Constraints
    h.check(
        "B: no Equal was added",
        len(cons) == s["count"] and not any(c.Type == "Equal" for c in cons),
        [c.Type for c in cons],
    )
    text = told()
    h.check("B: the message says it was not added", "Equal: not added" in text, text)
    h.check(
        "B: and names the two dimensions it fights",
        "the 40 mm dimension" in text and "the 20 mm dimension" in text,
        text,
    )
    want = sorted(dims(40) + dims(20))
    h.check(
        "B: those two are highlighted", explain().highlighted() == want, explain().highlighted()
    )
    rings_on(want, "B")
    h.check("B: still fully constrained", sk().solve() == 0 and sk().DoF == 0)
    h.shot("B-conflict")
    esc()


def b_cleared():
    h.check("B: the next key ends the highlight", explain().highlighted() == [])
    h.check("B: the rings are gone", explain().highlight_rings() == [])
    h.check("B: and the selection", selected_constraints() == [], selected_constraints())
    esc()


# == C: a repeat ===========================================================================
def c_parallel():
    s["count"] = len(sk().Constraints)
    si.menu_item("CONSTRAINTS", "Parallel")


def c_pick_bottom():
    st.click(V(14, 0, 0))


def c_pick_top():
    st.click(V(14, 20, 0))


def c_check():
    cons = sk().Constraints
    h.check(
        "C: no Parallel was added",
        len(cons) == s["count"] and not any(c.Type == "Parallel" for c in cons),
        [c.Type for c in cons],
    )
    text = told()
    h.check("C: the message says what already makes it so", "already make it so" in text, text)
    h.check("C: the two Horizontals", text.count("the Horizontal on Line") == 2, text)
    horizontals = sorted(i for i, c in enumerate(cons) if c.Type == "Horizontal")
    h.check(
        "C: the Horizontals are highlighted",
        explain().highlighted() == horizontals,
        (explain().highlighted(), horizontals),
    )
    esc()
    esc()


# == D: SciForge's own pick tool ==============================================================
def d_collinear():
    s["count"] = len(sk().Constraints)
    si.menu_item("CONSTRAINTS", "Collinear")


def d_pick_bottom():
    h.check("D: Collinear runs", st.tool_title() == "Collinear", st.tool_title())
    st.click(V(26, 0, 0))


def d_pick_top():
    st.click(V(26, 20, 0))


def d_check():
    t = st.tool()
    text = (t.hint_text() if t is not None else "") or told()
    h.check("D: refused", "Collinear: not added, it conflicts with" in text, text)
    h.check("D: names the 20 mm dimension", "the 20 mm dimension" in text, text)
    h.check("D: nothing added", len(sk().Constraints) == s["count"])
    h.check(
        "D: the 20 mm dimension is highlighted",
        set(dims(20)) <= set(explain().highlighted()),
        explain().highlighted(),
    )
    rings_on(dims(20), "D")
    h.check(
        "D: ...and selected in the sketch (SciForge's tool lets constraints be selected)",
        set(dims(20)) <= set(selected_constraints()),
        selected_constraints(),
    )
    esc()
    esc()


# == E: a dimension on a size already set ======================================================
def e_dim():
    s["count"] = len(sk().Constraints)
    h.press("d")


def e_pick_top():
    st.click(V(30, 20, 0))


def e_place():
    st.click(V(30, 28, 0))


def e_check():
    cons = sk().Constraints
    h.check("E: a dimension was added", len(cons) == s["count"] + 1, [c.Type for c in cons])
    new = cons[-1]
    h.check("E: it is a driven dimension", not new.Driving, new)
    text = told()
    h.check("E: the message names the 40 mm dimension", "the 40 mm dimension" in text, text)
    h.check(
        "E: the 40 mm dimension is highlighted",
        set(dims(40)) <= set(explain().highlighted()),
        explain().highlighted(),
    )
    rings_on(dims(40), "E")
    esc()
    esc()


# == F: a value that does not fit ===============================================================
def f_old_sketch():
    import Sketcher

    left = line_at(None, vertical=True, x=0.0)
    s["left"] = left
    # a sketch made before SciForge refused repeats: the left side carries its own driving
    # 20 mm (FreeCAD keeps such a sketch, redundant)
    s["left_dim"] = sk().addConstraint(Sketcher.Constraint("Distance", left, 20.0))
    sk().solve()
    App.ActiveDocument.recompute()


# the setup recomputes a sketch FreeCAD calls redundant: its own note about it is expected
f_old_sketch.notes_ok = ("redundant constraint",)


def f_open_box():
    point = si.dimension_label(sk(), s["left_dim"])
    h.double_click(point)


def f_type():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    h.check("F: the dimension box is open", session is not None and session.editor is not None)
    si.type_text("25")


def f_check():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    ed = session.editor if session is not None else None
    h.check("F: the box stays open", ed is not None)
    text = ed.reason() if ed is not None else ""
    h.check("F: it says the value conflicts", "That value does not fit" in text, text)
    h.check("F: and with what", "the 20 mm dimension" in text, text)
    right = dims(20)
    h.check(
        "F: the other 20 mm dimension is highlighted",
        bool(set(right) & set(explain().highlighted())),
        (right, explain().highlighted()),
    )
    h.check(
        "F: ...selected in the sketch",
        bool(set(right) & set(selected_constraints())),
        selected_constraints(),
    )
    h.check("F: the value stayed 20", abs(sk().getDatum(s["left_dim"]).Value - 20) < 1e-9)
    h.shot("F-value")
    esc()


def f_closed():
    sk().delConstraint(s["left_dim"])  # back to the plain rectangle
    sk().solve()
    App.ActiveDocument.recompute()


# == G: after Finish Sketch ======================================================================
def g_finish():
    h.ribbon("Finish Sketch")


def g_check():
    h.check("G: the sketch is closed", h.in_sketch() is None)
    locked, tip = browser_locked()
    h.check("G: the padlock stays in the browser", locked, tip)
    button = timeline_button()
    h.check(
        "G: and on the timeline icon",
        button is not None and button.property("locked") == "true",
    )
    h.shot("G-finished")


g_check.wait_ms = 900

h.run(
    "sketch_explain",
    si.watched(
        st.start_steps("SketchExplain")
        + [
            a_rect,
            a_corner,
            a_opposite,
            a_rect_check,
            a_not_locked,
            a_dim_width,
            a_pick_bottom,
            a_place_bottom,
            a_type_40,
            a_dim_height,
            a_pick_right,
            a_place_right,
            a_type_20,
            a_locked,
            a_padlock,
            b_equal,
            b_pick_bottom,
            b_pick_right,
            b_check,
            b_cleared,
            c_parallel,
            c_pick_bottom,
            c_pick_top,
            c_check,
            d_collinear,
            d_pick_bottom,
            d_pick_top,
            d_check,
            e_dim,
            e_pick_top,
            e_place,
            e_check,
            f_old_sketch,
            f_open_box,
            f_type,
            f_check,
            f_closed,
            g_finish,
            g_check,
        ]
    ),
)
