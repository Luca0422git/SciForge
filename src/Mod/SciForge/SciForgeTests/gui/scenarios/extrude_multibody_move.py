# SPDX-License-Identifier: LGPL-2.1-or-later
"""An Extrude that cuts several bodies can be dragged along the timeline: its hidden step
in the other body moves with it (before, the drag was refused with a message). Real input
on the timeline (drags, the marker, the right-click menu, Undo / Redo).

Body1 = x 0..20, Body2 = x 30..50 (20 x 20 x 10 = 4000 each). A cut from z 10 over x 10..40,
y 5..15, 5 deep goes through both (3500 / 3500). Then a fill in Body2: 36..42 x 8..12, 3 deep
from z 10, Join: it puts 4 x 4 x 3 = 48 back into the cut (Body2 = 3548).
  drag the cut after the fill (the end of the timeline): the fill now comes first (adds
      nothing, Body2 is solid there) and the cut after it: 3500 / 3500; the hidden step sits
      after the fill in Body2's history. Marker before the cut: 4000 / 4000; to the end:
      3500 / 3500. Suppress / Unsuppress: 4000 / 4000, then 3500 / 3500.
  drag the cut back before the fill: 3500 / 3548. Undo: 3500 / 3500. Redo: 3500 / 3548.
  drag Body2's box after the cut: refused (the cut would come before Body2 exists), nothing
      changes. Delete the cut: 4000 / 4000, no hidden step left.
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def body1():
    return s.bodies()[0]


def body2():
    return s.bodies()[1]


def near(a, c):
    return s.close(a, c)


def check_volumes(where, v1, v2):
    h.check("%s: Body1 = %g" % (where, v1), near(s.volume(body1()), v1), s.volume(body1()))
    h.check("%s: Body2 = %g" % (where, v2), near(s.volume(body2()), v2), s.volume(body2()))


def followers():
    from sciforge import extrude_bodies

    doc = App.ActiveDocument
    return [o for o in doc.Objects if extrude_bodies.is_follower(o)] if doc else []


def solid_order(body):
    """Names of the body's solid steps in its history order (hidden steps included)."""
    return [o.Name for o in body.Group if "BaseFeature" in o.PropertiesList]


def setup():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("MultiBodyMove")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    s1 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s1, 0, 0, 20, 20)
    extrude.make(body, s1, {"distance": 10.0})
    s2 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(s2, 30, 0, 50, 20)
    state["e2"] = extrude.make(body, s2, {"distance": 10.0, "operation": "new_body"})
    App.ActiveDocument.recompute()
    s3 = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    s3.AttachmentOffset = App.Placement(V(0, 0, 10), App.Rotation())
    h.draw_rectangle(s3, 10, 5, 40, 15)
    App.ActiveDocument.recompute()
    state["cut"] = extrude.make(body, s3, {"distance": -5.0, "operation": "cut", "bodies": "auto"})
    App.ActiveDocument.recompute()
    other = body2()
    planes2 = sketch_ui.origin_planes(other)
    s4 = sketch_ui.create_sketch(other, (planes2["XY_Plane"], ""))
    s4.AttachmentOffset = App.Placement(V(0, 0, 10), App.Rotation())
    h.draw_rectangle(s4, 36, 8, 42, 12)
    App.ActiveDocument.recompute()
    state["fill"] = extrude.make(other, s4, {"distance": -3.0, "operation": "join"})
    App.ActiveDocument.recompute()
    h.fit()
    check_volumes("cut through both, then the fill in Body2", 3500, 3548)
    h.check("one hidden step in Body2", len(followers()) == 1, [f.Label for f in followers()])
    state["cut_title"] = s.timeline_title_of(state["cut"])
    state["fill_title"] = s.timeline_title_of(state["fill"])
    state["box2_title"] = s.timeline_title_of(state["e2"])
    h.check("the cut and the fill are in the timeline", state["cut_title"] and state["fill_title"],
            (state["cut_title"], state["fill_title"]))
    state["titles"] = list(t.titles())


# -- the cut dragged after the fill ------------------------------------------------------------
def drag_cut_to_end():
    h.check("drag the cut to the end of the timeline", t.drag_step(state["cut_title"],
                                                                      after_last=True))


drag_cut_to_end.wait_ms = 2500


def moved_after_fill():
    titles = list(t.titles())
    h.check("the cut is last now", titles and titles[-1] == state["cut_title"], titles)
    check_volumes("the fill first, then the cut", 3500, 3500)
    h.check("still one hidden step", len(followers()) == 1, [f.Label for f in followers()])
    order = solid_order(body2())
    if followers():
        h.check("Body2's history: box, fill, then the hidden cut",
                order == [state["e2"].Name, state["fill"].Name, followers()[0].Name], order)
    h.check("no step in error", not [o.Label for o in App.ActiveDocument.Objects
                                     if "Invalid" in o.State])
    h.shot("1-moved")


def marker_before_cut():
    t.drag_marker(before_title=state["cut_title"])


def rolled_back():
    check_volumes("marker before the cut", 4000, 4000)
    t.drag_marker(to_end=True)


def rolled_forward():
    check_volumes("marker at the end", 3500, 3500)
    t.menu(state["cut_title"], "Suppress Features")


def suppressed():
    check_volumes("suppressed", 4000, 4000)
    t.menu(state["cut_title"], "Unsuppress Features")


def unsuppressed():
    check_volumes("unsuppressed", 3500, 3500)


# -- back before the fill, Undo / Redo ------------------------------------------------------------
def drag_cut_back():
    h.check("drag the cut back before the fill",
            t.drag_step(state["cut_title"], before_title=state["fill_title"]))


drag_cut_back.wait_ms = 2500


def moved_back():
    titles = list(t.titles())
    cut, fill = s.timeline_title_of(state["cut"]), s.timeline_title_of(state["fill"])
    h.check("the cut is right before the fill again",
            cut in titles and fill in titles and titles.index(cut) == titles.index(fill) - 1,
            (cut, fill, titles))
    check_volumes("the cut first, then the fill", 3500, 3548)
    order = solid_order(body2())
    if followers():
        h.check("Body2's history: box, the hidden cut, then the fill",
                order == [state["e2"].Name, followers()[0].Name, state["fill"].Name], order)
    s.undo()


def undone():
    check_volumes("Undo the move", 3500, 3500)
    s.redo()


def redone():
    check_volumes("Redo the move", 3500, 3548)
    h.check("still one hidden step", len(followers()) == 1)


# -- a move that cannot be: Body2's box after the cut ---------------------------------------------
def drag_box2_after_cut():
    state["before_refused"] = list(t.titles())
    h.check("drag Body2's box after the cut",
            t.drag_step(state["box2_title"], before_title=state["fill_title"]))


drag_box2_after_cut.wait_ms = 1200  # the red mark and its reason stay 2.5 s


def refused():
    reason = t.tl().refusal()
    h.check("refused: the timeline is as it was", list(t.titles()) == state["before_refused"],
            (t.titles(), state["before_refused"]))
    check_volumes("refused: nothing changed", 3500, 3548)
    h.check("the timeline said why (Body2 would not exist yet)",
            "does not exist yet" in reason, reason)
    h.check("no step in error", not [o.Label for o in App.ActiveDocument.Objects
                                     if "Invalid" in o.State])
    h.check("no pop-up", not h.popups(), h.popups())


# -- delete ------------------------------------------------------------------------------------
def delete_cut():
    state["cut_name"] = state["cut"].Name
    t.menu(state["cut_title"], "Delete")


def deleted():
    check_volumes("deleted", 4000, 4000)
    h.check("no hidden step left behind", not followers(), [f.Label for f in followers()])
    h.check("the cut is gone", App.ActiveDocument.getObject(state["cut_name"]) is None,
            t.titles())


h.run(
    "extrude_multibody_move",
    [
        setup,
        drag_cut_to_end,
        moved_after_fill,
        marker_before_cut,
        rolled_back,
        rolled_forward,
        suppressed,
        unsuppressed,
        drag_cut_back,
        moved_back,
        undone,
        redone,
        drag_box2_after_cut,
        refused,
        delete_cut,
        deleted,
    ],
)
