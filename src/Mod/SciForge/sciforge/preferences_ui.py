# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Preferences window (UTILITIES > Preferences): the pages on the left (General with
Design and API under it, Material, Graphics, Unit and Value Display, Default Units, Network),
the options of the page on the right, Restore Defaults at the lower left, OK / Cancel / Apply.

The pages and options are data (prefs_core.py); every option is kept where it acts: FreeCAD's
own parameters (units, language, anti-aliasing...) or SciForge's (the mouse preset, reverse
zoom, design history for new designs...). The ones that change the 3D view's mouse are applied
while SciForge is on and the user's own FreeCAD values come back when it is off
(theme.keep_and_set / give_back), like the rest of SciForge's viewer settings.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, theme, ui_icon, ui_icon_path, warn
from . import prefs_core as core
from .compat import QtCore, QtWidgets

BACKUP = "User parameter:BaseApp/Preferences/Mod/SciForge/PreferencesBackup"
# Shown for an option whose parameter was never set (FreeCAD's own default applies).
FALLBACK = {
    "anti_aliasing": 0,
    "transparency": 0,
    "show_fps": False,
    "decimals": 2,
    "default_units": 0,
}
_state = {"on": False, "observer": None, "dialog": None}


# -- reading and writing ------------------------------------------------------------------------
def _group(path):
    return App.ParamGet(path)


def _has(group, kind, name):
    try:
        return name in getattr(group, "Get" + kind + "s")()
    except Exception:
        return False


def _fallback(opt):
    key = opt["key"]
    if key in FALLBACK:
        return FALLBACK[key]
    if key == "language":
        return _current_language()
    if key == "project_folder":
        from . import versions_ui

        return versions_ui.project_folder()
    if key == "scripts_folder":
        return App.getUserMacroDir(True)
    if key == "addins_folder":
        return addins_folder()
    if key == "script_editor":
        return ""
    return opt["default"]


def _current_language():
    """The language FreeCAD runs in (its name as the language list has it)."""
    try:
        locales = Gui.supportedLocales()
    except Exception:
        locales = {}
    try:
        code = Gui.getLocale() if hasattr(Gui, "getLocale") else ""
    except Exception:
        code = ""
    for name, value in locales.items():
        if code and (value == code or name == code):
            return name
    return "English" if "English" in locales or not locales else sorted(locales)[0]


def value(key):
    """The option's value now (its parameter, else its default)."""
    opt = core.option(key)
    store = opt["store"]
    if store is None:
        return opt["default"]
    path, kind, name = store
    group = _group(path)
    if _has(group, kind, name):
        try:
            return getattr(group, "Get" + kind)(name)
        except Exception:
            pass
    return opt["default"] if opt["default"] is not None else _fallback(opt)


def write(key, new_value):
    """Keep one option (its parameter, or removed for a None default)."""
    opt = core.option(key)
    for path, kind, name, val in core.writes(opt, new_value):
        group = _group(path)
        if val is None:
            getattr(group, "Rem" + kind)(name)
        else:
            getattr(group, "Set" + kind)(name, val)


def addins_folder():
    try:
        path = _group(core.PREFS).GetString("AddInsFolder", "")
    except Exception:
        path = ""
    return path or os.path.join(App.getUserAppDataDir(), "SciForge", "AddIns")


def mouse_preset():
    try:
        preset = _group(core.PREFS).GetString("MousePreset", core.DEFAULT_MOUSE)
    except Exception:
        return core.DEFAULT_MOUSE
    return (
        preset
        if preset in core.choice_values(core.option("mouse_preset"), True)
        else (core.DEFAULT_MOUSE)
    )


def fusion_mouse():
    """True while the mouse works Fusion's way (orbit_ui's middle-button handling)."""
    return mouse_preset() == "fusion"


def capture_history_default():
    try:
        return _group(core.PREFS).GetBool("CaptureHistory", True)
    except Exception:
        return True


# -- applying -----------------------------------------------------------------------------------
def _viewer_settings():
    """SciForge's values of FreeCAD's viewer parameters this window decides (the user's own
    are kept in BACKUP while SciForge is on)."""
    reverse = bool(value("reverse_zoom"))
    return [(core.VIEW, "Bool", "InvertZoom", core.invert_zoom(reverse))]


# Written again after a new NavigationStyle (theme.VIEWER_SETTINGS sets them after it too).
_AFTER_STYLE = ("OrbitStyle", "RotationMode", "ShowRotationCenter", "ZoomAtCursor")


def _set_navigation(style):
    """FreeCAD's navigation style for the mouse preset. FreeCAD tells every 3D view about
    each write, even of the same value, and a view then makes a new navigation style that
    has lost the orbit settings: written only when it changes, and then the orbit settings
    written again after it."""
    group = _group(core.VIEW)
    if group.GetString("NavigationStyle", "") == style:
        return False
    group.SetString("NavigationStyle", style)
    for name in _AFTER_STYLE:
        if name in group.GetInts():
            group.SetInt(name, group.GetInt(name))
        elif name in group.GetBools():
            group.SetBool(name, group.GetBool(name))
    return True


def apply_viewer():
    """The mouse preset and the zoom direction on FreeCAD's 3D views (SciForge on only)."""
    if not _state["on"]:
        return
    try:
        # NavigationStyle is kept with SciForge's own viewer settings (theme.VIEWER_SETTINGS):
        # the user's value comes back when SciForge is off.
        _set_navigation(core.mouse_style(mouse_preset()))
    except Exception as exc:
        warn("preferences: mouse: %s" % exc)
    try:
        settings = _viewer_settings()
        group = _group(core.VIEW)
        kept = theme._backup_key(core.VIEW, "InvertZoom") in _group(BACKUP).GetStrings()
        if not kept or any(group.GetBool(n, not v) != v for _p, _k, n, v in settings):
            theme.keep_and_set(settings, BACKUP)
    except Exception as exc:
        warn("preferences: zoom direction: %s" % exc)


def _apply(kind):
    try:
        if kind in ("mouse", "zoom"):
            apply_viewer()
        elif kind == "orbit":
            from . import orbit_ui, shell

            if shell.is_on():
                orbit_ui.apply_mode()
        elif kind == "recovery":
            from . import versions_ui

            recovery = versions_ui.recovery()
            if recovery is not None:
                recovery.restart()
        elif kind == "project":
            from . import versions_ui

            panel = versions_ui._state.get("panel")
            if versions_ui._alive(panel):
                panel.set_folder(versions_ui.project_folder())
    except Exception as exc:
        warn("preferences: %s: %s" % (kind, exc))


def save(values, remove=()):
    """Keep {key: value} and apply what changed; the keys in `remove` go back to FreeCAD's own
    default (their parameter is removed). Returns the keys that need a restart."""
    before = {k: value(k) for k in values}
    restart = []
    applies = []
    for key in remove:
        opt = core.option(key)
        if opt["store"] is None or not opt["available"]:
            continue
        path, kind, name = opt["store"]
        if not _has(_group(path), kind, name):
            continue
        write(key, None)
        if opt["restart"]:
            restart.append(key)
        if opt["apply"] and opt["apply"] not in applies:
            applies.append(opt["apply"])
    for key, val in values.items():
        opt = core.option(key)
        if opt["store"] is None or not opt["available"] or key in remove:
            continue
        if val == before.get(key):
            continue
        write(key, val)
        if opt["restart"]:
            restart.append(key)
        if opt["apply"] and opt["apply"] not in applies:
            applies.append(opt["apply"])
    for kind in applies:
        _apply(kind)
    if applies or restart:
        log("preferences saved (%s)" % ", ".join(applies + restart))
    return restart


def reset_for_tests():
    """The test harness (harness.run): every option that changes how clicks, views or new
    designs behave back to its default, so a scenario never inherits another's choice."""
    for key in (
        "mouse_preset",
        "reverse_zoom",
        "capture_history",
        "default_units",
        "default_material",
        "orientation",
    ):
        opt = core.option(key)
        try:
            write(key, opt["default"])
        except Exception as exc:
            warn("preferences reset %s: %s" % (key, exc))
    try:  # no scripts or add-ins run at start-up in the next scenario
        App.ParamGet(core.PREFS).RemString("RunOnStartup")
    except Exception:
        pass
    apply_viewer()


# -- new designs ---------------------------------------------------------------------------------
class _NewDesigns:
    """A design made with New (not opened from a file) gets the Design preferences: Capture
    design history off makes it a direct design from the start. (Its units come from FreeCAD,
    which gives every new document the default unit schema.)"""

    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            QtCore.QTimer.singleShot(0, lambda: _new_design(name))
        except Exception:
            pass


def _new_design(name):
    try:
        if name not in App.listDocuments() or capture_history_default():
            return
        doc = App.getDocument(name)
        if doc.FileName or doc.Objects or getattr(doc, "Restoring", False):
            return  # opened from a file, or a helper document already in use
        gdoc = Gui.getDocument(name)
        if gdoc is None or gdoc.ActiveView is None:
            return  # a hidden helper document (an import, a Derive's copy)
        from . import direct

        undo = doc.UndoMode
        doc.UndoMode = 0  # not a step to undo: the design starts this way
        try:
            direct.settings(doc, create=True).CaptureHistory = False
        finally:
            doc.UndoMode = undo
        gdoc.Modified = False
        log("%s: a new design without design history (Preferences)" % doc.Label)
    except Exception as exc:
        warn("new design preferences: %s" % exc)


def enable():
    _state["on"] = True
    apply_viewer()
    try:  # Scripts and Add-Ins ticked Run on Startup: once per session, after the start
        from . import scripts_ui

        QtCore.QTimer.singleShot(2000, scripts_ui.run_startup)
    except Exception as exc:
        warn("scripts at start-up: %s" % exc)
    if _state["observer"] is None:
        _state["observer"] = _NewDesigns()
        App.addDocumentObserver(_state["observer"])


def disable():
    _state["on"] = False
    try:
        theme.give_back(_viewer_settings(), BACKUP)
    except Exception as exc:
        warn("preferences off: %s" % exc)
    observer, _state["observer"] = _state["observer"], None
    if observer is not None:
        try:
            App.removeDocumentObserver(observer)
        except Exception:
            pass


def give_back_left_over():
    """SciForge is off: the user's own zoom direction back (a session that ended with SciForge
    on left SciForge's)."""
    try:
        theme.give_back(_viewer_settings(), BACKUP)
    except Exception as exc:
        warn("preferences: %s" % exc)


# -- the window ---------------------------------------------------------------------------------
class PreferencesDialog(QtWidgets.QDialog):
    last = None

    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        PreferencesDialog.last = self
        self.setObjectName("SciForgePreferences")
        self.setWindowTitle("Preferences")
        self.setWindowIcon(ui_icon("tl_settings"))
        self.resize(780, 560)
        # The pages scroll; their background stays the window's (a light scroll area put
        # SciForge's light text on white).
        self.setStyleSheet(
            "#SciForgePreferences QScrollArea, #SciForgePreferences QScrollArea > QWidget, "
            "#SciForgePreferences QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.widgets = {}  # key -> widget
        self.page_index = {}
        self.restart_note = QtWidgets.QLabel("")
        self.restart_note.setObjectName("SciForgePreferencesNote")
        self.restart_note.setWordWrap(True)
        self.restart_note.setStyleSheet("color: #ffcc66;")

        outer = QtWidgets.QVBoxLayout(self)
        body = QtWidgets.QHBoxLayout()
        self.pages = QtWidgets.QTreeWidget()
        self.pages.setObjectName("SciForgePreferencesPages")
        self.pages.setHeaderHidden(True)
        self.pages.setFixedWidth(210)
        self.stack = QtWidgets.QStackedWidget()
        body.addWidget(self.pages)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)
        outer.addWidget(self.restart_note)

        buttons = QtWidgets.QHBoxLayout()
        self.restore_button = QtWidgets.QPushButton("Restore Defaults")
        self.restore_button.setObjectName("SciForgePreferencesRestore")
        self.restore_button.clicked.connect(self._restore)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.setObjectName("SciForgePreferencesOK")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("SciForgePreferencesCancel")
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setObjectName("SciForgePreferencesApply")
        self.apply_button.clicked.connect(self.apply)
        for button in (self.ok_button, self.cancel_button, self.apply_button):
            buttons.addWidget(button)
        outer.addLayout(buttons)

        items = {}
        for pid, title, parent in core.pages():
            parent_item = items.get(parent)
            item = (
                QtWidgets.QTreeWidgetItem(parent_item, [title])
                if parent_item is not None
                else QtWidgets.QTreeWidgetItem(self.pages, [title])
            )
            item.setData(0, QtCore.Qt.UserRole, pid)
            items[pid] = item
            self.page_index[pid] = self.stack.addWidget(self._page(pid, title))
        self.pages.expandAll()
        self.pages.currentItemChanged.connect(self._page_changed)
        self.pages.setCurrentItem(items["general"])
        self.load()

    # -- building -------------------------------------------------------------------------
    def _page(self, pid, title):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        inner = QtWidgets.QWidget()
        inner.setObjectName("SciForgePreferencesPage_" + pid)
        layout = QtWidgets.QVBoxLayout(inner)
        heading = QtWidgets.QLabel("<b>%s</b>" % title)
        layout.addWidget(heading)
        for group, opts in core.groups(pid):
            box = QtWidgets.QGroupBox(group)
            form = QtWidgets.QFormLayout(box)
            for opt in opts:
                widget = self._widget(opt)
                self.widgets[opt["key"]] = widget
                label = QtWidgets.QLabel(opt["label"] if opt["kind"] != "bool" else "")
                if not opt["available"]:
                    widget.setEnabled(False)
                    label.setEnabled(False)
                    tip = opt["why"] + " (Not available in SciForge yet.)"
                    widget.setToolTip(tip)
                    label.setToolTip(tip)
                elif opt["tip"]:
                    widget.setToolTip(opt["tip"])
                    label.setToolTip(opt["tip"])
                form.addRow(label, widget)
            layout.addWidget(box)
        if pid == "network":
            note = QtWidgets.QLabel(
                "SciForge never sends anything anywhere: there is no account and no data "
                "collection. Only the Add-on Manager goes online, with these settings."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #c3cad4;")
            layout.addWidget(note)
        layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _widget(self, opt):
        kind = opt["kind"]
        name = "SciForgePref_" + opt["key"]
        if kind == "bool":
            widget = QtWidgets.QCheckBox(opt["label"])
        elif kind == "int":
            widget = QtWidgets.QSpinBox()
            widget.setRange(
                opt["minimum"] if opt["minimum"] is not None else -(10**6),
                opt["maximum"] if opt["maximum"] is not None else 10**6,
            )
            if opt["suffix"]:
                widget.setSuffix(opt["suffix"])
            widget.setKeyboardTracking(False)
        elif kind == "choice":
            widget = QtWidgets.QComboBox()
            for val, label, available, why in self._choices(opt):
                widget.addItem(label, val)
                if not available:
                    index = widget.count() - 1
                    model_item = widget.model().item(index)
                    if model_item is not None:
                        model_item.setEnabled(False)
                        model_item.setToolTip(why + " (Not available in SciForge yet.)")
                    widget.setItemData(
                        index, why + " (Not available in SciForge yet.)", QtCore.Qt.ToolTipRole
                    )
        elif kind in ("folder", "file"):
            widget = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(widget)
            row.setContentsMargins(0, 0, 0, 0)
            field = QtWidgets.QLineEdit()
            field.setObjectName(name + "_field")
            button = QtWidgets.QToolButton()
            button.setText("...")
            button.clicked.connect(lambda _=False, o=opt, f=field: self._browse(o, f))
            row.addWidget(field, 1)
            row.addWidget(button)
            widget.field = field
        else:
            widget = QtWidgets.QLineEdit()
        widget.setObjectName(name)
        return widget

    def _choices(self, opt):
        if opt["key"] == "language":
            try:
                names = sorted(Gui.supportedLocales().keys())
            except Exception:
                names = ["English"]
            return [(n, n, True, "") for n in names]
        if opt["key"] == "default_material":
            from . import material

            return [(e["key"], e["label"], True, "") for e in material.entries()]
        return opt["choices"]

    def _browse(self, opt, field):
        try:
            if opt["kind"] == "folder":
                path = QtWidgets.QFileDialog.getExistingDirectory(self, opt["label"], field.text())
            else:
                path, _f = QtWidgets.QFileDialog.getOpenFileName(self, opt["label"], field.text())
            if path:
                field.setText(path)
        except Exception as exc:
            warn("preferences: %s" % exc)

    def _page_changed(self, current, _previous):
        if current is None:
            return
        pid = current.data(0, QtCore.Qt.UserRole)
        if pid in self.page_index:
            self.stack.setCurrentIndex(self.page_index[pid])

    def show_page(self, pid):
        for item in self.pages.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
            if item.data(0, QtCore.Qt.UserRole) == pid:
                self.pages.setCurrentItem(item)
                return True
        return False

    def current_page(self):
        item = self.pages.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item is not None else None

    # -- values ---------------------------------------------------------------------------
    def set_widget(self, key, val):
        widget = self.widgets[key]
        opt = core.option(key)
        kind = opt["kind"]
        if kind == "bool":
            widget.setChecked(bool(val))
        elif kind == "int":
            widget.setValue(int(val if val is not None else 0))
        elif kind == "choice":
            index = widget.findData(val)
            if index < 0 and val is not None:
                index = widget.findText(str(val))
            if index < 0 and val is not None and val != "":
                # A value the list does not have (a language FreeCAD names differently): shown
                # as it is, so OK never changes it by accident.
                widget.insertItem(0, str(val), val)
                index = 0
            if index >= 0:
                widget.setCurrentIndex(index)
        elif kind in ("folder", "file"):
            widget.field.setText(str(val or ""))
        else:
            widget.setText(str(val or ""))

    def get_widget(self, key):
        widget = self.widgets[key]
        kind = core.option(key)["kind"]
        if kind == "bool":
            return widget.isChecked()
        if kind == "int":
            return int(widget.value())
        if kind == "choice":
            return widget.currentData()
        if kind in ("folder", "file"):
            return widget.field.text().strip()
        return widget.text().strip()

    def load(self):
        self.loaded = {}
        for opt in core.options():
            key = opt["key"]
            try:
                val = value(key)
            except Exception as exc:
                warn("preferences: %s: %s" % (key, exc))
                val = opt["default"]
            self.loaded[key] = val
            try:
                self.set_widget(key, val)
            except Exception as exc:
                warn("preferences: %s: %s" % (key, exc))
        self.restart_note.setText("")
        self.restored = False

    def values(self):
        found = {}
        for opt in core.options():
            if opt["store"] is None or not opt["available"]:
                continue
            try:
                found[opt["key"]] = self.get_widget(opt["key"])
            except Exception as exc:
                warn("preferences: %s: %s" % (opt["key"], exc))
        return found

    # -- buttons --------------------------------------------------------------------------
    def apply(self):
        try:
            values = self.values()
            changed = {k: v for k, v in values.items() if v != self.loaded.get(k)}
            remove = []
            if self.restored:  # FreeCAD's own defaults: their parameters removed again
                for key, val in values.items():
                    opt = core.option(key)
                    if opt["default"] is None and val == _fallback_default(opt):
                        remove.append(key)
            restart = save(changed, remove)
            self.load()
            if restart:
                labels = ", ".join(core.option(k)["label"] for k in restart)
                self.restart_note.setText("Restart SciForge to see the new %s." % labels)
            return True
        except core.PrefError as exc:
            self.restart_note.setText("⚠ %s" % exc)
            return False
        except Exception as exc:
            warn("preferences: %s" % exc)
            self.restart_note.setText("⚠ %s" % exc)
            return False

    def _restore(self):
        """Fusion's Restore Defaults: every option of every page to its default (OK or Apply
        keeps them, Cancel does not)."""
        for opt in core.options():
            if opt["store"] is None:
                continue
            default = opt["default"] if opt["default"] is not None else _fallback_default(opt)
            try:
                self.set_widget(opt["key"], default)
            except Exception as exc:
                warn("preferences: %s: %s" % (opt["key"], exc))
        self.restored = True
        self.restart_note.setText("Defaults shown: OK or Apply keeps them.")

    def accept(self):
        if self.apply():
            super().accept()

    def reject(self):
        super().reject()


def _fallback_default(opt):
    """The value a None default shows (FreeCAD's own default)."""
    key = opt["key"]
    if key in FALLBACK:
        return FALLBACK[key]
    if key == "language":
        return "English"
    if key == "project_folder":
        from . import versions_ui

        return versions_ui.default_project_folder()
    if key == "scripts_folder":
        return App.getUserMacroDir(False)
    if key == "addins_folder":
        return os.path.join(App.getUserAppDataDir(), "SciForge", "AddIns")
    return ""


def refocus_main():
    """After a window closes: the main window active again and the 3D view gets the keys
    (without a window manager nothing else does it, and every shortcut was dead)."""
    try:
        from . import versions_ui

        versions_ui._refocus_main()
    except Exception as exc:
        warn("focus after a dialog: %s" % exc)


def show(page=None):
    dialog = _state.get("dialog")
    try:
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            if page:
                dialog.show_page(page)
            return dialog
    except RuntimeError:
        pass
    dialog = PreferencesDialog()
    _state["dialog"] = dialog
    dialog.finished.connect(lambda *_: QtCore.QTimer.singleShot(0, refocus_main))
    if page:
        dialog.show_page(page)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


class PreferencesCommand:
    def GetResources(self):
        return {
            "MenuText": "Preferences",
            "ToolTip": "SciForge's preferences: navigation, units of new designs, design "
            "history, materials, graphics, network (Fusion's Preferences window)",
            "Pixmap": ui_icon_path("tl_settings"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            show()
        except Exception as exc:
            warn("Preferences: %s" % exc)
            commands.tell("Preferences could not open: %s" % exc)


COMMANDS = {"SciForge_Preferences": PreferencesCommand}
