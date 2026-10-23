# SPDX-License-Identifier: LGPL-2.1-or-later
"""Entering and leaving a sketch (2026-10-23, sketch-enter): Create Sketch, a sketch edited
again (what a double-click does) and Finish Sketch, each timed and profiled.

Information only: the times are printed and written to sketch-enter-report.md next to the
other test output; nothing fails on time (Luca judges the feel on his own machine). The checks
say that each step happened: the sketch is open, the SKETCH ribbon is up, and after Finish
the SOLID ribbon is back and nothing is left in edit.
"""
import cProfile
import io
import os
import pstats
import statistics
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
S = {"enter": [], "leave": [], "profiles": {}}
ROUNDS = 5


def out_dir():
    return os.environ.get("SCIFORGE_SMOKE_OUT") or os.getcwd()


def pump(seconds=0.0):
    end = time.perf_counter() + seconds
    while True:
        QtWidgets.QApplication.processEvents()
        if time.perf_counter() >= end:
            break


def timed(label, fn):
    """Wall time of fn() and the events it queues (timers due at once); the profile kept."""
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    fn()
    QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.processEvents()
    pr.disable()
    t = time.perf_counter() - t0
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(40)
    S["profiles"].setdefault(label, s.getvalue())
    return t


def sketch_tab_up():
    from sciforge import shell

    rib = shell.ribbon()
    return rib is not None and bool(getattr(rib, "_sketch_mode", False)) and rib.current_tab() == "sketch"


def workbench():
    wb = Gui.activeWorkbench()
    return wb.name() if wb is not None else ""


def first_enter():
    for d in list(App.listDocuments()):
        App.closeDocument(d)
    App.newDocument("SketchEnter")
    h.fit()
    pump(0.3)
    t = timed("create sketch (ribbon + plane click)", lambda: (h.ribbon("Create Sketch"), pl.click_on_plane(V(12, -8, 0))))
    sk = h.in_sketch()
    h.check("Create Sketch opened a sketch", sk is not None)
    if sk is None:
        return
    S["sk"] = sk
    S["create"] = t
    h.check("Create Sketch: SKETCH tab up", sketch_tab_up())
    print("[SciForge] workbench in the sketch: %s" % workbench(), flush=True)
    h.draw_rectangle(sk, 0, 0, 20, 10)
    App.ActiveDocument.recompute()
    pump(0.3)
    t = timed("finish sketch", lambda: h.ribbon("Finish Sketch"))
    S["leave"].append(t)
    h.check("Finish Sketch left the sketch", h.in_sketch() is None)


def rounds():
    sk = S.get("sk")
    if sk is None:
        h.check("rounds need a sketch", False)
        return
    for i in range(ROUNDS):
        pump(0.3)
        t = timed("edit sketch (setEdit, as a double-click)", lambda: Gui.ActiveDocument.setEdit(sk.Name))
        S["enter"].append(t)
        h.check("round %d: sketch open" % i, h.in_sketch() is not None)
        h.check("round %d: SKETCH tab up" % i, sketch_tab_up())
        pump(0.3)
        t = timed("finish sketch", lambda: h.ribbon("Finish Sketch"))
        S["leave"].append(t)
        h.check("round %d: sketch closed" % i, h.in_sketch() is None)
        h.check("round %d: SKETCH tab gone" % i, not sketch_tab_up())
    print("[SciForge] workbench after the rounds: %s" % workbench(), flush=True)


def no_switch_experiment():
    """Information only: the same rounds with the sketch's EditingWorkbench empty (FreeCAD
    then stays in the SciForge workbench), to see what the switch itself costs. Not what
    SciForge does (the SKETCH tab follows the switch); the property is put back after."""
    sk = S.get("sk")
    if sk is None:
        return
    S["exp_enter"], S["exp_leave"] = [], []
    try:
        sk.ViewObject.EditingWorkbench = ""
        for i in range(3):
            pump(0.3)
            t0 = time.perf_counter()
            Gui.ActiveDocument.setEdit(sk.Name)
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()
            S["exp_enter"].append(time.perf_counter() - t0)
            S["exp_workbench"] = workbench()
            pump(0.3)
            t0 = time.perf_counter()
            Gui.ActiveDocument.resetEdit()
            QtWidgets.QApplication.processEvents()
            QtWidgets.QApplication.processEvents()
            S["exp_leave"].append(time.perf_counter() - t0)
    finally:
        sk.ViewObject.EditingWorkbench = "SketcherWorkbench"
        if h.in_sketch() is not None:
            Gui.ActiveDocument.resetEdit()
        pump(0.3)
    h.check("experiment: nothing left in edit", h.in_sketch() is None)


def report():
    lines = ["# Entering and leaving a sketch", ""]

    def ms(v):
        return "%.0f ms" % (v * 1000.0)

    if "create" in S:
        lines.append("- Create Sketch (ribbon + plane click): %s" % ms(S["create"]))
    if S["enter"]:
        lines.append("- Edit sketch (setEdit): median %s, all %s" % (ms(statistics.median(S["enter"])), ", ".join(ms(v) for v in S["enter"])))
    if S["leave"]:
        lines.append("- Finish Sketch: median %s, all %s" % (ms(statistics.median(S["leave"])), ", ".join(ms(v) for v in S["leave"])))
    if S.get("exp_enter"):
        lines.append(
            "- (experiment, EditingWorkbench empty, workbench %s) enter median %s, leave median %s"
            % (S.get("exp_workbench"), ms(statistics.median(S["exp_enter"])), ms(statistics.median(S["exp_leave"])))
        )
    lines.append("")
    for label, text in S["profiles"].items():
        lines += ["## %s" % label, "", "```", text.strip(), "```", ""]
    path = os.path.join(out_dir(), "sketch-enter-report.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    for ln in lines[:7]:
        if ln:
            print("[SciForge] %s" % ln, flush=True)
    h.check("report written", os.path.exists(path))


h.run("sketch_enter_perf", [first_enter, rounds, no_switch_experiment, report])
