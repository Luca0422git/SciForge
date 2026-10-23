# SPDX-License-Identifier: LGPL-2.1-or-later
"""SHEET METAL > Flange, contour flange, like a Fusion user, only real input; Cancel; save and
reopen.

Create Sketch on XY, an open L line (0,0)-(50,0)-(50,50), Finish Sketch. Flange, click the
line: the whole L is taken (chain), a contour flange 10 deep with the corner bent at the rule's
radius (volume by hand). Distance 20; Orientation Side 2 (the sheet outside the L); Direction
Symmetric (centred on the sketch); drag the arrow. Cancel: nothing is left, the sketch is
shown. Flange again on the line, Distance 20, OK: "Flange 1". Save, close, reopen: the body is
sheet metal with its rule, the same volume after a recompute, "Flange 1" opens again from the
timeline as a contour flange; Esc.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sheetmetal_steps as sm
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
MID = 96 + math.pi / 2 * 1.5  # mid-layer length of the L with the line outside (Side 1)


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SheetContour")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_l():
    sk = h.in_sketch()
    h.check("a sketch is open", sk is not None)
    if sk is not None:
        st.add_lines(sk, [(0, 0), (50, 0), (50, 50)])
        s["sketch"] = sk


def finish_sketch():
    h.ribbon("Finish Sketch")


def flange():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def click_line():
    h.fit()
    h.check("clicked the line", h.click_edge(V(25, 0, 0)))


def contour():
    sm.settle()
    p = sm.panel()
    h.check("a contour flange", p is not None and p.kind == "contour", p and p.kind)
    h.check("the whole L (chain)", p is not None and len(p.refs) == 2, p and p.refs)
    body = sm.target_body()
    s["body"] = body
    h.check(
        "10 deep, corner bent",
        body is not None and sm.near(sm.volume(body), 10 * MID, 1e-7),
        sm.volume(body),
    )
    h.check(
        "Distance, Direction and Bend Radius shown",
        sm.shown("distance") and sm.shown("direction") and sm.shown("override_bend_radius"),
    )
    h.check(
        "the distance arrow is there",
        p is not None and "distance" in p.arrows,
        p and list(p.arrows),
    )
    h.shot("1-contour")


def distance_20():
    sm.type_field("distance", "20")


def twenty():
    sm.settle()
    h.check("20 deep", sm.near(sm.volume(s["body"]), 20 * MID, 1e-7), sm.volume(s["body"]))
    box = s["body"].Shape.BoundBox
    h.check("the sheet inside the L", abs(box.XMax - 50) < 1e-6 and abs(box.YMin) < 1e-6, box)


def side_2():
    sm.choose("orientation", "Side 2")


def outside():
    sm.settle()
    box = s["body"].Shape.BoundBox
    h.check(
        "Side 2: the sheet outside the L",
        abs(box.XMax - 51) < 1e-6 and abs(box.YMin + 1) < 1e-6,
        box,
    )
    h.check(
        "bend inside radius 1 on the line",
        sm.near(sm.volume(s["body"]), 20 * (98 + math.pi / 2 * 1.5), 1e-7),
    )


def symmetric():
    sm.choose("direction", "Symmetric")


def centred():
    sm.settle()
    box = s["body"].Shape.BoundBox
    h.check(
        "Symmetric: centred on the sketch",
        abs(box.ZMin + 10) < 1e-6 and abs(box.ZMax - 10) < 1e-6,
        box,
    )


def drag():
    s["drag"] = sm.drag_arrow("distance", 30.0)


drag.wait_ms = 2200


def dragged():
    sm.settle()
    d = s.get("drag")
    h.check("the drag finished", d is not None and d.done, getattr(d, "error", None))
    p = sm.panel()
    value = p.options["distance"] if p else 0
    h.check("the drag changed the distance", abs(value - 20) > 2 and 5 < value < 60, value)
    box = s["body"].Shape.BoundBox
    h.check("the sheet followed", abs(box.ZLength - value) < 1e-6, (box, value))


def cancel():
    sm.cancel()


def cancelled():
    h.check("dialog closed", sm.panel() is None)
    h.check("Cancel: no sheet metal left", not sm.sheet_bodies(), sm.bodies())
    h.check("the sketch still shown", s["sketch"].ViewObject.Visibility)
    h.check("nothing in the timeline but the sketch", "Flange 1" not in sm.timeline_titles())


def flange_again():
    h.fit()
    h.ribbon("Flange")


def click_line_again():
    h.fit()
    h.check("clicked the line", h.click_edge(V(25, 0, 0)))


def distance_20_again():
    sm.settle()
    sm.type_field("distance", "20")


def ok():
    sm.settle()
    s["body"] = sm.target_body()
    h.check("20 deep again", sm.near(sm.volume(s["body"]), 20 * MID, 1e-7))
    sm.ok()


def done():
    h.check("dialog closed", sm.panel() is None)
    h.check("Flange 1 in the timeline", "Flange 1" in sm.timeline_titles(), sm.timeline_titles())
    h.check("the sketch hidden", not s["sketch"].ViewObject.Visibility)
    s["label"] = s["body"].Label
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-sheet-"), "sheet_contour.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    App.closeDocument(App.ActiveDocument.Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import sheetmetal

    doc = App.ActiveDocument
    body = [b for b in doc.Objects if b.TypeId == "PartDesign::Body" and b.Label == s["label"]]
    h.check("the body is back", len(body) == 1)
    if not body:
        return
    body = body[0]
    s["body"] = body
    h.check("still sheet metal", sheetmetal.is_sheet_metal_body(body))
    h.check("its rule", sheetmetal.body_rule_name(body) == "Steel (mm)")
    for obj in body.Group:
        obj.touch()
    doc.recompute()
    h.check(
        "the same flange after a recompute",
        sm.near(sm.volume(body), 20 * MID, 1e-7),
        sm.volume(body),
    )
    h.check("Flange 1 in the timeline", "Flange 1" in sm.timeline_titles(), sm.timeline_titles())


def edit():
    sm.double_click_timeline("Flange 1")


def edit_open():
    p = sm.panel()
    h.check("the dialog opens on the contour flange", p is not None and p.kind == "contour")
    h.check("its two curves", p is not None and len(p.refs) == 2)
    h.check("distance 20 read back", p is not None and abs(p.options["distance"] - 20) < 1e-9)
    # a stand-alone contour is no contour on a sheet edge (QA: it found its own edge)
    h.check("not taken for a contour on a sheet edge", p is not None and p.attached is None)
    h.check(
        "Distance, Orientation and Direction shown",
        sm.shown("distance") and sm.shown("orientation") and sm.shown("direction"),
    )
    h.shot("2-reopened-edit")


def esc():
    sm.esc()


def escaped():
    h.check("Esc closed it", sm.panel() is None)
    h.check("unchanged", sm.near(sm.volume(s["body"]), 20 * MID, 1e-7))


def design_2():
    App.newDocument("SheetContourEdge")
    h.fit()


def d2_sketch():
    h.ribbon("Create Sketch")


def d2_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def d2_rect():
    sm.rect_sketch(0, 0, 50, 30)


def d2_finish():
    h.ribbon("Finish Sketch")


def d2_flange():
    h.fit()
    h.click_empty()
    sm.tab()
    h.ribbon("Flange")


def d2_profile():
    h.fit()
    h.click(V(25, 15, 0))


def d2_ok():
    sm.settle()
    s["plate"] = sm.target_body()
    sm.ok()


def side_sketch():
    h.check("a plate", s["plate"] is not None and sm.near(sm.volume(s["plate"]), 1500.0))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def side_plane():
    from SciForgeTests.gui import plane_input as pl

    pl.click_square("XZ_Plane")


def side_lines():
    sk = h.in_sketch()
    h.check("a sketch on XZ", sk is not None)
    if sk is not None:
        st.add_lines(sk, [(50, 1), (50, 11), (60, 11)])


def side_finish():
    h.ribbon("Finish Sketch")


def edge_contour():
    h.fit()
    h.click_empty()
    h.ribbon("Flange")


def click_side_line():
    h.fit()
    h.check("clicked the line", h.click_edge(V(50, 0, 6)))


def on_edge():
    sm.settle()
    p = sm.panel()
    h.check("a contour flange", p is not None and p.kind == "contour", p and p.kind)
    h.check("found the sheet edge it starts at", p is not None and p.attached is not None)
    h.check("Operation Join", p is not None and p.operation_box.currentData() == "join")
    h.check("no Distance (it runs the whole edge)", not sm.shown("distance"))
    h.check(
        "says so", p is not None and "runs the whole edge" in p.mode.text(), p and p.mode.text()
    )
    vol = sm.volume(s["plate"])
    expect = 1470 + 30 * (2 * (math.pi / 2) * 1.5 + 7 + 8)
    h.check(
        "bent out of the sheet along the edge (by hand)", sm.near(vol, expect, 1e-7), (vol, expect)
    )
    h.shot("3-on-edge")


def ok_on_edge():
    sm.ok()


def on_edge_done():
    h.check("dialog closed", sm.panel() is None)
    h.check("Flange 2 in the timeline", "Flange 2" in sm.timeline_titles(), sm.timeline_titles())
    h.check("one sheet metal body", len(sm.sheet_bodies()) == 1, sm.sheet_bodies())


h.run(
    "sheetmetal_contour",
    [
        new_design,
        create_sketch,
        pick_xy,
        draw_l,
        finish_sketch,
        flange,
        click_line,
        contour,
        distance_20,
        twenty,
        side_2,
        outside,
        symmetric,
        centred,
        drag,
        dragged,
        cancel,
        cancelled,
        flange_again,
        click_line_again,
        distance_20_again,
        ok,
        done,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
        edit,
        edit_open,
        esc,
        escaped,
        design_2,
        d2_sketch,
        d2_xy,
        d2_rect,
        d2_finish,
        d2_flange,
        d2_profile,
        d2_ok,
        side_sketch,
        side_plane,
        side_lines,
        side_finish,
        edge_contour,
        click_side_line,
        on_edge,
        ok_on_edge,
        on_edge_done,
    ],
)
