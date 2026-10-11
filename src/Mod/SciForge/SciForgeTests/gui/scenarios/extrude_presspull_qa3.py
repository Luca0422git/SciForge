# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude and Press Pull, power-user paths (QA, only real input).

Path 11, edits with later steps on top: a boss sketched on the top face, the first
         extrude made taller from the timeline (the boss follows), the boss switched to
         Cut from the timeline, Undo brings the boss back.
Path 12, a new extrude with the history marker rolled back: it goes in before the later
         steps, the marker dragged back to the end keeps everything valid.
Path 13, Press Pull's other modes: an edge (round), a click on a face while rounding
         edges (explained, no error), the round's face (radius edit in place), a typed
         expression.
Path 10, a second profile of a sketch already used: extrude the ring, show the sketch
         again with the browser's eye, extrude the disc (seen from the top).
Path 14, profiles from two sketches in one extrude, edited, saved, reopened, edited.

Numbers by hand: 40 x 30 rectangle with an r5 circle at (20, 15).
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
RING = 1200.0 - 25.0 * math.pi
DISC = 25.0 * math.pi
BOSS = 9.0 * math.pi  # r3


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def ppanel():
    from sciforge import presspull_ui

    return presspull_ui.PressPullPanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def shown():
    b = h.body()
    return bool(b and b.Tip and b.ViewObject.Visibility and b.Tip.ViewObject.Visibility)


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def step(fn, name):
    fn.__name__ = name
    return fn


def tl():
    from sciforge import timeline_ui

    t = timeline_ui.widget()
    t.refresh()
    QtWidgets.QApplication.processEvents()
    return t


def timeline_menu(title, entry):
    for b in tl()._buttons:
        if b.item.display == title:
            return w.right_click(b, w.center(b), entry)
    h.check("timeline has %r" % title, False, tl().titles())
    return False


def browser():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()
    return t


def click_eye(label):
    t = browser()
    item = t.row(label)
    h.check("browser row %r" % label, item is not None, t.labels())
    if item is not None:
        w.click(t.viewport(), t.eye_point(item))


def sketch_on(tag, point, draw_fn):
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
            draw_fn(sk)
            s["sketch_" + tag] = sk

    def finish():
        h.ribbon("Finish Sketch")

    def after():
        h.check("left sketch %s" % tag, h.in_sketch() is None)
        h.fit()

    return [
        step(create, "sketch_%s_create" % tag),
        step(pick, "sketch_%s_pick" % tag),
        step(draw, "sketch_%s_draw" % tag),
        step(finish, "sketch_%s_finish" % tag),
        step(after, "sketch_%s_after" % tag),
    ]


def rect(x0, y0, x1, y1, z):
    def draw(sk):
        ax, ay = h.to_sketch(sk, V(x0, y0, z))
        bx, by = h.to_sketch(sk, V(x1, y1, z))
        h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    return draw


def circle(cx, cy, r, z):
    def draw(sk):
        x, y = h.to_sketch(sk, V(cx, cy, z))
        h.draw_circle(sk, x, y, r)

    return draw


# -- Path 10: a second profile of a used sketch ----------------------------------------------
def p11_new():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QAPower")
    h.fit()


def p10_new():
    App.newDocument("QAReuse")
    h.fit()


def p10_e():
    h.fit()
    h.press("e")


def p10_ring():
    h.click(V(3, 3, 0))


def p11_both():
    h.click(V(20, 15, 0))


def p11_block_ok():
    p = xpanel()
    h.check("ring and disc: the full block", len(p.profiles) == 2, p.profiles)
    h.check("block 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.task_button("OK")


def p10_ring_ok():
    h.check("ring 10", near(h.solid_volume(), RING * 10.0), h.solid_volume())
    h.task_button("OK")


def p10_show_sketch():
    h.check("the used sketch is hidden", not s["sketch_plate"].ViewObject.Visibility)
    click_eye("Sketch")


def p10_e_again():
    h.check("the browser's eye shows it", s["sketch_plate"].ViewObject.Visibility)
    h.fit()
    h.press("e")


def p10_regions_offered():
    p = xpanel()
    names = [(r[0].Name, r[1]) for r in p.picker.regions] if p.picker else []
    h.check("the shown sketch's areas are offered again", len(names) >= 2, names)
    h.check("nothing picked by itself (the sketch is used)", p.target is None)
    # The disc lies at the bottom of the hole: from the top it can be seen (and clicked).
    h.fit(iso=False)
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()
    h.click(V(20, 15, 0))


def p10_disc():
    p = xpanel()
    h.check("the disc picked", len(p.profiles) == 1, p.profiles)
    h.check("Join (the hole is empty)", p.operation.currentText() == "Join")
    h.check("disc fills the hole: 12000", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.task_button("OK")


def p10_done():
    h.check("two extrudes from one sketch", not dialog_open() and shown())
    h.check("the sketch is hidden again", not s["sketch_plate"].ViewObject.Visibility)
    h.fit()


# -- Path 11: edits with later steps on top ---------------------------------------------------
def p11_boss_e():
    h.fit()
    h.press("e")


def p11_boss_type():
    p = xpanel()
    h.check("boss circle picked by itself", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "5")


def p11_boss_ok():
    h.check("boss r3 x 5", near(h.solid_volume(), 12000.0 + BOSS * 5), h.solid_volume())
    s["boss"] = xpanel().target.Name
    h.task_button("OK")


def p11_edit_first():
    h.check("boss kept", not dialog_open())
    h.check("double-click Extrude 1", ui.double_click_timeline("Extrude 1"), ui.timeline_titles())


def p11_taller():
    p = xpanel()
    h.check("editing the ring", p is not None and p.editing and not p._closed)
    if p is not None and p.editing:
        ui.type_into(p.distance.widget, "12")


def p11_taller_ok():
    h.task_button("OK")


def p11_followed():
    want = 14400.0 + BOSS * 5.0
    h.check(
        "the block 12 tall, the boss on top",
        near(h.solid_volume(), want, 1e-5),
        (h.solid_volume(), want),
    )
    h.check("no step in error", not broken(), broken())
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"), ui.timeline_titles())


def p11_boss_to_cut():
    p = xpanel()
    h.check("editing the boss", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("choose Operation: Cut", ui.choose(p.operation, "Cut"))
    ui.type_into(p.distance.widget, "-5")


def p11_cut_ok():
    want = 14400.0 - BOSS * 5.0
    h.check(
        "the boss is now a hole r3 x 5",
        near(h.solid_volume(), want, 1e-5),
        (h.solid_volume(), want, xpanel().message.text()),
    )
    h.task_button("OK")


def p11_undo():
    h.check("cut kept", not dialog_open() and shown())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p11_undone():
    want = 14400.0 + BOSS * 5.0
    h.check("Undo: the boss is back", near(h.solid_volume(), want, 1e-5), h.solid_volume())
    h.check("the part is drawn", shown())
    pads = [o for o in h.body().Group if o.TypeId == "PartDesign::Pad"]
    h.check("two Pads again", len(pads) == 2, [o.Name for o in pads])
    s["volume"] = h.solid_volume()


# -- Path 12: an extrude with the history marker rolled back -------------------------------------
def p12_roll():
    h.check("roll the marker to Extrude 1", timeline_menu("Extrude 1", "Roll History Marker Here"))


def p12_rolled():
    h.check("rolled back: no boss", near(h.solid_volume(), 14400.0, 1e-5), h.solid_volume())
    h.fit()


def p12_extrude():
    p = xpanel()
    h.check("square on the rolled-back part picked", p.target is not None, p.message.text())
    ui.type_into(p.distance.widget, "4")


def p12_ok():
    want = 14400.0 + 16.0 * 4.0
    h.check("the new block 4 x 4 x 4", near(h.solid_volume(), want, 1e-5), h.solid_volume())
    s["late"] = xpanel().target.Name
    h.task_button("OK")


def p12_to_end():
    h.check("new step kept", not dialog_open())
    marker = tl().marker()
    last = tl()._buttons[-1]
    end = last.mapToGlobal(last.rect().center()) + QtCore.QPoint(30, 0)
    w.drag(marker, QtCore.QPoint(4, 4), end)


def p12_at_end():
    want = s["volume"] + 16.0 * 4.0
    h.check("marker at the end: everything", near(h.solid_volume(), want, 1e-5), h.solid_volume())
    h.check("no step in error", not broken(), broken())
    names = [o.Name for o in h.body().Group]
    h.check(
        "the new extrude sits before the boss",
        s.get("late") in names and names.index(s["late"]) < names.index(s["boss"]),
        names,
    )
    h.shot("p12-inserted")
    s["volume"] = h.solid_volume()


# -- Path 13: Press Pull's other modes -------------------------------------------------------------
def p13_q():
    h.click_empty()
    h.fit()
    h.press("q")


def p13_edge():
    h.click_edge(V(30, 0, 12))  # the front top edge of the ring


def p13_edge_picked():
    p = ppanel()
    h.check("an edge: Press Pull rounds it", p.mode == "fillet", (p.mode, p.message.text()))
    h.click(V(36, 26, 12))  # then a face: this Press Pull rounds edges


def p13_face_refused():
    p = ppanel()
    h.check(
        "a face while rounding edges is explained", "edges" in p.message.text(), p.message.text()
    )
    h.check("still one edge", len(p.names) == 1, p.names)
    ui.type_into(p.field.widget, "1.5")


def p13_round_ok():
    h.task_button("OK")


def p13_round_done():
    want = s["volume"] - 40.0 * 1.5 * 1.5 * (1 - math.pi / 4)
    h.check(
        "round r1.5 on the 40 mm edge", near(h.solid_volume(), want, 1e-5), (h.solid_volume(), want)
    )
    s["volume"] = h.solid_volume()
    h.click_empty()
    h.press("q")


def p13_round_face():
    h.fit()
    # the round's face, half way round (45 degrees) at x = 30
    r = 1.5
    h.click(V(30, r - r * math.cos(math.radians(45)), 12 - r + r * math.sin(math.radians(45))))


def p13_radius_edit():
    p = ppanel()
    h.check("the round's face edits its radius", p.mode == "edit_blend", (p.mode, p.message.text()))
    ui.type_into(p.field.widget, "2*1.25")


def p13_radius_ok():
    want = s["volume"] - 40.0 * (2.5**2 - 1.5**2) * (1 - math.pi / 4)
    h.check(
        "typed 2*1.25: radius 2.5", near(h.solid_volume(), want, 1e-5), (h.solid_volume(), want)
    )
    h.task_button("OK")


def p13_done():
    fillets = [o for o in h.body().Group if o.TypeId == "PartDesign::Fillet"]
    h.check("still one round in the timeline", len(fillets) == 1, [o.Name for o in fillets])
    h.check("its radius is 2.5", fillets and near(fillets[0].Radius.Value, 2.5))
    h.check("nothing in error", not broken(), broken())


# -- Path 14: two sketches in one extrude ---------------------------------------------------------
def p14_new():
    App.newDocument("QATwoSketches")
    h.fit()


def p14_e():
    h.click_empty()
    h.fit()
    h.press("e")


def p14_pick_a():
    p = xpanel()
    h.check(
        "the newest sketch's only area is picked by itself (Fusion)",
        len(p.profiles) == 1 and p.profiles[0][0] is s["sketch_b"],
        p.profiles,
    )
    h.fit()
    h.click(V(5, 5, 10))


def p14_both():
    p = xpanel()
    h.check("the square of the other sketch added", len(p.profiles) == 2, p.profiles)
    h.check("Join", p.operation.currentText() == "Join", p.operation.currentText())
    ui.type_into(p.distance.widget, "5")


def p14_ok():
    h.check("two 6 x 6 x 5 blocks", near(h.solid_volume(), 12000.0 + 360.0), h.solid_volume())
    h.task_button("OK")


def p14_save():
    h.check("kept", not dialog_open() and near(h.solid_volume(), 12360.0))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-qa-"), "two_sketches.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def p14_open():
    App.openDocument(s["path"])
    h.fit()


def p14_edit():
    h.check("reopened", near(h.solid_volume(), 12360.0), h.solid_volume())
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"), ui.timeline_titles())


def p14_editing():
    p = xpanel()
    h.check("editing", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("both profiles back", len(p.profiles) == 2, p.profiles)
    h.fit()
    h.click(V(35, 21, 15))  # the second block's top, in front of its arrow: drop that square


def p14_dropped():
    p = xpanel()
    h.check("one profile left", len(p.profiles) == 1, p.profiles)
    h.check("one block", near(h.solid_volume(), 12180.0), (h.solid_volume(), p.message.text()))
    ui.type_into(p.distance.widget, "8")


def p14_ok2():
    h.check("one block 8 tall", near(h.solid_volume(), 12000.0 + 288.0), h.solid_volume())
    h.task_button("OK")


def p14_done():
    h.check("kept", not dialog_open() and near(h.solid_volume(), 12288.0), h.solid_volume())
    h.check("nothing in error", not broken(), broken())
    h.check("drawn", shown())
    h.shot("p14-end")


h.run(
    "extrude_presspull_qa3",
    [
        p11_new,
        *sketch_on(
            "block", V(12, -8, 0), lambda sk: (rect(0, 0, 40, 30, 0)(sk), circle(20, 15, 5, 0)(sk))
        ),
        p10_e,
        p10_ring,
        p11_both,
        p11_block_ok,
        *sketch_on("boss", V(30, 25, 10), circle(8, 8, 3, 10)),
        p11_boss_e,
        p11_boss_type,
        p11_boss_ok,
        p11_edit_first,
        p11_taller,
        p11_taller_ok,
        p11_followed,
        p11_boss_to_cut,
        p11_cut_ok,
        p11_undo,
        p11_undone,
        p12_roll,
        p12_rolled,
        *sketch_on("late", V(30, 25, 12), rect(32, 20, 36, 24, 12)),
        step(lambda: (h.fit(), h.press("e")), "p12_e"),
        p12_extrude,
        p12_ok,
        p12_to_end,
        p12_at_end,
        p13_q,
        p13_edge,
        p13_edge_picked,
        p13_face_refused,
        p13_round_ok,
        p13_round_done,
        p13_round_face,
        p13_radius_edit,
        p13_radius_ok,
        p13_done,
        p10_new,
        *sketch_on(
            "plate", V(12, -8, 0), lambda sk: (rect(0, 0, 40, 30, 0)(sk), circle(20, 15, 5, 0)(sk))
        ),
        p10_e,
        p10_ring,
        p10_ring_ok,
        p10_show_sketch,
        p10_e_again,
        p10_regions_offered,
        p10_disc,
        p10_done,
        p14_new,
        *sketch_on("base", V(12, -8, 0), rect(0, 0, 40, 30, 0)),
        step(lambda: (h.fit(), h.press("e")), "p14_base_e"),
        step(lambda: h.task_button("OK"), "p14_base_ok"),
        *sketch_on("a", V(20, 15, 10), rect(2, 2, 8, 8, 10)),
        *sketch_on("b", V(20, 15, 10), rect(30, 20, 36, 26, 10)),
        p14_e,
        p14_pick_a,
        p14_both,
        p14_ok,
        p14_save,
        p14_open,
        p14_edit,
        p14_editing,
        p14_dropped,
        p14_ok2,
        p14_done,
    ],
)
