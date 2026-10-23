# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA of surface-4: Mirror Join of a surface body and Split Body by a surface across a save
and a reopen, and a changed edit cancelled with Esc, real input.

Half an open box of surfaces (30 x 20 floor, walls 10 high on three sides, open at x = 0:
area 1400) and, beside it, a 40 x 30 x 20 solid box (at x 60 .. 100) with a curved surface
over it (an arc of radius 52 in the XZ plane, extruded 15 each way: half the box's depth).
SURFACE > CREATE > Mirror: click a wall, Operation Join, the YZ square: one surface of 2800.
Stitch Tolerance 0.5, OK. SURFACE > MODIFY > Split Body: the box, then the curved surface,
OK: two pieces. Double-click the Split Body: Extend Splitting Tool off (the surface no longer
reaches through: the dialog says so), Esc: the two pieces are as they were, Extend on.
Save, close, reopen: the mirror is still stitched (2800, one shell) with its Stitch Tolerance
0.5, the split's two pieces have their volumes, the timeline is the same. Double-click the
Mirror: Join and 0.5 read back; Esc: nothing changes.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
BOX = 24000.0
BELOW = 30 * (20 * 48 + 52**2 * math.asin(20.0 / 52.0) - 40 * 40)


def doc():
    return App.ActiveDocument


def split_panel():
    from sciforge import split_ui

    p = split_ui.SplitPanel.last
    return p if p is not None and not p._closed else None


def mirror_step():
    from sciforge import pattern

    found = [o for o in doc().Objects if pattern.kind_of(o) == "mirror"]
    return found[0] if found else None


def split_volumes():
    from sciforge import split

    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    pieces = split.piece_bodies(feature) if feature is not None else []
    return sorted([round(st.volume(s["box"]), 4)] + [round(st.volume(p), 4) for p in pieces])


def setup():
    from sciforge import bodies, extrude, surface

    s4.new_design("Surface4QAReopen")
    s["half"] = s4.surface_box(open_side=True)
    sk = s4.sketch([(60, 0), (100, 0), (100, 30), (60, 30)])
    box_body = bodies.body_of(sk)
    extrude.make(box_body, sk, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["box"] = box_body
    arc = s4.arc_sketch(80, -40, 52, 40, 140, plane="XZ_Plane", body=box_body)
    step = surface.build(
        "extrude", {"refs": s4.edges(arc)}, {"distance": 15.0, "direction": "symmetric"}
    )
    doc().recompute()
    bodies.set_shown(arc, False)
    s["tool"] = bodies.body_of(step)
    h.fit()
    h.check("the half box: 1400", st.near(st.area(s["half"]), 1400.0), st.area(s["half"]))
    h.check("a 24000 box", st.near(st.volume(s["box"]), BOX), st.volume(s["box"]))
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("CREATE", "Mirror")


def click_wall():
    p = ps.panel()
    h.check("the Mirror dialog", p is not None and p.kind == "mirror")
    h.click(V(15, 0, 5))


def choose_join():
    p = ps.panel()
    h.check("Pattern Type is Bodies", p is not None and p.pattern_type.currentData() == "bodies")
    if p is not None:
        b.choose(p.operation, "Join")
    ps.click_box("plane")


def click_yz():
    h.fit()
    pl.click_square("YZ_Plane")


def tolerance():
    s4.settle()
    h.idle_step()()
    p = ps.panel()
    h.check("one surface of 2800", st.near(st.area(s["half"]), 2800.0), st.area(s["half"]))
    if p is not None:
        bs.type_value(p.stitch_field.widget, "0.5")


def mirror_ok():
    h.idle_step()()
    h.task_button("OK")


def mirrored():
    step = mirror_step()
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check(
        "Stitch Tolerance 0.5",
        step is not None and abs(step.StitchTolerance.Value - 0.5) < 1e-9,
        step and step.StitchTolerance,
    )
    h.check("2800, one shell", len(s["half"].Shape.Shells) == 1)
    Gui.Selection.clearSelection()
    h.fit()
    st.menu("MODIFY", "Split Body")


def click_box():
    p = split_panel()
    h.check("the Split Body dialog", p is not None)
    h.click(V(100, 25, 3))


def click_surface():
    h.click(V(110, 0, -40 + math.sqrt(52**2 - 30**2)))


def split_ok():
    st.settle()
    h.idle_step()()
    p = split_panel()
    h.check(
        "the whole surface body is the tool",
        p is not None and p.options["tools"] == [(s["tool"], "")],
        p and p.options["tools"],
    )
    st.ok()


def split_done():
    vols = split_volumes()
    s["vols"] = vols
    h.check("two pieces", len(vols) == 2, vols)
    h.check("below the arc: 12825.46", len(vols) == 2 and st.near(vols[1], BELOW, 1e-5), vols)
    titles = st.timeline_titles()
    s["split"] = next((t for t in titles if t.startswith("Split Body")), "Split Body")
    Gui.Selection.clearSelection()
    h.check("double-clicked the Split Body", st.double_click_timeline(s["split"]))


def extend_off():
    h.idle_step()()
    p = split_panel()
    h.check("the Split Body edit", p is not None)
    h.check("Extend Splitting Tool on", p is not None and p.extend.isChecked())
    if p is not None:
        bs.toggle(p.extend)


def refused_preview():
    st.settle()
    h.idle_step()()
    p = split_panel()
    text = p.message.text() if p is not None else ""
    h.check("says the tool does not cut it in two", "two" in text or "cut" in text, text)
    st.esc()


def split_cancelled():
    from sciforge import split

    h.idle_step()()
    h.check("Esc closed it", split_panel() is None)
    h.check("the pieces are as they were", split_volumes() == s["vols"], split_volumes())
    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    h.check(
        "Extend Splitting Tool still on",
        feature is not None and split.read(feature)["extend"],
    )
    h.check("no error popup", not h.popups(), h.popups())
    s["titles"] = st.timeline_titles()
    s["labels"] = (s["half"].Label, s["box"].Label)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface4-qa-"), "qa_reopen.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    half = (doc().getObjectsByLabel(s["labels"][0]) or [None])[0]
    box = (doc().getObjectsByLabel(s["labels"][1]) or [None])[0]
    h.check("the bodies are back", half is not None and box is not None)
    if half is None or box is None:
        return
    s["half"], s["box"] = half, box
    step = mirror_step()
    h.check("the mirror computed", step is not None and "Invalid" not in list(step.State))
    h.check(
        "still stitched: 2800, one shell",
        st.near(st.area(half), 2800.0) and len(half.Shape.Shells) == 1,
        (st.area(half), len(half.Shape.Shells)),
    )
    h.check(
        "Stitch Tolerance 0.5 kept",
        step is not None and abs(step.StitchTolerance.Value - 0.5) < 1e-9,
        step and step.StitchTolerance,
    )
    h.check("the split pieces", split_volumes() == s["vols"], (split_volumes(), s["vols"]))
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))
    mirror = next((t for t in titles if t.startswith("Mirror")), "Mirror")
    h.check("double-clicked the Mirror", st.double_click_timeline(mirror))


def mirror_edit():
    h.idle_step()()
    p = ps.panel()
    h.check("the Mirror edit", p is not None and p.editing, p)
    if p is None:
        return
    h.check("Join reads back", p.operation.currentData() == "join", p.operation.currentData())
    h.check(
        "Stitch Tolerance 0.5 reads back",
        p.stitch_field.widget.isVisible() and st.near(p.stitch_field.value(), 0.5),
        p.stitch_field.value(),
    )
    st.esc()


def closed_unchanged():
    h.idle_step()()
    h.check("Esc closed it", not Gui.Control.activeDialog())
    h.check("still 2800", st.near(st.area(s["half"]), 2800.0), st.area(s["half"]))
    h.check("no error popup", not h.popups(), h.popups())


h.run(
    "surface4_qa_reopen",
    [
        setup,
        click_wall,
        choose_join,
        click_yz,
        tolerance,
        mirror_ok,
        mirrored,
        click_box,
        click_surface,
        split_ok,
        split_done,
        extend_off,
        refused_preview,
        split_cancelled,
        close,
        reopen,
        reopened,
        mirror_edit,
        closed_unchanged,
    ],
)
