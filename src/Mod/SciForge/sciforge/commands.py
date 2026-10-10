"""SciForge's own commands plus the drop-down group commands."""

import FreeCAD as App
import FreeCADGui as Gui

from . import config, icon_path, log, registry, warn


def active_body():
    try:
        view = Gui.ActiveDocument.ActiveView
        return view.getActiveObject("pdbody")
    except Exception:
        return None


def find_body():
    """The active body; else the body of the selection or the document's first body,
    which is then made active (a reopened file has no active body)."""
    body = active_body()
    if body is not None:
        return body
    doc = App.ActiveDocument
    if doc is None:
        return None
    candidates = []
    for sel in Gui.Selection.getSelectionEx():
        parent = sel.Object.getParentGeoFeatureGroup()
        if parent is not None and parent.TypeId == "PartDesign::Body":
            candidates.append(parent)
        elif sel.Object.TypeId == "PartDesign::Body":
            candidates.append(sel.Object)
    candidates += doc.findObjects("PartDesign::Body")
    if not candidates:
        return None
    try:
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", candidates[0])
    except Exception as exc:
        warn("could not activate %s: %s" % (candidates[0].Label, exc))
    return candidates[0]


def tell(msg):
    """A short message next to the mouse pointer (and in the log), for when a command
    cannot start: silence made it look like the keys and buttons were broken."""
    log(msg)
    try:
        from .compat import QtGui, QtWidgets

        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), msg, Gui.getMainWindow())
    except Exception:
        pass


def leave_edit():
    """Finish the edit in progress. A sketch is closed with FreeCAD's own Finish Sketch,
    which first stops the active drawing tool: a plain resetEdit() with a tool still
    running crashes FreeCAD 1.1 (SketcherGui solver update on a closing view)."""
    gdoc = Gui.ActiveDocument
    if gdoc is None or gdoc.getInEdit() is None:
        return
    obj = gdoc.getInEdit().Object
    if obj is not None and obj.TypeId == "Sketcher::SketchObject":
        Gui.runCommand("Sketcher_LeaveSketch")
    else:
        gdoc.resetEdit()
    if App.ActiveDocument is not None:
        App.ActiveDocument.recompute()


def finish_open_dialog():
    """Fusion: starting a command ends the one in progress. SciForge dialogs are
    finished (OK, or Cancel if OK is not possible) and a sketch being edited is
    closed. Returns True when nothing is open any more."""
    if not Gui.Control.activeDialog():
        return True
    from . import taskui

    current = taskui.current()
    try:
        if current is not None:
            current.finish()
        elif Gui.ActiveDocument is not None and Gui.ActiveDocument.getInEdit() is not None:
            leave_edit()
    except Exception as exc:
        warn("could not close the open dialog: %s" % exc)
    if Gui.Control.activeDialog():
        tell("Finish the open command first (OK or Cancel in the panel on the right).")
        return False
    return True


def ensure_body():
    """Make sure a document and an active PartDesign body exist, like Fusion
    quietly creating a component. Returns the body or None."""
    if App.ActiveDocument is None:
        App.newDocument("Design")
    doc = App.ActiveDocument
    body = find_body()
    if body is not None:
        return body
    try:
        Gui.runCommand("PartDesign_Body")
    except Exception:
        body = doc.addObject("PartDesign::Body", "Body")
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        doc.recompute()
        return body
    return active_body()


class _Command:
    title = ""
    tip = ""
    icon = ""

    def GetResources(self):
        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            res["Pixmap"] = icon_path(self.icon)
        return res

    def IsActive(self):
        return True


class NewDesign(_Command):
    title = "New Design"
    tip = "Start a design: creates a document and a body if needed"
    icon = "design.svg"

    def Activated(self):
        ensure_body()


class NewSketch(_Command):
    title = "Create Sketch"
    tip = "Create a sketch: click an origin plane or a flat face (creates a body if needed)"
    icon = "sketch.svg"

    def Activated(self):
        try:
            from . import sketch_ui

            if finish_open_dialog():
                sketch_ui.start()
        except Exception as exc:
            warn("Create Sketch failed to start: %s" % exc)


class CommandSearch(_Command):
    title = "Search Commands"
    tip = "Find and run any command by name"
    icon = "search.svg"

    def Activated(self):
        from . import search_ui

        search_ui.show()


class ToggleTimeline(_Command):
    title = "Toggle Timeline"
    tip = "Show or hide the feature timeline"
    icon = "timeline.svg"

    def Activated(self):
        from . import timeline_ui

        timeline_ui.toggle()


class ResetShortcuts(_Command):
    title = "Restore Original Shortcuts"
    tip = "Undo the Fusion-style shortcut map"

    def Activated(self):
        from . import shortcuts

        shortcuts.restore()


class Diagnostics(_Command):
    title = "Diagnostics"
    tip = "Show versions and any commands SciForge could not find"

    def Activated(self):
        from . import diagnostics

        diagnostics.show()


class GroupCommand:
    """A toolbar drop-down that holds several existing commands."""

    def __init__(self, title, tip, commands):
        self._title = title
        self._tip = tip
        self._commands = list(commands)

    def GetCommands(self):
        return tuple(self._commands)

    def GetDefaultCommand(self):
        return 0

    def GetResources(self):
        return {"MenuText": self._title, "ToolTip": self._tip}

    def Activated(self, index=0):
        Gui.runCommand(self._commands[index])

    def IsActive(self):
        return True


FORGE_COMMANDS = {
    "SciForge_NewDesign": NewDesign,
    "SciForge_NewSketch": NewSketch,
    "SciForge_CommandSearch": CommandSearch,
    "SciForge_ToggleTimeline": ToggleTimeline,
    "SciForge_ResetShortcuts": ResetShortcuts,
    "SciForge_Diagnostics": Diagnostics,
}


def _feature_commands():
    """Commands implemented in their own modules (imported lazily: they need the GUI).

    Every sciforge/*_ui.py module that defines a module-level
    COMMANDS = {"SciForge_Name": CommandClass, ...} (and optionally EDITORS) is registered
    automatically, so a new feature only adds its own file. Each module is loaded on its
    own: one that fails to import is reported and skipped, it never takes the other
    commands down with it."""
    import importlib
    import os

    from . import taskui

    # Older modules that expose their commands differently.
    legacy = {
        "extrude_ui": lambda m: {"SciForge_Extrude": m.ExtrudeCommand},
        "presspull_ui": lambda m: {"SciForge_PressPull": m.PressPullCommand},
        "parameters_ui": lambda m: {"SciForge_ChangeParameters": m.ChangeParametersCommand},
        "construct_ui": lambda m: m.command_classes(),
        "make3d_ui": lambda m: {"SciForge_3DPrint": m.PrintCommand},
    }
    found = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for filename in sorted(os.listdir(here)):
        if not filename.endswith("_ui.py"):
            continue
        name = filename[:-3]
        try:
            module = importlib.import_module("." + name, __package__)
            if name in legacy:
                found.update(legacy[name](module))
            found.update(getattr(module, "COMMANDS", {}))
            taskui.EDITORS.update(getattr(module, "EDITORS", {}))
        except Exception as exc:
            warn("could not load %s: %s" % (filename, exc))
    return found


def register_all():
    commands = dict(FORGE_COMMANDS)
    try:
        commands.update(_feature_commands())
    except Exception as exc:
        warn("could not load feature commands: %s" % exc)
    for name, cls in commands.items():
        try:
            Gui.addCommand(name, cls())
        except Exception as exc:
            warn("could not register %s: %s" % (name, exc))


def resolve_groups(available):
    """Resolve every group to the commands that exist. {group_id: [names]}"""
    groups = {}
    for group_id, spec in config.GROUPS.items():
        found, missing = registry.resolve_many(spec["commands"], available)
        registry.MISSING.extend(missing)
        groups[group_id] = found
    return groups


def register_groups(groups):
    for group_id, found in groups.items():
        if not found:
            continue
        spec = config.GROUPS[group_id]
        try:
            Gui.addCommand(group_id, GroupCommand(spec["title"], spec["tip"], found))
        except Exception as exc:
            warn("could not register group %s: %s" % (group_id, exc))
