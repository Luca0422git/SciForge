# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet's and Chamfer's live picture (sciforge/fillet_live.py): while the radius / distance
arrow is dragged (real mouse input, the button held, the program running between the moves:
arrow_input.HeldDrag) the round follows the mouse as a picture and the exact solid is built
only when the mouse rests or is let go, as Draft's does. Every check of the picture puts its
points on the exact round at the picture's size (Part's makeFillet / blend.trial).

Box 40 x 30 x 10 (real input), then:
  Fillet, front top edge   picked: the picture is made while nothing happens; drag the arrow
                           out: the picture shows during the moves at the dialog's radius and
                           lies on the exact round; no exact rebuild between the moves; let
                           go: the picture goes, the exact round (its volume) is shown
  past the largest radius  dragged far: held at the limit (just under 10 mm), no picture at
                           the end; 6 typed, dragged far again (the limit known): the
                           picture follows up to the limit and stops there, never past it
  a typed radius           Tab out of the box: the picture at once, the exact round on the
                           rest, the picture gone
  Cancel                   a radius typed (the picture shows) then Cancel: no picture left in
                           the view, no fillet in the body
  Chamfer, Two Distances   the second distance's arrow dragged: the flat band follows and lies
                           on the exact chamfer; let go: exact; OK: nothing left in the view
  Undo                     Fillet on another edge, a radius typed (the picture shows), Ctrl+Z:
                           the dialog ends, nothing left in the view
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
RIGHT_TOP = V(40, 15, 10)
BACK_TOP = V(20, 30, 10)
TOL = 1e-3
NODE = "SciForgeBlendLive"


def panel():
    return b.blend_panel()


def one_edge(r, length=40):
    return b.BOX - length * b.spandrel(r)


def overlay_in_scene():
    """True when a live picture node is in the 3D view's scene."""
    try:
        root = Gui.ActiveDocument.ActiveView.getSceneGraph()
    except Exception:
        return False
    for i in range(root.getNumChildren()):
        if root.getChild(i).getName().getString() == NODE:
            return True
    return False


def live_value(p, what):
    """The size the picture shows now (None when it is not shown)."""
    live = getattr(p, "_live", None)
    if live is None or not live.shown or live.spec is None:
        return None
    row = p._row_key()
    data = live.spec if row is None else live.spec["sets"][row]
    return float(data.get(what, 0.0))


def exact_faces(p):
    """The exact result's faces for the dialog's sizes now (nothing in the document)."""
    import Part

    from sciforge import blend

    row = p.spec["sets"][p._native_row()]
    refs = p.groups[p._native_row()]
    if p.kind == "fillet":
        names = blend.blended_edges(p.info, refs)
        edges = [blend.element(p.info.shape, n) for n in names]
        shape = p.info.shape.makeFillet(float(row["radius"]), edges)
    else:
        shape = blend.trial("chamfer", p.info, refs, row)
    return Part.Compound(shape.Faces)


def picture_matches(label, p):
    """Every point of the picture lies on the exact result at the picture's sizes."""
    import Part

    live = p._live
    pts = live.picture.points(live.spec)
    faces = exact_faces(p)
    worst = max(faces.distToShape(Part.Vertex(V(*q)))[0] for q in pts)
    h.check(
        "%s: the picture lies on the exact result" % label,
        worst < TOL and len(pts) >= 4,
        "worst %.5f mm, %d points" % (worst, len(pts)),
    )


def held_drag(along, label, index=0, moves=30, hold_ms=500):
    """Drag arrow `index` `along` mm like a hand does; a look after every move."""
    p = panel()
    if p is None or len(p.arrows) <= index:
        h.check("%s: an arrow to drag" % label, False, p and len(p.arrows))
        return
    p._timer.stop()
    dragger, spot, _origin, direction = p.arrows[index]
    what = spot["what"]
    rec = s["rec"] = {"samples": [], "builds": [], "checked": False, "what": what}
    old = p._preview

    def preview(*args, **kwargs):
        rec["builds"].append(len(rec["samples"]))
        return old(*args, **kwargs)

    p._preview = preview

    def sample(i):
        q = panel()
        if q is None:
            return
        shown = bool(q._live is not None and q._live.shown)
        value = q._value(q._row_key(), what)
        rec["samples"].append(
            {"i": i, "shown": shown, "value": value, "live": live_value(q, what)}
        )
        if i >= moves // 2 and shown and not rec["checked"]:
            rec["checked"] = True
            picture_matches(label + ", while dragged", q)
            import time

            q._last_motion = time.perf_counter()  # the check is not a pause of the hand

    head = a.head_point(dragger)
    start, end = h.screen_point(head), h.screen_point(head + direction * along)
    s["drag"] = a.HeldDrag(start, end, moves=moves, every_ms=16, hold_ms=hold_ms, sample=sample)
    s["drag"].run()


def dragged(label, check_builds=True):
    rec = s.get("rec") or {}
    p = panel()
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    samples = rec.get("samples", [])
    moving = [x for x in samples if x["i"] > 0]
    h.check("%s: the arrow was held and moved" % label, len(moving) >= 10, len(moving))
    shown = [x for x in moving if x["shown"]]
    h.check(
        "%s: the picture showed while moving" % label,
        len(shown) >= 0.6 * max(1, len(moving)),
        "%d of %d" % (len(shown), len(moving)),
    )
    h.check(
        "%s: at the dialog's size" % label,
        all(abs(x["live"] - x["value"]) < 1e-9 for x in shown),
        [(x["live"], x["value"]) for x in shown if abs(x["live"] - x["value"]) >= 1e-9][:4],
    )
    values = [x["value"] for x in moving]
    h.check(
        "%s: the size followed the mouse" % label,
        len(set(round(v, 6) for v in values)) >= 5,
        values[:: max(1, len(values) // 8)],
    )
    if check_builds:
        last = max([x["i"] for x in moving], default=0)
        early = [i for i in rec.get("builds", []) if i < last - 1]
        h.check("%s: no exact rebuild between the moves" % label, not early, early)
    h.check("%s: the picture was checked" % label, rec.get("checked"))


def exact_shown(label, volume=None):
    p = panel()
    if p is None:
        h.check("%s: dialog open" % label, False)
        return
    h.check("%s: the picture is gone" % label, not (p._live and p._live.shown))
    h.check("%s: no picture node in the view" % label, not overlay_in_scene())
    h.check("%s: the preview solid is shown again" % label, not p._live_hid)
    h.check("%s: no message" % label, not p.error, p.error)
    if volume is not None:
        v = h.solid_volume()
        h.check("%s: the exact result" % label, b.close(v, volume), (v, volume))


# -- Fillet: the front top edge ------------------------------------------------------------------
def fillet_start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def pick_front_top():
    h.click_edge(FRONT_TOP)


def picked():
    p = panel()
    h.check("one edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("its arrow", p is not None and len(p.arrows) == 1, p and len(p.arrows))
    h.check(
        "the picture was made while nothing happened",
        p is not None and p._live is not None and p._live_key is not None,
    )
    h.check("but not shown yet", not overlay_in_scene())


picked.wait_ms = 1500


def drag_out():
    held_drag(4.0, "fillet drag")


def dragged_out():
    dragged("fillet drag")
    p = panel()
    r = p.radius.value() if p else 0.0
    s["r"] = r
    h.check("the radius grew", r > 1.5, r)
    exact_shown("fillet let go", one_edge(r))
    h.shot("1-fillet-after-drag")


dragged_out.wait_ms = 1500


def drag_far():
    p = panel()
    s["searches"] = p.limits.searches if p else 0
    held_drag(40.0, "fillet far", moves=30, hold_ms=600)


def dragged_far():
    p = panel()
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    if p is None:
        h.check("dialog open after the far drag", False)
        return
    r = p.radius.value()
    s["limit"] = r
    h.check("held just under 10 mm", 9.0 < r <= 10.0, r)
    exact_shown("held at the limit", one_edge(r))


dragged_far.wait_ms = 2500


def type_six():
    p = panel()
    if p is not None:
        b.type_into(p.radius.widget, "6")
        QtTest.QTest.keyClick(p.radius.widget, QtCore.Qt.Key_Tab)


def typed_six():
    exact_shown("typed 6", one_edge(6.0))


typed_six.wait_ms = 1500


def drag_far_again():
    """The limit is known now: a drag past it again is held there on every move."""
    held_drag(40.0, "fillet far again", moves=30, hold_ms=300)


def dragged_far_again():
    rec = s.get("rec") or {}
    p = panel()
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    r = s.get("limit", 0.0)
    samples = [x for x in rec.get("samples", []) if x["i"] > 0]
    shown = [x for x in samples if x["live"] is not None]
    past = [x["live"] for x in shown if x["live"] > r + 1e-9]
    h.check("dragged past the limit again: the picture showed", len(shown) >= 10, len(shown))
    h.check("no picture past the limit", not past, past[:4])
    held = [x for x in shown if abs(x["live"] - r) < 1e-9]
    h.check("the picture stopped at the limit", len(held) >= 3, len(held))
    exact_shown("held at the limit again", one_edge(r))


dragged_far_again.wait_ms = 1500


def type_three():
    p = panel()
    if p is None:
        return
    b.type_into(p.radius.widget, "3")
    QtTest.QTest.keyClick(p.radius.widget, QtCore.Qt.Key_Tab)
    s["typed_live"] = live_value(p, "radius")
    s["typed_scene"] = overlay_in_scene()


def typed_three():
    h.check("typed 3: the picture at once", s.get("typed_live") == 3.0, s.get("typed_live"))
    h.check("typed 3: its node in the view", s.get("typed_scene"))
    exact_shown("typed 3", one_edge(3.0))


typed_three.wait_ms = 1500


def type_then_cancel():
    p = panel()
    if p is None:
        return
    b.type_into(p.radius.widget, "2.5")
    QtTest.QTest.keyClick(p.radius.widget, QtCore.Qt.Key_Tab)
    s["cancel_live"] = live_value(p, "radius")
    h.task_button("Cancel")


def cancelled():
    h.check("typed 2.5: the picture showed", s.get("cancel_live") == 2.5, s.get("cancel_live"))
    h.check("Cancel closed the dialog", b.blend_panel() is None and not Gui.Control.activeDialog())
    h.check("no picture left in the view", not overlay_in_scene())
    h.check("no fillet", not b.blends(), b.blends())
    v = h.solid_volume()
    h.check("the box as it was", b.close(v, b.BOX), v)


cancelled.wait_ms = 1000


# -- Chamfer: Two Distances ----------------------------------------------------------------------
def chamfer_start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def pick_right_top():
    h.click_edge(RIGHT_TOP)


def two_distances():
    p = panel()
    h.check("Chamfer, one edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p:
        b.choose(p.ctype, "Two Distances")


two_distances.wait_ms = 1500


def chamfer_drag():
    p = panel()
    h.check("two arrows", p is not None and len(p.arrows) == 2, p and len(p.arrows))
    held_drag(3.0, "chamfer drag", index=1)


def chamfer_dragged():
    dragged("chamfer drag")
    p = panel()
    if p is None:
        return
    d1, d2 = p.distance.value(), p.distance2.value()
    h.check("the second distance grew", d2 > 1.5 and abs(d1 - 1.0) < 1e-9, (d1, d2))
    exact_shown("chamfer let go", b.BOX - 30.0 * d1 * d2 / 2.0)


chamfer_dragged.wait_ms = 1500


def chamfer_ok():
    h.task_button("OK")


def chamfer_made():
    h.check("OK closed the dialog", b.blend_panel() is None and not Gui.Control.activeDialog())
    h.check("no picture left in the view", not overlay_in_scene())
    h.check("one chamfer", len(b.blends()) == 1, b.blends())


chamfer_made.wait_ms = 1000


# -- Undo while the picture shows ----------------------------------------------------------------
def undo_start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def pick_back_top():
    h.click_edge(BACK_TOP)


def type_then_undo():
    p = panel()
    h.check("Fillet on the back edge", p is not None and len(p.refs) == 1, p and p.refs)
    if p is None:
        return
    b.type_into(p.radius.widget, "2")
    QtTest.QTest.keyClick(p.radius.widget, QtCore.Qt.Key_Tab)
    s["undo_live"] = live_value(p, "radius")
    h.press("z", QtCore.Qt.ControlModifier)


type_then_undo.wait_ms = 1500


def undone():
    h.check("typed 2: the picture showed", s.get("undo_live") == 2.0, s.get("undo_live"))
    h.check("Ctrl+Z ended the dialog", b.blend_panel() is None and not Gui.Control.activeDialog())
    h.check("no picture left in the view", not overlay_in_scene())


undone.wait_ms = 1500


h.run(
    "fillet_live",
    b.box_steps("FilletLive")
    + [
        fillet_start,
        pick_front_top,
        picked,
        drag_out,
        dragged_out,
        drag_far,
        dragged_far,
        type_six,
        typed_six,
        drag_far_again,
        dragged_far_again,
        type_three,
        typed_three,
        type_then_cancel,
        cancelled,
        chamfer_start,
        pick_right_top,
        two_distances,
        chamfer_drag,
        chamfer_dragged,
        chamfer_ok,
        chamfer_made,
        undo_start,
        pick_back_top,
        type_then_undo,
        undone,
    ],
)
