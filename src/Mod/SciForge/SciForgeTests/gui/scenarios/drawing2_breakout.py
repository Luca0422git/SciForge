# SPDX-License-Identifier: LGPL-2.1-or-later
"""Breakout Section View (CREATE > Breakout Section View), with real clicks.

The plate (drawing_fixtures.plate: 80 x 50 x 10, holes at (20, 15) and (60, 35)), ISO
A3, base view Top at 1:1 and, made by script, its projected view below (the plate seen
edge on from its front: 80 x 10, the holes only as hidden lines; hole 1's middle 15 mm
behind the front).

A  Esc: the command, a click on the base view, two points of a boundary, Esc: nothing
   made, no preview left.
B  The command, a click on the front view (the depth box offers half the part: 25), the
   corners of a boundary around hole 1 and its first corner again (closes it); 15 typed
   as the depth: the view draws a trimmed copy (hidden) of the plate: hole 1's sides
   show as lines now, the cut floor is hatched inside the boundary; OK.
C  Undo: the whole plate again and the copy gone; Redo: the breakout back.
D  The command again, a click on the front view: refused (it has a breakout); Esc.
E  Double-click inside the boundary: Edit Breakout with depth 15; 60 typed (more than
   the plate): through it, no floor left to hatch, more taken away; Default: 25 again;
   OK; Undo: 15 again.
F  Hole 1 made 12 mm across (by script): the copy and the hatching follow (the floor
   narrower).
G  Projected views of the front view (by script): the one on the right shows the whole
   plate, an isometric one the breakout too (Fusion: isometric views inherit it).
H  Export DXF (by script): the hatching on layer HATCH, the copy's lines.
I  Double-click inside the boundary, Remove Breakout: the whole plate (also in the
   isometric view), copy and hatching gone; Undo: back.
J  Saved, closed and opened again (by script); Workspace > Drawing: the breakout is
   back, its copy is made again when hole 1 changes back to 10 mm.
K  The front view selected, Delete: the copy goes with it.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

state = {}
BOUNDARY = [(-30.0, -8.0), (-10.0, -8.0), (-10.0, 8.0), (-30.0, 8.0)]
INSIDE = (-28.0, 2.0)  # a point inside the boundary, away from its lines


def front():
    return App.ActiveDocument.getObject(state["front"]) if "front" in state else None


def data():
    from sciforge import drawing_breakout

    view = front()
    return drawing_breakout.breakout_of(view) if view is not None else None


def visible_upright(view, u):
    """Visible lines of a view standing at x = u (its own coordinates, 1:1)."""
    found = 0
    for edge in view.getVisibleEdges(True):
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        if abs(a.x - u) < 0.05 and abs(b.x - u) < 0.05 and abs(a.y - b.y) > 1.0:
            found += 1
    return found


def uprights(view):
    found = []
    for edge in view.getVisibleEdges(True):
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        if abs(a.x - b.x) < 0.05 and abs(a.y - b.y) > 1.0:
            found.append(round(a.x, 3))
    return sorted(found)


def set_up():
    from sciforge import drawing

    base = w.base()
    x, y = drawing.view_position(base)
    view = drawing.add_projected(base, "Bottom", x, y - 60.0)
    base.Document.recompute()
    state["front"] = view.Name


set_up.wait_ms = 3000


def set_up_check():
    view = front()
    h.check("the front view", view is not None and len(view.getVisibleEdges()) > 0)
    h.check("hole 1 not seen yet", visible_upright(view, -25.0) == 0)
    state["objects"] = len(App.ActiveDocument.Objects)


# -- A ------------------------------------------------------------------------------------------
def a_command():
    w.menu("CREATE", "Breakout Section View")


a_command.wait_ms = 800


def a_points():
    p = d.panel_of("BreakoutPanel")
    if not h.check("Breakout Section View dialog", p is not None, d.panel()):
        return
    w.click(0.0, 0.0)
    w.click(-30.0, -20.0)
    w.click(-10.0, -20.0)
    w.move(-10.0, 0.0)


a_points.wait_ms = 800


def a_escape():
    p = d.panel_of("BreakoutPanel")
    h.check("the base view picked", p is not None and p.view is not None and p.view == w.base())
    h.check("two points so far", p is not None and len(p.points) == 2, p and p.points)
    h.check("a preview of the boundary", d.previews_left() > 0, d.previews_left())
    d.key(QtCore.Qt.Key_Escape)


a_escape.wait_ms = 1000


def a_nothing():
    from sciforge import drawing

    h.check("dialog closed", d.panel() is None, d.panel())
    h.check("no breakout", not drawing.has_breakout(w.base()))
    h.check("nothing new", len(App.ActiveDocument.Objects) == state["objects"])
    h.check("no preview left", d.previews_left() == 0, d.previews_left())


# -- B ------------------------------------------------------------------------------------------
def b_command():
    w.menu("CREATE", "Breakout Section View")


b_command.wait_ms = 800


def b_view():
    state["before"] = len(front().getVisibleEdges())
    w.click(30.0, 0.0, front())


b_view.wait_ms = 800


def b_points():
    p = d.panel_of("BreakoutPanel")
    if not h.check("the front view picked", p is not None and p.view == front()):
        return
    h.check("the depth offered: half the part", p.distance.text() == "25", p.distance.text())
    for u, v in BOUNDARY:
        w.click(u, v, front())
    w.move(-29.0, -7.0, front())


b_points.wait_ms = 800


def b_close():
    p = d.panel_of("BreakoutPanel")
    h.check("four corners", p is not None and len(p.points) == 4, p and p.points)
    w.click(*BOUNDARY[0], view=front())


b_close.wait_ms = 3000


def b_made():
    p = d.panel_of("BreakoutPanel")
    h.check("closed: the breakout is made", data() is not None, data())
    h.check("25 deep", data() is not None and data()["depth"] == 25.0, data())
    if p is not None:
        d.type_into(p.distance, "15")
        d.key(QtCore.Qt.Key_Tab)


b_made.wait_ms = 3500


def b_ok():
    h.check("15 deep", data() is not None and data()["depth"] == 15.0, data())
    h.check("hole 1's sides show", visible_upright(front(), -25.0) >= 1)
    d.ok()


b_ok.wait_ms = 2500


def b_check():
    from sciforge import drawing, drawing_breakout

    view = front()
    h.check("dialog closed", d.panel() is None, d.panel())
    h.check("no preview left", d.previews_left() == 0, d.previews_left())
    clip = drawing._get(view, "SciForgeDepthClip", None)
    h.check("a trimmed copy", clip is not None and clip.TypeId == "Part::FeaturePython")
    if clip is None:
        return
    state["clip"] = clip.Name
    state["volume"] = clip.Shape.Volume
    h.check("the view draws it", [s.Name for s in view.Source] == [clip.Name])
    h.check("hidden in the design", not clip.ViewObject.Visibility)
    body = App.ActiveDocument.getObject("Body")
    h.check("the view's parts stay the body", drawing_breakout.real_sources(view) == [body])
    h.check("material taken away", 0 < clip.Shape.Volume < body.Shape.Volume)
    hatch = drawing_breakout.hatch_of(view)
    tags = drawing._get(view, "SciForgeBreakoutTags", []) or []
    h.check("the floor hatched", len(hatch) > 0 and len(tags) == len(hatch), (hatch, tags))
    # the boundary as clicked (corners land a fraction of a mm from the aimed ones: the
    # sheet's scale follows the window, and a 13 px shorter view moved one by 0.14 mm)
    drawn = (data() or {}).get("points") or []
    h.check(
        "the corners where they were clicked",
        len(drawn) == 4
        and all(abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) < 0.5 for a, b in zip(drawn, BOUNDARY)),
        drawn,
    )
    lo = min((p[0] for p in drawn), default=-30.0) - 0.01
    hi = max((p[0] for p in drawn), default=-10.0) + 0.01
    inside = all(
        lo <= x <= hi and -5.01 <= y <= 5.01 for seg in hatch for x, y in (seg[:2], seg[2:])
    )
    h.check("the hatching inside the boundary", inside, (hatch, drawn))
    state["hatch"] = hatch
    h.check("more lines than before", len(view.getVisibleEdges()) > state["before"])
    h.shot("b-breakout")


# -- C ------------------------------------------------------------------------------------------
def c_undo():
    d.undo()


c_undo.wait_ms = 2500


def c_undone():
    from sciforge import drawing

    view = front()
    h.check("undo: no breakout", not drawing.has_breakout(view))
    h.check("the whole body again", [s.Name for s in view.Source] == ["Body"])
    h.check("the copy gone", App.ActiveDocument.getObject(state["clip"]) is None)
    h.check("hole 1 hidden again", visible_upright(view, -25.0) == 0)
    d.redo()


c_undone.wait_ms = 3000


def c_redone():
    view = front()
    h.check("redo: the breakout back", data() is not None and data()["depth"] == 15.0)
    h.check("drawing the copy", [s.Name for s in view.Source] == [state["clip"]])


# -- D ------------------------------------------------------------------------------------------
def d_command():
    w.menu("CREATE", "Breakout Section View")


d_command.wait_ms = 800


def d_click():
    w.click(30.0, 0.0, front())


d_click.wait_ms = 800


def d_refused():
    p = d.panel_of("BreakoutPanel")
    h.check(
        "refused: it has one",
        p is not None and p.view is None and "already" in p.message.text(),
        p and p.message.text(),
    )
    d.key(QtCore.Qt.Key_Escape)


d_refused.wait_ms = 1000


def d_closed():
    h.check("dialog closed", d.panel() is None)


# -- E ------------------------------------------------------------------------------------------
def e_open():
    d.double_click_at(*w.at(*INSIDE, view=front()))


e_open.wait_ms = 1500


def e_through():
    p = d.panel_of("BreakoutPanel")
    if not h.check("Edit Breakout", p is not None and p.closed, d.panel()):
        return
    h.check("depth 15", p.distance.text() == "15", p.distance.text())
    h.check("Remove Breakout offered", p.remove_button.isVisibleTo(p.form))
    d.type_into(p.distance, "60")
    d.key(QtCore.Qt.Key_Tab)


e_through.wait_ms = 3000


def e_deep():
    from sciforge import drawing_breakout

    h.check("60 deep", data() is not None and data()["depth"] == 60.0, data())
    clip = App.ActiveDocument.getObject(state["clip"])
    h.check("more taken away", clip.Shape.Volume < state["volume"] - 1.0)
    h.check("no floor to hatch", drawing_breakout.hatch_of(front()) == [])
    wi.click(d.panel().default_button)


e_deep.wait_ms = 3000


def e_ok():
    from sciforge import drawing_breakout

    p = d.panel()
    h.check("Default: 25", data() is not None and data()["depth"] == 25.0, data())
    h.check("written in the box", p is not None and p.distance.text() == "25")
    h.check("hatched again", bool(drawing_breakout.hatch_of(front())))
    d.ok()


e_ok.wait_ms = 2000


def e_undo():
    h.check("dialog closed", d.panel() is None)
    d.undo()


e_undo.wait_ms = 2500


def e_undone():
    from sciforge import drawing_breakout

    h.check("undo: 15 deep again", data() is not None and data()["depth"] == 15.0, data())
    h.check("hatched again", drawing_breakout.hatch_of(front()) == state["hatch"])


# -- F ------------------------------------------------------------------------------------------
def f_hole():
    doc = App.ActiveDocument
    doc.getObject("Hole1").Radius = 6.0
    doc.recompute()


f_hole.wait_ms = 4000


def f_followed():
    from sciforge import drawing_breakout

    clip = App.ActiveDocument.getObject(state["clip"])
    h.check("the copy made again", abs(clip.Shape.Volume - state["volume"]) > 1.0)
    hatch = drawing_breakout.hatch_of(front())
    h.check("the hatching follows", hatch and hatch != state["hatch"], hatch)
    h.check("still drawing the copy", [s.Name for s in front().Source] == [state["clip"]])
    h.check("hole 1's sides (12 mm now)", visible_upright(front(), -26.0) >= 1, uprights(front()))
    h.shot("f-followed")


# -- G ------------------------------------------------------------------------------------------
def g_child():
    from sciforge import drawing

    x, y = drawing.view_position(front())
    child = drawing.add_projected(front(), "Right", x + 70.0, y)
    App.ActiveDocument.recompute()
    state["child"] = child.Name


g_child.wait_ms = 2500


def g_check():
    from sciforge import drawing

    child = App.ActiveDocument.getObject(state["child"])
    h.check("the projected view shows the body", [s.Name for s in child.Source] == ["Body"])
    h.check("and has lines", len(child.getVisibleEdges()) > 0)
    x, y = drawing.view_position(front())
    iso = drawing.add_projected(front(), "FrontTopRight", x + 70.0, y - 50.0)
    App.ActiveDocument.recompute()
    state["iso"] = iso.Name


g_check.wait_ms = 2500


def g_iso():
    from sciforge import drawing

    iso = App.ActiveDocument.getObject(state["iso"])
    h.check("the isometric view draws the copy", [s.Name for s in iso.Source] == [state["clip"]])
    h.check("its parts are the body", [s.Name for s in drawing._view_sources(iso)] == ["Body"])
    h.check("and has lines", len(iso.getVisibleEdges()) > 0)


# -- H ------------------------------------------------------------------------------------------
def h_export():
    from sciforge import drawing

    path = os.path.join(d.ensure_out(), "drawing2_breakout.dxf")
    if os.path.exists(path):
        os.remove(path)
    drawing.export_dxf(d.page(), path)
    text = open(path, encoding="utf-8", errors="replace").read() if os.path.exists(path) else ""
    h.check("DXF written", bool(text))
    h.check("hatching on layer HATCH", "\nHATCH\n" in text)


# -- I ------------------------------------------------------------------------------------------
def i_open():
    d.double_click_at(*w.at(*INSIDE, view=front()))


i_open.wait_ms = 1500


def i_remove():
    p = d.panel_of("BreakoutPanel")
    if not h.check("Edit Breakout", p is not None and p.closed, d.panel()):
        return
    wi.click(p.remove_button)


i_remove.wait_ms = 3000


def i_removed():
    from sciforge import drawing

    view = front()
    h.check("dialog closed", d.panel() is None, d.panel())
    h.check("no breakout", not drawing.has_breakout(view))
    h.check("the whole body", [s.Name for s in view.Source] == ["Body"])
    h.check("the copy gone", App.ActiveDocument.getObject(state["clip"]) is None)
    h.check("the hatching gone", not (drawing._get(view, "SciForgeBreakoutTags", []) or []))
    iso = App.ActiveDocument.getObject(state["iso"])
    h.check("the isometric view: the whole body", [s.Name for s in iso.Source] == ["Body"])
    d.undo()


i_removed.wait_ms = 3000


def i_back():
    h.check("undo: the breakout back", data() is not None and data()["depth"] == 15.0)
    h.check("the copy back", App.ActiveDocument.getObject(state["clip"]) is not None)
    iso = App.ActiveDocument.getObject(state["iso"])
    h.check("the isometric view too", [s.Name for s in iso.Source] == [state["clip"]])


# -- J ------------------------------------------------------------------------------------------
def j_save():
    state["label"] = d.page().Label
    path = os.path.join(d.ensure_out(), "Brk2.FCStd")
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    state["file"] = path


j_save.wait_ms = 1500


def j_close():
    h.check("saved", os.path.isfile(state["file"]))
    App.closeDocument(App.ActiveDocument.Name)


j_close.wait_ms = 1500


def j_open():
    App.openDocument(state["file"])


j_open.wait_ms = 4000


def j_drawing():
    d.workspace("Drawing", state["label"])


j_drawing.wait_ms = 5000


def j_back():
    from sciforge import drawing

    view = front()
    h.check("the drawing open", d.page() is not None)
    h.check("the breakout back", view is not None and data() is not None and data()["depth"] == 15)
    clip = App.ActiveDocument.getObject(state["clip"])
    h.check(
        "its copy back, still made by SciForge",
        clip is not None and type(clip.Proxy).__name__ == "BreakoutCut",
        clip and clip.Proxy,
    )
    h.check("drawn", view is not None and [s.Name for s in view.Source] == [state["clip"]])
    h.check("hatched", bool(drawing._get(view, "SciForgeBreakoutTags", []) or []))
    state["volume"] = clip.Shape.Volume if clip is not None else 0.0
    App.ActiveDocument.getObject("Hole1").Radius = 5.0
    App.ActiveDocument.recompute()


j_back.wait_ms = 4000


def j_followed():
    clip = App.ActiveDocument.getObject(state["clip"])
    h.check(
        "made again after reopening", clip is not None and clip.Shape.Volume > state["volume"] + 1
    )
    h.check("hole 1's sides (10 mm again)", visible_upright(front(), -25.0) >= 1, uprights(front()))


# -- K ------------------------------------------------------------------------------------------
def j_select():
    d.click_at(380, 250)  # the sheet takes the keyboard (empty paper)
    Gui.Selection.addSelection(front())
    d.key(QtCore.Qt.Key_Delete)


j_select.wait_ms = 2500


def j_deleted():
    doc = App.ActiveDocument
    h.check("the front view deleted", doc.getObject(state["front"]) is None)
    h.check("its copy with it", doc.getObject(state["clip"]) is None)
    h.check("and its projected views", doc.getObject(state["iso"]) is None)
    h.check("the base view stays", w.base() is not None)


h.run(
    "drawing2_breakout",
    [w.new_design("Brk")]
    + w.sheet_steps()
    + [d.wait_geometry(1500), set_up, set_up_check]
    + [a_command, a_points, a_escape, a_nothing]
    + [b_command, b_view, b_points, b_close, b_made, b_ok, b_check]
    + [c_undo, c_undone, c_redone]
    + [d_command, d_click, d_refused, d_closed]
    + [e_open, e_through, e_deep, e_ok, e_undo, e_undone]
    + [f_hole, f_followed]
    + [g_child, g_check, g_iso]
    + [h_export]
    + [i_open, i_remove, i_removed, i_back]
    + [j_save, j_close, j_open, j_drawing, j_back, j_followed]
    + [j_select, j_deleted],
)
