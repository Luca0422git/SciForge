# SPDX-License-Identifier: LGPL-2.1-or-later
"""Delete (Del, Modify > Delete), only real input.

Part: box 0..40 x 0..30 x 10 (12000), a through hole r 5 at (20, 15) cut with Extrude
(- 250 pi = 785.398...), a round boss r 3, 5 high at (8, 8) on top (+ 45 pi = 141.37...).

  A  nothing selected, Del: nothing happens (a note by the pointer), no error.
  B  click the hole's wall, Del: a "Delete Face" step closes the hole: 12000 + 45 pi. Ctrl+Z
     brings the hole back, Ctrl+Y closes it again, Ctrl+Z again.
  C  click the box's top face, Del: it cannot be closed; nothing changes, no error.
  D  click the boss in the timeline, Modify > Delete: the boss step is gone, the steps after
     it (none) and before it are fine: 12000 - 250 pi. Ctrl+Z.
  E  click the hole's sketch in the browser, Modify > Delete: the hole's extrude has no
     profile any more: it is red in the timeline (with the reason), adds nothing, the boss
     after it still builds: 12000 + 45 pi; the Report view stays clean. Ctrl+Z.
  F  a second body (New Body): click it in the browser, Modify > Delete: one body left;
     Ctrl+Z brings it back.
  G  Delete Face edited from the timeline (double-click): its dialog opens; Cancel.
"""
import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
HOLE = 250 * math.pi
BOSS = 45 * math.pi
state = {}


def body():
    return s.bodies()[0]


def vol():
    return s.volume(body())


def steps():
    return [o for o in body().Group if "BaseFeature" in o.PropertiesList]


def hole_step():
    return state.get("hole")


def remember_steps():
    found = [o for o in body().Group if o.TypeId in ("PartDesign::Pad", "PartDesign::Pocket")]
    found += [o for o in body().Group if getattr(o, "SciForgeType", "") == "Extrude"]
    found = sorted(set(found), key=lambda o: o.ID)
    h.check("three extrudes", len(found) == 3, [o.Name for o in found])
    if len(found) == 3:
        state["box"], state["hole"], state["boss"] = found
    h.check("part volume", s.close(vol(), 12000 - HOLE + BOSS), vol())


# -- A ----------------------------------------------------------------------------------------
def a_delete_nothing():
    h.click_empty()
    state["count"] = len(body().Group)
    h.press(QtCore.Qt.Key_Delete)


def a_nothing_happened():
    h.check("nothing deleted", len(body().Group) == state["count"])
    h.check("volume kept", s.close(vol(), 12000 - HOLE + BOSS), vol())
    s.no_popups("Del with nothing selected")


# -- B ----------------------------------------------------------------------------------------
def b_click_wall():
    h.fit()
    a = math.radians(135)
    h.click(V(20 + 5 * math.cos(a), 15 + 5 * math.sin(a), 8))


def b_delete():
    sel = s.selected_names()
    h.check("the hole's wall is selected", bool(sel), sel)
    h.press(QtCore.Qt.Key_Delete)


def b_closed():
    found = s.steps_of_kind("DeleteFace")
    h.check("a Delete Face step", len(found) == 1, found)
    h.check("hole closed: 12000 + 45 pi", s.close(vol(), 12000 + BOSS), vol())
    h.check("Delete Face is the end", found and body().Tip is found[0])
    h.shot("B-face-deleted")


def b_undo():
    s.undo()


def b_undone():
    h.check("undo: hole back", s.close(vol(), 12000 - HOLE + BOSS), vol())
    h.check("undo: no Delete Face", not s.steps_of_kind("DeleteFace"))


def b_redo():
    s.redo()


def b_redone():
    h.check("redo: hole closed", s.close(vol(), 12000 + BOSS), vol())


def b_undo_again():
    s.undo()


# -- C ----------------------------------------------------------------------------------------
def c_click_top():
    h.check("hole is back", s.close(vol(), 12000 - HOLE + BOSS), vol())
    h.click(V(32, 24, 10))


def c_delete():
    h.press(QtCore.Qt.Key_Delete)


def c_unchanged():
    h.check("top face refused: nothing changed", s.close(vol(), 12000 - HOLE + BOSS), vol())
    h.check("no Delete Face step", not s.steps_of_kind("DeleteFace"))
    s.no_popups("Del on the top face")


# -- D ----------------------------------------------------------------------------------------
def d_select_boss():
    h.click_empty()
    s.click_timeline(state["boss"])


def d_delete():
    h.check("boss selected", s.selected_names() == [state["boss"].Name], s.selected_names())
    s.menu("MODIFY", "Delete")


def d_deleted():
    h.check("boss gone: 12000 - 250 pi", s.close(vol(), 12000 - HOLE), vol())
    h.check("boss step removed", state["boss"].Name not in [o.Name for o in body().Group])
    h.check("the hole is the end now", body().Tip is state["hole"], body().Tip.Name)


def d_undo():
    s.undo()


def d_undone():
    h.check("undo: boss back", s.close(vol(), 12000 - HOLE + BOSS), vol())


# -- E ----------------------------------------------------------------------------------------
def e_select_sketch():
    from sciforge import timeline_ops

    sketch = timeline_ops.profile_sketch(state["hole"])
    state["sketch"] = sketch.Label if sketch is not None else "?"
    h.click_empty()
    s.click_browser_row(state["sketch"])


def e_delete():
    h.check(
        "sketch selected",
        s.selected_names() == [App.ActiveDocument.getObjectsByLabel(state["sketch"])[0].Name],
        s.selected_names(),
    )
    s.menu("MODIFY", "Delete")


def e_flagged():
    kind, reason = s.timeline_status(state["hole"])
    h.check("hole extrude flagged red", kind == "error", (kind, reason))
    h.check("the reason names the profile", "profile" in reason.lower(), reason)
    h.check("hole adds nothing, boss still built", s.close(vol(), 12000 + BOSS), vol())
    h.shot("E-flagged")


def e_undo():
    s.undo()


def e_undone():
    h.check("undo: sketch back", bool(App.ActiveDocument.getObjectsByLabel(state["sketch"])))
    h.check("undo: hole back", s.close(vol(), 12000 - HOLE + BOSS), vol())


# -- F ----------------------------------------------------------------------------------------
def f_select_body():
    h.check("two bodies", len(s.bodies()) == 2, [b.Label for b in s.bodies()])
    h.click_empty()
    s.click_browser_row(s.bodies()[1].Label)


def f_delete():
    s.menu("MODIFY", "Delete")


def f_deleted():
    h.check("one body left", len(s.bodies()) == 1, [b.Label for b in s.bodies()])


def f_undo():
    s.undo()


def f_undone():
    h.check("undo: two bodies", len(s.bodies()) == 2, [b.Label for b in s.bodies()])


# -- G ----------------------------------------------------------------------------------------
def g_delete_face_again():
    h.click_empty()
    h.fit()
    a = math.radians(135)
    h.click(V(20 + 5 * math.cos(a), 15 + 5 * math.sin(a), 8))


def g_delete():
    h.press(QtCore.Qt.Key_Delete)


def g_edit():
    found = s.steps_of_kind("DeleteFace")
    if h.check("Delete Face made", len(found) == 1, found):
        s.timeline_double_click(found[0])


def g_dialog():
    p = s.panel()
    h.check("Delete Face dialog", p is not None and p.title == "Delete Face", p)
    h.check("one face listed", p is not None and len(p.names) == 1, p and p.names)


def g_cancel():
    h.task_button("Cancel")


def g_cancelled():
    h.check("dialog closed", s.panel() is None)
    h.check("still closed: 12000 + 45 pi", s.close(vol(), 12000 + BOSS), vol())


h.run(
    "bodies_delete",
    [s.new_design("Delete")]
    + s.box_steps("box", (0, 0, 40, 30), 10, V(12, -8, 0))
    + ps.make_cut("hole", (20, 15), 5, 10)
    + ps.make_boss("boss", (8, 8), 3, 5, V(34, 6, 10))
    + [
        remember_steps,
        a_delete_nothing,
        a_nothing_happened,
        b_click_wall,
        b_delete,
        b_closed,
        b_undo,
        b_undone,
        b_redo,
        b_redone,
        b_undo_again,
        c_click_top,
        c_delete,
        c_unchanged,
        d_select_boss,
        d_delete,
        d_deleted,
        d_undo,
        d_undone,
        e_select_sketch,
        e_delete,
        e_flagged,
        e_undo,
        e_undone,
    ]
    + s.box_steps("other", (50, 0, 60, 10), 10, V(12, -8, 0), new_body=True)
    + [
        f_select_body,
        f_delete,
        f_deleted,
        f_undo,
        f_undone,
        g_delete_face_again,
        g_delete,
        g_edit,
        g_dialog,
        g_cancel,
        g_cancelled,
    ],
)
