# SPDX-License-Identifier: LGPL-2.1-or-later
"""Files in and out with their structure (Fusion's File > Open of a STEP / IGES file,
Insert STEP into the current design, right-click a sketch > Save As DXF, right-click a body
or component > Save As Mesh, right-click a linked component > Break Link). The file work is
in step_import.py, exchange.py and design_insert.py. Spec and sources:
docs/sciforge/parity/insert-export.md ("Part 2")."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, components, ui_icon_path, warn
from . import exchange_core as core
from .compat import QtCore, QtWidgets

# Tests put a function() -> path here instead of the system's Open dialog.
OPEN_PICKER = None
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"
OPEN_FILTER = (
    "Designs and CAD files (*.FCStd *.fcstd *.step *.stp *.STEP *.STP *.iges *.igs *.IGES "
    "*.IGS);;Designs (*.FCStd *.fcstd);;STEP files (*.step *.stp *.STEP *.STP);;IGES files "
    "(*.iges *.igs *.IGES *.IGS);;All files (*)"
)


def _refresh_browser():
    try:
        from . import browser_ui

        widget = browser_ui.widget()
        if widget is not None:
            widget.refresh(force=True)
    except Exception:
        pass


def place_after(doc_name, name):
    """Fusion's Initial Position after an insert: the Move dialog opens on the new
    component (Esc leaves it where it came in)."""

    def run():
        try:
            if doc_name not in App.listDocuments():
                return
            obj = App.getDocument(doc_name).getObject(name)
            if obj is None:
                return
            from . import component_move_ui

            component_move_ui.start(picks=[obj])
        except Exception as exc:
            warn("insert: the move could not start: %s" % exc)

    QtCore.QTimer.singleShot(0, run)


# -- File > Open -------------------------------------------------------------------------------
def pick_open_file():
    if OPEN_PICKER is not None:
        return OPEN_PICKER()
    try:
        prefs = App.ParamGet(PREFS)
        start = prefs.GetString("LastOpenFolder", "")
        if not start or not os.path.isdir(start):
            try:
                from . import versions_ui

                start = versions_ui.project_folder()
            except Exception:
                start = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            Gui.getMainWindow(), "Open", start, OPEN_FILTER
        )
        if path:
            prefs.SetString("LastOpenFolder", os.path.dirname(path))
            return path
    except Exception as exc:
        warn("open dialog: %s" % exc)
    return None


def open_file(path):
    """Open a design, or a STEP / IGES file as a new design with its components (Fusion
    uploads such a file and opens it as a design). Returns the document."""
    kind = core.file_kind(path)
    if kind == "design":
        from . import versions_ui

        return versions_ui.open_design(path)
    from . import step_import

    name = core.base_name(path)
    doc = App.newDocument(_doc_name(name))
    doc.Label = name
    try:
        made = step_import.import_file(doc, path, core.OPEN)
    except Exception:
        try:
            if App.GuiUp:
                Gui.getDocument(doc.Name).Modified = False
            App.closeDocument(doc.Name)
        except Exception:
            pass
        raise
    doc.recompute()
    step_import.apply_looks(made)
    try:
        Gui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass
    _refresh_browser()
    comps = [c for c in made.components]
    commands.tell(
        "Opened %s"
        % core.describe(len(comps), len(made.instances), len(made.bodies), os.path.basename(path))
    )
    return doc


def _doc_name(label):
    """A document name FreeCAD takes (letters, digits, underscores)."""
    import re

    name = re.sub(r"[^A-Za-z0-9_]", "_", label) or "Design"
    if name[0].isdigit():
        name = "D_" + name
    return name


class OpenCommand:
    """File > Open (Ctrl+O): a design, or a STEP / IGES file opened as a new design."""

    def GetResources(self):
        return {
            "MenuText": "Open",
            "ToolTip": "Open a design, or a STEP / IGES file as a new design with its components",
            "Pixmap": ui_icon_path("qa_open"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            path = pick_open_file()
            if path:
                open_file(path)
        except core.ExchangeError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("Open failed: %s" % exc)
            commands.tell("The file could not be opened: %s" % exc)


# -- Insert STEP into the current design -------------------------------------------------------
def insert_cad_file(path):
    """Insert a STEP / IGES file into the active design as one component (named after the
    file, its products nested in it), one undo step; then place it (Fusion's Initial
    Position). Returns the step_import.Made."""
    from . import step_import

    if App.ActiveDocument is None:
        App.newDocument("Design")
    doc = App.ActiveDocument
    parent = components.active_component(doc) if App.GuiUp else None
    doc.openTransaction("Insert STEP")
    try:
        made = step_import.import_file(doc, path, core.INSERT, parent)
    except Exception:
        doc.abortTransaction()
        App.closeActiveTransaction(True)
        doc.recompute()
        raise
    doc.commitTransaction()
    App.closeActiveTransaction()
    doc.recompute()
    step_import.apply_looks(made)
    try:
        Gui.Selection.clearSelection()
        Gui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass
    _refresh_browser()
    commands.tell(
        "Inserted %s. Place it with the arrows (or type the values), then OK."
        % core.describe(
            len(made.components) - 1, len(made.instances), len(made.bodies), os.path.basename(path)
        )
    )
    if made.top is not None:
        place_after(doc.Name, made.top.Name)
    return made


# -- Save As DXF / Save As Mesh ----------------------------------------------------------------
def _selected():
    try:
        return Gui.Selection.getSelectionEx()
    except Exception:
        return []


def selected_flat():
    """The sketch or flat face picked (window or browser), as (object, sub), or None."""
    from . import exchange

    for sel in _selected():
        subs = list(sel.SubElementNames) or [""]
        for sub in subs:
            found = exchange.flat_target(sel.Object, sub)
            if found is not None:
                return found
    return None


def save_as_dxf(target=None, path=None):
    """Right-click a sketch > Save As DXF (also a flat face from File > Export). Returns the
    path written, or None."""
    from . import export_ui, exchange

    target = target or selected_flat()
    if target is None:
        commands.tell("Select a sketch (or a flat face) first, then Save As DXF.")
        return None
    if path is None:
        start = os.path.join(export_ui._home(App.ActiveDocument), core.dxf_name(target[0].Label))
        path = export_ui._save_dialog("Save As DXF", start, "DXF (*.dxf)")
        if not path:
            return None
    written = exchange.export_dxf(target, path)
    export_ui._remember_folder(written)
    commands.tell("Saved %s as %s" % (target[0].Label, os.path.basename(written)))
    return written


class SaveAsDXFCommand:
    def GetResources(self):
        return {
            "MenuText": "Save As DXF",
            "ToolTip": "The sketch's curves as a DXF file (for laser and plasma cutting)",
            "Pixmap": ui_icon_path("export"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            save_as_dxf()
        except core.ExchangeError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("Save As DXF failed: %s" % exc)
            commands.tell("The DXF could not be saved: %s" % exc)


def save_as_mesh(obj=None):
    """Right-click a body or component > Save As Mesh: the Export dialog on it, a mesh type
    chosen (Fusion's Save As Mesh: Format, Unit Type, Structure, Refinement)."""
    from . import export_ui

    doc = App.ActiveDocument
    if doc is None:
        return None
    if obj is None:
        for sel in _selected():
            candidate = sel.Object
            if components.is_component(candidate) or bodies.is_body(candidate):
                obj = candidate
                break
            body = bodies.body_of(candidate)
            if body is not None:
                obj = body
                break
    if obj is None:
        commands.tell("Select a body or a component first, then Save As Mesh.")
        return None
    dialog = export_ui.ExportDialog(doc, preset=obj, mesh=True)
    dialog.show()
    return dialog


class SaveAsMeshCommand:
    def GetResources(self):
        return {
            "MenuText": "Save As Mesh",
            "ToolTip": "A body or component as 3MF, STL or OBJ",
            "Pixmap": ui_icon_path("export"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            save_as_mesh()
        except Exception as exc:
            warn("Save As Mesh failed: %s" % exc)


# -- Break Link --------------------------------------------------------------------------------
def break_link(component=None):
    """Right-click a linked component > Break Link: one undo step."""
    from . import design_insert

    if component is None:
        for sel in _selected():
            comp = components.component_of(sel.Object)
            if design_insert.is_linked(comp):
                component = comp
                break
    if component is None or not design_insert.is_linked(component):
        commands.tell("Select a component inserted from another design first.")
        return None
    if not commands.finish_open_dialog():
        return None
    doc = component.Document
    doc.openTransaction("Break Link")
    try:
        made = design_insert.break_link(component)
    except ValueError as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return None
    except Exception as exc:
        doc.abortTransaction()
        doc.recompute()
        warn("Break Link failed: %s" % exc)
        commands.tell("The link could not be broken: %s" % exc)
        return None
    doc.commitTransaction()
    _refresh_browser()
    commands.tell(
        "%s is now part of this design: its features can be edited here." % component.Label
    )
    return made


class BreakLinkCommand:
    def GetResources(self):
        return {
            "MenuText": "Break Link",
            "ToolTip": "Make an inserted design independent: its features are copied in",
            "Pixmap": ui_icon_path("insert_component"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            break_link()
        except Exception as exc:
            warn("Break Link failed: %s" % exc)


COMMANDS = {
    "SciForge_Open": OpenCommand,
    "SciForge_SaveAsDXF": SaveAsDXFCommand,
    "SciForge_SaveAsMesh": SaveAsMeshCommand,
    "SciForge_BreakLink": BreakLinkCommand,
}

try:
    from . import design_insert as _design_insert

    _design_insert.install_watch()
except Exception as _exc:  # pragma: no cover - only without a GUI
    warn("linked designs watch not installed: %s" % _exc)
