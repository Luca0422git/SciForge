# SPDX-License-Identifier: LGPL-2.1-or-later
"""More of the timeline the way Fusion users use it (QA, only real input on the
timeline, the browser and the dialogs).

Part (real input): box 40 x 30 x 10, a sketch on the top face with a circle r5 at the
middle, E = a boss 5 high.

Path 19, the marker before a sketch: the boss and its sketch are rolled back (the
         sketch is not drawn and its timeline icon is greyed). Double-click the sketch:
         Fusion rolls to it and opens it; Finish Sketch puts the marker back.
         Edit Profile Sketch on the rolled-back boss does the same.
Path 20, double-click a feature while a sketch is open: the sketch closes, the
         feature's dialog opens; Cancel leaves everything as it was.
Path 21, rename a step, Ctrl+Z: the old name is back; Ctrl+Y: the new one.
Path 22, Roll History Marker Here on the sketch, then a new sketch + extrude: they go in
         at the marker; Ctrl+Z twice takes them out again.
Path 23, delete the first extrude (everything is built on it): the sketch on its face
         stays where it was (yellow, the reason on hover), the boss still builds,
         nothing in the Report view; Ctrl+Z.
Path 24, a long design (60 more steps): a new step made with E is in view at the end of
         the timeline, the mouse wheel scrolls it, a far step can still be dragged to.
Path 25, the mouse over a step lights up what it made in the 3D view (a sketch: its
         curves); leaving the icon clears it.

Numbers by hand: box 12000; boss r5 x 5 = 125 pi; the second boss r3 x 4 = 36 pi.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtGui, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
s = {}
BOX = 12000.0
BOSS = 125.0 * math.pi
SMALL = 36.0 * math.pi


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def boss_steps(tag, point, center, radius, height):
    """Create Sketch on the face at `point`, a circle, Finish Sketch, E, type, OK."""

    def create():
        h.click_empty()
        h.ribbon("Create Sketch")

    def pick():
        h.fit()
        h.click(point)

    def draw():
        sk = h.in_sketch()
        h.check("sketch %s open" % tag, sk is not None)
        if sk:
            x, y = h.to_sketch(sk, center)
            h.draw_circle(sk, x, y, radius)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def distance():
        p = xpanel()
        h.check("Extrude picked circle %s" % tag, p is not None and len(p.profiles) == 1)
        if p is not None:
            ui.type_into(p.distance.widget, "%g" % height)

    def ok():
        h.task_button("OK")

    return [
        t.step(create, "%s_create" % tag),
        t.step(pick, "%s_pick" % tag),
        t.step(draw, "%s_draw" % tag),
        t.step(finish, "%s_finish" % tag),
        t.step(extrude, "%s_extrude" % tag),
        t.step(distance, "%s_distance" % tag),
        t.step(ok, "%s_ok" % tag),
    ]


def part_made():
    h.check("box with a boss", t.near(t.volume(), BOX + BOSS), t.volume())
    h.check(
        "four steps",
        t.titles() == ["Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        t.titles(),
    )
    t.click_eye(t.obj("Sketch 2").Label)  # Luca keeps the boss sketch shown


# -- Path 19: the marker before a sketch ---------------------------------------------------------
def p19_roll():
    h.check("the boss sketch is shown", t.shown(t.obj("Sketch 2")))
    t.drag_marker(before_title="Sketch 2")


def p19_rolled():
    st = t.states()
    h.check(
        "Sketch 2 and Extrude 2 after the marker",
        st["Sketch 2"][0] == "rolled_back" and st["Extrude 2"][0] == "rolled_back",
        st,
    )
    h.check("the sketch is not drawn", not t.shown(t.obj("Sketch 2")))
    h.check("box only", t.near(t.volume(), BOX), t.volume())
    b_ = t.button("Sketch 2")
    h.check("its icon is greyed", b_ is not None and b_.property("state") == "rolled_back")
    h.shot("1-before-sketch")
    t.double_click("Sketch 2")


def p19_editing():
    sk = h.in_sketch()
    h.check(
        "double-click opens the rolled-back sketch",
        sk is not None and sk.Name == t.item("Sketch 2").name,
    )
    h.check("Fusion rolls to it", t.item("Sketch 2").state == "done", t.states())


def p19_finish():
    h.ribbon("Finish Sketch")


def p19_back():
    h.check("left the sketch", h.in_sketch() is None)
    st = t.states()
    h.check("the marker is back before the sketch", st["Sketch 2"][0] == "rolled_back", st)
    h.check("the sketch is hidden again", not t.shown(t.obj("Sketch 2")))
    t.menu("Extrude 2", "Edit Profile Sketch")


def p19_profile():
    sk = h.in_sketch()
    h.check("Edit Profile Sketch opens it", sk is not None and sk.Name == t.item("Sketch 2").name)


def p19_profile_finish():
    h.ribbon("Finish Sketch")


def p19_profile_back():
    st = t.states()
    h.check("and the marker goes back again", st["Sketch 2"][0] == "rolled_back", st)
    t.drag_marker(to_end=True)


def p19_end():
    h.check("at the end the sketch is drawn again", t.shown(t.obj("Sketch 2")))
    h.check("box and boss", t.near(t.volume(), BOX + BOSS), t.volume())


# -- Path 20: double-click a feature while a sketch is open ------------------------------------------
def p20_open_sketch():
    t.double_click("Sketch 1")


def p20_double_click_feature():
    h.check("in Sketch 1", h.in_sketch() is not None)
    t.double_click("Extrude 2")


def p20_feature_dialog():
    h.check("the sketch closed", h.in_sketch() is None)
    p = xpanel()
    h.check("Extrude opened on Extrude 2", p is not None and p.target is not None)
    h.task_button("Cancel")


def p20_cancelled():
    h.check("nothing changed", t.near(t.volume(), BOX + BOSS), t.volume())
    h.check("no dialog", not t.dialog_open())


# -- Path 21: rename, Ctrl+Z, Ctrl+Y --------------------------------------------------------------------
def p21_rename():
    t.menu("Extrude 2", "Rename")


def p21_type():
    field = t.rename_field()
    if h.check("name field", field is not None):
        from SciForgeTests.gui import widget_input as w

        w.key(field, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(field, "Boss")
        w.key(field, QtCore.Qt.Key_Return)


def p21_undo():
    h.check("renamed", "Boss" in t.titles(), t.titles())
    t.ctrl("z")


def p21_undone():
    h.check("Ctrl+Z: old name", t.titles()[-1] == "Extrude 2", t.titles())
    t.ctrl("y")


def p21_redone():
    h.check("Ctrl+Y: Boss again", t.titles()[-1] == "Boss", t.titles())


# -- Path 22: Roll History Marker Here on a sketch, then new steps -----------------------------------------
def p22_roll_here():
    t.menu("Sketch 2", "Roll History Marker Here")


def p22_rolled():
    st = t.states()
    h.check(
        "the marker right after the sketch",
        st["Sketch 2"][0] == "done" and st["Boss"][0] == "rolled_back",
        st,
    )
    h.check("box only", t.near(t.volume(), BOX), t.volume())


P22 = boss_steps("p22", V(10, 8, 10), V(8, 8, 10), 3, 4)


def p22_inserted():
    titles = t.titles()
    h.check(
        "the new sketch and extrude are at the marker",
        titles == ["Sketch 1", "Extrude 1", "Sketch 2", "Sketch 3", "Extrude 3", "Boss"],
        titles,
    )
    h.check("Boss still after the marker", t.item("Boss").state == "rolled_back", t.states())
    h.check("box with the small boss", t.near(t.volume(), BOX + SMALL), t.volume())
    t.ctrl("z")


def p22_undo_once():
    t.ctrl("z")


def p22_undo_twice():
    t.ctrl("z")


p22_undo_twice.wait_ms = 1200


def p22_undone():
    titles = t.titles()
    h.check(
        "Ctrl+Z takes them out again",
        titles == ["Sketch 1", "Extrude 1", "Sketch 2", "Boss"],
        titles,
    )
    t.drag_marker(to_end=True)


def p22_end():
    h.check("box and boss", t.near(t.volume(), BOX + BOSS), t.volume())


# -- Path 23: delete the first extrude ----------------------------------------------------------------------
def p23_delete():
    t.menu("Extrude 1", "Delete")


def p23_deleted():
    i = t.item("Sketch 2")
    h.check(
        "the sketch on its face stays, yellow",
        i is not None and i.status == "warning",
        i and (i.status, i.message),
    )
    tip = t.button("Sketch 2").toolTip() if i is not None else ""
    h.check("the reason on hover", "Warning" in tip, tip)
    boss = t.item("Boss")
    h.check("the boss still builds", boss is not None and boss.status == "ok", t.states())
    h.check("only the boss is left", t.near(t.volume(), BOSS), t.volume())
    h.shot("2-first-deleted")
    t.ctrl("z")


def p23_undone():
    h.check("Ctrl+Z: box and boss", t.near(t.volume(), BOX + BOSS), t.volume())
    st = t.states()
    h.check("nothing yellow or red", all(v[1] == "ok" for v in st.values()), st)


# -- Path 25: hover a step ------------------------------------------------------------------------------------
def hover_nodes():
    """Names of the highlight nodes in the 3D view's scene (looked up fresh)."""
    sg = Gui.ActiveDocument.ActiveView.getSceneGraph()
    return [
        sg.getChild(i).getName().getString()
        for i in range(sg.getNumChildren())
        if sg.getChild(i).getName().getString() == "SciForgeTimelineHover"
    ]


def p25_hover_boss():
    b_ = t.button("Boss")
    from SciForgeTests.gui import widget_input as w

    w.move(b_, w.center(b_) + QtCore.QPoint(3, 0))
    w.move(b_, w.center(b_))


def p25_lit():
    tl = t.tl()
    h.check("the mouse over Boss lights it up", tl.hovered() == t.item("Boss").name, tl.hovered())
    h.check("drawn in the 3D view", len(hover_nodes()) == 1, hover_nodes())
    h.shot("2b-hover")
    from SciForgeTests.gui import widget_input as w

    w.move(h.gl_widget(), QtCore.QPoint(200, 200))


def p25_gone():
    h.check("leaving the icon clears it", t.tl().hovered() is None, t.tl().hovered())
    h.check("nothing left in the 3D view", not hover_nodes(), hover_nodes())
    b_ = t.button("Sketch 2")
    from SciForgeTests.gui import widget_input as w

    w.move(b_, w.center(b_) + QtCore.QPoint(3, 0))
    w.move(b_, w.center(b_))


def p25_sketch():
    h.check("a sketch lights up too", t.tl().hovered() == t.item("Sketch 2").name, t.tl().hovered())
    from SciForgeTests.gui import widget_input as w

    w.move(h.gl_widget(), QtCore.QPoint(200, 200))


# -- Path 24: a long design -----------------------------------------------------------------------------------
def p24_many_steps():
    """60 more steps (posts on the box), made in code: what is tested is the timeline."""
    from sciforge import commands, extrude, sketch_ui

    body = commands.find_body()
    top = t.obj("Boss")
    for i in range(30):
        sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
        sk.addGeometry(Part.Circle(V(-10 - (i % 6) * 8, (i // 6) * 8, 0), V(0, 0, 1), 2))
        sk.recompute()
        extrude.make(body, sk, {"distance": 3.0})
    App.ActiveDocument.recompute()
    s["posts"] = 30 * 4.0 * math.pi * 3.0
    s["top"] = top.Name
    h.fit()


P24 = boss_steps("p24", V(30, 25, 10), V(32, 25, 10), 3, 4)


def in_view(widget):
    """The widget lies inside the visible part of the timeline's scroll area."""
    if widget is None:
        return False
    tl = t.tl()
    left = widget.mapTo(tl._inner, QtCore.QPoint(0, 0)).x()
    start = tl._scroll.horizontalScrollBar().value()
    return start <= left and left + widget.width() <= start + tl._scroll.viewport().width()


def view_info():
    tl = t.tl()
    bar = tl._scroll.horizontalScrollBar()
    marker = tl.marker()
    return (
        bar.value(),
        bar.maximum(),
        tl._scroll.viewport().width(),
        marker.mapTo(tl._inner, QtCore.QPoint(0, 0)).x() if marker else None,
    )


def p24_in_view():
    tl = t.tl()
    h.check("64 + 2 steps", len(t.titles()) == 66, len(t.titles()))
    h.check("the marker is in view", in_view(tl.marker()), view_info())
    h.check("the new extrude's icon is in view", in_view(tl._buttons[-1]), view_info())
    h.check(
        "everything",
        t.near(t.volume(), BOX + BOSS + s["posts"] + SMALL),
        (t.volume(), BOX + BOSS + s["posts"] + SMALL),
    )
    h.shot("3-long")


def p24_wheel():
    tl = t.tl()
    view = tl._scroll.viewport()
    s["scroll"] = tl._scroll.horizontalScrollBar().value()
    for _ in range(40):  # the wheel turned towards the start
        event = QtGui.QWheelEvent(
            QtCore.QPointF(50, 10),
            QtCore.QPointF(view.mapToGlobal(QtCore.QPoint(50, 10))),
            QtCore.QPoint(0, 0),
            QtCore.QPoint(0, 120),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase,
            False,
        )
        QtWidgets.QApplication.sendEvent(view, event)
    QtWidgets.QApplication.processEvents()


def p24_scrolled():
    tl = t.tl()
    h.check(
        "the wheel scrolls to the start",
        tl._scroll.horizontalScrollBar().value() == 0,
        (s["scroll"], tl._scroll.horizontalScrollBar().value()),
    )
    h.check("Extrude 1 is in view again", in_view(tl._buttons[1]), view_info())
    t.drag_marker(before_title="Sketch 2")


def p24_rolled():
    h.check("the marker could be dragged far back", t.near(t.volume(), BOX), t.volume())
    h.check("and is in view", in_view(t.tl().marker()), view_info())
    t.playback("end")


def p24_end():
    h.check("Go to end", t.near(t.volume(), BOX + BOSS + s["posts"] + SMALL), t.volume())
    h.check("the marker is in view at the end", in_view(t.tl().marker()), view_info())
    t.no_popups("the end")
    h.shot("4-end")


STEPS = (
    b.box_steps("TimelineQA4")
    + boss_steps("boss", V(30, 20, 10), V(20, 15, 10), 5, 5)
    + [
        part_made,
        p19_roll,
        p19_rolled,
        p19_editing,
        p19_finish,
        p19_back,
        p19_profile,
        p19_profile_finish,
        p19_profile_back,
        p19_end,
        p20_open_sketch,
        p20_double_click_feature,
        p20_feature_dialog,
        p20_cancelled,
        p21_rename,
        p21_type,
        p21_undo,
        p21_undone,
        p21_redone,
        p22_roll_here,
        p22_rolled,
    ]
    + P22
    + [
        p22_inserted,
        p22_undo_once,
        p22_undo_twice,
        p22_undone,
        p22_end,
        p23_delete,
        p23_deleted,
        p23_undone,
        p25_hover_boss,
        p25_lit,
        p25_gone,
        p25_sketch,
        p24_many_steps,
    ]
    + P24
    + [p24_in_view, p24_wheel, p24_scrolled, p24_rolled, p24_end]
)

h.run("timeline_browser_qa4", t.watched(STEPS))
