# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style BROWSER panel on the left (replaces FreeCAD's tree while on).

Each row: expand arrow, eye (show/hide), icon, name. Click selects (also in the
3D view, and a selection made in the 3D view shows here), double-click edits a
sketch or construction plane or activates a body, hover lights the object up in
the 3D view, F2 renames, Delete deletes, right click opens Fusion's menu for
that kind of row. Structure: browser_core.py; deleting goes through
timeline_ops.py (one undo step, later steps kept working where possible).
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import _remember, browser_core as core
from . import commands, timeline_ops as ops, ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets
from .inline_edit import InlineEditor

ROLE_NODE = QtCore.Qt.UserRole
EYE = 18  # width of the eye area at the start of a row
META_VIEW = "SciForge.NamedView."
_isolated = {}  # document name -> names of bodies Isolate hid


def _objects(doc):
    rows = []
    for obj in doc.Objects:
        try:
            parent = obj.getParentGeoFeatureGroup()
            visible = obj.ViewObject.Visibility if obj.ViewObject is not None else None
            if visible is not None and getattr(obj, "Role", None) in core.ORIGIN_ROLES:
                visible = _origin_visible(obj)
            row = {
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
                "sciforge_type": getattr(obj, "SciForgeType", ""),
            }
            if obj.TypeId in core.SKETCH_TYPES or obj.TypeId in core.CONSTRUCTION_TYPES:
                kind, reason = ops.problem(obj)
                if kind:
                    row[kind] = reason
                if ops.is_suppressed(obj):
                    row["warning"] = "Suppressed in the timeline"
            rows.append(row)
        except Exception:
            continue
    return rows


def _origin_of(feature):
    for parent in feature.InList:
        if parent.TypeId == "App::Origin":
            return parent
    return None


def _origin_visible(feature):
    """What you see: an origin plane shows only if it and its Origin are both on."""
    origin = _origin_of(feature)
    shown = feature.ViewObject.Visibility
    if origin is not None and origin.ViewObject is not None:
        shown = shown and origin.ViewObject.Visibility
    return bool(shown)


def _show_origin_feature(feature, visible, only=False):
    """Show/hide one origin plane/axis. FreeCAD shows them through their Origin, which
    shows all of them: turning one on alone turns the others off first."""
    origin = _origin_of(feature)
    if visible and origin is not None and origin.ViewObject is not None:
        if not origin.ViewObject.Visibility:
            if only:
                for other in origin.OriginFeatures:
                    if other is not feature and other.ViewObject is not None:
                        other.ViewObject.Visibility = False
            origin.ViewObject.Visibility = True
    feature.ViewObject.Visibility = visible
    if not visible and origin is not None and origin.ViewObject is not None:
        if not any(f.ViewObject.Visibility for f in origin.OriginFeatures if f.ViewObject):
            origin.ViewObject.Visibility = False


def units(doc):
    """Fusion's short unit name for the document ("mm")."""
    try:
        schema = doc.getEnumerationsOfProperty("UnitSystem").index(doc.UnitSystem)
    except Exception:
        try:
            schema = App.Units.getSchema()
        except Exception:
            return "mm"
    return core.unit_label(schema) or "mm"


def saved_views(doc):
    try:
        meta = doc.Meta
    except Exception:
        return []
    return sorted(k[len(META_VIEW) :] for k in meta if k.startswith(META_VIEW))


def _edit_object(obj):
    from . import taskui

    try:
        body = ops.body_of(obj)
        if body is not None:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    except Exception:
        pass
    taskui.edit_object(obj)


def _later(fn, *args):
    def run():
        try:
            fn(*args)
        except ops.TimelineError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("browser: %s" % exc)

    QtCore.QTimer.singleShot(0, run)


class _RowDelegate(QtWidgets.QStyledItemDelegate):
    """Draws the eye between the expand arrow and the icon, like Fusion, and turns a
    click on it into show/hide."""

    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree

    def _node(self, index):
        return index.data(ROLE_NODE) if index.column() == 1 else None

    def eye_rect(self, rect):
        return QtCore.QRect(rect.left() + 1, rect.top() + (rect.height() - 16) // 2, 16, 16)

    def paint(self, painter, option, index):
        node = self._node(index)
        if node is None:
            return super().paint(painter, option, index)
        if node["visible"] is not None:
            icon = ui_icon("eye" if node["visible"] else "eye_off")
            mode = QtGui.QIcon.Normal if node["visible"] else QtGui.QIcon.Disabled
            icon.paint(painter, self.eye_rect(option.rect), QtCore.Qt.AlignCenter, mode)
        shifted = QtWidgets.QStyleOptionViewItem(option)
        shifted.rect = option.rect.adjusted(EYE + 2, 0, 0, 0)
        if node["status"] == "error":
            shifted.palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#ff8a80"))
        elif node["status"] == "warning":
            shifted.palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#f2c440"))
        super().paint(painter, shifted, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QtCore.QSize(size.width() + EYE + 2, max(size.height(), 24))

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(EYE + 22, 0, 0, 0))

    def editorEvent(self, event, model, option, index):
        node = self._node(index)
        if node is None or node["visible"] is None:
            return False
        if event.type() in (
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseButtonRelease,
            QtCore.QEvent.MouseButtonDblClick,
        ):
            if self.eye_rect(option.rect).contains(event.position().toPoint()):
                if event.type() == QtCore.QEvent.MouseButtonRelease:
                    key = node["key"]
                    QtCore.QTimer.singleShot(0, lambda: self.tree.toggle_eye(key))
                return True
        return False


class BrowserWidget(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeBrowser")
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setTreePosition(1)
        self.setColumnHidden(0, True)  # the eye is drawn in the row (see _RowDelegate)
        self.setIndentation(14)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setMouseTracking(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header().setStretchLastSection(True)
        self.delegate = _RowDelegate(self)
        self.setItemDelegateForColumn(1, self.delegate)
        self._sig = None
        self._building = False
        self._syncing = False
        self._tree = None
        self._expanded = {"document", "bodies", "sketches", "settings", "construction"}
        self._doc = None
        self._renaming = None
        self._hover = None
        self._handlers = {}
        self._busy = 0
        self.itemClicked.connect(self._clicked)
        self.itemDoubleClicked.connect(self._double_clicked)
        self.itemEntered.connect(self._entered)
        self.itemSelectionChanged.connect(self._selection_changed)
        self.itemExpanded.connect(lambda i: self._expanded.add(i.data(1, ROLE_NODE)["key"]))
        self.itemCollapsed.connect(lambda i: self._expanded.discard(i.data(1, ROLE_NODE)["key"]))
        self.customContextMenuRequested.connect(self._menu)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)
        self._observer = None

    def start(self):
        self.refresh()
        self._timer.start()
        if self._observer is None:
            widget = self

            class Observer:
                """3D view selection -> browser (deferred: no work inside FreeCAD's
                selection handling)."""

                def _later(self, *args):
                    QtCore.QTimer.singleShot(30, widget._sync_selection)

                addSelection = removeSelection = setSelection = clearSelection = _later

            self._observer = Observer()
            try:
                Gui.Selection.addObserver(self._observer)
            except Exception as exc:
                warn("browser selection sync unavailable: %s" % exc)

    def stop(self):
        self._timer.stop()
        if self._observer is not None:
            try:
                Gui.Selection.removeObserver(self._observer)
            except Exception:
                pass
            self._observer = None

    # -- building ------------------------------------------------------------------
    def tree(self):
        doc = App.ActiveDocument
        self._doc = doc
        if doc is None:
            return core._node("document", "(no design open)", "document", "document")
        body = commands.active_body()
        return core.build(
            doc.Label,
            _objects(doc),
            units(doc),
            body.Name if body is not None else None,
            saved_views(doc),
        )

    def refresh(self, force=False):
        if self._busy:
            return
        try:
            if self._renaming is not None:
                return  # do not rebuild under the user's typing
            tree = self.tree()
            sig = core.signature(tree)
            if sig != self._sig or force:
                self._sig = sig
                self._tree = tree
                self._rebuild(tree)
            self._sync_selection()
        except Exception as exc:
            _remember("info", "browser refresh skipped: %s" % exc)

    def _rebuild(self, tree):
        self._building = True
        selected = {i.data(1, ROLE_NODE)["key"] for i in self.selectedItems()}
        try:
            self.clear()
            self._add(None, tree)
            for item in self._items():
                if item.data(1, ROLE_NODE)["key"] in selected:
                    item.setSelected(True)
        finally:
            self._building = False

    def _add(self, parent, node):
        item = QtWidgets.QTreeWidgetItem(parent if parent is not None else self)
        item.setData(1, ROLE_NODE, node)
        item.setIcon(1, ui_icon(node["icon"]))
        item.setText(1, node["label"])
        if node["active"]:
            font = item.font(1)
            font.setBold(True)
            item.setFont(1, font)
            item.setText(1, node["label"] + "  ●")
        tips = [node["tip"]] if node["tip"] else []
        if node["visible"] is not None:
            tips.append("Click the eye to show or hide")
        if tips:
            item.setToolTip(1, "\n".join(tips))
        for child in node["children"]:
            self._add(item, child)
        item.setExpanded(node["key"] in self._expanded)
        return item

    def _items(self):
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value():
            yield it.value()
            it += 1

    def item_for(self, key):
        for item in self._items():
            if item.data(1, ROLE_NODE)["key"] == key:
                return item
        return None

    def labels(self):
        return [i.text(1) for i in self._items()]

    def row(self, label):
        """The row whose name is ``label`` (tests and Find)."""
        for item in self._items():
            node = item.data(1, ROLE_NODE)
            if node["label"] == label or item.text(1) == label:
                return item
        return None

    def eye_point(self, item):
        """Viewport point of a row's eye (for a click)."""
        rect = self.visualRect(self.indexFromItem(item, 1))
        return self.delegate.eye_rect(rect).center()

    def label_point(self, item):
        rect = self.visualRect(self.indexFromItem(item, 1))
        return QtCore.QPoint(rect.left() + EYE + 30, rect.center().y())

    # -- selection: browser <-> 3D view ----------------------------------------------
    def _sync_selection(self):
        if self._building or self._syncing:
            return
        try:
            names = set()
            for sel in Gui.Selection.getSelectionEx():
                if sel.SubElementNames and any(sel.SubElementNames):
                    continue  # a face or edge: Fusion does not light up the browser
                names.add(sel.ObjectName)
        except Exception:
            return
        self._syncing = True
        self.blockSignals(True)
        try:
            for item in self._items():
                node = item.data(1, ROLE_NODE)
                want = node["object"] in names and node["kind"] not in ("view", "saved_view")
                if item.isSelected() != want:
                    item.setSelected(want)
        finally:
            self.blockSignals(False)
            self._syncing = False

    def _selection_changed(self):
        """Rows picked in the browser are selected in the 3D view too."""
        if self._building or self._syncing or self._doc is None:
            return
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            for item in self.selectedItems():
                obj = self._object(item.data(1, ROLE_NODE))
                if obj is not None:
                    Gui.Selection.addSelection(self._doc.Name, obj.Name)
        except Exception as exc:
            warn("browser: %s" % exc)
        finally:
            self._syncing = False

    def _entered(self, item, column):
        """Hover: light the object up in the 3D view, like Fusion."""
        try:
            obj = self._object(item.data(1, ROLE_NODE))
            if obj is self._hover:
                return
            Gui.Selection.clearPreselection()
            self._hover = obj
            if obj is not None and obj.ViewObject is not None and obj.ViewObject.Visibility:
                Gui.Selection.setPreselection(obj, "")
        except Exception:
            pass

    def leaveEvent(self, event):
        if self._hover is not None:
            self._hover = None
            try:
                Gui.Selection.clearPreselection()
            except Exception:
                pass
        super().leaveEvent(event)

    # -- actions -------------------------------------------------------------------
    def _object(self, node):
        if node is None or node["kind"] in ("view", "saved_view"):
            return None
        return self._doc.getObject(node["object"]) if self._doc and node["object"] else None

    def _set_visible(self, node, visible):
        targets = [n for n in core.walk(node) if n["object"] and n["visible"] is not None]
        for n in targets:
            obj = self._doc.getObject(n["object"]) if self._doc else None
            if obj is None or obj.ViewObject is None:
                continue
            if n["kind"] == "origin":
                _show_origin_feature(obj, visible, only=node["kind"] == "origin")
            else:
                obj.ViewObject.Visibility = visible
        self._refresh_soon()

    def _rename_key(self, key):
        item = self.item_for(key)
        if item is not None:
            self.rename(item)

    def toggle_eye(self, key):
        try:
            node = core.find(self._tree, key) if self._tree is not None else None
            if node is not None and node["visible"] is not None:
                self._set_visible(node, not node["visible"])
        except Exception as exc:
            warn("browser: %s" % exc)

    def _clicked(self, item, column):
        node = item.data(1, ROLE_NODE)
        try:
            if column == 0 and node["visible"] is not None:
                self._set_visible(node, not node["visible"])
                return
            if node["kind"] == "view":
                Gui.runCommand(node["object"])
            elif node["kind"] == "saved_view":
                self._go_to_view(node["object"])
            elif node["kind"] == "units":
                _later(open_units_panel)
        except Exception as exc:
            warn("browser: %s" % exc)

    def _double_clicked(self, item, column):
        node = item.data(1, ROLE_NODE)
        try:
            obj = self._object(node)
            if node["kind"] == "body" and obj is not None:
                self._activate(obj)
            elif node["kind"] in ("sketch", "construction") and obj is not None:
                _later(_edit_object, obj)
        except Exception as exc:
            warn("browser: %s" % exc)

    def _activate(self, body):
        Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        self._refresh_soon()

    def keyPressEvent(self, event):
        try:
            item = self.currentItem()
            node = item.data(1, ROLE_NODE) if item is not None else None
            if node is not None and event.key() == QtCore.Qt.Key_F2:
                self.rename(item)
                return
            if node is not None and event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                nodes = [i.data(1, ROLE_NODE) for i in self.selectedItems()] or [node]
                _later(self.delete, nodes)
                return
        except Exception as exc:
            warn("browser: %s" % exc)
            return
        super().keyPressEvent(event)

    def event(self, event):
        if event.type() == QtCore.QEvent.ShortcutOverride and event.key() in (
            QtCore.Qt.Key_Delete,
            QtCore.Qt.Key_Backspace,
            QtCore.Qt.Key_F2,
        ):
            event.accept()
            return True
        return super().event(event)

    RENAMABLE = ("body", "sketch", "construction", "analysis", "saved_view", "document")

    def rename(self, item):
        """The name becomes editable in place (Enter keeps it, Esc cancels)."""
        node = item.data(1, ROLE_NODE)
        if node["kind"] not in self.RENAMABLE:
            return
        self._cancel_rename()
        rect = self.visualRect(self.indexFromItem(item, 1)).adjusted(EYE + 22, 0, 0, 0)
        rect.setWidth(max(rect.width(), 120))
        key = node["key"]
        self._renaming = InlineEditor(
            self.viewport(), rect, node["label"], lambda text: self._renamed(key, text)
        )

    def _renamed(self, key, text):
        self._renaming = None
        node = core.find(self._tree, key) if self._tree is not None else None
        text = (text or "").strip()
        if node is None or not text:
            self._refresh_soon()
            return
        try:
            if node["kind"] == "document" and self._doc is not None:
                self._doc.Label = text
            elif node["kind"] == "saved_view":
                self._rename_view(node["object"], text)
            else:
                obj = self._object(node)
                if obj is not None and text != obj.Label:
                    ops.rename(self._doc, obj.Name, text)
        except Exception as exc:
            warn("browser rename: %s" % exc)
        self._refresh_soon()

    def _cancel_rename(self):
        if self._renaming is not None:
            editor, self._renaming = self._renaming, None
            editor.on_commit = lambda _t: None
            editor.cancel()

    def _refresh_soon(self):
        """Rebuild after the current click/key has been handled (rows stay valid)."""
        QtCore.QTimer.singleShot(0, lambda: self.refresh(force=True))

    def delete(self, nodes):
        doc = self._doc
        if doc is None or not commands.finish_open_dialog():
            return
        steps = [n["object"] for n in nodes if n["kind"] in ("sketch", "construction", "analysis")]
        body_names = [n["object"] for n in nodes if n["kind"] == "body"]
        views = [n["object"] for n in nodes if n["kind"] == "saved_view"]
        Gui.Selection.clearSelection()
        if steps:
            ops.delete(doc, [s for s in steps if doc.getObject(s) is not None])
        if body_names:
            ops.delete_bodies(doc, body_names)
        for name in views:
            self._delete_view(name)
        self.refresh(force=True)

    # -- named views ----------------------------------------------------------------
    def new_named_view(self):
        doc = self._doc
        if doc is None:
            return None
        existing = set(saved_views(doc))
        n = 1
        while "Named View %d" % n in existing:
            n += 1
        name = "Named View %d" % n
        meta = dict(doc.Meta)
        meta[META_VIEW + name] = Gui.ActiveDocument.ActiveView.getCamera()
        doc.Meta = meta
        self._expanded.add("views")
        self.refresh(force=True)
        return name

    def _go_to_view(self, name):
        camera = self._doc.Meta.get(META_VIEW + name) if self._doc else None
        if camera:
            Gui.ActiveDocument.ActiveView.setCamera(camera)

    def _rename_view(self, old, new):
        if not new or new == old or self._doc is None:
            return
        meta = dict(self._doc.Meta)
        if META_VIEW + old in meta and META_VIEW + new not in meta:
            meta[META_VIEW + new] = meta.pop(META_VIEW + old)
            self._doc.Meta = meta

    def _delete_view(self, name):
        meta = dict(self._doc.Meta)
        if meta.pop(META_VIEW + name, None) is not None:
            self._doc.Meta = meta

    # -- context menu ----------------------------------------------------------------
    def _menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        node = item.data(1, ROLE_NODE)
        if not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
        self.setCurrentItem(item)
        menu = self.build_menu(item)
        if menu is None:
            return
        self._busy += 1  # no rebuild under an open menu
        try:
            chosen = menu.exec_(self.viewport().mapToGlobal(pos))
        finally:
            self._busy -= 1
        action = self._handlers.get(chosen) if chosen is not None else None
        self._handlers = {}
        if action is not None:
            _later(action)

    def build_menu(self, item):
        node = item.data(1, ROLE_NODE)
        obj = self._object(node)
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("SciForgeBrowserMenu")
        self._handlers = {}
        doc = self._doc
        handlers = {
            "Show/Hide": lambda: self._set_visible(node, not node["visible"]),
            "Rename": lambda key=node["key"]: self._rename_key(key),
            "Delete": lambda: self.delete([node]),
            "Edit Sketch": lambda: _edit_object(obj),
            "Edit Feature": lambda: _edit_object(obj),
            "Activate Body": lambda: self._activate(obj),
            "Isolate": lambda: self._isolate(obj),
            "Find in Window": lambda: self._find_in_window(obj),
            "Find in Timeline": lambda: self._find_in_timeline(node),
            "Look At": lambda: self._look_at(obj),
            "Create Sketch": lambda: self._create_sketch(obj),
            "Change Active Units": open_units_panel,
            "New Named View": self.new_named_view,
            "Go to View": lambda: (
                Gui.runCommand(node["object"])
                if node["kind"] == "view"
                else self._go_to_view(node["object"])
            ),
            "Show All Bodies": lambda: self._show_all("body", True),
            "Show All Sketches": lambda: self._show_all("sketch", True),
            "Hide All Sketches": lambda: self._show_all("sketch", False),
        }
        if node["kind"] == "body" and _isolated.get(doc.Name if doc else None):
            handlers["Isolate"] = lambda: self._unisolate()
        entries = core.menu_for(node)
        if node["visible"] is None and "Show/Hide" in entries:
            entries.remove("Show/Hide")
        if node["kind"] in ("body", "sketch", "construction", "analysis") and obj is None:
            return None
        added = False
        for entry in entries:
            if entry == "-":
                if added:
                    menu.addSeparator()
                continue
            text = entry
            if entry == "Show/Hide":
                text = "Hide" if node["visible"] else "Show"
            if entry == "Isolate" and _isolated.get(doc.Name if doc else None):
                text = "Exit Isolate"
            if entry == "Activate Body" and node["active"]:
                continue
            action = (
                menu.addAction(ui_icon("delete"), text)
                if entry == "Delete"
                else menu.addAction(text)
            )
            self._handlers[action] = handlers.get(entry)
            if entry in ("Edit Sketch", "Edit Feature"):
                font = action.font()
                font.setBold(True)
                action.setFont(font)
            added = True
        return menu if added else None

    def _isolate(self, body):
        doc = self._doc
        hidden = []
        for other in ops.bodies(doc):
            if other is not body and other.ViewObject is not None and other.ViewObject.Visibility:
                other.ViewObject.Visibility = False
                hidden.append(other.Name)
        if body.ViewObject is not None:
            body.ViewObject.Visibility = True
        _isolated[doc.Name] = hidden
        self.refresh(force=True)

    def _unisolate(self):
        doc = self._doc
        for name in _isolated.pop(doc.Name, []):
            obj = doc.getObject(name)
            if obj is not None and obj.ViewObject is not None:
                obj.ViewObject.Visibility = True
        self.refresh(force=True)

    def _show_all(self, kind, visible):
        types = core.BODY_TYPES if kind == "body" else core.SKETCH_TYPES
        for obj in self._doc.Objects:
            if obj.TypeId in types and obj.ViewObject is not None:
                obj.ViewObject.Visibility = visible
        if kind == "body":
            _isolated.pop(self._doc.Name, None)
        self.refresh(force=True)

    def _find_in_window(self, obj):
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj.Document.Name, obj.Name)
        Gui.SendMsgToActiveView("ViewSelection")

    def _find_in_timeline(self, node):
        from . import timeline_ui

        if node["kind"] == "body":
            body = self._object(node)
            names = [o.Name for o, b in ops.steps(self._doc) if b is body]
            w = timeline_ui.widget()
            if w is not None and names:
                w.refresh()
                w.select(names)
            return
        timeline_ui.find(node["object"])

    def _look_at(self, sketch):
        view = Gui.ActiveDocument.ActiveView
        view.setCameraOrientation(sketch.getGlobalPlacement().Rotation)
        if sketch.ViewObject is not None and sketch.ViewObject.Visibility:
            self._find_in_window(sketch)
        else:
            view.fitAll()

    def _create_sketch(self, plane):
        if not commands.finish_open_dialog():
            return
        body = ops.body_of(plane)
        if body is not None:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(plane.Document.Name, plane.Name)
        Gui.runCommand("SciForge_NewSketch")

    # -- find ------------------------------------------------------------------------
    def find(self, name):
        """Show and select the row of an object (Find in Browser from the timeline)."""
        self.refresh(force=True)
        if self._doc is None or self._tree is None:
            return False
        obj = self._doc.getObject(name)
        body = ops.body_of(obj) if obj is not None else None
        key = core.node_for_object(self._tree, name, body.Name if body is not None else None)
        if key is None:
            return False
        for folder in core.path_to(self._tree, key) or []:
            self._expanded.add(folder)
        self.refresh(force=True)
        item = self.item_for(key)
        if item is None:
            return False
        self.clearSelection()
        item.setSelected(True)
        self.setCurrentItem(item)
        self.scrollToItem(item)
        return True


# -- Change Active Units (Document Settings > Units) -------------------------------------
class UnitsPanel:
    """Fusion's small 'Change Active Units' dialog, as a task panel."""

    last = None

    def __init__(self, doc):
        from . import taskui

        UnitsPanel.last = self
        self.doc = doc
        self._closed = False
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Change Active Units")
        self.form.setWindowIcon(ui_icon("units"))
        layout = QtWidgets.QFormLayout(self.form)
        self.combo = QtWidgets.QComboBox()
        self.combo.setObjectName("SciForgeUnitType")
        current = units(doc)
        for short, long, _index in core.UNITS:
            self.combo.addItem(long, short)
        self.combo.setCurrentIndex([u[0] for u in core.UNITS].index(current))
        layout.addRow("Unit Type", self.combo)
        self.default = QtWidgets.QCheckBox("Set as Default")
        self.default.setObjectName("SciForgeUnitDefault")
        layout.addRow(self.default)
        taskui.set_current(self)

    def getStandardButtons(self):
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return getattr(buttons, "value", buttons)

    def accept(self):
        try:
            short = self.combo.currentData()
            schema = [u[2] for u in core.UNITS if u[0] == short][0]
            set_units(self.doc, schema, self.default.isChecked())
        except Exception as exc:
            warn("units: %s" % exc)
        return self._close()

    def reject(self):
        return self._close()

    def finish(self):
        self.accept()

    def _close(self):
        from . import taskui

        self._closed = True
        if taskui._OPEN["dialog"] is self:
            taskui._OPEN["dialog"] = None
        Gui.Control.closeDialog()
        w = widget()
        if w is not None:
            w.refresh(force=True)
        return True


def set_units(doc, schema, as_default=False):
    """Units of a design (FreeCAD keeps them per document since 1.0)."""
    names = doc.getEnumerationsOfProperty("UnitSystem")
    doc.UnitSystem = names[schema]
    App.Units.setSchema(schema)
    if as_default:
        App.ParamGet("User parameter:BaseApp/Preferences/Units").SetInt("UserSchema", schema)
    try:
        Gui.updateGui()
    except Exception:
        pass


def open_units_panel():
    doc = App.ActiveDocument
    if doc is None or not commands.finish_open_dialog():
        return None
    panel = UnitsPanel(doc)
    Gui.Control.showDialog(panel)
    return panel


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


def find(name):
    w = widget()
    if w is None:
        return False
    try:
        return w.find(name)
    except Exception as exc:
        warn("browser: %s" % exc)
        return False
