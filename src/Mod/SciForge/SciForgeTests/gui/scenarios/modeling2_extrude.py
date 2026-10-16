# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude To Object's Extend choices and Offset (wave 4, modeling-2), only real input.

A block whose cross-section (on XZ) has a flat top (z 20, x 0..15), a slope down to z 10
at x 25 and a lower step, 30 long (Symmetric, y -15..15).

1. A 15 x 10 rectangle on the XY plane, E, Start Offset 30 (above the block), Extent To
   Object, click the block's top face: Extend appears with To Selected Face (the face's
   plane, extended: the column ends at z 20 everywhere, also over the slope) and To Adjacent
   Faces (the column ends on the top face and on the slope next to it). OK.
2. Edit from the timeline: Extend comes back; switch to To Selected Face, OK.
3. Ctrl+Z / Ctrl+Y.
4. A pocket from the top face, Esc first (nothing changes), E again: To Object the XY
   plane (picked in the browser): a plane has no Extend choice; Offset -5 stops it 5 mm
   short of the plane. OK.
5. Save, close, reopen: both extrudes read back their Extend and Offset.

Hand-derived: block = 600 mm^2 x 30 = 18000; column over x 5..20, y -5..5 from z 30: to the
top face's plane 15 x 10 x 10 = 1500; To Adjacent Faces 10 (100 + int_15^20 (10 + x - 15)
dx) = 1625; pocket 3 x 6, from z 20 to z 5: 270.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BLOCK = 18000.0
SECTION = [(0, 0), (40, 0), (40, 10), (25, 10), (15, 20), (0, 20)]


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def total():
    return sum(
        b.Shape.Volume for b in doc().findObjects("PartDesign::Body") if not b.Shape.isNull()
    )


# -- the block ------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("M2Extrude")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    pl.click_square("XZ_Plane")  # where the square shows (was 12, 0, 8)


def draw_section():
    import Part
    import Sketcher

    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and "XZ" in (sk.AttachmentSupport[0][0].Name))
    if sk is None:
        return
    pts = [V(*h.to_sketch(sk, V(x, 0, z)), 0) for x, z in SECTION]
    n = len(pts)
    for i in range(n):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % n]))
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % n, 1))
    doc().recompute()


def finish_section():
    h.ribbon("Finish Sketch")


def extrude_block():
    h.fit()
    h.press("e")


def block_symmetric():
    p = panel()
    h.check("the section picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check("Direction Symmetric", ui.choose(p.direction, "Symmetric"))
    ui.type_into(p.distance.widget, "15")


def block_ok():
    h.task_button("OK")


def block_made():
    h.check("the block: 600 x 30", near(total(), BLOCK), total())
    h.fit()


# -- 1. To Object, To Adjacent Faces ---------------------------------------------------------
def sketch_profile():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was -15, -20, 0)


def draw_profile():
    sk = h.in_sketch()
    h.check("1 sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 5, -5, 20, 5)


def finish_profile():
    h.ribbon("Finish Sketch")


def extrude_column():
    h.click_empty()
    h.fit()
    h.press("e")


def column_options():
    p = panel()
    h.check("1 the rectangle picked by itself", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    h.check("1 Start: Offset", ui.choose(p.start, "Offset"))
    ui.type_into(p.start_offset.widget, "30")
    h.check("1 Extent: To Object", ui.choose(p.extent, "To Object"))
    h.check("1 the Object box takes the click", p.active == "extent_object", p.active)
    h.check("1 no Extend choice before an object", not p.extend.isVisible())
    h.check("1 the Offset field shows", p.object_offset.widget.isVisible())


def click_top_face():
    h.fit()
    h.click(V(4, 10, 20))


def selected_face():
    p = panel()
    if p is None:
        return
    h.check("1 the top face picked", p.options.get("extent_object") is not None, p.message.text())
    items = [p.extend.itemText(i) for i in range(p.extend.count())]
    h.check(
        "1 Extend: To Selected Face / To Adjacent Faces",
        p.extend.isVisible() and items == ["To Selected Face", "To Adjacent Faces"],
        items,
    )
    h.check("1 Join", ui.choose(p.operation, "Join"))


def selected_built():
    p = panel()
    h.check(
        "1 To Selected Face: ends at z 20 everywhere (+1500)",
        near(total(), BLOCK + 1500),
        total(),
    )
    if p:
        h.check("1 choose To Adjacent Faces", ui.choose(p.extend, "To Adjacent Faces"))


def adjacent_built():
    h.check(
        "1 To Adjacent Faces: ends on the top face and the slope (+1625)",
        near(total(), BLOCK + 1625),
        total(),
    )
    h.shot("1-adjacent")


def column_ok():
    h.check("1 the preview", near(total(), BLOCK + 1625), total())
    h.task_button("OK")


def column_done():
    h.check("1 OK closed the dialog", panel() is None)
    h.check("1 kept: +1625", near(total(), BLOCK + 1625), total())
    s["title"] = ui.timeline_titles()[-1] if ui.timeline_titles() else ""


# -- 2. Edit from the timeline -------------------------------------------------------------------
def edit_column():
    h.fit()
    h.check("2 double-click the column", ui.double_click_timeline(s["title"] or "?"))


def edit_open():
    p = panel()
    h.check("2 editing the column", p is not None and p.editing)
    if p is None:
        return
    h.check("2 To Object comes back", p.extent.currentText() == "To Object")
    h.check(
        "2 with To Adjacent Faces",
        p.extend.currentText() == "To Adjacent Faces",
        p.extend.currentText(),
    )
    h.check("2 choose To Selected Face", ui.choose(p.extend, "To Selected Face"))


def edit_ok():
    h.check("2 the preview: +1500", near(total(), BLOCK + 1500), total())
    h.task_button("OK")


def edited():
    h.check("2 the edit stays", near(total(), BLOCK + 1500), total())


# -- 3. Undo / redo --------------------------------------------------------------------------
def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("3 Ctrl+Z: To Adjacent Faces again", near(total(), BLOCK + 1625), total())


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("3 Ctrl+Y: To Selected Face", near(total(), BLOCK + 1500), total())
    undo()


def undone_again():
    h.check("3 Ctrl+Z again", near(total(), BLOCK + 1625), total())


# -- 4. A pocket To Object a plane with an Offset ----------------------------------------------
def pocket_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def pocket_face():
    h.fit()
    h.click(V(4, 10, 20))


def pocket_draw():
    sk = h.in_sketch()
    h.check("4 sketch on the top face", sk is not None)
    if sk:
        a = h.to_sketch(sk, V(1, -3, 20))  # beside the column (x 5..20)
        b = h.to_sketch(sk, V(4, 3, 20))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def pocket_finish():
    h.ribbon("Finish Sketch")


def pocket_e():
    h.click_empty()
    h.fit()
    h.press("e")


def pocket_esc():
    p = panel()
    h.check("4 the square picked by itself", p is not None and len(p.profiles) == 1)
    if p is not None:
        ui.type_into(p.distance.widget, "4")
    h.press(QtCore.Qt.Key_Escape)


def pocket_after_esc():
    h.check("4 Esc closed the dialog", panel() is None)
    h.check("4 Esc: nothing changed", near(total(), BLOCK + 1625), total())


def pocket_e_again():
    h.click_empty()
    h.fit()
    h.press("e")


def pocket_pick_again():
    p = panel()
    if p is not None and not p.profiles:
        h.click(V(2.5, 0, 20))  # click inside the square's area


def pocket_to():
    p = panel()
    h.check("4 the square is the profile", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    # the dialog starts with the last extrude's settings (Start Offset 30): from the sketch
    h.check("4 Start: Profile Plane", ui.choose(p.start, "Profile Plane"))
    h.check("4 Cut", ui.choose(p.operation, "Cut"))
    h.check("4 Extent: To Object", ui.choose(p.extent, "To Object"))


def expand_origin():
    t = hs.browser()
    item = t.row("Origin")
    if h.check("4 browser has Origin", item is not None, t.labels()):
        w.click(t.viewport(), t.label_point(item))
        w.key(t, QtCore.Qt.Key_Right)


def click_xy():
    t = hs.browser()
    item = t.row("XY")
    if h.check("4 browser has the XY plane", item is not None, t.labels()):
        w.click(t.viewport(), t.label_point(item))


def plane_picked():
    p = panel()
    if p is None:
        return
    ref = p.options.get("extent_object")
    h.check("4 To the XY plane", ref is not None and ref[0].Name.startswith("XY"), ref)
    h.check("4 a plane has no Extend choice", not p.extend.isVisible())
    t = p.target
    detail = (
        total(),
        {
            k: p.options.get(k)
            for k in ("start", "start_offset", "direction", "extent", "operation")
        },
        t and t.TypeId,
        t and [(f.Surface.TypeId, f.Area, f.CenterOfMass) for f in t.Shape.Faces if f.Area < 60],
    )
    h.check("4 through to the plane: 3 x 6 x 20", near(total(), BLOCK + 1625 - 360), detail)
    ui.type_into(p.object_offset.widget, "-5")


def offset_built():
    h.check("4 Offset -5: stops 5 short (3 x 6 x 15)", near(total(), BLOCK + 1625 - 270), total())
    h.task_button("OK")


def pocket_done():
    h.check("4 OK", panel() is None)
    h.check("4 kept", near(total(), BLOCK + 1625 - 270), total())
    s["v"] = total()


# -- 5. Save, close, reopen -----------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-m2-extrude-"), "m2_extrude.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("5 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import extrude

    h.check("5 same volume after reopening", near(total(), s["v"]), total())
    found = [o for o in doc().Objects if extrude.is_extrude(o) and o.Name != "Pad"]
    options = [extrude.read(o)[1] for o in sorted(found, key=lambda o: o.ID)]
    extends = [o.get("extend") for o in options]
    offsets = [o.get("object_offset") for o in options]
    h.check("5 the column keeps To Adjacent Faces", "adjacent" in extends, extends)
    h.check("5 the pocket keeps its Offset", any(near(x, -5.0) for x in offsets), offsets)
    h.check(
        "5 every body valid", all(b.Shape.isValid() for b in doc().findObjects("PartDesign::Body"))
    )
    hs.no_popups("To Object options")


column_options.wait_ms = 600
selected_built.wait_ms = 800
adjacent_built.wait_ms = 800
plane_picked.wait_ms = 800
offset_built.wait_ms = 800

h.run(
    "modeling2_extrude",
    [
        new_design,
        pick_xz,
        draw_section,
        finish_section,
        extrude_block,
        block_symmetric,
        block_ok,
        block_made,
        sketch_profile,
        pick_xy,
        draw_profile,
        finish_profile,
        extrude_column,
        column_options,
        click_top_face,
        selected_face,
        selected_built,
        adjacent_built,
        column_ok,
        column_done,
        edit_column,
        edit_open,
        edit_ok,
        edited,
        undo,
        undone,
        redo,
        redone,
        undone_again,
        pocket_sketch,
        pocket_face,
        pocket_draw,
        pocket_finish,
        pocket_e,
        pocket_esc,
        pocket_after_esc,
        pocket_e_again,
        pocket_pick_again,
        pocket_to,
        expand_origin,
        click_xy,
        plane_picked,
        offset_built,
        pocket_done,
        save,
        reopen,
        reopened,
    ],
)
