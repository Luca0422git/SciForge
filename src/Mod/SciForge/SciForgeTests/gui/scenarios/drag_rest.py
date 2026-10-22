# SPDX-License-Identifier: LGPL-2.1-or-later
"""When a dragged handle's dialog rebuilds, on a heavy part (draft_perf_parts.PART, 179
faces): the review findings of the second round of "Draft in real time"
(docs/sciforge/sessions/2026-10-22-draft-live.md, "Review fixes"), with real mouse input:

  2-F2 Press Pull: the first moves of a drag do not rebuild (the cost of a rebuild is not
       known yet: it took 1.3 s and froze the arrow as it was grabbed)
  2-F6 Press Pull: letting go does not rebuild the value of the last drag step a second time
  2-F5 Press Pull: let go right after moving, the rebuild starts at once (not after the rest)
  2-F3 Draft: a drag with short stops (0.32 s, button held) rebuilds nothing until it rests
       longer or is let go (each stop started a 0.25-0.3 s rebuild that froze the next moves)
  2-F1 Draft: past the steepest angle, the background search builds nothing while the mouse
       moves, and dragging back below what it found to fail cuts it off
"""

import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import draft_perf_parts as parts
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
S = {}


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


class Probe:
    """When the dialog rebuilt (start, end, value), when the mouse moved, and when the limit
    search built a trial."""

    def __init__(self, panel, value):
        self.p = panel
        self.value = value
        self.rebuilds = []
        self.moves = []
        self.trials = []
        self.press = self.release = None
        old = panel._recompute

        def recompute(*args, **kw):
            t0 = time.perf_counter()
            try:
                return old(*args, **kw)
            finally:
                try:
                    v = round(float(value()), 2)
                except Exception:
                    v = None
                self.rebuilds.append((t0, time.perf_counter(), v))

        panel._recompute = recompute
        if hasattr(panel, "limit_works"):
            works_of = panel.limit_works

            def limit_works(what):
                works = works_of(what)

                def timed(v):
                    self.trials.append(time.perf_counter())
                    return works(v)

                return timed

            panel.limit_works = limit_works

    def stop(self):
        for name in ("_recompute", "limit_works"):
            try:
                delattr(self.p, name)
            except Exception:
                pass


class Drive:
    """Press at `start`, then each (point, delay_ms) is one mouse move `delay_ms` after the
    last (the program runs in between), hold `hold_ms`, release. Button held throughout."""

    def __init__(self, start, plan, hold_ms, probe):
        self.start, self.plan, self.hold_ms, self.probe = start, plan, hold_ms, probe
        self.i = 0

    def run(self):
        h.BUSY.add(self)
        h.move(self.start)
        self.widget = a.on_top(self.start)
        QtTest.QTest.mousePress(
            self.widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, self._local(self.start)
        )
        QtWidgets.QApplication.processEvents()
        self.probe.press = time.perf_counter()
        QtCore.QTimer.singleShot(int(self.plan[0][1]) if self.plan else 0, self._next)

    def _local(self, pos):
        gl = h.gl_widget()
        if self.widget is gl:
            return QtCore.QPoint(int(pos.x()), int(pos.y()))
        return self.widget.mapFromGlobal(gl.mapToGlobal(QtCore.QPoint(int(pos.x()), int(pos.y()))))

    def _next(self):
        try:
            pos = self.plan[self.i][0]
            local = QtCore.QPointF(self._local(pos))
            event = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove,
                local,
                QtCore.QPointF(self.widget.mapToGlobal(local.toPoint())),
                QtCore.Qt.NoButton,
                QtCore.Qt.LeftButton,
                QtCore.Qt.NoModifier,
            )
            QtWidgets.QApplication.sendEvent(self.widget, event)
            self.probe.moves.append(time.perf_counter())
            self.i += 1
            if self.i < len(self.plan):
                QtCore.QTimer.singleShot(int(self.plan[self.i][1]), self._next)
            else:
                QtCore.QTimer.singleShot(self.hold_ms, self._release)
        except Exception as exc:
            print("[SciForge] drag_rest drive: %s" % exc, flush=True)
            self._release()

    def _release(self):
        try:
            end = self.plan[-1][0] if self.plan else self.start
            QtTest.QTest.mouseRelease(
                self.widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, self._local(end)
            )
            self.probe.release = time.perf_counter()
            QtWidgets.QApplication.processEvents()
        finally:
            h.BUSY.discard(self)


def plan_of(point_of, segments, every_ms=16):
    """segments: [(from, to, moves, pause before the first move, ms)] -> [(pixel, delay)]."""
    plan = []
    for v0, v1, n, pause in segments:
        for i in range(1, n + 1):
            v = v0 + (v1 - v0) * i / float(n)
            plan.append((h.screen_point(point_of(v)), pause if i == 1 and pause else every_ms))
    return plan


def start_drag(key, panel, start_point, plan, hold_ms, value):
    try:
        panel._timer.stop()
    except Exception:
        pass
    probe = Probe(panel, value)
    S[key] = probe
    Drive(start_point, plan, hold_ms, probe).run()


def ms(seconds):
    return round(seconds * 1000.0)


# -- Press Pull -------------------------------------------------------------------------------
def pp_panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def pp_open():
    build("RestPP", parts.PART)
    face = None
    for i, f in enumerate(tip().Shape.Faces, 1):
        if (
            f.Surface.__class__.__name__ == "Plane"
            and abs(f.normalAt(0, 0).y + 1) < 1e-6
            and f.BoundBox.XLength > 20
        ):
            face = "Face%d" % i
            break
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(S["doc"].Name, tip().Name, face)
    h.ribbon("Press Pull")


pp_open.wait_ms = 5000


def pp_arrow(p):
    d = p.dragger
    place = d.root.getChild(0)
    origin = place.translation.getValue().getValue()
    axis = place.rotation.getValue().multVec(d.coin.SbVec3f(1, 0, 0)).getValue()
    head = V(*origin) + V(*axis) * (d.distance() + d.size * 0.9)
    return head, V(*axis), d


def pp_drag(key, segments, hold_ms):
    def step():
        p = pp_panel()
        if p is None or p.dragger is None:
            h.check("%s: Press Pull arrow" % key, False)
            return
        head, axis, d = pp_arrow(p)
        v0 = segments[0][0]
        plan = plan_of(lambda v: head + axis * (v - v0), segments)
        start_drag(key, p, h.screen_point(head), plan, hold_ms, lambda: p.field.value())

    step.__name__ = "pp_drag_" + key
    step.wait_ms = 3500
    return step


def pp_steady_check():
    probe = S["pp steady"]
    probe.stop()
    last = probe.moves[-1]
    during = [(ms(s - probe.press), ms(e - s)) for s, e, _v in probe.rebuilds if s <= last]
    h.check(
        "2-F2: Press Pull on the part: no rebuild while the arrow is dragged", not during, during
    )
    after = [(ms(s - probe.release), ms(e - s), v) for s, e, v in probe.rebuilds if s > last]
    h.check("2-F2: the rebuild comes once the arrow rests", bool(after), after)
    final = after[-1][2] if after else None
    again = [r for r in after if r[0] > 0 and r[2] == final]
    held = [r for r in after if r[0] <= 0]
    h.check(
        "2-F6: let go, the value built while it rested is not built again",
        held and not again,
        {"while held": held, "after the release": again},
    )


def pp_quick_check():
    probe = S["pp quick"]
    probe.stop()
    after = [
        (ms(s - probe.release), ms(e - s), v) for s, e, v in probe.rebuilds if s > probe.moves[-1]
    ]
    first = after[0][0] if after else None
    h.check(
        "2-F5: let go right after moving, the rebuild starts at once (not after the rest)",
        first is not None and first < 150,
        after,
    )


# -- Draft ------------------------------------------------------------------------------------
def draft_open():
    from sciforge import draft_ui

    build("RestDraft", parts.PART)
    body = S["b"].body
    xy = [o for o in body.Origin.OriginFeatures if o.Role == "XY_Plane"][0]
    picks = [(xy, "")] + [(tip(), n) for n in parts.outer_sides(tip().Shape)]
    Gui.Selection.clearSelection()
    Gui.Control.showDialog(draft_ui.DraftPanel(S["doc"], picks=picks, body=body))


draft_open.wait_ms = 5000


def draft_drag(key, segments, hold_ms, wait_ms):
    def step():
        p = sd.draft_panel()
        if p is None or p.handle is None:
            h.check("%s: Draft disc" % key, False)
            return
        here = h.screen_point(p.handle.point_at(p.handle.angle()))
        plan = plan_of(p.handle.point_at, segments)
        start_drag(key, p, here, plan, hold_ms, lambda: p.options.get("angle", 0.0))

    step.__name__ = "draft_drag_" + key.replace(" ", "_")
    step.wait_ms = wait_ms
    return step


def draft_settle_check():
    probe = S["draft first"]
    probe.stop()
    costs = [e - s for s, e, _v in probe.rebuilds]
    S["draft cost"] = max(costs) if costs else None
    h.check("Draft: the first drag rebuilt once it rested", bool(costs), costs)


def draft_hesitant_check():
    probe = S["draft hesitant"]
    probe.stop()
    last = probe.moves[-1]
    during = [(ms(s - probe.press), ms(e - s), v) for s, e, v in probe.rebuilds if s <= last]
    cost = S.get("draft cost")
    if cost is not None and cost * 2.0 * 1000.0 < 340:
        # a quicker machine: a rebuild of under 0.17 s may run in a 0.32 s stop (as designed)
        h.check("2-F3: (rebuild quick enough to run in a short stop)", True, cost)
        return
    h.check(
        "2-F3: Draft on the part, stops of 0.32 s with the button held: nothing rebuilt",
        not during,
        {"rebuilds": during, "last rebuild cost ms": ms(cost or 0.0)},
    )
    after = [r for r in probe.rebuilds if r[0] > last]
    h.check("2-F3: rebuilt once let go", bool(after))


def draft_back_check():
    probe = S["draft back"]
    probe.stop()
    p = sd.draft_panel()
    held_moves = [m for m in probe.moves]
    busy = []
    for t in probe.trials:
        near = [m for m in held_moves if 0.0 <= t - m < 0.19]
        if near and t < (probe.release or 1e18):
            busy.append(ms(t - probe.press))
    h.check(
        "2-F1: no trial build of the limit search right after a mouse move",
        not busy,
        {"trials (ms after the press)": [ms(t - probe.press) for t in probe.trials], "busy": busy},
    )
    h.check(
        "2-F1: dragged back below the limit, the angle is kept, no search left",
        abs(float(p.options.get("angle", 0.0)) - S["back to"]) < 0.11 and not p.limit_searching(),
        (p.options.get("angle"), p.limit_searching(), p.limits.note),
    )
    after = [
        (ms(s - probe.release), ms(e - s), v) for s, e, v in probe.rebuilds if s > probe.release
    ]
    h.check(
        "2-F1: its exact preview comes soon after the release",
        after and after[0][0] < 1500 and abs(after[-1][2] - S["back to"]) < 0.11,
        after,
    )
    h.task_button("Cancel")


def start():
    Gui.activateWorkbench("SciForgeWorkbench")


def set_back(value):
    def step():
        S["back to"] = value

    step.__name__ = "set_back"
    return step


h.run(
    "drag_rest",
    [
        start,
        pp_open,
        pp_drag("pp steady", [(0, 6, 40, 0)], 700),
        pp_steady_check,
        pp_drag("pp quick", [(6, 3, 20, 0)], 30),
        pp_quick_check,
        lambda: h.task_button("Cancel"),
        draft_open,
        draft_drag("draft first", [(0, 6, 30, 0)], 900, 3000),
        draft_settle_check,
        draft_drag(
            "draft hesitant",
            [(6, 5.4, 12, 0), (5.4, 4.8, 12, 320), (4.8, 4.2, 12, 320), (4.2, 3.6, 12, 320)],
            50,
            3000,
        ),
        draft_hesitant_check,
        set_back(3.9),
        draft_drag("draft back", [(3.6, 20, 20, 0), (20, 3.9, 8, 1200)], 300, 9000),
        draft_back_check,
        close_all,
    ],
)
