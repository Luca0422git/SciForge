# SPDX-License-Identifier: LGPL-2.1-or-later
"""Box selection like Fusion (parity/selection.md), only real input on a 40 x 30 x 10 box.

A  a window (left to right) around the whole box: the faces and edges the camera sees
   (3 and 9: Select Through is off by default), no corner points (Fusion's box takes
   faces and edges); the box widget is gone after.
B  a click on empty space clears the selection (FreeCAD's own click).
C  a small crossing box (right to left) inside the top face: the top face alone.
   The same small box left to right (window): nothing is fully inside, nothing selected.
D  a small crossing box over the front-top edge: that edge and the two faces it bounds.
E  a window around the top face (its screen rectangle + 6 px): the top face, its 4
   edges and the two vertical edges that hang below the rectangle's left and right
   corners (8 screen units, the rectangle reaches 20 below them); the side faces, only
   partly inside, are not taken.
F  modifiers: Shift + crossing box over the front-top edge adds the front face to E's
   picks; Ctrl + the same box removes the edge and the two faces it crosses; a plain box
   replaces the selection.
G  Esc clears the selection; Esc while a box is being dragged cancels it (the box
   widget hides, the release selects nothing).
H  Select Through on: the window around the whole box takes the hidden faces and edges
   too (all 6 and 12); off again: back to 3 and 9.
I  Paint Selection (key 3): a stroke from the top face onto the front face selects both
   (and at most the edge between them); key 1 brings Window Selection back.
J  Freeform Selection (key 2): a lasso through the same corners selects what E did.
K  an empty design: a box drag selects nothing and prints no error.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as si

V = App.Vector
st = {}


def names():
    if "names" not in st:
        st["names"] = si.name_map()
    return st["names"]


def corners():
    box = h.body().Shape.BoundBox
    return [
        V(x, y, z)
        for x in (box.XMin, box.XMax)
        for y in (box.YMin, box.YMax)
        for z in (box.ZMin, box.ZMax)
    ]


def top_corners():
    return [V(0, 0, 10), V(40, 0, 10), V(40, 30, 10), V(0, 30, 10)]


def last():
    return si.selection_ui().last() or {}


# -- A -------------------------------------------------------------------------------------------
def a_window_whole_box():
    h.fit()
    si.box_around(corners(), margin=25)


def a_check():
    sel = si.selected_elements()
    faces = {n for n in sel if n.startswith("Face")}
    edges = {n for n in sel if n.startswith("Edge")}
    vertices = {n for n in sel if n.startswith("Vertex")}
    seen_faces, seen_edges = si.visible_elements()
    h.check("A Select Through is off to begin with", not si.selection_ui().select_through())
    h.check(
        "A the camera sees 3 faces and 9 edges of the box",
        (len(seen_faces), len(seen_edges)) == (3, 9),
        (seen_faces, seen_edges),
    )
    h.check(
        "A window around the box selects the 3 faces it shows", faces == seen_faces, sorted(sel)
    )
    h.check("A ... and the 9 edges it shows", edges == seen_edges, sorted(sel))
    h.check("A ... and no corner points", not vertices, sorted(vertices))
    h.check("A the selection came from a window box", last().get("mode") == "window", last())
    band = si.band()
    h.check("A the box widget is hidden again", band is not None and not band.isVisible())
    h.shot("A-window")


# -- B -------------------------------------------------------------------------------------------
def b_click_empty():
    h.click_empty()


def b_check():
    h.check("B a click on empty space clears the selection", not Gui.Selection.hasSelection())


# -- C -------------------------------------------------------------------------------------------
def c_crossing_inside_top():
    si.box_at(V(22, 16, 10), half=7, crossing=True)


def c_check():
    h.check(
        "C a crossing box inside the top face takes it",
        si.selected_elements() == {names()["top"]},
        si.selected(),
    )
    h.check("C ... as a crossing box", last().get("mode") == "crossing", last())


def c_window_inside_top():
    si.box_at(V(22, 16, 10), half=7, crossing=False)


def c_window_check():
    h.check(
        "C a window inside the top face takes nothing",
        not Gui.Selection.hasSelection(),
        si.selected(),
    )


# -- D -------------------------------------------------------------------------------------------
def d_crossing_front_top_edge():
    si.box_at(V(20, 0, 10), half=6, crossing=True)


def d_check():
    want = {names()["edge_front_top"], names()["top"], names()["front"]}
    h.check(
        "D a crossing box over the front-top edge: the edge and its two faces",
        si.selected_elements() == want,
        (si.selected(), want),
    )


# -- E -------------------------------------------------------------------------------------------
def e_window_top_face():
    si.box_around(top_corners(), margin=6)


def top_window_set():
    n = names()
    return {n["top"], n["edge_up_front_left"], n["edge_up_back_right"]} | n["top_edges"]


def e_check():
    want = top_window_set()
    h.check(
        "E a window around the top face: the face, its 4 edges, the 2 hanging edges",
        si.selected_elements() == want,
        (si.selected(), want),
    )
    st["e"] = set(si.selected_elements())


# -- F -------------------------------------------------------------------------------------------
def f_shift_adds():
    si.box_at(V(20, 0, 10), half=6, crossing=True, modifiers=si.SHIFT)


def f_shift_check():
    want = st.get("e", set()) | {names()["front"]}
    h.check(
        "F Shift + box adds (the front face joins E's picks)",
        si.selected_elements() == want,
        (si.selected(), want),
    )
    h.check("F ... the box said add", last().get("plan") == "add", last())


def f_ctrl_toggles():
    si.box_at(V(20, 0, 10), half=6, crossing=True, modifiers=si.CTRL)


def f_ctrl_check():
    want = (st.get("e", set()) | {names()["front"]}) - {
        names()["edge_front_top"],
        names()["top"],
        names()["front"],
    }
    h.check(
        "F Ctrl + box removes what it crosses that was selected",
        si.selected_elements() == want,
        (si.selected(), want),
    )
    h.check("F ... the box said toggle", last().get("plan") == "toggle", last())


def f_plain_replaces():
    si.box_at(V(20, 0, 10), half=6, crossing=True)


def f_plain_check():
    want = {names()["edge_front_top"], names()["top"], names()["front"]}
    h.check(
        "F a plain box replaces the selection",
        si.selected_elements() == want,
        (si.selected(), want),
    )


# -- G -------------------------------------------------------------------------------------------
def g_escape_clears():
    h.press(QtCore.Qt.Key_Escape)


def g_escape_check():
    h.check("G Esc clears the selection", not Gui.Selection.hasSelection(), si.selected())


def g_escape_mid_drag():
    pos = si.press_and_move(V(5, 5, 10), 90, 60)
    band = si.band()
    st["g_shown"] = band is not None and band.isVisible()
    h.press(QtCore.Qt.Key_Escape)
    st["g_hidden"] = band is not None and not band.isVisible()
    si.release_at(pos)


def g_mid_drag_check():
    h.check("G the box widget showed while dragging", st.get("g_shown"))
    h.check("G Esc hid the box", st.get("g_hidden"))
    h.check(
        "G ... and the release selected nothing", not Gui.Selection.hasSelection(), si.selected()
    )


# -- H -------------------------------------------------------------------------------------------
def h_through_on():
    Gui.runCommand("SciForge_SelectThrough")
    h.check("H Select Through is on", si.selection_ui().select_through())
    si.box_around(corners(), margin=25)


def h_through_check():
    sel = si.selected_elements()
    faces = {n for n in sel if n.startswith("Face")}
    edges = {n for n in sel if n.startswith("Edge")}
    h.check("H with Select Through the window takes all 6 faces", len(faces) == 6, sorted(sel))
    h.check("H ... and all 12 edges", len(edges) == 12, sorted(sel))
    h.shot("H-select-through")


def h_through_off():
    Gui.runCommand("SciForge_SelectThrough")
    h.check("H Select Through is off again", not si.selection_ui().select_through())
    si.box_around(corners(), margin=25)


def h_through_off_check():
    seen_faces, seen_edges = si.visible_elements()
    sel = si.selected_elements()
    h.check(
        "H without Select Through the window takes the 3 + 9 shown again",
        sel == seen_faces | seen_edges,
        (sorted(sel), sorted(seen_faces | seen_edges)),
    )
    h.click_empty()


# -- I -------------------------------------------------------------------------------------------
def i_paint_mode():
    h.press("3")
    h.check(
        "I key 3: Paint Selection", si.selection_ui().mode() == "paint", si.selection_ui().mode()
    )
    si.paint([V(20, 18, 10), V(20, 8, 10), V(20, 0, 7), V(20, 0, 3)])


def i_paint_check():
    sel = si.selected_elements()
    h.check("I the paint stroke selected the top face", names()["top"] in sel, sorted(sel))
    h.check("I ... and the front face", names()["front"] in sel, sorted(sel))
    allowed = {names()["top"], names()["front"], names()["edge_front_top"]}
    h.check("I ... and nothing else (at most the edge between them)", sel <= allowed, sorted(sel))
    h.check("I the last stroke was a paint", last().get("kind") == "paint", last())
    h.press("1")
    h.check(
        "I key 1: Window Selection again",
        si.selection_ui().mode() == "window",
        si.selection_ui().mode(),
    )
    h.click_empty()


# -- J -------------------------------------------------------------------------------------------
def j_freeform():
    h.press("2")
    h.check(
        "J key 2: Freeform Selection",
        si.selection_ui().mode() == "freeform",
        si.selection_ui().mode(),
    )
    si.lasso(top_corners(), margin=10)


def j_freeform_check():
    want = top_window_set()
    h.check(
        "J a lasso around the top face selects what the window did",
        si.selected_elements() == want,
        (si.selected(), want),
    )
    h.check(
        "J ... as a freeform window",
        last().get("shape") == "freeform" and last().get("mode") == "window",
        last(),
    )
    h.press("1")
    h.click_empty()


# -- K -------------------------------------------------------------------------------------------
def k_empty_design():
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    App.newDocument("SelEmpty")
    QtWidgets.QApplication.processEvents()
    gl = h.gl_widget()
    si.drag_box(
        gl.width() // 2 - 80, gl.height() // 2 - 60, gl.width() // 2 + 80, gl.height() // 2 + 60
    )
    si.drag_box(
        gl.width() // 2 - 80,
        gl.height() // 2 - 60,
        gl.width() // 2 + 80,
        gl.height() // 2 + 60,
        crossing=True,
    )


def k_check():
    h.check("K a box in an empty design selects nothing", not Gui.Selection.hasSelection())
    band = si.band()
    h.check("K ... and leaves no box widget shown", band is None or not band.isVisible())


steps = b.box_steps("SelBox") + [
    a_window_whole_box,
    a_check,
    b_click_empty,
    b_check,
    c_crossing_inside_top,
    c_check,
    c_window_inside_top,
    c_window_check,
    d_crossing_front_top_edge,
    d_check,
    e_window_top_face,
    e_check,
    f_shift_adds,
    f_shift_check,
    f_ctrl_toggles,
    f_ctrl_check,
    f_plain_replaces,
    f_plain_check,
    g_escape_clears,
    g_escape_check,
    g_escape_mid_drag,
    g_mid_drag_check,
    h_through_on,
    h_through_check,
    h_through_off,
    h_through_off_check,
    i_paint_mode,
    i_paint_check,
    j_freeform,
    j_freeform_check,
    k_empty_design,
    k_check,
]

h.run("selection_box", steps)
