"""Forge's own commands plus the drop-down group commands."""
import FreeCAD as App
import FreeCADGui as Gui

from . import config, icon_path, registry, warn


def active_body():
    try:
        view = Gui.ActiveDocument.ActiveView
        return view.getActiveObject("pdbody")
    except Exception:
        return None


def ensure_body():
    """Make sure a document and an active PartDesign body exist, like Fusion
    quietly creating a component. Returns the body or None."""
    doc = App.ActiveDocument or App.newDocument("Design")
    body = active_body()
    if body is not None:
        return body
    existing = doc.findObjects("PartDesign::Body")
    if existing:
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", existing[0])
        return existing[0]
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
    tip = "Create a sketch on a plane or face (creates a body first if needed)"
    icon = "sketch.svg"

    def Activated(self):
        ensure_body()
        Gui.runCommand("Sketcher_NewSketch")


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
    tip = "Show versions and any commands Forge could not find"

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
    "Forge_NewDesign": NewDesign,
    "Forge_NewSketch": NewSketch,
    "Forge_CommandSearch": CommandSearch,
    "Forge_ToggleTimeline": ToggleTimeline,
    "Forge_ResetShortcuts": ResetShortcuts,
    "Forge_Diagnostics": Diagnostics,
}


def register_all():
    for name, cls in FORGE_COMMANDS.items():
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
