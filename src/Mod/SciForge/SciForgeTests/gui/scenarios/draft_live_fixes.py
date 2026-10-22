# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft in real time, the review findings of the first round (docs/sciforge/sessions/
2026-10-22-draft-live.md, "Review fixes"), each with the input that showed it:

  F1  an angle past the limit typed and Enter / OK pressed at once: one press takes the
      steepest angle that fits and closes the dialog (it needed two)
  F2  a background limit search is cut off when a smaller angle is typed: the exact preview of
      that angle comes at the normal pace (it waited ~3.5 s for the stale search)
  F3  a wall under a sloping top that is not drafted (a wedge): the live picture lies on the
      exact drafted solid (its outline moved half as far as its face)
  F4  picks refused whatever the angle (a round face in the tangent chain): no live picture,
      the refusal stays in sight
  F5  the steepest angle that fits on a part of 180 faces is the same every time (the search
      runs to its end), and OK finds the same one
  F6  a body sketched on YZ: the limit is the one of the same box sketched on XY (71.5 deg);
      60 deg is accepted (it was held at a false 36.8 deg)
  2-F7 the disc held at a limit inside its snap-to-0 zone (hole walls, 1.5 deg) and dragged
      on: it stays at the limit (it jumped between 1.5 and 0 with an error)
"""

import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import draft_perf_parts as parts
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
S = {}

WEDGE = [
    {
        "op": "sketch",
        "id": "s1",
        "plane": "YZ",
        "geometry": [{"polyline": [[0, 0], [30, 0], [30, 6], [0, 10]]}],
    },
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 40},
]
YZBOX = [
    {"op": "sketch", "id": "s1", "plane": "YZ", "geometry": [{"rect": [0, 0, 30, 10]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 40},
]
FILLETED = parts.BOX + [
    {
        "op": "fillet",
        "id": "f1",
        "edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4},
        "radius": 2,
    },
]


def close_all():
    try:
        if Gui.Control.activeDialog():
            h.task_button("Cancel")
    except Exception:
        pass
    for name in list(App.listDocuments()):
        try:
            App.closeDocument(name)
        except Exception:
            pass


def build(name, steps):
    close_all()
    doc = App.newDocument(name)
    S["doc"] = doc
    S["b"] = parts.build(doc, steps)
    h.fit()


def tip():
    return S["b"].body.Tip


def front_faces():
    return [
        "Face%d" % i
        for i, f in enumerate(tip().Shape.Faces, 1)
        if f.Surface.__class__.__name__ == "Plane"
        and (f.normalAt(0, 0) - V(0, -1, 0)).Length < 1e-6
    ]


def hole_walls():
    names = []
    for i, f in enumerate(tip().Shape.Faces, 1):
        if (
            f.Surface.__class__.__name__ == "Cylinder"
            and abs(f.Surface.Radius - 3.0) < 1e-6
            and f.BoundBox.ZLength > 25
        ):
            names.append("Face%d" % i)
    return names


def open_draft(names):
    from sciforge import draft_ui

    Gui.Selection.clearSelection()
    body = S["b"].body
    xy = [o for o in body.Origin.OriginFeatures if o.Role == "XY_Plane"][0]
    picks = [(xy, "")] + [(tip(), n) for n in names]
    Gui.Control.showDialog(draft_ui.DraftPanel(S["doc"], picks=picks, body=body))


def panel():
    return sd.draft_panel()


def kept_angle():
    obj = tip()
    return round(float(obj.Angle), 2) if hasattr(obj, "Angle") else None


def opener(name, steps, names_fn, wait=3000):
    def step():
        build(name, steps)
        open_draft(names_fn())

    step.__name__ = "open_" + name
    step.wait_ms = wait
    return step


def cancel():
    if Gui.Control.activeDialog():
        h.task_button("Cancel")


# -- F1: typed past the limit, Enter / OK at once ----------------------------------------------
def f1_enter():
    p = panel()
    sd.type_into(p.angle.widget, "80")
    QtTest.QTest.keyClick(p.angle.widget, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()
    S["f1 closed"] = not Gui.Control.activeDialog()


f1_enter.wait_ms = 3000


def f1_check():
    h.check(
        "F1: box, 80 typed and Enter: one press closes the dialog",
        S.get("f1 closed") and not Gui.Control.activeDialog(),
        S.get("f1 closed"),
    )
    h.check("F1: the draft kept is held at the limit (71.5)", kept_angle() == 71.5, kept_angle())
    cancel()


def f1_part_ok():
    p = panel()
    sd.type_into(p.angle.widget, "15")
    t = time.perf_counter()
    h.task_button("OK")
    S["f1 part ok ms"] = round((time.perf_counter() - t) * 1000.0)
    S["f1 part closed"] = not Gui.Control.activeDialog()


f1_part_ok.wait_ms = 3000


def f1_part_check():
    S["ok angle"] = kept_angle()
    h.check(
        "F1: part, 15 typed and OK: one press closes the dialog at the steepest angle",
        S.get("f1 part closed") and S["ok angle"] is not None and 6.0 < S["ok angle"] < 10.0,
        (S.get("f1 part closed"), S["ok angle"], S.get("f1 part ok ms")),
    )
    h.check("F1: the solid kept is sound", tip().Shape.isValid())
    cancel()


# -- F5: the same limit every time --------------------------------------------------------------
def f5_typed():
    sd.type_into(panel().angle.widget, "15")


f5_typed.wait_ms = 12000  # the background search (the harness waits for it too)


def f5_record(key):
    def step():
        p = panel()
        S[key] = (round(float(p.options.get("angle", 0.0)), 2), p.limits.note, p.error)
        cancel()

    step.__name__ = "f5_record_" + key
    return step


def f5_check():
    one, two = S.get("f5 first"), S.get("f5 second")
    h.check(
        "F5: the steepest angle is the same in two dialogs",
        one is not None and two is not None and one[0] == two[0] and not one[2],
        (one, two),
    )
    h.check(
        "F5: OK at once finds the same steepest angle",
        one is not None and S.get("ok angle") == one[0],
        (one, S.get("ok angle")),
    )
    h.check(
        "F5: the note names it",
        one is not None and one[1] == "15° does not fit: limited to %.1f°" % one[0],
        one,
    )


# -- F2: a smaller angle typed during the search ------------------------------------------------
def f2_typed():
    p = panel()
    S["f2"] = {}
    sd.type_into(p.angle.widget, "15")
    began = time.perf_counter()
    h.BUSY.add("f2")

    def watch():
        try:
            q = panel()
            if q is None:
                h.BUSY.discard("f2")
                return
            if q.limit_searching() and "typed" not in S["f2"]:
                S["f2"]["typed"] = time.perf_counter()
                sd.type_into(q.angle.widget, "3")
                S["f2"]["searching after"] = q.limit_searching()
                orig = q.show_preview

                def show(on):
                    if on and "exact" not in S["f2"]:
                        S["f2"]["exact"] = (
                            round((time.perf_counter() - S["f2"]["typed"]) * 1000.0),
                            q.options.get("angle"),
                        )
                        h.BUSY.discard("f2")
                    return orig(on)

                q.show_preview = show
                return
            if time.perf_counter() - began < 6.0:
                QtCore.QTimer.singleShot(15, watch)
            else:
                h.BUSY.discard("f2")
        except Exception as exc:
            S["f2"]["error"] = str(exc)
            h.BUSY.discard("f2")

    QtCore.QTimer.singleShot(15, watch)


f2_typed.wait_ms = 2000


def f2_check():
    info = S.get("f2", {})
    p = panel()
    try:
        del p.show_preview
    except Exception:
        pass
    h.check("F2: the search started", "typed" in info, info)
    h.check("F2: typing 3 cuts the search off", info.get("searching after") is False, info)
    exact = info.get("exact")
    # a normal exact rebuild of this part takes ~0.4 s after the 0.2 s rest; the stale search
    # held it ~3.5 s (a loaded machine is allowed for)
    h.check(
        "F2: the exact preview of 3 deg comes at the normal pace",
        exact is not None and exact[1] == 3.0 and exact[0] < 2000,
        info,
    )
    h.check("F2: 3 deg kept, no note", p.options.get("angle") == 3.0 and not p.limits.note)
    cancel()


# -- F3: the wedge's sloping top -----------------------------------------------------------------
def f3_typed(angle):
    def step():
        import Part

        from sciforge import drafting

        p = panel()
        sd.type_into(p.angle.widget, "%g" % angle)
        live = p._live
        if live is None or not live.pictures:
            h.check("F3: picture made at %g deg" % angle, False)
            return
        pic = live.pictures[0]
        faces, lines = pic.points_at(float(angle))
        options = dict(p._spec_options())
        options["angle"] = float(angle)
        exact = drafting.draft_shape(
            p.base.Shape, list(p.names()), drafting.build_spec(p.plane_ref, options, p.base)
        )

        def worst(points):
            out = 0.0
            for q in points:
                v = V(*q)
                if pic.placement is not None:
                    v = pic.placement.inverse().multVec(v)
                out = max(out, exact.distToShape(Part.Vertex(v))[0])
            return round(out, 4)

        info = {"faces": worst(faces), "lines": worst(lines), "points": len(faces)}
        h.check(
            "F3: wedge at %g deg: the picture lies on the exact solid" % angle,
            info["faces"] < 2e-3 and info["lines"] < 2e-3,
            info,
        )

    step.__name__ = "f3_typed_%g" % angle
    step.wait_ms = 2500
    return step


# -- F4: refused picks -------------------------------------------------------------------------
def f4_typed():
    p = panel()
    S["f4 before"] = p.error
    sd.type_into(p.angle.widget, "5")
    S["f4 live"] = bool(p._live is not None and p._live.shown)
    S["f4 error"] = p.error


f4_typed.wait_ms = 2500


def f4_check():
    p = panel()
    h.check(
        "F4: picks refused whatever the angle: no live picture",
        S.get("f4 live") is False,
        (S.get("f4 before"), S.get("f4 live")),
    )
    h.check(
        "F4: the refusal stays in sight",
        bool(S.get("f4 error")) and "Only faces that run along" in (p.error or ""),
        S.get("f4 error"),
    )
    h.check("F4: still no picture after the rest", not (p._live is not None and p._live.shown))
    cancel()


# -- F6: a body sketched on YZ --------------------------------------------------------------------
def f6_typed(text):
    def step():
        sd.type_into(panel().angle.widget, text)

    step.__name__ = "f6_typed_" + text
    step.wait_ms = 4000
    return step


def f6_check_60():
    p = panel()
    h.check(
        "F6: YZ body, 60 deg is accepted",
        p.options.get("angle") == 60.0 and not p.limits.note and not p.error,
        (p.options.get("angle"), p.limits.note, p.error),
    )
    h.check("F6: the preview at 60 deg", kept_angle() == 60.0, kept_angle())


def f6_check_80():
    p = panel()
    h.check(
        "F6: YZ body, 80 deg is held at 71.5 (as the same box sketched on XY)",
        p.options.get("angle") == 71.5,
        (p.options.get("angle"), p.limits.note),
    )
    cancel()


# -- 2-F7: a held limit inside the disc's snap-to-0 zone -------------------------------------------
def holes_first_drag():
    p = panel()
    if p is None or p.handle is None:
        h.check("2-F7: the angle disc", False)
        return
    here, there = p.handle.screen_points(5.0)
    d = a.HeldDrag(h.screen_point(here), h.screen_point(there), moves=25, every_ms=16, hold_ms=300)
    d.run()


holes_first_drag.wait_ms = 12000


def holes_second_drag():
    p = panel()
    S["f7 limit"] = float(p.options.get("angle", 0.0))
    S["f7 vals"] = []
    if p.handle is None:
        h.check("2-F7: the angle disc", False)
        return
    # from the disc held at the limit, outward and on (5 -> 3 deg, as a hand does)
    here = p.handle.point_at(p.handle.angle())
    _h, there = p.handle.screen_points(4.0)

    def sample(_i):
        q = panel()
        if q is not None:
            S["f7 vals"].append((float(q.options.get("angle", 0.0)), q.error))

    d = a.HeldDrag(
        h.screen_point(here),
        h.screen_point(there),
        moves=30,
        every_ms=16,
        hold_ms=300,
        sample=sample,
    )
    d.run()


holes_second_drag.wait_ms = 6000


def holes_check():
    p = panel()
    limit = S.get("f7 limit")
    vals = S.get("f7 vals", [])
    zeros = [v for v in vals if abs(v[0]) < 1e-9 or (v[1] and "must not be 0" in v[1])]
    h.check(
        "2-F7: the hole walls are held at a small limit",
        limit is not None and 0 < limit < 3.0,
        limit,
    )
    h.check("2-F7: dragged on, the disc never jumps to 0", vals and not zeros, vals[:20])
    h.check(
        "2-F7: it stays at the limit",
        abs(float(p.options.get("angle", 0.0)) - limit) < 1e-9 and not p.error,
        (p.options.get("angle"), p.error, p.limits.note),
    )
    cancel()


def start():
    Gui.activateWorkbench("SciForgeWorkbench")


h.run(
    "draft_live_fixes",
    [
        start,
        opener("EnterBox", parts.BOX, front_faces, 2500),
        f1_enter,
        f1_check,
        opener("YZBox", YZBOX, front_faces, 2500),
        f6_typed("60"),
        f6_check_60,
        f6_typed("80"),
        f6_check_80,
        opener("Wedge", WEDGE, front_faces, 2500),
        f3_typed(15),
        f3_typed(5),
        cancel,
        opener("Refused", FILLETED, front_faces, 2500),
        f4_typed,
        f4_check,
        opener("OkPart", parts.PART, lambda: parts.outer_sides(tip().Shape), 5000),
        f1_part_ok,
        f1_part_check,
        opener("Steep1", parts.PART, lambda: parts.outer_sides(tip().Shape), 5000),
        f5_typed,
        f5_record("f5 first"),
        opener("Steep2", parts.PART, lambda: parts.outer_sides(tip().Shape), 5000),
        f5_typed,
        f5_record("f5 second"),
        f5_check,
        opener("Stale", parts.PART, lambda: parts.outer_sides(tip().Shape), 5000),
        f2_typed,
        f2_check,
        opener("Holes", parts.PART, hole_walls, 6000),
        holes_first_drag,
        holes_second_drag,
        holes_check,
        close_all,
    ],
)
