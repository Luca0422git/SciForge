"""SciForge > Diagnostics: what version am I on and what could not be found?"""

import sys

import FreeCAD as App

from . import RECENT, __version__, registry


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
    try:
        from . import build_info

        build = "%s %s" % (build_info.COMMIT, build_info.DATE)
    except Exception:
        build = "unknown"
    # Which program this is (SciForge.exe since the branding pass, FreeCAD.exe before it)
    # and where its settings live: a SciForge must say SciForge and %APPDATA%\SciForge, a
    # quick update on FreeCAD says FreeCAD and FreeCAD's folder.
    try:
        program = App.ConfigGet("ExeName")
        home = App.getHomePath()
        settings = App.getUserAppDataDir()
    except Exception:
        program = home = settings = "unknown"
    # The compiled part this build has (the update check installs the small module update only
    # over the same one; "unknown" for a source tree or a quick update from a test run).
    try:
        from . import update_core

        core_id = update_core.installed_core() or "unknown"
    except Exception:
        core_id = "unknown"
    lines = [
        "SciForge %s (build %s)" % (__version__, build.strip()),
        "FreeCAD %s" % fc_version,
        "Python %s" % sys.version.split()[0],
        "Qt %s" % qt,
        "Program: %s in %s" % (program, home),
        "Settings folder: %s" % settings,
        "Update core: %s" % core_id,
        "",
    ]
    if registry.MISSING:
        lines.append("Commands not found in this FreeCAD (skipped):")
        lines.extend("  - %s" % m for m in sorted(set(registry.MISSING)))
    else:
        lines.append("All configured commands were found.")
    lines += ["", "Recent SciForge messages (newest last):"]
    lines.extend("  " + m for m in RECENT[-60:])
    if not RECENT:
        lines.append("  (none)")
    return "\n".join(lines)


def show():
    text = report()
    App.Console.PrintMessage("[SciForge] diagnostics\n%s\n" % text)
    try:
        import FreeCADGui as Gui
        from .compat import QtGui, QtWidgets

        dialog = QtWidgets.QDialog(Gui.getMainWindow())
        dialog.setWindowTitle("SciForge Diagnostics")
        dialog.resize(760, 520)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(
            QtWidgets.QLabel("Select all and copy this text when reporting a problem:")
        )
        box = QtWidgets.QPlainTextEdit(text)
        box.setReadOnly(True)
        box.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(box)
        buttons = QtWidgets.QDialogButtonBox()
        copy = buttons.addButton("Copy", QtWidgets.QDialogButtonBox.ActionRole)
        copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(text))
        buttons.addButton(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec_()
    except Exception:
        pass
