# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD opened in SciForge a second time (Luca, 2026-10-17: the second start showed only
the browser and an empty view). Run twice with one profile by run_tests.sh:

    SCIFORGE_SMOKE_OUT=/dir SCIFORGE_RESTART_PHASE=1 FreeCAD restart_gui.py
    SCIFORGE_SMOKE_OUT=/dir SCIFORGE_RESTART_PHASE=2 FreeCAD restart_gui.py

Each start checks that SciForge's ribbon, document tabs bar and timeline are shown, then
closes the window as a person does (FreeCAD saves its window layout then), and writes
restart-<phase>.json.
"""

import json
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT_DIR = os.environ.get("SCIFORGE_SMOKE_OUT") or App.getUserAppDataDir()
PHASE = os.environ.get("SCIFORGE_RESTART_PHASE", "1")
checks = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print("[SciForge] restart %s %s: %s %s" % (PHASE, "PASS" if ok else "FAIL", name, detail))


def run():
    main = Gui.getMainWindow()
    try:
        wb = Gui.activeWorkbench()
        check("opens in SciForge", wb is not None and wb.name() == "SciForgeWorkbench", wb)
        ribbon = main.findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
        check("the ribbon is shown", ribbon is not None and ribbon.isVisible())
        tabs = main.findChild(QtWidgets.QTabBar, "SciForgeDocumentTabs")
        check("the document tabs bar exists", tabs is not None)
        timeline = main.findChild(QtWidgets.QDockWidget, "SciForgeTimelineDock")
        check("the timeline is shown", timeline is not None and timeline.isVisible())
        check("FreeCAD's menu bar is hidden", not main.menuBar().isVisible())
        try:
            main.grab().save(os.path.join(OUT_DIR, "restart-%s.png" % PHASE))
        except Exception:
            pass
    except Exception as exc:
        check("no exception", False, exc)
    with open(os.path.join(OUT_DIR, "restart-%s.json" % PHASE), "w") as handle:
        json.dump({"passed": all(c["ok"] for c in checks), "checks": checks}, handle, indent=2)
    QtCore.QTimer.singleShot(300, main.close)  # (FreeCAD saves the window layout here)


QtCore.QTimer.singleShot(8000, run)
