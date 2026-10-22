# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft's live picture (Luca, 2026-10-22: "The whole point of being able to drag the angle of
a draft is to see it update in real time"). While the angle handle is dragged (real mouse
input, the button held, the program running between the moves: arrow_input.HeldDrag) the
drafted faces follow the mouse as a picture (sciforge/draft_live.py) and the exact solid is
built only when the mouse rests or is let go. Checked on every case the picture must get
right, each time by putting every point of the picture on the exact drafted solid at the
picture's angle (drafting.draft_shape):

  box, the front face          drag 1 -> 8 deg: the picture shows during the moves, at the
                               dialog's angle; no exact rebuild while moving; let go: the
                               picture goes, the exact solid (the right volume) is shown
  box, its four sides          typed 4: the picture shows at once (corners move with both
                               sides), the exact solid follows
  negative angle               the handle dragged below zero: the faces lean out
  a body moved and turned      the picture sits on the part (global coordinates)
  Two Side, Symmetric          a box from z -5 to 5 about XY: the picture bends at the hinge
  Parting Line, One Side       only the pull side tilts
  pocket walls                 drafted about the top face: the pocket opens up
  a curved wall                an elliptical side (draft_walls)
  edited from the timeline     a draft with a fillet after it: the fillet waits (rolled back)
                               while the angle is dragged and comes back at OK
  past the steepest angle      the picture never stays at an angle that does not work: held
                               at the steepest one, said in the dialog
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import draft_perf_parts as parts
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
S = {}
TOL = 2e-3


def build(name, steps, placement=None):
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
    if placement is not None:
        S["b"].body.Placement = placement
        doc.recompute()
    h.fit()


def origin(role):
    return [o for o in S["b"].body.Origin.OriginFeatures if o.Role == role][0]


def faces_where(pred):
    shape = S["b"].body.Tip.Shape
    return ["Face%d" % i for i, f in enumerate(shape.Faces, 1) if pred(f)]


def plane_facing(x, y, z):
    def pred(f):
        if f.Surface.__class__.__name__ != "Plane":
            return False
        n = f.normalAt(0, 0)
        return (n - V(x, y, z)).Length < 1e-6

    return pred


def sides(f):
    return f.Surface.__class__.__name__ == "Plane" and abs(f.normalAt(0, 0).z) < 1e-6


def open_draft(names, plane=None):
    """The Draft dialog with the pull direction (an origin plane, or a face of the part) and
    `names` picked."""
    from sciforge import draft_ui

    Gui.Selection.clearSelection()
    body = S["b"].body
    tip = body.Tip
    plane = plane if plane is not None else (origin("XY_Plane"), "")
    whole = not plane[1]
    picks = ([plane] if whole else []) + [(tip, n) for n in names]
    panel = draft_ui.DraftPanel(S["doc"], picks=picks, body=body)
    if not whole:
        panel._set_plane(plane)  # a face as the pull direction, as clicking it does
        panel._picks_updated()
    Gui.Control.showDialog(panel)
    S["panel"] = panel


def panel():
    p = sd.draft_panel()
    return p


def picture_matches(label, p=None):
    """Every point of the live picture (faces and edges) lies on the exact drafted solid at the
    picture's angles."""
    import Part

    from sciforge import drafting

    p = p or panel()
    live = getattr(p, "_live", None) if p is not None else None
    if live is None or not live.shown or live.angles is None:
        h.check("%s: the live picture is shown" % label, False, live and live.angles)
        return False
    angle, angle2 = live.angles
    options = dict(p._spec_options())
    options["angle"] = angle
    if angle2 is not None:
        options["angle2"] = angle2
    pic = live.pictures[0]
    spec = drafting.build_spec(p.plane_ref, options, p.base)
    try:
        exact = drafting.draft_shape(p.base.Shape, list(p.names()), spec)
    except Exception as exc:
        h.check("%s: the picture shows an angle that works (%.1f)" % (label, angle), False, exc)
        return False
    faces, lines = pic.points_at(angle, angle2)
    back = pic.placement.inverse() if pic.placement is not None else None
    worst = 0.0
    moved = 0.0
    rest = pic.points_at(0.0, 0.0 if angle2 is not None else None)[0]
    for q, q0 in zip(faces, rest):
        moved = max(moved, (V(*q) - V(*q0)).Length)
    for q in faces + lines:
        v = V(*q)
        if back is not None:
            v = back.multVec(v)
        worst = max(worst, exact.distToShape(Part.Vertex(v))[0])
    ok = worst < TOL and moved > 1e-3
    h.check(
        "%s: the picture lies on the drafted solid at %.1f deg" % (label, angle),
        ok,
        "worst %.5f mm, moved %.4f mm, %d + %d points" % (worst, moved, len(faces), len(lines)),
    )
    return ok


def exact_ok(label, volume=None):
    """The picture is gone and the exact solid at the dialog's angle is shown."""
    from sciforge import drafting

    p = panel()
    if p is None or p.target is None:
        h.check("%s: a preview" % label, False)
        return
    h.check("%s: the picture is gone" % label, not (p._live and p._live.shown))
    h.check("%s: the preview solid is shown again" % label, not p._live_hid)
    h.check("%s: no message" % label, not p.error, p.error)
    options = dict(p._spec_options())
    spec = drafting.build_spec(p.plane_ref, options, p.base)
    want = drafting.draft_shape(p.base.Shape, list(p.names()), spec)
    try:
        want = want.removeSplitter()
    except Exception:
        pass
    got = p.target.Shape
    h.check(
        "%s: the preview is the drafted solid at %.1f deg" % (label, options["angle"]),
        abs(got.Volume - want.Volume) < 1e-6 * max(1.0, want.Volume),
        (got.Volume, want.Volume),
    )
    if volume is not None:
        h.check("%s: its volume" % label, sd.close(got.Volume, volume), (got.Volume, volume))


def drag(to_deg, label, hold_ms=600, moves=30, check=True):
    """Turn the angle disc to `to_deg` with the button held; samples after every move."""
    p = panel()
    if p is None or p.handle is None:
        h.check("%s: the angle handle" % label, False)
        return
    p._timer.stop()
    S["rec"] = rec = {"samples": [], "builds": [], "label": label, "checked": not check}
    old = p._preview

    def preview(*args, **kwargs):
        rec["builds"].append(len(rec["samples"]))
        return old(*args, **kwargs)

    p._preview = preview

    def sample(index):
        q = panel()
        if q is None:
            return
        live = q._live
        shown = bool(live and live.shown)
        rec["samples"].append(
            {
                "i": index,
                "active": q.handle is not None and q.handle.box_active(),
                "shown": shown,
                "angle": float(q.options.get("angle", 0.0)),
                "live": live.angles[0] if shown and live.angles else None,
            }
        )
        angle = float(q.options.get("angle", 0.0))
        if index >= moves // 2 and shown and not rec["checked"] and abs(angle) > 0.5:
            rec["checked"] = True
            picture_matches(label + ", while dragged", q)
            # the check took a while with the mouse still: that is not a pause of the hand
            q._last_motion = time.perf_counter()

    here, there = p.handle.screen_points(to_deg)
    S["drag"] = a.HeldDrag(
        h.screen_point(here),
        h.screen_point(there),
        moves=moves,
        every_ms=16,
        hold_ms=hold_ms,
        sample=sample,
    )
    S["drag"].run()


def dragged(label, expect_sign=None):
    rec = S.get("rec") or {}
    p = panel()
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    samples = rec.get("samples", [])
    moving = [x for x in samples if x["i"] > 0 and x["active"]]
    h.check("%s: the disc was held and moved" % label, len(moving) >= 10, len(moving))
    shown = [x for x in moving if x["shown"]]
    h.check(
        "%s: the picture showed while moving" % label,
        len(shown) >= 0.6 * max(1, len(moving)),
        "%d of %d" % (len(shown), len(moving)),
    )
    h.check(
        "%s: at the dialog's angle" % label,
        all(abs(x["live"] - x["angle"]) < 1e-9 for x in shown),
        [(x["live"], x["angle"]) for x in shown if abs(x["live"] - x["angle"]) >= 1e-9][:4],
    )
    last_move = max([x["i"] for x in moving], default=0)
    early = [i for i in rec.get("builds", []) if i < last_move - 1]
    h.check("%s: no exact rebuild between the moves" % label, not early, early)
    h.check("%s: the picture was checked" % label, rec.get("checked"), rec.get("checked"))
    if expect_sign is not None and p is not None:
        angle = float(p.options.get("angle", 0.0))
        h.check("%s: the angle went %s" % (label, expect_sign), (angle > 0) == (expect_sign == "up"), angle)


# -- box, the front face ----------------------------------------------------------------------------
def box_build():
    Gui.activateWorkbench("SciForgeWorkbench")
    build("LiveBox", parts.BOX)


def box_open():
    open_draft(faces_where(plane_facing(0, -1, 0)))


box_open.wait_ms = 1500


def box_drag():
    drag(8.0, "box front")


def box_dragged():
    dragged("box front", "up")
    p = panel()
    angle = float(p.options["angle"]) if p else 0.0
    import math

    exact_ok("box front", sd.BOX - 40 * 100.0 * math.tan(math.radians(angle)) / 2.0)


box_dragged.wait_ms = 1000


# -- box, its four sides, typed ----------------------------------------------------------------------
def four_sides():
    p = panel()
    if p is None:
        return
    base = p.base  # the part before the step (the body's Tip is the preview now)
    for i, face in enumerate(base.Shape.Faces, 1):
        if sides(face):
            p._add_face(base, "Face%d" % i)
    p._picks_updated()


four_sides.wait_ms = 1500


def four_typed():
    p = panel()
    h.check("four sides picked", p is not None and len(p.names()) == 4, p and p.names())
    if p is None:
        return
    sd.type_into(p.angle.widget, "4")
    # at once (the exact solid follows a moment later): the picture at 4 deg
    picture_matches("four sides, typed 4")


four_typed.wait_ms = 1500


def four_exact():
    exact_ok("four sides", sd.drafted_box(4.0))


# -- negative ------------------------------------------------------------------------------------------
def negative_drag():
    drag(-5.0, "four sides, negative")


def negative_dragged():
    dragged("four sides, negative", "down")
    exact_ok("four sides, negative")
    h.task_button("Cancel")


negative_dragged.wait_ms = 1000


# -- a body moved and turned -----------------------------------------------------------------------
def moved_build():
    place = App.Placement(V(15, -10, 4), App.Rotation(V(0, 0, 1), 30))
    build("LiveMoved", parts.BOX, placement=place)


def moved_open():
    open_draft(faces_where(sides))


moved_open.wait_ms = 1500


def moved_drag():
    drag(6.0, "moved body")


def moved_dragged():
    dragged("moved body", "up")
    exact_ok("moved body")
    h.task_button("Cancel")


moved_dragged.wait_ms = 1000


# -- Two Side, Symmetric, Parting Line ----------------------------------------------------------------
SYM = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"center_rect": [0, 0, 30, 20]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10, "direction": "symmetric"},
]


def sym_build():
    build("LiveTwoSide", SYM)


def sym_open():
    open_draft(faces_where(sides))


sym_open.wait_ms = 1500


def two_side():
    p = panel()
    if p is None:
        return
    sd.choose(p.sides, "Two Side")


two_side.wait_ms = 1500


def two_typed():
    p = panel()
    if p is None:
        return
    sd.type_into(p.angle2.widget, "2")
    picture_matches("Two Side, angle 2 typed")


two_typed.wait_ms = 1500


def two_drag():
    drag(5.0, "Two Side")


def two_dragged():
    dragged("Two Side", "up")
    exact_ok("Two Side")


two_dragged.wait_ms = 1000


def symmetric():
    p = panel()
    if p is None:
        return
    sd.choose(p.sides, "Symmetric")


symmetric.wait_ms = 1500


def sym_typed():
    p = panel()
    if p is None:
        return
    sd.type_into(p.angle.widget, "3")
    picture_matches("Symmetric, typed 3")


sym_typed.wait_ms = 1500


def sym_exact():
    exact_ok("Symmetric")


def parting():
    p = panel()
    if p is None:
        return
    sd.choose(p.sides, "One Side")
    sd.choose(p.type, "Parting Line")
    p._set_parting_plane((origin("XY_Plane"), ""))
    p._picks_updated()


parting.wait_ms = 1500


def parting_typed():
    p = panel()
    if p is None:
        return
    h.check("Parting Line with the XY plane", p.type.currentData() == "parting" and p.parting)
    sd.type_into(p.angle.widget, "4")
    picture_matches("Parting Line One Side, typed 4")


parting_typed.wait_ms = 1500


def parting_exact():
    exact_ok("Parting Line One Side")
    h.task_button("Cancel")


# -- pocket walls --------------------------------------------------------------------------------------
POCKET = parts.BOX + [
    {"op": "sketch", "id": "s2", "plane": "XY", "offset": 10, "geometry": [{"rect": [10, 8, 30, 22]}]},
    {"op": "extrude", "id": "e2", "profile": "s2", "distance": 6, "flip": True, "operation": "cut"},
]


def pocket_build():
    build("LivePocket", POCKET)


def pocket_open():
    walls = faces_where(
        lambda f: f.Surface.__class__.__name__ == "Plane"
        and abs(f.normalAt(0, 0).z) < 1e-6
        and f.BoundBox.XMin > 9
        and f.BoundBox.XMax < 31
        and f.BoundBox.YMin > 7
        and f.BoundBox.YMax < 23
    )
    top = faces_where(plane_facing(0, 0, 1))
    top = [n for n in top if abs(S["b"].body.Tip.Shape.getElement(n).BoundBox.ZMax - 10) < 1e-6]
    open_draft(walls, plane=(S["b"].body.Tip, top[0]))


pocket_open.wait_ms = 1500


def pocket_drag():
    drag(6.0, "pocket walls")


def pocket_dragged():
    dragged("pocket walls")
    exact_ok("pocket walls")
    h.task_button("Cancel")


pocket_dragged.wait_ms = 1000


# -- a curved wall ------------------------------------------------------------------------------------
ELLIPSE = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"ellipse": [0, 0, 12.0, 6.0]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10.0},
]


def curved_build():
    build("LiveCurved", ELLIPSE)


def curved_open():
    open_draft(faces_where(lambda f: f.Surface.__class__.__name__ != "Plane"))


curved_open.wait_ms = 2500


def curved_drag():
    drag(4.0, "elliptical wall")


def curved_dragged():
    dragged("elliptical wall", "up")
    exact_ok("elliptical wall")
    h.task_button("Cancel")


curved_dragged.wait_ms = 2000


# -- edited from the timeline ---------------------------------------------------------------------------
EDITED = parts.BOX + [
    {"op": "sf_draft", "id": "d1", "plane": "XY", "faces": {"normal": [0, -1, 0], "count": 1}, "angle": 3},
    {
        "op": "fillet",
        "id": "f1",
        "edges": {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "y", "value": "max"}, "count": 2},
        "radius": 2,
    },
]


def edit_build():
    build("LiveEdit", EDITED)
    S["fillet"] = S["b"].objects["f1"]


def edit_open():
    titles = sd.timeline_titles()
    draft = [t for t in titles if t.startswith("Draft")]
    h.check("a Draft step in the timeline", bool(draft), titles)
    if draft:
        sd.timeline_double_click(draft[0])


edit_open.wait_ms = 2000


def edit_drag():
    p = panel()
    h.check("editing the Draft", p is not None and p.editing)
    drag(7.0, "edited from the timeline")


def edit_dragged():
    dragged("edited from the timeline", "up")
    exact_ok("edited from the timeline")
    from sciforge import preview

    h.check("the fillet after it waits (rolled back)", preview.holding(S["doc"]))
    h.task_button("OK")


edit_dragged.wait_ms = 1000


def edit_done():
    h.check("Draft closed", not Gui.Control.activeDialog())
    fillet = S["fillet"]
    h.check("the fillet is back, sound", "Invalid" not in fillet.State and fillet.Shape.isValid())
    h.check("the body ends with the fillet", S["b"].body.Tip is fillet)


# -- past the steepest angle -----------------------------------------------------------------------------
def steep_build():
    build("LiveSteep", parts.PART)


steep_build.wait_ms = 1500


def steep_open():
    open_draft(parts.outer_sides(S["b"].body.Tip.Shape))


steep_open.wait_ms = 3000


def steep_drag():
    # past what fits, not known yet: the picture follows (nothing tells it apart before the
    # exact solid is tried) until the mouse rests; the limit is looked for then
    drag(20.0, "past the steepest angle", hold_ms=1500, check=False)


def steep_dragged():
    p = panel()
    rec = S.get("rec") or {}
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    angle = float(p.options.get("angle", 0.0)) if p else 0.0
    h.check("held at the steepest angle that fits (7-8 deg)", 7.0 <= angle < 8.0, angle)
    h.check("said so", p is not None and p.limits.note.startswith("Largest"), p and p.limits.note)
    h.check("the handle is there too", p is not None and abs(p.handle.angle() - angle) < 0.05)
    h.check("the picture is gone", p is not None and not (p._live and p._live.shown))
    exact_ok("held at the steepest angle")
    h.check("moved during the drag", len(rec.get("samples", [])) > 10)
    # dragged past it again: the picture stops where the angles are known not to work
    drag(25.0, "past the steepest angle again", hold_ms=300, check=False)


steep_dragged.wait_ms = 2000


def steep_again():
    rec = S.get("rec") or {}
    p = panel()
    limit = float(p.options.get("angle", 0.0)) if p else 0.0
    wall = None
    if p is not None:
        found = p.limits.cache.get(p.limit_key("angle"), "hi+")
        wall = found[2] if found else None
    samples = rec.get("samples", [])
    shown = [x["live"] for x in samples if x["shown"]]
    angles = [x["angle"] for x in samples]
    h.check(
        "dragged past it again: the dialog and the picture stay before the angles known not "
        "to work",
        bool(angles) and wall is not None and max(angles + shown) < wall,
        (max(angles) if angles else None, max(shown) if shown else None, limit, wall),
    )
    h.check("held at the steepest angle again", 7.0 <= limit < 8.0, limit)
    if p is not None:
        try:
            del p._preview
        except Exception:
            pass
    h.task_button("OK")


steep_again.wait_ms = 2000


def steep_done():
    h.check("OK at the steepest angle", not Gui.Control.activeDialog())
    tip = S["b"].body.Tip
    h.check("the part is sound", tip.Shape.isValid() and "Invalid" not in tip.State)


h.run(
    "draft_live",
    [
        box_build,
        box_open,
        box_drag,
        box_dragged,
        four_sides,
        four_typed,
        four_exact,
        negative_drag,
        negative_dragged,
        moved_build,
        moved_open,
        moved_drag,
        moved_dragged,
        sym_build,
        sym_open,
        two_side,
        two_typed,
        two_drag,
        two_dragged,
        symmetric,
        sym_typed,
        sym_exact,
        parting,
        parting_typed,
        parting_exact,
        pocket_build,
        pocket_open,
        pocket_drag,
        pocket_dragged,
        curved_build,
        curved_open,
        curved_drag,
        curved_dragged,
        edit_build,
        edit_open,
        edit_drag,
        edit_dragged,
        edit_done,
        steep_build,
        steep_open,
        steep_drag,
        steep_dragged,
        steep_again,
        steep_done,
    ],
)
