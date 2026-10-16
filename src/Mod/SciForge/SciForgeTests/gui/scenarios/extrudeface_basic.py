# SPDX-License-Identifier: LGPL-2.1-or-later
"""Luca: "when extruding, clicking on a face should bring that extrusion to the same height as
that face" (Fusion: once a profile is picked, a click on a face out of its plane sets the
distance to reach it; parity/extrude-presspull.md). Only real input.

A plate 50 x 30 x 10 (x 10..60) with a tower 10 x 30 up to z 40 on its left and a block
10 x 30 up to z 22 on its right. A 10 x 10 square sketched on the plate's top (x 30..40,
y 10..20, z 10).

P1  E: the square is picked by itself, the dialog says a face can be clicked. Click the
    tower's top: Distance 30 exactly (Extent stays Distance), the dialog says "Up to the
    face: 30 mm", the arrow sits at 30, the boss reaches z 40 (Join). OK: the step's
    length is 30 and the part is 40 tall.
P2  Undo takes the boss away, Redo brings it back.
P3  Edit from the timeline, click the block's top: Distance 12, the boss ends at z 22. OK.
P4  Edit again, click the tower's top (30 shown), Esc: the step keeps 12.
P5  Save, close, reopen: the boss is 12 tall; the edit shows Distance 12 (a plain number,
    Extent Distance). Cancel.
P6  Edit, Extent To Object, click the tower's top (the Object box takes it): to z 40. A
    click on the block's top then makes it the object (To Object stays, parametric): to
    z 22. Cancel: still 12.

Hand-derived: plate 15000, tower 12000, block 6600 = 33600; boss 100 mm^2 x 30 = 3000,
x 12 = 1200.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import extrudeface_steps as x
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
PARTS = 15000.0 + 12000.0 + 6600.0
TOWER_TOP = V(5, 15, 40)
BLOCK_TOP = V(65, 15, 22)


def p1_opened():
    p = x.panel()
    if not h.check("P1 E opens Extrude", p is not None):
        return
    h.check("P1 the square is picked by itself", len(p.profiles) == 1, p.profiles)
    h.check("P1 it starts at 0", x.near(p.distance.value(), 0.0), p.distance.value())
    h.check(
        "P1 the dialog says a face can be clicked", "click a face" in p.info.text(), p.info.text()
    )
    h.fit()
    s["clicked"] = h.click(TOWER_TOP)


def p1_reached():
    p = x.panel()
    if p is None:
        h.check("P1 the dialog stays open", False)
        return
    h.check(
        "P1 the tower's top was clicked",
        s.get("clicked") and "Face" in s["clicked"][1],
        h.state.get("last_click"),
    )
    h.check("P1 Distance 30 exactly", p.distance.value() == 30.0, p.distance.value())
    h.check(
        "P1 Extent stays Distance", p.extent.currentData() == "distance", p.extent.currentText()
    )
    h.check(
        "P1 the dialog says what happened", p.info.text() == "Up to the face: 30 mm", p.info.text()
    )
    h.check("P1 no warning", p.message.text() == "", p.message.text())
    h.check(
        "P1 the arrow sits at 30",
        p.dragger is not None and x.near(p.dragger.distance(), 30),
        p.dragger and p.dragger.distance(),
    )
    h.check("P1 Join", p.operation.currentData() == "join", p.operation.currentText())
    h.check(
        "P1 still one profile (the tower's top is no profile)", len(p.profiles) == 1, p.profiles
    )
    h.check("P1 the preview reaches the tower's top", x.near(x.total(), PARTS + 3000.0), x.total())
    h.shot("P1-up-to-the-tower")
    h.task_button("OK")


def p1_done():
    h.check("P1 the dialog closed", x.panel() is None and not Gui.Control.activeDialog())
    feature = x.last_extrude()
    s["feature"] = feature.Name if feature is not None else None
    h.check("P1 the step's length is 30", x.length(feature) == 30.0, x.length(feature))
    h.check(
        "P1 a plain length (Distance)",
        getattr(feature, "Type", None) == "Length",
        getattr(feature, "Type", None),
    )
    h.check("P1 the part", x.near(x.total(), PARTS + 3000.0), x.total())
    zmax = max(b.Shape.BoundBox.ZMax for b in x.bodies())
    h.check("P1 the boss ends at the tower's height (z 40)", x.near(zmax, 40.0), zmax)
    tops = [
        f
        for b in x.bodies()
        for f in b.Shape.Faces
        if abs(f.BoundBox.ZMin - 40.0) < 1e-6 and abs(f.BoundBox.ZMax - 40.0) < 1e-6
    ]
    covers = [f for f in tops if f.BoundBox.XMin <= 30.0 + 1e-6 and f.BoundBox.XMax >= 40 - 1e-6]
    h.check("P1 the boss's top is at z 40", bool(covers), [f.BoundBox for f in tops])


# -- P2 ------------------------------------------------------------------------------------
def p2_undo():
    h.check("Undo button", ui.quick_access("Undo"))


def p2_undone():
    h.check("P2 Undo takes the boss away", x.near(x.total(), PARTS), x.total())


def p2_redo():
    h.check("Redo button", ui.quick_access("Redo"))


def p2_redone():
    h.check("P2 Redo brings it back", x.near(x.total(), PARTS + 3000.0), x.total())
    h.fit()


# -- P3: edit from the timeline --------------------------------------------------------------
def p3_edit():
    title = x.timeline_extrude_title()
    s["title"] = title
    h.check(
        "P3 double-click %s" % title,
        title and ui.double_click_timeline(title),
        ui.timeline_titles(),
    )


def p3_click_block():
    p = x.panel()
    if not h.check("P3 editing", p is not None and p.editing):
        return
    h.check("P3 the edit shows 30", p.distance.value() == 30.0, p.distance.value())
    h.fit()
    h.click(BLOCK_TOP)


def p3_reached():
    p = x.panel()
    if p is None:
        h.check("P3 still editing", False)
        return
    h.check("P3 Distance 12 exactly", p.distance.value() == 12.0, p.distance.value())
    h.check("P3 says so", p.info.text() == "Up to the face: 12 mm", p.info.text())
    h.check("P3 the boss ends at z 22", x.near(x.total(), PARTS + 1200.0), x.total())
    h.task_button("OK")


def p3_done():
    feature = App.ActiveDocument.getObject(s["feature"]) if s.get("feature") else None
    h.check("P3 the same step, now 12 long", x.length(feature) == 12.0, x.length(feature))
    h.check("P3 kept", x.near(x.total(), PARTS + 1200.0), x.total())
    h.check(
        "P3 one extrude more than the parts", len(x.extrudes()) == 4, [o.Name for o in x.extrudes()]
    )


# -- P4: Esc --------------------------------------------------------------------------------
def p4_edit():
    h.check("P4 double-click", ui.double_click_timeline(s.get("title") or ""), ui.timeline_titles())


def p4_click_tower():
    p = x.panel()
    if not h.check("P4 editing", p is not None and p.editing):
        return
    h.fit()
    h.click(TOWER_TOP)


def p4_escape():
    p = x.panel()
    h.check("P4 30 shown", p is not None and p.distance.value() == 30.0, p and p.distance.value())
    h.check("P4 the preview reaches the tower", x.near(x.total(), PARTS + 3000.0), x.total())
    x.escape()


def p4_kept():
    h.check("P4 Esc closed the dialog", x.panel() is None and not Gui.Control.activeDialog())
    feature = App.ActiveDocument.getObject(s["feature"]) if s.get("feature") else None
    h.check("P4 the step keeps 12", x.length(feature) == 12.0, x.length(feature))
    h.check("P4 the part as before", x.near(x.total(), PARTS + 1200.0), x.total())


# -- P5: save, reopen ------------------------------------------------------------------------
def p5_reopened():
    h.check("P5 reopened", x.near(x.total(), PARTS + 1200.0), x.total())
    feature = App.ActiveDocument.getObject(s["feature"]) if s.get("feature") else None
    h.check("P5 the step's length is 12", x.length(feature) == 12.0, x.length(feature))
    h.check("P5 double-click", ui.double_click_timeline(s.get("title") or ""), ui.timeline_titles())


def p5_editing():
    p = x.panel()
    if not h.check("P5 editing", p is not None and p.editing):
        return
    h.check("P5 Distance 12", p.distance.value() == 12.0, p.distance.value())
    h.check("P5 Extent Distance", p.extent.currentData() == "distance", p.extent.currentText())
    h.check("P5 no formula", not p.options.get("expressions"), p.options.get("expressions"))
    h.task_button("Cancel")


def p5_done():
    h.check("P5 Cancel closed it", x.panel() is None and not Gui.Control.activeDialog())
    h.check("P5 nothing changed", x.near(x.total(), PARTS + 1200.0), x.total())
    h.check("P5 no snap mark left", not x.snap_marks(), len(x.snap_marks()))
    h.shot("P5-end")


# -- P6: a side that is To Object already ------------------------------------------------------
def p6_edit():
    h.check("P6 double-click", ui.double_click_timeline(s.get("title") or ""), ui.timeline_titles())


def p6_to_object():
    p = x.panel()
    if not h.check("P6 editing", p is not None and p.editing):
        return
    h.check("P6 To Object", ui.choose(p.extent, "To Object"))


def p6_click_tower():
    p = x.panel()
    h.check(
        "P6 the Object box takes the click",
        p is not None and p.active == "extent_object",
        p and p.active,
    )
    h.fit()
    h.click(TOWER_TOP)


def p6_tower():
    p = x.panel()
    if p is None:
        return
    ref = p.options.get("extent_object")
    h.check("P6 the tower's top is the object", ref is not None and ref[1].startswith("Face"), ref)
    h.check("P6 up to z 40", x.near(x.total(), PARTS + 3000.0), x.total())
    h.check("P6 the Profiles box takes clicks again", p.active == "profiles", p.active)
    h.fit()
    h.click(BLOCK_TOP)


def p6_block():
    p = x.panel()
    if p is None:
        return
    h.check("P6 To Object stays", p.extent.currentData() == "to_object", p.extent.currentText())
    ref = p.options.get("extent_object")
    face = ref[0].Shape.getElement(ref[1]) if ref is not None else None
    h.check(
        "P6 the block's top is the object now",
        face is not None and abs(face.BoundBox.ZMax - 22.0) < 1e-6,
        face and face.BoundBox,
    )
    h.check("P6 says so", p.info.text() == "Ends on the face (To Object)", p.info.text())
    h.check("P6 up to z 22", x.near(x.total(), PARTS + 1200.0), x.total())
    h.check("P6 the profile is kept", len(p.profiles) == 1, p.profiles)
    h.task_button("Cancel")


def p6_done():
    h.check("P6 Cancel", x.panel() is None and not Gui.Control.activeDialog())
    feature = App.ActiveDocument.getObject(s["feature"]) if s.get("feature") else None
    h.check(
        "P6 still a plain 12",
        x.length(feature) == 12.0 and getattr(feature, "Type", None) == "Length",
        (x.length(feature), getattr(feature, "Type", None)),
    )


h.run(
    "extrudeface_basic",
    [
        x.new_design("ExtrudeFace"),
        *x.xy_block("plate", (10, 0, 60, 30), 10, 15000.0),
        *x.xy_block("tower", (0, 0, 10, 30), 40, 27000.0),
        *x.xy_block("block", (60, 0, 70, 30), 22, PARTS),
        *x.face_sketch("square", V(45, 25, 10), (30, 10, 40, 20)),
        x.press_e("p1_e"),
        p1_opened,
        p1_reached,
        p1_done,
        p2_undo,
        p2_undone,
        p2_redo,
        p2_redone,
        p3_edit,
        p3_click_block,
        p3_reached,
        p3_done,
        p4_edit,
        p4_click_tower,
        p4_escape,
        p4_kept,
        x.save_and_close(s, "extrudeface_basic.FCStd"),
        x.reopen(s),
        p5_reopened,
        p5_editing,
        p5_done,
        p6_edit,
        p6_to_object,
        p6_click_tower,
        p6_tower,
        p6_block,
        p6_done,
    ],
)
