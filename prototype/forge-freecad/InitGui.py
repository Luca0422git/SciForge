# Forge workbench registration. FreeCAD executes this file at startup.
import FreeCAD
import FreeCADGui


class ForgeWorkbench(FreeCADGui.Workbench):
    def __init__(self):
        import forgecad

        self.__class__.MenuText = "Forge"
        self.__class__.ToolTip = "Fusion-style workflow layer for FreeCAD"
        self.__class__.Icon = forgecad.icon_path("forge.svg")

    def Initialize(self):
        # Runs once, the first time the workbench is selected.
        try:
            from forgecad import workbench

            workbench.build(self)
        except Exception as exc:  # never take FreeCAD down with us
            import traceback

            FreeCAD.Console.PrintError("[Forge] Initialize failed: %s\n" % exc)
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")

    def Activated(self):
        try:
            from forgecad import workbench

            workbench.activated()
        except Exception as exc:
            FreeCAD.Console.PrintError("[Forge] Activated failed: %s\n" % exc)

    def Deactivated(self):
        try:
            from forgecad import workbench

            workbench.deactivated()
        except Exception as exc:
            FreeCAD.Console.PrintError("[Forge] Deactivated failed: %s\n" % exc)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(ForgeWorkbench())
