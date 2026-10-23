# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live pictures of Press Pull, Shell and Extrude (sciforge/live_shapes.py): while the handle
is dragged (real mouse input, the button held, the program running between the moves:
arrow_input.HeldDrag) the faces that move follow the mouse as a picture, and the exact solid
is built only when the mouse rests or is let go, as Draft does (draft_live). Timing is not
checked here (Luca, 2026-10-23: he judges the feel on his own computer); what is checked:

  every case    the picture shows during the moves, at the dialog's value; no exact rebuild
                between two moves; let go: the picture goes, the exact solid comes back
                (shown again, the part before the step no longer see-through), with the
                volume the same dialog built before the live pictures; every point of the
                picture at the final value lies on that exact solid
  Press Pull    the box's top pulled up, then pushed down; a hole's wall (radius changes)
  Shell         an open box (inside wall), then the Outside wall
  Extrude       a rectangle and a circle: distance, then the taper disc, then Symmetric
  leftovers     no picture node in the scene after OK, Cancel, or Undo in the middle of a drag
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import draft_perf_parts as parts
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
S = {}
TOL = 2e-3
NODE = "SciForgeLiveShape"

BOX_HOLE = parts.BOX + [
    {
        "op": "sketch",
        "id": "s2",
        "plane": "XY",
        "offset": 10,
        "geometry": [{"circle": [20, 15, 4]}],
    },
    {"op": "extrude", "id": "e2", "profile": "s2", "distance": 6, "flip": True, "operation": "cut"},
]
PROFILE = [
    {
        "op": "sketch",
        "id": "s1",
        "plane": "XY",
        "geometry": [{"rect": [0, 0, 30, 20]}, {"circle": [45, 10, 6]}],
    },
]


# -- helpers --------------------------------------------------------------------------------
def fresh(name, steps):
    try:
        if Gui.Control.activeDialog():
            h.task_button("Cancel")
    except Exception:
        pass
    for doc in list(App.listDocuments()):
        try:
            App.closeDocument(doc)
        except Exception:
            pass
    doc = App.newDocument(name)
    S["b"] = parts.build(doc, steps)
    S["doc"] = doc
    h.fit()


def body():
    return S["b"].body


def tip_faces(pred):
    shape = body().Tip.Shape
    return ["Face%d" % i for i, f in enumerate(shape.Faces, 1) if pred(f)]


def top_face(f):
    return f.Surface.__class__.__name__ == "Plane" and f.normalAt(0, 0).z > 0.999


def nodes_left():
    try:
        root = Gui.ActiveDocument.ActiveView.getSceneGraph()
    except Exception:
        return 0
    return sum(
        1 for i in range(root.getNumChildren()) if root.getChild(i).getName().getString() == NODE
    )


def live_of(p):
    return p.__dict__.get("_live_view") if p is not None else None


def global_of(obj):
    """The exact solid of a step in global coordinates."""
    shape = obj.Shape.copy()
    holder = obj.getParentGeoFeatureGroup()
    if holder is not None:
        shape.Placement = holder.getGlobalPlacement().multiply(shape.Placement)
    return shape


def picture_on(label, p, exact):
    """Every point of the picture at the dialog's values now lies on `exact` (global)."""
    import Part

    live = live_of(p)
    overlay = live.overlay if live is not None else None
    if overlay is None or not overlay.pictures:
        h.check("%s: a picture was made" % label, False)
        return
    values = p.live_values()
    worst, count = 0.0, 0
    for pic in overlay.pictures:
        faces, lines = pic.points_at(values)
        for q in faces + lines:
            worst = max(worst, exact.distToShape(Part.Vertex(V(*q)))[0])
            count += 1
    h.check(
        "%s: the picture lies on the exact solid" % label,
        worst < TOL and count > 0,
        "worst %.5f mm over %d points, values %s" % (worst, count, values),
    )


def held(p, handle, start, end, label, moves=24):
    """Drag a handle with the button held; record what the dialog shows after every move."""
    p._timer.stop()
    S["rec"] = rec = {"samples": [], "builds": [], "label": label}
    real = p._recompute

    def counted(*args, **kwargs):
        rec["builds"].append(len(rec["samples"]))
        return real(*args, **kwargs)

    p._recompute = counted

    rec["start"] = p.live_values()

    def sample(index):
        live = live_of(p)
        shown = bool(live is not None and live.shown)
        rec["samples"].append(
            {
                "i": index,
                "changed": p.live_values() != rec["start"],
                "shown": shown,
                "same": shown and live.values == p.live_values(),
                "values": live.values if shown else None,
            }
        )

    S["drag"] = a.HeldDrag(start, end, moves=moves, every_ms=25, hold_ms=150, sample=sample)
    S["drag"].run()


def after_drag(label, p, hidden=(), unghosted=()):
    rec = S.get("rec") or {}
    try:
        del p._recompute
    except Exception:
        pass
    moving = [x for x in rec.get("samples", []) if x["i"] > 0]
    h.check("%s: the handle moved" % label, len(moving) >= 10, len(moving))
    # from the first move that changed the value (a handle takes a few pixels to start)
    first = next((k for k, x in enumerate(moving) if x["changed"]), len(moving))
    moving = moving[first:]
    shown = [x for x in moving if x["shown"]]
    h.check("%s: the value changed during the moves" % label, len(moving) >= 6, len(moving))
    h.check(
        "%s: the picture showed while moving" % label,
        len(shown) >= 0.6 * max(1, len(moving)),
        "%d of %d: %s" % (len(shown), len(moving), [int(x["shown"]) for x in moving]),
    )
    h.check(
        "%s: at the dialog's values" % label,
        all(x["same"] for x in shown),
        [x["values"] for x in shown if not x["same"]][:3],
    )
    last = max([x["i"] for x in moving], default=0)
    early = [i for i in rec.get("builds", []) if i < last - 1]
    h.check("%s: no exact rebuild between the moves" % label, not early, early)
    live = live_of(p)
    h.check("%s: let go, the picture is gone" % label, live is None or not live.shown)
    h.check("%s: nothing hidden for it any more" % label, live is None or not live.hid)
    for obj in hidden:
        h.check(
            "%s: %s shown again" % (label, obj.Label),
            obj.ViewObject is not None and live_shapes_shown(obj.ViewObject),
        )
    for obj in unghosted:
        h.check(
            "%s: %s out of sight again" % (label, obj.Label),
            obj.ViewObject is None or not live_shapes_shown(obj.ViewObject),
        )


def live_shapes_shown(vobj):
    from sciforge import live_shapes

    return live_shapes.shown(vobj)


def close(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


# -- Press Pull ------------------------------------------------------------------------------------
def pp_panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def pp_build():
    fresh("LivePressPull", parts.BOX)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(body().Tip, tip_faces(top_face)[0])


def pp_open():
    h.press("q")


def pp_drag_up():
    p = pp_panel()
    if not h.check("Press Pull open on the top face", p is not None and p.dragger is not None):
        return
    head = a.head_point(p.dragger)
    held(
        p,
        p.dragger,
        h.screen_point(head),
        h.screen_point(head + p.dragger.direction * 8.0),
        "Press Pull up",
    )


pp_drag_up.wait_ms = 2000


def pp_up_done():
    p = pp_panel()
    if not h.check("Press Pull still open", p is not None):
        return
    d = p.field.value()
    after_drag("Press Pull up", p, hidden=[p.target], unghosted=[p.base])
    h.check("pulled up", d > 0.5, d)
    h.check("the exact solid: the box taller by d", close(p.target.Shape.Volume, 1200.0 * (10 + d)))
    picture_on("Press Pull up", p, global_of(p.target))
    head = a.head_point(p.dragger)
    held(
        p,
        p.dragger,
        h.screen_point(head),
        h.screen_point(head - p.dragger.direction * 14.0),
        "Press Pull down",
    )


pp_up_done.wait_ms = 2000


def pp_down_done():
    p = pp_panel()
    if not h.check("Press Pull still open", p is not None):
        return
    d = p.field.value()
    after_drag("Press Pull down", p, hidden=[p.target], unghosted=[p.base])
    h.check("pushed down", d < -0.5, d)
    h.check("the exact solid: the box lower by d", close(p.target.Shape.Volume, 1200.0 * (10 + d)))
    picture_on("Press Pull down", p, global_of(p.target))
    h.task_button("OK")


def pp_ok():
    h.check("Press Pull: OK closed it", pp_panel() is None and not Gui.Control.activeDialog())
    h.check("Press Pull: no picture left after OK", nodes_left() == 0, nodes_left())


def hole_build():
    fresh("LiveHole", BOX_HOLE)
    Gui.Selection.clearSelection()
    wall = tip_faces(lambda f: f.Surface.__class__.__name__ == "Cylinder")
    Gui.Selection.addSelection(body().Tip, wall[0])
    S["hole_volume"] = body().Tip.Shape.Volume


def hole_drag():
    p = pp_panel()
    if not h.check("Press Pull open on the hole's wall", p is not None and p.dragger is not None):
        return
    head = a.head_point(p.dragger)
    held(
        p,
        p.dragger,
        h.screen_point(head),
        h.screen_point(head + p.dragger.direction * 2.5),
        "the hole's wall",
    )


hole_drag.wait_ms = 2000


def hole_done():
    from sciforge import presspull_core

    p = pp_panel()
    if not h.check("Press Pull still open", p is not None):
        return
    d = p.field.value()
    after_drag("the hole's wall", p, hidden=[p.target], unghosted=[p.base])
    want = presspull_core.press_pull(
        p.base.Shape, [p.base.Shape.getElement(n) for n in p.names], d
    ).Volume
    h.check("the exact solid", close(p.target.Shape.Volume, want), (p.target.Shape.Volume, want))
    picture_on("the hole's wall", p, global_of(p.target))
    # a drag step, then Undo before the mouse rests: the dialog goes, nothing stays
    p._dragged(d + 1.0)
    live = live_of(p)
    h.check("a drag step shows the picture", live is not None and live.shown)
    h.press("z", QtCore.Qt.ControlModifier)


def hole_undone():
    h.check("Undo closed Press Pull", pp_panel() is None and not Gui.Control.activeDialog())
    h.check("no picture left after Undo", nodes_left() == 0, nodes_left())
    tip = body().Tip
    h.check("the part as before", close(tip.Shape.Volume, S["hole_volume"]))
    h.check("the part is shown", live_shapes_shown(tip.ViewObject))


# -- Shell -----------------------------------------------------------------------------------------
def shell_build():
    fresh("LiveShell", parts.BOX)


def shell_open():
    from sciforge import shell_ui

    picks = [(body().Tip, tip_faces(top_face)[0])]
    panel = shell_ui.ShellPanel(S["doc"], picks=picks, body=body())
    Gui.Control.showDialog(panel)


def shell_drag(label="Shell inside"):
    p = sd.shell_panel()
    if not h.check("%s: Shell with an arrow" % label, p is not None and p.arrows):
        return
    start, end = sd.arrow_screen(p, 0, 2.0)
    held(p, p.arrows[0][0], start, end, label)


shell_drag.wait_ms = 2000


def shell_done():
    from sciforge import shelling

    p = sd.shell_panel()
    if not h.check("Shell still open", p is not None):
        return
    t = float(p.options["inside"])
    after_drag("Shell inside", p, hidden=[p.target])
    h.check("the wall changed", abs(t - 1.0) > 0.05, t)
    want = shelling.build(p.base.Shape, list(p.names()), p.options).Volume
    h.check("the exact shell", close(p.target.Shape.Volume, want), (p.target.Shape.Volume, want))
    picture_on("Shell inside", p, global_of(p.target))
    sd.choose(p.direction, "Outside")


def shell_outside():
    shell_drag("Shell outside")


shell_outside.wait_ms = 2000


def shell_outside_done():
    p = sd.shell_panel()
    if not h.check("Shell still open", p is not None):
        return
    after_drag("Shell outside", p, hidden=[p.target])
    picture_on("Shell outside", p, global_of(p.target))
    h.task_button("Cancel")


def shell_cancelled():
    h.check("Shell: Cancel closed it", sd.shell_panel() is None and not Gui.Control.activeDialog())
    h.check("Shell: no picture left after Cancel", nodes_left() == 0, nodes_left())
    h.check("Shell: the box as before", close(body().Tip.Shape.Volume, 12000.0))


# -- Extrude ----------------------------------------------------------------------------------------
def x_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def x_build():
    fresh("LiveExtrude", PROFILE)


def sketch():
    return [o for o in S["doc"].Objects if o.TypeId == "Sketcher::SketchObject"][0]


def x_open():
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch())
    h.press("e")


def x_type():
    p = x_panel()
    if not h.check("Extrude open", p is not None):
        return
    p.distance.set_value(10.0)  # a first exact extrusion to drag from


x_type.wait_ms = 1500


def x_drag():
    p = x_panel()
    arrow = p.draggers.get("distance") if p is not None else None
    if not h.check("Extrude: its arrow", arrow is not None):
        return
    head = a.head_point(arrow)
    held(p, arrow, h.screen_point(head), h.screen_point(head + arrow.direction * 8.0), "Extrude")


x_drag.wait_ms = 2000


def extrusion_volume(d, taper=0.0):
    import math

    if abs(taper) < 1e-12:
        return (600.0 + math.pi * 36.0) * d
    return None


def x_done():
    p = x_panel()
    if not h.check("Extrude still open", p is not None and p.target is not None):
        return
    d = float(p.options["distance"])
    after_drag("Extrude", p, hidden=[p.target])
    h.check("dragged", abs(d - 10.0) > 0.5, d)
    want = extrusion_volume(d)
    h.check(
        "the exact extrusion", close(p.target.Shape.Volume, want), (p.target.Shape.Volume, want)
    )
    picture_on("Extrude", p, global_of(p.target))
    p.taper.set_value(4.0)  # the taper disc shows from here


x_done.wait_ms = 1500


def x_taper_drag():
    p = x_panel()
    disc = p.draggers.get("taper") if p is not None else None
    if not h.check("Extrude: the taper disc", disc is not None):
        return
    here, there = disc.screen_points(9.0)
    held(p, disc, h.screen_point(here), h.screen_point(there), "Extrude taper")


x_taper_drag.wait_ms = 2000


def x_taper_done():
    p = x_panel()
    if not h.check("Extrude still open", p is not None and p.target is not None):
        return
    taper = float(p.options["taper"])
    after_drag("Extrude taper", p, hidden=[p.target])
    h.check("the taper changed", abs(taper - 4.0) > 0.5, taper)
    picture_on("Extrude taper", p, global_of(p.target))
    sd.choose(p.direction, "Symmetric")


x_taper_done.wait_ms = 1500


def x_sym_drag():
    p = x_panel()
    arrow = p.draggers.get("distance") if p is not None else None
    if not h.check("Extrude Symmetric: its arrow", arrow is not None):
        return
    head = a.head_point(arrow)
    held(p, arrow, h.screen_point(head), h.screen_point(head + arrow.direction * 5.0), "Symmetric")


x_sym_drag.wait_ms = 2000


def x_sym_done():
    p = x_panel()
    if not h.check("Extrude still open", p is not None and p.target is not None):
        return
    after_drag("Symmetric", p, hidden=[p.target])
    picture_on("Symmetric", p, global_of(p.target))
    S["x_target"] = p.target
    h.task_button("OK")


def x_ok():
    h.check("Extrude: OK closed it", x_panel() is None and not Gui.Control.activeDialog())
    h.check("Extrude: no picture left after OK", nodes_left() == 0, nodes_left())
    made = S.get("x_target")
    h.check("Extrude: a solid", made is not None and made.Shape.isValid() and made.Shape.Volume > 0)


h.run(
    "live_shapes",
    [
        pp_build,
        pp_open,
        pp_drag_up,
        pp_up_done,
        pp_down_done,
        pp_ok,
        hole_build,
        pp_open,
        hole_drag,
        hole_done,
        hole_undone,
        shell_build,
        shell_open,
        shell_drag,
        shell_done,
        shell_outside,
        shell_outside_done,
        shell_cancelled,
        x_build,
        x_open,
        x_type,
        x_drag,
        x_done,
        x_taper_drag,
        x_taper_done,
        x_sym_drag,
        x_sym_done,
        x_ok,
    ],
)
