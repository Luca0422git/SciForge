# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Plane Cut on an inserted box (20 x 10 x 5, 1000 mm3); only real input.

A  MESH > Plane Cut, click the box: the Plane box waits and the three origin planes show as
   squares; the body is not cut yet.
B  Click the XY square: the plane lies under the box, so the dialog says it does not cut the
   body and OK waits (a refusal with its reason).
C  Distance 2 (typed): Trim takes away the part above, the cut is closed (Uniform fill):
   400 mm3, closed.
D  Flip: the part below goes instead: 600 mm3.
E  The plane's arrow dragged up: Distance follows (about 3), the cut follows.
F  Fill Type Minimal: closed, fewer faces than Uniform; No Fill: an open hole.
G  X Angle 20 (typed): the tilted cut is still closed, the volume as worked out by hand.
H  Type Split Body (X Angle 0, Distance 2, Uniform): two bodies, 400 + 600 mm3, both closed,
   "box_20x10x5" and "box_20x10x5 (2)" in the browser.
I  OK: "Plane Cut 1" in the timeline, the inserted box used up.
J  Timeline double-click Plane Cut 1: the dialog with Split Body; Type Trim: one body again;
   OK: one body of 400 mm3 (the second body gone with its piece).
K  Ctrl+Z: split again (two bodies); Ctrl+Y: trimmed.
L  Plane Cut again, the body, XY, Distance 1, Cancel: the body as it was (400 mm3, one Plane
   Cut step).
"""

import math

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

V = App.Vector
NAME = "box_20x10x5"
state = {}


def box():
    return m.body(NAME)


def cut():
    found = m.steps("MeshPlaneCut")
    return found[0] if found else None


def kept():
    """The body the cut leaves (Trim: the step itself; Split Body: its first piece)."""
    return m.body(NAME)


# -- A ----------------------------------------------------------------------------------------
def a_open():
    m.mesh_tab()
    h.fit()
    h.ribbon("Plane Cut")


def a_click_body():
    p = m.panel()
    h.check("Plane Cut dialog", p is not None and p.title == "Plane Cut", p)
    s.no_popups("Plane Cut")
    m.click_body(box())


a_click_body.wait_ms = 1500


def a_waits_for_plane():
    p = m.panel()
    h.check("the Body box names the box", p is not None and NAME in p.fields["body"].button.text())
    h.check("the Plane box waits", p is not None and p.active == "plane", p and p.active)
    h.check("origin squares shown", p is not None and p.squares is not None)
    step = cut()
    h.check("a Plane Cut step", step is not None)
    h.check(
        "not cut yet",
        step is not None and i.close(m.volume(step), 1000.0, 1e-6),
        step and m.volume(step),
    )


# -- B ----------------------------------------------------------------------------------------
def b_click_xy():
    p = m.panel()
    # a point on the XY square away from the box (the box is 0..20 x 0..10 x 0..5)
    h.click(p.squares.point_on("XY", -0.7, -0.7))


b_click_xy.wait_ms = 1500


def b_refused():
    p = m.panel()
    h.check("the plane is picked", p is not None and p.frame is not None, p and p.frame)
    h.check(
        "the Plane box names XY",
        p is not None and "XY" in p.plane_field.button.text(),
        p and p.plane_field.button.text(),
    )
    h.check("handles shown", p is not None and "distance" in p.handles, p and list(p.handles))
    text = p.message.text() if p else ""
    h.check("the dialog says the plane does not cut the body", "does not cut" in text, text)
    h.task_button("OK")


b_refused.wait_ms = 1200


def b_still_open():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Plane Cut", p)


# -- C ----------------------------------------------------------------------------------------
def c_distance():
    m.type_field(m.panel().distance, "2")


c_distance.wait_ms = 2000


def c_check():
    p = m.panel()
    step = cut()
    h.check("no message", p.message.text() == "", p.message.text())
    h.check("Trim keeps the 400 mm3 below", i.close(m.volume(step), 400.0, 1e-4), m.volume(step))
    h.check("the cut is closed", m.closed(step), m.analysis(step))
    state["uniform_faces"] = m.facets(step)
    lo = step.Mesh.BoundBox
    h.check("up to z = 2", abs(lo.ZMax - 2.0) < 1e-4, lo.ZMax)


# -- D ----------------------------------------------------------------------------------------
def d_flip():
    m.tick(m.panel().flip, True)


d_flip.wait_ms = 2000


def d_check():
    step = cut()
    h.check("Flip: the 600 mm3 above", i.close(m.volume(step), 600.0, 1e-4), m.volume(step))
    h.check("closed", m.closed(step))


# -- E ----------------------------------------------------------------------------------------
def e_drag():
    p = m.panel()
    handle = p.handles.get("distance")
    if not h.check("the distance arrow", handle is not None):
        return
    start = handle.base_point() + handle.direction * (0.6 * handle.size)
    state["before_drag"] = p.distance.value()
    h.drag(h.screen_point(start), h.screen_point(start + V(0, 0, 1.0)))


e_drag.wait_ms = 2500


def e_check():
    p = m.panel()
    value = p.distance.value()
    h.check(
        "Distance grew with the drag",
        value > state.get("before_drag", 0) + 0.3,
        (state.get("before_drag"), value),
    )
    step = cut()
    expected = 1000.0 - 200.0 * value
    h.check(
        "the cut followed (above the plane kept)",
        i.close(m.volume(step), expected, 1e-3),
        (m.volume(step), expected),
    )


def e_back():
    p = m.panel()
    m.type_field(p.distance, "2")
    m.tick(p.flip, False)


e_back.wait_ms = 2000


# -- F ----------------------------------------------------------------------------------------
def f_minimal():
    m.choose(m.panel().fill, "Minimal")


f_minimal.wait_ms = 1500


def f_check_minimal():
    step = cut()
    h.check("Minimal: closed", m.closed(step))
    h.check("Minimal: 400 mm3", i.close(m.volume(step), 400.0, 1e-4), m.volume(step))
    h.check(
        "fewer faces than Uniform",
        m.facets(step) < state.get("uniform_faces", 0),
        (m.facets(step), state.get("uniform_faces")),
    )


def f_no_fill():
    m.choose(m.panel().fill, "No Fill")


f_no_fill.wait_ms = 1500


def f_check_no_fill():
    step = cut()
    info = m.analysis(step)
    h.check("No Fill: the cut stays open", not info["closed"] and info["holes"] == 1, info)


def f_uniform():
    m.choose(m.panel().fill, "Uniform")


f_uniform.wait_ms = 1500


# -- G ----------------------------------------------------------------------------------------
def g_angle():
    m.type_field(m.panel().angle_x, "20")


g_angle.wait_ms = 2000


def g_check():
    step = cut()
    h.check("the tilted cut is closed", m.closed(step), m.analysis(step))
    volume = m.volume(step)
    # The plane turns about its own X axis through its origin (the box's corner, lifted to
    # z = 2): it rises 2 + y tan 20 across the box, the box is 5 high; below it is kept.
    t = math.tan(math.radians(20.0))
    y_top = 3.0 / t
    expected = 20.0 * (2.0 * y_top + t * y_top * y_top / 2.0 + (10.0 - y_top) * 5.0)
    h.check(
        "tilted 20 degrees: %.2f mm3 kept" % expected,
        i.close(volume, expected, 1e-3),
        (volume, expected),
    )
    m.type_field(m.panel().angle_x, "0")


g_check.wait_ms = 2000


# -- H ----------------------------------------------------------------------------------------
def h_split():
    m.choose(m.panel().cut_type, "Split Body")


h_split.wait_ms = 2500


def h_check():
    step = cut()
    from sciforge import mesh

    pieces = mesh.pieces_of(step)
    h.check("two pieces", len(pieces) == 2, pieces)
    if len(pieces) == 2:
        volumes = sorted(round(m.volume(p), 3) for p in pieces)
        h.check("400 + 600 mm3", volumes == [400.0, 600.0], volumes)
        h.check("both closed", m.closed(pieces[0]) and m.closed(pieces[1]))
        labels = sorted(p.Label for p in pieces)
        h.check("named after the body", labels == [NAME, NAME + " (2)"], labels)
        h.check("both shown", m.shown(pieces[0]) and m.shown(pieces[1]))
        h.check("the step itself hidden", not m.shown(step))


# -- I ----------------------------------------------------------------------------------------
def i_ok():
    h.task_button("OK")


i_ok.wait_ms = 1500


def i_check():
    h.check("dialog closed", m.panel() is None)
    labels = i.browser_labels()
    h.check("the browser lists both bodies", NAME in labels and NAME + " (2)" in labels, labels)
    step = cut()
    h.check(
        "timeline: Plane Cut 1",
        step is not None and m.timeline_title(step) == "Plane Cut 1",
        step and m.timeline_title(step),
    )
    insert = [o for o in m.mesh_objects() if o.TypeId == "Mesh::Feature"]
    h.check("the inserted box used up", insert and not m.shown(insert[0]))
    h.check(
        "the pieces are not timeline steps",
        "MeshPiece" not in str(i.timeline_titles()),
        i.timeline_titles(),
    )


# -- J ----------------------------------------------------------------------------------------
def j_edit():
    s.timeline_double_click(cut())


j_edit.wait_ms = 1500


def j_dialog():
    p = m.panel()
    h.check("edit dialog", p is not None and p.title == "Plane Cut", p)
    if p is None:
        return
    h.check("Type Split Body", p.cut_type.currentText() == "Split Body", p.cut_type.currentText())
    h.check("Distance 2", abs(p.distance.value() - 2.0) < 1e-6, p.distance.value())
    m.choose(p.cut_type, "Trim")


j_dialog.wait_ms = 2500


def j_ok():
    h.task_button("OK")


j_ok.wait_ms = 1500


def j_check():
    h.check("dialog closed", m.panel() is None)
    bodies = [b.Label for b in m.bodies()]
    h.check("one body again", bodies.count(NAME) == 1 and NAME + " (2)" not in bodies, bodies)
    body = kept()
    h.check(
        "400 mm3, closed",
        body is not None and i.close(m.volume(body), 400.0, 1e-4) and m.closed(body),
        body and m.volume(body),
    )


# -- K ----------------------------------------------------------------------------------------
def k_undo():
    i.undo()


k_undo.wait_ms = 1500


def k_check_undo():
    labels = [b.Label for b in m.bodies()]
    h.check("Ctrl+Z: split again", NAME + " (2)" in labels, labels)


def k_redo():
    i.redo()


k_redo.wait_ms = 1500


def k_check_redo():
    labels = [b.Label for b in m.bodies()]
    h.check("Ctrl+Y: trimmed", NAME + " (2)" not in labels and labels.count(NAME) == 1, labels)
    body = kept()
    h.check("400 mm3", body is not None and i.close(m.volume(body), 400.0, 1e-4))


# -- L ----------------------------------------------------------------------------------------
def l_open():
    h.ribbon("Plane Cut")


def l_body():
    m.click_body(kept())


l_body.wait_ms = 1500


def l_plane():
    p = m.panel()
    h.click(p.squares.point_on("XY", -0.7, -0.7))


l_plane.wait_ms = 1500


def l_distance():
    m.type_field(m.panel().distance, "1")


l_distance.wait_ms = 2000


def l_previewed():
    steps = m.steps("MeshPlaneCut")
    h.check("a second cut previewed", len(steps) == 2, steps)
    h.task_button("Cancel")


l_previewed.wait_ms = 1500


def l_check():
    h.check("dialog closed", m.panel() is None)
    h.check("one Plane Cut step", len(m.steps("MeshPlaneCut")) == 1, m.steps("MeshPlaneCut"))
    body = kept()
    h.check(
        "the body as it was: 400 mm3",
        body is not None and i.close(m.volume(body), 400.0, 1e-4) and m.shown(body),
        body and m.volume(body),
    )
    h.shot("end")


h.run(
    "mesh_plane_cut",
    [i.new_design("MeshPlaneCut")]
    + m.insert_file(i.fixture("box_20x10x5.stl"))
    + [
        a_open,
        a_click_body,
        a_waits_for_plane,
        b_click_xy,
        b_refused,
        b_still_open,
        c_distance,
        c_check,
        d_flip,
        d_check,
        e_drag,
        e_check,
        e_back,
        f_minimal,
        f_check_minimal,
        f_no_fill,
        f_check_no_fill,
        f_uniform,
        g_angle,
        g_check,
        h_split,
        h_check,
        i_ok,
        i_check,
        j_edit,
        j_dialog,
        j_ok,
        j_check,
        k_undo,
        k_check_undo,
        k_redo,
        k_check_redo,
        l_open,
        l_body,
        l_plane,
        l_distance,
        l_previewed,
        l_check,
    ],
)
