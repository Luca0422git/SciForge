# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab: where SciForge opens (Luca, 2026-10-19: "Make the home screen default every
time"), like Fusion's Home (docs/sciforge/parity/home.md).

A tab of its own in the document tabs (a window of FreeCAD's MDI area, as FreeCAD's Start
page is). Luca's sketch (2026-10-19): one page of rows, top to bottom,
  * Home, New design, Open..., + Connect a cloud or NAS, a search box;
  * a banner when a session left unsaved work behind (versions_ui's recovery copies);
  * Recent: the designs opened and saved, pinned ones first;
  * This computer (the folder designs are saved in, its path shown; designs saved in other
    folders of this computer too), then each cloud and NAS connected: all their designs,
    their folders' too.
Each row's tiles run left to right on as many lines as they need. A tile: picture, name,
place or folder, "edited 2 h ago", versions. Double-click opens; right-click: Open, Pin,
Show in Folder, Version History, Remove from List (a missing design: Locate...). A place's
... menu: Show in Folder, Change Folder... (This computer), Disconnect (the others).
The ribbon's commands are hidden while Home is in front (its top bar stays).

The Home button at the left of the application bar and File > Home bring it back; closing
the last design comes back to it (Fusion since April 2026). Preferences > General > Show
Home at start (on unless switched off).

The list itself is home_core.py. Pictures, file checks and version counts are read on a
worker thread (file work only: never Qt nor FreeCAD there), so a slow NAS never holds the
window; the tiles fill in as the answers come.
"""

import os
import queue
import threading
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, home_core as core, log, theme, ui_icon, versions, warn
from .compat import QtCore, QtGui, QtWidgets

OPTION = ("User parameter:BaseApp/Preferences/Mod/SciForge", "ShowHomeAtStart")
FREECAD_RECENT = "User parameter:BaseApp/Preferences/RecentFiles"
FREECAD_GENERAL = "User parameter:BaseApp/Preferences/General"  # its file dialogs' folder
TITLE = "Home"
THUMB = 132  # tile picture (px)
TILE_W, TILE_H = THUMB + 76, THUMB + 54  # (two lines of text under it)
LOCATE_PICKER = None  # tests: a function returning the path Locate... picks

_state = {"sub": None, "watch": None, "on": False, "loader": None, "refresh": None}


# -- settings and files ----------------------------------------------------------------
def show_at_start():
    """The Preferences option (on unless switched off)."""
    try:
        path, name = OPTION
        return App.ParamGet(path).GetBool(name, True)
    except Exception:
        return True


def home_dir():
    return os.path.join(App.getUserAppDataDir(), "SciForge", "home")


def recent_file():
    return os.path.join(home_dir(), "recent.json")


def thumbs_dir():
    return os.path.join(home_dir(), "thumbs")


def places():
    """{location id: its folder on this computer}: This computer, the clouds and NAS."""
    from . import locations_ui

    return locations_ui.roots()


def place_name(location_id):
    from . import locations_ui

    return locations_ui.names().get(location_id or "", "")


def _sidecar(path):
    """The small picture beside a design in a cloud place, or None (locations_core)."""
    from . import locations_core, locations_ui

    place = locations_core.place_of(path, locations_ui.all_places())
    if place is None or place["kind"] not in locations_core.CLOUD_KINDS:
        return None
    return locations_core.sidecar_file(place["root"], path)


def write_sidecar(path):
    """After a save in a cloud place: its picture beside it for the other computers."""
    try:
        target = _sidecar(path)
        data = versions.thumbnail_bytes(path) if target else None
        if data:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target + ".tmp", "wb") as handle:
                handle.write(data)
            os.replace(target + ".tmp", target)
    except Exception as exc:
        warn("home: picture beside %s: %s" % (path, exc))


def _skip_folders():
    """SciForge's own copies (recovery copies, older versions opened read-only)."""
    return [os.path.join(App.getUserAppDataDir(), "SciForge")]


def load_state():
    """The recent list; the first time, FreeCAD's own recent files join it."""
    try:
        with open(recent_file(), "r", encoding="utf-8") as handle:
            state = core.load(handle.read())
    except OSError:
        state = core.empty()
    if not state["merged_mru"]:
        try:
            group = App.ParamGet(FREECAD_RECENT)
            strings = {name: group.GetString(name) for name in group.GetStrings()}
            count = group.GetInt("RecentFiles", 0) or None
            core.merge_mru(
                state, core.mru_paths(strings, count), time.time(), places(), _skip_folders()
            )
            save_state(state)
        except Exception as exc:
            warn("home: FreeCAD's recent files: %s" % exc)
    return state


def save_state(state):
    try:
        os.makedirs(home_dir(), exist_ok=True)
        versions.atomic_write_text(recent_file(), core.dump(state))
    except Exception as exc:
        warn("home: could not write %s: %s" % (recent_file(), exc))


def record(path):
    """A design was opened or saved: first in the recent list."""
    try:
        if not core.remembered(path, _skip_folders()):
            return None
        state = load_state()
        entry = core.record(state, path, time.time(), places())
        save_state(state)
        refresh_soon()
        return entry
    except Exception as exc:
        warn("home: could not remember %s: %s" % (path, exc))
        return None


# -- the worker thread -----------------------------------------------------------------
class _Loader:
    """One background thread for the tiles' file work: does the design exist, is it online
    only, its picture (cached), its version count. Answers wait in a queue the window reads
    with a timer."""

    def __init__(self):
        self.jobs = queue.Queue()
        self.done = queue.Queue()
        self.thread = None
        self.counter = core.VersionCounter()

    def ask(self, job):
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, name="SciForgeHome", daemon=True)
            self.thread.start()
        self.jobs.put(job)

    def _run(self):
        while True:
            job = self.jobs.get()
            try:
                status, mtime, png = core.load_thumbnail(
                    job["path"], job["key"], job["cache"], sidecar=job.get("sidecar")
                )
                count = 0
                if status == core.OK and job.get("count"):
                    try:
                        count = self.counter.count(job["path"], job["project"], job["git"])
                    except Exception:
                        count = 0
                self.done.put((job, status, mtime, png, count, ""))
            except Exception as exc:  # (reported on the GUI thread)
                self.done.put((job, core.MISSING, None, None, 0, str(exc)))


def loader():
    if _state["loader"] is None:
        _state["loader"] = _Loader()
    return _state["loader"]


# -- the window ------------------------------------------------------------------------
def _tile_pixmap(png, pinned=False, dim=False):
    """The tile's picture: the design's own thumbnail (or a plain solid), a blue pin badge
    at the top right when pinned, greyed when the design is not there."""
    canvas = QtGui.QPixmap(THUMB, THUMB)
    canvas.fill(QtGui.QColor(theme.FIELD))
    painter = QtGui.QPainter(canvas)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        picture = QtGui.QPixmap()
        if not (png and picture.loadFromData(QtCore.QByteArray(png), "PNG")):
            picture = ui_icon("document").pixmap(64, 64)
        else:
            picture = picture.scaled(
                THUMB, THUMB, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
        painter.drawPixmap((THUMB - picture.width()) // 2, (THUMB - picture.height()) // 2, picture)
        if pinned:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(theme.ACCENT))
            painter.drawEllipse(THUMB - 26, 6, 20, 20)
            painter.setBrush(QtGui.QColor(theme.TEXT))  # a pin head and its point
            painter.drawEllipse(THUMB - 20, 10, 8, 8)
            painter.drawRect(THUMB - 17, 17, 2, 6)
    finally:
        painter.end()
    if dim:
        return QtGui.QIcon(canvas).pixmap(THUMB, THUMB, QtGui.QIcon.Disabled)
    return canvas


_KIND = QtCore.Qt.UserRole  # ("recent" | "design", key, path)
_STATUS = QtCore.Qt.UserRole + 1  # home_core.OK / MISSING / ONLINE
_WHERE = QtCore.Qt.UserRole + 2  # the second line's start: the place, or the folder in it
_CONFLICT = QtCore.Qt.UserRole + 3  # a conflict copy: the original's file name
_ROOT = QtCore.Qt.UserRole + 4  # the folder of the tile's place ("" for Recent)

RECENT = "recent"  # the first row

QSS = """
#SciForgeHome {{ background: {view}; }}
#SciForgeHomeScroll, #SciForgeHomeRows {{ background: {view}; border: none; }}
#SciForgeHomeAI {{ background: {chrome}; }}
#SciForgeHomeAIStatus {{ color: {text_dim}; padding: 4px 0px 8px 0px; }}
#SciForgeHomeHeading {{ color: {text}; font-size: 22px; }}
#SciForgeHomeTitle {{ color: {text}; font-size: 16px; }}
#SciForgeHomePath {{ color: {text_dim}; font-size: 12px; }}
#SciForgeHomeLine {{ background: #3b4250; border: none; }}
#SciForgeHomeEmpty {{ color: {text_dim}; font-size: 13px; padding: 6px 4px 10px 4px; }}
#SciForgeHomeList {{ background: {view}; border: none; }}
#SciForgeHomeList::item {{ color: {text}; border-radius: 3px; padding: 4px; }}
#SciForgeHomeList::item:hover {{ background: #343a46; }}
#SciForgeHomeList::item:selected {{ background: {active}; }}
#SciForgeHomeNew {{ background: {accent}; color: #ffffff; border: none; font-weight: bold;
    padding: 6px 18px; }}
#SciForgeHomeNew:hover {{ background: #5bb8f7; }}
#SciForgeHomeRecovery {{ background: #5a4a2a; border-radius: 3px; }}
#SciForgeHomeClear, #SciForgeHomeConnect, #SciForgeHomePlaceMenu {{ color: {accent};
    background: transparent; border: none; }}
#SciForgeHomePlaceMenu {{ font-size: 16px; font-weight: bold; padding: 0px 6px; }}
"""


def _colours():
    """The theme's colours by name, for the style sheets."""
    return dict(
        view=theme.VIEW,
        chrome=theme.CHROME,
        active=theme.ACTIVE,
        line=theme.LINE,
        hover=theme.HOVER,
        text=theme.TEXT,
        text_dim=theme.TEXT_DIM,
        accent=theme.ACCENT,
    )


class _Painted(QtWidgets.QWidget):
    """A panel that paints its own background in a colour of the look (theme.py), whatever
    the Qt style: on Luca's Windows the AI column came out white in the dark look, its
    style sheet's background not drawn (it was here, on Linux)."""

    def __init__(self, colour_name):
        super().__init__()
        self.colour_name = colour_name

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        try:
            painter.fillRect(self.rect(), QtGui.QColor(getattr(theme, self.colour_name)))
        finally:
            painter.end()


def _no_tab_focus(widget):
    """Home's buttons and tiles take the keyboard focus only when clicked, never through
    the Tab order: a timeline button hidden while it had the focus gave it to the next
    widget in that order, a button of Home's newer rows, and the focus in Home's tab
    brought Home to the front over the design being edited."""
    for child in [widget] + widget.findChildren(QtWidgets.QWidget):
        policy = child.focusPolicy()
        if policy & QtCore.Qt.TabFocus:
            strong = (policy & QtCore.Qt.ClickFocus) and not isinstance(
                child, QtWidgets.QAbstractButton
            )
            child.setFocusPolicy(QtCore.Qt.ClickFocus if strong else QtCore.Qt.NoFocus)


class _Tiles(QtWidgets.QListWidget):
    """A row's tiles: left to right, on as many lines as they need so every design shows
    (no scroll bar of its own: the Home page scrolls)."""

    def __init__(self, row_id):
        super().__init__()
        self.setObjectName("SciForgeHomeList")
        self.setProperty("row", row_id)
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setWrapping(True)
        self.setIconSize(QtCore.QSize(THUMB, THUMB))
        self.setGridSize(QtCore.QSize(TILE_W, TILE_H))
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMovement(QtWidgets.QListView.Static)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setFixedHeight(0)

    def fit(self):
        """As tall as its lines of tiles."""
        try:
            per_line = max(1, self.viewport().width() // TILE_W)
            lines = (self.count() + per_line - 1) // per_line
            self.setFixedHeight(lines * TILE_H + 2 * self.frameWidth() + (6 if lines else 0))
        except RuntimeError:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.fit)


class _Row(QtWidgets.QWidget):
    """One row of Home: a heading (Recent, This computer, Dropbox...) over its tiles."""

    def __init__(self, page, row_id, title, icon, path=""):
        super().__init__()
        self.row_id = row_id
        self.setObjectName("SciForgeHomeRow")
        self.setProperty("row", row_id)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 6, 0, 0)
        column.setSpacing(4)
        line = QtWidgets.QFrame()
        line.setObjectName("SciForgeHomeLine")
        line.setFixedHeight(1)
        column.addWidget(line)
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 6, 0, 0)
        self.icon = QtWidgets.QLabel()
        self.icon.setPixmap(ui_icon(icon).pixmap(18, 18))
        head.addWidget(self.icon)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("SciForgeHomeTitle")
        head.addWidget(self.title)
        # where the place is on this computer (This computer: where designs are saved)
        self.path_label = QtWidgets.QLabel(os.path.normpath(path) if path else "")
        self.path_label.setObjectName("SciForgeHomePath")
        self.path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.path_label.setVisible(bool(path))
        head.addWidget(self.path_label)
        head.addStretch(1)
        self.clear_button = None
        self.menu_button = None
        if row_id == RECENT:
            self.clear_button = QtWidgets.QPushButton("Clear List")
            self.clear_button.setObjectName("SciForgeHomeClear")
            self.clear_button.setCursor(QtCore.Qt.PointingHandCursor)
            self.clear_button.setToolTip("Remove every design that is not pinned from Recent")
            self.clear_button.clicked.connect(page.clear_list)
            head.addWidget(self.clear_button)
        else:
            self.menu_button = QtWidgets.QPushButton("...")
            self.menu_button.setObjectName("SciForgeHomePlaceMenu")
            self.menu_button.setCursor(QtCore.Qt.PointingHandCursor)
            self.menu_button.setToolTip("Show in Folder, and more")
            self.menu_button.clicked.connect(
                lambda *_: page.place_menu(row_id).exec_(
                    self.menu_button.mapToGlobal(QtCore.QPoint(0, self.menu_button.height()))
                )
            )
            head.addWidget(self.menu_button)
        column.addLayout(head)
        self.list = _Tiles(row_id)
        self.list.customContextMenuRequested.connect(lambda pos: page._menu(self.list, pos))
        self.list.itemDoubleClicked.connect(page.open_item)
        column.addWidget(self.list)
        self.empty = QtWidgets.QLabel("")
        self.empty.setObjectName("SciForgeHomeEmpty")
        self.empty.setWordWrap(True)
        self.empty.hide()
        column.addWidget(self.empty)

    def say(self, text):
        """No tiles: a sentence instead."""
        self.empty.setText(text)
        self.empty.setVisible(bool(text))


class HomeView(QtWidgets.QWidget):
    """The Home tab's page: Recent, then one row per place (This computer, the clouds and
    NAS connected), each showing all its designs (Luca's sketch, 2026-10-19)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeHome")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(QSS.format(**_colours()))
        self.generation = 0  # tiles of an older listing ignore late answers
        self.tiles = {}  # tile id -> QListWidgetItem waiting for its picture
        self.pinned = set()
        self.rows = {}  # row id -> _Row
        self.listing = []  # what refresh() found; the search box filters it
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._main(), 1)
        row.addWidget(self._ai())
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(50)
        self.poll.timeout.connect(self._answers)
        self.banner_timer = QtCore.QTimer(self)
        self.banner_timer.setInterval(3000)
        self.banner_timer.timeout.connect(self.update_banner)
        self.refresh()
        self.update_banner()
        _no_tab_focus(self)

    # -- pieces
    def _ai(self):
        """The AI column: AI control on / off (a switch), the AIs added with their badges
        (as many as there are: the list scrolls), + Add an AI, Open AI panel."""
        from . import ai_panel_ui

        side = _Painted("CHROME")
        side.setObjectName("SciForgeHomeAI")
        side.setFixedWidth(250)
        column = QtWidgets.QVBoxLayout(side)
        column.setContentsMargins(14, 18, 14, 12)
        title = QtWidgets.QLabel("AI")
        title.setObjectName("SciForgeHomeTitle")
        column.addWidget(title)
        self.ai_toggle = QtWidgets.QCheckBox("AI control")
        self.ai_toggle.setObjectName("SciForgeAIToggle")
        self.ai_toggle.setToolTip(
            "Allow AI apps (Claude Desktop, Gemini CLI...) to control SciForge. "
            "The same switch as Preferences > AI."
        )
        self.ai_toggle.setStyleSheet(ai_panel_ui._qss())
        self.ai_toggle.toggled.connect(self._ai_toggled)
        column.addWidget(self.ai_toggle, 0, QtCore.Qt.AlignLeft)
        self.ai_status = QtWidgets.QLabel("")
        self.ai_status.setObjectName("SciForgeHomeAIStatus")
        self.ai_status.setWordWrap(True)
        column.addWidget(self.ai_status)
        self.ai_list = QtWidgets.QListWidget()
        self.ai_list.setObjectName("SciForgeHomeAIs")
        self.ai_list.setIconSize(QtCore.QSize(26, 26))
        self.ai_list.setToolTip("The AIs you added. Double-click one to use it.")
        self.ai_list.itemDoubleClicked.connect(self._ai_used)
        column.addWidget(self.ai_list, 1)
        self.add_ai_button = QtWidgets.QPushButton("+ Add an AI")
        self.add_ai_button.setObjectName("SciForgeHomeAddAI")
        self.add_ai_button.setToolTip("Let Claude Desktop, Gemini CLI or another AI app build here")
        self.add_ai_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, _add_ai))
        column.addWidget(self.add_ai_button)
        self.ai_panel_button = QtWidgets.QPushButton("Open AI panel")
        self.ai_panel_button.setObjectName("SciForgeHomeAIPanel")
        self.ai_panel_button.setIcon(ui_icon("ai_panel"))
        self.ai_panel_button.setProperty("sciforgeIcon", "ai_panel")
        self.ai_panel_button.setToolTip("Chat, your AIs, what they did (also UTILITIES > AI)")
        self.ai_panel_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, _ai_chat))
        column.addWidget(self.ai_panel_button)
        self.update_ai()
        return side

    def update_ai(self):
        """The switch, the words and the AIs as they are now."""
        try:
            from . import ai_panel_ui, ai_ui
            from .ai import bridge

            self.ai_toggle.blockSignals(True)
            self.ai_toggle.setChecked(bridge.allowed())
            self.ai_toggle.blockSignals(False)
            self.ai_status.setText("\n".join(ai_ui.status_words()))
            self.ai_list.clear()
            found = ai_panel_ui.entries()
            for entry in found:
                item = QtWidgets.QListWidgetItem(
                    ai_panel_ui.badge(entry["badge"]), "%s\n%s" % (entry["name"], entry["status"])
                )
                item.setData(QtCore.Qt.UserRole, (entry["kind"], entry["id"]))
                self.ai_list.addItem(item)
            if not found:
                item = QtWidgets.QListWidgetItem("No AI added yet")
                item.setFlags(QtCore.Qt.NoItemFlags)
                self.ai_list.addItem(item)
        except RuntimeError:
            pass
        except Exception as exc:
            warn("home: AI: %s" % exc)

    def ai_names(self):
        """The AIs listed (tests)."""
        return [
            self.ai_list.item(i).text().split("\n")[0]
            for i in range(self.ai_list.count())
            if self.ai_list.item(i).data(QtCore.Qt.UserRole)
        ]

    def _ai_toggled(self, on):
        try:
            from . import ai_ui
            from .ai import bridge

            bridge.set_allowed(on)
            log("AI control %s (Home)" % ("on" if on else "off"))
            ai_ui._refresh_home()
        except Exception as exc:
            warn("home: AI: %s" % exc)

    def _ai_used(self, item):
        """Double-click an AI: the AI panel, with it."""
        try:
            from . import ai_panel_ui

            data = item.data(QtCore.Qt.UserRole) if item is not None else None
            if not data:
                return
            kind, name = data
            if kind == "chat":
                page = ai_panel_ui.show("chat").widget()
                index = page.chat.provider.findData(name)
                if index >= 0:
                    page.chat.provider.setCurrentIndex(index)
            else:
                QtCore.QTimer.singleShot(0, lambda: ai_panel_ui._add_ai(name))
        except Exception as exc:
            warn("home: AI: %s" % exc)

    def _main(self):
        main = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(main)
        column.setContentsMargins(24, 14, 12, 0)
        column.setSpacing(10)
        heading = QtWidgets.QLabel(TITLE)
        heading.setObjectName("SciForgeHomeHeading")
        column.addWidget(heading)
        top = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton("New design")
        self.new_button.setObjectName("SciForgeHomeNew")
        self.new_button.setToolTip("Start a new design (Ctrl+N)")
        self.new_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, new_design))
        top.addWidget(self.new_button)
        self.open_button = QtWidgets.QPushButton("Open...")
        self.open_button.setObjectName("SciForgeHomeOpen")
        self.open_button.setToolTip("Open a design, or a STEP / IGES file (Ctrl+O)")
        self.open_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, open_file))
        top.addWidget(self.open_button)
        self.connect_button = QtWidgets.QPushButton("+ Connect a cloud or NAS")
        self.connect_button.setObjectName("SciForgeHomeConnect")
        self.connect_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.connect_button.setToolTip(
            "Keep designs in your Dropbox, OneDrive, Google Drive or NAS folder"
        )
        self.connect_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, _connect))
        top.addWidget(self.connect_button)
        self.preferences_button = QtWidgets.QPushButton("Preferences")
        self.preferences_button.setObjectName("SciForgeHomePreferences")
        self.preferences_button.setIcon(ui_icon("tl_settings"))
        self.preferences_button.setProperty("sciforgeIcon", "tl_settings")
        self.preferences_button.setToolTip(
            "SciForge's Preferences: the look (dark or light), navigation, units, AI..."
        )
        self.preferences_button.clicked.connect(
            lambda *_: QtCore.QTimer.singleShot(0, _preferences)
        )
        top.addWidget(self.preferences_button)
        top.addStretch(1)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SciForgeHomeSearch")
        self.search.setPlaceholderText("Search designs")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda *_: self.show_rows())
        top.addWidget(self.search)
        top.addSpacing(12)
        column.addLayout(top)

        self.banner = QtWidgets.QFrame()
        self.banner.setObjectName("SciForgeHomeRecovery")
        self.banner.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        line = QtWidgets.QHBoxLayout(self.banner)
        line.setContentsMargins(12, 6, 8, 6)
        self.banner_text = QtWidgets.QLabel("")
        self.banner_text.setWordWrap(True)
        line.addWidget(self.banner_text, 1)
        self.recover_button = QtWidgets.QPushButton("Recover...")
        self.recover_button.setObjectName("SciForgeHomeRecover")
        self.recover_button.clicked.connect(lambda *_: QtCore.QTimer.singleShot(0, _recover))
        line.addWidget(self.recover_button)
        self.banner.hide()
        column.addWidget(self.banner)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setObjectName("SciForgeHomeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        holder = QtWidgets.QWidget()
        holder.setObjectName("SciForgeHomeRows")
        self.rows_layout = QtWidgets.QVBoxLayout(holder)
        self.rows_layout.setContentsMargins(0, 0, 12, 12)
        self.rows_layout.setSpacing(8)
        self.rows_layout.addStretch(1)
        self.scroll.setWidget(holder)
        column.addWidget(self.scroll, 1)
        return main

    # -- what is shown
    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.banner_timer.start()
            self.update_banner()
        except Exception as exc:
            warn("home: %s" % exc)

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self.banner_timer.stop()
        except Exception:
            pass

    def refresh(self):
        """Look again at the recent list and every place's folders, then show the rows
        (the pictures come a moment later)."""
        try:
            self.listing = self._collect()
        except Exception as exc:
            warn("home: %s" % exc)
            self.listing = []
        self.show_rows()

    def _collect(self):
        """[(row id, title, icon, path shown, tiles, sentence when empty)]; a tile is a dict
        (kind, key, path, name, where, conflict, root)."""
        from . import locations_core, locations_ui

        state = load_state()
        known = places()
        self.pinned = {e["key"] for e in state["entries"] if e["pinned"]}
        found = []
        recent = []
        for entry in core.ordered(state):
            recent.append(
                dict(
                    kind="recent",
                    key=entry["key"],
                    path=core.resolve(entry, known),
                    name=entry["name"],
                    where=place_name(entry["location_id"]),
                    search="%s %s" % (entry["name"], entry.get("rel", "")),
                )
            )
        found.append(
            (
                RECENT,
                "Recent",
                "recent",
                "",
                recent,
                "No recent designs yet. Click New design to start one, or Open... to open a "
                "design. The designs you open and save show here.",
            )
        )
        for place in locations_ui.all_places():
            location_id, root = place["id"], place["root"]
            local = place["kind"] == "local"
            if local:
                _make_default_folder(root)
            tiles, empty = [], "No designs here yet."
            if not root or not os.path.isdir(root):
                empty = (
                    "The folder of %s (%s) is not there. Choose another one in the ... menu "
                    "(Change Folder...)." % (place["name"], root)
                    if local
                    else "%s is offline: %s is not reachable now. Is the cloud app running, "
                    "the NAS on? Its designs come back when it is." % (place["name"], root)
                )
            else:
                _finish_unfinished_saves(root)
                tiles = self._place_tiles(root, locations_core, locations_ui)
                if local:
                    tiles += self._elsewhere_tiles(state, known)
            title = place["name"]
            if not local and locations_core.status(place) != locations_core.OK:
                title += "  · Offline"
            found.append((location_id, title, "folder", root, tiles, empty))
        return found

    def _place_tiles(self, root, locations_core, locations_ui):
        tiles = []
        for folder, rel, designs in core.walk(root, versions.list_folder):
            conflicts = locations_ui.conflicts(
                folder, [os.path.basename(d["path"]) for d in designs]
            )
            for design in designs:
                tiles.append(
                    dict(
                        kind="design",
                        key=versions.path_key(design["path"]),
                        path=design["path"],
                        name=design["name"],
                        where="in %s" % rel.replace("/", " / ") if rel else "",
                        conflict=conflicts.get(os.path.basename(design["path"])),
                        root=root,
                        cad=design.get("cad"),
                        modified=design.get("modified", ""),
                        search="%s %s" % (design["name"], rel),
                    )
                )
        return core.newest_first(tiles)  # the last saved first

    def _elsewhere_tiles(self, state, known):
        """Designs saved in another folder of this computer (none is lost: Luca's saves
        that This computer did not show)."""
        tiles = []
        for entry in core.elsewhere(state, known):
            path = core.resolve(entry, known)
            if path.startswith("\\\\") or path.startswith("//") or not os.path.isfile(path):
                continue  # (a network path could hold Home for seconds; a gone file: Recent)
            tiles.append(
                dict(
                    kind="design",
                    key=entry["key"],
                    path=path,
                    name=entry["name"],
                    where="another folder",
                    tip="Saved outside This computer's folder, in:\n%s" % path,
                    root="",
                    search="%s %s" % (entry["name"], path),
                )
            )
        return tiles

    def show_rows(self):
        """The rows from what refresh() found, filtered by the search box."""
        try:
            self.generation += 1
            self.tiles = {}
            text = self.search.text()
            self._clear_rows()
            for row_id, title, icon, path, tiles, empty in self.listing:
                row = _Row(self, row_id, title, icon, path)
                _no_tab_focus(row)
                self.rows[row_id] = row
                self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
                shown = [t for t in tiles if core.matches({"name": t["search"]}, text)]
                for tile in shown:
                    self._add_tile(row, tile)
                if row.clear_button is not None:
                    row.clear_button.setVisible(bool(tiles))
                if not tiles:
                    row.say(empty)
                elif not shown:
                    row.say("Nothing here matches “%s”." % text)
                row.list.setVisible(bool(shown))
                row.list.fit()
            if self.tiles:
                self.poll.start()
        except Exception as exc:
            warn("home: %s" % exc)

    def _clear_rows(self):
        for row in self.rows.values():
            row.hide()
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.rows = {}

    def _add_tile(self, row, tile):
        conflict = tile.get("conflict")
        item = QtWidgets.QListWidgetItem(
            QtGui.QIcon(_tile_pixmap(None, tile["key"] in self.pinned)),
            "%s\n%s" % (tile["name"], tile["where"]),
        )
        item.setData(_KIND, (tile["kind"], tile["key"], tile["path"]))
        item.setData(_STATUS, core.OK)
        item.setData(_WHERE, tile["where"])
        item.setData(_CONFLICT, conflict or "")
        item.setData(_ROOT, tile.get("root") or "")
        item.setToolTip(tile.get("tip") or tile["path"])
        item.setSizeHint(QtCore.QSize(TILE_W, TILE_H))
        if conflict:
            from . import locations_core

            who = locations_core.conflict_who(os.path.basename(tile["path"]), conflict)
            item.setText(
                "%s\nConflict copy%s" % (versions.design_name(conflict), ", " + who if who else "")
            )
            item.setForeground(QtGui.QColor("#ffb74d"))
            item.setToolTip(
                "%s\nYour cloud app made this copy: %s was changed on two computers. "
                "Right-click: Compare, Keep This One." % (tile["path"], conflict)
            )
        row.list.addItem(item)
        if not tile.get("cad"):
            tile_id = "%s|%s" % (row.row_id, tile["key"])
            self.tiles[tile_id] = item
            self._ask(tile_id, tile["key"], tile["path"])

    def _ask(self, tile, key, path, count=True):
        from . import versions_ui

        loader().ask(
            {
                "generation": self.generation,
                "tile": tile,
                "key": key,
                "path": path,
                "cache": thumbs_dir(),
                "sidecar": _sidecar(path),
                "count": count,
                "project": versions_ui.project_folder(),
                "git": versions_ui.use_git(),
            }
        )

    def _answers(self):
        """The worker's answers: pictures and second lines of the tiles."""
        try:
            done = loader().done
            for _n in range(20):
                try:
                    job, status, mtime, png, count, error = done.get_nowait()
                except queue.Empty:
                    break
                if error:
                    warn("home: %s: %s" % (job["path"], error))
                if job["generation"] != self.generation:
                    continue
                item = self.tiles.pop(job["tile"], None)
                if item is None:
                    continue
                kind, key, path = item.data(_KIND)
                dim = status == core.MISSING
                item.setIcon(QtGui.QIcon(_tile_pixmap(png, key in self.pinned, dim)))
                item.setData(_STATUS, status)
                name, _sep, line = item.text().partition("\n")
                where = item.data(_WHERE) or ""
                if kind == "recent":
                    where = place_name(core.place_of(path, places())[0])
                if not line.startswith("Conflict"):
                    line = core.subtitle(where, status, mtime, count)
                    if status == core.MISSING and _place_offline(path):
                        line = "%s, offline" % where
                item.setText("%s\n%s" % (name, line))
                if dim:
                    item.setForeground(QtGui.QColor(theme.TEXT_DISABLED))
                    item.setToolTip(
                        "Not found: %s\nRight-click it to Locate it or Remove it from the list."
                        % path
                    )
                elif status == core.ONLINE:
                    item.setToolTip(
                        "%s\nKept online only by your cloud app: it downloads when you open it."
                        % path
                    )
            if not self.tiles:
                self.poll.stop()
        except RuntimeError:
            pass  # (the tab was closed)
        except Exception as exc:
            warn("home: %s" % exc)

    def update_banner(self):
        """The recovery banner: shown while another session's recovery copies are kept."""
        try:
            entries = _leftovers()
            if entries:
                self.banner_text.setText(
                    "SciForge did not close properly last time: %d design%s ha%s unsaved work "
                    "that can be recovered."
                    % (
                        len(entries),
                        "" if len(entries) == 1 else "s",
                        "s" if len(entries) == 1 else "ve",
                    )
                )
            self.banner.setVisible(bool(entries))
        except RuntimeError:
            pass
        except Exception as exc:
            warn("home: recovery banner: %s" % exc)

    # -- reading it (tests)
    def row(self, row_id):
        return self.rows.get(row_id)

    def items(self, row_id=None):
        """[(kind, key, path, text, status)] as listed, of one row or of all."""
        found = []
        for rid, row in self.rows.items():
            if row_id is not None and rid != row_id:
                continue
            for i in range(row.list.count()):
                item = row.list.item(i)
                kind, key, path = item.data(_KIND)
                found.append((kind, key, path, item.text(), item.data(_STATUS)))
        return found

    def item_for(self, path, row_id=None):
        """(the row's tile list, the tile) of a design, or (None, None)."""
        for rid, row in self.rows.items():
            if row_id is not None and rid != row_id:
                continue
            for i in range(row.list.count()):
                item = row.list.item(i)
                if versions.same_path(item.data(_KIND)[2], path):
                    return row.list, item
        return None, None

    def loading(self):
        """Tiles still waiting for their picture (tests)."""
        return len(self.tiles)

    # -- actions
    def open_item(self, item):
        """Double-click: open the design. The item's data is read now and the work done a
        moment later (opening can rebuild the rows)."""
        try:
            if item is None:
                return
            kind, key, path = item.data(_KIND)
            status = item.data(_STATUS)
        except Exception as exc:
            warn("home: %s" % exc)
            return
        QtCore.QTimer.singleShot(0, lambda: self._open(kind, key, path, status))

    def _open(self, kind, key, path, status):
        try:
            if status == core.MISSING or not os.path.exists(path):
                commands.tell(
                    "%s is not at %s any more. Right-click it to Locate it, or to Remove it "
                    "from the list." % (versions.design_name(path), path)
                )
                return
            open_design(path)
        except Exception as exc:
            warn("home: %s" % exc)

    def clear_list(self):
        try:
            state = load_state()
            core.clear(state)
            save_state(state)
            log("home: recent list cleared (pinned designs kept)")
            self.refresh()
        except Exception as exc:
            warn("home: %s" % exc)

    def _menu(self, tiles, pos):
        try:
            item = tiles.itemAt(pos)
            if item is None:
                return
            self.context_menu(item).exec_(tiles.viewport().mapToGlobal(pos))
        except Exception as exc:
            warn("home: %s" % exc)

    def context_menu(self, item):
        """The tile's right-click menu (a QMenu; tests read its actions)."""
        kind, key, path = item.data(_KIND)
        missing = item.data(_STATUS) == core.MISSING
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeHomeMenu")

        def add(text, fn):
            action = menu.addAction(text)
            action.triggered.connect(lambda *_: QtCore.QTimer.singleShot(0, fn))
            return action

        if missing:
            add("Locate...", lambda: self.locate(key))
        else:
            add("Open", lambda: self._open(kind, key, path, core.OK))
            original = item.data(_CONFLICT)
            if kind == "design" and original:
                twin = os.path.join(os.path.dirname(path), original)
                root = item.data(_ROOT) or None
                add(
                    "Compare with %s" % versions.design_name(original), lambda: _compare(path, twin)
                )
                add("Keep This One", lambda: self.keep_copy(path, twin, root))
        if kind == "recent":
            pinned = key in self.pinned
            add("Unpin" if pinned else "Pin", lambda: self.pin(key, not pinned))
        if not missing:
            add("Show in Folder", lambda: _show_in_folder(path))
            add("Version History", lambda: _history(path))
        if kind == "recent":
            menu.addSeparator()
            add("Remove from List", lambda: self.forget(key))
        return menu

    def place_menu(self, location_id):
        """A place's menu (its row's ... button; tests read its actions)."""
        from . import locations_ui

        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeHomePlaceMenu")
        root = places().get(location_id, "")
        menu.addAction("Show in Folder").triggered.connect(
            lambda *_: QtCore.QTimer.singleShot(0, lambda: _open_folder(root))
        )
        if location_id == core.LOCAL:
            menu.addAction("Change Folder...").triggered.connect(
                lambda *_: QtCore.QTimer.singleShot(0, _change_folder)
            )
        else:
            menu.addSeparator()
            menu.addAction("Disconnect").triggered.connect(
                lambda *_: QtCore.QTimer.singleShot(0, lambda: locations_ui.disconnect(location_id))
            )
        return menu

    def keep_copy(self, copy, original, root=None):
        from . import versions_ui

        kept = versions_ui.keep_conflict_copy(copy, original, root)
        self.refresh()
        return kept

    def pin(self, key, on=True):
        try:
            state = load_state()
            core.set_pinned(state, key, on)
            save_state(state)
            self.refresh()
        except Exception as exc:
            warn("home: %s" % exc)

    def forget(self, key):
        try:
            state = load_state()
            core.forget(state, key)
            save_state(state)
            self.refresh()
        except Exception as exc:
            warn("home: %s" % exc)

    def locate(self, key):
        """Locate...: pick where the design is now; it keeps its pin and its place."""
        try:
            path = LOCATE_PICKER() if LOCATE_PICKER is not None else None
            if path is None:
                from . import versions_ui

                path, _filter = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Locate", versions_ui.project_folder(), "Designs (*.FCStd *.fcstd)"
                )
            if not path:
                return None
            state = load_state()
            moved = core.relocate(state, key, path, places())
            save_state(state)
            self.refresh()
            return moved
        except Exception as exc:
            warn("home: %s" % exc)
            return None


# -- actions shared with the commands --------------------------------------------------
def new_design():
    """Home's New design: a new design with its first body, like File > New Design."""
    try:
        if not commands.finish_open_dialog():
            return None
        doc = App.newDocument("Untitled")
        commands.ensure_body()
        log("home: new design %s" % doc.Name)
        return doc
    except Exception as exc:
        warn("home: new design: %s" % exc)
        commands.tell("A new design could not be started: %s" % exc)
        return None


def open_file():
    """Home's Open...: the same as File > Open (designs, STEP and IGES files), starting in
    the folder designs are saved in."""
    try:
        from . import versions_ui

        folder = versions_ui.project_folder()
        if os.path.isdir(folder):
            App.ParamGet(FREECAD_GENERAL).SetString("FileOpenSavePath", folder)
        Gui.runCommand(commands.preferred("Std_Open"))
    except Exception as exc:
        warn("home: open: %s" % exc)


def open_design(path):
    from . import versions_ui

    return versions_ui.open_design(path)


def _show_in_folder(path):
    from . import versions_ui

    versions_ui._show_in_folder(path)


def _history(path):
    from . import versions_ui

    versions_ui.show_history(path)


def _open_folder(folder):
    try:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
    except Exception as exc:
        warn("home: %s" % exc)


def _compare(path, twin):
    from . import versions_ui

    versions_ui.compare_files(path, twin)


def _add_ai():
    from . import ai_ui

    ai_ui.add_ai()


def _ai_chat():
    from .ai import chat_ui

    chat_ui.show()


def _preferences():
    try:
        Gui.runCommand("SciForge_Preferences")
    except Exception as exc:
        warn("home: preferences: %s" % exc)


def _ai_activity():
    from . import ai_ui

    ai_ui.show_activity()


def _connect():
    from . import locations_ui

    locations_ui.connect_place()


def _finish_unfinished_saves(root, max_depth=6):
    """Saves FreeCAD could not finish (its last step, renaming "<design>.FCStd.<uuid>" to
    the design, refused while Google Drive backed the folder up: Luca's Documents, where
    every save stayed such a file and Home showed none) become their designs. Only a
    complete one at least 10 s old (never a save being written now)."""
    todo = [(root, 0)]
    while todo:
        folder, depth = todo.pop()
        try:
            for design in versions.unfinished_saves(folder):
                done = versions.finish_save(design, settle=10.0)
                if done:
                    log("home: finished a save FreeCAD left unfinished: %s" % design)
                elif done is False:
                    warn(
                        "home: a save FreeCAD left unfinished could not be finished: %s: %s"
                        % (design, versions.FINISH["last_error"])
                    )
            if depth < max_depth:
                subfolders, _designs = versions.list_folder(folder)
                todo.extend((sub["path"], depth + 1) for sub in subfolders)
        except Exception as exc:
            warn("home: unfinished saves in %s: %s" % (folder, exc))


def _make_default_folder(root):
    """This computer's folder is where designs are saved: the default one (Documents /
    SciForge Designs) is made at once so Home shows it; a folder chosen by the person is
    never made (a NAS share that is off must say so)."""
    try:
        from . import versions_ui

        chosen = versions_ui.prefs().GetString("ProjectFolder", "")
        if not chosen and root and not os.path.isdir(root):
            os.makedirs(root, exist_ok=True)
            log("home: made the folder designs are saved in: %s" % root)
    except Exception as exc:
        warn("home: %s: %s" % (root, exc))


def _change_folder():
    """This computer's ... menu > Change Folder...: File > Project and Recovery Settings."""
    try:
        Gui.runCommand("SciForge_FilesSettings")
    except Exception as exc:
        warn("home: %s" % exc)


def _place_offline(path):
    from . import locations_core, locations_ui

    place = locations_core.place_of(path, locations_ui.all_places())
    return place is not None and locations_core.status(place) != locations_core.OK


def places_changed():
    """A place was connected or disconnected: the open Home lists them again."""
    page = view()
    if page is None:
        return
    page.refresh()  # (the places are listed again first)


def _leftovers():
    from . import versions_ui

    recovery = versions_ui.recovery()
    return recovery.leftovers() if recovery is not None else []


def _recover():
    try:
        from . import versions_ui

        versions_ui.recover_documents()
    except Exception as exc:
        warn("home: recover: %s" % exc)


# -- the tab ---------------------------------------------------------------------------
def _area():
    try:
        return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    except Exception:
        return None


def subwindow():
    """The Home tab's window while it is open, else None."""
    sub, area = _state["sub"], _area()
    if sub is None or area is None:
        return None
    try:
        for open_sub in area.subWindowList():
            if open_sub is sub:
                return sub
    except RuntimeError:
        pass
    _state["sub"] = None
    return None


def view():
    """The Home page while its tab is open (tests), else None."""
    sub = subwindow()
    try:
        return sub.widget() if sub is not None else None
    except RuntimeError:
        return None


def is_active():
    sub, area = subwindow(), _area()
    return sub is not None and area is not None and area.activeSubWindow() is sub


def show(activate=True):
    """Open the Home tab (or bring it to the front). activate=False: it is added but the
    design being worked on stays in front (FreeCAD was started with a file)."""
    try:
        area = _area()
        if area is None:
            return None
        sub = subwindow()
        if sub is None:
            before = area.activeSubWindow()
            page = HomeView()
            sub = area.addSubWindow(page)
            sub.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            sub.setWindowTitle(TITLE)
            sub.setWindowIcon(ui_icon("qa_home"))
            _state["sub"] = sub
            sub.showMaximized()
            log("home: shown")
            if not activate and before is not None:
                area.setActiveSubWindow(before)
                return sub
        else:
            page = sub.widget()
            if page is not None:
                page.refresh()
        if activate:
            area.setActiveSubWindow(sub)
            try:
                sub.widget().setFocus()
            except Exception:
                pass
        QtCore.QTimer.singleShot(0, _follow_active)
        return sub
    except Exception as exc:
        warn("home: could not show: %s" % exc)
        return None


def close():
    try:
        sub = subwindow()
        if sub is not None:
            sub.close()
        _state["sub"] = None
    except Exception as exc:
        warn("home: could not close: %s" % exc)


def refresh_soon():
    """Refresh the open Home page once a burst of opens and saves is over."""
    try:
        timer = _state["refresh"]
        if timer is None:
            timer = _state["refresh"] = QtCore.QTimer()
            timer.setSingleShot(True)
            timer.setInterval(300)
            timer.timeout.connect(_refresh_now)
        timer.start()
    except Exception as exc:
        warn("home: %s" % exc)


def _refresh_now():
    try:
        page = view()
        if page is not None:
            page.refresh()
    except Exception as exc:
        warn("home: %s" % exc)


def _design_views():
    """Whether a design's window is open (FreeCAD was started with a file)."""
    area = _area()
    if area is None:
        return False
    return any(sub is not _state["sub"] for sub in area.subWindowList())


def at_start():
    """From shell.startup, when FreeCAD opens in SciForge."""
    try:
        if _state["on"] and show_at_start():
            show(activate=not _design_views())
    except Exception as exc:
        warn("home: at start: %s" % exc)


def _window_closing():
    try:
        app = QtWidgets.QApplication.instance()
        return app is None or app.closingDown() or not Gui.getMainWindow().isVisible()
    except Exception:
        return True


def _after_close():
    """The last design was closed: back to Home (Fusion since April 2026: Home, not an
    empty window)."""
    try:
        if not _state["on"] or not show_at_start() or _window_closing():
            return
        if not App.listDocuments() and subwindow() is None:
            show()
    except Exception as exc:
        warn("home: %s" % exc)


def _saved(path):
    record(path)
    write_sidecar(path)


class _Watch:
    """Remembers the designs opened and saved; notices the last design closing."""

    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            # (an opened document gets its file name after it is created)
            QtCore.QTimer.singleShot(0, lambda: _opened(name))
        except Exception as exc:
            warn("home: %s" % exc)

    def slotFinishSaveDocument(self, doc, filename):
        try:
            path = str(filename or doc.FileName)
            QtCore.QTimer.singleShot(0, lambda: _saved(path))
        except Exception as exc:
            warn("home: %s" % exc)

    def slotDeletedDocument(self, doc):
        try:
            QtCore.QTimer.singleShot(0, _after_close)
        except Exception as exc:
            warn("home: %s" % exc)


def _opened(name):
    try:
        doc = App.listDocuments().get(name)
        if doc is not None and doc.FileName:
            record(doc.FileName)
    except Exception as exc:
        warn("home: %s" % exc)


def theme_changed():
    """The look was switched: Home's tiles drawn again (their background is the look's)."""
    page = view()
    if page is not None:
        page.refresh()
        page.update_ai()
        sub = subwindow()
        if sub is not None:
            sub.setWindowIcon(ui_icon("qa_home"))


def _follow_browser():
    """The browser closes while Home is in front (Luca: "make sure thats closed on the home
    screen as well") and comes back on a design, unless the person had closed it."""
    try:
        from . import browser_ui, shell

        dock = browser_ui._state.get("dock")
        if dock is None or not shell.is_on():
            return
        if is_active():
            if dock.isVisible():
                dock.hide()
                _state["browser_hidden"] = True
        elif _state.get("browser_hidden"):
            _state["browser_hidden"] = False
            dock.show()
    except RuntimeError:
        pass


def _follow_active(*_args):
    """The navigation bar (orbit, pan, zoom...) floats over the 3D view: not over Home. The
    ribbon's commands neither (Luca: "on the home screen, lets hide the toolbar")."""
    try:
        from . import navbar_ui, shell

        ribbon = shell.ribbon()
        if ribbon is not None:
            ribbon.set_home(is_active())
        _follow_browser()
        nav = navbar_ui.bar()
        if nav is None:
            return
        if is_active():
            nav.hide()
        elif shell.is_on() and nav.isHidden():
            nav.show()
            nav.place()
    except RuntimeError:
        pass
    except Exception as exc:
        warn("home: %s" % exc)


def enable():
    """SciForge on: designs opened and saved are remembered."""
    if _state["on"]:
        return
    _state["on"] = True
    if _state["watch"] is None:
        _state["watch"] = _Watch()
    App.addDocumentObserver(_state["watch"])
    area = _area()
    if area is not None and not _state.get("following"):
        area.subWindowActivated.connect(lambda *_a: QtCore.QTimer.singleShot(0, _follow_active))
        _state["following"] = True


def disable():
    """SciForge off (another workbench): the Home tab closes, nothing is recorded."""
    if not _state["on"]:
        return
    _state["on"] = False
    for step in (lambda: App.removeDocumentObserver(_state["watch"]), close):
        try:
            step()
        except Exception as exc:
            warn("home off: %s" % exc)


# -- commands --------------------------------------------------------------------------
class HomeCommand:
    def GetResources(self):
        from . import ui_icon_path

        return {
            "MenuText": "Home",
            "ToolTip": "Home: your recent designs, New design, Open",
            "Pixmap": ui_icon_path("qa_home"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            show()
        except Exception as exc:
            warn("Home: %s" % exc)


COMMANDS = {"SciForge_Home": HomeCommand}
