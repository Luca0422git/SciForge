# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab: where SciForge opens (Luca, 2026-10-19: "Make the home screen default every
time"), like Fusion's Home (docs/sciforge/parity/home.md).

A tab of its own in the document tabs (a window of FreeCAD's MDI area, as FreeCAD's Start
page is), with
  * Places on the left: Recent, and This computer (the project folder; clouds and NAS
    places come with milestone M2);
  * New design, Open..., a search box;
  * a banner when a session left unsaved work behind (versions_ui's recovery copies);
  * the recent designs as tiles: picture, name, place, "edited 2 h ago", versions.
    Pinned ones first. Double-click opens; right-click: Open, Pin, Show in Folder,
    Version History, Remove from List (a missing design: Locate..., Remove from List).

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
    canvas.fill(QtGui.QColor("#2f3540"))
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


_KIND = QtCore.Qt.UserRole  # ("recent" | "design" | "folder", key or "", path)
_STATUS = QtCore.Qt.UserRole + 1  # home_core.OK / MISSING / ONLINE

QSS = """
#SciForgeHome {{ background: {view}; }}
#SciForgeHomeSide {{ background: {chrome}; }}
#SciForgeHomeSide QListWidget {{ background: {chrome}; border: none; font-size: 13px; }}
#SciForgeHomeSide QListWidget::item {{ padding: 6px 10px; }}
#SciForgeHomeSide QListWidget::item:selected {{ background: {active}; }}
#SciForgeHomeHeading {{ color: {text}; font-size: 20px; padding: 12px 10px 8px 10px; }}
#SciForgeHomeTitle {{ color: {text}; font-size: 16px; }}
#SciForgeHomeEmpty {{ color: {text_dim}; font-size: 13px; padding: 24px; }}
#SciForgeHomeList {{ background: {view}; border: none; }}
#SciForgeHomeList::item {{ color: {text}; border-radius: 3px; padding: 4px; }}
#SciForgeHomeList::item:hover {{ background: #343a46; }}
#SciForgeHomeList::item:selected {{ background: {active}; }}
#SciForgeHomeNew {{ background: {accent}; color: #ffffff; border: none; font-weight: bold;
    padding: 6px 18px; }}
#SciForgeHomeNew:hover {{ background: #5bb8f7; }}
#SciForgeHomeRecovery {{ background: #5a4a2a; border-radius: 3px; }}
#SciForgeHomeClear, #SciForgeHomeUp {{ color: {accent}; background: transparent; border: none; }}
"""


class HomeView(QtWidgets.QWidget):
    """The Home tab's page."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeHome")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            QSS.format(
                view=theme.VIEW,
                chrome=theme.CHROME,
                active=theme.ACTIVE,
                text=theme.TEXT,
                text_dim=theme.TEXT_DIM,
                accent=theme.ACCENT,
            )
        )
        self.mode = "recent"  # or a location id: that place's folder is shown
        self.folder = None
        self.generation = 0  # tiles of an older listing ignore late answers
        self.tiles = {}  # tile id -> QListWidgetItem
        self.pinned = set()
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._side())
        row.addWidget(self._main(), 1)
        self.poll = QtCore.QTimer(self)
        self.poll.setInterval(50)
        self.poll.timeout.connect(self._answers)
        self.banner_timer = QtCore.QTimer(self)
        self.banner_timer.setInterval(3000)
        self.banner_timer.timeout.connect(self.update_banner)
        self.refresh()
        self.update_banner()

    # -- pieces
    def _side(self):
        side = QtWidgets.QFrame()
        side.setObjectName("SciForgeHomeSide")
        side.setFixedWidth(210)
        side.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        column = QtWidgets.QVBoxLayout(side)
        column.setContentsMargins(0, 0, 0, 0)
        heading = QtWidgets.QLabel(TITLE)
        heading.setObjectName("SciForgeHomeHeading")
        column.addWidget(heading)
        self.places = QtWidgets.QListWidget()
        self.places.setObjectName("SciForgeHomePlaces")
        self.places.setFocusPolicy(QtCore.Qt.NoFocus)
        recent = QtWidgets.QListWidgetItem(ui_icon("recent"), "Recent")
        recent.setData(_KIND, "recent")
        self.places.addItem(recent)
        header = QtWidgets.QListWidgetItem("PLACES")
        header.setFlags(QtCore.Qt.NoItemFlags)
        header.setForeground(QtGui.QColor(theme.TEXT_DISABLED))
        self.places.addItem(header)
        self.places.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.places.customContextMenuRequested.connect(self._place_menu)
        self.fill_places()
        self.places.setCurrentRow(0)
        self.places.currentItemChanged.connect(self._place_clicked)
        column.addWidget(self.places, 1)
        return side

    def fill_places(self):
        """The place rows (after Recent and the PLACES header): name and status, then
        + Connect a cloud or NAS."""
        from . import locations_core, locations_ui

        while self.places.count() > 2:
            self.places.takeItem(2)
        for place in locations_ui.all_places():
            # (This computer's folder is made when first needed: never "offline")
            offline = place["kind"] != "local" and (
                locations_core.status(place) != locations_core.OK
            )
            item = QtWidgets.QListWidgetItem(
                ui_icon("folder"), place["name"] + ("  \u00b7 Offline" if offline else "")
            )
            item.setData(_KIND, place["id"])
            item.setToolTip(
                place["root"]
                + ("\nNot reachable now: is the cloud app running, the NAS on?" if offline else "")
            )
            if offline:
                item.setForeground(QtGui.QColor(theme.TEXT_DISABLED))
            self.places.addItem(item)
        connect = QtWidgets.QListWidgetItem("+ Connect a cloud or NAS")
        connect.setData(_KIND, "__connect__")
        connect.setForeground(QtGui.QColor(theme.ACCENT))
        connect.setToolTip("Keep designs in your Dropbox, OneDrive, Google Drive or NAS folder")
        self.places.addItem(connect)

    def _refill_places(self):
        """The places again (a folder may have come back or gone), the current one kept."""
        self.places.blockSignals(True)
        try:
            self.fill_places()
            if self.mode != "recent" and self.mode not in places():
                self.mode = "recent"
            self.select_place(self.mode)
        finally:
            self.places.blockSignals(False)

    def select_place(self, location_id):
        for i in range(self.places.count()):
            if self.places.item(i).data(_KIND) == location_id:
                self.places.setCurrentRow(i)
                return True
        return False

    def _place_menu(self, pos):
        try:
            item = self.places.itemAt(pos)
            location_id = item.data(_KIND) if item is not None else None
            if location_id in (None, "recent", "__connect__"):
                return
            self.place_menu(location_id).exec_(self.places.viewport().mapToGlobal(pos))
        except Exception as exc:
            warn("home: %s" % exc)

    def place_menu(self, location_id):
        """A place's right-click menu (tests read its actions)."""
        from . import locations_ui

        menu = QtWidgets.QMenu(self)
        root = places().get(location_id, "")
        menu.addAction("Show in Folder").triggered.connect(
            lambda *_: QtCore.QTimer.singleShot(0, lambda: _open_folder(root))
        )
        if location_id != core.LOCAL:
            menu.addSeparator()
            menu.addAction("Disconnect").triggered.connect(
                lambda *_: QtCore.QTimer.singleShot(0, lambda: locations_ui.disconnect(location_id))
            )
        return menu

    def _main(self):
        main = QtWidgets.QWidget()
        column = QtWidgets.QVBoxLayout(main)
        column.setContentsMargins(24, 18, 24, 12)
        column.setSpacing(10)
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
        top.addStretch(1)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SciForgeHomeSearch")
        self.search.setPlaceholderText("Search designs")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda *_: self.refresh())
        top.addWidget(self.search)
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

        header = QtWidgets.QHBoxLayout()
        self.up = QtWidgets.QPushButton("< Up")
        self.up.setObjectName("SciForgeHomeUp")
        self.up.setCursor(QtCore.Qt.PointingHandCursor)
        self.up.clicked.connect(self.go_up)
        header.addWidget(self.up)
        self.title = QtWidgets.QLabel("Recent")
        self.title.setObjectName("SciForgeHomeTitle")
        header.addWidget(self.title)
        header.addStretch(1)
        self.clear_button = QtWidgets.QPushButton("Clear List")
        self.clear_button.setObjectName("SciForgeHomeClear")
        self.clear_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.clear_button.setToolTip("Remove every design that is not pinned from Recent")
        self.clear_button.clicked.connect(self.clear_list)
        header.addWidget(self.clear_button)
        column.addLayout(header)

        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeHomeList")
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.list.setIconSize(QtCore.QSize(THUMB, THUMB))
        self.list.setGridSize(QtCore.QSize(TILE_W, TILE_H))
        self.list.setResizeMode(QtWidgets.QListView.Adjust)
        self.list.setMovement(QtWidgets.QListView.Static)
        self.list.setWordWrap(True)
        self.list.setSpacing(8)
        self.list.setUniformItemSizes(True)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemDoubleClicked.connect(self.open_item)
        column.addWidget(self.list, 1)
        self.empty = QtWidgets.QLabel("")
        self.empty.setObjectName("SciForgeHomeEmpty")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignHCenter)
        column.addWidget(self.empty)
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

    def _place_clicked(self, item, _previous=None):
        try:
            if item is None or not item.data(_KIND):
                return
            if item.data(_KIND) == "__connect__":
                back = self.mode
                QtCore.QTimer.singleShot(0, lambda: self.select_place(back))
                QtCore.QTimer.singleShot(0, _connect)
                return
            self.mode = item.data(_KIND)
            self.folder = None
            self.refresh()
        except Exception as exc:
            warn("home: %s" % exc)

    def refresh(self):
        """List the tiles again (their pictures come a moment later)."""
        try:
            self._refill_places()
            self.generation += 1
            self.list.clear()
            self.tiles = {}
            if self.mode == "recent":
                self._list_recent()
            else:
                self._list_place()
            if self.tiles:
                self.poll.start()
        except Exception as exc:
            warn("home: %s" % exc)
            self.empty.setText("Home could not list the designs: %s" % exc)
            self.empty.show()

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

    def _list_recent(self):
        state = load_state()
        known = places()
        text = self.search.text()
        entries = core.ordered(state)
        shown = [e for e in entries if core.matches(e, text)]
        self.pinned = {e["key"] for e in entries if e["pinned"]}
        self.title.setText("Recent")
        self.up.hide()
        self.clear_button.setVisible(bool(entries))
        for entry in shown:
            path = core.resolve(entry, known)
            item = QtWidgets.QListWidgetItem(
                QtGui.QIcon(_tile_pixmap(None, entry["pinned"])),
                "%s\n%s" % (entry["name"], place_name(entry["location_id"])),
            )
            item.setData(_KIND, ("recent", entry["key"], path))
            item.setData(_STATUS, core.OK)
            item.setToolTip(path)
            item.setSizeHint(QtCore.QSize(TILE_W, TILE_H))
            self.list.addItem(item)
            self.tiles[entry["key"]] = item
            self._ask(entry["key"], entry["key"], path)
        if not entries:
            self.empty.setText(
                "No recent designs yet. Click New design to start one, or Open... to open a "
                "design. The designs you open and save show here."
            )
        elif not shown:
            self.empty.setText("No recent design matches “%s”." % text)
        self.empty.setVisible(not shown)
        self.list.setVisible(bool(shown))

    def _list_place(self):
        root = places().get(self.mode)
        name = place_name(self.mode)
        self.clear_button.hide()
        if not root or not os.path.isdir(root):
            self.title.setText(name)
            self.up.hide()
            self.empty.setText(
                (
                    "The folder of %s (%s) is not there. Choose another one in File > Project "
                    "and Recovery Settings." % (name, root)
                )
                if self.mode == core.LOCAL
                else "%s is offline: %s is not reachable now. Is the cloud app running, the NAS "
                "on? Its designs come back when it is." % (name, root)
            )
            self.empty.show()
            self.list.hide()
            return
        if not self.folder or not versions.inside(root, self.folder):
            self.folder = root
        crumbs = [label for label, _path in versions.breadcrumbs(root, self.folder)][1:]
        self.title.setText(" / ".join([name] + crumbs))
        self.up.setVisible(not versions.same_path(root, self.folder))
        folders, designs = versions.list_folder(self.folder)
        from . import locations_ui

        self.conflicts = locations_ui.conflicts(
            self.folder, [os.path.basename(d["path"]) for d in designs]
        )
        text = self.search.text()
        for folder in folders:
            if not core.matches({"name": folder["name"]}, text):
                continue
            item = QtWidgets.QListWidgetItem(
                QtGui.QIcon(ui_icon("folder").pixmap(THUMB, THUMB)), folder["name"]
            )
            item.setData(_KIND, ("folder", "", folder["path"]))
            item.setSizeHint(QtCore.QSize(TILE_W, TILE_H))
            self.list.addItem(item)
        for design in designs:
            if not core.matches({"name": design["name"]}, text):
                continue
            key = versions.path_key(design["path"])
            item = QtWidgets.QListWidgetItem(
                QtGui.QIcon(_tile_pixmap(None, key in self.pinned)), design["name"]
            )
            item.setData(_KIND, ("design", key, design["path"]))
            item.setData(_STATUS, core.OK)
            item.setToolTip(design["path"])
            original = self.conflicts.get(os.path.basename(design["path"]))
            if original:
                from . import locations_core

                who = locations_core.conflict_who(os.path.basename(design["path"]), original)
                item.setText(
                    "%s\nConflict copy%s"
                    % (versions.design_name(original), ", " + who if who else "")
                )
                item.setForeground(QtGui.QColor("#ffb74d"))
                item.setToolTip(
                    "%s\nYour cloud app made this copy: %s was changed on two computers. "
                    "Right-click: Compare, Keep This One." % (design["path"], original)
                )
            item.setSizeHint(QtCore.QSize(TILE_W, TILE_H))
            self.list.addItem(item)
            if not design.get("cad"):
                self.tiles[key] = item
                self._ask(key, key, design["path"])
        shown = self.list.count()
        self.empty.setText(
            "No designs here yet." if not text else "Nothing here matches “%s”." % text
        )
        self.empty.setVisible(not shown)
        self.list.setVisible(bool(shown))

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
                where = place_name(core.place_of(path, places())[0]) if kind == "recent" else ""
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

    # -- actions
    def items(self):
        """[(kind, key, path, text, status)] as listed (tests)."""
        found = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            kind, key, path = item.data(_KIND)
            found.append((kind, key, path, item.text(), item.data(_STATUS)))
        return found

    def item_for(self, path):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if versions.same_path(item.data(_KIND)[2], path):
                return item
        return None

    def loading(self):
        """Tiles still waiting for their picture (tests)."""
        return len(self.tiles)

    def open_item(self, item):
        """Double-click: open the design (or go into the folder). The item's data is read
        now and the work done a moment later (opening can rebuild the list)."""
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
            if kind == "folder":
                self.folder = path
                self.refresh()
                return
            if status == core.MISSING or not os.path.exists(path):
                commands.tell(
                    "%s is not at %s any more. Right-click it to Locate it, or to Remove it "
                    "from the list." % (versions.design_name(path), path)
                )
                return
            open_design(path)
        except Exception as exc:
            warn("home: %s" % exc)

    def go_up(self):
        try:
            root = places().get(self.mode)
            if root and self.folder and not versions.same_path(root, self.folder):
                self.folder = os.path.dirname(self.folder)
                self.refresh()
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

    def _menu(self, pos):
        try:
            item = self.list.itemAt(pos)
            if item is None:
                return
            kind, key, path = item.data(_KIND)
            if kind == "folder":
                return
            menu = self.context_menu(item)
            menu.exec_(self.list.viewport().mapToGlobal(pos))
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
            original = getattr(self, "conflicts", {}).get(os.path.basename(path))
            if kind == "design" and original:
                twin = os.path.join(os.path.dirname(path), original)
                add(
                    "Compare with %s" % versions.design_name(original), lambda: _compare(path, twin)
                )
                add("Keep This One", lambda: self.keep_copy(path, twin))
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

    def keep_copy(self, copy, original):
        from . import versions_ui

        kept = versions_ui.keep_conflict_copy(copy, original, places().get(self.mode))
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
    """Home's Open...: the same as File > Open (designs, STEP and IGES files)."""
    try:
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


def _connect():
    from . import locations_ui

    locations_ui.connect_place()


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


def _follow_active(*_args):
    """The navigation bar (orbit, pan, zoom...) floats over the 3D view: not over Home."""
    try:
        from . import navbar_ui, shell

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
