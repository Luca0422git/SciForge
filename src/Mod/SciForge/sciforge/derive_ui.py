# SPDX-License-Identifier: LGPL-2.1-or-later
"""Derive (CREATE) and Insert Derive (INSERT), Fusion-style. The document side is derive.py.

What a person does (sources in docs/sciforge/parity/misc.md):
  * INSERT > Insert Derive: pick a saved design; the Derive dialog lists that design's
    bodies, sketches, construction geometry and parameters with tick boxes (its browser);
    Place Objects At Origin; OK brings the ticked items in, linked. The timeline shows one
    Derive step. A design never saved is saved first (the source is kept by a path
    relative to it).
  * CREATE > Derive (in the source design): the same list with what is selected ticked,
    and the Destination: a New Design (opens in its own tab) or an Existing Design.
  * When the source is saved again, the Derive turns yellow in the timeline ("Out of
    date") and a note says so; right-click > Update Derive brings the changes in (later
    steps built on the derived bodies follow). Edit Feature (double-click) opens the
    dialog again: tick more, untick, Update, Break Link (the objects stay, the link goes).
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, log, taskui, ui_icon_path, warn
from . import derive, derive_core as core
from .compat import QtCore, QtWidgets

# Tests put a function(kind) -> path here instead of the file dialog.
FILE_PICKER = None
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"
INFO_STYLE = "color: #9fb3c8;"
_told = {}  # (document, Derive) -> the source stamp already reported as newer


def pick_design(title):
    """The file dialog for a design (the project folder first). None when cancelled."""
    if FILE_PICKER is not None:
        return FILE_PICKER(title)
    try:
        from . import versions_ui

        start = App.ParamGet(PREFS).GetString("LastDeriveFolder", "")
        if not start or not os.path.isdir(start):
            start = versions_ui.project_folder()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            Gui.getMainWindow(), title, start, "Designs (*.FCStd *.fcstd)"
        )
        if path:
            App.ParamGet(PREFS).SetString("LastDeriveFolder", os.path.dirname(path))
            return path
    except Exception as exc:
        warn("file dialog: %s" % exc)
    return None


def _older_version(doc):
    try:
        from . import versions_ui

        return bool(versions_ui.version_of(doc))
    except Exception:
        return False


def _save_first(doc, after, why):
    from . import versions_ui

    commands.tell(why)
    versions_ui.save_design(doc, after=after)


def _modified(doc):
    try:
        return bool(Gui.getDocument(doc.Name).Modified)
    except Exception:
        return False


# -- the dialog ----------------------------------------------------------------------------------
class DerivePanel(taskui.Panel):
    """Fusion's Derive dialog. mode "insert" (Insert Derive: into this design from `source`),
    "create" (Derive: from this design into a new or existing one) or "edit" (a Derive
    step: tick / untick, Update, Break Link)."""

    icon = "derive"
    last = None

    def __init__(self, doc, mode, source=None, master=None, preselect=()):
        self.mode = mode
        self.master = master
        self.title = {"insert": "Insert Derive", "create": "Derive", "edit": "Edit Derive"}[mode]
        super().__init__(doc, self.title)
        DerivePanel.last = self
        self.form.setWindowTitle(self.title)
        self.source = source
        self.data = None
        self.destination = None  # an existing design's file ("create" mode)
        self.guards = []
        try:
            from . import preview

            self.guards = [
                preview.EscapeCancels(self),
                preview.UndoCancels(self),
                preview.EnterFinishes(self),
            ]
        except Exception as exc:
            warn("Derive: keys unavailable: %s" % exc)
        if mode == "edit":
            self.source = derive.source_path(master)
        elif mode == "create":
            self.source = doc.FileName
        if self.source:
            self.data = derive.read_source(self.source)
        elif mode != "edit":
            raise core.DeriveError("Pick the design to derive from.")
        name = (
            master.SourceName
            if mode == "edit"
            else core.design_name(self.source if mode == "insert" else doc.FileName)
        )
        self.source_label = QtWidgets.QLabel(name)
        self.source_label.setObjectName("SciForgeDeriveSource")
        self.layout.addRow(
            QtWidgets.QLabel("Source" if mode != "create" else "Design"), self.source_label
        )
        if mode == "create":
            self._destination_rows()
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("SciForgeDeriveTree")
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(220)
        self.layout.addRow(self.tree)
        self.origin = QtWidgets.QCheckBox("Place Objects At Origin")
        self.origin.setObjectName("SciForgeDeriveAtOrigin")
        self.origin.setToolTip(
            "Each object at its own component's origin instead of where it is in the source"
        )
        self.origin.setChecked(bool(master.PlaceAtOrigin) if master is not None else False)
        self.layout.addRow(self.origin)
        self.state_label = QtWidgets.QLabel("")
        self.state_label.setObjectName("SciForgeDeriveState")
        self.state_label.setWordWrap(True)
        self.update_button = None
        self.break_button = None
        if mode == "edit":
            self.layout.addRow(self.state_label)
            row = QtWidgets.QWidget()
            box = QtWidgets.QHBoxLayout(row)
            box.setContentsMargins(0, 0, 0, 0)
            self.update_button = QtWidgets.QPushButton("Update")
            self.update_button.setObjectName("SciForgeDeriveUpdate")
            self.update_button.setToolTip("Bring in what was saved in the source since")
            self.update_button.clicked.connect(lambda: self._guarded(self.update_now))
            self.break_button = QtWidgets.QPushButton("Break Link")
            self.break_button.setObjectName("SciForgeDeriveBreak")
            self.break_button.setToolTip(
                "Keep the derived objects as they are; they never follow the source again"
            )
            self.break_button.clicked.connect(lambda: self._guarded(self.break_now))
            box.addWidget(self.update_button)
            box.addWidget(self.break_button)
            self.layout.addRow(row)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet(INFO_STYLE)
        self.layout.addRow(self.info)
        self.finish_layout()
        self._fill(preselect)
        self._show_state()
        self.tree.itemChanged.connect(lambda *_: self._guarded(self._ticks_changed))

    # -- rows ----------------------------------------------------------------------------
    def _destination_rows(self):
        self.dest_combo = QtWidgets.QComboBox()
        self.dest_combo.setObjectName("SciForgeDeriveDestination")
        self.dest_combo.addItems(["New Design", "Existing Design"])
        self.dest_combo.currentIndexChanged.connect(lambda *_: self._guarded(self._dest_changed))
        self.layout.addRow(QtWidgets.QLabel("Destination"), self.dest_combo)
        self.dest_label = QtWidgets.QLabel("A new design in its own tab")
        self.dest_label.setObjectName("SciForgeDeriveDestinationFile")
        self.dest_button = QtWidgets.QPushButton("...")
        self.dest_button.setObjectName("SciForgeDeriveDestinationPick")
        self.dest_button.setEnabled(False)
        self.dest_button.clicked.connect(lambda: self._guarded(self._pick_destination))
        row = QtWidgets.QWidget()
        box = QtWidgets.QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.dest_label, 1)
        box.addWidget(self.dest_button)
        self.layout.addRow(row)

    def _dest_changed(self):
        existing = self.dest_combo.currentIndex() == 1
        self.dest_button.setEnabled(existing)
        if not existing:
            self.destination = None
            self.dest_label.setText("A new design in its own tab")
        elif self.destination is None:
            self.dest_label.setText("Click ... to pick the design")
            self._pick_destination()

    def _pick_destination(self):
        path = pick_design("Derive into")
        if not path:
            return
        derive.check(path, self.doc.FileName)  # the destination must not feed the source
        self.destination = path
        self.dest_label.setText(core.design_name(path))
        self.message.setText("")

    def _fill(self, preselect):
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            ticked = set(self.master.Items) if self.master is not None else set(preselect)
            if self.data is not None:
                rows = self.data["rows"]
            else:  # the source is gone: what this Derive took, greyed
                labels = core.result_map(self.master.ItemLabels)
                rows = []
                for key in self.master.Items:
                    kind, name = core.parse_item(key)
                    rows.append({"kind": kind, "name": name, "label": labels.get(key) or name})
            for kind, title, members in core.tree(rows):
                group = QtWidgets.QTreeWidgetItem(self.tree, [title])
                group.setFlags(
                    group.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsAutoTristate
                )
                for row in members:
                    key = core.item_key(kind, row["name"])
                    item = QtWidgets.QTreeWidgetItem(group, [core.row_text(row)])
                    item.setData(0, QtCore.Qt.UserRole, key)
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(
                        0, QtCore.Qt.Checked if key in ticked else QtCore.Qt.Unchecked
                    )
                    if self.data is None or self.master is not None and self.master.LinkBroken:
                        item.setDisabled(True)
                group.setExpanded(True)
            if not rows:
                QtWidgets.QTreeWidgetItem(self.tree, ["(nothing to derive: no bodies yet)"])
        finally:
            self.tree.blockSignals(False)

    def ticked(self):
        keys = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == QtCore.Qt.Checked:
                    keys.append(item.data(0, QtCore.Qt.UserRole))
        return [k for k in keys if k]

    def item_for(self, key):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                if group.child(j).data(0, QtCore.Qt.UserRole) == key:
                    return group.child(j)
        return None

    def set_ticked(self, key, on=True):
        item = self.item_for(key)
        if item is not None:
            item.setCheckState(0, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
        return item is not None

    def _ticks_changed(self):
        keys = self.ticked()
        self.message.setText("")
        self.info.setText("Brings in %s." % core.summary(keys) if keys else "")

    def _show_state(self):
        if self.mode != "edit":
            name = core.design_name(self.source if self.mode == "insert" else self.doc.FileName)
            self.info.setText(
                "Tick what to bring in. It stays linked to %s: when %s is saved again, the "
                "Derive shows that it is out of date." % (name, name)
            )
            return
        current = derive.state(self.master)
        self.state_label.setText(core.state_words(current, self.master.SourceName))
        broken = bool(self.master.LinkBroken)
        if self.update_button is not None:
            self.update_button.setEnabled(current == core.NEWER and self.data is not None)
        if self.break_button is not None:
            self.break_button.setEnabled(not broken)
        self.origin.setEnabled(self.data is not None and not broken)

    def _guarded(self, fn):
        if getattr(self, "_closed", False):
            return
        try:
            fn()
        except core.DeriveError as exc:
            self.message.setText("⚠ %s" % exc)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            self.message.setText("⚠ %s" % exc)

    # -- edit actions -----------------------------------------------------------------------
    def update_now(self):
        gone = derive.update(self.master, self.data)
        self.doc.recompute()
        _told.pop((self.doc.Name, self.master.Name), None)
        self._show_state()
        self.info.setText(
            "Updated from %s." % self.master.SourceName
            + (" Some items are no longer there and kept their last shape." if gone else "")
        )
        _refresh()

    def break_now(self):
        derive.break_link(self.master)
        self._fill(())
        self._show_state()
        self.info.setText("The derived objects stay; they no longer follow the source.")
        _refresh()

    # -- OK / Cancel ------------------------------------------------------------------------
    def feature(self):
        return None

    def accept(self):
        if getattr(self, "_closed", False):
            return True
        try:
            if self.mode == "insert":
                done = self._accept_insert()
            elif self.mode == "create":
                done = self._accept_create()
            else:
                done = self._accept_edit()
        except core.DeriveError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            self.message.setText("⚠ %s" % exc)
            return False
        if not done:
            return False
        result = super().accept()
        _refresh()
        return result

    def _keys_or_say(self):
        keys = self.ticked()
        if not keys:
            raise core.DeriveError(
                "Tick at least one body, sketch, construction object or parameter."
            )
        return keys

    def _accept_insert(self):
        from . import components

        keys = self._keys_or_say()
        body = commands.find_body()
        master = derive.derive(
            self.doc,
            self.data,
            keys,
            self.origin.isChecked(),
            target_body=body,
            component=components.active_component(self.doc),
        )
        self.doc.recompute()
        commands.tell("Derived %s from %s." % (core.summary(keys), master.SourceName))
        return True

    def _accept_create(self):
        keys = self._keys_or_say()
        if self.dest_combo.currentIndex() == 1:
            if not self.destination:
                raise core.DeriveError("Pick the existing design to derive into (...).")
            target = _open_design(self.destination)
        else:
            target = App.newDocument("Design")
            target.Label = "%s Derive" % core.design_name(self.doc.FileName)
        target.openTransaction("Derive")
        try:
            master = derive.derive(target, self.data, keys, self.origin.isChecked())
            target.recompute()
        except Exception:
            target.abortTransaction()
            raise
        target.commitTransaction()
        name = target.Name
        QtCore.QTimer.singleShot(0, lambda: _show_design(name))
        commands.tell("Derived %s into %s." % (core.summary(keys), target.Label or target.Name))
        log("derive from %s into %s (%s)" % (master.SourceName, target.Name, master.Name))
        return True

    def _accept_edit(self):
        master = self.master
        if master.LinkBroken or self.data is None:
            return True
        added, removed, _kept = core.plan_edit(master.Items, self.ticked())
        if not self.ticked():
            raise core.DeriveError(
                "A Derive needs at least one item. To remove it, delete it in the timeline."
            )
        if removed:
            derive.remove_items(master, removed)
        if self.origin.isChecked() != bool(master.PlaceAtOrigin):
            derive.set_place_at_origin(master, self.origin.isChecked(), self.data)
        if added:
            from . import components

            derive.build(
                master,
                self.data,
                added,
                target_body=commands.find_body(),
                component=components.active_component(self.doc),
            )
        self.doc.recompute()
        return True

    def reject(self):
        result = super().reject()
        _refresh()
        return result

    def cleanup(self):
        for guard in self.guards:
            try:
                guard.remove()
            except Exception:
                pass
        self.guards = []
        super().cleanup()


def _open_design(path):
    for name in App.listDocuments():
        doc = App.getDocument(name)
        if doc.FileName and os.path.normcase(os.path.abspath(doc.FileName)) == os.path.normcase(
            os.path.abspath(path)
        ):
            return doc
    return App.openDocument(path)


def _show_design(name):
    try:
        if name in App.listDocuments():
            App.setActiveDocument(name)
            Gui.setActiveDocument(name)
            gdoc = Gui.getDocument(name)
            if gdoc is not None and gdoc.ActiveView is not None:
                gdoc.ActiveView.viewIsometric()
                gdoc.ActiveView.fitAll()
    except Exception as exc:
        warn("derive: showing the design: %s" % exc)


def _refresh():
    for module, fn in (("browser_ui", "widget"), ("timeline_ui", None)):
        try:
            mod = __import__("sciforge." + module, fromlist=[module])
            if fn == "widget":
                w = mod.widget()
                if w is not None:
                    w.refresh(force=True)
            else:
                getattr(mod, "refresh", lambda *a: None)()
        except Exception:
            pass


def _show_panel(panel_class, doc, *args, **kwargs):
    try:
        panel = panel_class(doc, *args, **kwargs)
    except core.DeriveError as exc:
        _abort(doc)
        commands.tell(str(exc))
        return None
    except Exception as exc:
        _abort(doc)
        warn("Derive could not start: %s" % exc)
        commands.tell("Derive could not start: %s" % exc)
        return None
    try:
        Gui.Control.showDialog(panel)
    except Exception as exc:
        try:
            panel.reject()
        except Exception:
            _abort(doc)
        warn("Derive: %s" % exc)
        return None
    return panel


def _abort(doc):
    try:
        doc.abortTransaction()
        App.closeActiveTransaction(True)
    except Exception:
        pass
    current = taskui._OPEN.get("dialog")
    if current is not None and getattr(current, "doc", None) is doc:
        taskui.set_current(None)


# -- starting the commands ------------------------------------------------------------------------
def insert_derive(path=None):
    """INSERT > Insert Derive."""
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("Design")
    if _older_version(doc):
        commands.tell("This is an older version opened read-only: nothing can be derived into it.")
        return None
    if not doc.FileName:
        _save_first(
            doc,
            lambda: insert_derive(path),
            "Save the design first: the design it derives from is kept relative to this file.",
        )
        return None
    if path is None:
        path = pick_design("Insert Derive")
        if not path:
            return None
    if not os.path.isfile(path):
        commands.tell("The design %s was not found." % path)
        return None
    try:
        derive.check(doc.FileName, path)
    except core.DeriveError as exc:
        commands.tell(str(exc))
        return None
    return _show_panel(DerivePanel, doc, "insert", source=path)


def _preselected(doc):
    keys = []
    try:
        for sel in Gui.Selection.getSelectionEx(doc.Name):
            obj = sel.Object
            body = bodies.body_of(obj)
            if obj.TypeId == "Sketcher::SketchObject":
                keys.append(core.item_key("sketch", obj.Name))
            elif obj.TypeId in derive.DATUM_TYPES:
                keys.append(core.item_key("construction", obj.Name))
            elif body is not None:
                keys.append(core.item_key("body", body.Name))
    except Exception:
        pass
    return list(dict.fromkeys(keys))


def create_derive():
    """CREATE > Derive (from the design that is open)."""
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        commands.tell("Open the design to derive from first.")
        return None
    if _older_version(doc):
        commands.tell("Open the design itself (not an older version) to derive from it.")
        return None
    if not doc.FileName or _modified(doc):
        _save_first(
            doc,
            create_derive,
            "Save the design first: Derive takes the saved design, as Fusion does.",
        )
        return None
    picked = _preselected(doc)
    return _show_panel(DerivePanel, doc, "create", preselect=picked)


def edit_derive(master):
    if not commands.finish_open_dialog():
        return None
    return _show_panel(DerivePanel, master.Document, "edit", master=master)


def update_derive(master):
    """Right-click > Update Derive (one undo step)."""
    try:
        current = derive.state(master)
        if current == core.UP_TO_DATE:
            commands.tell("%s is up to date with %s." % (master.Label, master.SourceName))
            return False
        if current != core.NEWER:
            commands.tell(core.state_words(current, master.SourceName))
            return False
        if not commands.finish_open_dialog():
            return False
        doc = master.Document
        doc.openTransaction("Update Derive")
        try:
            gone = derive.update(master)
            doc.recompute()
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        _told.pop((doc.Name, master.Name), None)
        commands.tell(
            "%s updated from %s%s."
            % (master.Label, master.SourceName, " (some items are gone there)" if gone else "")
        )
        _refresh()
        return True
    except core.DeriveError as exc:
        commands.tell(str(exc))
    except Exception as exc:
        warn("Update Derive: %s" % exc)
        commands.tell("Update Derive did not work: %s" % exc)
    return False


def break_derive_link(master):
    try:
        if master.LinkBroken:
            commands.tell("%s no longer follows %s already." % (master.Label, master.SourceName))
            return False
        if not commands.finish_open_dialog():
            return False
        doc = master.Document
        doc.openTransaction("Break Link")
        derive.break_link(master)
        doc.commitTransaction()
        commands.tell(
            "%s keeps its objects; they no longer follow %s." % (master.Label, master.SourceName)
        )
        _refresh()
        return True
    except Exception as exc:
        warn("Break Link: %s" % exc)
    return False


# -- out of date: the source saved again ----------------------------------------------------------
def check_doc(doc, tell=True):
    """Mark every Derive of `doc` whose source changed or went missing (the timeline turns it
    yellow, with the reason) and say so once per new version. Returns {name: state}."""
    found = {}
    for master in derive.masters(doc):
        try:
            current = derive.state(master)
            found[master.Name] = current
            note = getattr(master, derive.WARNING, "") or ""
            mine = note.startswith("Out of date") or note.startswith("The source design")
            if current in (core.NEWER, core.MISSING):
                derive.set_warning(master, core.state_words(current, master.SourceName))
                key = (doc.Name, master.Name)
                if (
                    current == core.NEWER
                    and tell
                    and _told.get(key) != current + _stamp_now(master)
                ):
                    _told[key] = current + _stamp_now(master)
                    commands.tell(
                        "%s is out of date: %s was saved again. Right-click it in the "
                        "timeline > Update Derive." % (master.Label, master.SourceName)
                    )
            elif mine:
                derive.set_warning(master, "")
        except Exception as exc:
            warn("derive check %s: %s" % (master.Label, exc))
    return found


def _stamp_now(master):
    path = derive.source_path(master)
    try:
        st = os.stat(path)
        return "%s|%s" % (st.st_mtime, st.st_size)
    except Exception:
        return ""


def check_all(tell=True):
    for name in list(App.listDocuments()):
        try:
            doc = App.getDocument(name)
            if getattr(doc, "Restoring", False):
                continue
            check_doc(doc, tell)
        except Exception as exc:
            warn("derive check: %s" % exc)


class _Watch:
    """A design opened: its Derives checked. A design saved: Derives of other open designs
    that read it are checked (Fusion's out-of-date notice); its own Derives keep their
    source's path relative to the new file."""

    def slotCreatedDocument(self, doc):
        try:
            name = doc.Name
            QtCore.QTimer.singleShot(1500, lambda: _check_named(name))
        except Exception:
            pass

    def slotStartSaveDocument(self, doc, filename):
        try:
            for master in derive.masters(doc):
                derive.set_relative(master, filename)
        except Exception as exc:
            warn("derive: keeping the source path: %s" % exc)

    def slotFinishSaveDocument(self, doc, filename):
        try:
            QtCore.QTimer.singleShot(300, lambda: check_all(True))
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        self._quiet_check(doc)

    def slotRedoDocument(self, doc):
        self._quiet_check(doc)

    def _quiet_check(self, doc):
        """An undo / redo of an Update: the yellow note follows (nothing is said)."""
        try:
            if not derive.masters(doc):
                return
            name = doc.Name
            QtCore.QTimer.singleShot(200, lambda: _check_named(name, False))
        except Exception:
            pass


def _check_named(name, tell=True):
    try:
        if name in App.listDocuments():
            doc = App.getDocument(name)
            if getattr(doc, "Restoring", False):
                QtCore.QTimer.singleShot(500, lambda: _check_named(name, tell))
                return
            if derive.masters(doc):
                check_doc(doc, tell)
                _refresh()
    except Exception as exc:
        warn("derive check: %s" % exc)


_STATE = {"watch": None, "app": False, "timer": None}


def _app_state(state):
    try:
        if state == QtCore.Qt.ApplicationActive:
            timer = _STATE["timer"]
            if timer is None:
                timer = QtCore.QTimer()
                timer.setSingleShot(True)
                timer.setInterval(400)
                timer.timeout.connect(lambda: check_all(True))
                _STATE["timer"] = timer
            timer.start()
    except Exception as exc:
        warn("derive check: %s" % exc)


def install_watch():
    if not App.GuiUp:
        return
    if _STATE["watch"] is None:
        _STATE["watch"] = _Watch()
        App.addDocumentObserver(_STATE["watch"])
    if not _STATE["app"]:
        try:
            QtWidgets.QApplication.instance().applicationStateChanged.connect(_app_state)
            _STATE["app"] = True
        except Exception as exc:
            warn("derive: %s" % exc)


# -- commands ------------------------------------------------------------------------------------
class _Command:
    text = ""
    tip = ""
    icon = "derive"

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return True

    def Activated(self):
        try:
            self.run()
        except core.DeriveError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("%s failed: %s" % (self.text, exc))

    def run(self):
        pass


class DeriveCommand(_Command):
    text = "Derive"
    tip = (
        "Bodies, sketches, planes and parameters of this design into a new or existing "
        "design, linked: they update when this design is saved again"
    )

    def run(self):
        create_derive()


class InsertDeriveCommand(_Command):
    text = "Insert Derive"
    tip = (
        "Bodies, sketches, planes and parameters of another saved design into this one, "
        "linked: they update when that design is saved again"
    )

    def run(self):
        insert_derive()


def _selected_master():
    for sel in Gui.Selection.getSelectionEx():
        if derive.is_derive(sel.Object):
            return sel.Object
    doc = App.ActiveDocument
    found = derive.masters(doc) if doc is not None else []
    return found[0] if len(found) == 1 else None


class UpdateDerivesCommand(_Command):
    text = "Update Derives"
    tip = "Bring in what was saved in the source designs of this design's out-of-date Derives"

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        doc = App.ActiveDocument
        late = [m for m in derive.masters(doc) if derive.state(m) == core.NEWER]
        if not late:
            commands.tell("Every Derive of this design is up to date.")
            return
        for master in late:
            update_derive(master)


def edit_step(obj):
    return edit_derive(obj)


COMMANDS = {
    "SciForge_Derive": DeriveCommand,
    "SciForge_InsertDerive": InsertDeriveCommand,
    "SciForge_UpdateDerives": UpdateDerivesCommand,
}
EDITORS = {"SciForge::" + derive.TYPE: edit_step}
# Extra entries of the timeline's right-click menu for a Derive step.
MENU_EXTRAS = {
    "SciForge::"
    + derive.TYPE: [
        (
            "Update Derive",
            update_derive,
            lambda obj: not obj.LinkBroken and derive.state(obj, refresh=False) == core.NEWER,
        ),
        ("Break Link", break_derive_link, lambda obj: not obj.LinkBroken),
    ]
}

try:
    install_watch()
except Exception as _exc:  # pragma: no cover - only without a GUI
    warn("derive watch not installed: %s" % _exc)
