# SPDX-License-Identifier: LGPL-2.1-or-later
"""How the Draft angle handle feels while it is dragged (Luca, 2026-10-22: "The whole point of
being able to drag the angle of a draft is to see it update in real time ... the angle dragger
doesn't even update either: it waits behind for the model to update"). Real mouse input: the
button goes down on the angle disc, the mouse moves every 16 ms (a 60 Hz mouse) with the
program running in between (arrow_input.HeldDrag), stays still with the button down (a
pause), and lets go.

Measured on the simple box (40 x 30 x 10, the front face) and on a realistic part
(draft_perf_parts.PART: ~180 faces, its 8 outer side walls), per mouse move:
  value box   the move until the dialog took the new angle (the box shows it)
  frame       the move until the 3D view drew a new frame (the disc at its new place)
  live        the move until the live preview showed the new angle (none before 2026-10-22)
  blocked     the longest time the program did not run during the moving (a frozen handle)
and once per drag:
  exact       the mouse stopped until the exact drafted solid was shown at the final angle
A third drag on the part goes past the steepest angle that fits (the limit search).

The report goes to perf-draft-report.json / .md next to the other output; the speed guard
(perf_guard.py, baseline SciForgeTests/gui/perf_baseline.json) compares each number. The
sandbox draws with software OpenGL (slow frames): the frame column is about the machine, the
others are SciForge's own time. The checks also prove the drags still make the same solid.

Run alone: tools/sciforge/run_tests.sh --scenario perf_draft
"""
import cProfile
import io
import json
import os
import pstats
import statistics
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import draft_perf_parts as parts
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import perf_guard

V = App.Vector
S = {}
RESULTS = []
MOVE_MS = 16  # a 60 Hz mouse


def out_dir():
    return os.environ.get("SCIFORGE_SMOKE_OUT") or os.path.dirname(os.path.abspath(__file__))


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
    S["b"] = parts.build(doc, steps)
    S["doc"] = doc
    h.fit()


def xy_plane():
    return [o for o in S["b"].body.Origin.OriginFeatures if o.Role == "XY_Plane"][0]


def open_draft(names):
    """The Draft dialog with the XY plane and `names` picked (as start() does with a selection)."""
    from sciforge import draft_ui

    Gui.Selection.clearSelection()
    body = S["b"].body
    tip = body.Tip
    S["base_shape"] = tip.Shape
    S["names"] = list(names)
    picks = [(xy_plane(), "")] + [(tip, n) for n in names]
    panel = draft_ui.DraftPanel(S["doc"], picks=picks, body=body)
    Gui.Control.showDialog(panel)
    S["panel"] = panel


def panel():
    p = S.get("panel")
    return None if p is None or p._closed else p


# -- the probe ----------------------------------------------------------------------------------
class Probe:
    """Time stamps of what happens during one drag: mouse moves, the dialog taking the angle,
    frames drawn, live preview updates, exact rebuilds, and a 2 ms heartbeat (gaps in it are
    times the program did not run)."""

    def __init__(self, p):
        self.p = p
        self.moves = []  # (time, disc angle right after the move)
        self.taken = []  # (time, angle) the dialog took
        self.frames = []
        self.live = []  # (time, angle) shown by the live preview
        self.exact = []  # (end time, angle, error) of each exact rebuild
        self.beats = []
        self.released = None
        self.handle = p.handle
        old_drag, old_release = self.handle.on_drag, self.handle.on_release
        self.saved = (old_drag, old_release)

        def drag(value, *args):
            old_drag(value, *args)
            self.taken.append((time.perf_counter(), float(p.options.get("angle", 0.0))))

        def release(value, *args):
            self.released = time.perf_counter()
            old_release(value, *args)
            self.taken.append((time.perf_counter(), float(p.options.get("angle", 0.0))))

        self.handle.on_drag, self.handle.on_release = drag, release
        self._preview = p._preview

        def preview(*args, **kwargs):
            result = self._preview(*args, **kwargs)
            self.exact.append((time.perf_counter(), float(p.options.get("angle", 0.0)), p.error))
            return result

        p._preview = preview
        live = getattr(p, "live_shown", None)  # the live preview's hook (2026-10-22)
        if live is not None:
            p.live_shown = lambda angle: self.live.append((time.perf_counter(), float(angle)))
        self.gl = h.gl_widget()
        self.gl.frameSwapped.connect(self._frame)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(2)
        self.timer.timeout.connect(lambda: self.beats.append(time.perf_counter()))
        self.timer.start()

    def _frame(self):
        self.frames.append(time.perf_counter())

    def stop(self):
        self.timer.stop()
        try:
            self.gl.frameSwapped.disconnect(self._frame)
        except Exception:
            pass
        try:
            self.handle.on_drag, self.handle.on_release = self.saved
        except Exception:
            pass
        try:
            del self.p._preview
        except Exception:
            pass
        try:
            del self.p.live_shown
        except Exception:
            pass

    def sample(self, index):
        if index < 0:
            return
        try:
            angle = self.handle.angle()
        except Exception:
            angle = None
        self.moves.append((time.perf_counter(), angle))

    @staticmethod
    def _after(stamps, t, ok=None):
        for item in stamps:
            when = item[0] if isinstance(item, tuple) else item
            if when >= t and (ok is None or ok(item)):
                return when - t
        return None

    def summary(self):
        moved = []
        last = None
        for t, angle in self.moves:
            if angle is not None and (last is None or abs(angle - last) > 1e-6):
                moved.append((t, angle))
            last = angle
        box, frame, live = [], [], []
        for t, _angle in moved:
            for out, stamps in ((box, self.taken), (frame, self.frames), (live, self.live)):
                gap = self._after(stamps, t)
                if gap is not None:
                    out.append(gap)
        t_first = self.moves[0][0] if self.moves else 0.0
        t_last = self.moves[-1][0] if self.moves else 0.0
        beats = [b for b in self.beats if t_first <= b <= t_last + 0.05]
        blocked = max((b - a for a, b in zip(beats, beats[1:])), default=None)
        final = float(self.p.options.get("angle", 0.0))
        # the last time the dialog held another angle than the final one (moved by the mouse,
        # or an exact rebuild at another angle): the exact solid at the final angle comes after
        # it; counted from the last mouse move (0 when it came before)
        t_other = t_first
        for when, angle in self.taken:
            if abs(angle - final) > 1e-9:
                t_other = max(t_other, when)
        for when, angle, _error in self.exact:
            if abs(angle - final) > 1e-9:
                t_other = max(t_other, when)
        exact = None
        for when, angle, error in self.exact:
            if when >= t_other and abs(angle - final) < 1e-9 and not error:
                exact = max(0.0, when - t_last)
                break
        during = len([e for e in self.exact if t_first <= e[0] <= t_last])
        return {
            "moves": len(moved),
            "box": box,
            "frame": frame,
            "live": live,
            "blocked": blocked,
            "exact": exact,
            "rebuilds_while_moving": during,
            "final": final,
        }


def drag_handle(to_deg, moves=40, hold_ms=1500):
    """Turn the angle disc from where it is to `to_deg` with the button held, then hold still
    (hold_ms) and let go."""
    p = panel()
    if p is None or p.handle is None:
        h.check("the Draft handle to drag", False)
        return
    p._timer.stop()
    here, there = p.handle.screen_points(to_deg)
    S["probe"] = probe = Probe(p)
    S["drag"] = a.HeldDrag(
        h.screen_point(here),
        h.screen_point(there),
        moves=moves,
        every_ms=MOVE_MS,
        hold_ms=hold_ms,
        sample=probe.sample,
    )
    S["drag"].run()


def _ms(values, how):
    if not values:
        return None
    values = sorted(values)
    if how == "median":
        return statistics.median(values)
    return values[-1]


def record(label, seconds, **extra):
    entry = {"label": label, "change": seconds}
    entry.update(extra)
    if seconds is None:
        entry.pop("change")
        entry["note"] = "not measured"
    RESULTS.append(entry)


def finish_drag(name):
    """Stop the probe (the drag ended and the dialog had time to rebuild) and record."""
    probe = S.pop("probe", None)
    if probe is None:
        h.check("%s: measured" % name, False)
        return None
    probe.stop()
    s = probe.summary()
    record("Draft drag, %s: value box follows a mouse move (median)" % name, _ms(s["box"], "median"))
    record("Draft drag, %s: value box follows a mouse move (worst)" % name, _ms(s["box"], "max"))
    record("Draft drag, %s: frame drawn after a mouse move (median)" % name, _ms(s["frame"], "median"))
    record("Draft drag, %s: live preview follows a mouse move (median)" % name, _ms(s["live"], "median"))
    record("Draft drag, %s: live preview follows a mouse move (worst)" % name, _ms(s["live"], "max"))
    record("Draft drag, %s: longest freeze while moving" % name, s["blocked"])
    record("Draft drag, %s: exact solid after the mouse stops" % name, s["exact"])
    RESULTS[-1]["rebuilds_while_moving"] = s["rebuilds_while_moving"]
    RESULTS[-1]["moves"] = s["moves"]
    print(
        "[SciForge] perf_draft %s: %s"
        % (name, json.dumps({k: v for k, v in s.items() if not isinstance(v, list)})),
        flush=True,
    )
    h.check("%s: the disc moved" % name, s["moves"] >= 10, s["moves"])
    h.check("%s: the exact solid came at the final angle" % name, s["exact"] is not None, s)
    return s


def same_solid(name, angle=None):
    """The preview's solid is the one drafting.draft_shape makes at the dialog's angle."""
    from sciforge import drafting

    p = panel()
    if p is None or p.target is None:
        h.check("%s: a preview" % name, False)
        return
    angle = float(p.options["angle"]) if angle is None else angle
    options = dict(p.options)
    options["angle"] = angle
    spec = drafting.build_spec((xy_plane(), ""), options, p.base)
    try:
        want = drafting.draft_shape(S["base_shape"], S["names"], spec)
    except Exception as exc:
        h.check("%s: the angle %.1f deg can be drafted" % (name, angle), False, str(exc))
        return
    if p.target.Refine and hasattr(want, "removeSplitter"):
        try:
            want = want.removeSplitter()
        except Exception:
            pass
    got = p.target.Shape
    h.check(
        "%s: the preview is the drafted solid at %.1f deg" % (name, angle),
        abs(got.Volume - want.Volume) < 1e-6 * max(1.0, want.Volume)
        and len(got.Faces) == len(want.Faces),
        (got.Volume, want.Volume, len(got.Faces), len(want.Faces)),
    )
    h.check("%s: no message" % name, not p.error, p.error)


# -- the steps ------------------------------------------------------------------------------------
def box_build():
    Gui.activateWorkbench("SciForgeWorkbench")
    build("PerfDraftBox", parts.BOX)


def box_open():
    shape = S["b"].body.Tip.Shape
    front = [
        "Face%d" % i
        for i, f in enumerate(shape.Faces, 1)
        if f.Surface.__class__.__name__ == "Plane" and abs(f.normalAt(0, 0).y + 1) < 1e-6
    ]
    open_draft(front)


box_open.wait_ms = 1500


def box_drag():
    drag_handle(8.0)


def box_dragged():
    s = finish_drag("box")
    if s is not None:
        h.check("box: the angle went up to about 8 deg", 6.0 < s["final"] < 9.0, s["final"])
    same_solid("box")


box_dragged.wait_ms = 1000


def box_close():
    h.task_button("OK")


def part_build():
    build("PerfDraftPart", parts.PART)
    S["part_faces"] = len(S["b"].body.Tip.Shape.Faces)
    h.check("the part has ~180 faces", S["part_faces"] > 150, S["part_faces"])


part_build.wait_ms = 1500


def part_open():
    open_draft(parts.outer_sides(S["b"].body.Tip.Shape))


part_open.wait_ms = 3000


def part_drag():
    drag_handle(6.0)


def part_dragged():
    s = finish_drag("part")
    if s is not None:
        h.check("part: the angle went up to about 6 deg", 4.5 < s["final"] < 7.0, s["final"])
    same_solid("part")


part_dragged.wait_ms = 1500


def part_profile():
    """One exact rebuild of the part's preview, typed (5.5 deg), profiled."""
    p = panel()
    if p is None:
        return
    p._typed(5.5)
    p._timer.stop()
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    p._recompute()
    Gui.updateGui()
    pr.disable()
    seconds = time.perf_counter() - t0
    out = io.StringIO()
    pstats.Stats(pr, stream=out).sort_stats("cumulative").print_stats(30)
    record("Draft, part: one exact rebuild (typed angle), with the redraw", seconds)
    S["profile"] = [ln for ln in out.getvalue().splitlines() if ln.strip()][:45]


part_profile.wait_ms = 1500


def part_drag_far():
    drag_handle(20.0, hold_ms=3500)


def part_dragged_far():
    s = finish_drag("part, past the limit")
    p = panel()
    if s is not None and p is not None:
        h.check(
            "part: held at the steepest angle that fits (7-8 deg)",
            7.0 <= s["final"] < 8.0,
            (s["final"], p.limits.note),
        )
        h.check("part: the note says so", p.limits.note.startswith("Largest"), p.limits.note)
    same_solid("part, at the limit")


part_dragged_far.wait_ms = 2000


def part_close():
    h.task_button("OK")


def report():
    def ms(v):
        return "" if v is None else "%.0f" % (v * 1000.0)

    guard = perf_guard.compare(RESULTS, perf_guard.baseline_path())
    data = {"part_faces": S.get("part_faces"), "results": RESULTS, "guard": guard}
    with open(os.path.join(out_dir(), "perf-draft-report.json"), "w") as f:
        json.dump(data, f, indent=1)
    cells = perf_guard.columns(guard)
    lines = [
        "# Draft angle drag: how it feels",
        "",
        "Milliseconds. Real mouse moves every %d ms with the button held, then a pause, then "
        "release. The part has %s faces." % (MOVE_MS, S.get("part_faces")),
        "",
        "| What | ms | baseline |",
        "|---|---:|---:|",
    ]
    for r in RESULTS:
        lines.append("| %s | %s | %s |" % (r["label"], ms(r.get("change")), cells(r["label"])[0]))
    lines += [""] + perf_guard.markdown(guard) + [""]
    if S.get("profile"):
        lines += ["## One exact rebuild of the part, profiled", "", "```"] + S["profile"] + ["```", ""]
    with open(os.path.join(out_dir(), "perf-draft-report.md"), "w") as f:
        f.write("\n".join(lines))
    for line in lines:
        print("[SciForge] %s" % line, flush=True)
    written = perf_guard.write_baseline(RESULTS)
    if written:
        print("[SciForge] speed baseline written: %s" % written, flush=True)
    h.check(
        "no measurement over twice as slow as the baseline (SCIFORGE_PERF_STRICT)",
        perf_guard.passed(guard),
        guard.get("slower"),
    )


h.run(
    "perf_draft",
    [
        box_build,
        box_open,
        box_drag,
        box_dragged,
        box_close,
        part_build,
        part_open,
        part_drag,
        part_dragged,
        part_profile,
        part_drag_far,
        part_dragged_far,
        part_close,
        report,
    ],
)
