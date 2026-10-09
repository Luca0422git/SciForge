"""Runs InitGui.py and the whole workbench against a fake FreeCAD and Qt.

This cannot prove the GUI looks right (only real FreeCAD can), but it catches
import errors, typos, bad wiring and crashes in Initialize/Activated/
Deactivated before you ever open FreeCAD.
"""

import os
import sys
import tempfile
import types
import unittest

# The module root (src/Mod/SciForge), where InitGui.py lives.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any


class _Any(metaclass=_Meta):
    """Stands in for any Qt class, instance, enum or signal."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Any()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()

    def __iter__(self):
        return iter(())


def _purge_sciforge():
    """Drop sciforge and its submodules so the next import is fresh."""
    for name in list(sys.modules):
        if name == "sciforge" or name.startswith("sciforge."):
            del sys.modules[name]


def _anything_module(name):
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda attr: _Any
    return mod


class FakeCommand:
    def __init__(self):
        self.shortcut = ""

    def getShortcut(self):
        return self.shortcut

    def setShortcut(self, key):
        self.shortcut = key
        return True

    def getInfo(self):
        return {"menuText": "Fake", "shortcut": self.shortcut}


class FakeWorkbench:
    # Real FreeCAD does not call the base __init__ either, so build lazily.
    def appendToolbar(self, name, cmds):
        self.__dict__.setdefault("toolbars", {})[name] = list(cmds)

    def appendMenu(self, name, cmds):
        key = tuple(name) if isinstance(name, list) else (name,)
        self.__dict__.setdefault("menus", {})[key] = list(cmds)


REAL_COMMANDS = [
    "PartDesign_Pad",
    "PartDesign_Fillet",
    "PartDesign_Hole",
    "PartDesign_Pocket",
    "Sketcher_NewSketch",
    "Sketcher_CreateLine",
    "Sketcher_CreateCircle",
    "Sketcher_CreateRectangle",
    "Sketcher_Trimming",
    "Sketcher_ToggleConstruction",
    "Sketcher_LeaveSketch",
    "Sketcher_Dimension",
    "Std_ViewFitAll",
    "Std_ViewIsometric",
]


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self._saved_modules = dict(sys.modules)
        self.registered = {}
        self.commands = {n: FakeCommand() for n in REAL_COMMANDS}
        self.workbenches = []
        registered = self.registered
        commands = self.commands
        workbenches = self.workbenches
        user_dir = tempfile.mkdtemp()

        self.errors = errors = []
        fc = types.ModuleType("FreeCAD")
        fc.Console = types.SimpleNamespace(
            PrintMessage=lambda m: None,
            PrintWarning=lambda m: None,
            PrintError=lambda m: errors.append(m),
        )
        fc.Version = lambda: ["1", "1", "4", "0000"]
        fc.getUserAppDataDir = lambda: user_dir
        fc.ActiveDocument = None

        gui = types.ModuleType("FreeCADGui")
        gui.Workbench = FakeWorkbench
        gui.addWorkbench = lambda wb: workbenches.append(wb)
        gui.listCommands = lambda: list(commands) + list(registered)
        gui.addCommand = lambda name, obj: registered.__setitem__(name, obj)
        gui.Command = types.SimpleNamespace(get=lambda n: commands.get(n))
        gui.runCommand = lambda *a, **k: None
        gui.getMainWindow = lambda: _Any()
        gui.ActiveDocument = None

        # Start from a clean sciforge so no stale submodule leaks between tests
        # (discovery may already have imported it for the other test files).
        _purge_sciforge()
        sys.modules.update(
            {
                "FreeCAD": fc,
                "FreeCADGui": gui,
                "PySide": _anything_module("PySide"),
                "PartGui": types.ModuleType("PartGui"),
                "PartDesignGui": types.ModuleType("PartDesignGui"),
                "SketcherGui": types.ModuleType("SketcherGui"),
            }
        )
        # PySide must expose QtCore/QtGui/QtWidgets as importable names
        for sub in ("QtCore", "QtGui", "QtWidgets"):
            sys.modules["PySide"].__dict__[sub] = _anything_module("PySide." + sub)
            sys.modules["PySide." + sub] = sys.modules["PySide"].__dict__[sub]
        sys.path.insert(0, ROOT)

    def tearDown(self):
        sys.path.remove(ROOT)
        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]
        sys.modules.update(self._saved_modules)
        _purge_sciforge()
        # Initialize/Activated swallow exceptions on purpose (so FreeCAD never
        # crashes); the test must still fail if they logged one. Checked last
        # so cleanup always runs first.
        self.assertEqual(self.errors, [], "workbench logged errors")

    def _load_workbench(self):
        with open(os.path.join(ROOT, "InitGui.py"), "r", encoding="utf-8") as handle:
            source = handle.read()
        exec(compile(source, "InitGui.py", "exec"), {"__name__": "InitGui"})
        self.assertEqual(len(self.workbenches), 1)
        return self.workbenches[0]

    def test_full_lifecycle(self):
        wb = self._load_workbench()
        self.assertEqual(wb.MenuText, "SciForge")

        wb.Initialize()
        self.assertIn("SciForge Design", wb.toolbars)
        design = wb.toolbars["SciForge Design"]
        self.assertIn("SciForge_NewDesign", design)
        self.assertIn("SciForge_GroupCreate", design)  # group registered, Pad exists
        self.assertIn("SciForge_GroupCreate", self.registered)
        group = self.registered["SciForge_GroupCreate"]
        self.assertEqual(group.GetCommands(), ("PartDesign_Pad",))
        self.assertIn(("SciForge",), wb.menus)

        wb.Activated()
        self.assertEqual(self.commands["PartDesign_Pad"].shortcut, "E")
        self.assertEqual(self.commands["Std_ViewFitAll"].shortcut, "F6")

        wb.Deactivated()
        self.assertEqual(self.commands["PartDesign_Pad"].shortcut, "")

    def test_flat_toolbar_mode(self):
        wb = self._load_workbench()
        import sciforge.config as config

        config.USE_DROPDOWNS = False
        wb.Initialize()
        self.assertNotIn("SciForge_GroupCreate", wb.toolbars["SciForge Design"])
        self.assertIn("PartDesign_Pad", wb.toolbars["SciForge Design"])

    def test_missing_commands_are_reported_not_fatal(self):
        wb = self._load_workbench()
        wb.Initialize()
        import sciforge.registry as registry

        self.assertIn("PartDesign_Chamfer", registry.MISSING)


if __name__ == "__main__":
    unittest.main()
