# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style BROWSER panel on the left (replaces FreeCAD's tree while on).

Eye column toggles visibility (folders toggle everything inside), click
selects, double-click edits a sketch or activates a body, right click offers
Rename / Show-Hide / Edit / Activate / Delete. Structure: browser_core.py.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import browser_core as core
from . import commands, ui_icon, warn
from .compat import QtCore, QtWidgets

ROLE_NODE = QtCore.Qt.UserRole


def _objects(doc):
    rows = []
    for obj in doc.Objects:
        try:
            parent = obj.getParentGeoFeatureGroup()
            visible = obj.ViewObject.Visibility if obj.ViewObject is not None else None
            rows.append(
                {
                    "name": obj.Name,
                    "label": obj.Label,
                    "type_id": obj.TypeId,
                    "visible": visible,
                    "body": (
                        parent.Name
                        if parent is not None and parent.TypeId == "PartDesign::Body"
                        else None
                    ),
                    "role": getattr(obj, "Role", None),
                }
            )
        except Exception:
            continue
    return rows


def _units():
    try:
        schema = App.Units.listSchemas(App.Units.getSchema())
        inside = schema.split("(", 1)[1].split(")")[0]
        return ", ".join(part.strip() for part in inside.split(",")[:2])
    except Exception:
        return "mm"


class BrowserWidget(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeBrowser")
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header().setStretchLastSection(True)
        self.setColumnWidth(0, 44)
        self._sig = None
        self._building = False
        self._expanded = {"document", "bodies", "sketches", "settings"}
        self._doc = None
        self.itemClicked.connect(self._clicked)
        self.itemDoubleClicked.connect(self._double_clicked)
        self.itemChanged.connect(self._renamed)
        self.itemExpanded.connect(lambda i: self._expanded.add(i.data(1, ROLE_NODE)["key"]))
        self.itemCollapsed.connect(lambda i: self._expanded.discard(i.data(1, ROLE_NODE)["key"]))
        self.customContextMenuRequested.connect(self._menu)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)

    def start(self):
        self.refresh()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # -- building ------------------------------------------------------------------
    def tree(self):
        doc = App.ActiveDocument
        self._doc = doc
        if doc is None:
            return core._node("document", "(no design open)", "document", "document")
        body = commands.active_body()
        return core.build(
            doc.Label, _objects(doc), _units(), body.Name if body is not None else None
        )

    def refresh(self):
        try:
            tree = self.tree()
            sig = core.signature(tree)
            if sig != self._sig:
                self._sig = sig
                self._rebuild(tree)
            self._sync_selection()
        except Exception as exc:
            warn("browser refresh skipped: %s" % exc)

    def _rebuild(self, tree):
        self._building = True
        try:
            self.clear()
            self._add(None, tree)
        finally:
            self._building = False

    def _add(self, parent, node):
        item = QtWidgets.QTreeWidgetItem(parent if parent is not None else self)
        item.setData(1, ROLE_NODE, node)
        if node["visible"] is not None:
            item.setIcon(0, ui_icon("eye" if node["visible"] else "eye_off"))
            item.setToolTip(0, "Show/hide")
        item.setIcon(1, ui_icon(node["icon"]))
        item.setText(1, node["label"])
        if node["kind"] in ("body", "sketch", "construction"):
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        for child in node["children"]:
            self._add(item, child)
        item.setExpanded(node["key"] in self._expanded)
        return item

    def _sync_selection(self):
        names = {s.ObjectName for s in Gui.Selection.getSelectionEx()}
        self.blockSignals(True)
        try:
            for item in self._items():
                node = item.data(1, ROLE_NODE)
                item.setSelected(node["object"] in names and node["kind"] != "view")
        finally:
            self.blockSignals(False)

    def _items(self):
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value():
            yield it.value()
            it += 1

    # -- actions -------------------------------------------------------------------
    def _object(self, node):
        return self._doc.getObject(node["object"]) if self._doc and node["object"] else None

    def _set_visible(self, node, visible):
        targets = [n for n in core.walk(node) if n["object"] and n["visible"] is not None]
        for n in targets:
            obj = self._object(n)
            if obj is not None and obj.ViewObject is not None:
                obj.ViewObject.Visibility = visible
        self.refresh()

    def _clicked(self, item, column):
        node = item.data(1, ROLE_NODE)
        try:
            if column == 0 and node["visible"] is not None:
                self._set_visible(node, not node["visible"])
                return
            if node["kind"] == "view":
                Gui.runCommand(node["object"])
                return
            obj = self._object(node)
            if obj is not None:
                modifiers = QtWidgets.QApplication.keyboardModifiers()
                if not modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                    Gui.Selection.clearSelection()
                Gui.Selection.addSelection(self._doc.Name, obj.Name)
        except Exception as exc:
            warn("browser: %s" % exc)

    def _double_clicked(self, item, column):
        node = item.data(1, ROLE_NODE)
        try:
            obj = self._object(node)
            if node["kind"] == "body" and obj is not None:
                self._activate(obj)
            elif node["kind"] in ("sketch", "construction") and obj is not None:
                Gui.ActiveDocument.setEdit(obj.Name)
            elif node["kind"] == "units":
                Gui.runCommand("Std_DlgPreferences")
        except Exception as exc:
            warn("browser: %s" % exc)

    def _activate(self, body):
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        self.refresh()

    def _renamed(self, item, column):
        if self._building or column != 1:
            return
        node = item.data(1, ROLE_NODE)
        obj = self._object(node)
        text = item.text(1).replace("●", "").strip()
        if obj is not None and text and text != obj.Label:
            obj.Label = text
        self._sig = None
        QtCore.QTimer.singleShot(0, self.refresh)

    def _menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        node = item.data(1, ROLE_NODE)
        obj = self._object(node)
        menu = QtWidgets.QMenu(self)
        actions = {}
        if obj is not None:
            actions[menu.addAction("Rename")] = lambda: self.editItem(item, 1)
        if node["visible"] is not None:
            label = "Hide" if node["visible"] else "Show"
            actions[menu.addAction(label)] = lambda: self._set_visible(node, not node["visible"])
        if node["kind"] in ("sketch", "construction") and obj is not None:
            actions[menu.addAction("Edit")] = lambda: Gui.ActiveDocument.setEdit(obj.Name)
        if node["kind"] == "body" and obj is not None:
            actions[menu.addAction("Activate")] = lambda: self._activate(obj)
        if obj is not None and node["kind"] != "origin":
            menu.addSeparator()

            def delete():
                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(self._doc.Name, obj.Name)
                Gui.runCommand("Std_Delete")

            actions[menu.addAction(ui_icon("delete"), "Delete")] = delete
        if not actions:
            return
        chosen = menu.exec_(self.viewport().mapToGlobal(pos))
        if chosen in actions:
            try:
                actions[chosen]()
            except Exception as exc:
                warn("browser: %s" % exc)


_state = {"widget": None, "dock": None, "original": None, "title": None}


def show():
    """Put the browser inside FreeCAD's "Model" dock in place of its tree. The dock
    itself stays visible, so FreeCAD never saves it as hidden."""
    main = Gui.getMainWindow()
    dock = main.findChild(QtWidgets.QDockWidget, "Model")
    if _state["widget"] is None:
        _state["widget"] = BrowserWidget()
    if dock is None:  # unusual layout: fall back to a dock of our own
        dock = QtWidgets.QDockWidget("BROWSER", main)
        dock.setObjectName("SciForgeBrowserDock")
        main.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    if dock.widget() is not _state["widget"]:
        _state["original"] = dock.widget()
        _state["title"] = dock.windowTitle()
        if _state["original"] is not None:
            _state["original"].hide()
        dock.setWidget(_state["widget"])
    _state["dock"] = dock
    dock.setWindowTitle("BROWSER")
    dock.show()
    _state["widget"].show()
    _state["widget"].start()


def hide():
    """Give FreeCAD its tree back."""
    widget, dock = _state["widget"], _state["dock"]
    if widget is None or dock is None:
        return
    widget.stop()
    if dock.widget() is widget:
        dock.setWidget(_state["original"])
        widget.setParent(None)
        if _state["original"] is not None:
            _state["original"].show()
        if _state["title"]:
            dock.setWindowTitle(_state["title"])
    _state["dock"] = None


def widget():
    return _state["widget"]
