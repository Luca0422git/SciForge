# SPDX-License-Identifier: LGPL-2.1-or-later
"""The profile sketch shows while an existing extrude is edited (Fusion), and goes back to
hidden on OK or Cancel without an extra undo step (R6 only kept a new extrude's sketch).

A block 40 x 30 x 10 from sketch A (hidden by the extrude). Double-click Extrude 1: the
dialog opens on it and sketch A is shown; Cancel: hidden again, the undo list unchanged.
Double-click again, Distance 12, OK: 40 x 30 x 12, sketch A hidden, exactly one undo step
more; Undo: 40 x 30 x 10 and the sketch stays hidden (the show / hide was never part of
the step); Redo: 12, still hidden.
Two bodies (x 0..20 and x 30..50, 20 x 20 x 10) cut across by one extrude from a sketch at
z 10 (x 10..40, y 5..15, 5 deep): double-click the cut: its sketch shows; -6 then OK: both
3400, the sketch hidden, one undo step; Undo: 3500 / 3500, hidden.

Hand-derived: 40*30*10 = 12000, 40*30*12 = 14400; 4000 - 10*10*5 = 3500, 4000 - 600 = 3400.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as bst
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def shown(sketch):
    try:
        return bool(sketch.ViewObject.Visibility)
    except Exception:
        return None


def undo_count():
    return len(App.ActiveDocument.UndoNames)


def title_of(feature):
    from SciForgeTests.gui import timeline_input as t

    for item in t.tl().items():
        if item.name == feature.Name:
            return item.display
    return None


# -- a block from a hidden sketch -------------------------------------------------------------
def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("EditSketchShown")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    s["a"] = sk
    s["e1"] = extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()
    h.check("block 40 x 30 x 10", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("the extrude hid its sketch", shown(sk) is False, shown(sk))
    s["undo0"] = undo_count()


def edit():
    s["title"] = title_of(s["e1"])
    h.check("double-click the extrude", ui.double_click_timeline(s["title"] or "?"))


def shown_while_editing():
    p = panel()
    h.check("the edit dialog is open", p is not None and p.editing and p.target is s["e1"])
    h.check("the profile sketch is shown while editing", shown(s["a"]) is True, shown(s["a"]))
    h.shot("1-edit-sketch-shown")
    h.task_button("Cancel")


def hidden_after_cancel():
    h.check("Cancel closed the dialog", panel() is None and not Gui.Control.activeDialog())
    h.check("Cancel: the sketch is hidden again", shown(s["a"]) is False, shown(s["a"]))
    h.check("Cancel: no undo step was added", undo_count() == s["undo0"],
            (undo_count(), s["undo0"], App.ActiveDocument.UndoNames[:3]))
    h.check("block unchanged", near(h.solid_volume(), 12000.0), h.solid_volume())


def edit_again():
    h.check("double-click the extrude again", ui.double_click_timeline(s["title"] or "?"))


def change_distance():
    p = panel()
    h.check("the edit dialog is open again", p is not None and p.editing)
    h.check("the sketch is shown again", shown(s["a"]) is True, shown(s["a"]))
    if p is not None:
        ui.type_into(p.distance.widget, "12")


def ok():
    h.check("the preview follows: 40 x 30 x 12", near(h.solid_volume(), 14400.0), h.solid_volume())
    h.task_button("OK")


def hidden_after_ok():
    h.check("OK closed the dialog", panel() is None)
    h.check("40 x 30 x 12 kept", near(h.solid_volume(), 14400.0), h.solid_volume())
    h.check("OK: the sketch is hidden again", shown(s["a"]) is False, shown(s["a"]))
    h.check("OK: exactly one undo step more", undo_count() == s["undo0"] + 1,
            (undo_count(), s["undo0"], App.ActiveDocument.UndoNames[:3]))
    bst.undo()


def undone():
    h.check("Undo: 40 x 30 x 10 again", near(h.solid_volume(), 12000.0), h.solid_volume())
    h.check("Undo does not show the sketch (never part of the step)", shown(s["a"]) is False,
            shown(s["a"]))
    bst.redo()


def redone():
    h.check("Redo: 40 x 30 x 12", near(h.solid_volume(), 14400.0), h.solid_volume())
    h.check("Redo: the sketch stays hidden", shown(s["a"]) is False, shown(s["a"]))


# -- a multi-body extrude --------------------------------------------------------------------------
def setup_bodies():
    from sciforge import commands, extrude, sketch_ui

    App.newDocument("EditSketchShownBodies")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    s1 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s1, 0, 0, 20, 20)
    extrude.make(body, s1, {"distance": 10.0})
    s2 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s2, 30, 0, 50, 20)
    extrude.make(body, s2, {"distance": 10.0, "operation": "new_body"})
    App.ActiveDocument.recompute()
    s3 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    s3.AttachmentOffset = App.Placement(V(0, 0, 10), App.Rotation())
    h.draw_rectangle(s3, 10, 5, 40, 15)
    App.ActiveDocument.recompute()
    s["cut"] = extrude.make(body, s3, {"distance": -5.0, "operation": "cut", "bodies": "auto"})
    s["s3"] = s3
    App.ActiveDocument.recompute()
    h.fit()
    bodies = bst.bodies()
    h.check("two bodies cut across: 3500 / 3500",
            len(bodies) == 2 and near(bst.volume(bodies[0]), 3500) and near(bst.volume(bodies[1]), 3500),
            [bst.volume(b) for b in bodies])
    h.check("the cut hid its sketch", shown(s3) is False, shown(s3))
    s["undo1"] = undo_count()


def edit_cut():
    s["cut_title"] = title_of(s["cut"])
    h.check("double-click the multi-body cut", ui.double_click_timeline(s["cut_title"] or "?"))


def cut_sketch_shown():
    p = panel()
    h.check("the edit dialog is open on the cut", p is not None and p.editing)
    h.check("the cut's sketch is shown while editing", shown(s["s3"]) is True, shown(s["s3"]))
    h.check("the row lists both bodies", p is not None
            and p.fields["bodies"].button.text() == "2 bodies",
            p and p.fields["bodies"].button.text())
    if p is not None:
        ui.type_into(p.distance.widget, "-6")


def cut_ok():
    bodies = bst.bodies()
    h.check("-6: 3400 / 3400", all(near(bst.volume(b), 3400) for b in bodies),
            [bst.volume(b) for b in bodies])
    h.task_button("OK")


def cut_hidden_after_ok():
    h.check("OK closed the dialog", panel() is None)
    h.check("OK: the cut's sketch is hidden again", shown(s["s3"]) is False, shown(s["s3"]))
    h.check("OK: one undo step more", undo_count() == s["undo1"] + 1,
            (undo_count(), s["undo1"], App.ActiveDocument.UndoNames[:3]))
    bst.undo()


def cut_undone():
    bodies = bst.bodies()
    h.check("Undo: 3500 / 3500", all(near(bst.volume(b), 3500) for b in bodies),
            [bst.volume(b) for b in bodies])
    h.check("Undo leaves the sketch hidden", shown(s["s3"]) is False, shown(s["s3"]))


h.run(
    "extrude_edit_sketch_shown",
    [
        setup,
        edit,
        shown_while_editing,
        hidden_after_cancel,
        edit_again,
        change_distance,
        ok,
        hidden_after_ok,
        undone,
        redone,
        setup_bodies,
        edit_cut,
        cut_sketch_shown,
        cut_ok,
        cut_hidden_after_ok,
        cut_undone,
    ],
)
