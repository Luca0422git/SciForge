# SPDX-License-Identifier: LGPL-2.1-or-later
"""CREATE > Create Flat Pattern of the SHEET METAL tab and the FLAT PATTERN environment
(Fusion's behaviour; flatpattern.py does the work).

Create Flat Pattern: pick the stationary face (a flat top or bottom face of a wall, never an
edge face); the dialog says the flat size or why the part cannot be laid flat. OK makes the
Flat Pattern (one per component, under it in the browser) and opens it: the design's tabs
give way to the FLAT PATTERN tab (Export DXF, Finish Flat Pattern), the folded part is hidden
and the flat part is shown from the top with its bend lines. Finish Flat Pattern goes back.
Double-click the Flat Pattern in the browser (or right-click > Edit Flat Pattern) to open it
again; it follows edits of the folded part.

Export DXF: the outline, the holes, the bend centre lines (up / down) and extent lines and
bend notes, each on its own layer (flatpattern_dxf), with Fusion's options: Export bend
center lines, Export bend extent lines, Convert Splines to Polylines and its tolerance.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, flatpattern, log, taskui, ui_icon_path, warn
from . import flatpattern_dxf as fdxf
from . import sheetmetal_unfold as unfolder
from .compat import QtCore, QtWidgets
from .unfold_panel import SheetPanel, planar_face

STATE = {"fp": None, "doc": None, "hidden": [], "camera": None}


# -- the environment ----------------------------------------------------------------------------
def _ribbon(on):
    try:
        from . import shell

        ribbon = shell.ribbon()
        if ribbon is not None and hasattr(ribbon, "set_flat_pattern_mode"):
            ribbon.set_flat_pattern_mode(on)
    except Exception as exc:
        warn("flat pattern tab: %s" % exc)


def active():
    """The flat pattern open now, or None."""
    fp = STATE["fp"]
    if fp is None:
        return None
    try:
        if not flatpattern.is_flat_pattern(fp):
            raise ValueError("gone")
    except Exception:
        STATE.update(fp=None, doc=None, hidden=[], camera=None)
        _ribbon(False)
        return None
    return fp


def enter(fp):
    """Open the flat pattern: only it is shown, from the top; the FLAT PATTERN tab."""
    try:
        if active() is fp:
            return True
        if active() is not None:
            leave()
        if not commands.finish_open_dialog():
            return False
        doc = fp.Document
        if doc.Name != getattr(App.ActiveDocument, "Name", None):
            App.setActiveDocument(doc.Name)
        gdoc = Gui.getDocument(doc.Name)
        hidden = []
        for obj in doc.Objects:
            if obj is fp or obj.TypeId in ("App::Part", "App::Origin"):
                continue
            vobj = getattr(obj, "ViewObject", None)
            try:
                if vobj is not None and vobj.Visibility:
                    vobj.Visibility = False
                    hidden.append(obj.Name)
            except Exception:
                continue
        camera = None
        try:
            camera = gdoc.ActiveView.getCamera()
        except Exception:
            pass
        STATE.update(fp=fp, doc=doc.Name, hidden=hidden, camera=camera)
        if "Invalid" in list(fp.State) or fp.Shape.isNull() or doc.isTouched():
            # the flat pattern is computed when it opens (after an undo / redo too)
            doc.recompute()
        if fp.ViewObject is not None:
            fp.ViewObject.Visibility = True
        _ribbon(True)
        try:
            gdoc.ActiveView.viewTop()
            gdoc.ActiveView.fitAll()
        except Exception:
            pass
        log("flat pattern %s open" % fp.Label)
        if "Invalid" in list(fp.State):
            commands.tell("The flat pattern cannot be computed: %s" % fp.getStatusString())
        return True
    except Exception as exc:
        warn("flat pattern could not open: %s" % exc)
        return False


def leave():
    """Finish Flat Pattern: back to the folded part as it was shown."""
    fp = STATE["fp"]
    doc = App.getDocument(STATE["doc"]) if STATE["doc"] in App.listDocuments() else None
    hidden = list(STATE["hidden"])
    camera = STATE["camera"]
    STATE.update(fp=None, doc=None, hidden=[], camera=None)
    _ribbon(False)
    if doc is None:
        return
    try:
        if fp is not None and flatpattern.is_flat_pattern(fp) and fp.ViewObject is not None:
            fp.ViewObject.Visibility = False
        for name in hidden:
            obj = doc.getObject(name)
            if obj is not None and getattr(obj, "ViewObject", None) is not None:
                obj.ViewObject.Visibility = True
        if camera:
            Gui.getDocument(doc.Name).ActiveView.setCamera(camera)
        log("flat pattern closed")
    except Exception as exc:
        warn("finish flat pattern: %s" % exc)


def _show_folded(doc, folded):
    """The objects hidden for the open flat pattern shown again (folded=True), or hidden
    again with the flat shown; the environment's state stays as it is."""
    fp = STATE["fp"]
    for name in STATE["hidden"]:
        obj = doc.getObject(name)
        if obj is not None and getattr(obj, "ViewObject", None) is not None:
            obj.ViewObject.Visibility = folded
    if fp is not None and flatpattern.is_flat_pattern(fp) and fp.ViewObject is not None:
        fp.ViewObject.Visibility = not folded


class _DocWatch:
    """Close the environment when its document closes or an undo takes the flat away."""

    def slotDeletedDocument(self, doc):
        try:
            if STATE["doc"] == doc.Name:
                STATE.update(fp=None, doc=None, hidden=[], camera=None)
                _ribbon(False)
        except Exception as exc:
            warn("flat pattern watch: %s" % exc)

    def slotDeletedObject(self, obj):
        try:
            if STATE["fp"] is not None and obj is STATE["fp"]:
                QtCore.QTimer.singleShot(0, leave)
        except Exception as exc:
            warn("flat pattern watch: %s" % exc)

    def slotStartSaveDocument(self, doc, filename):
        """Saved while the flat pattern is open: the file keeps the folded part shown."""
        try:
            if STATE["doc"] == doc.Name:
                _show_folded(doc, True)
        except Exception as exc:
            warn("flat pattern save: %s" % exc)

    def slotFinishSaveDocument(self, doc, filename):
        try:
            if STATE["doc"] == doc.Name:
                _show_folded(doc, False)
        except Exception as exc:
            warn("flat pattern save: %s" % exc)

    def slotActivateDocument(self, doc):
        """Another design's tab: the open flat pattern is finished (its design keeps the
        folded part shown)."""
        try:
            if STATE["doc"] and doc is not None and doc.Name != STATE["doc"]:
                QtCore.QTimer.singleShot(0, leave)
        except Exception as exc:
            warn("flat pattern watch: %s" % exc)

    def slotUndoDocument(self, doc):
        self._check(doc)

    def slotRedoDocument(self, doc):
        self._check(doc)

    def _check(self, doc):
        try:
            if STATE["doc"] == doc.Name:
                QtCore.QTimer.singleShot(0, active)
        except Exception as exc:
            warn("flat pattern watch: %s" % exc)


_WATCH = {"obj": None}


def _install_watch():
    try:
        if _WATCH["obj"] is None:
            _WATCH["obj"] = _DocWatch()
            App.addDocumentObserver(_WATCH["obj"])
    except Exception as exc:
        warn("flat pattern watch: %s" % exc)


_install_watch()


# -- the browser node ---------------------------------------------------------------------------
class ViewProviderFlatPattern:
    """Saved files store "sciforge.flatpattern_ui.ViewProviderFlatPattern": never rename."""

    OUTLINE = (0.1, 0.1, 0.12)
    UP = (0.85, 0.15, 0.15)  # bend centre lines folding up (Fusion's help shows them red)
    DOWN = (0.15, 0.35, 0.85)
    EXTENT = (0.45, 0.45, 0.5)

    def __init__(self, vobj):
        vobj.Proxy = self
        try:
            vobj.Visibility = False
        except Exception:
            pass

    def attach(self, vobj):
        self.Object = vobj.Object

    def updateData(self, obj, prop):
        """Bend centre lines red (up) / blue (down), extent lines grey, outline dark."""
        if prop != "Shape":
            return
        try:
            vobj = obj.ViewObject
            if vobj is None or "LineColorArray" not in vobj.PropertiesList:
                return
            kinds = flatpattern.line_kinds(obj)
            edges = obj.Shape.Edges
            colors = [self.OUTLINE] * max(0, len(edges) - len(kinds))
            look = {"up": self.UP, "down": self.DOWN, "extent": self.EXTENT}
            colors += [look[k] for k in kinds]
            if len(colors) == len(edges) and colors:
                vobj.LineColorArray = colors
        except Exception as exc:
            warn("flat pattern colours: %s" % exc)

    def getIcon(self):
        return ui_icon_path("flat_pattern")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        QtCore.QTimer.singleShot(0, lambda: enter(vobj.Object))
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        QtCore.QTimer.singleShot(0, lambda: enter(vobj.Object))
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def edit_flat_pattern(fp):
    enter(fp)


def toggle(fp, prop):
    """Browser > Show/Hide Bend Lines or Bend Extents (one undo step)."""
    try:
        if not commands.finish_open_dialog():
            return
        doc = fp.Document
        doc.openTransaction("Show/Hide Bend Lines")
        setattr(fp, prop, not getattr(fp, prop))
        doc.recompute()
        doc.commitTransaction()
    except Exception as exc:
        warn("flat pattern %s: %s" % (prop, exc))


# -- Create Flat Pattern ------------------------------------------------------------------------
class CreateFlatPatternPanel(SheetPanel):
    title = "Create Flat Pattern"
    icon = "sm_flat_pattern"
    SLOTS = (("face", "Stationary Face", planar_face, False),)

    def __init__(self, doc):
        self.made = None
        super().__init__(doc, "Create Flat Pattern")

    def build_fields(self):
        self.add_slot_rows()
        self.info = QtWidgets.QLabel("Pick a flat top or bottom face of a wall: it lies on XY.")
        self.info.setWordWrap(True)
        self.layout.addRow(self.info)

    def update(self):
        try:
            self._update()
        except Exception as exc:
            self.say("⚠ %s" % exc)

    def _update(self):
        face = self.pick("face")
        if not face:
            self.say("")
            return
        other = flatpattern.of_component(self.doc, _container(self.body))
        if other is not None:
            self.say(
                "⚠ This component already has a flat pattern (Fusion keeps one per "
                "component): double-click it in the browser, or delete it first."
            )
            return
        try:
            result = unfolder.unfold(self.base.Shape, face, _k(self.body))
        except unfolder.UnfoldError as exc:
            self.say("⚠ %s" % exc)
            return
        frame = unfolder.flat_frame(result)
        flat = result.shape.copy()
        flat.transformShape(frame)
        bb = flat.BoundBox
        self.say("")
        self.info.setText(
            "Flat: %.2f x %.2f mm, %d bend(s), thickness %.2f mm."
            % (bb.XLength, bb.YLength, len(result.bends), result.thickness)
        )

    def ready(self):
        face = self.pick("face")
        if not face:
            return "Pick the stationary face first."
        try:
            self.made = flatpattern.create(self.body, face)
        except flatpattern.FlatPatternError as exc:
            return str(exc)
        return None

    def feature(self):
        return self.made

    def accept(self):
        ok = super().accept()
        if ok and self.made is not None:
            fp = self.made
            QtCore.QTimer.singleShot(0, lambda: enter(fp))
        return ok


def _container(body):
    from . import components

    return components.container_of(body)


def _k(body):
    from . import sheetmetal_flat

    return sheetmetal_flat.k_factor(body)


# -- Export DXF ---------------------------------------------------------------------------------
def default_path(fp):
    doc = fp.Document
    folder = os.path.dirname(doc.FileName) if doc.FileName else os.path.expanduser("~")
    body = fp.Body.Label if fp.Body is not None else "part"
    return os.path.join(folder, "%s flat pattern.dxf" % body)


class ExportPanel(taskui.Panel):
    """Export Flat Pattern as DXF (the file name, the options, OK writes it)."""

    title = "Export DXF"
    icon = "fp_export_dxf"
    last = None

    def __init__(self, fp):
        super().__init__(fp.Document, "Export DXF")
        ExportPanel.last = self
        self.fp = fp
        self.written = None
        row = QtWidgets.QHBoxLayout()
        self.path = QtWidgets.QLineEdit(default_path(fp))
        self.path.setObjectName("SciForgeDxfPath")
        browse = QtWidgets.QPushButton("…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        self.layout.addRow("File", row)
        opts = fdxf.DEFAULT_OPTIONS
        self.centre = QtWidgets.QCheckBox("Export bend center lines")
        self.centre.setChecked(opts["center_lines"])
        self.extent = QtWidgets.QCheckBox("Export bend extent lines")
        self.extent.setChecked(opts["extent_lines"])
        self.polylines = QtWidgets.QCheckBox("Convert Splines to Polylines")
        self.polylines.setChecked(opts["splines_to_polylines"])
        self.tolerance = taskui.DistanceField(opts["tolerance"])
        for box in (self.centre, self.extent, self.polylines):
            self.layout.addRow(box)
        self.layout.addRow("Tolerance", self.tolerance.widget)
        self.polylines.toggled.connect(self.tolerance.widget.setEnabled)
        self.tolerance.widget.setEnabled(self.polylines.isChecked())
        self.finish_layout()

    def _browse(self):
        try:
            path, _f = QtWidgets.QFileDialog.getSaveFileName(
                Gui.getMainWindow(), "Export DXF", self.path.text(), "DXF (*.dxf)"
            )
            if path:
                self.path.setText(path)
        except Exception as exc:
            warn("Export DXF browse: %s" % exc)

    def options(self):
        return {
            "center_lines": self.centre.isChecked(),
            "extent_lines": self.extent.isChecked(),
            "splines_to_polylines": self.polylines.isChecked(),
            "tolerance": self.tolerance.value(),
        }

    def accept(self):
        path = self.path.text().strip()
        if not path:
            self.message.setText("⚠ Give the file a name.")
            return False
        try:
            self.written = flatpattern.export_dxf(self.fp, path, self.options())
        except Exception as exc:
            self.message.setText("⚠ The DXF could not be written: %s" % exc)
            return False
        commands.tell("Flat pattern saved as %s" % os.path.basename(self.written))
        return super().accept()


def export_dialog(fp=None):
    try:
        fp = fp or active()
        if fp is None:
            commands.tell("Open a flat pattern first (double-click it in the browser).")
            return
        if not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(ExportPanel(fp))
    except Exception as exc:
        warn("Export DXF failed to start: %s" % exc)


# -- commands -----------------------------------------------------------------------------------
def _start_create():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            return
        from . import sheetmetal

        if not sheetmetal.sheet_metal_bodies(doc):
            commands.tell(
                "A flat pattern is made of a sheet metal body: make a Flange or use Convert "
                "to Sheet Metal first."
            )
            return
        Gui.Control.showDialog(CreateFlatPatternPanel(doc))
        log("create flat pattern started")
    except Exception as exc:
        warn("Create Flat Pattern failed to start: %s" % exc)


class CreateFlatPatternCommand:
    def GetResources(self):
        return {
            "MenuText": "Create Flat Pattern",
            "ToolTip": "Lay the sheet metal part flat from a top or bottom face",
            "Pixmap": ui_icon_path("sm_flat_pattern"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start_create()


class ExportDxfCommand:
    def GetResources(self):
        return {
            "MenuText": "Export DXF",
            "ToolTip": "The open flat pattern as DXF, bend lines on their own layers",
            "Pixmap": ui_icon_path("fp_export_dxf"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        export_dialog()


class FinishFlatPatternCommand:
    def GetResources(self):
        return {
            "MenuText": "Finish Flat Pattern",
            "ToolTip": "Back to the folded part",
            "Pixmap": ui_icon_path("fp_finish"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            leave()
        except Exception as exc:
            warn("Finish Flat Pattern: %s" % exc)


COMMANDS = {
    "SciForge_CreateFlatPattern": CreateFlatPatternCommand,
    "SciForge_FlatPatternExportDXF": ExportDxfCommand,
    "SciForge_FinishFlatPattern": FinishFlatPatternCommand,
}
EDITORS = {"SciForge::FlatPattern": edit_flat_pattern}
