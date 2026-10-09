"""Forge: a Fusion-style workflow layer for FreeCAD.

This package must stay importable outside FreeCAD (the *_core modules are
pure Python and are unit tested), so nothing here imports FreeCAD or Qt at
module level except inside the logging helpers.
"""
import os

__version__ = "0.1.0"
ROOT = os.path.dirname(os.path.abspath(__file__))


def icon_path(name):
    return os.path.join(ROOT, "icons", name)


def _console():
    try:
        import FreeCAD

        return FreeCAD.Console
    except ImportError:
        return None


def log(msg):
    console = _console()
    if console:
        console.PrintMessage("[Forge] %s\n" % msg)
    else:
        print("[Forge] %s" % msg)


def warn(msg):
    console = _console()
    if console:
        console.PrintWarning("[Forge] %s\n" % msg)
    else:
        print("[Forge] WARNING: %s" % msg)
