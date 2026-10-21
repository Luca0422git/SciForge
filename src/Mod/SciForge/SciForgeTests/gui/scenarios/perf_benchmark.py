# SPDX-License-Identifier: LGPL-2.1-or-later
"""Speed benchmark (Luca, 2026-10-21: "optimizing everything all around"): how long the
things a person does take, on a part with a history.

Measured, each on its own (a failure is reported and the next one runs):
  open    the command or the timeline's double-click until its dialog stands with a preview
  change  one value typed (or one drag step): the preview rebuilt and the view updated
  finish  OK (the steps after the marker catch up) or Cancel

The report goes to perf-report.json and perf-report.md next to the other test output,
slowest first, with the top of a profile for each. Nothing here fails on time (machines
differ): the checks only say that each measurement ran; compare reports between versions.

Run alone: tools/sciforge/run_tests.sh --scenario perf_benchmark
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
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
S = {}
RESULTS = []

# A part like the ones Luca makes: a block, four holes, a boss, rounded corners, a chamfer, a
# shell (the steps after the first one are what an edit of the first one has to wait for).
STEPS = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 15},
    {
        "op": "sketch",
        "id": "s2",
        "plane": "XY",
        "geometry": [
            {"circle": [10, 10, 3]},
            {"circle": [50, 10, 3]},
            {"circle": [10, 30, 3]},
            {"circle": [50, 30, 3]},
        ],
    },
    {"op": "extrude", "id": "e2", "profile": "s2", "distance": 15, "operation": "cut"},
    {"op": "sketch", "id": "s3", "plane": "XY", "offset": 15, "geometry": [{"rect": [20, 12, 40, 28]}]},
    {"op": "extrude", "id": "e3", "profile": "s3", "distance": 8},
    {
        "op": "fillet",
        "id": "f1",
        "edges": {
            "any_of": [
                {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "min"}},
                {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "max"}},
            ],
            "count": 4,
        },
        "radius": 4,
    },
    {
        "op": "chamfer",
        "id": "c1",
        "edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4},
        "distance": 1,
    },
    {"op": "sf_shell", "id": "sh1", "faces": {"normal": [0, 0, -1], "count": 1}, "inside": 1},
]


def out_dir():
    return os.environ.get("SCIFORGE_SMOKE_OUT") or os.path.dirname(os.path.abspath(__file__))


# -- the part --------------------------------------------------------------------------------
def build(steps=STEPS, name="PerfPart"):
    from SciForgeTests.golden.builder import Builder

    for d in list(App.listDocuments()):
        try:
            App.closeDocument(d)
        except Exception:
            pass
    doc = App.newDocument(name)
    b = Builder(doc)
    for step in steps:
        b.run(step)
    doc.recompute()
    S["b"] = b
    h.fit()
    return b


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    t0 = time.perf_counter()
    build()
    S["build"] = time.perf_counter() - t0


# -- measuring --------------------------------------------------------------------------------
def pump(seconds=0.0):
    end = time.perf_counter() + seconds
    while True:
        QtWidgets.QApplication.processEvents()
        if time.perf_counter() >= end:
            break


def _profile_top(pr, n=14):
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(n)
    lines = [ln for ln in s.getvalue().splitlines() if ln.strip()]
    keep = []
    for ln in lines:
        if "ncalls" in ln or "/sciforge/" in ln or "{method" in ln or "{built-in" in ln:
            keep.append(ln.replace(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ""))
    return keep[: n + 1]


def busy(fn, wait=0.3):
    """(seconds of work, profile) for fn() and what it leaves to timers within `wait`: the
    profiler's total minus the idle sleeps between event rounds."""
    pr = cProfile.Profile()
    pr.enable()
    fn()
    end = time.perf_counter() + wait
    while time.perf_counter() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    pr.disable()
    stats = pstats.Stats(pr)
    idle = sum(row[2] for key, row in stats.stats.items() if "time.sleep" in key[2])
    return max(0.0, stats.total_tt - idle), _profile_top(pr)


def record(label, **values):
    entry = {"label": label}
    entry.update(values)
    RESULTS.append(entry)
    h.check("measured: %s" % label, "error" not in values, values.get("error", ""))


def measure_dialog(label, open_fn, panel_fn, change_fn, values, finish="Cancel"):
    """Open a dialog, time each value change's preview and the finish."""
    try:
        t0 = time.perf_counter()
        pr_open = cProfile.Profile()
        pr_open.enable()
        open_fn()
        pump()
        pr_open.disable()
        p = panel_fn()
        if p is None or getattr(p, "_closed", True):
            record(label, error="the dialog did not open")
            return
        pr_open.enable()
        try:
            p._timer.stop()
            p._recompute()  # the first preview, if the dialog left it to its timer
        except Exception:
            pass
        pump()
        pr_open.disable()
        t_open = time.perf_counter() - t0
        times = []
        pr = cProfile.Profile()
        for v in values:
            change_fn(p, v)
            p._timer.stop()  # measured here, not by the dialog's timer
            t1 = time.perf_counter()
            pr.enable()
            p._recompute()
            Gui.updateGui()
            pr.disable()
            times.append(time.perf_counter() - t1)
        t2 = time.perf_counter()
        pr_finish = cProfile.Profile()
        pr_finish.enable()
        h.task_button(finish)
        pump()
        pr_finish.disable()
        t_finish = time.perf_counter() - t2
        record(
            label,
            open=t_open,
            change=statistics.median(times),
            change_max=max(times),
            finish=t_finish,
            finish_kind=finish,
            profile=_profile_top(pr),
            profile_open=_profile_top(pr_open),
            profile_finish=_profile_top(pr_finish),
        )
    except Exception as exc:
        record(label, error="%s: %s" % (type(exc).__name__, exc))
        try:
            if Gui.Control.activeDialog():
                h.task_button("Cancel")
        except Exception:
            pass


def select(obj, subs):
    Gui.Selection.clearSelection()
    for sub in subs:
        Gui.Selection.addSelection(obj, sub)


def faces(shape, pred):
    return ["Face%d" % i for i, f in enumerate(shape.Faces, 1) if pred(f)]


def edges(shape, pred):
    return ["Edge%d" % i for i, e in enumerate(shape.Edges, 1) if pred(e)]


def flat_at(z):
    return lambda f: f.Surface.__class__.__name__ == "Plane" and abs(f.BoundBox.ZMin - z) < 1e-6 and abs(f.BoundBox.ZMax - z) < 1e-6


def tip():
    return S["b"].body.Tip


def last(module, cls):
    def get():
        mod = __import__("sciforge." + module, fromlist=[cls])
        return getattr(mod, cls).last

    return get


def run(command):
    return lambda: Gui.runCommand(command)


# -- the measurements -------------------------------------------------------------------------
def m_extrude_new():
    b = S["b"]
    b.run({"op": "sketch", "id": "s9", "plane": "XY", "offset": 23, "geometry": [{"circle": [30, 20, 4]}]})
    App.ActiveDocument.recompute()
    measure_dialog(
        "Extrude, new (sketch selected first)",
        lambda: (select(b.objects["s9"], []), Gui.runCommand("SciForge_Extrude")),
        last("extrude_ui", "ExtrudePanel"),
        lambda p, v: p._distance_typed(v),
        [3, 4, 5, 6, 7, 8],
    )
    try:
        App.ActiveDocument.removeObject(b.objects["s9"].Name)
        App.ActiveDocument.recompute()
    except Exception:
        pass


def m_extrude_edit_first():
    from sciforge import taskui

    measure_dialog(
        "Extrude, edit the FIRST step (8 later steps), OK",
        lambda: taskui.edit_object(S["b"].objects["e1"]),
        last("extrude_ui", "ExtrudePanel"),
        lambda p, v: p._distance_typed(v),
        [16, 17, 18, 17, 16, 15],
        finish="OK",
    )


def m_presspull():
    measure_dialog(
        "Press Pull, the boss top",
        lambda: (select(tip(), faces(tip().Shape, flat_at(23))[:1]), Gui.runCommand("SciForge_PressPull")),
        last("presspull_ui", "PressPullPanel"),
        lambda p, v: p._typed(v),
        [1, 2, 3, 4, 5, 6],
    )


def _outer_vertical(shape):
    def ok(e):
        if e.Curve.__class__.__name__ != "Line":
            return False
        d = e.Vertexes[-1].Point - e.Vertexes[0].Point
        return abs(d.z) > 0.99 * d.Length and e.BoundBox.ZMax <= 15.001 and e.BoundBox.XMin in (0.0, 60.0)

    return edges(shape, ok)


def m_fillet():
    build(STEPS[:6], "PerfFillet")
    measure_dialog(
        "Fillet, new, 4 vertical edges",
        lambda: (select(tip(), _outer_vertical(tip().Shape)), Gui.runCommand("SciForge_Fillet")),
        last("fillet_ui", "FilletPanel"),
        lambda p, v: p._typed("radius", v),
        [2, 2.5, 3, 3.5, 4, 4.5],
    )


def m_chamfer():
    measure_dialog(
        "Chamfer, new, 4 vertical edges",
        lambda: (select(tip(), _outer_vertical(tip().Shape)), Gui.runCommand("SciForge_Chamfer")),
        last("fillet_ui", "ChamferPanel"),
        lambda p, v: p._typed("distance", v),
        [1, 1.5, 2, 2.5, 3, 3.5],
    )


def m_shell():
    measure_dialog(
        "Shell, new, the bottom face taken away",
        lambda: (select(tip(), faces(tip().Shape, flat_at(0))), Gui.runCommand("SciForge_Shell")),
        last("shell_ui", "ShellPanel"),
        lambda p, v: p._inside_typed(v),
        [1, 1.2, 1.4, 1.6, 1.8, 2],
    )


def m_draft():
    from sciforge import draft_ui

    def open_():
        select(tip(), [])
        Gui.runCommand("SciForge_Draft")
        p = draft_ui.DraftPanel.last
        xy = [o for o in S["b"].body.Origin.OriginFeatures if o.Role == "XY_Plane"][0]
        p._set_plane((xy, ""))
        side = faces(tip().Shape, lambda f: f.Surface.__class__.__name__ == "Plane" and abs(f.normalAt(0, 0).y + 1) < 1e-6)
        for name in side[:1]:
            p._add_face(tip(), name)
        p._picks_updated(schedule=False)

    measure_dialog(
        "Draft, new, the front wall",
        open_,
        last("draft_ui", "DraftPanel"),
        lambda p, v: p._typed(v),
        [2, 3, 4, 5, 6, 7],
    )


def m_pattern():
    measure_dialog(
        "Rectangular Pattern, the boss, quantity",
        lambda: (select(S["b"].body.Tip, []), Gui.runCommand("SciForge_RectangularPattern")),
        last("pattern_ui", "PatternPanel"),
        lambda p, v: p.quantity.setValue(int(v)),
        [2, 3, 4, 3, 2, 3],
    )


def m_move():
    measure_dialog(
        "Move, the body, X distance",
        lambda: (select(S["b"].body, []), Gui.runCommand("SciForge_Move")),
        last("move_ui", "MovePanel"),
        lambda p, v: p._field("dx", v),
        [5, 10, 15, 20, 25, 30],
    )


def m_timeline():
    """The history marker dragged to the start and back to the end; undo and redo."""
    try:
        doc = App.ActiveDocument
        names = ti.titles()
        t_back, prof_back = busy(lambda: ti.drag_marker(before_title=names[1]))
        t_end, prof_end = busy(lambda: ti.drag_marker(to_end=True))
        record(
            "Timeline marker: to the 2nd step / back to the end",
            open=t_back,
            finish=t_end,
            change=t_end,
            profile_open=prof_back,
            profile=prof_end,
        )
        t0 = time.perf_counter()
        doc.undo()
        doc.recompute()
        pump()
        t_undo = time.perf_counter() - t0
        t0 = time.perf_counter()
        doc.redo()
        doc.recompute()
        pump()
        t_redo = time.perf_counter() - t0
        record("Undo / redo", open=t_undo, finish=t_redo, change=max(t_undo, t_redo))
    except Exception as exc:
        record("Timeline / undo", error="%s: %s" % (type(exc).__name__, exc))


def m_hover():
    """The mouse moved over the part (preselection), with no command and with Fillet open."""
    try:
        h.fit()
        widget = h.gl_widget()
        box = tip().Shape.BoundBox
        a = h.screen_point(V(box.XMin, box.YMin, box.ZMax))
        b2 = h.screen_point(V(box.XMax, box.YMax, box.ZMax))

        def sweep():
            times = []
            for i in range(40):
                pos = QtCore.QPointF(a.x() + (b2.x() - a.x()) * i / 39.0, a.y() + (b2.y() - a.y()) * i / 39.0)
                ev = QtGui.QMouseEvent(
                    QtCore.QEvent.MouseMove, pos, QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                    QtCore.Qt.NoButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier,
                )
                t1 = time.perf_counter()
                QtWidgets.QApplication.sendEvent(widget, ev)
                QtWidgets.QApplication.processEvents()
                times.append(time.perf_counter() - t1)
            return statistics.median(times), max(times)

        med, worst = sweep()
        record("Mouse over the part (no command)", change=med, change_max=worst)
        select(tip(), _outer_vertical(tip().Shape)[:1])
        Gui.runCommand("SciForge_Fillet")
        pump()
        med, worst = sweep()
        record("Mouse over the part (Fillet open)", change=med, change_max=worst)
        h.task_button("Cancel")
        pump()
    except Exception as exc:
        record("Mouse over the part", error="%s: %s" % (type(exc).__name__, exc))


def m_sketch():
    """Create Sketch on XY, a sketch of 12 rectangles and 12 circles, a corner dragged,
    Finish Sketch."""
    try:
        for d in list(App.listDocuments()):
            App.closeDocument(d)
        App.newDocument("PerfSketch")
        h.fit()
        t_ribbon, _prof = busy(lambda: h.ribbon("Create Sketch"), wait=1.0)
        t_click, prof_enter = busy(lambda: pl.click_on_plane(V(12, -8, 0)), wait=1.0)
        t_enter = t_ribbon + t_click
        sk = h.in_sketch()
        if sk is None:
            record("Sketch", error="no sketch open")
            return
        import Part

        for i in range(12):
            x, y = (i % 4) * 30, (i // 4) * 25
            h.draw_rectangle(sk, x, y, x + 20, y + 15)
            sk.addGeometry(Part.Circle(V(x + 10, y + 7.5, 0), V(0, 0, 1), 3))
        App.ActiveDocument.recompute()
        h.fit()
        pump()
        widget = h.gl_widget()
        start = h.screen_point(sk.getGlobalPlacement().multVec(V(20, 15, 0)))
        end = h.screen_point(sk.getGlobalPlacement().multVec(V(26, 19, 0)))
        h.move(start)
        QtTest.QTest.mousePress(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
        times = []
        pr = cProfile.Profile()
        for i in range(1, 41):
            pos = QtCore.QPointF(start.x() + (end.x() - start.x()) * i / 40.0, start.y() + (end.y() - start.y()) * i / 40.0)
            ev = QtGui.QMouseEvent(
                QtCore.QEvent.MouseMove, pos, QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
                QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier,
            )
            t1 = time.perf_counter()
            pr.enable()
            QtWidgets.QApplication.sendEvent(widget, ev)
            QtWidgets.QApplication.processEvents()
            pr.disable()
            times.append(time.perf_counter() - t1)
        t1 = time.perf_counter()
        QtTest.QTest.mouseRelease(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, end)
        pump()
        t_release = time.perf_counter() - t1
        record(
            "Sketch: drag a corner (12 rectangles, 12 circles)",
            open=t_enter, change=statistics.median(times), change_max=max(times), finish=t_release,
            profile=_profile_top(pr),
            profile_open=prof_enter,
        )
        t_fin, prof_fin = busy(lambda: h.ribbon("Finish Sketch"), wait=0.5)
        record("Finish Sketch", change=t_fin, profile=prof_fin)
    except Exception as exc:
        record("Sketch", error="%s: %s" % (type(exc).__name__, exc))


def m_save_open():
    try:
        import tempfile

        build(STEPS, "PerfFile")
        path = os.path.join(tempfile.mkdtemp(prefix="sciforge_perf_"), "PerfFile.FCStd")
        doc = App.ActiveDocument
        t0 = time.perf_counter()
        doc.saveAs(path)
        t_save = time.perf_counter() - t0
        App.closeDocument(doc.Name)
        pump()
        t0 = time.perf_counter()
        App.openDocument(path)
        pump()
        t_open = time.perf_counter() - t0
        record("Save / open the 9-step part", open=t_open, finish=t_save, change=t_open)
    except Exception as exc:
        record("Save / open", error="%s: %s" % (type(exc).__name__, exc))


def rebuild():
    build()


# -- the report ---------------------------------------------------------------------------------
def report():
    def ms(v):
        return "" if v is None else "%.0f" % (v * 1000.0)

    rows = sorted(RESULTS, key=lambda r: -(r.get("change") or 0.0))
    data = {"build_seconds": S.get("build"), "results": RESULTS}
    with open(os.path.join(out_dir(), "perf-report.json"), "w") as f:
        json.dump(data, f, indent=1)
    lines = [
        "# SciForge speed benchmark",
        "",
        "Milliseconds; slowest change first. open = command to dialog with a preview, change = "
        "one value (or one mouse step), finish = OK / Cancel.",
        "",
        "| What | open | change | change max | finish |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        if "error" in r:
            lines.append("| %s | error: %s | | | |" % (r["label"], r["error"]))
            continue
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (r["label"], ms(r.get("open")), ms(r.get("change")), ms(r.get("change_max")), ms(r.get("finish")))
        )
    lines.append("")
    for r in rows:
        for key, what in (("profile", "change"), ("profile_open", "open"), ("profile_finish", "finish")):
            if r.get(key):
                lines += ["## %s (%s)" % (r["label"], what), "", "```"] + r[key] + ["```", ""]
    with open(os.path.join(out_dir(), "perf-report.md"), "w") as f:
        f.write("\n".join(lines))
    print("[SciForge] perf report: %s" % os.path.join(out_dir(), "perf-report.md"), flush=True)
    h.check("report written", True)


h.run(
    "perf_benchmark",
    [
        setup,
        m_extrude_new,
        m_extrude_edit_first,
        h.idle_step(),
        m_presspull,
        m_timeline,
        m_hover,
        m_fillet,
        m_chamfer,
        m_shell,
        m_draft,
        m_pattern,
        m_move,
        m_sketch,
        m_save_open,
        report,
    ],
)
