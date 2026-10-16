# SciForge workbench registration. FreeCAD executes this file at startup.
import FreeCAD
import FreeCADGui


class SciForgeWorkbench(FreeCADGui.Workbench):
    def __init__(self):
        import sciforge

        self.__class__.MenuText = "SciForge"
        self.__class__.ToolTip = "Fusion-style workflow layer for FreeCAD"
        self.__class__.Icon = sciforge.icon_path("sciforge.svg")

    def Initialize(self):
        # Runs once, the first time the workbench is selected.
        try:
            from sciforge import workbench

            workbench.build(self)
        except Exception as exc:  # never take FreeCAD down with us
            import traceback

            FreeCAD.Console.PrintError("[SciForge] Initialize failed: %s\n" % exc)
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")

    def Activated(self):
        try:
            from sciforge import workbench

            workbench.activated()
        except Exception as exc:
            FreeCAD.Console.PrintError("[SciForge] Activated failed: %s\n" % exc)

    def Deactivated(self):
        try:
            from sciforge import workbench

            workbench.deactivated()
        except Exception as exc:
            FreeCAD.Console.PrintError("[SciForge] Deactivated failed: %s\n" % exc)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(SciForgeWorkbench())

# FreeCAD opens in SciForge (Preferences > General > Start in SciForge). FreeCAD picks the
# workbench it opens in after every InitGui.py has run, so this counts for this start.
try:
    from sciforge import start_in

    start_in.at_launch()
except Exception as _exc:
    FreeCAD.Console.PrintError("[SciForge] start in SciForge: %s\n" % _exc)


def _sciforge_startup():
    try:
        from sciforge import shell

        shell.startup()
    except Exception as exc:  # never take FreeCAD down with us
        FreeCAD.Console.PrintError("[SciForge] startup check failed: %s\n" % exc)


# Once FreeCAD's window runs: follow workbench changes (see shell.startup).
try:
    from PySide import QtCore

    QtCore.QTimer.singleShot(0, _sciforge_startup)
except Exception as _exc:
    FreeCAD.Console.PrintError("[SciForge] startup check not scheduled: %s\n" % _exc)
