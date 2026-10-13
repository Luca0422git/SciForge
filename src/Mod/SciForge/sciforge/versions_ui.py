# SPDX-License-Identifier: LGPL-2.1-or-later
"""Save with versions, the version history, autosave with crash recovery, the Data Panel
and Insert Design: Fusion's file handling on local folders (outline 7.15).

Behaviour copied from Fusion (sources in docs/sciforge/parity/versions.md):
  * Ctrl+S / the Save button: a design without a file asks for a Name and a Location
    (project folder, New Folder); a saved design asks for a Version Description (Enter
    skips it) and every save becomes the next version (v1, v2, ...).
  * Version History: the list of versions; Open shows an older version read-only (Save is
    blocked there, like Fusion's out-of-date design); Promote ("Save As Latest") makes an
    older version the newest, as a new version, the later ones stay in the list.
  * A recovery copy of every changed design every few minutes (not while a command runs;
    Ctrl+Shift+S writes one now); at the next start after a crash: "Recover unsaved work?".
  * The Data Panel: the project folder's folders and designs with thumbnails, double-click
    opens, New Folder, right-click for Open / Version History / Insert / Rename / Delete.

The logic that needs no Qt or FreeCAD (stores, recovery files, summaries) is versions.py.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, theme, ui_icon, versions as core, warn
from .compat import QtCore, QtGui, QtWidgets

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
FREECAD_DOC_PREFS = "User parameter:BaseApp/Preferences/Document"
BACKUP = "User parameter:BaseApp/Preferences/Mod/SciForge/FilesBackup"
# FreeCAD's own autosave is off while SciForge is on: SciForge's recovery copies replace it
# (two autosavers would write every design twice and show two recovery dialogs after a
# crash). The user's own value comes back when SciForge is off (theme.keep_and_set).
FREECAD_SETTINGS = [(FREECAD_DOC_PREFS, "Bool", "AutoSaveEnabled", False)]
RECOVERED_DESCRIPTION = "Recovered after a crash"
THUMB = 96  # Data Panel thumbnail size (px)

_state = {
    "on": False,
    "watch": None,
    "recovery": None,
    "checked": False,  # the start-up check for unsaved work ran in this session
    "panel": None,
    "dock": None,
    "last_location": "",
}
_pending = {}  # document name -> description of the version its running save records
_version_docs = {}  # document name -> (design file, version number): an older version open
_recovered = {}  # document name -> recovery key of the copy it was opened from
_dialogs = {}  # open dialogs by key (one Save dialog per design, one history per file)


# -- settings ----
def prefs():
    return App.ParamGet(PREFS)


def default_project_folder():
    try:
        documents = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
    except Exception:
        documents = ""
    return os.path.join(documents or os.path.expanduser("~"), "SciForge Designs")


def project_folder():
    """The folder the Data Panel shows and git versions live in (the owner's NAS folder)."""
    try:
        value = prefs().GetString("ProjectFolder", "")
    except Exception:
        value = ""
    return value or default_project_folder()


def set_project_folder(path):
    prefs().SetString("ProjectFolder", path or "")


def autosave_minutes():
    try:
        return core.clamp_minutes(prefs().GetInt("AutosaveMinutes", core.DEFAULT_AUTOSAVE_MINUTES))
    except Exception:
        return core.DEFAULT_AUTOSAVE_MINUTES


def autosave_interval_ms():
    """Milliseconds between recovery copies. Tests set AutosaveTestSeconds for a short wait."""
    try:
        seconds = prefs().GetInt("AutosaveTestSeconds", 0)
    except Exception:
        seconds = 0
    if seconds > 0:
        return seconds * 1000
    return autosave_minutes() * 60 * 1000


def ask_description():
    """Fusion asks for a version description on every save of a saved design (and has no
    way to turn it off). SciForge keeps that as the default and offers the switch."""
    try:
        return prefs().GetBool("AskDescription", True)
    except Exception:
        return True


def use_git():
    try:
        return prefs().GetBool("UseGit", True)
    except Exception:
        return True


def user_dir():
    return App.getUserAppDataDir()


def recovery_folder():
    return core.recovery_folder(user_dir())


def store_of(path):
    """The version store of a design file, with what was decided logged."""
    notes = []
    store = core.store_for(
        path, project_folder(), use_git(), os.path.join(user_dir(), "SciForge", "versions"), notes
    )
    for note in notes:
        log("versions: %s" % note)
    return store


# -- documents ----
def _main():
    return Gui.getMainWindow()


def gui_doc(doc):
    try:
        return Gui.getDocument(doc.Name)
    except Exception:
        return None


def is_modified(doc):
    gd = gui_doc(doc)
    try:
        return bool(gd is not None and gd.Modified)
    except Exception:
        return False


def set_modified(doc, value):
    gd = gui_doc(doc)
    try:
        if gd is not None:
            gd.Modified = bool(value)
    except Exception as exc:
        warn("could not mark %s as %s: %s" % (doc.Label, "changed" if value else "saved", exc))


def version_of(doc):
    """(design file, version number) when `doc` is an older version opened read-only."""
    return _version_docs.get(doc.Name) if doc is not None else None


def doc_for_file(path):
    """The open document saved as `path` (not an older version of it), or None."""
    for name in App.listDocuments():
        doc = App.getDocument(name)
        if doc is not None and name not in _version_docs and core.same_path(doc.FileName, path):
            return doc
    return None


def _alive(widget):
    try:
        return widget is not None and widget.isVisible()
    except RuntimeError:
        return False


def _refocus_main():
    """Make the main window the active window again and give the 3D view the keyboard."""
    try:
        main = _main()
        main.activateWindow()
        gdoc = Gui.ActiveDocument
        view = gdoc.ActiveView if gdoc is not None else None
        if view is not None:
            try:
                view.setFocus()
            except Exception:
                pass
    except Exception as exc:
        warn("focus after a dialog: %s" % exc)


def _show(dialog, key):
    """Show a dialog (non-blocking: scenario timers keep running, nothing nests event
    loops) and remember it under key; an open one for the same key is raised instead."""
    old = _dialogs.get(key)
    if _alive(old):
        old.raise_()
        old.activateWindow()
        return old
    _dialogs[key] = dialog
    dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def closed(_result=0, k=key):
        _dialogs.pop(k, None)
        # The keys (Ctrl+S, E, Q...) belong to the main window: without a window manager
        # (a virtual screen, some Linux set-ups) nothing makes it the active window again
        # after a dialog closes, and every key was dead until a click. Done here.
        QtCore.QTimer.singleShot(0, _refocus_main)

    dialog.finished.connect(closed)
    if dialog.isModal():
        dialog.open()
    else:
        dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


# -- the Save dialog (Name, Location) ----
class SaveDialog(QtWidgets.QDialog):
    """Fusion's Save dialog for a design that has no file yet (and Save As): Name, Location
    (the project folder or a folder in it, New Folder), Save. The first save makes v1."""

    def __init__(self, doc, save_as=False):
        super().__init__(_main())
        self.setObjectName("SciForgeSaveDialog")
        self.setWindowTitle("Save As" if save_as else "Save")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.doc_name = doc.Name
        self.result_path = None
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit()
        self.name.setObjectName("SciForgeSaveName")
        self.name.setPlaceholderText("Name of the design")
        form.addRow("Name", self.name)
        row = QtWidgets.QHBoxLayout()
        self.location = QtWidgets.QLineEdit()
        self.location.setObjectName("SciForgeSaveLocation")
        self.location.setPlaceholderText("Folder")
        browse = QtWidgets.QToolButton()
        browse.setText("...")
        browse.setToolTip("Choose another folder")
        browse.clicked.connect(self._pick_location)
        self.new_folder = QtWidgets.QPushButton("New Folder")
        self.new_folder.setObjectName("SciForgeSaveNewFolder")
        self.new_folder.setToolTip("Make a new folder inside the location and save there")
        self.new_folder.clicked.connect(self._new_folder)
        row.addWidget(self.location, 1)
        row.addWidget(browse)
        row.addWidget(self.new_folder)
        form.addRow("Location", row)
        layout.addLayout(form)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        layout.addWidget(self.message)
        buttons = QtWidgets.QDialogButtonBox()
        self.save = buttons.addButton("Save", QtWidgets.QDialogButtonBox.AcceptRole)
        self.save.setObjectName("SciForgeSaveButton")
        self.save.setDefault(True)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        # Defaults: the design's own folder when it has one, else the last used, else the
        # project folder; a name that is free in that folder.
        older = version_of(doc)  # an older version opened read-only: its design's place
        design_file = older[0] if older else doc.FileName
        folder = os.path.dirname(design_file) if design_file else ""
        folder = folder or _state["last_location"] or project_folder()
        self.location.setText(folder)
        base = core.clean_name(core.design_name(design_file) if design_file else doc.Label)
        base = base or "Design"
        if save_as and doc.FileName:
            base = core.unique_name(folder, base + " copy", core.DESIGN_SUFFIX)
        else:
            base = core.unique_name(folder, base, core.DESIGN_SUFFIX)
        self.name.setText(base)
        self.name.selectAll()
        self.name.setFocus()

    def _pick_location(self):
        try:
            start = self.location.text() or project_folder()
            path = QtWidgets.QFileDialog.getExistingDirectory(self, "Location", start)
            if path:
                self.location.setText(path)
        except Exception as exc:
            warn("choosing a folder: %s" % exc)

    def _new_folder(self):
        try:
            parent = self.location.text().strip() or project_folder()
            os.makedirs(parent, exist_ok=True)
            path = core.new_folder(parent)
            self.location.setText(path)
            self.message.setText("")
            log("made the folder %s" % path)
        except Exception as exc:
            self.message.setText("The folder could not be made: %s" % exc)

    def accept(self):
        try:
            name = core.clean_name(self.name.text())
            folder = self.location.text().strip()
            if not name:
                self.message.setText("Give the design a name.")
                return
            if not folder:
                self.message.setText("Choose a folder to save in.")
                return
            if not core.writable_folder(folder):
                self.message.setText(
                    "The folder %s cannot be written. Choose another one." % folder
                )
                return
            path = core.design_path(folder, name)
            doc = App.getDocument(self.doc_name) if self.doc_name in App.listDocuments() else None
            if os.path.exists(path) and not (
                doc is not None and core.same_path(path, doc.FileName)
            ):
                self.message.setText(
                    "There is already a design called %s in this folder. Choose another name."
                    % name
                )
                return
            self.result_path = path
        except Exception as exc:
            self.message.setText(str(exc))
            return
        super().accept()


# -- the version description ----
class VersionDialog(QtWidgets.QDialog):
    """Fusion's Save dialog for a saved design: the Version Description (optional; Enter
    saves without one) and Save. With `note` it is Fusion's "Save As Latest" (Promote)."""

    def __init__(self, title, note="", default="", placeholder=""):
        super().__init__(_main())
        self.setObjectName("SciForgeVersionDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        layout = QtWidgets.QVBoxLayout(self)
        if note:
            label = QtWidgets.QLabel(note)
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addWidget(QtWidgets.QLabel("Version Description"))
        self.description = QtWidgets.QLineEdit(default)
        self.description.setObjectName("SciForgeVersionDescription")
        self.description.setPlaceholderText(
            placeholder or "What changed in this version (optional). Enter saves."
        )
        self.description.returnPressed.connect(self.accept)
        layout.addWidget(self.description)
        buttons = QtWidgets.QDialogButtonBox()
        self.save = buttons.addButton("Save", QtWidgets.QDialogButtonBox.AcceptRole)
        self.save.setObjectName("SciForgeVersionSave")
        self.save.setDefault(True)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.description.setFocus()

    def text(self):
        return self.description.text().strip()


class OlderVersionDialog(QtWidgets.QDialog):
    """Save pressed on an older version opened read-only. Fusion blocks Save there and
    offers Save As Latest; a copy can also be saved as a new design."""

    def __init__(self, doc, path, number):
        super().__init__(_main())
        self.setObjectName("SciForgeOlderVersionDialog")
        self.setWindowTitle("Save")
        self.setModal(True)
        self.choice = None
        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel(
            "This is v%d of %s, opened read-only. A newer version exists.\n\n"
            "Make this version the newest (Save As Latest), or save it as a new design."
            % (number, core.design_name(path))
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        buttons = QtWidgets.QDialogButtonBox()
        latest = buttons.addButton("Save As Latest", QtWidgets.QDialogButtonBox.AcceptRole)
        latest.setObjectName("SciForgeOlderSaveAsLatest")
        copy = buttons.addButton("Save As New Design", QtWidgets.QDialogButtonBox.ActionRole)
        copy.setObjectName("SciForgeOlderSaveAs")
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        latest.clicked.connect(lambda: self._pick("latest"))
        copy.clicked.connect(lambda: self._pick("copy"))
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick(self, choice):
        self.choice = choice
        self.accept()


# -- saving ----
def save_design(doc, after=None):
    """Fusion's Save for `doc`: Name + Location for a design without a file, the Version
    Description for a saved one; every save records a version. `after()` runs once the
    save is done (used by Insert Design, which needs a saved owner)."""
    if doc is None:
        commands.tell("Nothing to save: no design is open.")
        return
    older = version_of(doc)
    if older:
        path, number = older
        dialog = OlderVersionDialog(doc, path, number)

        def chosen():
            if dialog.choice == "latest":
                promote(path, number_to_info(path, number), from_doc=doc)
            elif dialog.choice == "copy":
                save_design_as(doc)

        dialog.accepted.connect(chosen)
        _show(dialog, "save:" + doc.Name)
        return
    # The document's name is taken now: the design may be closed while the dialog is open
    # (the lambda then read `doc.Name` from a deleted object: ReferenceError), and
    # _first_save / _save_version look the document up by name and do nothing when gone.
    name = doc.Name
    if not doc.FileName:
        dialog = SaveDialog(doc)
        dialog.accepted.connect(lambda: _first_save(name, dialog.result_path, after))
        _show(dialog, "save:" + name)
    elif ask_description():
        # A recovered design: the description says so unless the user writes another.
        default = RECOVERED_DESCRIPTION if name in _recovered else ""
        dialog = VersionDialog("Save", default=default)
        dialog.accepted.connect(lambda: _save_version(name, dialog.text(), after))
        _show(dialog, "save:" + name)
    else:
        _save_version(name, "", after)


def save_design_as(doc):
    """Save As: a new design (v1) in the chosen folder; the open design becomes that file."""
    if doc is None:
        commands.tell("Nothing to save: no design is open.")
        return
    name = doc.Name  # taken now: the design may be closed while the dialog is open
    dialog = SaveDialog(doc, save_as=True)
    dialog.accepted.connect(lambda: _first_save(name, dialog.result_path, None, save_as=True))
    _show(dialog, "saveas:" + name)


def _document(name):
    return App.getDocument(name) if name in App.listDocuments() else None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _first_save(doc_name, path, after=None, save_as=False):
    doc = _document(doc_name)
    if doc is None or not path:
        commands.tell("The design was closed before it could be saved.")
        return
    try:
        was_version = _version_docs.pop(doc_name, None)
        _pending[doc_name] = (
            "Saved as a new design from %s" % core.design_name(was_version[0])
            if was_version
            else ""
        )
        doc.saveAs(path)  # returns None in FreeCAD 1.1.4, raises when it fails
        if not os.path.isfile(path):
            _pending.pop(doc_name, None)
            commands.tell("The design could not be saved to %s." % path)
            return
        set_modified(doc, False)
        _state["last_location"] = os.path.dirname(path)
        _recovered.pop(doc_name, None)
        log("%s %s" % ("saved as a copy:" if save_as else "saved:", path))
        if after is not None:
            QtCore.QTimer.singleShot(0, after)
    except Exception as exc:
        _pending.pop(doc_name, None)
        warn("save failed: %s" % exc)
        commands.tell("The design could not be saved: %s" % exc)


def _save_version(doc_name, description, after=None):
    doc = _document(doc_name)
    if doc is None:
        commands.tell("The design was closed before it could be saved.")
        return
    try:
        _pending[doc_name] = description or ""
        before = _mtime(doc.FileName)
        # FreeCAD's save() returns None (1.1.4) and raises when it fails: the file tells.
        doc.save()
        if not os.path.isfile(doc.FileName) or _mtime(doc.FileName) < before:
            _pending.pop(doc_name, None)
            commands.tell("The design could not be saved to %s." % doc.FileName)
            return
        # FreeCAD's own Save command clears its "changed" mark after saving; a save from
        # Python does not, so the title kept its star. Done here.
        set_modified(doc, False)
        if after is not None:
            QtCore.QTimer.singleShot(0, after)
    except Exception as exc:
        _pending.pop(doc_name, None)
        warn("save failed: %s" % exc)
        commands.tell("The design could not be saved: %s" % exc)


class _Watch:
    """Every finished save of a design (SciForge's or FreeCAD's own File > Save) records a
    version and drops the design's recovery copy; a closed design drops its copy too."""

    def slotFinishSaveDocument(self, doc, filename):
        try:
            if not core.same_path(filename, doc.FileName):
                return  # a copy (recovery, Save a Copy): not a version of the design
            if core.inside(recovery_folder(), filename):
                return
            if doc.Name in _version_docs:
                return  # FreeCAD's own Save on a read-only copy: no version of that
            description = _pending.pop(doc.Name, "")
            name, label = doc.Name, doc.Label
            QtCore.QTimer.singleShot(0, lambda: _record(name, label, filename, description))
            recovery = _state["recovery"]
            if recovery is not None:
                recovery.clear_for(doc)
        except Exception as exc:
            warn("after saving: %s" % exc)

    def slotDeletedDocument(self, doc):
        try:
            _pending.pop(doc.Name, None)
            _version_docs.pop(doc.Name, None)
            recovery = _state["recovery"]
            if recovery is not None:
                recovery.clear_for(doc)
            _recovered.pop(doc.Name, None)
        except Exception as exc:
            warn("after closing a design: %s" % exc)

    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            QtCore.QTimer.singleShot(900, lambda: _check_links(name))
        except Exception as exc:
            warn("after opening a design: %s" % exc)


def _record(doc_name, label, path, description):
    """Record the version of a design just saved to `path` (a moment after the save)."""
    try:
        if description == RECOVERED_DESCRIPTION or doc_name in _recovered:
            key = _recovered.pop(doc_name, None)
            if key:
                core.discard_recovery(recovery_folder(), key)
            description = description or RECOVERED_DESCRIPTION
        store = store_of(path)
        try:
            info = store.record(description)
        except core.StoreError as exc:
            if store.backend != "git":
                raise
            warn("git could not record the version (%s); kept as a copy instead" % exc)
            store = core.PlainStore(path, os.path.join(user_dir(), "SciForge", "versions"))
            info = store.record(description)
        log(
            "saved %s as %s%s (%s)"
            % (label, info.label, (": " + description) if description else "", store.backend)
        )
        commands.tell("Saved %s (%s)" % (label, info.label))
        _refresh_views(path)
    except Exception as exc:
        warn("the save worked but its version could not be recorded: %s" % exc)
        commands.tell("Saved, but the version could not be recorded: %s" % exc)


def _refresh_views(path=None):
    panel = _state.get("panel")
    if _alive(panel):
        panel.refresh()
    for key, dialog in list(_dialogs.items()):
        if key.startswith("history:") and _alive(dialog):
            try:
                dialog.refresh()
            except Exception as exc:
                warn("version history: %s" % exc)


def _check_links(doc_name):
    """Links to other designs that could not be found: say so in words (FreeCAD prints its
    own 'file does not exist' lines). Linked designs are stored by their path relative to
    the design, so a project folder moved as a whole keeps working."""
    try:
        doc = _document(doc_name)
        if doc is None:
            return
        broken = []
        for obj in doc.Objects:
            if obj.TypeId == "App::Link" and getattr(obj, "LinkedObject", None) is None:
                broken.append(obj.Label)
        if broken:
            commands.tell(
                "%d linked design(s) were not found (%s). Keep linked designs inside the "
                "project folder and move the folder as a whole." % (len(broken), ", ".join(broken))
            )
    except Exception as exc:
        warn("checking links: %s" % exc)


# -- the version history ----
def number_to_info(path, number):
    for info in store_of(path).versions():
        if info.number == number:
            return info
    return None


class HistoryDialog(QtWidgets.QDialog):
    """The versions of one design, newest first: number, date, description, size. Open
    shows one read-only, Promote makes it the newest, Compare shows what differs."""

    def __init__(self, path):
        super().__init__(_main())
        self.setObjectName("SciForgeHistoryDialog")
        self.path = path
        self.setWindowTitle("Version History: %s" % core.design_name(path))
        self.resize(640, 360)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setObjectName("SciForgeHistoryTable")
        self.table.setHorizontalHeaderLabels(["Version", "Date", "Description", "Size"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_selected())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QtWidgets.QDialogButtonBox()
        self.open_button = buttons.addButton("Open", QtWidgets.QDialogButtonBox.ActionRole)
        self.open_button.setObjectName("SciForgeHistoryOpen")
        self.open_button.setToolTip("Open this version read-only, in its own tab")
        self.promote_button = buttons.addButton("Promote", QtWidgets.QDialogButtonBox.ActionRole)
        self.promote_button.setObjectName("SciForgeHistoryPromote")
        self.promote_button.setToolTip("Make this version the newest (Save As Latest)")
        self.compare_button = buttons.addButton("Compare", QtWidgets.QDialogButtonBox.ActionRole)
        self.compare_button.setObjectName("SciForgeHistoryCompare")
        self.compare_button.setToolTip("What differs between this version and the newest")
        buttons.addButton(QtWidgets.QDialogButtonBox.Close)
        self.open_button.clicked.connect(self.open_selected)
        self.promote_button.clicked.connect(self.promote_selected)
        self.compare_button.clicked.connect(self.compare_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.versions = []
        self.refresh()

    def refresh(self):
        try:
            store = store_of(self.path)
            self.versions = list(reversed(store.versions()))
            where = (
                "Versions are git commits in the project folder."
                if store.backend == "git"
                else "Versions are copies in %s." % store.folder
            )
        except Exception as exc:
            self.versions = []
            where = "The versions could not be read: %s" % exc
        self.table.setRowCount(len(self.versions))
        for row, info in enumerate(self.versions):
            cells = [
                info.label + ("  (current)" if info.current else ""),
                core.pretty_time(info.time),
                info.description,
                core.human_size(info.size),
            ]
            for col, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if info.current:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        if self.versions:
            self.table.selectRow(0)
            self.note.setText("%d version(s). %s" % (len(self.versions), where))
        else:
            self.note.setText("No versions yet: the first save makes v1. %s" % where)
        self._selection_changed()

    def selected(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = rows.pop()
        return self.versions[row] if 0 <= row < len(self.versions) else None

    def select_version(self, number):
        for row, info in enumerate(self.versions):
            if info.number == number:
                self.table.selectRow(row)
                return True
        return False

    def _selection_changed(self):
        info = self.selected()
        self.open_button.setEnabled(info is not None)
        self.promote_button.setEnabled(info is not None and not info.current)
        self.compare_button.setEnabled(info is not None and len(self.versions) > 1)

    def open_selected(self):
        info = self.selected()
        if info is not None:
            open_version(self.path, info)

    def promote_selected(self):
        info = self.selected()
        if info is not None and not info.current:
            promote(self.path, info)

    def compare_selected(self):
        info = self.selected()
        if info is None or len(self.versions) < 2:
            return
        newest = self.versions[0]
        other = info if not info.current else self.versions[1]
        dialog = CompareDialog(self.path, other, newest)
        _show(dialog, "compare:%s:%d:%d" % (self.path, other.number, newest.number))


def show_history(path):
    if not path:
        commands.tell("Save the design first: its version history starts with the first save.")
        return None
    return _show(HistoryDialog(path), "history:" + path)


def open_version(path, info):
    """Open version `info` of the design read-only, in its own tab (a copy in the user
    folder). Save is blocked for it; Promote makes it the newest (Fusion's out-of-date
    design)."""
    try:
        dest = os.path.join(user_dir(), "SciForge", core.OPEN_FOLDER)
        os.makedirs(dest, exist_ok=True)
        for name, (design, number) in list(_version_docs.items()):
            if (
                core.same_path(design, path)
                and number == info.number
                and name in App.listDocuments()
            ):
                App.setActiveDocument(name)
                commands.tell(
                    "%s of %s is already open (read-only)." % (info.label, core.design_name(path))
                )
                return App.getDocument(name)
        file = store_of(path).extract(info, dest)
        doc = App.openDocument(file)
        doc.Label = "%s %s" % (core.design_name(path), info.label)
        _version_docs[doc.Name] = (path, info.number)
        set_modified(doc, False)
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        log("opened %s of %s read-only (%s)" % (info.label, core.design_name(path), file))
        commands.tell(
            "%s opened read-only. Save is blocked here: use Promote to make it the newest "
            "version, or Save As for a new design." % info.label
        )
        return doc
    except Exception as exc:
        warn("could not open %s: %s" % (info.label, exc))
        commands.tell("The version could not be opened: %s" % exc)
        return None


def promote(path, info, from_doc=None):
    """Fusion's Save As Latest: ask for a description, then make `info` the newest version
    (recorded as a new number; the later versions stay). The open design is reloaded."""
    if info is None:
        commands.tell("That version was not found.")
        return
    name = core.design_name(path)
    current = doc_for_file(path)
    if current is not None and is_modified(current):
        commands.tell(
            "%s has unsaved changes. Save them first (Ctrl+S, they become a version), or "
            "close it without saving, then promote." % name
        )
        return
    dialog = VersionDialog(
        "Save As Latest",
        note="You are saving %s of %s as the latest version. The later versions stay in "
        "the history." % (info.label, name),
        default="Promoted %s" % info.label,
    )
    dialog.accepted.connect(lambda: _promote_now(path, info, dialog.text(), from_doc))
    _show(dialog, "promote:" + path)


def _promote_now(path, info, description, from_doc=None):
    try:
        current = doc_for_file(path)
        if current is not None:
            if is_modified(current):
                commands.tell("Save or close %s first." % current.Label)
                return
            App.closeDocument(current.Name)
        new = store_of(path).promote(info, description)
        # The read-only copies of this design are closed: the design itself is the newest.
        for doc_name, (design, _n) in list(_version_docs.items()):
            if core.same_path(design, path) and doc_name in App.listDocuments():
                set_modified(App.getDocument(doc_name), False)
                App.closeDocument(doc_name)
        doc = App.openDocument(path)
        set_modified(doc, False)
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        log("promoted %s of %s: now %s" % (info.label, core.design_name(path), new.label))
        commands.tell("%s is now the newest version (%s)." % (info.label, new.label))
        _refresh_views(path)
    except Exception as exc:
        warn("promote failed: %s" % exc)
        commands.tell("The version could not be promoted: %s" % exc)


# -- comparing two versions ----
def volume_of_file(path):
    """Total volume of the bodies in a saved design, by loading it hidden; None if that
    fails."""
    # A design that is open already is read as it is: FreeCAD hands the open document back
    # for its path, and closing that would close the user's design.
    for name in App.listDocuments():
        if core.same_path(App.getDocument(name).FileName, path):
            return _bodies_volume(App.getDocument(name))
    doc = None
    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    try:
        doc = App.openDocument(path, True)
        return _bodies_volume(doc)
    except Exception as exc:
        warn("could not read the volume of %s: %s" % (path, exc))
        return None
    finally:
        try:
            if doc is not None:
                App.closeDocument(doc.Name)
        except Exception:
            pass
        _restore_active(active)


def _bodies_volume(doc):
    total = 0.0
    for obj in doc.Objects:
        if obj.TypeId == "PartDesign::Body" and not obj.Shape.isNull():
            total += obj.Shape.Volume
    return total


def _restore_active(name):
    """A hidden document opened for a look becomes FreeCAD's active document and leaves
    none when closed: the design that was active before is made active again."""
    try:
        if (
            name
            and name in App.listDocuments()
            and (App.ActiveDocument is None or App.ActiveDocument.Name != name)
        ):
            App.setActiveDocument(name)
    except Exception as exc:
        warn("active design: %s" % exc)


def _active_doc():
    """The design the user works on: FreeCAD's active document, or the one whose tab is in
    front when the former is unset (a hidden document was just closed)."""
    doc = App.ActiveDocument
    if doc is None:
        try:
            gdoc = Gui.ActiveDocument
            doc = gdoc.Document if gdoc is not None else None
            if doc is not None:
                App.setActiveDocument(doc.Name)
        except Exception:
            doc = None
    return doc


class CompareDialog(QtWidgets.QDialog):
    """Two versions side by side: bodies, sketches, features, total volume, size, date;
    changed rows marked. (Fusion has no version comparison; SciForge's addition.)"""

    def __init__(self, path, a, b):
        super().__init__(_main())
        self.setObjectName("SciForgeCompareDialog")
        self.setWindowTitle("Compare %s and %s" % (a.label, b.label))
        self.resize(520, 300)
        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setObjectName("SciForgeCompareTable")
        self.table.setHorizontalHeaderLabels(["", a.label, b.label])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rows = []
        self.fill(path, a, b)

    def fill(self, path, a, b):
        try:
            store = store_of(path)
            folder = os.path.join(user_dir(), "SciForge", core.OPEN_FOLDER, "compare")
            os.makedirs(folder, exist_ok=True)
            files = []
            for info in (a, b):
                files.append(
                    store.extract(
                        info,
                        folder,
                        "compare-%s-%d%s" % (core.path_key(path), info.number, core.DESIGN_SUFFIX),
                    )
                )
            summaries = [core.summary(f) for f in files]
            for summary, file in zip(summaries, files):
                volume = volume_of_file(file)
                if volume is not None:
                    summary["volume"] = volume
            self.rows = core.compare(summaries[0], summaries[1])
            for file in files:
                try:
                    os.remove(file)
                except OSError:
                    pass
        except Exception as exc:
            warn("compare: %s" % exc)
            self.rows = [("Could not compare", str(exc), "", False)]
        self.table.setRowCount(len(self.rows))
        changed = 0
        for row, (title, va, vb, differs) in enumerate(self.rows):
            for col, text in enumerate((title, va, vb)):
                item = QtWidgets.QTableWidgetItem(text)
                if differs:
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#ffb74d")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, col, item)
            changed += 1 if differs else 0
        self.table.resizeColumnsToContents()
        self.note.setText(
            "%d of %d rows differ." % (changed, len(self.rows))
            if self.rows
            else "Nothing to compare."
        )


# -- recovery copies ----
class Recovery:
    """Writes a recovery copy of every changed design every few minutes (Fusion: the
    recovery save interval, default 5 minutes, not while a command runs), keeps track of
    them and offers the leftovers of a crashed session at the next start."""

    def __init__(self):
        self.session = core.new_session_id()
        self.folder = recovery_folder()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.postponed = False
        self.written = 0  # copies written this session (tests read it)

    def start(self):
        self.timer.setInterval(autosave_interval_ms())
        self.timer.start()
        log(
            "recovery copies every %s to %s" % (_interval_words(self.timer.interval()), self.folder)
        )

    def restart(self):
        if self.timer.isActive():
            self.timer.stop()
        self.start()

    def stop(self):
        self.timer.stop()

    def busy(self):
        """Fusion does not write a recovery copy while a command runs (its dialog is open).
        A sketch being edited is not a command here (it can take an hour)."""
        try:
            from . import sketch_mode

            if Gui.Control.activeDialog() and not sketch_mode.sketch_edited_anywhere():
                return True
            for name in App.listDocuments():
                if App.getDocument(name).Recomputing:
                    return True
        except Exception:
            return False
        return False

    def tick(self):
        try:
            self.save_all(forced=False)
        except Exception as exc:
            warn("recovery copy: %s" % exc)

    def save_all(self, forced=False):
        """A copy of every changed design (every design when forced: Ctrl+Shift+S). Returns
        the number of copies written; -1 when postponed because a command runs."""
        if self.busy():
            if not self.postponed:
                log("recovery copy postponed: a command is running")
            self.postponed = True
            return -1
        self.postponed = False
        count = 0
        for name in list(App.listDocuments()):
            doc = App.getDocument(name)
            if doc is None or name in _version_docs:
                continue
            if not forced and not is_modified(doc):
                continue
            if self.save_copy(doc):
                count += 1
        return count

    def key_of(self, doc):
        return _recovered.get(doc.Name) or core.recovery_key(doc.Name, doc.FileName)

    def save_copy(self, doc):
        key = core.recovery_key(doc.Name, doc.FileName)
        copy, _side = core.recovery_paths(self.folder, key)
        tmp = copy[: -len(core.DESIGN_SUFFIX)] + ".tmp" + core.DESIGN_SUFFIX
        try:
            os.makedirs(self.folder, exist_ok=True)
            doc.saveCopy(tmp)  # returns None in FreeCAD 1.1.4, raises when it fails
            if not os.path.isfile(tmp):
                raise RuntimeError("FreeCAD wrote no copy")
            os.replace(tmp, copy)
            core.write_recovery_sidecar(self.folder, key, doc.Label, doc.FileName, self.session)
            self.written += 1
            log("recovery copy of %s written" % doc.Label)
            return True
        except Exception as exc:
            warn("recovery copy of %s failed: %s" % (doc.Label, exc))
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False

    def clear_for(self, doc):
        """The design was saved or closed properly: its recovery copy is not needed (the
        one keyed by its file, the one keyed by its name from before its first save, and
        the one it was recovered from). Another session's copy (a crash's) stays: a design
        opened and closed again after a crash, without being recovered, must not lose it."""
        recovered_from = _recovered.get(doc.Name)
        keys = {
            core.recovery_key(doc.Name, doc.FileName),
            core.recovery_key(doc.Name, ""),
            recovered_from,
        }
        for key in keys:
            if not key:
                continue
            session = core.recovery_session(self.folder, key)
            if key == recovered_from or session in ("", self.session):
                core.discard_recovery(self.folder, key)

    def leftovers(self):
        return core.list_recovery(self.folder, other_than_session=self.session)

    def clear_session(self):
        core.discard_session_recovery(self.folder, self.session)


def _interval_words(ms):
    seconds = int(round(ms / 1000.0))
    if seconds % 60 == 0:
        minutes = seconds // 60
        return "%d minute%s" % (minutes, "" if minutes == 1 else "s")
    return "%d seconds" % seconds


class RecoverDialog(QtWidgets.QDialog):
    """ "Recover unsaved work?": the designs a crashed session left recovery copies of.
    Recover opens the ticked ones (saving puts them back into their own file); Delete
    throws the ticked copies away; Later keeps them for File > Recover Documents."""

    def __init__(self, entries):
        super().__init__(_main())
        self.setObjectName("SciForgeRecoverDialog")
        self.setWindowTitle("Recover unsaved work?")
        self.setModal(True)
        self.resize(560, 320)
        self.entries = entries
        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel(
            "SciForge did not close properly last time. These designs had unsaved changes; "
            "a recovery copy of each was kept. Tick the ones to open."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeRecoverList")
        for entry in entries:
            where = entry["file_name"] or "never saved"
            item = QtWidgets.QListWidgetItem(
                "%s    (%s, %s)" % (entry["label"], core.pretty_time(entry["saved"]), where)
            )
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, entry["key"])
            item.setToolTip(entry.get("copy", ""))
            self.list.addItem(item)
        layout.addWidget(self.list)
        buttons = QtWidgets.QDialogButtonBox()
        self.recover = buttons.addButton("Recover", QtWidgets.QDialogButtonBox.AcceptRole)
        self.recover.setObjectName("SciForgeRecoverOpen")
        self.recover.setDefault(True)
        self.delete = buttons.addButton("Delete", QtWidgets.QDialogButtonBox.DestructiveRole)
        self.delete.setObjectName("SciForgeRecoverDelete")
        self.delete.setToolTip("Throw the ticked recovery copies away")
        later = buttons.addButton("Later", QtWidgets.QDialogButtonBox.RejectRole)
        later.setObjectName("SciForgeRecoverLater")
        later.setToolTip("Keep the copies; File menu > Recover Documents shows them again")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.delete.clicked.connect(self._delete)
        layout.addWidget(buttons)

    def ticked(self):
        keys = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                keys.append(item.data(QtCore.Qt.UserRole))
        return [e for e in self.entries if e["key"] in keys]

    def accept(self):
        chosen = self.ticked()
        super().accept()
        for entry in chosen:
            recover_entry(entry)

    def _delete(self):
        chosen = self.ticked()
        for entry in chosen:
            core.discard_recovery(recovery_folder(), entry["key"])
            log("recovery copy of %s deleted" % entry["label"])
        self.done(2)


def recover_entry(entry):
    """Open a recovery copy as the design it was made from: the file name points back at
    the design's own file (a never-saved design stays unsaved), it shows as changed, and
    the next Save writes it there as the newest version."""
    try:
        doc = App.openDocument(entry["copy"])
        original = entry.get("file_name") or ""
        if original:
            try:
                doc.FileName = original
            except Exception as exc:
                warn("could not point the recovered %s at %s: %s" % (entry["label"], original, exc))
        else:
            try:
                doc.FileName = ""
            except Exception:
                pass
        doc.Label = entry["label"] or doc.Label
        _recovered[doc.Name] = entry["key"]
        _pending[doc.Name] = RECOVERED_DESCRIPTION
        set_modified(doc, True)
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        log("recovered %s from %s" % (doc.Label, entry["copy"]))
        commands.tell(
            "%s recovered. Press Ctrl+S to save it%s."
            % (doc.Label, " back into its file" if original else "")
        )
        return doc
    except Exception as exc:
        warn("could not recover %s: %s" % (entry.get("label"), exc))
        commands.tell("The recovery copy could not be opened: %s" % exc)
        return None


def startup_check():
    """Once per session, when SciForge comes on: offer the recovery copies another session
    left behind (a crash; a clean save or close removes them)."""
    recovery = _state["recovery"]
    if recovery is None:
        return False
    entries = recovery.leftovers()
    if not entries:
        log("no unsaved work to recover")
        return False
    log(
        "%d recovery cop%s found from an earlier session"
        % (len(entries), "y" if len(entries) == 1 else "ies")
    )
    _show(RecoverDialog(entries), "recover")
    return True


def recover_documents():
    """File > Recover Documents: the recovery copies kept (none: say so)."""
    recovery = _state["recovery"]
    entries = recovery.leftovers() if recovery is not None else []
    if not entries:
        commands.tell("No unsaved work to recover: every design was saved or closed properly.")
        return None
    return _show(RecoverDialog(entries), "recover")


# -- the Data Panel ----
class DataPanel(QtWidgets.QWidget):
    """Fusion's Data Panel on local files: the project folder's folders first, then its
    designs as cards with FreeCAD's thumbnail, name and version badge. Double-click opens a
    folder or a design; New Folder; right-click for more."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeDataPanel")
        self.folder = project_folder()
        self._thumbs = {}  # path -> (mtime, QIcon)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(2)
        self.up = self._tool("Up", "Up one folder", self.go_up, "SciForgeDataPanelUp")
        bar.addWidget(self.up)
        self.crumbs = QtWidgets.QLabel("")
        self.crumbs.setTextFormat(QtCore.Qt.RichText)
        self.crumbs.linkActivated.connect(self.set_folder)
        bar.addWidget(self.crumbs, 1)
        self.new_folder = self._tool(
            "New Folder", "New Folder", self.make_folder, "SciForgeDataPanelNewFolder"
        )
        self.new_folder.setIcon(ui_icon("folder"))
        self.new_folder.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        bar.addWidget(self.new_folder)
        self.choose = self._tool(
            "...",
            "Choose the project folder (your NAS folder)",
            self.choose_project_folder,
            "SciForgeDataPanelFolder",
        )
        bar.addWidget(self.choose)
        self.reload = self._tool("Refresh", "Refresh", self.refresh, "SciForgeDataPanelRefresh")
        bar.addWidget(self.reload)
        self.view_toggle = self._tool(
            "List", "List view / grid view", None, "SciForgeDataPanelView", checkable=True
        )
        self.view_toggle.toggled.connect(self._view_mode)
        bar.addWidget(self.view_toggle)
        outer.addLayout(bar)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeDataPanelList")
        self.list.setMinimumHeight(220)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemDoubleClicked.connect(self.open_item)
        self.list.setWordWrap(True)
        self._view_mode(False)
        outer.addWidget(self.list, 1)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.refresh()

    @staticmethod
    def _tool(text, tip, slot, object_name, checkable=False):
        """A flat text button of the panel's toolbar (readable on the dark panels)."""
        button = QtWidgets.QToolButton()
        button.setObjectName(object_name)
        button.setText(text)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setCheckable(checkable)
        if slot is not None:
            button.clicked.connect(slot)
        return button

    def _view_mode(self, as_list):
        if as_list:
            self.list.setViewMode(QtWidgets.QListView.ListMode)
            self.list.setIconSize(QtCore.QSize(24, 24))
            self.list.setGridSize(QtCore.QSize())
            self.list.setSpacing(1)
        else:
            self.list.setViewMode(QtWidgets.QListView.IconMode)
            self.list.setIconSize(QtCore.QSize(THUMB, THUMB))
            self.list.setGridSize(QtCore.QSize(THUMB + 24, THUMB + 44))
            self.list.setResizeMode(QtWidgets.QListView.Adjust)
            self.list.setMovement(QtWidgets.QListView.Static)
            self.list.setSpacing(6)

    # -- what is shown
    def set_folder(self, folder):
        project = project_folder()
        if not core.inside(project, folder):
            folder = project
        self.folder = folder
        self.refresh()

    def go_up(self):
        if core.same_path(self.folder, project_folder()):
            return
        self.set_folder(os.path.dirname(self.folder))

    def refresh(self):
        try:
            project = project_folder()
            if not os.path.isdir(project):
                try:
                    os.makedirs(project, exist_ok=True)
                    log("made the project folder %s" % project)
                except OSError:
                    pass
            if not core.inside(project, self.folder) or not os.path.isdir(self.folder):
                self.folder = project
            self.list.clear()
            if not os.path.isdir(project):
                self.crumbs.setText("")
                self.status.setText(
                    "The project folder %s is not there. Choose one with the ... button." % project
                )
                self.up.setEnabled(False)
                return
            crumbs = core.breadcrumbs(project, self.folder)
            self.crumbs.setText(
                " / ".join(
                    '<a href="%s" style="color:#f5f5f5;text-decoration:none">%s</a>' % (path, label)
                    for label, path in crumbs
                )
            )
            self.crumbs.setToolTip(self.folder)
            self.up.setEnabled(len(crumbs) > 1)
            folders, designs = core.list_folder(self.folder)
            counts = None
            if use_git() and core.git_available():
                root = core.repo_root(project)
                if root is not None:
                    counts = core.repo_counts(root)
                    if not core.same_path(root, project):
                        counts = {
                            os.path.relpath(os.path.join(root, k), project).replace(os.sep, "/"): n
                            for k, n in counts.items()
                        }
            for folder in folders:
                item = QtWidgets.QListWidgetItem(ui_icon("folder"), folder["name"])
                item.setData(QtCore.Qt.UserRole, ("folder", folder["path"]))
                item.setToolTip(folder["path"])
                self.list.addItem(item)
            for design in designs:
                n = core.version_count(design["path"], project, use_git(), counts)
                badge = ("  v%d" % n) if n else ""
                item = QtWidgets.QListWidgetItem(
                    self._thumbnail(design["path"]), design["name"] + badge
                )
                item.setData(QtCore.Qt.UserRole, ("design", design["path"]))
                item.setToolTip(
                    "%s\n%s, last saved %s%s"
                    % (
                        design["path"],
                        core.human_size(design["size"]),
                        core.pretty_time(design["modified"]),
                        (", %d version%s" % (n, "" if n == 1 else "s")) if n else "",
                    )
                )
                self.list.addItem(item)
            self.status.setText(
                "%d folder%s, %d design%s"
                % (
                    len(folders),
                    "" if len(folders) == 1 else "s",
                    len(designs),
                    "" if len(designs) == 1 else "s",
                )
            )
        except Exception as exc:
            warn("data panel: %s" % exc)
            self.status.setText("The folder could not be read: %s" % exc)

    def _thumbnail(self, path):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        cached = self._thumbs.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        icon = ui_icon("document")
        data = core.thumbnail_bytes(path)
        if data:
            pixmap = QtGui.QPixmap()
            if pixmap.loadFromData(QtCore.QByteArray(data), "PNG") and not pixmap.isNull():
                icon = QtGui.QIcon(
                    pixmap.scaled(
                        THUMB, THUMB, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
                    )
                )
        self._thumbs[path] = (mtime, icon)
        return icon

    def has_thumbnail(self, path):
        """Whether the card of `path` shows the design's own picture (tests)."""
        cached = self._thumbs.get(path)
        return bool(cached and core.thumbnail_bytes(path))

    def items(self):
        """[(kind, path, text)] as listed (tests)."""
        found = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            kind, path = item.data(QtCore.Qt.UserRole)
            found.append((kind, path, item.text()))
        return found

    def item_for(self, path):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if core.same_path(item.data(QtCore.Qt.UserRole)[1], path):
                return item
        return None

    # -- actions
    def open_item(self, item):
        """Double-click: into a folder, or open the design. The item's data is read now
        and the work done a moment later: entering a folder rebuilds the list, and the
        item would be gone under the signal."""
        try:
            if item is None:
                return
            kind, path = item.data(QtCore.Qt.UserRole)
        except Exception as exc:
            warn("data panel: %s" % exc)
            return
        QtCore.QTimer.singleShot(0, lambda: self._open(kind, path))

    def _open(self, kind, path):
        try:
            if kind == "folder":
                self.set_folder(path)
            else:
                open_design(path)
        except Exception as exc:
            warn("data panel: %s" % exc)

    def make_folder(self):
        try:
            path = core.new_folder(self.folder)
            log("made the folder %s" % path)
            self.refresh()
            item = self.item_for(path)
            if item is not None:
                self.list.setCurrentItem(item)
        except Exception as exc:
            warn("new folder: %s" % exc)
            commands.tell("The folder could not be made: %s" % exc)

    def choose_project_folder(self):
        try:
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Project folder (where your designs live)", project_folder()
            )
            if path:
                set_project_folder(path)
                self.set_folder(path)
                log("project folder: %s" % path)
        except Exception as exc:
            warn("choosing the project folder: %s" % exc)

    def _menu(self, pos):
        try:
            item = self.list.itemAt(pos)
            menu = QtWidgets.QMenu(self)
            if item is None:
                menu.addAction("New Folder", self.make_folder)
                menu.addAction("Refresh", self.refresh)
            else:
                kind, path = item.data(QtCore.Qt.UserRole)
                if kind == "folder":
                    menu.addAction("Open", lambda: self.set_folder(path))
                    menu.addAction("Rename", lambda: self._rename(path, True))
                else:
                    menu.addAction("Open", lambda: open_design(path))
                    menu.addAction("Version History", lambda: show_history(path))
                    menu.addAction(
                        "Insert into Current Design", lambda: insert_design(path)
                    ).setEnabled(App.ActiveDocument is not None)
                    menu.addSeparator()
                    menu.addAction("Rename", lambda: self._rename(path, False))
                    menu.addAction("Delete", lambda: self._trash(path))
                menu.addSeparator()
                menu.addAction("Show in Folder", lambda: _show_in_folder(path))
            menu.exec_(self.list.mapToGlobal(pos))
        except Exception as exc:
            warn("data panel menu: %s" % exc)

    def _rename(self, path, is_folder):
        try:
            old = os.path.basename(path) if is_folder else core.design_name(path)
            new, ok = QtWidgets.QInputDialog.getText(self, "Rename", "New name", text=old)
            if not ok or not new.strip() or new.strip() == old:
                return
            if is_folder:
                target = os.path.join(os.path.dirname(path), core.clean_name(new))
                if os.path.exists(target):
                    raise core.StoreError("A folder called %s is already there." % new)
                os.replace(path, target)
            else:
                if doc_for_file(path) is not None:
                    raise core.StoreError("Close the design before renaming it.")
                core.rename_design(path, new)
            self.refresh()
        except Exception as exc:
            warn("rename: %s" % exc)
            commands.tell("Could not rename: %s" % exc)

    def _trash(self, path):
        try:
            if doc_for_file(path) is not None:
                commands.tell("Close the design before deleting it.")
                return
            answer = QtWidgets.QMessageBox.question(
                self,
                "Delete design",
                "Move %s to the project's trash folder (%s)?\nIt can be taken back from there."
                % (core.design_name(path), core.TRASH_FOLDER),
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
            target = core.trash_design(path, project_folder())
            log("moved %s to %s" % (path, target))
            self.refresh()
        except Exception as exc:
            warn("delete: %s" % exc)
            commands.tell("Could not delete: %s" % exc)


def _show_in_folder(path):
    try:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.dirname(path)))
    except Exception as exc:
        warn("show in folder: %s" % exc)


def open_design(path):
    """Open a design from the Data Panel (bring it to the front if it is open already)."""
    try:
        existing = doc_for_file(path)
        if existing is not None:
            App.setActiveDocument(existing.Name)
            gd = gui_doc(existing)
            if gd is not None and gd.ActiveView is not None:
                try:
                    gd.ActiveView.setFocus()
                except Exception:
                    pass
            return existing
        doc = App.openDocument(path)
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
        log("opened %s" % path)
        return doc
    except Exception as exc:
        warn("could not open %s: %s" % (path, exc))
        commands.tell("The design could not be opened: %s" % exc)
        return None


def _ensure_dock():
    dock = _state.get("dock")
    if dock is not None:
        try:
            dock.objectName()
            return dock
        except RuntimeError:
            pass
    main = _main()
    dock = QtWidgets.QDockWidget("DATA PANEL", main)
    dock.setObjectName("SciForgeDataPanelDock")
    dock.toggleViewAction().setVisible(False)
    panel = DataPanel()
    dock.setWidget(panel)
    main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    _state["dock"], _state["panel"] = dock, panel
    return dock


def panel():
    return _state.get("panel")


def show_panel():
    dock = _ensure_dock()
    dock.show()
    dock.raise_()
    _state["panel"].refresh()


def hide_panel():
    dock = _state.get("dock")
    if dock is not None:
        try:
            dock.hide()
        except RuntimeError:
            pass


def toggle_panel():
    dock = _state.get("dock")
    if dock is not None and _alive(dock):
        hide_panel()
    else:
        show_panel()


def panel_visible():
    dock = _state.get("dock")
    return bool(dock is not None and _alive(dock))


# -- Insert Design (a link to another design, by relative path) ----
def insert_design(path=None):
    """Insert the bodies of another design into the active one as links that follow the
    other file (FreeCAD stores the link by its path relative to this design, so a project
    folder moved as a whole keeps working). The design must be saved first."""
    doc = _active_doc()
    if doc is None:
        doc = App.newDocument("Design")
    if version_of(doc):
        commands.tell("This is an older version opened read-only: nothing can be inserted here.")
        return
    if not doc.FileName:
        commands.tell("Save the design first: a linked design is stored relative to this file.")
        save_design(doc, after=lambda: insert_design(path))
        return
    if path is None:
        try:
            path, _filter = QtWidgets.QFileDialog.getOpenFileName(
                _main(), "Insert Design", project_folder(), "Designs (*.FCStd)"
            )
        except Exception as exc:
            warn("insert design: %s" % exc)
            return
        if not path:
            return
    if core.same_path(path, doc.FileName):
        commands.tell("A design cannot be inserted into itself.")
        return
    if not os.path.isfile(path):
        commands.tell("The design %s was not found." % path)
        return
    try:
        other = None
        for name in App.listDocuments():
            if core.same_path(App.getDocument(name).FileName, path):
                other = App.getDocument(name)
                break
        if other is None:
            other = App.openDocument(path, True)  # hidden: no tab of its own
            _restore_active(doc.Name)
        bodies = [o for o in other.Objects if o.TypeId == "PartDesign::Body"]
        if not bodies:
            commands.tell("%s has no bodies to insert." % core.design_name(path))
            return
        doc.openTransaction("Insert Design")
        made = []
        for body in bodies:
            link = doc.addObject(
                "App::Link", core.clean_name(body.Label).replace(" ", "_") or "Link"
            )
            link.LinkedObject = body
            link.Label = "%s: %s" % (core.design_name(path), body.Label)
            made.append(link)
        doc.commitTransaction()
        doc.recompute()
        rel = core.relative_path(doc.FileName, path)
        log(
            "inserted %d bod%s of %s, linked by the relative path %s"
            % (len(made), "y" if len(made) == 1 else "ies", core.design_name(path), rel)
        )
        commands.tell(
            "Inserted %s (%d bod%s), linked to its file."
            % (core.design_name(path), len(made), "y" if len(made) == 1 else "ies")
        )
        return made
    except Exception as exc:
        try:
            doc.abortTransaction()
        except Exception:
            pass
        warn("insert design failed: %s" % exc)
        commands.tell("The design could not be inserted: %s" % exc)
        return None


# -- settings dialog ----
class SettingsDialog(QtWidgets.QDialog):
    """Project folder, recovery copy interval, the description prompt and git."""

    def __init__(self):
        super().__init__(_main())
        self.setObjectName("SciForgeFilesSettings")
        self.setWindowTitle("Project and Recovery Settings")
        self.setModal(True)
        self.setMinimumWidth(480)
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        row = QtWidgets.QHBoxLayout()
        self.folder = QtWidgets.QLineEdit(project_folder())
        self.folder.setObjectName("SciForgeSettingsFolder")
        browse = QtWidgets.QToolButton()
        browse.setText("...")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form.addRow("Project folder", row)
        self.minutes = QtWidgets.QSpinBox()
        self.minutes.setObjectName("SciForgeSettingsMinutes")
        self.minutes.setRange(core.MIN_AUTOSAVE_MINUTES, core.MAX_AUTOSAVE_MINUTES)
        self.minutes.setValue(autosave_minutes())
        self.minutes.setSuffix(" minutes")
        form.addRow("Recovery copy every", self.minutes)
        self.ask = QtWidgets.QCheckBox("Ask for a version description on every save (Fusion)")
        self.ask.setObjectName("SciForgeSettingsAsk")
        self.ask.setChecked(ask_description())
        form.addRow("", self.ask)
        self.git = QtWidgets.QCheckBox(
            "Keep versions with git in the project folder (%s)"
            % ("git found" if core.git_available() else "git is not installed: copies are used")
        )
        self.git.setObjectName("SciForgeSettingsGit")
        self.git.setChecked(use_git())
        self.git.setEnabled(core.git_available())
        form.addRow("", self.git)
        layout.addLayout(form)
        note = QtWidgets.QLabel(
            "Outside the project folder, versions are kept as copies in a <Design>.versions "
            "folder beside the design. Recovery copies go to %s." % recovery_folder()
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #c3cad4;")
        layout.addWidget(note)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Project folder", self.folder.text()
        )
        if path:
            self.folder.setText(path)

    def accept(self):
        try:
            folder = self.folder.text().strip()
            if folder:
                set_project_folder(folder)
            prefs().SetInt("AutosaveMinutes", int(self.minutes.value()))
            prefs().SetBool("AskDescription", self.ask.isChecked())
            prefs().SetBool("UseGit", self.git.isChecked())
            recovery = _state["recovery"]
            if recovery is not None:
                recovery.restart()
            if _alive(_state.get("panel")):
                _state["panel"].set_folder(folder)
            log("files settings saved")
        except Exception as exc:
            warn("files settings: %s" % exc)
        super().accept()


# -- on / off ----
def enable():
    if _state["on"]:
        return
    _state["on"] = True
    try:
        theme.keep_and_set(FREECAD_SETTINGS, BACKUP)
    except Exception as exc:
        warn("files: %s" % exc)
    if _state["watch"] is None:
        _state["watch"] = _Watch()
    App.addDocumentObserver(_state["watch"])
    if _state["recovery"] is None:
        _state["recovery"] = Recovery()
    _state["recovery"].start()
    if not _state["checked"]:
        _state["checked"] = True
        QtCore.QTimer.singleShot(1500, _safe(startup_check))
    if not _state.get("quit_hooked"):
        try:
            QtWidgets.QApplication.instance().aboutToQuit.connect(_quit)
            _state["quit_hooked"] = True
        except Exception:
            pass


def disable():
    if not _state["on"]:
        return
    _state["on"] = False
    for step in (
        lambda: _state["recovery"].stop(),
        lambda: App.removeDocumentObserver(_state["watch"]),
        hide_panel,
        lambda: theme.give_back(FREECAD_SETTINGS, BACKUP),
    ):
        try:
            step()
        except Exception as exc:
            warn("files off: %s" % exc)


def give_back_left_over():
    """SciForge is off: FreeCAD's own autosave setting back (a session that ended with
    SciForge on left it off)."""
    try:
        theme.give_back(FREECAD_SETTINGS, BACKUP)
    except Exception as exc:
        warn("files: %s" % exc)


def _quit():
    """A clean quit: the running session's recovery copies are not unsaved work."""
    try:
        if _state["recovery"] is not None:
            _state["recovery"].clear_session()
    except Exception:
        pass


def _safe(fn):
    def run():
        try:
            fn()
        except Exception as exc:
            warn("%s: %s" % (getattr(fn, "__name__", "files"), exc))

    return run


def recovery():
    return _state["recovery"]


# -- commands ----
class _Command:
    title = ""
    tip = ""
    icon = None

    def GetResources(self):
        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            from . import ui_icon_path

            res["Pixmap"] = ui_icon_path(self.icon)
        return res

    def IsActive(self):
        return True

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            commands.tell("%s did not work: %s" % (self.title, exc))

    def run(self):
        raise NotImplementedError


class SaveCommand(_Command):
    title = "Save"
    tip = "Save the design as the next version (Ctrl+S)"
    icon = "qa_save"

    def run(self):
        doc = _active_doc()
        if doc is None:
            commands.tell("Nothing to save: no design is open.")
            return
        if not commands.finish_open_dialog():
            return
        save_design(doc)


class SaveAsCommand(_Command):
    title = "Save As"
    tip = "Save the design as a new design in another place (v1 there)"
    icon = "qa_save"

    def run(self):
        doc = _active_doc()
        if doc is None:
            commands.tell("Nothing to save: no design is open.")
            return
        if not commands.finish_open_dialog():
            return
        save_design_as(doc)


class RecoverySaveNowCommand(_Command):
    title = "Write Recovery Copies Now"
    tip = "Write a recovery copy of every open design now (Ctrl+Shift+S); no version is made"

    def run(self):
        recovery = _state["recovery"]
        if recovery is None:
            commands.tell("Recovery copies are only written while SciForge is on.")
            return
        count = recovery.save_all(forced=True)
        if count < 0:
            commands.tell("Finish the open command first, then the recovery copies are written.")
        else:
            commands.tell("Recovery cop%s written (%d)." % ("y" if count == 1 else "ies", count))


class VersionHistoryCommand(_Command):
    title = "Version History"
    tip = "The saved versions of this design: open one read-only, promote, compare"
    icon = "tl_settings"

    def run(self):
        doc = _active_doc()
        if doc is None:
            commands.tell("Open a design first.")
            return
        older = version_of(doc)
        show_history(older[0] if older else doc.FileName)


class RecoverDocumentsCommand(_Command):
    title = "Recover Documents"
    tip = "Open the recovery copies kept from a session that did not close properly"

    def run(self):
        recover_documents()


class DataPanelCommand(_Command):
    title = "Data Panel"
    tip = "Show or hide the project folder's designs (Ctrl+Alt+P)"
    icon = "folder"

    def run(self):
        toggle_panel()


class InsertDesignCommand(_Command):
    title = "Insert Design"
    tip = "Insert another design's bodies, linked to its file by a relative path"
    icon = "insert_component"

    def run(self):
        if not commands.finish_open_dialog():
            return
        insert_design()


class FilesSettingsCommand(_Command):
    title = "Project and Recovery Settings"
    tip = "The project folder, how often recovery copies are written, the description prompt"
    icon = "tl_settings"

    def run(self):
        _show(SettingsDialog(), "settings")


COMMANDS = {
    "SciForge_Save": SaveCommand,
    "SciForge_SaveAs": SaveAsCommand,
    "SciForge_RecoverySaveNow": RecoverySaveNowCommand,
    "SciForge_VersionHistory": VersionHistoryCommand,
    "SciForge_RecoverDocuments": RecoverDocumentsCommand,
    "SciForge_DataPanel": DataPanelCommand,
    "SciForge_InsertDesign": InsertDesignCommand,
    "SciForge_FilesSettings": FilesSettingsCommand,
}
