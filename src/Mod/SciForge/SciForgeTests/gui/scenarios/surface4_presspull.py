# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull (Q) on a surface body, real input.

An open box of surfaces (30 x 20 floor, 10 high walls: area 1600) and a curved surface
(an arc extruded). Q with nothing picked opens Press Pull; a click on the box's floor hands
over to the surface Press Pull (the face moves, the walls follow). Type -5: the floor goes
5 down (its normal points up into the box), the walls grow by 5: area 2100. OK: a "Press
Pull" step. Double-click it in the timeline: -5 reads back; type 3: the floor goes up 3,
the walls are cut back: area 1300; OK. Undo: 2100 again; Redo. A vertical edge selected,
Q: Press Pull on an edge of a surface body is its Fillet (the surface Fillet dialog opens
with the edge); radius 2, OK. Q, click that fillet's round face: the Fillet opens to change its
radius (Fusion); Esc. Q, click the curved surface (an arc of radius 52, 60 degrees, 20 long),
Distance 2, OK: it is offset (radius 50 or 54 by its normal). A refusal: Q, click the box's
floor, Distance 9: further than its walls reach, said in the dialog; Esc leaves the box as it
was. Save (Ctrl+S), close, reopen: the steps compute, the Press Pull edits again.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def setup():
    from sciforge import bodies, surface

    s4.new_design("Surface4PressPull")
    s["box"] = s4.surface_box()
    arc = s4.arc_sketch(80, -40, 52, 60, 120, plane="XZ_Plane")
    step = surface.build("extrude", {"refs": s4.edges(arc)}, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(arc, False)
    s["curved"] = bodies.body_of(step)
    h.fit()
    h.check("the open box", st.near(st.area(s["box"]), 1600.0), st.area(s["box"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    h.press("q")


def click_floor():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    shown = p is not None and not p._closed
    h.check("Press Pull opened, waiting", shown)
    if shown:
        h.check("no 'make a solid first'", "solid" not in p.message.text(), p.message.text())
        h.check("says to click a surface face", "surface body" in p.what.text(), p.what.text())
    h.click(V(8, 16, 0))


def handed_over():
    s4.settle()
    p = s4.panel()
    h.check("the surface Press Pull dialog", p is not None and p.kind == "surface_press_pull")
    h.check("the floor picked", p is not None and len(p.picked) == 1, p and p.picked)
    h.check("an arrow on the face", p is not None and len(p.arrows) == 1)
    s4.type_main("-5")


def pulled_down():
    s4.settle()
    h.check("preview: the walls grew", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    h.check("still 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.shot("1-press-pull")
    st.ok()


def done():
    h.check("dialog closed", s4.panel() is None)
    h.check("area 2100", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    bb = s["box"].Shape.BoundBox
    h.check("the floor at z = -5", abs(bb.ZMin + 5) < 1e-6, bb)
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Press Pull")), None)
    h.check("Press Pull in the timeline", s["title"] is not None, titles)
    h.check("double-clicked it", st.double_click_timeline(s["title"] or "Press Pull 1"))


def edit_open():
    s4.settle()
    p = s4.panel()
    h.check("edit dialog", p is not None and p.editing)
    if p is None:
        return
    h.check("-5 reads back", s4.near(p.fields["distance"][0].value(), -5.0))
    s4.type_main("3")


def edit_ok():
    s4.settle()
    st.ok()


def edited():
    h.check("area 1300", st.near(st.area(s["box"]), 1300.0), st.area(s["box"]))
    st.undo()


def undone():
    h.check("undo: 2100 again", st.near(st.area(s["box"]), 2100.0), st.area(s["box"]))
    st.redo()


def redone():
    h.check("redo: 1300", st.near(st.area(s["box"]), 1300.0), st.area(s["box"]))
    Gui.Selection.clearSelection()
    h.fit()


def select_edge():
    h.click_edge(V(0, 20, 7))


def q_on_edge():
    h.check("an edge selected", bool(Gui.Selection.getSelectionEx()))
    h.press("q")


def fillet_on_edge():
    s4.settle()
    p = s4.panel()
    h.check(
        "Press Pull on a surface edge is its Fillet", p is not None and p.kind == "surface_fillet"
    )
    h.check("with the edge", p is not None and len(p.picked) == 1, p and p.picked)
    s4.type_main("2")


def fillet_ok():
    s4.settle()
    st.ok()


def q_on_fillet_face():
    h.check("filleted: one face more", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    Gui.Selection.clearSelection()
    h.press("q")


def click_fillet_face():
    h.click(V(2 - 2**0.5, 18 + 2**0.5, 6.5))


def fillet_edit_opens():
    s4.settle()
    p = s4.panel()
    h.check(
        "Press Pull on the fillet's face changes that fillet",
        p is not None and p.kind == "surface_fillet" and p.editing,
        p and (p.kind, p.editing),
    )
    h.check("Radius 2 reads back", p is not None and s4.near(p.fields["radius"][0].value(), 2.0))
    st.esc()


def q_again():
    s4.settle()
    h.check("closed", s4.panel() is None)
    s["area"] = st.area(s["box"])
    Gui.Selection.clearSelection()
    h.press("q")


def click_curved():
    s["curved_area"] = st.area(s["curved"])
    h.click(V(80, -10, 12))


def curved_distance():
    s4.settle()
    p = s4.panel()
    h.check(
        "Press Pull takes the curved face",
        p is not None and p.kind == "surface_press_pull" and len(p.picked) == 1,
        p and p.picked,
    )
    h.check("not refused as curved", "flat" not in s4.message(), s4.message())
    s4.type_main("2")


def curved_ok():
    s4.settle()
    st.ok()


def curved_offset():
    from sciforge import surfmod

    h.check("dialog closed", s4.panel() is None)
    area = st.area(s["curved"])
    options = [r * math.pi / 3 * 20 for r in (50.0, 54.0)]
    h.check("offset by 2: radius 50 or 54", any(s4.near(area, a, 1e-5) for a in options), area)
    h.check("a Press Pull step on it", surfmod.kind_of(s["curved"].Tip) == "surface_press_pull")
    s["curved_area"] = area
    Gui.Selection.clearSelection()
    h.press("q")


def click_floor_again():
    h.click(V(8, 16, 3))


def too_far():
    s4.settle()
    s4.type_main("9")


def refused():
    s4.settle()
    text = s4.message()
    h.check("says it is further than the walls reach", "further" in text, text)
    st.esc()


def unchanged():
    s4.settle()
    h.check("closed", s4.panel() is None)
    h.check("the box unchanged", st.near(st.area(s["box"]), s["area"]))
    h.check("the curved surface as offset", st.near(st.area(s["curved"]), s["curved_area"]))
    import os
    import tempfile

    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface4-"), "surface4_pp.FCStd")
    s["path"] = path
    s["label"] = s["box"].Label
    s["titles"] = st.timeline_titles()
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    from PySide import QtCore

    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    from SciForgeTests.gui import versions_input as vi

    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("nothing unsaved", not App.ActiveDocument.isTouched())
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import surfmod

    found = App.ActiveDocument.getObjectsByLabel(s["label"])
    box = found[0] if found else None
    h.check("the box is back", box is not None, s["label"])
    if box is None:
        return
    s["box"] = box
    h.check("the same area", st.near(st.area(box), s["area"]), (st.area(box), s["area"]))
    steps = [o for o in box.Group if surfmod.is_step(o)]
    h.check("its Press Pull and Fillet steps", len(steps) == 2, [o.Label for o in steps])
    h.check(
        "they computed",
        all("Invalid" not in list(o.State) for o in steps),
        [o.State for o in steps],
    )
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))
    title = next((t for t in titles if t.startswith("Press Pull")), "Press Pull 1")
    h.check("double-clicked the Press Pull", st.double_click_timeline(title))


def edit_after_reopen():
    s4.settle()
    p = s4.panel()
    h.check(
        "its dialog opens after the reopen",
        p is not None and p.kind == "surface_press_pull" and p.editing,
    )
    h.check("3 reads back", p is not None and s4.near(p.fields["distance"][0].value(), 3.0))
    st.esc()


def closed_again():
    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("unchanged", st.near(st.area(s["box"]), s["area"]))


h.run(
    "surface4_presspull",
    [
        setup,
        click_floor,
        handed_over,
        pulled_down,
        done,
        edit_open,
        edit_ok,
        edited,
        undone,
        redone,
        select_edge,
        q_on_edge,
        fillet_on_edge,
        fillet_ok,
        q_on_fillet_face,
        click_fillet_face,
        fillet_edit_opens,
        q_again,
        click_curved,
        curved_distance,
        curved_ok,
        curved_offset,
        click_floor_again,
        too_far,
        refused,
        unchanged,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
        edit_after_reopen,
        closed_again,
    ],
)
