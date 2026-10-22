# SPDX-License-Identifier: LGPL-2.1-or-later
"""Speed with BIG designs (Luca approved idea 6 of docs/sciforge/dev/cadcraft-lessons.md):
how long what a person does takes when the design is large.

The design: a plate with a dense grid of holes and rounded bosses (well over a thousand
faces), a second body with a long history (more than a hundred timeline steps) and a third
body made into a component. On it, each measured on its own (a failure is reported and the
next one runs):

  idle        a few seconds with nothing happening: what SciForge's timers cost
  orbit/zoom  the camera turned / zoomed frame by frame, the view drawn each time
  hover       the mouse moved over the dense plate (preselection)
  select      a face clicked, a second one Ctrl+clicked, the selection cleared
  timeline    the timeline / browser rebuilt (forced) and their poll with nothing changed
  edit        a value of the first step changed: recompute, redisplay, timeline and browser
  undo/redo   that edit undone and redone
  save/open   the design saved and opened again

Software OpenGL under xvfb draws slowly, so what matters is the CPU time SciForge and Coin
add around the drawing; each measurement keeps the top of a cProfile for that reason.

The report goes to perf-big-report.json / .md next to the other test output. Regression
guard: with SCIFORGE_PERF_BASELINE set to a stored perf-big-report.json (or the default
SciForgeTests/gui/perf_baseline.json when it exists) every measurement that is more than
twice as slow as there is listed as a warning; SCIFORGE_PERF_STRICT=1 makes it a failure.
SCIFORGE_PERF_SCALE (default 1.0) shrinks or grows the design.

Run alone: tools/sciforge/run_tests.sh --scenario perf_big_model
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
from SciForgeTests.gui import perf_guard

V = App.Vector
S = {}
RESULTS = []
SCALE = float(os.environ.get("SCIFORGE_PERF_SCALE") or 1.0)


def out_dir():
    return os.environ.get("SCIFORGE_SMOKE_OUT") or os.path.dirname(os.path.abspath(__file__))


# -- the design --------------------------------------------------------------------------------
def plate_size():
    return max(2, int(20 * SCALE)), max(2, int(14 * SCALE))


def hole_sketch(b):
    """The plate's holes: a hexagon in every 10 mm cell, drawn in one go (no dimensions:
    a sketch of a few hundred dimensioned shapes takes the solver minutes, which is not what
    is measured here)."""
    import math

    import Part

    cols, rows = plate_size()
    b.run({"op": "sketch", "id": "p_s2", "plane": "XY", "geometry": []})
    sketch = b.objects["p_s2"]
    geo = []
    for i in range(cols):
        for j in range(rows):
            cx, cy, r = 5 + 10 * i, 5 + 10 * j, 2.8
            pts = [V(cx + r * math.cos(math.pi / 3 * k), cy + r * math.sin(math.pi / 3 * k), 0) for k in range(6)]
            geo += [Part.LineSegment(pts[k], pts[(k + 1) % 6]) for k in range(6)]
    sketch.addGeometry(geo, False)
    App.ActiveDocument.recompute()


def plate_steps():
    """A plate with a hexagon hole in every cell and a few bosses: well over a thousand
    faces. (No fillet on it: OpenCASCADE's fillet of a few edges of a solid this size takes
    over a minute, which is the kernel, not what SciForge adds; see the notes.)"""
    cols, rows = plate_size()
    width, depth = cols * 10.0, rows * 10.0
    bosses = []
    for i in range(1, cols - 1, 6):
        for j in range(1, rows - 1, 6):
            bosses.append({"rect": [10 * i + 7.5, 10 * j + 7.5, 10 * i + 12.5, 10 * j + 12.5]})
    return [
        {"op": "sketch", "id": "p_s1", "plane": "XY", "geometry": [{"rect": [0, 0, width, depth]}]},
        {"op": "extrude", "id": "p_e1", "profile": "p_s1", "distance": 8},
        hole_sketch,
        {"op": "extrude", "id": "p_e2", "profile": "p_s2", "distance": 8, "operation": "cut"},
        {"op": "sketch", "id": "p_s3", "plane": "XY", "offset": 8, "geometry": bosses},
        {"op": "extrude", "id": "p_e3", "profile": "p_s3", "distance": 5},
    ]


def tower_steps():
    """A second body with a long history: a base with rounded edges, then one small boss
    per two steps (sketch + extrude)."""
    n = max(4, int(55 * SCALE))
    steps = [
        {"op": "sketch", "id": "t_s0", "plane": "XY", "offset": -40, "geometry": [{"rect": [0, 0, 80, 80]}]},
        {"op": "extrude", "id": "t_e0", "profile": "t_s0", "distance": 4, "operation": "new_body"},
        {"op": "fillet", "id": "t_f0", "edges": {"type": "line", "at": {"axis": "z", "value": "max"}}, "radius": 1},
    ]
    for k in range(1, n):
        x, y = 5 + 10 * ((k - 1) % 7), 5 + 10 * ((k - 1) // 7 % 7)
        steps.append(
            {
                "op": "sketch",
                "id": "t_s%d" % k,
                "plane": "XY",
                "offset": -36,
                "geometry": [{"circle": [x, y, 2 + (k % 3) * 0.5]}],
            }
        )
        steps.append({"op": "extrude", "id": "t_e%d" % k, "profile": "t_s%d" % k, "distance": 2 + k % 5})
    # the last bosses rounded: a fillet late in the history that an early edit must keep
    steps.append(
        {
            "op": "fillet",
            "id": "t_f1",
            "edges": {"type": "circle", "at": {"axis": "z", "value": "max"}},
            "radius": 0.4,
        }
    )
    return steps


def part_steps():
    return [
        {"op": "sketch", "id": "c_s1", "plane": "XY", "offset": -80, "geometry": [{"circle": [40, 40, 20]}]},
        {"op": "extrude", "id": "c_e1", "profile": "c_s1", "distance": 10, "operation": "new_body"},
        {"op": "components_from_bodies", "id": "c_k1", "bodies": ["c_e1"], "label": "Hub"},
    ]


def build(name="PerfBig"):
    from SciForgeTests.golden.builder import Builder

    for d in list(App.listDocuments()):
        try:
            App.closeDocument(d)
        except Exception:
            pass
    doc = App.newDocument(name)
    b = Builder(doc)
    times = {}
    for label, steps in (("plate", plate_steps()), ("tower", tower_steps()), ("component", part_steps())):
        t0 = time.perf_counter()
        for step in steps:
            step(b) if callable(step) else b.run(step)
        times[label] = round(time.perf_counter() - t0, 2)
    doc.recompute()
    S["b"] = b
    S["plate"] = b.objects["p_e3"]
    S["first"] = b.objects["p_e1"]
    S["tower_first"] = b.objects["t_e0"]
    h.fit()
    pump(0.5)
    return times


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    t0 = time.perf_counter()
    times = build()
    S["build"] = time.perf_counter() - t0
    plate = S["plate"].Shape
    from sciforge import timeline_ui

    steps = len(timeline_ui.widget().items()) if timeline_ui.widget() is not None else 0
    S["size"] = {
        "plate_faces": len(plate.Faces),
        "plate_edges": len(plate.Edges),
        "objects": len(App.ActiveDocument.Objects),
        "timeline_steps": steps,
        "build_seconds": times,
    }
    print("[SciForge] perf_big_model design: %s" % S["size"], flush=True)
    h.check("the plate has over a thousand faces", len(plate.Faces) > 1000 * min(1.0, SCALE), len(plate.Faces))
    h.check("the timeline has over a hundred steps", steps > 100 * min(1.0, SCALE), steps)


# -- measuring --------------------------------------------------------------------------------
def pump(seconds=0.0):
    end = time.perf_counter() + seconds
    while True:
        QtWidgets.QApplication.processEvents()
        if time.perf_counter() >= end:
            break


def _profile_top(pr, n=16, sort="cumulative"):
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats(sort).print_stats(n)
    lines = [ln for ln in s.getvalue().splitlines() if ln.strip()]
    keep = []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for ln in lines:
        if "ncalls" in ln or "/sciforge/" in ln or "{method" in ln or "{built-in" in ln:
            keep.append(ln.replace(root, ""))
    return keep[: n + 1]


def _python_time(pr):
    """Seconds the profiler saw spent in SciForge's own code (and what it called): the
    cumulative time of every SciForge function as called from outside SciForge (a timer, an
    observer, FreeCAD), so nothing is counted twice."""
    stats = pstats.Stats(pr)
    total = 0.0
    for func, row in stats.stats.items():
        if "/sciforge/" not in func[0]:
            continue
        callers = row[4]
        if not callers:
            total += row[3]
            continue
        for caller, edge in callers.items():
            if "/sciforge/" not in caller[0]:
                total += edge[3]
    return total


def record(label, **values):
    entry = {"label": label}
    entry.update(values)
    RESULTS.append(entry)
    h.check("measured: %s" % label, "error" not in values, values.get("error", ""))


def frames(label, fn, count):
    """Median / worst wall time of `count` calls of fn(i), each followed by the events it
    queues (the redraw); with the profile of all of them."""
    times = []
    pr = cProfile.Profile()
    for i in range(count):
        t0 = time.perf_counter()
        pr.enable()
        fn(i)
        QtWidgets.QApplication.processEvents()
        pr.disable()
        times.append(time.perf_counter() - t0)
    record(
        label,
        change=statistics.median(times),
        change_max=max(times),
        python=_python_time(pr) / count,
        profile=_profile_top(pr),
        profile_self=_profile_top(pr, sort="tottime"),
    )


def once(label, fn, wait=0.3, **extra):
    """Wall time of fn() plus what it leaves to timers within `wait` (busy time, the idle
    sleeps between event rounds left out)."""
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    fn()
    pr.disable()
    wall = time.perf_counter() - t0
    pr.enable()
    end = time.perf_counter() + wait
    while time.perf_counter() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)
    pr.disable()
    values = dict(change=wall, python=_python_time(pr), profile=_profile_top(pr))
    values["profile_self"] = _profile_top(pr, sort="tottime")
    values.update(extra)
    record(label, **values)


def guarded(fn):
    def step():
        try:
            fn()
        except Exception as exc:
            import traceback

            record(fn.__name__, error="%s: %s" % (type(exc).__name__, exc))
            print(traceback.format_exc(), flush=True)

    step.__name__ = fn.__name__
    return step


# -- the measurements -------------------------------------------------------------------------
@guarded
def m_idle():
    """Nothing happening for a few seconds: the CPU SciForge's polling timers take."""
    Gui.Selection.clearSelection()
    pump(0.5)
    seconds = 3.0
    pr = cProfile.Profile()
    pr.enable()
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.005)
    pr.disable()
    stats = pstats.Stats(pr)
    idle = sum(row[2] for key, row in stats.stats.items() if "time.sleep" in key[2])
    record(
        "Idle: busy time per second (timers)",
        change=max(0.0, stats.total_tt - idle) / seconds,
        python=_python_time(pr) / seconds,
        profile=_profile_top(pr),
        profile_self=_profile_top(pr, sort="tottime"),
    )


def _camera():
    return h.view().getCameraNode()


@guarded
def m_orbit():
    from pivy import coin

    h.fit()
    pump(0.2)
    cam = _camera()
    start = cam.orientation.getValue()

    def turn(i):
        rot = coin.SbRotation(coin.SbVec3f(0, 0, 1), 0.05)
        cam.orientation.setValue(cam.orientation.getValue() * rot)
        h.view().redraw()

    frames("Orbit: one frame (camera turned)", turn, 30)
    cam.orientation.setValue(start)
    pump(0.1)


@guarded
def m_zoom():
    h.fit()
    pump(0.2)
    cam = _camera()

    def zoom(i):
        factor = 0.95 if i < 15 else 1.0 / 0.95
        if hasattr(cam, "height"):
            cam.height.setValue(cam.height.getValue() * factor)
        else:
            cam.heightAngle.setValue(cam.heightAngle.getValue() * factor)
        h.view().redraw()

    frames("Zoom: one frame", zoom, 30)
    h.fit()


@guarded
def m_pan():
    h.fit()
    pump(0.2)

    def slide(i):
        h.pan(6 if i < 15 else -6, 0)
        h.view().redraw()

    frames("Pan: one frame", slide, 30)
    h.fit()


@guarded
def m_view_settings():
    """FreeCAD's drawing settings that could help big designs, each tried on the orbit:
    Coin's render cache (View/RenderCache: 0 auto, 1 distributed, 2 centralized) and vertex
    buffer objects (View/UseVBO). Measured, then put back as they were."""
    from pivy import coin

    params = App.ParamGet("User parameter:BaseApp/Preferences/View")
    before = (params.GetInt("RenderCache", 0), params.GetBool("UseVBO", False))
    cam = _camera()
    start = cam.orientation.getValue()

    def turn(i):
        cam.orientation.setValue(cam.orientation.getValue() * coin.SbRotation(coin.SbVec3f(0, 0, 1), 0.05))
        h.view().redraw()

    try:
        for cache, vbo in ((0, False), (1, False), (2, False), (0, True)):
            params.SetInt("RenderCache", cache)
            params.SetBool("UseVBO", vbo)
            h.fit()
            pump(0.3)
            frames("View setting: orbit with RenderCache=%d UseVBO=%s" % (cache, vbo), turn, 30)
    finally:
        params.SetInt("RenderCache", before[0])
        params.SetBool("UseVBO", before[1])
        cam.orientation.setValue(start)
        h.fit()
        pump(0.2)


def _plate_points():
    box = S["plate"].Shape.BoundBox
    a = h.screen_point(V(box.XMin + 2, box.YMin + 2, 8))
    b = h.screen_point(V(box.XMax - 2, box.YMax - 2, 8))
    return a, b


@guarded
def m_hover():
    h.view().viewTop()
    h.view().fitAll()
    pump(0.2)
    widget = h.gl_widget()
    a, b = _plate_points()

    def step(i):
        pos = QtCore.QPointF(a.x() + (b.x() - a.x()) * i / 59.0, a.y() + (b.y() - a.y()) * i / 59.0)
        ev = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            pos,
            QtCore.QPointF(widget.mapToGlobal(pos.toPoint())),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, ev)

    frames("Hover: one mouse step over the dense plate", step, 60)


@guarded
def m_select():
    h.view().viewTop()
    h.view().fitAll()
    pump(0.2)
    widget = h.gl_widget()
    box = S["plate"].Shape.BoundBox
    # the plate's top between holes, then a boss top
    p1 = h.screen_point(V(box.XMin + 10, box.YMin + 0.6, 8))
    p2 = h.screen_point(V(box.XMin + 10, box.YMin + 10, 13))
    Gui.Selection.clearSelection()
    pump(0.1)

    def click1():
        h.move(p1)
        QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, p1)

    def click2():
        h.move(p2)
        QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.ControlModifier, p2)

    once("Select: click a face of the dense plate", click1)
    first = [(s.ObjectName, s.SubElementNames) for s in Gui.Selection.getSelectionEx()]
    once("Select: Ctrl+click a second face", click2)
    S["selected"] = [(s.ObjectName, s.SubElementNames) for s in Gui.Selection.getSelectionEx()]
    once("Select: clear the selection", Gui.Selection.clearSelection)
    h.check("a click selected a face", bool(first), first)


@guarded
def m_panels():
    """The timeline and the browser: rebuilt, read again with nothing changed (an explicit
    refresh) and their timers' tick with nothing changed."""
    from sciforge import browser_ui, timeline_ui

    def tenfold(label, fn):
        once(label, lambda: [fn() for _ in range(10)], wait=0.0)
        RESULTS[-1]["change"] /= 10.0
        RESULTS[-1]["python"] /= 10.0

    for name, widget in (("Timeline", timeline_ui.widget()), ("Browser", browser_ui.widget())):
        if widget is None:
            continue
        once("%s: rebuilt (forced)" % name, lambda: widget.refresh(force=True), wait=0.1)
        tenfold("%s: read again, nothing changed" % name, widget.refresh)
        tenfold("%s: its timer's tick, nothing changed" % name, getattr(widget, "_poll", widget.refresh))


def _settle(seconds=1.0):
    """Events until the document has stopped recomputing, then `seconds` more (the panels'
    polls run every 400-500 ms; the timeline's after-undo work is deferred)."""
    end = time.perf_counter() + 600
    while time.perf_counter() < end:
        QtWidgets.QApplication.processEvents()
        doc = App.ActiveDocument
        if doc is None or not doc.Recomputing:
            break
        time.sleep(0.01)
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.01)


def _measured(label, fn, settle=1.0):
    """fn() timed (wall) and profiled together with what it leaves to timers."""
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    fn()
    _settle(0.0)
    pr.disable()
    wall = time.perf_counter() - t0
    pr.enable()
    _settle(settle)
    pr.disable()
    record(
        label,
        change=wall,
        python=_python_time(pr),
        profile=_profile_top(pr),
        profile_self=_profile_top(pr, sort="tottime"),
    )


def _edit(label, feature, a, b):
    """The step's distance changed the way a dialog's OK does (the timeline's recompute
    inside the transaction), then Ctrl+Z and Ctrl+Y."""
    from sciforge import timeline_ops

    doc = App.ActiveDocument
    _settle(0.5)

    def edit():
        doc.openTransaction("Perf edit")
        feature.Length = b if abs(feature.Length.Value - a) < 1e-6 else a
        timeline_ops.recompute(doc)  # inside the transaction, like a dialog's OK
        doc.commitTransaction()
        Gui.updateGui()

    _measured("%s: recompute + redisplay" % label, edit)
    _measured("%s: Undo (Ctrl+Z)" % label, lambda: Gui.runCommand("Std_Undo"))
    _measured("%s: Redo (Ctrl+Y)" % label, lambda: Gui.runCommand("Std_Redo"))


@guarded
def m_edit_plate():
    """The plate's first step changed: the dense cut and the bosses rebuilt."""
    _edit("Edit the plate's first step", S["first"], 8.0, 9.0)


@guarded
def m_edit_tower():
    """The long history's first step changed: every later step rebuilt."""
    _edit("Edit the first of 110+ steps", S["tower_first"], 4.0, 5.0)


@guarded
def m_add_step():
    """A new step at the end of the long history: what the timeline / browser do after it."""
    b = S["b"]

    def add():
        b.run({"op": "sketch", "id": "t_new", "plane": "XY", "offset": -36, "geometry": [{"circle": [75, 75, 2]}]})
        b.run({"op": "extrude", "id": "t_enew", "profile": "t_new", "distance": 3})
        Gui.updateGui()

    _measured("Add a step at the end (sketch + extrude)", add)


@guarded
def m_save_open():
    import tempfile

    doc = App.ActiveDocument
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge_perf_big_"), "PerfBig.FCStd")
    _measured("Save the big design", lambda: doc.saveAs(path), settle=0.2)
    App.closeDocument(doc.Name)
    pump(0.3)

    def open_():
        App.openDocument(path)
        Gui.updateGui()

    _measured("Open the big design", open_)
    S["path"] = path


# -- the report ---------------------------------------------------------------------------------
def report():
    def ms(v):
        return "" if v is None else "%.1f" % (v * 1000.0)

    guard = perf_guard.compare(RESULTS, perf_guard.baseline_path())
    data = {"size": S.get("size"), "build_seconds": S.get("build"), "results": RESULTS, "guard": guard}
    with open(os.path.join(out_dir(), "perf-big-report.json"), "w") as f:
        json.dump(data, f, indent=1)
    lines = [
        "# SciForge speed with a big design",
        "",
        "Design: %s" % json.dumps(S.get("size")),
        "",
        "Milliseconds (idle: per second). wall = what a person waits, sciforge = the part "
        "of it spent in SciForge's own Python code (and what that code called).",
        "",
        "| What | wall | worst | sciforge |",
        "|---|---:|---:|---:|",
    ]
    for r in RESULTS:
        if "error" in r:
            lines.append("| %s | error: %s | | |" % (r["label"], r["error"]))
            continue
        lines.append("| %s | %s | %s | %s |" % (r["label"], ms(r.get("change")), ms(r.get("change_max")), ms(r.get("python"))))
    lines.append("")
    lines += perf_guard.markdown(guard)
    for r in RESULTS:
        for key, what in (("profile", "cumulative"), ("profile_self", "own time")):
            if r.get(key):
                lines += ["## %s (%s)" % (r["label"], what), "", "```"] + r[key] + ["```", ""]
    with open(os.path.join(out_dir(), "perf-big-report.md"), "w") as f:
        f.write("\n".join(lines))
    print("[SciForge] perf report: %s" % os.path.join(out_dir(), "perf-big-report.md"), flush=True)
    for line in perf_guard.markdown(guard):
        print("[SciForge] %s" % line, flush=True)
    written = perf_guard.write_baseline(RESULTS)
    if written:
        print("[SciForge] speed baseline written: %s" % written, flush=True)
    h.check("report written", True)
    h.check("no measurement over twice as slow as the baseline (SCIFORGE_PERF_STRICT)", perf_guard.passed(guard), guard.get("slower"))


h.run(
    "perf_big_model",
    [
        setup,
        h.idle_step(),
        m_idle,
        m_orbit,
        m_zoom,
        m_pan,
        m_view_settings,
        m_hover,
        m_select,
        m_panels,
        m_edit_plate,
        h.idle_step(),
        m_edit_tower,
        h.idle_step(),
        m_add_step,
        m_save_open,
        report,
    ],
)
