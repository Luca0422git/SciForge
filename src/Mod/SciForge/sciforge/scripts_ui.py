# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scripts and Add-Ins (UTILITIES > ADD-INS, Shift+S in Fusion), the dialog and running them.

What a person gets (Fusion's behaviour, sources in docs/sciforge/parity/misc.md):
  * one list of the scripts (FreeCAD macros in the scripts folder) and add-ins (a folder with
    a Python file of its name, defining run() and stop()), a filter box above it;
  * Run: a script runs once (one undo step on the open design); an add-in is loaded (run())
    and shows "Running" until Stop (stop()); double-click = Run;
  * Run on Startup: ticked ones run when SciForge starts;
  * Create (a script or an add-in from SciForge's own template, then Edit), Edit (the editor
    named in Preferences > General > API, else FreeCAD's own), the + button (a script from
    elsewhere is copied into the scripts folder), Open File Location (right-click), and
    Get Add-Ons (FreeCAD's Add-on Manager, the nearest thing to Fusion's App Store).
A script or add-in that fails never takes SciForge down: the dialog says what went wrong.
"""

import importlib.util
import os
import shutil
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, ui_icon, ui_icon_path, warn
from . import scripts_core as core
from .compat import QtCore, QtWidgets

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
STARTUP_KEY = "RunOnStartup"
# Tests replace these: a function(title, start) -> path for the + button, and the program
# starter for Edit / Open File Location ([program, args...] -> True when started).
FILE_PICKER = None
START_PROGRAM = None
_running = {}  # add-in name -> its loaded module
_state = {"startup_done": False, "dialog": None}


# -- folders and settings -----------------------------------------------------------------------
def scripts_folder():
    try:
        path = App.ParamGet("User parameter:BaseApp/Preferences/Macro").GetString("MacroPath", "")
    except Exception:
        path = ""
    return path or App.getUserMacroDir(True)


def addins_folder():
    from . import preferences_ui

    return preferences_ui.addins_folder()


def editor():
    try:
        return App.ParamGet(PREFS).GetString("ScriptEditor", "")
    except Exception:
        return ""


def startup_keys():
    try:
        return core.parse_startup(App.ParamGet(PREFS).GetString(STARTUP_KEY, ""))
    except Exception:
        return set()


def set_startup(entry, on):
    keys = startup_keys()
    key = core.entry_key(entry)
    if on:
        keys.add(key)
    else:
        keys.discard(key)
    App.ParamGet(PREFS).SetString(STARTUP_KEY, core.startup_text(keys))


def entries():
    return core.list_scripts(scripts_folder()) + core.list_addins(addins_folder())


def is_running(entry):
    return entry["kind"] == core.ADDIN and entry["name"] in _running


# -- running ------------------------------------------------------------------------------------
def run_script(entry):
    """Run a script once. Returns (ok, message). What it changes in the open design is one
    undo step ("Script <name>")."""
    doc = App.ActiveDocument
    opened = False
    if doc is not None:
        try:
            doc.openTransaction("Script %s" % entry["name"])
            opened = True
        except Exception:
            opened = False
    namespace = {"__name__": "__main__", "__file__": entry["path"], "__builtins__": __builtins__}
    try:
        with open(entry["path"], "r", encoding="utf-8") as handle:
            code = compile(handle.read(), entry["path"], "exec")
        exec(code, namespace)
    except BaseException as exc:  # a script may call sys.exit(): never the program's end
        if isinstance(exc, SystemExit) and not exc.code:
            return _ran(entry, doc, opened)  # sys.exit() / exit(0): a normal end
        if opened and doc is not None and _alive_doc(doc):
            try:
                doc.abortTransaction()
            except Exception:
                pass
        text = core.short_error(traceback.format_exc())
        _note("script %s stopped" % entry["name"], text)
        return False, "%s stopped with an error: %s" % (entry["name"], text)
    return _ran(entry, doc, opened)


def _ran(entry, doc, opened):
    """The script ended normally: its changes are one undo step."""
    if opened and _alive_doc(doc):
        try:
            doc.commitTransaction()
            doc.recompute()
        except Exception:
            pass
    log("script %s ran" % entry["name"])
    return True, "%s ran." % entry["name"]


def _note(what, detail):
    """A script's own failure: said in the window; the Report view gets a plain line (its
    details go to SciForge > Diagnostics), never an error of SciForge's."""
    from . import _remember

    log("%s (see Scripts and Add-Ins)" % what)
    _remember("script", "%s: %s" % (what, detail))


def _alive_doc(doc):
    try:
        return doc.Name in App.listDocuments()
    except Exception:
        return False


def start_addin(entry, at_startup=False):
    """Load an add-in and call its run(context). Returns (ok, message)."""
    name = entry["name"]
    if name in _running:
        return True, "%s is running already." % name
    module_name = "sciforge_addin_%s" % name
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry["main"])
        module = importlib.util.module_from_spec(spec)
        folder = os.path.dirname(entry["main"])
        if folder not in sys.path:
            sys.path.insert(0, folder)  # its own helper modules, like Fusion's add-ins
        spec.loader.exec_module(module)
        run = getattr(module, "run", None)
        if run is None:
            return False, "%s has no run(context) function." % name
        run({"IsApplicationStartup": bool(at_startup)})
    except BaseException:
        text = core.short_error(traceback.format_exc())
        _note("add-in %s did not start" % name, text)
        return False, "%s could not start: %s" % (name, text)
    _running[name] = module
    log("add-in %s started" % name)
    return True, "%s is running." % name


def stop_addin(entry):
    name = entry["name"]
    module = _running.pop(name, None)
    if module is None:
        return True, "%s is not running." % name
    try:
        stop = getattr(module, "stop", None)
        if stop is not None:
            stop({"IsApplicationStartup": False})
    except BaseException:
        text = core.short_error(traceback.format_exc())
        _note("add-in %s stopped" % name, text)
        return False, "%s stopped with an error: %s" % (name, text)
    log("add-in %s stopped" % name)
    return True, "%s stopped." % name


def run_entry(entry, at_startup=False):
    if entry["kind"] == core.ADDIN:
        if is_running(entry) and not at_startup:
            return stop_addin(entry)
        return start_addin(entry, at_startup)
    return run_script(entry)


def run_startup():
    """The Run on Startup ones, once per session (SciForge's interface turned on)."""
    if _state["startup_done"]:
        return
    _state["startup_done"] = True
    keys = startup_keys()
    if not keys:
        return
    for entry in core.startup_order(entries(), keys):
        try:
            ok, message = run_entry(entry, at_startup=True)
            if not ok:
                commands.tell(message)
        except Exception as exc:
            warn("start-up %s: %s" % (entry["name"], exc))


# -- files ---------------------------------------------------------------------------------------
def start_program(command):
    if START_PROGRAM is not None:
        return START_PROGRAM(command)
    try:
        return bool(QtCore.QProcess.startDetached(command[0], command[1:]))
    except Exception as exc:
        warn("could not start %s: %s" % (command[0], exc))
        return False


def edit_entry(entry):
    """Edit: the editor from the Preferences, else FreeCAD's own macro editor."""
    path = entry["main"] if entry["kind"] == core.ADDIN else entry["path"]
    program = editor()
    if program:
        if start_program([program, path]):
            return True, "Opened %s in %s." % (os.path.basename(path), os.path.basename(program))
        return False, "The editor %s could not be started (Preferences > General > API)." % (
            program
        )
    try:
        Gui.open(path)  # FreeCAD's own Python editor, in a tab of its own
        return True, "Opened %s in FreeCAD's editor." % os.path.basename(path)
    except Exception as exc:
        return False, "Could not open %s: %s" % (os.path.basename(path), exc)


def open_location(entry):
    folder = entry["path"] if entry["kind"] == core.ADDIN else os.path.dirname(entry["path"])
    if START_PROGRAM is not None:
        return START_PROGRAM(["open-folder", folder])
    try:
        from .compat import QtGui

        return QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
    except Exception as exc:
        warn("open folder: %s" % exc)
        return False


def create(kind, name, description=""):
    """Write a new script or add-in from the template. Returns its entry."""
    taken = [e["name"] for e in entries() if e["kind"] == kind]
    name = core.check_name(name, kind, taken)
    folder = addins_folder() if kind == core.ADDIN else scripts_folder()
    path, make = core.new_file(kind, folder, name)
    os.makedirs(make or os.path.dirname(path), exist_ok=True)
    text = (core.addin_template if kind == core.ADDIN else core.script_template)(name, description)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    log("%s %s created in %s" % (core.KIND_TITLES[kind].lower(), name, os.path.dirname(path)))
    for entry in entries():
        if entry["kind"] == kind and entry["name"] == name:
            return entry
    raise core.ScriptError("%s was written but is not listed." % name)


def add_existing(path):
    """The + button: a script from elsewhere copied into the scripts folder."""
    if not path or not os.path.isfile(path):
        raise core.ScriptError("The file was not found.")
    if not core.is_script_file(os.path.basename(path)):
        raise core.ScriptError("Pick a script (.FCMacro or .py).")
    folder = scripts_folder()
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, os.path.basename(path))
    if os.path.abspath(target) != os.path.abspath(path):
        if os.path.exists(target):
            raise core.ScriptError(
                "There is already a script called %s." % os.path.splitext(os.path.basename(path))[0]
            )
        shutil.copyfile(path, target)
    for entry in entries():
        if entry["kind"] == core.SCRIPT and os.path.abspath(entry["path"]) == os.path.abspath(
            target
        ):
            return entry
    raise core.ScriptError("The script was copied but is not listed.")


# -- the dialogs ---------------------------------------------------------------------------------
class CreateDialog(QtWidgets.QDialog):
    """Fusion's Create New Script or Add-In: Script / Add-In, Name, Description."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("SciForgeScriptCreate")
        self.setWindowTitle("Create New Script or Add-In")
        self.setModal(True)
        form = QtWidgets.QFormLayout(self)
        self.kind = QtWidgets.QComboBox()
        self.kind.setObjectName("SciForgeScriptCreateKind")
        self.kind.addItem("Script", core.SCRIPT)
        self.kind.addItem("Add-In", core.ADDIN)
        form.addRow("Type", self.kind)
        self.name = QtWidgets.QLineEdit()
        self.name.setObjectName("SciForgeScriptCreateName")
        form.addRow("Name", self.name)
        self.description = QtWidgets.QLineEdit()
        self.description.setObjectName("SciForgeScriptCreateDescription")
        form.addRow("Description", self.description)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        form.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Create")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.created = None

    def accept(self):
        try:
            self.created = create(
                self.kind.currentData(), self.name.text(), self.description.text()
            )
        except core.ScriptError as exc:
            self.message.setText("⚠ %s" % exc)
            return
        except OSError as exc:
            self.message.setText("⚠ It could not be written: %s" % exc)
            return
        super().accept()


class ScriptsDialog(QtWidgets.QDialog):
    last = None
    COLUMNS = ["Name", "Type", "Run on Startup", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        ScriptsDialog.last = self
        self.setObjectName("SciForgeScripts")
        self.setWindowTitle("Scripts and Add-Ins")
        self.setWindowIcon(ui_icon("parameters"))
        self.resize(620, 460)
        layout = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.filter = QtWidgets.QLineEdit()
        self.filter.setObjectName("SciForgeScriptsFilter")
        self.filter.setPlaceholderText("Search")
        self.filter.textChanged.connect(lambda *_: self.refresh())
        self.add_button = QtWidgets.QPushButton("+")
        self.add_button.setObjectName("SciForgeScriptsAdd")
        self.add_button.setFixedWidth(32)
        self.add_button.setToolTip("Add a script from another folder (it is copied here)")
        self.add_button.clicked.connect(self._add)
        top.addWidget(self.filter, 1)
        top.addWidget(self.add_button)
        layout.addLayout(top)
        self.list = QtWidgets.QTreeWidget()
        self.list.setObjectName("SciForgeScriptsList")
        self.list.setColumnCount(len(self.COLUMNS))
        self.list.setHeaderLabels(self.COLUMNS)
        self.list.setRootIsDecorated(False)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemDoubleClicked.connect(lambda *_: self.run_selected())
        self.list.itemChanged.connect(self._item_changed)
        self.list.currentItemChanged.connect(lambda *_: self._buttons())
        layout.addWidget(self.list, 1)
        self.where = QtWidgets.QLabel("")
        self.where.setWordWrap(True)
        self.where.setStyleSheet("color: #c3cad4;")
        layout.addWidget(self.where)
        self.message = QtWidgets.QLabel("")
        self.message.setObjectName("SciForgeScriptsMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        row = QtWidgets.QHBoxLayout()
        self.run_button = self._button("Run", "SciForgeScriptsRun", self.run_selected)
        self.create_button = self._button("Create", "SciForgeScriptsCreate", self.create_new)
        self.edit_button = self._button("Edit", "SciForgeScriptsEdit", self.edit_selected)
        self.get_button = self._button("Get Add-Ons", "SciForgeScriptsGet", self._addon_manager)
        self.get_button.setToolTip("FreeCAD's Add-on Manager: workbenches and macros to install")
        for button in (self.run_button, self.create_button, self.edit_button):
            row.addWidget(button)
        row.addStretch(1)
        row.addWidget(self.get_button)
        close = self._button("Close", "SciForgeScriptsClose", self.reject)
        row.addWidget(close)
        layout.addLayout(row)
        self._loading = False
        self.refresh()

    def _button(self, text, name, slot):
        button = QtWidgets.QPushButton(text)
        button.setObjectName(name)
        button.clicked.connect(lambda _=False: self._guarded(slot))
        return button

    def _guarded(self, fn):
        try:
            fn()
        except core.ScriptError as exc:
            self.say(str(exc), False)
        except Exception as exc:
            warn("Scripts and Add-Ins: %s" % exc)
            self.say(str(exc), False)

    def say(self, text, ok=True):
        self.message.setStyleSheet("color: %s;" % ("#9fe0a0" if ok else "#ff8a80"))
        self.message.setText(text)

    # -- the list -------------------------------------------------------------------------
    def refresh(self, select=None):
        current = select or self.selected_key()
        self._loading = True
        try:
            self.list.clear()
            keys = startup_keys()
            for entry in entries():
                if not core.matches(entry, self.filter.text()):
                    continue
                item = QtWidgets.QTreeWidgetItem(
                    self.list,
                    [
                        entry["name"],
                        core.KIND_TITLES[entry["kind"]],
                        "",
                        "Running" if is_running(entry) else "",
                    ],
                )
                item.setData(0, QtCore.Qt.UserRole, entry)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(
                    2,
                    QtCore.Qt.Checked if core.entry_key(entry) in keys else QtCore.Qt.Unchecked,
                )
                item.setToolTip(0, entry["path"])
                if current and core.entry_key(entry) == current:
                    self.list.setCurrentItem(item)
            for c in range(len(self.COLUMNS)):
                self.list.resizeColumnToContents(c)
        finally:
            self._loading = False
        self.where.setText("Scripts: %s\nAdd-ins: %s" % (scripts_folder(), addins_folder()))
        self._buttons()

    def selected(self):
        item = self.list.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item is not None else None

    def selected_key(self):
        entry = self.selected()
        return core.entry_key(entry) if entry else None

    def item_for(self, kind, name):
        for i in range(self.list.topLevelItemCount()):
            item = self.list.topLevelItem(i)
            entry = item.data(0, QtCore.Qt.UserRole)
            if entry and entry["kind"] == kind and entry["name"] == name:
                return item
        return None

    def _buttons(self):
        entry = self.selected()
        self.run_button.setEnabled(entry is not None)
        self.edit_button.setEnabled(entry is not None)
        self.run_button.setText("Stop" if entry is not None and is_running(entry) else "Run")

    def _item_changed(self, item, column):
        if self._loading or column != 2:
            return
        entry = item.data(0, QtCore.Qt.UserRole)
        if entry is None:
            return
        on = item.checkState(2) == QtCore.Qt.Checked
        try:
            set_startup(entry, on)
            self.say(
                "%s runs when SciForge starts." % entry["name"]
                if on
                else "%s no longer runs at start-up." % entry["name"]
            )
        except Exception as exc:
            warn("Run on Startup: %s" % exc)

    # -- actions --------------------------------------------------------------------------
    def run_selected(self):
        entry = self.selected()
        if entry is None:
            raise core.ScriptError("Pick a script or an add-in first.")
        ok, message = run_entry(entry)
        self.say(message, ok)
        self.refresh(core.entry_key(entry))

    def edit_selected(self):
        entry = self.selected()
        if entry is None:
            raise core.ScriptError("Pick a script or an add-in first.")
        ok, message = edit_entry(entry)
        self.say(message, ok)

    def create_new(self):
        dialog = CreateDialog(self)
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        dialog.accepted.connect(lambda: self._created(dialog.created))
        dialog.open()
        return dialog

    def _created(self, entry):
        if entry is None:
            return
        self.refresh(core.entry_key(entry))
        self.say("%s %s created. Edit opens it." % (core.KIND_TITLES[entry["kind"]], entry["name"]))

    def _add(self):
        def pick():
            if FILE_PICKER is not None:
                return FILE_PICKER("Add Script", scripts_folder())
            path, _f = QtWidgets.QFileDialog.getOpenFileName(
                self, "Add Script", os.path.expanduser("~"), "Scripts (*.FCMacro *.py)"
            )
            return path

        try:
            path = pick()
            if not path:
                return
            entry = add_existing(path)
            self.refresh(core.entry_key(entry))
            self.say("%s added." % entry["name"])
        except core.ScriptError as exc:
            self.say(str(exc), False)
        except OSError as exc:
            self.say("It could not be copied: %s" % exc, False)

    def _addon_manager(self):
        try:
            Gui.runCommand("Std_AddonMgr")
        except Exception as exc:
            self.say("The Add-on Manager could not open: %s" % exc, False)

    def _menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        self.list.setCurrentItem(item)
        entry = item.data(0, QtCore.Qt.UserRole)
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeScriptsMenu")
        run = menu.addAction("Stop" if is_running(entry) else "Run")
        edit = menu.addAction("Edit")
        where = menu.addAction("Open File Location")
        chosen = menu.exec_(self.list.viewport().mapToGlobal(pos))
        if chosen is run:
            self._guarded(self.run_selected)
        elif chosen is edit:
            self._guarded(self.edit_selected)
        elif chosen is where:
            open_location(entry)


def show():
    dialog = _state.get("dialog")
    try:
        if dialog is not None and dialog.isVisible():
            dialog.refresh()
            dialog.raise_()
            dialog.activateWindow()
            return dialog
    except RuntimeError:
        pass
    dialog = ScriptsDialog()
    _state["dialog"] = dialog

    def closed(*_):
        from . import preferences_ui

        QtCore.QTimer.singleShot(0, preferences_ui.refocus_main)

    dialog.finished.connect(closed)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


class ScriptsCommand:
    def GetResources(self):
        return {
            "MenuText": "Scripts and Add-Ins",
            "ToolTip": "Run, create and edit scripts and add-ins; choose which run at start-up",
            "Pixmap": ui_icon_path("parameters"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            show()
        except Exception as exc:
            warn("Scripts and Add-Ins: %s" % exc)
            commands.tell("Scripts and Add-Ins could not open: %s" % exc)


COMMANDS = {"SciForge_ScriptsAddIns": ScriptsCommand}
