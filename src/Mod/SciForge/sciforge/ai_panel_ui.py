# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI panel: one panel at the right of the window for everything AI (Luca, 2026-10-19:
reachable from an open design, a clear X to close it, a switch for AI control, the AIs
added shown with their icons, room for several). Parity: docs/sciforge/parity/ai.md.

  * its title bar: AI and an X that closes it (the browser's look);
  * AI control: a switch, the same option as Preferences > AI;
  * Your AIs: the AI apps set up (Claude Desktop, Gemini CLI) and the AIs of the chat with
    a key kept (or a local model's address), each with its badge; double-click one to use
    it; + Add an AI;
  * two tabs: Chat (ai/chat_ui.py) and Activity (ai_ui.ActivityPanel).

UTILITIES > AI and Home's Open AI panel show it; File > AI Chat and AI Activity open it on
their tab. The badges are SciForge's own (a colour and letters), never a company's logo.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import log, theme, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtGui, QtWidgets

TITLE = "AI"
_state = {"dock": None}

# badge id -> (letters, colour)
BADGES = {
    "claude": ("Cl", "#c8714f"),
    "anthropic": ("Cl", "#c8714f"),
    "gemini": ("Ge", "#4c7df0"),
    "openai": ("GPT", "#2e9e7a"),
    "openai_compat": ("Lo", "#7d8593"),
    "other": ("AI", "#7d8593"),
}

QSS = """
#SciForgeAIPanel {{ background: {chrome}; }}
#SciForgeAITitle {{ background: {chrome}; border-bottom: 1px solid {line}; }}
#SciForgeAITitle QLabel {{ color: {text}; font-weight: bold; letter-spacing: 0.5px; }}
#SciForgeAIClose {{ background: transparent; border: none; border-radius: 2px; padding: 3px; }}
#SciForgeAIClose:hover {{ background: {hover}; }}
#SciForgeAIToggle {{ color: {text}; font-size: 13px; }}
#SciForgeAIToggle::indicator {{ width: 34px; height: 18px; border-radius: 9px;
    background: #5d6778; border: none; image: none; }}
#SciForgeAIToggle::indicator:checked {{ background: {accent}; }}
#SciForgeAIToggleState {{ color: {text_dim}; }}
#SciForgeAIApps {{ background: {view}; border: 1px solid {line}; }}
#SciForgeAIApps::item {{ padding: 3px; }}
#SciForgeAIAppsTitle {{ color: {text_dim}; font-size: 11px; letter-spacing: 0.5px; }}
"""


def _qss():
    return QSS.format(
        chrome=theme.CHROME,
        view=theme.VIEW,
        line=theme.LINE,
        text=theme.TEXT,
        text_dim=theme.TEXT_DIM,
        hover=theme.HOVER,
        accent=theme.ACCENT,
    )


def badge(badge_id, size=28):
    """An AI's badge: its letters on its colour, in a rounded square (SciForge's own)."""
    letters, colour = BADGES.get(badge_id, BADGES["other"])
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(colour))
        painter.drawRoundedRect(QtCore.QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(size * (0.34 if len(letters) > 2 else 0.42)))
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignCenter, letters)
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


def entries():
    """The AIs added: [{"id", "kind" ("app" | "chat"), "badge", "name", "status"}]: the AI
    apps set up, then the chat's AIs with a key kept (a local model: its address set)."""
    found = []
    try:
        from . import ai_ui

        done = ai_ui.configured()
        names = dict(ai_ui.APPS)
        for app in ("claude", "gemini"):
            if done.get(app):
                found.append(
                    dict(
                        id=app,
                        kind="app",
                        badge=app,
                        name=names[app],
                        status="AI app on this computer",
                    )
                )
    except Exception as exc:
        warn("AI panel: apps: %s" % exc)
    try:
        from . import secrets_store
        from .ai import chat_ui, providers

        prefs = App.ParamGet(chat_ui.PREFS)
        for name in providers.ORDER:
            entry = providers.get(name)
            if entry["needs_key"]:
                if not secrets_store.read(chat_ui.key_name(name), chat_ui.secrets_folder()):
                    continue
                status = "Chat here, your key"
            else:
                address = prefs.GetString("ChatAddress", "")
                if not address:
                    continue
                status = "Chat here, %s" % address
            label = entry["display_name"] if entry["needs_key"] else "Local model"
            found.append(dict(id=name, kind="chat", badge=name, name=label, status=status))
    except Exception as exc:
        warn("AI panel: chat AIs: %s" % exc)
    return found


class _TitleBar(QtWidgets.QWidget):
    """The panel's title bar: its name and an X that closes it (like the browser's)."""

    def __init__(self, dock):
        super().__init__()
        self.setObjectName("SciForgeAITitle")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(_qss())  # (a title bar is not inside the panel: its own style)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 4, 4, 4)
        label = QtWidgets.QLabel(TITLE)
        row.addWidget(label)
        row.addStretch(1)
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setObjectName("SciForgeAIClose")
        self.close_button.setIcon(ui_icon("panel_close"))
        self.close_button.setProperty("sciforgeIcon", "panel_close")
        self.close_button.setIconSize(QtCore.QSize(14, 14))
        self.close_button.setToolTip("Close the AI panel (UTILITIES > AI opens it again)")
        self.close_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_button.clicked.connect(dock.close)
        row.addWidget(self.close_button)


class AIPanel(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeAIPanel")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(_qss())
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(8, 8, 8, 6)
        column.setSpacing(6)
        self.toggle = QtWidgets.QCheckBox("AI control")
        self.toggle.setObjectName("SciForgeAIToggle")
        self.toggle.setToolTip(
            "Allow AI apps (Claude Desktop, Gemini CLI...) to control SciForge. "
            "The same switch as Preferences > AI."
        )
        self.toggle.toggled.connect(self._toggled)
        column.addWidget(self.toggle, 0, QtCore.Qt.AlignLeft)  # (clicks on it, not beside it)
        self.toggle_state = QtWidgets.QLabel("")
        self.toggle_state.setObjectName("SciForgeAIToggleState")
        self.toggle_state.setWordWrap(True)
        column.addWidget(self.toggle_state)
        apps_title = QtWidgets.QLabel("YOUR AIs")
        apps_title.setObjectName("SciForgeAIAppsTitle")
        column.addWidget(apps_title)
        self.apps = QtWidgets.QListWidget()
        self.apps.setObjectName("SciForgeAIApps")
        self.apps.setIconSize(QtCore.QSize(26, 26))
        self.apps.setMaximumHeight(4 * 38 + 4)  # four rows show; more scroll
        self.apps.itemDoubleClicked.connect(self.use)
        column.addWidget(self.apps)
        row = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("+ Add an AI")
        self.add_button.setObjectName("SciForgeAIPanelAdd")
        self.add_button.setToolTip("Claude Desktop, Gemini CLI, or a chat AI with your own key")
        self.add_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, _add_ai))
        row.addWidget(self.add_button)
        row.addStretch(1)
        column.addLayout(row)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SciForgeAITabs")
        from . import ai_ui
        from .ai import chat_ui

        self.chat = chat_ui.ChatPanel()
        self.activity = ai_ui.ActivityPanel()
        self.tabs.addTab(self.chat, "Chat")
        self.tabs.addTab(self.activity, "Activity")
        column.addWidget(self.tabs, 1)
        self.refresh()

    def refresh(self):
        """The switch and the AIs as they are now."""
        try:
            from .ai import bridge

            self.toggle.blockSignals(True)
            self.toggle.setChecked(bridge.allowed())
            self.toggle.blockSignals(False)
            self.toggle_state.setText(
                "On: the AI apps you added can build in SciForge (it asks once per session)."
                if bridge.allowed()
                else "Off: AI apps cannot touch SciForge. The chat below still works."
            )
            self.apps.clear()
            found = entries()
            for entry in found:
                item = QtWidgets.QListWidgetItem(
                    badge(entry["badge"]), "%s\n%s" % (entry["name"], entry["status"])
                )
                item.setData(QtCore.Qt.UserRole, (entry["kind"], entry["id"]))
                item.setToolTip(
                    "Double-click: chat with it here"
                    if entry["kind"] == "chat"
                    else "Double-click: set up again, or remove"
                )
                self.apps.addItem(item)
            if not found:
                item = QtWidgets.QListWidgetItem("No AI added yet: + Add an AI")
                item.setFlags(QtCore.Qt.NoItemFlags)
                self.apps.addItem(item)
            self.activity.refresh()
        except RuntimeError:
            pass
        except Exception as exc:
            warn("AI panel: %s" % exc)

    def names(self):
        """The AIs listed (tests)."""
        return [
            self.apps.item(i).text().split("\n")[0]
            for i in range(self.apps.count())
            if self.apps.item(i).data(QtCore.Qt.UserRole)
        ]

    def _toggled(self, on):
        try:
            from . import ai_ui
            from .ai import bridge

            bridge.set_allowed(on)
            log("AI control %s (AI panel)" % ("on" if on else "off"))
            self.refresh()
            ai_ui._refresh_home()
        except Exception as exc:
            warn("AI panel: %s" % exc)

    def use(self, item):
        """Double-click an AI: the chat with it, or its set-up (Add an AI)."""
        try:
            data = item.data(QtCore.Qt.UserRole) if item is not None else None
            if not data:
                return
            kind, name = data
            if kind == "chat":
                index = self.chat.provider.findData(name)
                if index >= 0:
                    self.chat.provider.setCurrentIndex(index)
                self.tabs.setCurrentWidget(self.chat)
                self.chat.input.setFocus()
            else:
                QtCore.QTimer.singleShot(0, lambda: _add_ai(name))
        except Exception as exc:
            warn("AI panel: %s" % exc)


def _add_ai(app=None):
    from . import ai_ui

    dialog = ai_ui.add_ai()
    try:
        if app and dialog is not None:
            index = dialog.app.findData(app)
            if index >= 0:
                dialog.app.setCurrentIndex(index)
    except Exception as exc:
        warn("AI panel: %s" % exc)
    return dialog


# -- the dock --------------------------------------------------------------------------------------
def dock():
    """The AI panel's dock (made the first time)."""
    found = _state["dock"]
    try:
        if found is not None:
            found.isVisible()
            return found
    except RuntimeError:
        pass
    main = Gui.getMainWindow()
    found = QtWidgets.QDockWidget(TITLE, main)
    found.setObjectName("SciForgeAIDock")
    found.setTitleBarWidget(_TitleBar(found))
    found.setWidget(AIPanel())
    found.setMinimumWidth(300)
    main.addDockWidget(QtCore.Qt.RightDockWidgetArea, found)
    _state["dock"] = found
    return found


def panel():
    """The AI panel while it exists, else None."""
    found = _state["dock"]
    try:
        return found.widget() if found is not None else None
    except RuntimeError:
        return None


def is_shown():
    found = _state["dock"]
    try:
        return found is not None and found.isVisible()
    except RuntimeError:
        return False


def show(tab=None):
    """Show the AI panel (on the Chat or Activity tab when asked)."""
    found = dock()
    found.show()
    found.raise_()
    page = found.widget()
    page.refresh()
    if tab == "chat":
        page.tabs.setCurrentWidget(page.chat)
    elif tab == "activity":
        page.tabs.setCurrentWidget(page.activity)
    return found


def toggle():
    """UTILITIES > AI: show the panel, or close it when it shows."""
    if is_shown():
        _state["dock"].close()
        return False
    show()
    return True


def refresh():
    page = panel()
    if page is not None:
        page.refresh()


class PanelCommand:
    def GetResources(self):
        return {
            "MenuText": "AI",
            "ToolTip": "The AI panel: chat with an AI that builds here, the AI apps you added, "
            "AI control on or off, what the AIs did",
            "Pixmap": ui_icon_path("ai_panel"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            toggle()
        except Exception as exc:
            warn("AI panel: %s" % exc)


COMMANDS = {"SciForge_AIPanel": PanelCommand}
