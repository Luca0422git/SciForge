# SPDX-License-Identifier: LGPL-2.1-or-later
"""Places in SciForge's windows (brief home-cloud-ai.md section 3, milestone M2; parity:
docs/sciforge/parity/cloud.md). The rules are locations_core.py.

  * Connect a cloud or NAS (Home's "+ Connect a cloud or NAS", File > Connect a Cloud or
    NAS): Dropbox, OneDrive, Google Drive, a NAS / network folder or any folder. SciForge
    shows the folder it found (or Browse...), a SciForge folder inside it, a name.
  * Before a save: was the file changed on another computer since it was opened here?
    Then Keep both (mine saved beside theirs, the default) / Replace theirs / Open theirs.
  * While a design in a place is open, a note in <place>/.sciforge/locks/ says so; opening
    it on another computer within 12 hours asks Open anyway / Open read-only.
  * Designs inside a folder a cloud app syncs keep their versions as copies, never git.
"""

import getpass
import os
import shutil
import socket
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, locations_core as core, log, versions, warn
from .compat import QtCore, QtWidgets

BROWSE_PICKER = None  # tests: a function returning the folder Browse... picks
DETECT = None  # tests: a function returning the wizard's offers (locations_core.detect)
COMPUTER = None  # tests: this computer's name

_state = {"watch": None, "on": False, "timer": None, "sync": (0.0, [])}
_fingerprints = {}  # document name -> the file as it was opened or last saved here
_read_only = set()  # documents opened read-only (open on another computer)
_notes = {}  # document name -> the note file this computer wrote


# -- the list ------------------------------------------------------------------------------
def places_file():
    return os.path.join(App.getUserAppDataDir(), "SciForge", "locations.json")


def kept():
    """The places connected (not This computer)."""
    try:
        with open(places_file(), "r", encoding="utf-8") as handle:
            return core.load(handle.read())
    except OSError:
        return []


def save(places):
    os.makedirs(os.path.dirname(places_file()), exist_ok=True)
    versions.atomic_write_text(places_file(), core.dump(places))


def project_folder():
    from . import versions_ui

    return versions_ui.project_folder()


def all_places():
    return core.all_places(project_folder(), kept())


def roots():
    return core.roots(project_folder(), kept())


def names():
    return {p["id"]: p["name"] for p in all_places()}


def computer():
    if COMPUTER:
        return COMPUTER
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "this computer"


def user():
    try:
        return getpass.getuser()
    except Exception:
        return ""


# -- what this computer has -------------------------------------------------------------------
def _registry(root, path, name):
    try:
        import winreg

        with winreg.OpenKey(root, path) as key:
            return str(winreg.QueryValueEx(key, name)[0])
    except Exception:
        return ""


def _registry_onedrive():
    """OneDrive's own list of accounts (HKCU\\Software\\Microsoft\\OneDrive\\Accounts)."""
    found = []
    try:
        import winreg

        path = r"Software\Microsoft\OneDrive\Accounts"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            i = 0
            while True:
                try:
                    account = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                folder = _registry(winreg.HKEY_CURRENT_USER, path + "\\" + account, "UserFolder")
                label = "OneDrive" if account == "Personal" else "OneDrive (work)"
                if folder:
                    found.append((label, folder))
    except Exception:
        pass
    return found


def _drive_roots():
    if os.name != "nt":
        return []
    return [
        "%s:\\" % letter for letter in "DEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(letter + ":\\")
    ]


def detect_offers(scan_drives=True):
    """The cloud folders this computer has (the wizard's offers). scan_drives=False: no
    look at every drive letter (a disconnected network drive can hold Windows for seconds),
    for the check at every save."""
    if DETECT is not None:
        return DETECT()
    windows = os.name == "nt"
    home = os.path.expanduser("~")
    texts = []
    for path in core.dropbox_info_files(os.environ, home, windows):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                texts.append(handle.read())
        except OSError:
            pass
    gdrive_roots = []
    if windows:
        import winreg

        gdrive_roots += core.gdrive_mount_points(
            _registry(
                winreg.HKEY_CURRENT_USER, r"Software\Google\DriveFS", "PerAccountPreferences"
            ),
            _registry(winreg.HKEY_LOCAL_MACHINE, r"Software\Google\DriveFS", "DefaultMountPoint")
            or _registry(winreg.HKEY_CURRENT_USER, r"Software\Google\DriveFS", "DefaultMountPoint"),
        )
        if scan_drives:
            gdrive_roots += _drive_roots()
    gdrive_roots.append(home)  # (a mirrored My Drive in the home folder)
    return core.detect(
        dropbox=core.dropbox_folders(texts),
        onedrive=core.onedrive_folders(
            os.environ, _registry_onedrive() if windows else (), home, windows=windows
        ),
        gdrive=core.gdrive_folders(gdrive_roots),
    )


def _offers():
    """detect_offers without the drive scan, kept a minute (asked at every save and every
    Data Panel listing)."""
    when, found = _state["sync"]
    if time.time() - when > 60:
        try:
            found = detect_offers(scan_drives=False)
        except Exception as exc:
            warn("places: finding the cloud folders: %s" % exc)
            found = []
        _state["sync"] = (time.time(), found)
    return found


def sync_roots():
    """The folders cloud apps keep in sync here: found ones and connected cloud places."""
    found = [offer["path"] for offer in _offers()]
    return found + [p["root"] for p in kept() if p["kind"] in core.CLOUD_KINDS]


def git_allowed(path):
    """versions_ui asks before choosing git for a design's versions."""
    try:
        return core.git_allowed(path, all_places(), sync_roots())
    except Exception as exc:
        warn("places: %s" % exc)
        return True


def kind_of_folder(folder):
    """The kind of cloud whose copies may sit in `folder` (for the conflict badge)."""
    place = core.place_of(os.path.join(folder, "x"), all_places())
    if place is not None and place["kind"] in core.CLOUD_KINDS:
        return place["kind"]
    for offer in _offers():
        if versions.inside(offer["path"], folder):
            return offer["kind"]
    return place["kind"] if place is not None else ""


def conflicts(folder, file_names):
    """{copy name: original name} of the sync apps' conflict copies among `file_names`."""
    try:
        return core.conflicts_in(file_names, kind_of_folder(folder), computer())
    except Exception as exc:
        warn("places: %s" % exc)
        return {}


# -- the wizard --------------------------------------------------------------------------------
WIZARD_KINDS = [
    ("dropbox", "Dropbox"),
    ("onedrive", "OneDrive"),
    ("gdrive", "Google Drive"),
    ("nas", "NAS or network folder"),
    ("folder", "Another folder"),
]


class ConnectDialog(QtWidgets.QDialog):
    """Connect a cloud or NAS: the kind, the folder (found or chosen), a name."""

    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        self.setObjectName("SciForgeConnectDialog")
        self.setWindowTitle("Connect a cloud or NAS")
        self.place = None
        self.offers = []
        try:
            self.offers = detect_offers()
        except Exception as exc:
            warn("places: %s" % exc)
        form = QtWidgets.QFormLayout(self)
        self.kind = QtWidgets.QComboBox()
        self.kind.setObjectName("SciForgeConnectKind")
        for kind, label in WIZARD_KINDS:
            self.kind.addItem(label, kind)
        form.addRow("Where", self.kind)
        self.note = QtWidgets.QLabel("")
        self.note.setObjectName("SciForgeConnectNote")
        self.note.setWordWrap(True)
        form.addRow(self.note)
        row = QtWidgets.QHBoxLayout()
        self.folder = QtWidgets.QLineEdit()
        self.folder.setObjectName("SciForgeConnectFolder")
        row.addWidget(self.folder, 1)
        browse = QtWidgets.QPushButton("Browse...")
        browse.setObjectName("SciForgeConnectBrowse")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        form.addRow("Folder", row)
        self.name = QtWidgets.QLineEdit()
        self.name.setObjectName("SciForgeConnectName")
        form.addRow("Name", self.name)
        self.git = QtWidgets.QCheckBox("Keep versions with git (only if no cloud app syncs it)")
        self.git.setObjectName("SciForgeConnectGit")
        form.addRow(self.git)
        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("SciForgeConnectError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #ef6f6c;")
        form.addRow(self.error)
        buttons = QtWidgets.QDialogButtonBox()
        self.connect_button = buttons.addButton("Connect", QtWidgets.QDialogButtonBox.AcceptRole)
        self.connect_button.setObjectName("SciForgeConnectOK")
        self.connect_button.setDefault(True)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        first = self.offers[0]["kind"] if self.offers else "nas"
        self.kind.setCurrentIndex(max(0, self.kind.findData(first)))
        self._kind_changed()
        self.resize(560, self.sizeHint().height())

    def _offer(self, kind):
        for offer in self.offers:
            if offer["kind"] == kind:
                return offer
        return None

    def _kind_changed(self, *_args):
        try:
            kind = self.kind.currentData()
            label = dict(WIZARD_KINDS)[kind]
            cloud = kind in core.CLOUD_KINDS
            offer = self._offer(kind) if cloud else None
            self.error.setText("")
            if offer is not None:
                self.folder.setText(os.path.join(offer["path"], core.SUBFOLDER))
                self.note.setText(
                    "Found %s at %s. SciForge keeps your designs in a %s folder there; the "
                    "%s app keeps them in sync with your other computers."
                    % (label, offer["path"], core.SUBFOLDER, label)
                )
            elif cloud:
                self.folder.setText("")
                self.note.setText(
                    "%s was not found on this computer. Is its app installed and signed in? "
                    "You can also choose its folder with Browse..." % label
                )
            else:
                self.folder.setText("")
                self.note.setText(
                    "Choose the folder: a mapped drive or a network path such as "
                    "\\\\nas\\share\\SciForge. An offline NAS shows greyed, never an error."
                    if kind == "nas"
                    else "Choose any folder for your designs."
                )
            self.git.setVisible(not cloud)
            self.git.setChecked(False)
            self.name.setText(core.KINDS[kind][0] if kind != "nas" else "NAS")
        except Exception as exc:
            warn("places: %s" % exc)

    def _browse(self):
        try:
            path = BROWSE_PICKER() if BROWSE_PICKER is not None else None
            if path is None:
                path = QtWidgets.QFileDialog.getExistingDirectory(
                    self, "Folder", self.folder.text() or os.path.expanduser("~")
                )
            if path:
                self.folder.setText(path)
        except Exception as exc:
            warn("places: %s" % exc)

    def accept(self):
        try:
            folder = self.folder.text().strip()
            kind = self.kind.currentData()
            if not folder:
                self.error.setText("Choose a folder first.")
                return
            places = kept()
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError as exc:
                self.error.setText("The folder %s cannot be made: %s" % (folder, exc))
                return
            try:
                place = core.add(
                    places, kind, folder, self.name.text(), project_folder(), self.git.isChecked()
                )
            except core.PlaceError as exc:
                self.error.setText(str(exc))
                return
            save(places)
            _state["sync"] = (0.0, [])
            self.place = place
            log("places: connected %s (%s) at %s" % (place["name"], kind, place["root"]))
            _refresh_views()
            super().accept()
        except Exception as exc:
            warn("places: connect: %s" % exc)
            self.error.setText("The place could not be connected: %s" % exc)


def connect_place():
    """Show the wizard (Home's + Connect a cloud or NAS)."""
    from . import versions_ui

    return versions_ui._show(ConnectDialog(), "connect")


def disconnect(place_id):
    """SciForge forgets the place; the folder and its designs stay where they are."""
    places = kept()
    place = core.find(places, place_id)
    if place is None:
        return
    core.remove(places, place_id)
    save(places)
    _state["sync"] = (0.0, [])
    log("places: disconnected %s (the folder %s stays)" % (place["name"], place["root"]))
    _refresh_views()


def _refresh_views():
    try:
        from . import home_ui

        home_ui.places_changed()
    except Exception as exc:
        warn("places: %s" % exc)


# -- changed on another computer ---------------------------------------------------------------
class ChangedDialog(QtWidgets.QDialog):
    """The file was changed on another computer since it was opened here."""

    def __init__(self, path, when):
        super().__init__(Gui.getMainWindow())
        self.setObjectName("SciForgeChangedDialog")
        self.setWindowTitle("Changed on another computer")
        self.choice = None
        column = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel(
            "%s was changed on another computer at %s, after you opened it here. Saving now "
            "would overwrite that work.\n\nKeep both: your design is saved beside it as a "
            "copy. Replace theirs: your design overwrites it. Open theirs: their design "
            "opens read-only next to yours."
            % (versions.design_name(path), time.strftime("%H:%M", time.localtime(when)))
        )
        text.setWordWrap(True)
        column.addWidget(text)
        row = QtWidgets.QHBoxLayout()
        for choice, label in (
            (core.KEEP_BOTH, "Keep both"),
            (core.REPLACE, "Replace theirs"),
            (core.OPEN_THEIRS, "Open theirs"),
        ):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("SciForgeChanged_" + choice)
            button.clicked.connect(lambda _=False, c=choice: self._choose(c))
            if choice == core.KEEP_BOTH:
                button.setDefault(True)
            row.addWidget(button)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        column.addLayout(row)

    def _choose(self, choice):
        self.choice = choice
        self.accept()


def remember(doc):
    """The file as it is now is the one this design was opened from / saved to."""
    try:
        if doc.FileName:
            _fingerprints[doc.Name] = core.fingerprint(doc.FileName)
    except Exception as exc:
        warn("places: %s" % exc)


def before_save(doc, proceed):
    """versions_ui.save_design asks first: True to save as usual; False when a question
    was shown instead (its answer saves, or not)."""
    try:
        name = doc.Name
        if name in _read_only:
            commands.tell(
                "%s was opened read-only: it is open on another computer. Use Save As to keep "
                "your changes as a new design." % doc.Label
            )
            return False
        path = doc.FileName
        if not path or not core.changed_since(_fingerprints.get(name), path):
            return True
        log("places: %s was changed on another computer" % path)
        dialog = ChangedDialog(path, os.path.getmtime(path))

        def chosen():
            _resolve(name, path, dialog.choice, proceed)

        dialog.accepted.connect(chosen)
        from . import versions_ui

        versions_ui._show(dialog, "changed:" + name)
        return False
    except Exception as exc:
        warn("places: before save: %s" % exc)
        return True


def _resolve(name, path, choice, proceed):
    try:
        from . import versions_ui

        doc = App.listDocuments().get(name)
        if doc is None:
            return
        if choice == core.KEEP_BOTH:
            target = core.copy_name(path, computer())
            versions_ui._first_save(name, target, save_as=True)
            commands.tell(
                "Saved yours as %s. Theirs stays as %s."
                % (os.path.basename(target), os.path.basename(path))
            )
        elif choice == core.REPLACE:
            _fingerprints[name] = core.fingerprint(path)  # theirs seen: overwrite it
            proceed()
        elif choice == core.OPEN_THEIRS:
            open_read_only(path, "theirs")
    except Exception as exc:
        warn("places: %s" % exc)
        commands.tell("That did not work: %s" % exc)


def open_read_only(path, why):
    """A copy of the file opened read-only in its own tab (the original is not touched)."""
    from . import versions_ui

    folder = os.path.join(App.getUserAppDataDir(), "SciForge", "open")
    os.makedirs(folder, exist_ok=True)
    copy = os.path.join(
        folder, "%s (%s)%s" % (versions.design_name(path), why, versions.DESIGN_SUFFIX)
    )
    shutil.copy2(path, copy)
    doc = App.openDocument(copy)
    doc.Label = "%s (%s, read-only)" % (versions.design_name(path), why)
    _read_only.add(doc.Name)
    versions_ui.set_modified(doc, False)
    log("places: opened %s read-only (%s)" % (path, why))
    return doc


# -- open on another computer ------------------------------------------------------------------
class OpenElsewhereDialog(QtWidgets.QDialog):
    def __init__(self, path, note):
        super().__init__(Gui.getMainWindow())
        self.setObjectName("SciForgeOpenElsewhereDialog")
        self.setWindowTitle("Open on another computer")
        self.choice = None
        column = QtWidgets.QVBoxLayout(self)
        who = (" (%s)" % note["user"]) if note.get("user") else ""
        text = QtWidgets.QLabel(
            "%s is open on %s%s since %s. If you change it here too, one of the two "
            "computers' work is overwritten (SciForge asks before saving).\n\nOpen read-only "
            "to look at it, or Open anyway to work on it here."
            % (
                versions.design_name(path),
                note["computer"],
                who,
                time.strftime("%H:%M", time.localtime(note["since"])),
            )
        )
        text.setWordWrap(True)
        column.addWidget(text)
        row = QtWidgets.QHBoxLayout()
        anyway = QtWidgets.QPushButton("Open anyway")
        anyway.setObjectName("SciForgeOpenAnyway")
        anyway.clicked.connect(lambda: self._choose("anyway"))
        row.addWidget(anyway)
        read_only = QtWidgets.QPushButton("Open read-only")
        read_only.setObjectName("SciForgeOpenReadOnly")
        read_only.setDefault(True)
        read_only.clicked.connect(lambda: self._choose("read_only"))
        row.addWidget(read_only)
        column.addLayout(row)

    def _choose(self, choice):
        self.choice = choice
        self.accept()


def _note_for(path):
    place = core.place_of(path, all_places())
    return core.note_file(place["root"], path) if place is not None else None


def write_note(name, path):
    note = _note_for(path)
    if note is None:
        return
    try:
        os.makedirs(os.path.dirname(note), exist_ok=True)
        import json

        versions.atomic_write_text(note, json.dumps(core.make_note(computer(), user())))
        _notes[name] = note
    except OSError as exc:
        warn("places: could not write %s: %s" % (note, exc))


def drop_note(name):
    note = _notes.pop(name, None)
    if note is None:
        return
    try:
        with open(note, "r", encoding="utf-8") as handle:
            mine = core.read_note(handle.read())
        if mine is None or mine.get("computer", "").lower() == computer().lower():
            os.remove(note)
    except OSError:
        pass


def _opened(name):
    """A design was opened: remember its file; a note of another computer asks first."""
    try:
        doc = App.listDocuments().get(name)
        if doc is None or not doc.FileName or name in _read_only:
            return
        path = doc.FileName
        remember(doc)
        note_path = _note_for(path)
        if note_path is None:
            return
        try:
            with open(note_path, "r", encoding="utf-8") as handle:
                note = core.read_note(handle.read())
        except OSError:
            note = None
        if not core.note_blocks(note, computer()):
            write_note(name, path)
            return
        dialog = OpenElsewhereDialog(path, note)

        def chosen():
            if dialog.choice == "anyway":
                write_note(name, path)
                log("places: %s opened although it is open on %s" % (path, note["computer"]))
            else:
                _read_only.add(name)
                log("places: %s opened read-only (open on %s)" % (path, note["computer"]))

        dialog.accepted.connect(chosen)
        dialog.rejected.connect(lambda: _read_only.add(name))  # (Esc: the safe choice)
        from . import versions_ui

        versions_ui._show(dialog, "elsewhere:" + name)
    except Exception as exc:
        warn("places: %s" % exc)


def _refresh_notes():
    """A session longer than the notes' 12 hours keeps them fresh (every hour)."""
    for name, note in list(_notes.items()):
        doc = App.listDocuments().get(name)
        if doc is not None and doc.FileName:
            write_note(name, doc.FileName)


class _Watch:
    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            QtCore.QTimer.singleShot(0, lambda: _opened(name))
        except Exception as exc:
            warn("places: %s" % exc)

    def slotFinishSaveDocument(self, doc, filename):
        try:
            name = doc.Name
            QtCore.QTimer.singleShot(0, lambda: _saved(name))
        except Exception as exc:
            warn("places: %s" % exc)

    def slotDeletedDocument(self, doc):
        try:
            name = doc.Name
            _fingerprints.pop(name, None)
            _read_only.discard(name)
            drop_note(name)
        except Exception as exc:
            warn("places: %s" % exc)


def _saved(name):
    try:
        doc = App.listDocuments().get(name)
        if doc is None or not doc.FileName:
            return
        remember(doc)
        old = _notes.get(name)
        new = _note_for(doc.FileName)
        if old != new:
            drop_note(name)  # (saved somewhere else: Save As, Keep both)
        if new is not None:
            write_note(name, doc.FileName)
    except Exception as exc:
        warn("places: %s" % exc)


def enable():
    if _state["on"]:
        return
    _state["on"] = True
    if _state["watch"] is None:
        _state["watch"] = _Watch()
    App.addDocumentObserver(_state["watch"])
    if _state["timer"] is None:
        _state["timer"] = QtCore.QTimer()
        _state["timer"].setInterval(3600 * 1000)
        _state["timer"].timeout.connect(_refresh_notes)
    _state["timer"].start()


def disable():
    if not _state["on"]:
        return
    _state["on"] = False
    for step in (
        lambda: App.removeDocumentObserver(_state["watch"]),
        lambda: _state["timer"].stop(),
        lambda: [drop_note(n) for n in list(_notes)],
    ):
        try:
            step()
        except Exception as exc:
            warn("places off: %s" % exc)


# -- commands ---------------------------------------------------------------------------------
class ConnectCommand:
    def GetResources(self):
        from . import ui_icon_path

        return {
            "MenuText": "Connect a Cloud or NAS",
            "ToolTip": "Keep designs in your Dropbox, OneDrive, Google Drive or NAS folder",
            "Pixmap": ui_icon_path("folder"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            connect_place()
        except Exception as exc:
            warn("Connect a Cloud or NAS: %s" % exc)


COMMANDS = {"SciForge_ConnectPlace": ConnectCommand}
