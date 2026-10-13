# SPDX-License-Identifier: LGPL-2.1-or-later
"""Align (MODIFY > Align) like Fusion, only real input.

Bodies made with Create Sketch + Extrude: a table 0..60 x 0..40 x 10 (Body) and a block
80..100 x 0..10 x 5 (New Body, 1000).

  A  The A key opens Appearance, not Align (Fusion gives Align no key); Esc. MODIFY > Align:
     the From box waits; Objects is Bodies.
  B  From: the block's top face; To: the table's top face: the two faces end up facing each
     other, the block lies upside down on the table, centred on its top (z 10..15),
     previewed.
  C  Flip: the block turns over into the table (z 5..10); Flip again: back on top; Angle:
     turned 90 degrees about the table's normal (10 x 20 seen from above); OK: an "Align 1"
     step, same volume. Undo: the block is back where it was; Redo.
  D  Double-click Align 1: the To box waits; clear it, click the table's +X side: the block
     now sits against that side (x 60..65); OK.
  E  Components: Create Components from Bodies on the block, then Align with Objects:
     Components: the block's +X face onto the table's top: the component moves (z 10..15),
     the body itself gets no new step; "Align 2" in the timeline. Undo / Redo.
  F  Delete Align 2 in the timeline: the component goes back where it was.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as wi

V = App.Vector
state = {}


def table():
    return d.bodies()[0]


def block():
    return d.bodies()[1]


def box():
    """The block's bounding box in the design (inside a component: where it shows)."""
    from sciforge import bodies

    return bodies.global_shape(block().Tip).BoundBox


def at(bb, xmin=None, xmax=None, ymin=None, ymax=None, zmin=None, zmax=None):
    want = (xmin, xmax, ymin, ymax, zmin, zmax)
    got = (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)
    return all(w is None or abs(w - g) < 1e-6 for w, g in zip(want, got))


def aligns():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "Align"]


# -- A ------------------------------------------------------------------------------------------
def a_key():
    h.click_empty()
    h.fit()
    h.press("a")


def a_appearance():
    p = d.panel()
    h.check("A opens Appearance", p is not None and p.title == "Appearance", p and p.title)
    h.press(QtCore.Qt.Key_Escape)


def a_start():
    h.check("Esc closed it", d.panel() is None)
    d.ribbon_menu("MODIFY", "Align")


def a_waits():
    p = d.panel()
    if not h.check("Align dialog", p is not None and p.title == "Align", p):
        return
    h.check("the From box waits", p.active == "from", p.active)
    h.check("Objects: Bodies", p.objects.currentData() == "bodies", p.objects.currentText())
    h.check("no pop-up", not h.popups(), h.popups())


# -- B ------------------------------------------------------------------------------------------
def b_click_block_top():
    h.click(V(95, 3, 5))


def b_click_table_top():
    p = d.panel()
    h.check(
        "From taken, the To box waits",
        p is not None and p.options["from_pick"] and p.active == "to",
        p and p.options,
    )
    h.click(V(10, 30, 10))


def b_preview():
    bb = box()
    h.check("upside down on the table, centred", at(bb, 20, 40, 15, 25, 10, 15), bb)
    h.check("same volume", d.near(d.volume(block()), 1000), d.volume(block()))
    h.shot("B-preview")


# -- C ------------------------------------------------------------------------------------------
def c_flip():
    wi.click(d.panel().flip_button)


def c_flipped():
    bb = box()
    h.check("Flip: into the table (z 5..10)", at(bb, 20, 40, 15, 25, 5, 10), bb)
    wi.click(d.panel().flip_button)


def c_unflipped():
    bb = box()
    h.check("Flip again: back on top", at(bb, 20, 40, 15, 25, 10, 15), bb)
    wi.click(d.panel().angle_button)


def c_turned():
    bb = box()
    h.check("Angle: turned 90 degrees (10 x 20)", at(bb, 25, 35, 10, 30, 10, 15), bb)
    p = d.panel()
    h.check("the dialog says it is turned", "90" in p.state.text(), p.state.text())


def c_ok():
    h.task_button("OK")


def c_done():
    h.check("dialog closed", d.panel() is None)
    h.check("Align 1 in the timeline", "Align 1" in t.titles(), t.titles())
    h.check("still turned on the table", at(box(), 25, 35, 10, 30, 10, 15), box())
    h.check("same volume", d.near(d.volume(block()), 1000), d.volume(block()))


def c_undo():
    t.undo()


def c_undone():
    h.check("undo: back where it was", at(box(), 80, 100, 0, 10, 0, 5), box())
    h.check("undo: no Align step", not aligns(), aligns())


def c_redo():
    t.redo()


def c_redone():
    h.check("redo: on the table again", at(box(), 25, 35, 10, 30, 10, 15), box())


# -- D ------------------------------------------------------------------------------------------
def d_edit():
    h.fit()
    h.check("double-click Align 1", ui.double_click_timeline("Align 1"), t.titles())


def d_clear():
    p = d.panel()
    if not h.check("the edit dialog", p is not None and p.editing, p):
        return
    h.check("the To box waits", p.active == "to", p.active)
    wi.click(p.fields["to"].clear)


def d_click_side():
    h.click(V(60, 34, 4))


def d_preview():
    bb = box()
    h.check(
        "against the +X side (x 60..65), centred on it",
        at(bb, 60, 65)
        and abs((bb.YMin + bb.YMax) / 2 - 20) < 1e-6
        and abs((bb.ZMin + bb.ZMax) / 2 - 5) < 1e-6,
        bb,
    )


def d_ok():
    h.task_button("OK")


def d_done():
    h.check("dialog closed", d.panel() is None)
    h.check("still one Align step", len(aligns()) == 1, aligns())
    h.check("against the side", at(box(), 60, 65), box())
    state["steps"] = [o.Name for o in block().Group]


# -- E ------------------------------------------------------------------------------------------
def e_component():
    h.click_empty()
    state["label"] = block().Label
    t.row_menu(state["label"], "Create Components from Bodies")


def e_made():
    from sciforge import components

    part = components.component_of(block())
    h.check("the block is in a component", part is not None)
    state["part"] = part.Name if part is not None else None
    state["place"] = App.Placement(part.Placement) if part is not None else None


def e_align():
    h.click_empty()
    h.fit()
    d.ribbon_menu("MODIFY", "Align")


def e_components():
    d.choose("objects", "Components")


def e_click_block():
    p = d.panel()
    h.check(
        "Objects: Components",
        p is not None and p.objects.currentData() == "components",
        p and p.objects.currentText(),
    )
    h.click(V(65, 21, 6))


def e_click_table():
    p = d.panel()
    part = d.doc().getObject(state["part"]) if state.get("part") else None
    h.check("the component moves", p is not None and p.moving is part, p and p.moving)
    h.click(V(10, 30, 10))


def e_preview():
    bb = box()
    h.check("the block's +X face on the table (z 10..15)", at(bb, zmin=10, zmax=15), bb)


def e_ok():
    h.task_button("OK")


def e_done():
    bb = box()
    h.check("on the table", at(bb, zmin=10, zmax=15), bb)
    part = d.doc().getObject(state["part"])
    h.check("the component moved", not part.Placement.isSame(state["place"], 1e-9), part.Placement)
    h.check(
        "no new step in the body",
        [o.Name for o in block().Group] == state["steps"],
        [o.Name for o in block().Group],
    )
    h.check("Align 2 in the timeline", "Align 2" in t.titles(), t.titles())


def e_undo():
    t.undo()


def e_undone():
    h.check("undo: the component is back", at(box(), 60, 65), box())


def e_redo():
    t.redo()


def e_redone():
    h.check("redo: on the table again", at(box(), zmin=10, zmax=15), box())


# -- F ------------------------------------------------------------------------------------------
def f_delete():
    h.click_empty()
    t.menu("Align 2", "Delete")


def f_deleted():
    h.check("Align 2 gone", "Align 2" not in t.titles(), t.titles())
    h.check("the component went back", at(box(), 60, 65), box())
    h.check("Align 1 kept", "Align 1" in t.titles(), t.titles())


h.run(
    "modify_align",
    t.watched(
        [s.new_design("Align")]
        + s.box_steps("table", (0, 0, 60, 40), 10, V(12, -8, 0))
        + s.box_steps("block", (80, 0, 100, 10), 5, V(12, -8, 0), new_body=True)
        + [
            a_key,
            a_appearance,
            a_start,
            a_waits,
            b_click_block_top,
            b_click_table_top,
            b_preview,
            c_flip,
            c_flipped,
            c_unflipped,
            c_turned,
            c_ok,
            c_done,
            c_undo,
            c_undone,
            c_redo,
            c_redone,
            d_edit,
            d_clear,
            d_click_side,
            d_preview,
            d_ok,
            d_done,
            e_component,
            e_made,
            e_align,
            e_components,
            e_click_block,
            e_click_table,
            e_preview,
            e_ok,
            e_done,
            e_undo,
            e_undone,
            e_redo,
            e_redone,
            f_delete,
            f_deleted,
        ]
    ),
)
