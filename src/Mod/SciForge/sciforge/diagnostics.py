"""SciForge > Diagnostics: what version am I on and what could not be found?"""

import sys

import FreeCAD as App

from . import __version__, registry


def report():
    try:
        fc_version = ".".join(str(p) for p in App.Version()[:3])
    except Exception:
        fc_version = "unknown"
    try:
        from .compat import QtCore

        qt = QtCore.qVersion()
    except Exception:
        qt = "unknown"
    lines = [
        "SciForge %s" % __version__,
        "FreeCAD %s" % fc_version,
        "Python %s" % sys.version.split()[0],
        "Qt %s" % qt,
        "",
    ]
    if registry.MISSING:
        lines.append("Commands not found in this FreeCAD (skipped):")
        lines.extend("  - %s" % m for m in sorted(set(registry.MISSING)))
    else:
        lines.append("All configured commands were found.")
    return "\n".join(lines)


def show():
    text = report()
    App.Console.PrintMessage("[SciForge] diagnostics\n%s\n" % text)
    try:
        import FreeCADGui as Gui
        from .compat import QtWidgets

        box = QtWidgets.QMessageBox(Gui.getMainWindow())
        box.setWindowTitle("SciForge Diagnostics")
        box.setText(text)
        box.exec_()
    except Exception:
        pass
