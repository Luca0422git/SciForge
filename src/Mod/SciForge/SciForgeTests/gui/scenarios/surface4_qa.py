# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA of SURFACE > MODIFY on surface bodies (surface-4): the paths the builder's scenarios did
not walk, real input.

An empty design first, SURFACE tab: MODIFY > Fillet, Q and Del with nothing to work on open
no surface dialog and raise nothing (the SOLID dialogs say to make a solid first; Esc).
Then an open box of surfaces (30 x 20 floor, 10 high walls, area 1600) and a strip (an
extruded polyline 0-10-20 along y = 40 and a turn: three faces, two of them in one plane).
Fillet a vertical corner, Radius 3, OK. Double-click it: type 1 (the preview follows), Esc:
the fillet is radius 3 again and nothing is left changed; one Ctrl+Z then removes the fillet
(the cancelled edit left no step of its own), Ctrl+Y puts it back. Q on the floor (the
filleted corner makes it no polygon), -5: the walls and the fillet grow by 5 all round. Its
edit, Distance 2, Esc: unchanged. Click the right wall, Del: a Delete Face step. Its edit:
click another wall (two picked), Esc: still one face deleted. Delete the Fillet in the
timeline: the Press Pull and the Delete Face go on without it (the floor and the right wall
found again where they were: before, the Press Pull lost its floor and the Delete Face took
the left wall); Ctrl+Z. MODIFY > Merge of the strip's
two faces in one plane, OK. Save, close, reopen: every step computes, the areas and the
timeline are the same; the Fillet edits again (Radius 3 reads back); Esc.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
AREA = 1600.0


def doc():
    return App.ActiveDocument


def fillet_area(r):
    return AREA - 2 * r * 10 + (math.pi * r / 2) * 10 - (r * r - math.pi * r * r / 4)


def floor_perimeter(r):
    """The floor's edge round the filleted corner: the walls' bottom line."""
    return 2 * (30 + 20) - 2 * r + math.pi * r / 2


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


def any_dialog():
    return bool(Gui.Control.activeDialog())


# -- an empty design --------------------------------------------------------------------------
def empty_design():
    s4.new_design("Surface4QA")
    h.fit()
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def empty_fillet():
    h.idle_step()()
    h.check("no surface Fillet dialog in an empty design", s4.panel() is None)
    h.check("no error popup", not h.popups(), h.popups())
    if any_dialog():
        st.esc()


def empty_q():
    h.idle_step()()
    h.check("closed", not any_dialog())
    h.press("q")


def empty_q_open():
    from sciforge import presspull_ui

    h.idle_step()()
    p = presspull_ui.PressPullPanel.last
    shown = p is not None and not p._closed
    h.check("Press Pull opens (nothing to hand over)", shown)
    h.check("no surface dialog", s4.panel() is None)
    if shown:
        h.check("not the surface hint", "surface body" not in p.what.text(), p.what.text())
    st.esc()


def empty_delete():
    h.idle_step()()
    h.check("Esc closed it", not any_dialog())
    h.press(QtCore.Qt.Key_Delete)


def empty_after_delete():
    h.idle_step()()
    h.check("Del with nothing: no dialog", not any_dialog())
    h.check("no error popup", not h.popups(), h.popups())
    h.check("still empty", not [o for o in doc().Objects if o.TypeId == "PartDesign::Body"])


# -- the bodies -------------------------------------------------------------------------------
def setup():
    from sciforge import bodies, surface

    s["box"] = s4.surface_box()
    strip = s4.sketch([(0, 40), (10, 40), (20, 40), (20, 50)], closed=False)
    step = surface.build("extrude", {"refs": s4.edges(strip)}, {"distance": 10.0})
    doc().recompute()
    bodies.set_shown(strip, False)
    s["strip"] = bodies.body_of(step)
    h.fit()
    h.check("the open box", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("area 1600", s4.near(st.area(s["box"]), AREA), st.area(s["box"]))
    h.check("the strip: 3 faces", s4.faces(s["strip"]) == 3, s4.faces(s["strip"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Fillet")


def click_corner():
    p = s4.panel()
    h.check("the surface Fillet dialog", p is not None and p.kind == "surface_fillet")
    h.click_edge(V(30, 0, 5))


def type_radius():
    s4.settle()
    s4.type_main("3")


def fillet_ok():
    s4.settle()
    st.ok()


def filleted():
    h.check("dialog closed", s4.panel() is None)
    h.check("radius 3 corner", s4.near(st.area(s["box"]), fillet_area(3), 1e-5), st.area(s["box"]))
    titles = st.timeline_titles()
    s["fillet"] = next((t for t in titles if t.startswith("Fillet")), "Fillet")
    h.check("double-clicked the Fillet", st.double_click_timeline(s["fillet"]))


def edit_type():
    s4.settle()
    p = s4.panel()
    h.check("the Fillet edit", p is not None and p.editing, p)
    s4.type_main("1")


def edit_preview():
    s4.settle()
    h.check(
        "the preview follows radius 1",
        s4.near(st.area(s["box"]), fillet_area(1), 1e-5),
        st.area(s["box"]),
    )
    st.esc()


def edit_cancelled():
    from sciforge import surfmod

    s4.settle()
    h.check("Esc closed the edit", s4.panel() is None)
    h.check(
        "Esc: radius 3 again", s4.near(st.area(s["box"]), fillet_area(3), 1e-5), st.area(s["box"])
    )
    step = s["box"].Tip
    h.check(
        "the step's Radius is 3 again",
        surfmod.kind_of(step) == "surface_fillet" and s4.near(step.Radius.Value, 3.0),
        surfmod.kind_of(step) and step.Radius,
    )
    h.check("no error popup", not h.popups(), h.popups())
    st.undo()


def undone_once():
    h.check("one Ctrl+Z removes the fillet", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    st.redo()


def redone():
    h.check("Ctrl+Y: the fillet again", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    s["area"] = st.area(s["box"])
    Gui.Selection.clearSelection()
    h.press("q")


def click_floor():
    h.click(V(8, 16, 0))


def pull_type():
    s4.settle()
    p = s4.panel()
    h.check(
        "the surface Press Pull took the floor",
        p is not None and p.kind == "surface_press_pull" and len(p.picked) == 1,
        p and (p.kind, p.picked),
    )
    s4.type_main("-5")


def pull_ok():
    s4.settle()
    text = s4.message()
    h.check("not refused", "⚠" not in text, text)
    st.ok()


def pulled():
    h.check("dialog closed", s4.panel() is None)
    expect = s["area"] + 5 * floor_perimeter(3)
    h.check(
        "the walls and the fillet grew by 5 all round",
        s4.near(st.area(s["box"]), expect, 1e-5),
        (st.area(s["box"]), expect),
    )
    h.check("still 6 faces", s4.faces(s["box"]) == 6, s4.faces(s["box"]))
    s["area"] = st.area(s["box"])
    titles = st.timeline_titles()
    s["pull"] = next((t for t in titles if t.startswith("Press Pull")), "Press Pull")
    h.check("double-clicked the Press Pull", st.double_click_timeline(s["pull"]))


def pull_edit():
    s4.settle()
    p = s4.panel()
    h.check("the Press Pull edit", p is not None and p.editing, p)
    h.check("-5 reads back", p is not None and s4.near(p.fields["distance"][0].value(), -5.0))
    s4.type_main("2")


def pull_edit_preview():
    s4.settle()
    h.check("the preview changed", not s4.near(st.area(s["box"]), s["area"]), st.area(s["box"]))
    st.esc()


def pull_cancelled():
    from sciforge import surfmod

    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("unchanged", s4.near(st.area(s["box"]), s["area"]), (st.area(s["box"]), s["area"]))
    step = s["box"].Tip
    h.check(
        "Distance -5 kept",
        surfmod.kind_of(step) == "surface_press_pull" and s4.near(step.Distance.Value, -5.0),
    )
    Gui.Selection.clearSelection()
    st.tab("SURFACE")
    h.click(V(30, 10, 5))


def delete_wall():
    h.check("the right wall is selected", bool(Gui.Selection.getSelectionEx()))
    h.press(QtCore.Qt.Key_Delete)


def wall_deleted():
    from sciforge import surfmod

    h.idle_step()()
    h.check("5 faces left", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("a surface Delete Face step", surfmod.kind_of(s["box"].Tip) == "surface_delete_face")
    s["area"] = st.area(s["box"])
    titles = st.timeline_titles()
    s["delete"] = next((t for t in titles if t.startswith("Delete Face")), "Delete Face")
    Gui.Selection.clearSelection()
    h.check("double-clicked the Delete Face", st.double_click_timeline(s["delete"]))


def delete_edit():
    s4.settle()
    p = s4.panel()
    h.check("the Delete Face edit", p is not None and p.kind == "surface_delete_face", p)
    h.click(V(15, 0, 5))


def delete_edit_esc():
    s4.settle()
    p = s4.panel()
    h.check("two faces picked", p is not None and len(p.picked) == 2, p and p.picked)
    h.check("the preview takes the front wall too", s4.faces(s["box"]) == 4, s4.faces(s["box"]))
    st.esc()


def delete_cancelled():
    from SciForgeTests.gui import timeline_input as tl

    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("still 5 faces", s4.faces(s["box"]) == 5, s4.faces(s["box"]))
    h.check("the same area", s4.near(st.area(s["box"]), s["area"]), st.area(s["box"]))
    Gui.Selection.clearSelection()
    tl.menu(s["fillet"], "Delete")


def fillet_deleted():
    from sciforge import surfmod

    h.idle_step()()
    steps = [o for o in s["box"].Group if surfmod.is_step(o)]
    kinds = sorted(surfmod.kind_of(o) for o in steps)
    h.check("the Fillet is gone", kinds == ["surface_delete_face", "surface_press_pull"], kinds)
    h.check(
        "the Press Pull and the Delete Face still compute",
        all("Invalid" not in list(o.State) for o in steps),
        [(o.Label, o.State) for o in steps],
    )
    # the floor 5 down without the round corner (2100), the right wall still deleted (300)
    h.check("area 1800", s4.near(st.area(s["box"]), 1800.0), st.area(s["box"]))
    xs = [round(f.CenterOfMass.x, 6) for f in s["box"].Shape.Faces]
    h.check("the right wall is the one deleted (not the left)", 30.0 not in xs and 0.0 in xs, xs)
    st.undo()


def fillet_back():
    h.idle_step()()
    h.check("Ctrl+Z: the fillet is back", s4.near(st.area(s["box"]), s["area"]), st.area(s["box"]))
    Gui.Selection.clearSelection()
    h.fit()
    st.menu("MODIFY", "Merge")


def merge_first():
    p = s4.panel()
    h.check("the Merge dialog", p is not None and p.kind == "surface_merge")
    h.click(V(5, 40, 5))


def merge_second():
    s4.settle()
    h.click(V(15, 40, 5))


def merge_ok():
    s4.settle()
    text = s4.message()
    h.check("says they become one face", "become one face" in text, text)
    st.ok()


def merged():
    h.check("dialog closed", s4.panel() is None)
    h.check("the strip: 2 faces", s4.faces(s["strip"]) == 2, s4.faces(s["strip"]))
    s["strip_area"] = st.area(s["strip"])
    s["titles"] = st.timeline_titles()
    s["label"] = s["box"].Label
    s["strip_label"] = s["strip"].Label
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface4-qa-"), "surface4_qa.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import surfmod

    box = (doc().getObjectsByLabel(s["label"]) or [None])[0]
    strip = (doc().getObjectsByLabel(s["strip_label"]) or [None])[0]
    h.check("the box and the strip are back", box is not None and strip is not None)
    if box is None or strip is None:
        return
    s["box"], s["strip"] = box, strip
    steps = [o for o in box.Group if surfmod.is_step(o)]
    kinds = sorted(surfmod.kind_of(o) for o in steps)
    h.check(
        "Fillet, Press Pull and Delete Face",
        kinds == ["surface_delete_face", "surface_fillet", "surface_press_pull"],
        kinds,
    )
    steps += [o for o in strip.Group if surfmod.is_step(o)]
    h.check(
        "every step computed",
        all("Invalid" not in list(o.State) and "Error" not in list(o.State) for o in steps),
        [(o.Label, o.State) for o in steps],
    )
    h.check("the box's area", s4.near(st.area(box), s["area"]), (st.area(box), s["area"]))
    h.check("the merged strip", s4.faces(strip) == 2 and s4.near(st.area(strip), s["strip_area"]))
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))
    h.check("double-clicked the Fillet", st.double_click_timeline(s["fillet"]))


def fillet_after_reopen():
    s4.settle()
    p = s4.panel()
    h.check("the Fillet edits after the reopen", p is not None and p.editing, p)
    h.check("Radius 3 reads back", p is not None and s4.near(p.fields["radius"][0].value(), 3.0))
    st.esc()


def closed_again():
    s4.settle()
    h.check("Esc closed it", s4.panel() is None)
    h.check("unchanged", s4.near(st.area(s["box"]), s["area"]))
    h.check("no error popup", not h.popups(), h.popups())


h.run(
    "surface4_qa",
    [
        empty_design,
        empty_fillet,
        empty_q,
        empty_q_open,
        empty_delete,
        empty_after_delete,
        setup,
        click_corner,
        type_radius,
        fillet_ok,
        filleted,
        edit_type,
        edit_preview,
        edit_cancelled,
        undone_once,
        redone,
        click_floor,
        pull_type,
        pull_ok,
        pulled,
        pull_edit,
        pull_edit_preview,
        pull_cancelled,
        delete_wall,
        wall_deleted,
        delete_edit,
        delete_edit_esc,
        delete_cancelled,
        fillet_deleted,
        fillet_back,
        merge_first,
        merge_second,
        merge_ok,
        merged,
        close,
        reopen,
        reopened,
        fillet_after_reopen,
        closed_again,
    ],
)
