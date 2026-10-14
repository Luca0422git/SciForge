# SPDX-License-Identifier: LGPL-2.1-or-later
"""The history marker before the first step (Fusion: an empty design) and the browser
using the timeline's names, only real input on the timeline, the browser and the view.

Part (real input): box 40 x 30 x 10 (Sketch 1, Extrude 1).
Path T1, drag the marker before Sketch 1: nothing is left (no solid, the sketch is not
         drawn), Sketch 1 and Extrude 1 are greyed, the marker is the first thing in the row.
Path T2, a post made there (Create Sketch on XY, a 10 x 10 square, E 15): Sketch 2 and
         Extrude 2 go in at the marker, before Sketch 1; only the post (1500) exists.
Path T3, Go to end: the box is built on the post: 12000 + 10 x 10 x 5 = 12500, nothing red.
         Ctrl+Z: the marker goes back (only the post); Ctrl+Y: 12500 again.
Path T4, the browser calls the sketches what the timeline calls them ("Sketch 1",
         "Sketch 2", not "Sketch" / "Sketch001"); Enter in its name field renames nothing.
Path T5, the playback buttons: Go to beginning empties the design again; Next step: the
         post; Go to end: everything."""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
BOX = 12000.0
POST = 1500.0
FULL = 12500.0
st = {}


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def order():
    return t.titles()


# -- T1: the marker before everything -----------------------------------------------------------
def t1_drag():
    h.check("box", t.near(t.volume(), BOX), t.volume())
    h.check("timeline", order() == ["Sketch 1", "Extrude 1"], order())
    t.drag_marker(before_title="Sketch 1")


def t1_empty():
    body = h.body()
    h.check("an empty design", body.Tip is None and body.Shape.isNull(), body.Tip)
    states = t.states()
    h.check(
        "Sketch 1 and Extrude 1 after the marker",
        states["Sketch 1"][0] == "rolled_back" and states["Extrude 1"][0] == "rolled_back",
        states,
    )
    tl = t.tl()
    h.check("the marker is first in the row", tl._timeline.marker == 0, tl._timeline.marker)
    first = tl._row.itemAt(0).widget() if tl._row.count() else None
    h.check(
        "drawn left of every step",
        first is not None and first.property("role") == "marker",
        first and first.property("role"),
    )
    h.check("the sketch is not drawn", not t.shown(t.obj("Sketch 1")))
    h.check("the extrude is not drawn", not t.shown(t.obj("Extrude 1")))
    h.shot("1-empty")


# -- T2: a post at the marker -------------------------------------------------------------------
def t2_create():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def t2_pick():
    h.click(V(12, -8, 0))  # the XY square (nothing else is shown)


def t2_draw():
    sk = h.in_sketch()
    if h.check("sketch open on XY", sk is not None):
        st["sketch"] = sk.Name
        h.draw_rectangle(sk, 10, 10, 20, 20)


def t2_finish():
    h.ribbon("Finish Sketch")


def t2_extrude():
    h.fit()
    h.press("e")


def t2_distance():
    p = xpanel()
    if h.check("Extrude opens with the square", p is not None and len(p.profiles) == 1):
        ui.type_into(p.distance.widget, "15")


def t2_ok():
    h.task_button("OK")


def t2_inserted():
    h.check(
        "Sketch 2 and Extrude 2 went in at the marker",
        order() == ["Sketch 2", "Extrude 2", "Sketch 1", "Extrude 1"],
        order(),
    )
    states = t.states()
    h.check(
        "the box is still after the marker",
        states["Extrude 2"][0] == "done" and states["Extrude 1"][0] == "rolled_back",
        states,
    )
    h.check("only the post: 1500", t.near(t.volume(), POST), t.volume())
    body = h.body()
    first = [o for o in body.Group if "BaseFeature" in o.PropertiesList][0]
    profile = getattr(first, "Profile", None)
    h.check(
        "the post is the body's first solid step",
        profile is not None and profile[0].Name == st.get("sketch"),
        (first.Name, profile),
    )
    h.check("built on nothing", first.BaseFeature is None, first.BaseFeature)
    h.shot("2-post")


# -- T3: Go to end, undo, redo ------------------------------------------------------------------
def t3_end():
    t.playback("end")


def t3_full():
    h.check("the box on the post: 12500", t.near(t.volume(), FULL), t.volume())
    items = t.tl().items()
    h.check(
        "nothing red", all(i.status == "ok" for i in items), [(i.display, i.message) for i in items]
    )
    h.check("marker at the end", t.tl()._timeline.at_end)
    t.ctrl("z")


def t3_undone():
    h.check("Ctrl+Z: the marker goes back (the post only)", t.near(t.volume(), POST), t.volume())
    t.ctrl("y")


def t3_redone():
    h.check("Ctrl+Y: 12500 again", t.near(t.volume(), FULL), t.volume())


# -- T4: the browser's names --------------------------------------------------------------------
def t4_names():
    rows = t.children("Sketches") or []
    h.check("the browser says Sketch 1, Sketch 2", sorted(rows) == ["Sketch 1", "Sketch 2"], rows)
    sk = App.ActiveDocument.getObject(st.get("sketch", ""))
    h.check(
        "Sketch 2 is FreeCAD's Sketch001",
        sk is not None and sk.Label != "Sketch 2" and t.tree().row(sk.Label) is not None,
        sk and sk.Label,
    )
    st["label"] = sk.Label if sk is not None else None
    t.click_row("Sketch 2")
    w.key(t.tree(), QtCore.Qt.Key_F2)


def t4_enter():
    field = t.browser_field()
    if h.check("F2 opens the name field", field is not None and field.isVisible()):
        h.check("it shows Sketch 2", field.text() == "Sketch 2", field.text())
        w.key(field, QtCore.Qt.Key_Return)


def t4_kept():
    sk = App.ActiveDocument.getObject(st.get("sketch", ""))
    h.check(
        "Enter renamed nothing", sk is not None and sk.Label == st.get("label"), sk and sk.Label
    )
    h.check("still Sketch 2 in the timeline", "Sketch 2" in order(), order())


# -- T5: playback -------------------------------------------------------------------------------
def t5_start():
    h.click_empty()
    t.playback("start")


def t5_empty():
    body = h.body()
    h.check("Go to beginning: an empty design", body.Tip is None and t.volume() == 0.0, t.volume())
    t.playback("next")


def t5_post():
    h.check("Next step: the post", t.near(t.volume(), POST), t.volume())
    t.playback("end")


def t5_end():
    h.check("Go to end: everything", t.near(t.volume(), FULL), t.volume())
    t.no_popups("the end")
    h.shot("3-end")


h.run(
    "gaps_timeline_start",
    t.watched(
        b.box_steps("TimelineStart")
        + [
            t1_drag,
            t1_empty,
            t2_create,
            t2_pick,
            t2_draw,
            t2_finish,
            t2_extrude,
            t2_distance,
            t2_ok,
            t2_inserted,
            t3_end,
            t3_full,
            t3_undone,
            t3_redone,
            t4_names,
            t4_enter,
            t4_kept,
            t5_start,
            t5_empty,
            t5_post,
            t5_end,
        ]
    ),
)
