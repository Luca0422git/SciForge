# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export, 3D Print and Export Everything: the dialogs (Fusion's File > Export, Utilities >
Make > 3D Print, Save As Mesh). The file work is in export.py. Spec and sources:
docs/sciforge/parity/insert-export.md."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, export, log, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtGui, QtWidgets

# Tests replace these: the folder opener, the slicer starter and the file / folder dialogs.
OPEN_FOLDER = None
START_PROGRAM = None
SAVE_DIALOG = None
FOLDER_DIALOG = None
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"
NOTE_STYLE = "color: #9fb3c8;"


def open_folder(path):
    """Show the folder in the system's file browser (Fusion's 'open folder' after an export)."""
    try:
        if OPEN_FOLDER is not None:
            OPEN_FOLDER(path)
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
    except Exception as exc:
        warn("could not open the folder %s: %s" % (path, exc))


def start_program(command):
    """Start the slicer with the file (detached, so SciForge goes on)."""
    if START_PROGRAM is not None:
        return START_PROGRAM(command)
    ok = QtCore.QProcess.startDetached(command[0], command[1:])
    if not ok:
        raise export.ExportError("The slicer could not be started: %s" % command[0])
    return ok


def _save_dialog(title, start, filter_text):
    if SAVE_DIALOG is not None:
        return SAVE_DIALOG(title, start, filter_text)
    path, _ = QtWidgets.QFileDialog.getSaveFileName(Gui.getMainWindow(), title, start, filter_text)
    return path or None


def _folder_dialog(title, start):
    if FOLDER_DIALOG is not None:
        return FOLDER_DIALOG(title, start)
    path = QtWidgets.QFileDialog.getExistingDirectory(Gui.getMainWindow(), title, start)
    return path or None


def _home(doc):
    if doc is not None and doc.FileName:
        return os.path.dirname(doc.FileName)
    try:
        folder = App.ParamGet(PREFS).GetString("LastExportFolder", "")
        if folder and os.path.isdir(folder):
            return folder
    except Exception:
        pass
    return os.path.expanduser("~")


def _remember_folder(path):
    try:
        App.ParamGet(PREFS).SetString("LastExportFolder", os.path.dirname(path))
    except Exception:
        pass


def _design_name(doc):
    if doc.FileName:
        return os.path.splitext(os.path.basename(doc.FileName))[0]
    return doc.Label


# -- the bodies list ---------------------------------------------------------------------------
class BodyList(QtWidgets.QListWidget):
    """Fusion's Selection: the bodies to export, ticked. Pre-ticked from the selection, else
    all shown bodies."""

    def __init__(self, doc, on_change):
        super().__init__()
        self.doc = doc
        self.setMaximumHeight(110)
        selected = {sel.ObjectName for sel in Gui.Selection.getSelectionEx()}
        for sel in Gui.Selection.getSelectionEx():
            body = bodies.body_of(sel.Object)
            if body is not None:
                selected.add(body.Name)
        for body in export.exportable_bodies(doc, names={o.Name for o in doc.Objects}):
            item = QtWidgets.QListWidgetItem(body.Label)
            item.setData(QtCore.Qt.UserRole, body.Name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            tick = body.Name in selected if selected else bodies.is_shown(body)
            item.setCheckState(QtCore.Qt.Checked if tick else QtCore.Qt.Unchecked)
            self.addItem(item)
        self.itemChanged.connect(lambda *_: on_change())

    def chosen(self):
        names = []
        for i in range(self.count()):
            item = self.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                names.append(item.data(QtCore.Qt.UserRole))
        return [self.doc.getObject(n) for n in names if self.doc.getObject(n) is not None]

    def tick_all(self, on):
        for i in range(self.count()):
            self.item(i).setCheckState(QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)


class _RefinementRows:
    """Refinement Low / Medium / High / Custom with Surface and Normal Deviation, and the
    Number of Triangles, as in Fusion's mesh dialogs."""

    def __init__(self, form, on_change):
        self.on_change = on_change
        self.level = QtWidgets.QComboBox()
        self.level.addItems(export.REFINEMENTS)
        self.level.setCurrentText(export.DEFAULT_REFINEMENT)
        self.level.currentIndexChanged.connect(lambda *_: self._level_changed())
        form.addRow("Refinement", self.level)
        self.surface = QtWidgets.QDoubleSpinBox()
        self.surface.setDecimals(4)
        self.surface.setRange(0.0001, 100.0)
        self.surface.setSuffix(" mm")
        self.surface.setKeyboardTracking(False)
        self.normal = QtWidgets.QDoubleSpinBox()
        self.normal.setDecimals(1)
        self.normal.setRange(0.1, 90.0)
        self.normal.setSuffix(" °")
        self.normal.setKeyboardTracking(False)
        form.addRow("Surface Deviation", self.surface)
        form.addRow("Normal Deviation", self.normal)
        self.triangles = QtWidgets.QLabel("")
        form.addRow("Number of Triangles", self.triangles)
        self.surface.valueChanged.connect(lambda *_: self._custom_changed())
        self.normal.valueChanged.connect(lambda *_: self._custom_changed())
        self._level_changed()

    def _level_changed(self):
        level = self.level.currentText()
        custom = level == "Custom"
        if not custom:
            surface, normal = export.REFINEMENT[level]
            self.surface.blockSignals(True)
            self.normal.blockSignals(True)
            self.surface.setValue(surface)
            self.normal.setValue(normal)
            self.surface.blockSignals(False)
            self.normal.blockSignals(False)
        self.surface.setEnabled(custom)
        self.normal.setEnabled(custom)
        self.on_change()

    def _custom_changed(self):
        if self.level.currentText() == "Custom":
            self.on_change()

    def values(self):
        return (self.level.currentText(), self.surface.value(), self.normal.value())

    def set_triangles(self, count):
        self.triangles.setText("" if count is None else "{:,}".format(count).replace(",", " "))


class _MeshDialog(QtWidgets.QDialog):
    """What the Export (mesh types) and 3D Print dialogs share."""

    last = None

    def __init__(self, doc, title, icon):
        super().__init__(Gui.getMainWindow())
        type(self).last = self
        self.doc = doc
        self.setWindowTitle(title)
        self.setWindowIcon(ui_icon(icon))
        self.setModal(False)
        self.form = QtWidgets.QFormLayout(self)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        self._count_timer = QtCore.QTimer(self)
        self._count_timer.setSingleShot(True)
        self._count_timer.setInterval(150)
        self._count_timer.timeout.connect(self._count)

    def say(self, text):
        self.message.setText(("⚠ " + text) if text else "")

    def schedule_count(self):
        self._count_timer.start()

    def _count(self):
        """The Number of Triangles at the current refinement (meshing is quick on the kinds of
        parts Luca prints; a very big design shows the count a moment later)."""
        try:
            if not hasattr(self, "refinement") or not self.isVisible():
                return
            if not self.is_mesh():
                self.refinement.set_triangles(None)
                return
            chosen = self.bodies.chosen()
            if not chosen:
                self.refinement.set_triangles(0)
                return
            level, surface, normal = self.refinement.values()
            self.refinement.set_triangles(export.body_triangles(chosen, level, surface, normal))
        except export.ExportError as exc:
            self.refinement.set_triangles(None)
            self.say(str(exc))
        except Exception as exc:
            warn("triangle count: %s" % exc)

    def is_mesh(self):
        return True


# ============================================================================ Export
class ExportDialog(_MeshDialog):
    """Fusion's Export: Name, Type, Location (and, for mesh types, what Save As Mesh offers:
    Unit Type, Structure, Refinement). Exports the whole design or the ticked bodies."""

    def __init__(self, doc):
        super().__init__(doc, "Export", "export")
        form = self.form
        self.what = QtWidgets.QComboBox()
        self.what.addItems(["Whole design", "Selected bodies"])
        form.addRow("Export", self.what)
        self.bodies = BodyList(doc, self.schedule_count)
        form.addRow("Bodies", self.bodies)
        preselected = bool(Gui.Selection.getSelectionEx())
        self.what.setCurrentText("Selected bodies" if preselected else "Whole design")
        self.what.currentIndexChanged.connect(lambda *_: self._what_changed())
        self.type = QtWidgets.QComboBox()
        self.type.addItems([entry[0] for entry in export.FORMATS])
        self.type.currentIndexChanged.connect(lambda *_: self._type_changed())
        form.addRow("Type", self.type)
        self.unit = QtWidgets.QComboBox()
        self.unit.addItems(export.UNIT_NAMES)
        form.addRow("Unit Type", self.unit)
        self.structure = QtWidgets.QComboBox()
        self.structure.addItems(export.STRUCTURES)
        form.addRow("Structure", self.structure)
        self.refinement = _RefinementRows(form, self.schedule_count)
        self.name = QtWidgets.QLineEdit(export.safe_name(_design_name(doc)))
        form.addRow("Name", self.name)
        location = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(location)
        row.setContentsMargins(0, 0, 0, 0)
        self.folder = QtWidgets.QLineEdit(_home(doc))
        browse = QtWidgets.QToolButton()
        browse.setText("…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form.addRow("Location", location)
        self.open_folder = QtWidgets.QCheckBox("Open the folder afterwards")
        self.open_folder.setChecked(True)
        form.addRow(self.open_folder)
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox()
        self.export_button = buttons.addButton("Export", QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.run)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._what_changed()
        self._type_changed()
        if self.bodies.count() == 0:
            self.say("There is no body with a solid to export yet.")

    def _what_changed(self):
        whole = self.what.currentText() == "Whole design"
        self.bodies.setEnabled(not whole)
        if whole:
            self.bodies.tick_all(True)
        self.schedule_count()

    def is_mesh(self):
        return export.is_mesh_format(self.type.currentText())

    def _type_changed(self):
        mesh = self.is_mesh()
        for widget in (
            self.unit,
            self.structure,
            self.refinement.level,
            self.refinement.surface,
            self.refinement.normal,
            self.refinement.triangles,
        ):
            widget.setEnabled(
                mesh
                and (
                    widget is not self.refinement.surface
                    and widget is not self.refinement.normal
                    or self.refinement.level.currentText() == "Custom"
                )
            )
        self.schedule_count()

    def _browse(self):
        folder = _folder_dialog("Export to", self.folder.text() or _home(self.doc))
        if folder:
            self.folder.setText(folder)

    def chosen_bodies(self):
        if self.what.currentText() == "Whole design":
            return export.exportable_bodies(self.doc)
        return [b for b in self.bodies.chosen() if export.can_export(b)]

    def run(self, path=None):
        """Export (the button). `path` skips the Name / Location rows (tests)."""
        try:
            chosen = self.chosen_bodies()
            if not chosen:
                raise export.ExportError("Tick at least one body (or switch to Whole design).")
            fmt = self.type.currentText()
            if path is None:
                folder = self.folder.text().strip() or _home(self.doc)
                name = export.safe_name(self.name.text(), "design")
                path = os.path.join(folder, name + export.extension_of(fmt))
            written = self.export_to(path, chosen, fmt)
            self.say("")
            _remember_folder(path)
            if self.open_folder.isChecked():
                open_folder(os.path.dirname(path))
            commands.tell(
                "Exported %d file%s to %s"
                % (len(written), "" if len(written) == 1 else "s", os.path.dirname(path))
            )
            self.accept()
            return written
        except export.ExportError as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("Export failed: %s" % exc)
            self.say("The export failed: %s" % exc)
        return None

    def export_to(self, path, chosen, fmt):
        if not export.is_mesh_format(fmt):
            return [(export.export_step(chosen, path), None)]
        level, surface, normal = self.refinement.values()
        return export.export_mesh_files(
            self.doc,
            chosen,
            fmt,
            path,
            level,
            surface,
            normal,
            unit=self.unit.currentText(),
            per_body=self.structure.currentText() == "One File Per Body",
        )


# ============================================================================ 3D Print
class PrintDialog(_MeshDialog):
    """Fusion's 3D Print (Utilities > Make): Selection, Format, Unit Type, Refinement with
    its options, Number of Triangles, Output: a file (and open its folder) or straight to
    the slicer you chose once (Send to 3D Print Utility)."""

    def __init__(self, doc, parent=None):
        super().__init__(doc, "3D Print", "insert_mesh")
        form = self.form
        self.bodies = BodyList(doc, self.schedule_count)
        form.addRow("Selection", self.bodies)
        self.format = QtWidgets.QComboBox()
        self.format.addItems(export.PRINT_FORMATS)
        self.format.currentIndexChanged.connect(lambda *_: self.schedule_count())
        form.addRow("Format", self.format)
        self.unit = QtWidgets.QComboBox()
        self.unit.addItems(export.UNIT_NAMES)
        form.addRow("Unit Type", self.unit)
        self.refinement = _RefinementRows(form, self.schedule_count)
        self.send = QtWidgets.QCheckBox("Send to 3D Print Utility (your slicer)")
        self.send.setChecked(bool(export.slicer_program()))
        self.send.toggled.connect(lambda *_: self._send_changed())
        form.addRow(self.send)
        program_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(program_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.program = QtWidgets.QLineEdit(export.slicer_program())
        self.program.setPlaceholderText("The slicer program (PrusaSlicer, Cura, Bambu Studio...)")
        browse = QtWidgets.QToolButton()
        browse.setText("…")
        browse.clicked.connect(self._browse_program)
        row.addWidget(self.program, 1)
        row.addWidget(browse)
        self.program_caption = QtWidgets.QLabel("Print Utility")
        form.addRow(self.program_caption, program_row)
        self.open_folder = QtWidgets.QCheckBox("Open the folder after saving")
        self.open_folder.setChecked(True)
        form.addRow(self.open_folder)
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._send_changed()
        if self.bodies.count() == 0:
            self.say("There is no body to print yet.")
        self.schedule_count()

    def _send_changed(self):
        sending = self.send.isChecked()
        self.program.setEnabled(sending)
        self.program_caption.setEnabled(sending)
        self.open_folder.setEnabled(not sending)

    def _browse_program(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Your slicer program", self.program.text() or os.path.expanduser("~")
        )
        if path:
            self.program.setText(path)

    def default_path(self):
        chosen = self.bodies.chosen()
        name = chosen[0].Label if len(chosen) == 1 else _design_name(self.doc)
        return os.path.join(
            _home(self.doc),
            export.safe_name(name, "part") + export.extension_of(self.format.currentText()),
        )

    def save(self, path=None):
        """OK: write the file (asked for unless `path` is given) and open the folder, or
        hand it to the slicer. Returns True when done."""
        try:
            chosen = [b for b in self.bodies.chosen() if export.can_export(b)]
            if not chosen:
                raise export.ExportError("Tick at least one body to print.")
            fmt = self.format.currentText()
            sending = self.send.isChecked()
            if sending:
                command_program = self.program.text().strip()
                export.slicer_command(command_program, "x")  # checks the program is set
                export.set_slicer_program(command_program)
            if path is None:
                if sending:
                    folder = os.path.join(App.getUserCachePath(), "SciForge", "print")
                    os.makedirs(folder, exist_ok=True)
                    path = os.path.join(folder, os.path.basename(self.default_path()))
                else:
                    path = _save_dialog(
                        "Save for 3D printing",
                        self.default_path(),
                        "%s (*%s)" % (fmt, export.extension_of(fmt)),
                    )
                    if not path:
                        return False
            level, surface, normal = self.refinement.values()
            written = export.export_mesh_files(
                self.doc, chosen, fmt, path, level, surface, normal, unit=self.unit.currentText()
            )
            file_path, count = written[0]
            self.last_file = file_path
            log("3D print: %s (%d triangles)" % (file_path, count))
            if sending:
                start_program(export.slicer_command(self.program.text().strip(), file_path))
            else:
                _remember_folder(file_path)
                if self.open_folder.isChecked():
                    open_folder(os.path.dirname(file_path))
            self.accept()
            return True
        except export.ExportError as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("3D Print failed: %s" % exc)
            self.say("The export failed: %s" % exc)
        return False


# ============================================================================ everything
def export_everything(doc, folder=None, open_after=True):
    """The whole design to open formats in one go (STEP, STL, 3MF, OBJ, a picture and a
    README) in a folder beside the design file, then that folder is opened."""
    if folder is None:
        if doc.FileName:
            folder = export.export_folder_for(doc.FileName, _home(doc))
        else:
            folder = _folder_dialog("Export everything to", _home(doc))
            if not folder:
                return None
            folder = os.path.join(folder, export.safe_name(doc.Label) + export.EXPORT_FOLDER_SUFFIX)
    chosen = export.exportable_bodies(doc)
    if not chosen:
        raise export.ExportError("There is no solid body or mesh body to export yet.")

    def screenshot(path):
        view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
        if view is None or not hasattr(view, "saveImage"):
            return
        view.saveImage(path, 1600, 1200, "Current")

    written = export.export_everything(doc, folder, chosen, screenshot, _design_name(doc))
    if open_after:
        open_folder(folder)
    return written


# ============================================================================ commands
class _Command:
    text = ""
    tip = ""
    icon = "export"

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if App.ActiveDocument is None:
                commands.tell("Open or start a design first.")
                return
            if not commands.finish_open_dialog():
                return
            self.run(App.ActiveDocument)
        except export.ExportError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("%s failed: %s" % (self.text, exc))
            commands.tell("%s could not be done: %s" % (self.text, exc))

    def run(self, doc):
        pass


class ExportCommand(_Command):
    text = "Export"
    tip = "STEP, STL, 3MF or OBJ of the design or of chosen bodies"
    icon = "export"

    def run(self, doc):
        ExportDialog(doc).show()


class PrintCommand(_Command):
    text = "3D Print"
    tip = "Bodies as 3MF, STL or OBJ for your slicer"
    icon = "insert_mesh"

    def run(self, doc):
        PrintDialog(doc).show()


class ExportEverythingCommand(_Command):
    text = "Export Everything"
    tip = "The whole design as STEP + STL + 3MF + OBJ + a picture, in a folder beside it"
    icon = "export_all"

    def run(self, doc):
        written = export_everything(doc)
        if written:
            commands.tell(
                "%d files written to %s" % (len(written), os.path.dirname(written["readme"]))
            )


COMMANDS = {
    "SciForge_Export": ExportCommand,
    "SciForge_3DPrint": PrintCommand,
    "SciForge_ExportEverything": ExportEverythingCommand,
}
