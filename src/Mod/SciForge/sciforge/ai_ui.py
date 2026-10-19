# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI apps in SciForge's windows (brief home-cloud-ai.md section 4.4, milestone M3; parity:
docs/sciforge/parity/ai.md). The bridge itself is sciforge/ai/bridge.py.

  * Add an AI (Home's AI card, File > Add an AI App): sets SciForge up in Claude Desktop or
    Gemini CLI (their settings file is changed, with a backup), builds a Claude Desktop
    extension file, or shows the command line for other apps (Claude Code, Codex...).
  * The AI activity panel: every call an AI app made, Undo last AI step, Stop AI control.
"""

import os
import shutil
import sys
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, ui_icon_path, warn
from .ai import bridge, bridge_core, installers
from .compat import QtCore, QtGui, QtWidgets

OPEN_FILE = None  # tests: a function(path) instead of opening a file with its app
PYTHON = None  # tests: the Python the MCP server runs with

APPS = [
    ("claude", "Claude Desktop"),
    ("gemini", "Gemini CLI"),
    ("other", "Another app (Claude Code, Codex, ...)"),
]


# -- the MCP server's command -----------------------------------------------------------------
def python_exe():
    """A Python for the MCP server (standard library only): FreeCAD's own on Windows (a
    stable path), else python3 on the PATH (a Linux AppImage mounts at a new path at every
    start, so its own Python cannot be named in an app's settings)."""
    if PYTHON:
        return PYTHON
    candidates = []
    if os.name == "nt":
        home = App.getHomePath()
        candidates += [
            os.path.join(home, "bin", "python.exe"),
            os.path.join(os.path.dirname(sys.executable), "python.exe"),
        ]
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    mount = os.environ.get("APPDIR") or ""  # (an AppImage's own folder: gone after a restart)
    for path in candidates:
        if path and os.path.isfile(path) and not (mount and path.startswith(mount)):
            if "/.mount_" not in path:
                return path
    return "python3"


def server_env():
    """The environment to start the MCP server from SciForge (tests): without the
    PYTHONHOME / PYTHONPATH an AppImage sets for its own Python, which another Python
    cannot start with."""
    env = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(name, None)
    return env


def script_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "sciforge_mcp.py")


def bridge_file():
    return bridge_core.bridge_path(App.getUserAppDataDir())


def server_command():
    return installers.server_command(python_exe(), script_path(), bridge_file())


def configured():
    """{app: set up} for Claude Desktop and Gemini CLI."""
    return {
        "claude": installers.is_configured(installers.claude_desktop_config_path()),
        "gemini": installers.is_configured(installers.gemini_settings_path()),
    }


def set_up(app):
    """Set SciForge up in an app; the words to show. Switches AI control on (an AI app set
    up but refused would only say "SciForge is not running")."""
    command, args = server_command()
    if app == "claude":
        text = installers.add_to_claude_desktop(command, args)
    elif app == "gemini":
        text = installers.add_to_gemini(command, args)
    else:
        raise ValueError(app)
    if not bridge.allowed():
        bridge.set_allowed(True)
        text += " AI control is now on (Preferences > AI)."
    log("AI: set up in %s" % app)
    _refresh_home()
    return text


def remove(app):
    text = (
        installers.remove_from_claude_desktop()
        if app == "claude"
        else installers.remove_from_gemini()
    )
    log("AI: removed from %s" % app)
    _refresh_home()
    return text


def build_extension():
    """A Claude Desktop extension file (.mcpb): opening it installs SciForge in Claude."""
    import sciforge

    out = os.path.join(App.getUserAppDataDir(), "SciForge", "ai", "SciForge.mcpb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    mod_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    installers.build_mcpb(
        out,
        installers.mcpb_files(mod_root),
        installers.manifest(sciforge.__version__, python_exe(), bridge_file=bridge_file()),
    )
    log("AI: extension written to %s" % out)
    return out


def _open_file(path):
    if OPEN_FILE is not None:
        return OPEN_FILE(path)
    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))


def _refresh_home():
    try:
        from . import home_ui

        page = home_ui.view()
        if page is not None:
            page.update_ai()
    except Exception as exc:
        warn("AI: %s" % exc)


def status_words():
    """Home's AI card: AI control on / off, the apps set up, when last used."""
    lines = ["AI control: %s" % ("on" if bridge.allowed() else "off (Preferences > AI)")]
    try:
        done = configured()
    except Exception:
        done = {}
    names = dict(APPS)
    for app in ("claude", "gemini"):
        if done.get(app):
            lines.append("%s: set up" % names[app])
    used = bridge.last_used()
    if used:
        lines.append("Last used %s" % time.strftime("%H:%M", time.localtime(used)))
    return lines


# -- Add an AI ------------------------------------------------------------------------------------
class AddAIDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        self.setObjectName("SciForgeAddAIDialog")
        self.setWindowTitle("Add an AI app")
        column = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "An AI app you chat with (Claude Desktop, Gemini CLI...) can build in SciForge: "
            "every step it makes is in the timeline and can be undone. Nothing happens unless "
            "AI control is on, and SciForge asks you the first time in each session."
        )
        intro.setWordWrap(True)
        column.addWidget(intro)
        self.allow = QtWidgets.QCheckBox("Allow AI apps to control SciForge")
        self.allow.setObjectName("SciForgeAddAIAllow")
        self.allow.setChecked(bridge.allowed())
        self.allow.toggled.connect(self._allow)
        column.addWidget(self.allow)
        self.app = QtWidgets.QComboBox()
        self.app.setObjectName("SciForgeAddAIApp")
        for key, label in APPS:
            self.app.addItem(label, key)
        column.addWidget(self.app)
        self.note = QtWidgets.QLabel("")
        self.note.setObjectName("SciForgeAddAINote")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setObjectName("SciForgeAddAIText")
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(110)
        column.addWidget(self.text)
        row = QtWidgets.QHBoxLayout()
        self.set_up_button = QtWidgets.QPushButton("Set up")
        self.set_up_button.setObjectName("SciForgeAddAISetUp")
        self.set_up_button.clicked.connect(self._set_up)
        row.addWidget(self.set_up_button)
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.setObjectName("SciForgeAddAIRemove")
        self.remove_button.clicked.connect(self._remove)
        row.addWidget(self.remove_button)
        self.extension_button = QtWidgets.QPushButton("Install as Claude extension...")
        self.extension_button.setObjectName("SciForgeAddAIExtension")
        self.extension_button.clicked.connect(self._extension)
        row.addWidget(self.extension_button)
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.copy_button.setObjectName("SciForgeAddAICopy")
        self.copy_button.clicked.connect(self._copy)
        row.addWidget(self.copy_button)
        row.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        column.addLayout(row)
        self.app.currentIndexChanged.connect(self._app_changed)
        self._app_changed()
        self.resize(620, self.sizeHint().height())

    def _allow(self, on):
        try:
            bridge.set_allowed(on)
            _refresh_home()
        except Exception as exc:
            warn("AI: %s" % exc)

    def _app_changed(self, *_args):
        try:
            app = self.app.currentData()
            other = app == "other"
            done = configured().get(app, False)
            self.set_up_button.setVisible(not other)
            self.remove_button.setVisible(not other and done)
            self.extension_button.setVisible(app == "claude")
            self.copy_button.setVisible(other)
            command, args = server_command()
            if app == "claude":
                self.note.setText(
                    "Set up adds SciForge to Claude Desktop's settings (a backup of the file is "
                    "kept). Then quit Claude Desktop completely and start it again; SciForge's "
                    "tools show in its tools menu. Or install it as an extension file."
                    + ("\n\nSciForge is set up in Claude Desktop." if done else "")
                )
                self.text.setPlainText(installers.claude_desktop_config_path())
            elif app == "gemini":
                self.note.setText(
                    "Set up adds SciForge to Gemini CLI's settings (~/.gemini/settings.json, a "
                    "backup kept). Start Gemini CLI again and type /mcp to see SciForge listed."
                    + ("\n\nSciForge is set up in Gemini CLI." if done else "")
                )
                self.text.setPlainText(installers.gemini_settings_path())
            else:
                self.note.setText('Copy this into the app\'s MCP settings (a "stdio" server):')
                self.text.setPlainText(installers.other_app_text(command, args))
        except Exception as exc:
            warn("AI: %s" % exc)
            self.note.setText("Could not read the app's settings: %s" % exc)

    def _set_up(self):
        try:
            text = set_up(self.app.currentData())
            self.allow.blockSignals(True)
            self.allow.setChecked(bridge.allowed())
            self.allow.blockSignals(False)
            self._app_changed()
            self.text.setPlainText(text)
        except Exception as exc:
            warn("AI: set up: %s" % exc)
            self.text.setPlainText("Not set up: %s" % exc)

    def _remove(self):
        try:
            text = remove(self.app.currentData())
            self._app_changed()
            self.text.setPlainText(text)
        except Exception as exc:
            warn("AI: remove: %s" % exc)
            self.text.setPlainText("Not removed: %s" % exc)

    def _extension(self):
        try:
            path = build_extension()
            if not bridge.allowed():
                bridge.set_allowed(True)
                self.allow.setChecked(True)
            self.text.setPlainText(
                "The extension file is %s. It opens in Claude Desktop now: click Install there."
                % path
            )
            _open_file(path)
        except Exception as exc:
            warn("AI: extension: %s" % exc)
            self.text.setPlainText("The extension could not be made: %s" % exc)

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.text.toPlainText())
        commands.tell("Copied.")


def add_ai():
    from . import versions_ui

    return versions_ui._show(AddAIDialog(), "add-ai")


# -- the activity panel -----------------------------------------------------------------------------
class ActivityPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeAIActivity")
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(4, 4, 4, 4)
        self.state = QtWidgets.QLabel("")
        self.state.setWordWrap(True)
        column.addWidget(self.state)
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeAIActivityList")
        self.list.setWordWrap(True)
        column.addWidget(self.list, 1)
        row = QtWidgets.QHBoxLayout()
        self.undo_button = QtWidgets.QPushButton("Undo last AI step")
        self.undo_button.setObjectName("SciForgeAIUndo")
        self.undo_button.clicked.connect(undo_last)
        row.addWidget(self.undo_button)
        self.stop_button = QtWidgets.QPushButton("Stop AI control")
        self.stop_button.setObjectName("SciForgeAIStop")
        self.stop_button.clicked.connect(stop)
        row.addWidget(self.stop_button)
        column.addLayout(row)
        self.refresh()

    def refresh(self):
        try:
            self.state.setText(
                "AI control is on: an AI app can build in SciForge."
                if bridge.running()
                else "AI control is off."
            )
            self.stop_button.setEnabled(bridge.running())
            self.list.clear()
            for stamp, tool, text, is_error in reversed(bridge.activity()):
                short = " ".join(text.split())  # one line each (get_design answers pages)
                line = "%s  %s: %s" % (
                    time.strftime("%H:%M:%S", time.localtime(stamp)),
                    tool,
                    short if len(short) < 160 else short[:157] + "...",
                )
                item = QtWidgets.QListWidgetItem(line)
                item.setToolTip(text[:2000])
                if is_error:
                    item.setForeground(QtGui.QColor("#ef6f6c"))
                self.list.addItem(item)
        except RuntimeError:
            pass
        except Exception as exc:
            warn("AI activity: %s" % exc)


_panel = {"dock": None}


def _dock():
    dock = _panel["dock"]
    try:
        if dock is not None:
            dock.isVisible()
            return dock
    except RuntimeError:
        pass
    main = Gui.getMainWindow()
    dock = QtWidgets.QDockWidget("AI activity", main)
    dock.setObjectName("SciForgeAIActivityDock")
    dock.setWidget(ActivityPanel())
    main.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    _panel["dock"] = dock
    return dock


def panel():
    dock = _panel["dock"]
    try:
        return dock.widget() if dock is not None else None
    except RuntimeError:
        return None


def show_activity():
    dock = _dock()
    dock.show()
    dock.raise_()
    dock.widget().refresh()
    return dock


def _after_call():
    """Every AI call: the panel shows it (opened the first time), Home's card too."""
    show_activity()
    _refresh_home()


def undo_last():
    """Undo the newest step when an AI app made it (its name starts with "AI:")."""
    try:
        doc = App.ActiveDocument
        names = doc.UndoNames if doc is not None else []
        if not names or not names[0].startswith("AI:"):
            commands.tell("The last step was not made by an AI app.")
            return False
        doc.undo()
        doc.recompute()
        log("AI: undone %s" % names[0])
        p = panel()
        if p is not None:
            p.refresh()
        return True
    except Exception as exc:
        warn("AI: undo: %s" % exc)
        return False


def stop():
    """Stop AI control at once (the option goes off; calls are refused)."""
    try:
        bridge.set_allowed(False)
        p = panel()
        if p is not None:
            p.refresh()
        _refresh_home()
        commands.tell("AI control is off. Switch it on again in Preferences > AI.")
    except Exception as exc:
        warn("AI: stop: %s" % exc)


def enable():
    bridge.add_listener(_after_call)
    bridge.apply()


def disable():
    try:
        bridge.stop()
    except Exception as exc:
        warn("AI: %s" % exc)


# -- commands -------------------------------------------------------------------------------------
class AddAICommand:
    def GetResources(self):
        return {
            "MenuText": "Add an AI App",
            "ToolTip": "Let Claude Desktop, Gemini CLI or another AI app build in SciForge",
            "Pixmap": ui_icon_path("ai"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            add_ai()
        except Exception as exc:
            warn("Add an AI App: %s" % exc)


class ActivityCommand:
    def GetResources(self):
        return {
            "MenuText": "AI Activity",
            "ToolTip": "What AI apps did in SciForge; Undo the last AI step; Stop AI control",
            "Pixmap": ui_icon_path("ai"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            show_activity()
        except Exception as exc:
            warn("AI Activity: %s" % exc)


class ChatCommand:
    def GetResources(self):
        return {
            "MenuText": "AI Chat",
            "ToolTip": "Chat with an AI (Claude, ChatGPT, Gemini or a local model) that builds "
            "in SciForge, with your own key",
            "Pixmap": ui_icon_path("ai"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            from .ai import chat_ui

            chat_ui.show()
        except Exception as exc:
            warn("AI Chat: %s" % exc)


COMMANDS = {
    "SciForge_AddAI": AddAICommand,
    "SciForge_AIActivity": ActivityCommand,
    "SciForge_AIChat": ChatCommand,
}
