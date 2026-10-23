# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel: Fusion's, on local folders (outline 7.15; spec and sources in
docs/sciforge/parity/versions.md, "Data Panel" and "Data Panel, part 2").

    places     This computer (the project folder), each cloud and NAS connected
    the bar    Up, the folder path, Refresh; Upload, New Folder; Search, sort, list / grid
    cards      folders first, then designs: the design's picture with its version badge
               (V3) in the corner, the name and when it was saved; the list view puts
               them in rows with the size
    details    a design clicked: a big picture, Open, Insert (a copy or linked), and the
               tabs Versions (newest first; double-click opens one), Uses (the designs it
               inserts) and Used In (the designs of this place that insert it)
    dragging   a design dragged into an open design's 3D view (or onto a component in the
               browser) comes in as an independent copy (versions_ui.insert_copy); a card
               dropped on a folder card moves there; a design or STEP file dropped on the
               panel from the computer's file manager is copied into the folder shown
    keys       Enter opens, F2 renames, Delete moves to the trash folder, Backspace goes up

The logic without Qt is data_panel_core.py; saving, versions, Move / Copy and Insert are
versions_ui.py's.
"""

import os
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, theme, ui_icon, warn
from . import data_panel_core as dp
from . import versions as core
from . import versions_ui as vui
from .compat import QtCore, QtGui, QtWidgets

THUMB = 96  # a card's picture (px)
SMALL = 32  # a row's picture in the list view
BIG = 104  # the details' picture
ROLE = QtCore.Qt.UserRole  # (kind, path), as before (tests read it)
ROLE_NAME = QtCore.Qt.UserRole + 1
ROLE_BADGE = QtCore.Qt.UserRole + 2
ROLE_SUB = QtCore.Qt.UserRole + 3  # the list view's second line
ROLE_SHORT = QtCore.Qt.UserRole + 4  # the grid's second line
POLL_MS = 4000  # how often the folder shown is looked at for changes made elsewhere
SLOW_SCAN = 0.5  # seconds: a folder slower to list than this is not looked at again

# Tests put a function(paths) here to see what a drag out of the panel would carry instead
# of running QDrag's own event loop (which needs a real mouse).
DRAG_HOOK = None


def _prefs():
    return App.ParamGet(vui.PREFS)


def _color(name, fallback):
    value = getattr(theme, name, "") or fallback
    return QtGui.QColor(value)


# -- the cards ---------------------------------------------------------------------------------
class _CardDelegate(QtWidgets.QStyledItemDelegate):
    """Draws a card: the picture with the version badge in its top-right corner, the name
    and a dim second line (grid); or a row with a small picture (list)."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def _as_list(self):
        return self.view.viewMode() == QtWidgets.QListView.ListMode

    def sizeHint(self, option, index):
        if self._as_list():
            return QtCore.QSize(max(200, self.view.viewport().width() - 8), SMALL + 12)
        return QtCore.QSize(THUMB + 28, THUMB + 52)

    def paint(self, painter, option, index):
        try:
            self._paint(painter, option, index)
        except Exception as exc:  # never an exception out of a paint
            warn("data panel card: %s" % exc)

    def _paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # (read from the item: opt.icon is the option's own, emptied just below)
        icon = index.data(QtCore.Qt.DecorationRole)
        if isinstance(icon, QtGui.QPixmap):
            icon = QtGui.QIcon(icon)
        elif not isinstance(icon, QtGui.QIcon):
            icon = QtGui.QIcon()
        opt.text = ""
        opt.icon = QtGui.QIcon()
        widget = option.widget
        style = widget.style() if widget is not None else QtWidgets.QApplication.style()
        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, opt, painter, widget)
        rect = option.rect
        name = index.data(ROLE_NAME) or index.data(QtCore.Qt.DisplayRole) or ""
        badge = index.data(ROLE_BADGE) or ""
        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            text = _color("TEXT", "#f5f5f5")
            dim = _color("TEXT_DIM", "#c3cad4")
            if self.view.drop_row is not None and index.row() == self.view.drop_row:
                pen = QtGui.QPen(_color("ACCENT", "#3fa9f5"))
                pen.setWidthF(2.0)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                painter.drawRoundedRect(QtCore.QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5), 4, 4)
            if self._as_list():
                pic = QtCore.QRect(rect.left() + 6, rect.top() + 6, SMALL, SMALL)
                icon.paint(painter, pic, QtCore.Qt.AlignCenter)
                left = pic.right() + 10
                right = rect.right() - 8
                if badge:
                    right = self._badge(painter, badge, right, rect.top() + 6, from_right=True) - 6
                font = QtGui.QFont(opt.font)
                painter.setFont(font)
                painter.setPen(text)
                metrics = QtGui.QFontMetrics(font)
                line = QtCore.QRect(left, rect.top() + 5, right - left, metrics.height())
                painter.drawText(
                    line,
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    metrics.elidedText(name, QtCore.Qt.ElideRight, line.width()),
                )
                sub = index.data(ROLE_SUB) or ""
                if sub:
                    small = QtGui.QFont(font)
                    small.setPointSizeF(max(6.5, font.pointSizeF() * 0.88))
                    painter.setFont(small)
                    painter.setPen(dim)
                    m2 = QtGui.QFontMetrics(small)
                    line2 = QtCore.QRect(left, line.bottom() + 2, right - left, m2.height())
                    painter.drawText(
                        line2,
                        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                        m2.elidedText(sub, QtCore.Qt.ElideRight, line2.width()),
                    )
                return
            pic = QtCore.QRect(
                rect.left() + (rect.width() - THUMB) // 2, rect.top() + 6, THUMB, THUMB
            )
            icon.paint(painter, pic, QtCore.Qt.AlignCenter)
            if badge:
                self._badge(painter, badge, pic.right() - 2, pic.top() + 2, from_right=True)
            font = QtGui.QFont(opt.font)
            painter.setFont(font)
            painter.setPen(text)
            metrics = QtGui.QFontMetrics(font)
            line = QtCore.QRect(
                rect.left() + 4, pic.bottom() + 4, rect.width() - 8, metrics.height()
            )
            painter.drawText(
                line,
                QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
                metrics.elidedText(name, QtCore.Qt.ElideMiddle, line.width()),
            )
            short = index.data(ROLE_SHORT) or ""
            if short:
                small = QtGui.QFont(font)
                small.setPointSizeF(max(6.5, font.pointSizeF() * 0.85))
                painter.setFont(small)
                painter.setPen(dim)
                m2 = QtGui.QFontMetrics(small)
                line2 = QtCore.QRect(line.left(), line.bottom() + 1, line.width(), m2.height())
                painter.drawText(
                    line2,
                    QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
                    m2.elidedText(short, QtCore.Qt.ElideRight, line2.width()),
                )
        finally:
            painter.restore()

    @staticmethod
    def _badge(painter, text, x, y, from_right=False):
        """The version badge (V3): white on the accent colour. Returns its left edge."""
        font = QtGui.QFont(painter.font())
        font.setBold(True)
        font.setPointSizeF(max(6.5, font.pointSizeF() * 0.8))
        metrics = QtGui.QFontMetrics(font)
        width = metrics.horizontalAdvance(text) + 8
        height = metrics.height() + 2
        left = x - width if from_right else x
        box = QtCore.QRectF(left, y, width, height)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(_color("ACCENT", "#3fa9f5"))
        painter.drawRoundedRect(box, 3, 3)
        painter.setFont(font)
        painter.setPen(QtGui.QColor("#ffffff"))
        painter.drawText(box, QtCore.Qt.AlignCenter, text)
        return int(left)


class DataPanelList(QtWidgets.QListWidget):
    """The cards. Dragging a design starts a drag that an open design's 3D view takes (a
    copy goes in); a folder card takes designs dropped on it (they move there); files
    dropped from the computer's file manager are copied into the folder shown.

    The drag is started here (a press on a design card, then a move of a few pixels), not
    by Qt's own item dragging: the cards never move around, and a press on the empty space
    still draws the selection band."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.drop_row = None
        self._press = None  # where a press on a design card was (a drag may start there)
        self.setObjectName("SciForgeDataPanelList")
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.CopyAction)
        self.setMouseTracking(True)
        self.setItemDelegate(_CardDelegate(self))

    def mousePressEvent(self, event):
        self._press = None
        try:
            if event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint()
                item = self.itemAt(pos)
                if item is not None and item.data(ROLE)[0] == "design":
                    self._press = pos
        except Exception as exc:
            warn("data panel: %s" % exc)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        try:
            if self._press is not None and event.buttons() & QtCore.Qt.LeftButton:
                pos = event.position().toPoint()
                if (
                    pos - self._press
                ).manhattanLength() >= QtWidgets.QApplication.startDragDistance():
                    self._press = None
                    self.startDrag(QtCore.Qt.CopyAction)
                return  # a press on a card drags it, it does not stretch a selection band
        except Exception as exc:
            warn("data panel drag: %s" % exc)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press = None
        super().mouseReleaseEvent(event)

    # -- dragging out
    def mimeTypes(self):
        return [dp.MIME, "text/uri-list"]

    def mimeData(self, items):
        paths = [p for kind, p in (i.data(ROLE) for i in items) if kind == "design"]
        return make_mime(paths)

    def startDrag(self, supported):
        try:
            paths = self.panel.selected_designs()
            if not paths:
                return
            if DRAG_HOOK is not None:
                DRAG_HOOK(paths)
                return
            drag = QtGui.QDrag(self)
            drag.setMimeData(make_mime(paths))
            item = self.panel.item_for(paths[0])
            if item is not None:
                pixmap = item.icon().pixmap(64, 64)
                if not pixmap.isNull():
                    drag.setPixmap(pixmap)
                    drag.setHotSpot(QtCore.QPoint(pixmap.width() // 2, pixmap.height() // 2))
            session = DropSession()
            self.panel.dragging = True
            try:
                # Copy only: a file manager given a "move" would take the design out of the
                # project; what a drop here does is decided by SciForge (a move onto a folder).
                drag.exec(QtCore.Qt.CopyAction, QtCore.Qt.CopyAction)
            finally:
                self.panel.dragging = False
                session.finish()
        except Exception as exc:
            warn("data panel drag: %s" % exc)

    # -- dropping in
    def _drop_info(self, event):
        """(paths, folder) a drag over the cards would drop: designs of the panel onto a
        folder card (a move), or files from outside into a folder (Upload)."""
        mime = event.mimeData()
        pos = event.position().toPoint()
        item = self.itemAt(pos)
        kind, folder = item.data(ROLE) if item is not None else (None, None)
        if mime.hasFormat(dp.MIME):
            paths = dp.decode_paths(bytes(mime.data(dp.MIME)).decode("utf-8", "replace"))
            if kind == "folder" and dp.move_target(paths, folder):
                return "move", paths, folder, item
            return None, [], None, None
        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            paths = [p for p in paths if dp.upload_kind(p)]
            if paths:
                return "upload", paths, folder if kind == "folder" else self.panel.folder, item
        return None, [], None, None

    def _mark(self, item):
        row = self.row(item) if item is not None else None
        if row != self.drop_row:
            self.drop_row = row
            self.viewport().update()

    def dragEnterEvent(self, event):
        self.dragMoveEvent(event)

    def dragMoveEvent(self, event):
        try:
            action, _paths, _folder, item = self._drop_info(event)
        except Exception:
            action, item = None, None
        if action is None:
            self._mark(None)
            event.ignore()
            return
        self._mark(item if action == "move" or item is not None else None)
        event.setDropAction(QtCore.Qt.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._mark(None)
        event.accept()

    def dropEvent(self, event):
        self._mark(None)
        try:
            action, paths, folder, _item = self._drop_info(event)
        except Exception as exc:
            warn("data panel drop: %s" % exc)
            action = None
        if action is None:
            event.ignore()
            return
        event.setDropAction(QtCore.Qt.CopyAction)
        event.accept()
        panel = self.panel
        if action == "move":
            QtCore.QTimer.singleShot(0, lambda: panel.move_paths(paths, folder))
        else:
            QtCore.QTimer.singleShot(0, lambda: panel.upload_files(paths, folder))

    # -- keys
    KEYS = (
        QtCore.Qt.Key_Return,
        QtCore.Qt.Key_Enter,
        QtCore.Qt.Key_F2,
        QtCore.Qt.Key_Delete,
        QtCore.Qt.Key_Backspace,
    )

    def event(self, event):
        if event.type() == QtCore.QEvent.ShortcutOverride and event.key() in self.KEYS:
            event.accept()  # the panel's keys, not a SciForge shortcut, while it has focus
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        try:
            if self.panel.key(event.key()):
                return
        except Exception as exc:
            warn("data panel: %s" % exc)
            return
        super().keyPressEvent(event)


def make_mime(paths):
    mime = QtCore.QMimeData()
    mime.setData(dp.MIME, QtCore.QByteArray(dp.encode_paths(paths).encode("utf-8")))
    mime.setUrls([QtCore.QUrl.fromLocalFile(p) for p in paths])
    return mime


# -- a design dropped on an open design ---------------------------------------------------------
def _ancestors(widget):
    found = []
    while widget is not None:
        found.append(widget)
        try:
            widget = widget.parentWidget()
        except RuntimeError:
            break
    return found


def _same(a, b):
    if a is b:
        return True
    try:
        import shiboken6

        return shiboken6.getCppPointer(a)[0] == shiboken6.getCppPointer(b)[0]
    except Exception:
        return False


def _view_frame(inner):
    """The widgets from a 3D view's drawing area up to its tab (the MDI sub-window): any of
    them can be the one a drag reaches (the first that takes drops)."""
    found = []
    widget = inner
    while widget is not None:
        found.append(widget)
        if isinstance(widget, QtWidgets.QMdiSubWindow):
            break
        widget = widget.parentWidget()
    return found


def _view_widgets():
    """The drawing areas of every open 3D view (the view and its viewport)."""
    found = []
    for name in App.listDocuments():
        try:
            gdoc = Gui.getDocument(name)
            views = gdoc.mdiViewsOfType("Gui::View3DInventor") if gdoc is not None else []
        except Exception:
            continue
        for view in views:
            try:
                inner = view.graphicsView()
                if inner is not None:
                    found += [inner, inner.viewport()]
            except Exception:
                continue
    return found


def view_document(widget):
    """The design whose 3D view `widget` is (or is in, or holds), or None."""
    chain = _ancestors(widget)
    for name in App.listDocuments():
        try:
            gdoc = Gui.getDocument(name)
            views = gdoc.mdiViewsOfType("Gui::View3DInventor") if gdoc is not None else []
        except Exception:
            continue
        for view in views:
            try:
                inner = view.graphicsView()
            except Exception:
                continue
            if inner is None:
                continue
            if any(_same(inner, w) for w in chain) or any(
                _same(widget, w) for w in _view_frame(inner)
            ):
                return App.getDocument(name)
    return None


def _browser_of(widget):
    for w in _ancestors(widget):
        try:
            if w.objectName() == "SciForgeBrowser":
                return w
        except RuntimeError:
            return None
    return None


def _in_panel_list(widget):
    return any(isinstance(w, DataPanelList) for w in _ancestors(widget))


def drop_target(widget, pos=None):
    """Where a design dragged from the panel would go when dropped on `widget` at `pos`
    (widget coordinates): ("view", document, None) for a 3D view; ("browser", document,
    component or None) for the browser (a component row takes it); None elsewhere."""
    if widget is None or _in_panel_list(widget):
        return None
    doc = view_document(widget)
    if doc is not None:
        return ("view", doc, None)
    browser = _browser_of(widget)
    if browser is not None and App.ActiveDocument is not None:
        component = None
        try:
            if pos is not None:
                from .browser_ui import ROLE_NODE

                at = browser.viewport().mapFromGlobal(widget.mapToGlobal(pos))
                item = browser.itemAt(at)
                node = item.data(1, ROLE_NODE) if item is not None else None
                if node is not None and node.get("kind") == "component" and node.get("object"):
                    component = App.ActiveDocument.getObject(node["object"])
        except Exception:
            component = None
        return ("browser", App.ActiveDocument, component)
    return None


class _DropFilter(QtCore.QObject):
    """Watches the whole application while a design is dragged out of the panel: a 3D view
    or the browser takes it (a copy goes in); everywhere else it is refused, so FreeCAD's
    own handling of dropped files (merging them into the design) never sees it."""

    def __init__(self, session):
        super().__init__()
        self.session = session

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind not in (QtCore.QEvent.DragEnter, QtCore.QEvent.DragMove, QtCore.QEvent.Drop):
                return False
            if not isinstance(obj, QtWidgets.QWidget):
                return False
            mime = event.mimeData()
            if mime is None or not mime.hasFormat(dp.MIME):
                return False
            if _in_panel_list(obj):
                return False  # the panel's own cards (a folder takes a move)
            pos = event.position().toPoint()
            target = drop_target(obj, pos)
            paths = dp.decode_paths(bytes(mime.data(dp.MIME)).decode("utf-8", "replace"))
            paths = [p for p in paths if dp.insertable(p)]
            if target is None or not paths:
                event.ignore()
                return True
            event.setDropAction(QtCore.Qt.CopyAction)
            event.accept()
            if kind == QtCore.QEvent.Drop:
                self.session.dropped(target, paths)
            return True
        except Exception as exc:
            warn("data panel drop: %s" % exc)
            return False


class DropSession:
    """The application-wide watch of one drag out of the panel (_DropFilter). What a drop
    asks for is done when the drag has ended (finish), never inside the drag's own event
    loop. Qt hands a drag only to a widget that takes drops: every 3D view's drawing area
    takes them while the drag lasts (as it was afterwards)."""

    def __init__(self):
        self.pending = None
        self.opened = []  # 3D view widgets made to take drops for this drag
        for widget in _view_widgets():
            try:
                if not widget.acceptDrops():
                    widget.setAcceptDrops(True)
                    self.opened.append(widget)
            except RuntimeError:
                continue
        self.filter = _DropFilter(self)
        QtWidgets.QApplication.instance().installEventFilter(self.filter)

    def dropped(self, target, paths):
        kind, doc, component = target
        self.pending = (kind, doc.Name, component.Name if component is not None else None, paths)

    def finish(self):
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.filter)
        except Exception:
            pass
        for widget in self.opened:
            try:
                widget.setAcceptDrops(False)
            except RuntimeError:
                continue
        self.opened = []
        pending, self.pending = self.pending, None
        if pending is not None:
            QtCore.QTimer.singleShot(0, lambda: drop_designs(*pending))
        return pending


def drop_designs(kind, doc_name, component_name, paths):
    """Designs dropped on a design: each comes in as a copy (versions_ui.insert_copy); the
    last one's Move dialog places it."""
    try:
        if doc_name not in App.listDocuments():
            return []
        doc = App.getDocument(doc_name)
        App.setActiveDocument(doc_name)
        parent = vui.ACTIVE
        if component_name:
            parent = doc.getObject(component_name) or vui.ACTIVE
        made = []
        for i, path in enumerate(paths):
            comp = vui.insert_copy(path, doc, parent, place=(i == len(paths) - 1))
            if comp is not None:
                made.append(comp)
        log(
            "dropped %d design(s) on %s (%s): %d copied in"
            % (len(paths), doc.Label, "3D view" if kind == "view" else "browser", len(made))
        )
        return made
    except Exception as exc:
        warn("data panel drop: %s" % exc)
        commands.tell("The design could not be inserted: %s" % exc)
        return []


# -- the details of a design --------------------------------------------------------------------
class DetailsPane(QtWidgets.QFrame):
    """A design's details under the cards (Fusion's design details): picture, name, what it
    is, Open, Insert, and the tabs Versions, Uses and Used In."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.path = None
        self.kind = None
        self._used_in_for = None
        self.setObjectName("SciForgeDataPanelDetails")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)
        top = QtWidgets.QHBoxLayout()
        self.picture = QtWidgets.QLabel()
        self.picture.setObjectName("SciForgeDataPanelDetailsPicture")
        self.picture.setFixedSize(BIG, BIG)
        self.picture.setAlignment(QtCore.Qt.AlignCenter)
        self.picture.setStyleSheet("background: transparent;")
        top.addWidget(self.picture)
        right = QtWidgets.QVBoxLayout()
        head = QtWidgets.QHBoxLayout()
        self.name = QtWidgets.QLabel("")
        self.name.setObjectName("SciForgeDataPanelDetailsName")
        self.name.setWordWrap(True)
        font = self.name.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.15)
        self.name.setFont(font)
        head.addWidget(self.name, 1)
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setObjectName("SciForgeDataPanelDetailsClose")
        self.close_button.setIcon(ui_icon("panel_close"))
        self.close_button.setToolTip("Close the details")
        self.close_button.setAutoRaise(True)
        self.close_button.clicked.connect(self._close)
        head.addWidget(self.close_button, 0, QtCore.Qt.AlignTop)
        right.addLayout(head)
        self.info = QtWidgets.QLabel("")
        self.info.setObjectName("SciForgeDataPanelDetailsInfo")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: %s;" % (theme.TEXT_DIM or "#c3cad4"))
        right.addWidget(self.info)
        buttons = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open")
        self.open_button.setObjectName("SciForgeDataPanelDetailsOpen")
        self.open_button.clicked.connect(lambda *_: self._open())
        buttons.addWidget(self.open_button)
        self.insert_button = QtWidgets.QPushButton("Insert")
        self.insert_button.setObjectName("SciForgeDataPanelDetailsInsert")
        self.insert_button.setToolTip(
            "Insert into the open design (or drag the card into its 3D view: a copy goes in)"
        )
        self.insert_menu = QtWidgets.QMenu(self.insert_button)
        self.insert_menu.setObjectName("SciForgeDataPanelInsertMenu")
        self.insert_button.setMenu(self.insert_menu)
        buttons.addWidget(self.insert_button)
        buttons.addStretch(1)
        right.addLayout(buttons)
        right.addStretch(1)
        top.addLayout(right, 1)
        outer.addLayout(top)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SciForgeDataPanelDetailsTabs")
        self.versions = self._list("SciForgeDataPanelVersions", self._open_version)
        self.versions.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.versions.customContextMenuRequested.connect(self._version_menu)
        self.uses = self._list("SciForgeDataPanelUses", self._open_other)
        self.used_in = self._list("SciForgeDataPanelUsedIn", self._open_other)
        self.tabs.addTab(self.versions, "Versions")
        self.tabs.addTab(self.uses, "Uses")
        self.tabs.addTab(self.used_in, "Used In")
        self.tabs.currentChanged.connect(lambda *_: self._tab_shown())
        for widget in (self.versions, self.uses, self.used_in):
            widget.setMinimumHeight(54)
        self.tabs.setMaximumHeight(170)
        outer.addWidget(self.tabs, 1)
        self.hide()

    @staticmethod
    def _list(name, on_double):
        widget = QtWidgets.QListWidget()
        widget.setObjectName(name)
        widget.itemDoubleClicked.connect(on_double)
        return widget

    # -- what is shown
    def show_for(self, kind, path):
        """The details of `path` (a design or a STEP file); hidden for a folder or nothing."""
        if kind not in ("design",) or not path or not os.path.isfile(path):
            self.path = self.kind = None
            self.hide()
            return
        self.path, self.kind = path, kind
        self._used_in_for = None
        cad = core.is_cad_file(path)
        name = os.path.basename(path) if cad else core.design_name(path)
        self.name.setText(name)
        self.picture.setPixmap(self.panel.picture(path, BIG))
        try:
            stat = os.stat(path)
            design = {
                "path": path,
                "size": stat.st_size,
                "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
                "cad": cad,
            }
        except OSError:
            design = {"path": path, "size": 0, "modified": "", "cad": cad}
        count = 0 if cad else self.panel.count_of(path)
        where = os.path.relpath(os.path.dirname(path), self.panel.place_root())
        where = "" if where in (".", "") else where.replace(os.sep, " / ")
        parts = [dp.badge(count)] if count else []
        parts.append(dp.subtitle(design, where=where if self.panel.searching() else None))
        self.info.setText(" · ".join(p for p in parts if p))
        self.info.setToolTip(dp.tooltip(design, count))
        self._fill_insert(cad)
        self.tabs.setVisible(not cad)
        if not cad:
            self._fill_versions()
            self._fill_uses()
            self._tab_shown()
        self.show()

    def _fill_insert(self, cad):
        self.insert_menu.clear()
        has_doc = App.ActiveDocument is not None
        path = self.path
        if cad:
            self.insert_menu.addAction(
                "Insert into Current Design", lambda: vui._insert_cad(path)
            ).setEnabled(has_doc)
            return
        self.insert_menu.addAction(
            "Insert a Copy into Current Design", lambda: vui.insert_copy(path)
        ).setEnabled(has_doc)
        self.insert_menu.addAction(
            "Insert into Current Design (linked)", lambda: vui.insert_design(path)
        ).setEnabled(has_doc)

    def _fill_versions(self):
        self.versions.clear()
        try:
            listed = list(reversed(vui.store_of(self.path).versions()))  # newest first
        except Exception as exc:
            warn("data panel versions: %s" % exc)
            listed = []
        for info in listed:
            item = QtWidgets.QListWidgetItem(dp.version_row(info))
            item.setData(ROLE, info.number)
            if info.current or info is listed[0]:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.versions.addItem(item)
        if not listed:
            self.versions.addItem(QtWidgets.QListWidgetItem("No versions saved yet"))

    def _fill_uses(self):
        self.uses.clear()
        try:
            found = dp.uses(self.path, core.read_design_xml(self.path))
        except Exception:
            found = []
        for name, target, there in found:
            item = QtWidgets.QListWidgetItem(name + ("" if there else "  (not found)"))
            item.setData(ROLE, target)
            item.setToolTip(target)
            self.uses.addItem(item)
        if not found:
            self.uses.addItem(QtWidgets.QListWidgetItem("It inserts no other design"))
        self.tabs.setTabText(1, "Uses (%d)" % len(found) if found else "Uses")

    def _tab_shown(self):
        """Used In reads every design of the place: only when its tab is shown."""
        if self.tabs.currentWidget() is not self.used_in or self.path is None:
            return
        if self._used_in_for == self.path:
            return
        self._used_in_for = self.path
        self.used_in.clear()
        try:
            found = dp.used_in(self.path, self.panel.place_root())
        except Exception as exc:
            warn("data panel used in: %s" % exc)
            found = []
        for name, target in found:
            item = QtWidgets.QListWidgetItem(name)
            item.setData(ROLE, target)
            item.setToolTip(target)
            self.used_in.addItem(item)
        if not found:
            self.used_in.addItem(QtWidgets.QListWidgetItem("No design of this place inserts it"))

    # -- actions
    def _close(self):
        self.panel.details_closed = self.path
        self.hide()

    def _open(self):
        if self.path:
            path = self.path
            QtCore.QTimer.singleShot(0, lambda: vui.open_design(path))

    def _info(self, item):
        number = item.data(ROLE) if item is not None else None
        if number is None or self.path is None:
            return None
        return vui.number_to_info(self.path, number)

    def _open_version(self, item):
        try:
            info = self._info(item)
            if info is None:
                return
            listed = vui.store_of(self.path).versions()
            newest = listed[-1].number if listed else None
            path = self.path
            if info.number == newest:
                QtCore.QTimer.singleShot(0, lambda: vui.open_design(path))
            else:
                QtCore.QTimer.singleShot(0, lambda: vui.open_version(path, info))
        except Exception as exc:
            warn("data panel version: %s" % exc)

    def _version_menu(self, pos):
        try:
            item = self.versions.itemAt(pos)
            info = self._info(item)
            if info is None:
                return
            path = self.path
            menu = QtWidgets.QMenu(self)
            menu.addAction("Open", lambda: self._open_version(item))
            menu.addAction("Promote", lambda: vui.promote(path, info))
            menu.addSeparator()
            menu.addAction("Version History", lambda: vui.show_history(path))
            menu.exec_(self.versions.viewport().mapToGlobal(pos))
        except Exception as exc:
            warn("data panel version menu: %s" % exc)

    def _open_other(self, item):
        target = item.data(ROLE) if item is not None else None
        if target and os.path.isfile(target):
            QtCore.QTimer.singleShot(0, lambda: vui.open_design(target))


# -- the panel ----------------------------------------------------------------------------------
class DataPanel(QtWidgets.QWidget):
    """Fusion's Data Panel on local files (see the module text)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("SciForgeDataPanel")
        self.folder = vui.project_folder()
        self.root = None  # the place shown (None: This computer, the project folder)
        self.conflicts = {}  # file name -> its original's name (sync apps' copies here)
        self.dragging = False
        self.details_closed = None  # the design whose details were closed (stay closed)
        self._thumbs = {}  # (path, size) -> (mtime, QIcon or QPixmap)
        self._counts = {}  # path -> version count of the last listing
        self._listing = None  # what the folder held at the last refresh (for the poll)
        self._slow = set()  # folders too slow to look at every few seconds (a far NAS)
        try:
            self.sort = dp.known_sort(_prefs().GetString("DataPanelSort", dp.DEFAULT_SORT))
        except Exception:
            self.sort = dp.DEFAULT_SORT
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)
        # SCIFORGE places (M2): This computer, the clouds and NAS connected
        self.places = QtWidgets.QComboBox()
        self.places.setObjectName("SciForgeDataPanelPlace")
        self.places.setToolTip("Which place to show: this computer, a cloud or a NAS")
        self.places.activated.connect(self._place_chosen)
        outer.addWidget(self.places)
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(2)
        self.up = self._tool("Up", "Up one folder (Backspace)", self.go_up, "SciForgeDataPanelUp")
        bar.addWidget(self.up)
        self.crumbs = QtWidgets.QLabel("")
        self.crumbs.setTextFormat(QtCore.Qt.RichText)
        self.crumbs.linkActivated.connect(self.set_folder)
        bar.addWidget(self.crumbs, 1)
        self.reload = self._tool("Refresh", "Refresh", self.refresh, "SciForgeDataPanelRefresh")
        bar.addWidget(self.reload)
        self.choose = self._tool(
            "...",
            "Choose the project folder (your NAS folder)",
            self.choose_project_folder,
            "SciForgeDataPanelFolder",
        )
        bar.addWidget(self.choose)
        outer.addLayout(bar)
        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(4)
        self.upload = QtWidgets.QPushButton("Upload")
        self.upload.setObjectName("SciForgeDataPanelUpload")
        self.upload.setToolTip(
            "Copy a design or a STEP / IGES file into this folder (or drop files on the panel)"
        )
        self.upload.clicked.connect(lambda *_: self.upload_file())
        accent = theme.ACCENT or "#3fa9f5"
        self.upload.setStyleSheet(
            "QPushButton#SciForgeDataPanelUpload { background: %s; color: #ffffff; "
            "border: none; border-radius: 3px; padding: 4px 12px; }" % accent
        )
        actions.addWidget(self.upload)
        self.new_folder = self._tool(
            "New Folder", "New Folder", self.make_folder, "SciForgeDataPanelNewFolder"
        )
        self.new_folder.setIcon(ui_icon("folder"))
        self.new_folder.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        actions.addWidget(self.new_folder)
        actions.addStretch(1)
        outer.addLayout(actions)
        find = QtWidgets.QHBoxLayout()
        find.setSpacing(4)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SciForgeDataPanelSearch")
        self.search.setPlaceholderText("Search this place")
        self.search.setClearButtonEnabled(True)
        self.search.setToolTip("Find designs and folders by name, in every folder of this place")
        self.search.textChanged.connect(lambda *_: self._search_soon.start())
        self.search.installEventFilter(self)
        find.addWidget(self.search, 1)
        self.sort_box = QtWidgets.QComboBox()
        self.sort_box.setObjectName("SciForgeDataPanelSort")
        self.sort_box.setToolTip("Sort the designs (folders stay first)")
        for key, label in dp.SORTS:
            self.sort_box.addItem(label, key)
        self.sort_box.setCurrentIndex([k for k, _l in dp.SORTS].index(self.sort))
        self.sort_box.currentIndexChanged.connect(self._sort_chosen)
        find.addWidget(self.sort_box)
        self.as_list = False
        self.view_toggle = self._tool(
            "List",
            "List view / grid view",
            lambda *_: self._view_mode(not self.as_list),
            "SciForgeDataPanelView",
        )
        find.addWidget(self.view_toggle)
        outer.addLayout(find)
        self._search_soon = QtCore.QTimer(self)
        self._search_soon.setSingleShot(True)
        self._search_soon.setInterval(250)
        self._search_soon.timeout.connect(self.refresh)
        self.split = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.split.setObjectName("SciForgeDataPanelSplit")
        self.split.setChildrenCollapsible(False)
        self.list = DataPanelList(self)
        self.list.setMinimumHeight(180)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        self.list.itemDoubleClicked.connect(self.open_item)
        self.list.itemSelectionChanged.connect(self._selection_changed)
        self.list.setWordWrap(True)
        self.split.addWidget(self.list)
        self.details = DetailsPane(self)
        self.split.addWidget(self.details)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 1)
        outer.addWidget(self.split, 1)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        try:
            as_list = _prefs().GetBool("DataPanelList", False)
        except Exception:
            as_list = False
        self._view_mode(as_list)
        self._poll = QtCore.QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._look_for_changes)
        self._poll.start()
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

    def eventFilter(self, obj, event):
        """Esc in the search box clears it (the cards of the folder come back)."""
        try:
            if (
                obj is self.search
                and event.type() == QtCore.QEvent.KeyPress
                and event.key() == QtCore.Qt.Key_Escape
                and self.search.text()
            ):
                self.search.clear()
                return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _view_mode(self, as_list):
        self.as_list = bool(as_list)
        try:
            _prefs().SetBool("DataPanelList", self.as_list)
        except Exception:
            pass
        self.view_toggle.setText("Grid" if as_list else "List")
        if as_list:
            self.list.setViewMode(QtWidgets.QListView.ListMode)
            self.list.setIconSize(QtCore.QSize(SMALL, SMALL))
            self.list.setGridSize(QtCore.QSize())
            self.list.setSpacing(1)
        else:
            self.list.setViewMode(QtWidgets.QListView.IconMode)
            self.list.setIconSize(QtCore.QSize(THUMB, THUMB))
            self.list.setGridSize(QtCore.QSize(THUMB + 28, THUMB + 52))
            self.list.setResizeMode(QtWidgets.QListView.Adjust)
            self.list.setMovement(QtWidgets.QListView.Static)
            self.list.setSpacing(6)
        self.list.setDragEnabled(False)  # (DataPanelList starts its own drags)
        self.list.setAcceptDrops(True)
        self.list.doItemsLayout()

    def _sort_chosen(self, index):
        try:
            key = dp.known_sort(self.sort_box.itemData(index))
            if key == self.sort:
                return
            self.sort = key
            _prefs().SetString("DataPanelSort", self.sort)
            self.refresh()
        except Exception as exc:
            warn("data panel sort: %s" % exc)

    def set_sort(self, key):
        """Sort by `key` ("name", "modified", "size"), as the drop-down does (tests)."""
        keys = [k for k, _l in dp.SORTS]
        if key in keys:
            self.sort_box.setCurrentIndex(keys.index(key))

    # -- what is shown
    def place_root(self):
        return self.root or vui.project_folder()

    def searching(self):
        return bool(dp.words(self.search.text()))

    def _fill_places(self):
        try:
            from . import locations_core, locations_ui

            self.places.blockSignals(True)
            self.places.clear()
            current = 0
            for i, place in enumerate(locations_ui.all_places()):
                offline = place["kind"] != "local" and (
                    locations_core.status(place) != locations_core.OK
                )
                self.places.addItem(
                    place["name"] + (" (offline)" if offline else ""), place["root"]
                )
                if self.root and core.same_path(place["root"], self.root):
                    current = i
            self.places.setCurrentIndex(current)
            self.places.setVisible(self.places.count() > 1)
        except Exception as exc:
            warn("data panel: places: %s" % exc)
        finally:
            self.places.blockSignals(False)

    def _place_chosen(self, index):
        try:
            root = self.places.itemData(index)
            self.root = None if core.same_path(root, vui.project_folder()) else root
            self.folder = self.place_root()
            self.refresh()
        except Exception as exc:
            warn("data panel: %s" % exc)

    def set_folder(self, folder):
        project = self.place_root()
        if not core.inside(project, folder):
            folder = project
        self.folder = folder
        if self.search.text():
            self.search.blockSignals(True)
            self.search.clear()  # opening a folder leaves the search
            self.search.blockSignals(False)
        self.refresh()

    def go_up(self):
        if core.same_path(self.folder, self.place_root()):
            return
        self.set_folder(os.path.dirname(self.folder))

    def _version_counts(self, project):
        if self.root is not None or not vui.use_git() or not core.git_available():
            return None
        root = core.repo_root(project)
        if root is None:
            return None
        counts = core.repo_counts(root)
        if not core.same_path(root, project):
            counts = {
                os.path.relpath(os.path.join(root, k), project).replace(os.sep, "/"): n
                for k, n in counts.items()
            }
        return counts

    def count_of(self, path):
        if path in self._counts:
            return self._counts[path]
        try:
            return core.version_count(path, self.place_root(), vui.use_git())
        except Exception:
            return 0

    def refresh(self):
        try:
            self._fill_places()
            project = self.place_root()
            if self.root is None and not os.path.isdir(project):
                try:
                    os.makedirs(project, exist_ok=True)
                    log("made the project folder %s" % project)
                except OSError:
                    pass
            if not core.inside(project, self.folder) or not os.path.isdir(self.folder):
                self.folder = project
            selected = self.selected_paths()
            self.list.blockSignals(True)  # (the details follow once, at the end)
            self.list.clear()
            self._counts = {}
            if not os.path.isdir(project):
                self.crumbs.setText("")
                self.status.setText(
                    "The project folder %s is not there. Choose one with the ... button." % project
                    if self.root is None
                    else "This place is offline: %s is not reachable now (is the cloud app "
                    "running, the NAS on?)." % project
                )
                self.up.setEnabled(False)
                self.details.show_for(None, None)
                return
            crumbs = core.breadcrumbs(project, self.folder)
            link = theme.TEXT or "#f5f5f5"
            self.crumbs.setText(
                " / ".join(
                    '<a href="%s" style="color:%s;text-decoration:none">%s</a>'
                    % (path, link, label)
                    for label, path in crumbs
                )
            )
            self.crumbs.setToolTip(self.folder)
            self.up.setEnabled(len(crumbs) > 1)
            query = self.search.text() if self.searching() else None
            more = False
            if query:
                folders, designs, more = dp.search(project, query)
                self.conflicts = {}
            else:
                folders, designs = core.list_folder(self.folder)
                from . import locations_ui

                self.conflicts = locations_ui.conflicts(
                    self.folder, [os.path.basename(d["path"]) for d in designs]
                )
                self._listing = self._scan(self.folder)
            folders, designs = dp.sort_entries(folders, designs, self.sort)
            counts = self._version_counts(project)
            now = time.time()
            for folder in folders:
                item = QtWidgets.QListWidgetItem(ui_icon("folder"), folder["name"])
                item.setData(ROLE, ("folder", folder["path"]))
                item.setData(ROLE_NAME, folder["name"])
                where = folder.get("where")
                item.setData(ROLE_SUB, ("Folder, in " + where) if where else "Folder")
                item.setData(ROLE_SHORT, ("in " + where) if where else "")
                item.setToolTip(folder["path"])
                self.list.addItem(item)
            for design in designs:
                n = (
                    0
                    if design.get("cad")
                    else core.version_count(design["path"], project, vui.use_git(), counts)
                )
                self._counts[design["path"]] = n
                original = self.conflicts.get(os.path.basename(design["path"]))
                item = QtWidgets.QListWidgetItem(
                    self._thumbnail(design["path"]),
                    dp.card_text(design["name"], n, bool(original)),
                )
                item.setData(ROLE, ("design", design["path"]))
                item.setData(ROLE_NAME, design["name"] + ("  (conflict)" if original else ""))
                item.setData(ROLE_BADGE, dp.badge(n))
                item.setData(ROLE_SUB, dp.subtitle(design, now, design.get("where")))
                short = dp.age(design.get("modified"), now)
                if design.get("where") is not None and query:
                    short = ("in " + design["where"]) if design["where"] else short
                item.setData(ROLE_SHORT, short)
                item.setToolTip(dp.tooltip(design, n))
                self.list.addItem(item)
            for path in selected:
                item = self.item_for(path)
                if item is not None:
                    item.setSelected(True)
                    self.list.setCurrentItem(item, QtCore.QItemSelectionModel.NoUpdate)
            self.status.setText(dp.status_text(folders, designs, query, more))
        except Exception as exc:
            warn("data panel: %s" % exc)
            self.status.setText("The folder could not be read: %s" % exc)
        finally:
            self.list.blockSignals(False)
        self._selection_changed()

    # -- changes made elsewhere (the file manager, another computer on the NAS)
    def _scan(self, folder):
        started = time.time()
        try:
            found = tuple(
                sorted(
                    (entry.name, entry.stat().st_mtime if entry.is_file() else 0)
                    for entry in os.scandir(folder)
                )
            )
        except OSError:
            found = None
        if time.time() - started > SLOW_SCAN and folder not in self._slow:
            self._slow.add(folder)
            log("data panel: %s is slow to list; it is refreshed on Refresh only" % folder)
        return found

    def _look_for_changes(self):
        try:
            if (
                not self.isVisible()
                or self.dragging
                or self.searching()
                or self.folder in self._slow
                or QtWidgets.QApplication.activePopupWidget() is not None
            ):
                return
            if self._scan(self.folder) != self._listing:
                self.refresh()
        except Exception as exc:
            warn("data panel: %s" % exc)

    # -- pictures
    def _thumbnail(self, path):
        cached = self._thumbs.get((path, THUMB))
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        if cached is not None and cached[0] == mtime:
            return cached[1]
        icon = ui_icon("document")
        pixmap = self._pixmap(path, THUMB)
        if pixmap is not None:
            icon = QtGui.QIcon(pixmap)
        self._thumbs[(path, THUMB)] = (mtime, icon)
        return icon

    @staticmethod
    def _pixmap(path, size):
        data = core.thumbnail_bytes(path) if core.is_design(path) else None
        if not data:
            return None
        pixmap = QtGui.QPixmap()
        if pixmap.loadFromData(QtCore.QByteArray(data), "PNG") and not pixmap.isNull():
            return pixmap.scaled(
                size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
            )
        return None

    def picture(self, path, size):
        """The design's picture at `size` px (the details), or its file icon."""
        pixmap = self._pixmap(path, size)
        if pixmap is not None:
            return pixmap
        return ui_icon("document").pixmap(size // 2, size // 2)

    def has_thumbnail(self, path):
        """Whether the card of `path` shows the design's own picture (tests)."""
        cached = self._thumbs.get((path, THUMB))
        return bool(cached and core.thumbnail_bytes(path))

    # -- reading the cards
    def items(self):
        """[(kind, path, text)] as listed (tests)."""
        found = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            kind, path = item.data(ROLE)
            found.append((kind, path, item.text()))
        return found

    def item_for(self, path):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if core.same_path(item.data(ROLE)[1], path):
                return item
        return None

    def selected_paths(self):
        return [i.data(ROLE)[1] for i in self.list.selectedItems()]

    def selected_designs(self):
        """The selected designs (folders and STEP files are not dragged into a design)."""
        return [
            i.data(ROLE)[1]
            for i in self.list.selectedItems()
            if i.data(ROLE)[0] == "design" and dp.insertable(i.data(ROLE)[1])
        ]

    def select(self, path):
        """Click the card of `path` (tests, Upload, New Folder)."""
        item = self.item_for(path)
        if item is not None:
            self.list.clearSelection()
            self.list.setCurrentItem(item)
            item.setSelected(True)
        return item

    def _selection_changed(self):
        try:
            current = self.list.currentItem()
            items = self.list.selectedItems()
            if current is None or not current.isSelected():
                current = items[0] if items else None
            kind, path = current.data(ROLE) if current is not None else (None, None)
            if path is not None and path == self.details_closed:
                self.details.hide()
                return
            self.details_closed = None
            if self.details.path != path or not self.details.isVisible():
                self.details.show_for(kind, path)
        except Exception as exc:
            warn("data panel details: %s" % exc)

    # -- actions
    def key(self, key):
        """The panel's keys on the cards. True when the key was used."""
        item = self.list.currentItem()
        kind, path = item.data(ROLE) if item is not None else (None, None)
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and item is not None:
            self.open_item(item)
            return True
        if key == QtCore.Qt.Key_F2 and item is not None:
            QtCore.QTimer.singleShot(0, lambda: self._rename(path, kind == "folder"))
            return True
        if key == QtCore.Qt.Key_Delete and kind == "design":
            QtCore.QTimer.singleShot(0, lambda: self._trash(path))
            return True
        if key == QtCore.Qt.Key_Backspace:
            QtCore.QTimer.singleShot(0, self.go_up)
            return True
        return False

    def open_item(self, item):
        """Double-click: into a folder, or open the design. The item's data is read now
        and the work done a moment later: entering a folder rebuilds the list, and the
        item would be gone under the signal."""
        try:
            if item is None:
                return
            kind, path = item.data(ROLE)
        except Exception as exc:
            warn("data panel: %s" % exc)
            return
        QtCore.QTimer.singleShot(0, lambda: self._open(kind, path))

    def _open(self, kind, path):
        try:
            if kind == "folder":
                self.set_folder(path)
            else:
                vui.open_design(path)
        except Exception as exc:
            warn("data panel: %s" % exc)

    def upload_file(self, path=None):
        """Fusion's Upload: a design, or a STEP / IGES file, is copied into the folder
        shown; double-click opens it (a STEP file as a new design with its components)."""
        try:
            if path is None:
                path = vui.UPLOAD_PICKER() if vui.UPLOAD_PICKER is not None else None
            if path is None:
                path, _filter = QtWidgets.QFileDialog.getOpenFileName(
                    self,
                    "Upload",
                    os.path.expanduser("~"),
                    "Designs and STEP / IGES files (*.FCStd *.fcstd *.step *.stp *.STEP "
                    "*.STP *.iges *.igs *.IGES *.IGS)",
                )
            if not path:
                return None
            made = self.upload_files([path], self.folder)
            return made[0] if made else None
        except Exception as exc:
            warn("upload: %s" % exc)
            commands.tell("The file could not be uploaded: %s" % exc)
            return None

    def upload_files(self, paths, folder=None):
        """Copy designs / STEP / IGES files into `folder` (default: the one shown)."""
        import shutil

        folder = folder or self.folder
        made = []
        for path in paths:
            try:
                kind = dp.upload_kind(path)
                if kind is None:
                    commands.tell(
                        "Upload takes designs (.FCStd) and STEP (.step, .stp) or IGES "
                        "(.iges, .igs) files."
                    )
                    continue
                if kind == "design":
                    target = vui.copy_design(path, folder)
                else:
                    target = dp.upload_target(folder, path)
                    shutil.copy2(path, target)
                    log("uploaded %s to %s" % (path, target))
                    commands.tell(
                        "%s is in the project: double-click it to open it."
                        % os.path.basename(target)
                    )
                if target:
                    made.append(target)
            except Exception as exc:
                warn("upload: %s" % exc)
                commands.tell("The file could not be uploaded: %s" % exc)
        self.refresh()
        if made:
            self.select(made[-1])
        return made

    def make_folder(self):
        try:
            path = core.new_folder(self.folder)
            log("made the folder %s" % path)
            if self.search.text():
                self.search.clear()
            self.refresh()
            self.select(path)
        except Exception as exc:
            warn("new folder: %s" % exc)
            commands.tell("The folder could not be made: %s" % exc)

    def choose_project_folder(self):
        try:
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Project folder (where your designs live)", vui.project_folder()
            )
            if path:
                vui.set_project_folder(path)
                self.set_folder(path)
                log("project folder: %s" % path)
        except Exception as exc:
            warn("choosing the project folder: %s" % exc)

    def move_paths(self, paths, folder):
        """Cards dropped on a folder card: each design moves there with its versions
        (Fusion's drag onto a folder); a STEP file is just moved."""
        moved = []
        for path in dp.move_target(paths, folder):
            try:
                if core.is_cad_file(path):
                    target = dp.upload_target(folder, path)
                    os.replace(path, target)
                    log("moved %s to %s" % (path, target))
                    moved.append(target)
                else:
                    new = vui.move_design(path, folder)
                    if new:
                        moved.append(new)
            except Exception as exc:
                warn("move: %s" % exc)
                commands.tell("Could not move: %s" % exc)
        self.refresh()
        return moved

    def _menu(self, pos):
        try:
            item = self.list.itemAt(pos)
            menu = QtWidgets.QMenu(self)
            menu.setObjectName("SciForgeDataPanelMenu")
            if item is None:
                menu.addAction("New Folder", self.make_folder)
                menu.addAction("Upload...", lambda: self.upload_file())
                menu.addAction("Refresh", self.refresh)
            else:
                if not item.isSelected():
                    self.select(item.data(ROLE)[1])
                kind, path = item.data(ROLE)
                has_doc = App.ActiveDocument is not None
                if kind == "folder":
                    menu.addAction("Open", lambda: self.set_folder(path))
                    menu.addAction("Rename", lambda: self._rename(path, True))
                elif core.is_cad_file(path):  # an uploaded STEP / IGES file
                    menu.addAction("Open", lambda: vui.open_design(path))
                    menu.addAction(
                        "Insert into Current Design", lambda: vui._insert_cad(path)
                    ).setEnabled(has_doc)
                    menu.addSeparator()
                    menu.addAction("Delete", lambda: self._trash(path))
                else:
                    menu.addAction("Open", lambda: vui.open_design(path))
                    original = self.conflicts.get(os.path.basename(path))
                    if original:
                        twin = os.path.join(os.path.dirname(path), original)
                        menu.addAction(
                            "Compare with %s" % core.design_name(original),
                            lambda: vui.compare_files(path, twin),
                        )
                        menu.addAction("Keep This One", lambda: self.keep_copy(path, twin))
                        menu.addSeparator()
                    menu.addAction("Version History", lambda: vui.show_history(path))
                    menu.addAction("Milestones", lambda: vui.show_history(path, True))
                    menu.addAction(
                        "Insert into Current Design", lambda: vui.insert_design(path)
                    ).setEnabled(has_doc)
                    menu.addAction(
                        "Insert a Copy into Current Design", lambda: vui.insert_copy(path)
                    ).setEnabled(has_doc)
                    menu.addSeparator()
                    menu.addAction("Rename", lambda: self._rename(path, False))
                    menu.addAction("Move...", lambda: self.move_or_copy(path, "move"))
                    menu.addAction("Copy...", lambda: self.move_or_copy(path, "copy"))
                    menu.addAction("Delete", lambda: self._trash(path))
                menu.addSeparator()
                menu.addAction("Show in Folder", lambda: vui._show_in_folder(path))
            menu.exec_(self.list.mapToGlobal(pos))
        except Exception as exc:
            warn("data panel menu: %s" % exc)

    def keep_copy(self, copy, original):
        kept = vui.keep_conflict_copy(copy, original, self.place_root())
        self.refresh()
        return kept

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
                open_doc = vui.doc_for_file(path)
                if open_doc is not None and vui._has_views(open_doc):
                    raise core.StoreError("Close the design before renaming it.")
                users = vui._open_referrers(path)
                if users:
                    raise core.StoreError("Close %s first: it uses %s." % (", ".join(users), old))
                core.rename_design(path, new, vui.project_folder(), vui.use_git())
            self.refresh()
        except Exception as exc:
            warn("rename: %s" % exc)
            commands.tell("Could not rename: %s" % exc)

    def move_or_copy(self, path, kind):
        """Right-click > Move... / Copy...: pick the folder (Fusion's Move / Copy To)."""
        try:
            dialog = vui.MoveCopyDialog(path, kind, self.folder)
            dialog.accepted.connect(lambda: self._moved_or_copied(path, kind, dialog.target()))
            vui._show(dialog, "%s:%s" % (kind, path))
        except Exception as exc:
            warn("%s: %s" % (kind, exc))

    def _moved_or_copied(self, path, kind, folder):
        if not folder:
            return
        done = vui.move_design(path, folder) if kind == "move" else vui.copy_design(path, folder)
        if done:
            self.refresh()

    def _trash(self, path):
        try:
            if vui.doc_for_file(path) is not None:
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
            target = core.trash_design(path, vui.project_folder())
            log("moved %s to %s" % (path, target))
            self.refresh()
        except Exception as exc:
            warn("delete: %s" % exc)
            commands.tell("Could not delete: %s" % exc)
