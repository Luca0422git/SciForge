# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude To Object a whole body picked in the BROWSER (QA, only real input).

Path 29, a slab floating 20 mm above the block is made as a New Body (Start: Offset).
         The block is made active again (browser: Activate Body); a column sketched on it
         extrudes To Object: the slab body, picked by
         clicking its row in the browser (Fusion lets you pick a body there). The column
         stops at the slab's underside. Edit it from the timeline: the body is still the
         object; OK without a change; Undo, Redo (an unchanged dialog used to leave its
         undo step pending, and the next change threw the Redo away). The same after an
         Extrude cancelled with nothing picked.

Numbers by hand: block 40 x 30 x 10, slab 40 x 30 x 5 at z 30..35, column 10 x 10.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def xpanel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def bodies():
    return doc().findObjects("PartDesign::Body")


def vol(body):
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def browser():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()
    return t


def click_row(label):
    t = browser()
    item = t.row(label)
    h.check("browser row %r" % label, item is not None, t.labels())
    if item is not None:
        w.click(t.viewport(), t.label_point(item))


def step(fn, name):
    fn.__name__ = name
    return fn


def sketch_rect(tag, point, x0, y0, x1, y1):
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
            ax, ay = h.to_sketch(sk, V(x0, y0, point.z))
            bx, by = h.to_sketch(sk, V(x1, y1, point.z))
            h.draw_rectangle(sk, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    def finish():
        h.ribbon("Finish Sketch")

    return [
        step(create, "%s_create" % tag),
        step(pick, "%s_pick" % tag),
        step(draw, "%s_draw" % tag),
        step(finish, "%s_finish" % tag),
    ]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("QABodyTarget")
    h.fit()


def e():
    h.fit()
    h.press("e")


def block_ok():
    p = xpanel()
    h.check("block profile picked by itself", p.target is not None, p.message.text())
    h.task_button("OK")


def block_done():
    s["block"] = h.body()
    h.check("block 12000", near(vol(s["block"]), 12000.0), vol(s["block"]))


def slab_options():
    p = xpanel()
    h.check("slab profile picked by itself", p.target is not None, p.message.text())
    h.check("choose New Body", ui.choose(p.operation, "New Body"))
    h.check("choose Start: Offset", ui.choose(p.start, "Offset"))


def slab_offset():
    p = xpanel()
    ui.type_into(p.start_offset.widget, "20")


def slab_distance():
    p = xpanel()
    ui.type_into(p.distance.widget, "5")


def slab_ok():
    h.check("two bodies", len(bodies()) == 2, [b.Label for b in bodies()])
    h.task_button("OK")


def slab_done():
    from sciforge import commands

    s["slab"] = commands.active_body()
    h.check("the slab is its own body", s["slab"] is not s["block"])
    h.check("slab 40 x 30 x 5", near(vol(s["slab"]), 6000.0), vol(s["slab"]))
    bb = s["slab"].Shape.BoundBox
    h.check("floating at z 30..35", near(bb.ZMin, 30.0) and near(bb.ZMax, 35.0), (bb.ZMin, bb.ZMax))


def activate_block():
    # The new body became the active one; work on the block again (browser: Activate Body).
    t = browser()
    item = t.row(s["block"].Label)
    h.check("browser row of the block", item is not None, t.labels())
    if item is not None:
        h.check(
            "Activate Body on the block",
            w.right_click(t.viewport(), t.label_point(item), "Activate Body"),
        )


def block_active():
    from sciforge import commands

    h.check("the block is the active body", commands.active_body() is s["block"])


def column_to_object():
    p = xpanel()
    h.check("column profile picked by itself", p.target is not None, p.message.text())
    h.check("choose Extent: To Object", ui.choose(p.extent, "To Object"))


def pick_slab_in_browser():
    p = xpanel()
    h.check("the Object box waits", p.active == "extent_object", p.active)
    click_row(s["slab"].Label)


def column_reaches():
    p = xpanel()
    h.check(
        "the slab body is the object", p.options.get("extent_object") is not None, p.message.text()
    )
    h.check(
        "the column joins the block and stops under the slab: +10 x 10 x 20",
        near(vol(s["block"]), 14000.0),
        (vol(s["block"]), p.message.text()),
    )
    h.check("the slab is untouched", near(vol(s["slab"]), 6000.0), vol(s["slab"]))
    h.shot("p29-to-body")
    h.task_button("OK")


def edit_column():
    h.check("kept", not dialog_open() and near(vol(s["block"]), 14000.0))
    titles = ui.timeline_titles()
    s["column"] = [t for t in titles if t.startswith("Extrude")][-1]
    h.check("double-click %s" % s["column"], ui.double_click_timeline(s["column"]), titles)


def editing_column():
    p = xpanel()
    h.check("editing the column", p is not None and p.editing and not p._closed)
    if p is None or not p.editing:
        return
    h.check("To Object back", p.extent.currentText() == "To Object", p.extent.currentText())
    h.check(
        "the slab body is its object",
        s["slab"].Label in p.fields["extent_object"].button.text(),
        p.fields["extent_object"].button.text(),
    )
    h.task_button("OK")


def undo():
    h.check("closed", not dialog_open())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("Undo: no column", near(vol(s["block"]), 12000.0), vol(s["block"]))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("Redo: the column again", near(vol(s["block"]), 14000.0), vol(s["block"]))
    h.check("nothing in error", not broken(), broken())
    h.shot("p29-end")


def esc_nothing():
    h.click_empty()
    h.press("e")


def esc_now():
    p = xpanel()
    h.check("Extrude waits (nothing picked)", p is not None and p.target is None)
    h.press(QtCore.Qt.Key_Escape)


def undo_after_esc():
    h.check("closed", not dialog_open())
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def redo_after_esc():
    h.check("Undo after a cancelled dialog: no column", near(vol(s["block"]), 12000.0))
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone_after_esc():
    h.check(
        "Redo still works (the cancelled dialog left no step behind)",
        near(vol(s["block"]), 14000.0),
        (vol(s["block"]), App.ActiveDocument.UndoNames[:3]),
    )


h.run(
    "extrude_presspull_qa7",
    [
        new_design,
        *sketch_rect("base", V(12, -8, 0), 0, 0, 40, 30),
        step(e, "block_e"),
        block_ok,
        block_done,
        *sketch_rect("slab", V(30, 25, 10), 0, 0, 40, 30),
        step(e, "slab_e"),
        slab_options,
        slab_offset,
        slab_distance,
        slab_ok,
        slab_done,
        activate_block,
        block_active,
        *sketch_rect("column", V(30, 25, 10), 5, 5, 15, 15),
        step(e, "column_e"),
        column_to_object,
        pick_slab_in_browser,
        column_reaches,
        edit_column,
        editing_column,
        undo,
        undone,
        redone,
        esc_nothing,
        esc_now,
        undo_after_esc,
        redo_after_esc,
        redone_after_esc,
    ],
)
