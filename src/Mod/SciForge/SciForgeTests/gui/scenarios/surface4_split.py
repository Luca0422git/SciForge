# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Split Body with a surface body as the Splitting Tool (the hybrid
workflow: cut a solid with a sculpted surface), real input, then save and reopen.

A 40 x 30 x 20 box (solid) and a curved surface: an arc of radius 52 centred at x 20,
z -40 (the XZ plane), extruded 15 each way (it covers only half the box's depth: Extend
Splitting Tool carries it on). SURFACE tab, MODIFY > Split Body: click the box, then the
curved surface where it sticks out of the box: the whole surface body is the tool, the box
falls into two (below the arc: 30 x (integral of the arc over x 0..40) = 12825.46, above:
24000 - that). OK: a "Split Body" step, a new body with the top piece; the surface body
stays a surface. Undo: one box of 24000 again; Redo. Save (Ctrl+S, version description),
close, open again: both pieces are back with their volumes and the timeline is the same.
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
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
BOX = 24000.0
# below the arc z = -40 + sqrt(52^2 - (x - 20)^2), x 0..40, times the depth 30
BELOW = 30 * (20 * 48 + 52**2 * math.asin(20.0 / 52.0) - 40 * 40)


def doc():
    return App.ActiveDocument


def split_panel():
    from sciforge import split_ui

    p = split_ui.SplitPanel.last
    return p if p is not None and not p._closed else None


def setup():
    from sciforge import bodies, extrude, surface

    s4.new_design("Surface4Split")
    sk = s4.sketch([(0, 0), (40, 0), (40, 30), (0, 30)])
    box_body = bodies.body_of(sk)
    extrude.make(box_body, sk, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["box"] = box_body
    arc = s4.arc_sketch(20, -40, 52, 40, 140, plane="XZ_Plane", body=box_body)
    step = surface.build(
        "extrude", {"refs": s4.edges(arc)}, {"distance": 15.0, "direction": "symmetric"}
    )
    doc().recompute()
    bodies.set_shown(arc, False)
    s["tool"] = bodies.body_of(step)
    h.fit()
    h.check("a 24000 box", st.near(st.volume(s["box"]), BOX), st.volume(s["box"]))
    h.check("a surface body as the tool", surface.is_surface_body(s["tool"]))


def split_menu():
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Split Body")


def click_box():
    p = split_panel()
    h.check("the Split Body dialog", p is not None)
    h.click(V(40, 25, 3))


def click_surface():
    p = split_panel()
    h.check(
        "the box is the body to split",
        p is not None and p.options["body"] is s["box"],
        p and p.options["body"],
    )
    h.click(V(50, 0, -40 + math.sqrt(52**2 - 30**2)))


def pieces():
    from sciforge import split

    st.settle()
    h.idle_step()()
    p = split_panel()
    h.check(
        "the whole surface body is the tool",
        p is not None and p.options["tools"] == [(s["tool"], "")],
        p and p.options["tools"],
    )
    feature = p.target if p is not None else None
    others = split.piece_bodies(feature) if feature is not None else []
    h.check("one new body", len(others) == 1, others)
    total = st.volume(s["box"]) + sum(st.volume(b) for b in others)
    h.check("the pieces make the box", st.near(total, BOX, 1e-6), total)
    vols = sorted([st.volume(s["box"])] + [st.volume(b) for b in others])
    h.check("below the arc: 12825.46", st.near(vols[1], BELOW, 1e-5), (vols, BELOW))
    h.shot("1-split")
    st.ok()


def split_done():
    from sciforge import split, surface

    h.check("dialog closed", split_panel() is None)
    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    h.check("a Split Body step", feature is not None)
    s["piece"] = split.piece_bodies(feature)[0] if feature is not None else None
    h.check("the tool is still a surface body", surface.is_surface_body(s["tool"]))
    titles = st.timeline_titles()
    h.check("Split Body in the timeline", any(t.startswith("Split Body") for t in titles), titles)
    s["volumes"] = (st.volume(s["box"]), st.volume(s["piece"]))
    st.undo()


def undone():
    h.check("undo: the box whole", st.near(st.volume(s["box"]), BOX), st.volume(s["box"]))
    st.redo()


def redone():
    h.check(
        "redo: split again",
        st.near(st.volume(s["box"]), s["volumes"][0], 1e-6),
        st.volume(s["box"]),
    )
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface4-"), "surface4_split.FCStd")
    s["path"] = path
    s["labels"] = [s["box"].Label, s["tool"].Label, s["piece"].Label]
    s["titles"] = st.timeline_titles()
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("nothing unsaved", not doc().isTouched())
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import surface

    found = [doc().getObjectsByLabel(x) for x in s["labels"]]
    box, tool, piece = (f[0] if f else None for f in found)
    h.check("the three bodies are back", None not in (box, tool, piece), s["labels"])
    if None in (box, tool, piece):
        return
    h.check("the box piece", st.near(st.volume(box), s["volumes"][0], 1e-6), st.volume(box))
    h.check("the new piece", st.near(st.volume(piece), s["volumes"][1], 1e-6))
    h.check("the tool is a surface body", surface.is_surface_body(tool))
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))


h.run(
    "surface4_split",
    [
        setup,
        split_menu,
        click_box,
        click_surface,
        pieces,
        split_done,
        undone,
        redone,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
    ],
)
