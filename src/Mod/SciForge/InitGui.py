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
