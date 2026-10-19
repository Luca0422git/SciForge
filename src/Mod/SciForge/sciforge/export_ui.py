# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export, 3D Print and Export Everything: the dialogs (Fusion's File > Export, Utilities >
Make > 3D Print, Save As Mesh). The file work is in export.py. Spec and sources:
docs/sciforge/parity/insert-export.md."""

import os
import shutil
import sys
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, export, log, slicer_core, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtGui, QtWidgets

# Tests replace these: the folder opener, the slicer starter, the file / folder / program
# dialogs, and where 3D Print looks for slicers (SLICER_ENV: {"PATH": ..., "HOME": ...}).
OPEN_FOLDER = None
START_PROGRAM = None
SAVE_DIALOG = None
FOLDER_DIALOG = None
PROGRAM_DIALOG = None
SLICER_ENV = None
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
    ok = QtCore.QProcess.startDetached(command[0], list(command[1:]))
    if isinstance(ok, tuple):  # some PySide versions also give the process id
        ok = ok[0]
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
WHOLE = "Whole design"
SELECTED = "Selected bodies"
COMPONENT = "A component"
MESH_KINDS = ("stl", "stl_ascii", "3mf", "obj")


class ExportDialog(_MeshDialog):
    """Fusion's Export: Name, Type, Location (and, for mesh types, what Save As Mesh offers:
    Unit Type, Structure, Refinement). Exports the whole design (STEP keeps its components),
    the ticked bodies or one component; DXF / DWG take the sketch or flat face picked.
    `preset`: a body or component to export (Save As Mesh from the browser); `mesh`: start
    on a mesh type."""

    def __init__(self, doc, preset=None, mesh=False):
        super().__init__(doc, "Export", "export")
        from . import components, exchange_core

        self.exchange_core = exchange_core
        form = self.form
        self.what = QtWidgets.QComboBox()
        self.what.addItems([WHOLE, SELECTED, COMPONENT])
        form.addRow("Export", self.what)
        self.bodies = BodyList(doc, self.schedule_count)
        form.addRow("Bodies", self.bodies)
        self.component = QtWidgets.QComboBox()
        self.component_list = components.list_components(doc)
        for comp in self.component_list:
            self.component.addItem(comp.Label, comp.Name)
        self.component.currentIndexChanged.connect(lambda *_: self.schedule_count())
        form.addRow("Component", self.component)
        self.flat = None
        try:
            from . import exchange_ui

            self.flat = exchange_ui.selected_flat()
        except Exception:
            self.flat = None
        flat_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(flat_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.flat_label = QtWidgets.QLabel("")
        self.flat_label.setWordWrap(True)
        self.use_selection = QtWidgets.QPushButton("Use Selection")
        self.use_selection.setToolTip(
            "Pick a sketch (browser or window) or a flat face, then click"
        )
        self.use_selection.clicked.connect(lambda *_: self._take_selection())
        row.addWidget(self.flat_label, 1)
        row.addWidget(self.use_selection)
        self.flat_caption = QtWidgets.QLabel("Sketch or face")
        form.addRow(self.flat_caption, flat_row)
        preselected = bool(Gui.Selection.getSelectionEx())
        self.what.setCurrentText(SELECTED if preselected else WHOLE)
        self.type = QtWidgets.QComboBox()
        self.type.addItems([entry[0] for entry in exchange_core.EXPORT_TYPES])
        if self.flat is not None and self.flat[0].TypeId == "Sketcher::SketchObject":
            self.type.setCurrentText("DXF")
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
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(NOTE_STYLE)
        form.addRow(self.note)
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox()
        self.export_button = buttons.addButton("Export", QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.run)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if preset is not None:
            self._preset(preset, mesh)
        self.what.currentIndexChanged.connect(lambda *_: self._what_changed())
        self.type.currentIndexChanged.connect(lambda *_: self._type_changed())
        self._show_flat()
        self._type_changed()
        if self.bodies.count() == 0:
            self.say("There is no body with a solid to export yet.")

    def _preset(self, obj, mesh):
        from . import components

        if components.is_component(obj):
            index = self.component.findData(obj.Name)
            if index >= 0:
                self.component.setCurrentIndex(index)
            self.what.setCurrentText(COMPONENT)
        else:
            for i in range(self.bodies.count()):
                item = self.bodies.item(i)
                tick = item.data(QtCore.Qt.UserRole) == obj.Name
                item.setCheckState(QtCore.Qt.Checked if tick else QtCore.Qt.Unchecked)
            self.what.setCurrentText(SELECTED)
        self.name.setText(export.safe_name(obj.Label))
        if mesh:
            self.type.setCurrentText("3MF")

    def kind(self):
        return self.exchange_core.export_kind(self.type.currentText())

    def is_mesh(self):
        return self.kind() in MESH_KINDS

    def is_flat(self):
        return self.kind() in self.exchange_core.FLAT_KINDS

    def _take_selection(self):
        try:
            from . import exchange_ui

            found = exchange_ui.selected_flat()
            if found is None:
                self.say("Pick a sketch (in the browser or the window) or a flat face first.")
            else:
                self.flat = found
                self.say("")
            self._show_flat()
        except Exception as exc:
            warn("export: %s" % exc)

    def _show_flat(self):
        if self.flat is None:
            self.flat_label.setText("(pick a sketch or a flat face, then Use Selection)")
        else:
            obj, sub = self.flat
            self.flat_label.setText(obj.Label + (" " + sub if sub else ""))

    def _what_changed(self):
        what = self.what.currentText()
        flat = self.is_flat()
        self.what.setEnabled(not flat)
        self.bodies.setEnabled(what == SELECTED and not flat)
        self.component.setEnabled(what == COMPONENT and not flat)
        if what == WHOLE:
            self.bodies.tick_all(True)
        if what == COMPONENT and not self.component_list:
            self.say("The design has no components.")
        self.schedule_count()

    def _type_changed(self):
        mesh = self.is_mesh()
        flat = self.is_flat()
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
        self.flat_caption.setEnabled(flat)
        self.flat_label.setEnabled(flat)
        self.use_selection.setEnabled(flat)
        kind = self.kind()
        note = ""
        if kind == "step":
            note = "STEP keeps the components, their names and colours."
        elif kind == "iges":
            note = "IGES keeps the solids, not the components."
        elif kind == "dwg":
            from . import exchange

            if exchange.dwg_converter() is None:
                note = self.exchange_core.DWG_NONE
        elif flat:
            note = "DXF writes the picked sketch's curves (or a flat face's edges) in 2D."
        self.note.setText(note)
        self._what_changed()

    def _browse(self):
        folder = _folder_dialog("Export to", self.folder.text() or _home(self.doc))
        if folder:
            self.folder.setText(folder)

    def chosen_component(self):
        name = self.component.currentData()
        return self.doc.getObject(name) if name else None

    def chosen_bodies(self):
        what = self.what.currentText()
        if what == WHOLE:
            return export.exportable_bodies(self.doc)
        if what == COMPONENT:
            from . import exchange

            return exchange.mesh_bodies_of(self.doc, self.chosen_component())
        return [b for b in self.bodies.chosen() if export.can_export(b)]

    def run(self, path=None):
        """Export (the button). `path` skips the Name / Location rows (tests)."""
        try:
            fmt = self.type.currentText()
            if path is None:
                folder = self.folder.text().strip() or _home(self.doc)
                name = export.safe_name(self.name.text(), "design")
                path = os.path.join(folder, name + self.exchange_core.export_extension(fmt))
            written = self.export_to(path, fmt)
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
        except (export.ExportError, self.exchange_core.ExchangeError) as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("Export failed: %s" % exc)
            self.say("The export failed: %s" % exc)
        return None

    def export_to(self, path, fmt, chosen=None):
        from . import exchange

        core = self.exchange_core
        kind = core.export_kind(fmt)
        what = self.what.currentText()
        if kind in core.FLAT_KINDS:
            if self.flat is None:
                raise core.ExchangeError(
                    "DXF and DWG take a sketch or a flat face: pick one, then Use Selection."
                )
            if kind == "dxf":
                return [(exchange.export_dxf(self.flat, path), None)]
            return [(exchange.export_dwg(self.flat, path), None)]
        component = self.chosen_component() if what == COMPONENT else None
        if what == COMPONENT and component is None:
            raise export.ExportError("Pick the component to export.")
        if kind in core.CAD_KINDS:
            if what == SELECTED:
                picked = chosen if chosen is not None else self.chosen_bodies()
                if not picked:
                    raise export.ExportError("Tick at least one body (or switch to Whole design).")
                return [(exchange.export_cad(self.doc, kind, path, "bodies", chosen=picked), None)]
            scope = "component" if component is not None else "design"
            return [(exchange.export_cad(self.doc, kind, path, scope, target=component), None)]
        picked = chosen if chosen is not None else self.chosen_bodies()
        if not picked:
            raise export.ExportError("Tick at least one body (or switch to Whole design).")
        level, surface, normal = self.refinement.values()
        return export.export_mesh_files(
            self.doc,
            picked,
            fmt,
            path,
            level,
            surface,
            normal,
            unit=self.unit.currentText(),
            per_body=self.structure.currentText() == "One File Per Body",
            frame=exchange.component_frame(component) if component is not None else None,
        )


# ============================================================================ 3D Print
def _runnable(path):
    """A program that can be started: a file (executable outside Windows) or a macOS .app."""
    try:
        if not path:
            return False
        if os.path.isdir(path):
            return path.lower().endswith(".app")
        if not os.path.isfile(path):
            return False
        return sys.platform.startswith("win") or os.access(path, os.X_OK)
    except Exception:
        return False


def found_slicers():
    """[(id, name, program)] of the slicers on this computer (slicer_core's rules: the usual
    install folders and the PATH; nothing is started). Tests set SLICER_ENV to look in a
    folder of their own instead of the machine's."""
    try:
        if SLICER_ENV is not None:
            env, home = dict(SLICER_ENV), SLICER_ENV.get("HOME", "")
        else:
            env, home = dict(os.environ), os.path.expanduser("~")
        return slicer_core.find_slicers(
            sys.platform, env, _runnable, os.path.isdir, os.listdir, home
        )
    except Exception as exc:
        warn("3D Print: looking for slicers failed (%s)" % exc)
        return []


def print_folder():
    """The temporary folder the file for the slicer is written to (old files cleaned up)."""
    folder = os.path.join(App.getUserCachePath(), "SciForge", "print")
    os.makedirs(folder, exist_ok=True)
    try:
        entries = []
        for name in os.listdir(folder):
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                entries.append((name, os.path.getmtime(full)))
        for name in slicer_core.stale_files(entries, time.time()):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass  # still open in a slicer: next time
    except Exception as exc:
        warn("3D Print: old print files not cleaned up (%s)" % exc)
    return folder


def _program_dialog(start):
    if PROGRAM_DIALOG is not None:
        return PROGRAM_DIALOG(start)
    if sys.platform.startswith("win"):
        filter_text = "Programs (*.exe *.lnk *.bat *.cmd);;All files (*)"
    else:
        filter_text = "All files (*)"
    path, _ = QtWidgets.QFileDialog.getOpenFileName(
        Gui.getMainWindow(), "Your slicer program", start, filter_text
    )
    return path or None


class PrintDialog(_MeshDialog):
    """Fusion's 3D Print (Utilities > Make): Selection, where the design goes (Fusion's Print
    Utility list of the utilities it found, with Custom; or Export = a file only), Format,
    Unit Type, Refinement with its options, Number of Triangles. Sending writes a temporary
    file and starts the slicer with it; Save file only asks where to save and opens the
    folder. The choices are remembered (Preferences > 3D Print)."""

    def __init__(self, doc, parent=None):
        super().__init__(doc, "3D Print", "print_3d")
        form = self.form
        self.last_file = None
        self.last_copy = None
        self._picking = False
        self.found = found_slicers()
        self.bodies = BodyList(doc, self.schedule_count)
        form.addRow("Selection", self.bodies)
        self.send_to = QtWidgets.QComboBox()
        for key, label in slicer_core.send_to_entries(self.found):
            self.send_to.addItem(label, key)
        form.addRow("Send to", self.send_to)
        program_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(program_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.other_program = export.slicer_program()
        self.program = QtWidgets.QLineEdit()
        self.program.setPlaceholderText("Your slicer's program (.exe, shortcut or AppImage)")
        self.program.textEdited.connect(lambda *_: self._program_typed())
        self.browse = QtWidgets.QToolButton()
        self.browse.setText("…")
        self.browse.setToolTip("Pick your slicer's program")
        self.browse.clicked.connect(lambda *_: self._browse_program())
        row.addWidget(self.program, 1)
        row.addWidget(self.browse)
        self.program_caption = QtWidgets.QLabel("Program")
        form.addRow(self.program_caption, program_row)
        self.found_note = QtWidgets.QLabel("")
        self.found_note.setWordWrap(True)
        self.found_note.setStyleSheet(NOTE_STYLE)
        form.addRow(self.found_note)
        self.format = QtWidgets.QComboBox()
        self.format.addItems(export.PRINT_FORMATS)
        self.format.setCurrentText(export.print_format())
        self.format.currentIndexChanged.connect(lambda *_: self.schedule_count())
        form.addRow("Format", self.format)
        self.unit = QtWidgets.QComboBox()
        self.unit.addItems(export.UNIT_NAMES)
        form.addRow("Unit Type", self.unit)
        self.refinement = _RefinementRows(form, self.schedule_count)
        self.save_copy = QtWidgets.QCheckBox("Also save a copy next to the design")
        self.save_copy.setChecked(export.print_save_copy())
        form.addRow(self.save_copy)
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
        start = slicer_core.default_target(
            self.found, export.print_send_to(), self.other_program
        )
        self.send_to.setCurrentIndex(max(0, self.send_to.findData(start)))
        self.send_to.currentIndexChanged.connect(lambda *_: self._send_to_changed(True))
        self._send_to_changed(False)
        if self.bodies.count() == 0:
            self.say("There is no body to print yet.")
        self.schedule_count()

    # -- Send to ------------------------------------------------------------------------
    def target(self):
        return self.send_to.currentData() or slicer_core.FILE_ONLY

    def set_target(self, key):
        """Choose a Send to entry by its key (a slicer id, OTHER, FILE_ONLY)."""
        index = self.send_to.findData(key)
        if index >= 0:
            self.send_to.setCurrentIndex(index)
        return index >= 0

    def sending(self):
        return self.target() != slicer_core.FILE_ONLY

    def current_program(self):
        if self.target() == slicer_core.OTHER:
            return self.program.text().strip()
        return slicer_core.program_for(self.target(), self.found)

    def _send_to_changed(self, picked):
        try:
            target = self.target()
            other = target == slicer_core.OTHER
            sending = self.sending()
            self.program.setText(
                self.other_program if other else slicer_core.program_for(target, self.found)
            )
            self.program.setEnabled(other)
            self.browse.setEnabled(other)
            self.program_caption.setEnabled(sending)
            self.save_copy.setEnabled(sending)
            self.open_folder.setEnabled(not sending)
            # slicers get millimetres (an STL has no unit); a saved file keeps the Unit Type
            self.unit.setEnabled(not sending)
            self.unit.setToolTip(
                "A slicer always gets millimetres." if sending else "The unit the file counts in."
            )
            if sending:
                self.unit.setCurrentText("Millimeter")
            if not self.found:
                self.found_note.setText(slicer_core.NONE_FOUND)
            else:
                self.found_note.setText(
                    "Found on this computer: %s." % ", ".join(n for _i, n, _p in self.found)
                )
            self.say("")
            if other and picked and not self.program.text().strip():
                self._browse_program()  # Fusion's Custom: point it at the program
        except Exception as exc:
            warn("3D Print: %s" % exc)

    def _program_typed(self):
        if self.target() == slicer_core.OTHER:
            self.other_program = self.program.text().strip()

    def _browse_program(self):
        if self._picking:
            return
        self._picking = True
        try:
            start = self.program.text().strip() or os.path.expanduser("~")
            path = _program_dialog(start)
            if path:
                self.other_program = path
                if self.target() != slicer_core.OTHER:
                    self.set_target(slicer_core.OTHER)
                self.program.setText(path)
                self.say("")
        except Exception as exc:
            warn("3D Print: %s" % exc)
        finally:
            self._picking = False

    # -- OK -------------------------------------------------------------------------------
    def default_path(self):
        chosen = self.bodies.chosen()
        name = slicer_core.print_name(_design_name(self.doc), [b.Label for b in chosen])
        return os.path.join(_home(self.doc), name + export.extension_of(self.format.currentText()))

    def _remember(self, target):
        export.set_print_send_to(target)
        export.set_print_format(self.format.currentText())
        if target == slicer_core.OTHER:
            export.set_slicer_program(self.program.text().strip())
        if self.sending():
            export.set_print_save_copy(self.save_copy.isChecked())

    def _temp_path(self, fmt):
        path = os.path.join(print_folder(), os.path.basename(self.default_path()))
        if os.path.exists(path):
            try:
                os.remove(path)  # our own file from last time
            except OSError:  # still open in the slicer (Windows locks it)
                path = slicer_core.free_path(path, os.path.exists)
        return path

    def save(self, path=None):
        """OK: hand the file to the slicer (written to a temporary folder, a copy beside the
        design when asked), or write it where the save dialog says (unless `path` is given)
        and open the folder. Returns True when done."""
        try:
            chosen = [b for b in self.bodies.chosen() if export.can_export(b)]
            if not chosen:
                raise export.ExportError("Tick at least one body to print.")
            fmt = self.format.currentText()
            target = self.target()
            sending = self.sending()
            program = ""
            if sending:
                program = self.current_program()
                problem = slicer_core.check_program(program, _runnable, os.path.isdir)
                if problem:
                    if not self.found and not program:
                        problem = slicer_core.NONE_FOUND
                    raise export.ExportError(problem)
            if path is None:
                if sending:
                    path = self._temp_path(fmt)
                else:
                    path = _save_dialog(
                        "Save for 3D printing",
                        self.default_path(),
                        "%s (*%s)" % (fmt, export.extension_of(fmt)),
                    )
                    if not path:
                        return False
            self._remember(target)
            level, surface, normal = self.refinement.values()
            unit = slicer_core.send_unit(self.unit.currentText(), sending)
            written = export.export_mesh_files(
                self.doc, chosen, fmt, path, level, surface, normal, unit=unit
            )
            file_path, count = written[0]
            self.last_file = file_path
            self.last_copy = None
            log("3D print: %s (%d triangles, %s)" % (file_path, count, unit))
            if sending:
                name = slicer_core.slicer_name(target, self.found, program)
                if self.save_copy.isChecked():
                    folder = slicer_core.copy_folder(self.doc.FileName, _home(self.doc))
                    copy = slicer_core.free_path(
                        os.path.join(folder, os.path.basename(file_path)), os.path.exists
                    )
                    shutil.copyfile(file_path, copy)
                    self.last_copy = copy
                    log("3D print: a copy saved as %s" % copy)
                exe, args = slicer_core.launch_command(program, [file_path], sys.platform)
                start_program([exe] + args)
                log("3D print: sent to %s (%s)" % (name, program))
                commands.tell("Sent to %s: %s" % (name, os.path.basename(file_path)))
            else:
                _remember_folder(file_path)
                if self.open_folder.isChecked():
                    open_folder(os.path.dirname(file_path))
                commands.tell("Saved %s" % file_path)
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
    tip = "STEP (with its components), IGES, STL, 3MF, OBJ, or a sketch as DXF"
    icon = "export"

    def run(self, doc):
        ExportDialog(doc).show()


class PrintCommand(_Command):
    text = "3D Print"
    tip = "Send the bodies to your slicer (PrusaSlicer, Bambu Studio, OrcaSlicer, Cura...)"
    icon = "print_3d"

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
