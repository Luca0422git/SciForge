# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Measure (key I), Fusion-style.

Click one thing (a face, an edge, a corner, a body, a construction plane / axis / point) and
the dialog shows what it measures: area, length, volume, position... Click a second one and
it also shows the minimum distance between the two, the angle (when both have a direction)
and the X / Y / Z parts of the distance; a line with the distance is drawn between the two
nearest points. A third click starts a new measurement with it; clicking a picked item again
drops it. Selection Filter: faces / edges / corners, or whole bodies. Precision: the decimals
shown. Show Snap Points: the ends, middle and centres of the edge or face under the mouse
are drawn as dots to click (centre to centre of two holes). Click a value to copy it.
Values are in the design's units. Measure changes nothing in the design (no undo step).

In a sketch (Fusion's SKETCH tab has INSPECT > Measure too) the sketch stays open: Measure
shows at the top of the sketch's panel, measures the sketch's curves and points, and Close
or Esc ends Measure only. It also ends when the sketch is finished."""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, handles3d, hole_common, log, measure, preview, taskui, ui_icon, warn
from . import ui_icon_path
from .compat import QtCore, QtGui, QtWidgets

FILTERS = [
    ("Face/Edge/Vertex", "sub", True, ""),
    ("Body", "body", True, ""),
    ("Component", "component", True, "A click picks the whole component it lands on"),
]
LINE = (0.98, 0.78, 0.25)  # the measured distance, drawn over the part
DOT = (0.98, 0.78, 0.25)
SNAP = (0.55, 0.85, 0.55)
GREEDY = 1
NORMAL = 0
# Results lists: light text on the dark panel like Fusion's (FreeCAD's task panel drew the
# items in a dark grey that could hardly be read there).
RESULTS_STYLE = (
    "QTreeWidget { color: #f5f5f5; background: #2f3540; }"
    " QTreeWidget::item { color: #f5f5f5; }"
    " QTreeWidget::item:selected { background: #56647a; color: #ffffff; }"
    " QHeaderView::section { color: #c3cad4; }"
)
IN_SKETCH_STYLE = """
#SciForgeMeasureInSketch { background: #3b4453; border: 1px solid #56606f; border-radius: 2px; }
#SciForgeMeasureInSketch QLabel[role="title"] { color: #f5f5f5; font-weight: bold;
    letter-spacing: 0.5px; padding: 6px 8px; background: #2f3643; }
"""


def editing_sketch():
    """The sketch open for editing in the active design, or None."""
    try:
        gdoc = Gui.ActiveDocument
        edit = gdoc.getInEdit() if gdoc is not None else None
        obj = edit.Object if edit is not None else None
        if obj is not None and obj.TypeId == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass
    return None


class _EscCloses(QtCore.QObject):
    """Esc while Measure is open in a sketch ends Measure (the command in progress), not
    the sketch's drawing tool or its selection: Fusion's Esc ends the active command."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        QtWidgets.QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            if (
                self.panel is not None
                and event.type() == QtCore.QEvent.KeyPress
                and event.key() == QtCore.Qt.Key_Escape
                and not event.isAutoRepeat()
                and QtWidgets.QApplication.activePopupWidget() is None
                and QtWidgets.QApplication.activeModalWidget() is None
            ):
                panel = self.panel
                self.panel = None
                QtCore.QTimer.singleShot(0, panel.close)
                return True
        except Exception:
            pass
        return False

    def remove(self):
        self.panel = None
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass


def _units(doc):
    try:
        from . import browser_ui

        return browser_ui.units(doc)
    except Exception:
        return "mm"


def _resolve(obj, sub):
    """(leaf object, element) of a gate question (FreeCAD names the Body and a path)."""
    leaf, short = obj, sub or ""
    if "." in short:
        path, short = short.rsplit(".", 1)
        try:
            inner = obj.getSubObject(path + ".", retType=1)
        except Exception:
            inner = None
        if inner is not None:
            leaf = inner
    if leaf is not None and leaf.TypeId == "PartDesign::Body" and short:
        leaf = leaf.Tip
    return leaf, short


class _Gate:
    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed or obj is None:
                return True
            leaf, short = _resolve(obj, sub)
            return bool(panel.allow(leaf, short))
        except Exception:
            return False


class _Observer:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, doc, obj, sub, pnt):
        self.panel._selection_event(False)

    def removeSelection(self, doc, obj, sub):
        self.panel._selection_event(False)

    def setSelection(self, doc):
        self.panel._selection_event(False)

    def clearSelection(self, doc):
        self.panel._selection_event(True)


class MeasurePanel:
    """The Measure dialog (a task panel with Close only: nothing to keep or undo)."""

    title = "Measure"
    last = None

    def __init__(self, doc, initial=(), sketch=None):
        self.doc = doc
        self._closed = False
        self.sketch = sketch  # the sketch open for editing Measure runs in, or None
        self.frame = None
        self._esc = None
        self._poll = None
        MeasurePanel.last = self
        self.entities = []
        self.relation = None
        self.unit = _units(doc)
        self._shown = []  # selection keys put into FreeCAD's selection by _sync
        self._cleared = False
        self._syncing = False
        self._held = []
        self._style = None
        self._hover_pos = None
        self._hover_key = None
        self.dots = None
        self.snaps = []
        self.com_dots = None
        self.view = Gui.ActiveDocument.ActiveView
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.title)
        self.form.setWindowIcon(ui_icon("measure"))
        self._build()
        self.overlay = handles3d.Overlay(self.view)
        self._events = QtCore.QTimer()
        self._events.setSingleShot(True)
        self._events.setInterval(30)
        self._events.timeout.connect(self._process_selection)
        self._hover = QtCore.QTimer()
        self._hover.setSingleShot(True)
        self._hover.setInterval(60)
        self._hover.timeout.connect(self._update_snaps)
        Gui.Selection.clearSelection()
        for obj, short, point in initial:
            self._add(obj, short, point, quiet=True)
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        self.gate = None
        if sketch is None:
            # In a sketch the sketch editor does its own picking: no gate, its own style.
            self.gate = _Gate(self)
            try:
                Gui.Selection.addSelectionGate(self.gate)
            except Exception as exc:
                warn("Measure: selection filter unavailable: %s" % exc)
                self.gate = None
            try:
                self._style = NORMAL
                Gui.Selection.setSelectionStyle(GREEDY)
            except Exception:
                self._style = None
            self._hold_delete(True)
        self.callbacks = []
        try:
            self.callbacks.append(
                ("SoLocation2Event", self.view.addEventCallback("SoLocation2Event", self._moved))
            )
        except Exception as exc:
            warn("Measure: snap points unavailable: %s" % exc)
        self._guards = []
        try:
            if sketch is None:
                self._guards = [preview.EscapeCancels(self), preview.EnterFinishes(self)]
            else:
                self._esc = _EscCloses(self)
        except Exception as exc:
            warn("Measure: keys unavailable: %s" % exc)
        self.watch = None
        try:
            self.watch = hole_common.DocumentWatch(self)
        except Exception:
            self.watch = None
        self._sync()
        self._refresh()
        self._show_com_dots()
        if sketch is None:
            taskui.set_current(self)
        else:
            self._embed()

    # -- in a sketch ---------------------------------------------------------------------------
    def _embed(self):
        """Show the dialog at the top of the open sketch's panel (above the sketch palette),
        with its own Close button; the sketch's panel stays as it is below it."""
        from . import sketch_palette

        host = sketch_palette.sketch_panel()
        if host is None:
            self.cleanup()
            raise RuntimeError("the sketch's panel is not there")
        frame = QtWidgets.QFrame()
        frame.setObjectName("SciForgeMeasureInSketch")
        frame.setStyleSheet(IN_SKETCH_STYLE)
        box = QtWidgets.QVBoxLayout(frame)
        box.setContentsMargins(0, 0, 0, 6)
        box.setSpacing(4)
        title = QtWidgets.QLabel("MEASURE")
        title.setProperty("role", "title")
        box.addWidget(title)
        box.addWidget(self.form)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 0, 8, 0)
        row.addStretch(1)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("SciForgeMeasure_close")
        close.setToolTip("End Measure (Esc); the sketch stays open")
        close.clicked.connect(self.close)
        row.addWidget(close)
        box.addLayout(row)
        host.layout().insertWidget(0, frame)
        self.frame = frame
        self._poll = QtCore.QTimer()
        self._poll.setInterval(250)
        self._poll.timeout.connect(self._still_in_sketch)
        self._poll.start()

    def _still_in_sketch(self):
        """Measure ends with the sketch it was started in (Finish Sketch, undo...)."""
        try:
            if self._closed:
                return
            gone = editing_sketch() is not self.sketch
            if not gone:
                try:
                    gone = self.frame is None or not self.frame.isVisible()
                except RuntimeError:
                    gone = True  # the sketch's panel went, and the dialog with it
            if gone:
                self.close()
        except Exception as exc:
            warn("Measure: %s" % exc)

    def entity(self, obj, short, point=None, whole_body=False):
        """measure.Entity of a pick; picks in the sketch being edited are named by the
        sketch editor (measure.sketch_entity)."""
        if self.sketch is not None and obj is self.sketch and not whole_body:
            return measure.sketch_entity(obj, short, point)
        return measure.entity(obj, short, point, whole_body=whole_body)

    # -- the dialog --------------------------------------------------------------------------
    def _build(self):
        layout = QtWidgets.QFormLayout(self.form)
        self.filter = QtWidgets.QComboBox()
        self.filter.setObjectName("SciForgeMeasure_filter")
        for label, value, enabled, tip in FILTERS:
            self.filter.addItem(label, value)
            index = self.filter.count() - 1
            if tip:
                self.filter.setItemData(index, tip, QtCore.Qt.ToolTipRole)
            if not enabled:
                item = self.filter.model().item(index)
                if item is not None:
                    item.setEnabled(False)
        self.filter.currentIndexChanged.connect(self._filter_changed)
        layout.addRow("Selection Filter", self.filter)
        self.precision = QtWidgets.QComboBox()
        self.precision.setObjectName("SciForgeMeasure_precision")
        for text in measure.PRECISIONS:
            self.precision.addItem(text)
        self.precision.setCurrentIndex(measure.DEFAULT_PRECISION)
        self.precision.currentIndexChanged.connect(self._precision_changed)
        layout.addRow("Precision", self.precision)
        self.snap = QtWidgets.QCheckBox("Show Snap Points")
        self.snap.setObjectName("SciForgeMeasure_snap")
        self.snap.toggled.connect(self._snap_toggled)
        layout.addRow(self.snap)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("SciForgeMeasure_results")
        self.tree.setStyleSheet(RESULTS_STYLE)
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumHeight(260)
        self.tree.setToolTip("Click a value to copy it")
        self.tree.itemClicked.connect(self._copy)
        layout.addRow(self.tree)
        self.restart = QtWidgets.QPushButton("Restart Selection")
        self.restart.setObjectName("SciForgeMeasure_restart")
        self.restart.clicked.connect(self._restart)
        layout.addRow(self.restart)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setObjectName("SciForgeMeasure_message")
        layout.addRow(self.message)

    def decimals(self):
        return max(0, self.precision.currentIndex())

    def mode(self):
        return self.filter.currentData() or "sub"

    def text(self, value, quantity):
        return measure.fmt(value, quantity, self.decimals(), self.unit)

    def say(self, text):
        self.message.setText(text)

    def values(self):
        """{section: {name: text}} as shown (the scenarios read it)."""
        out = {}
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            rows = {}
            for j in range(top.childCount()):
                child = top.child(j)
                rows[child.text(0)] = child.text(1)
            out[top.text(0)] = rows
        return out

    def _refresh(self):
        """Fill the results and draw the measured distance."""
        self.tree.clear()
        self.overlay.clear()
        self.relation = None
        try:
            for i, e in enumerate(self.entities):
                top = QtWidgets.QTreeWidgetItem(["Selection %d" % (i + 1), e.label])
                self.tree.addTopLevelItem(top)
                for name, value, quantity in measure.properties(e):
                    QtWidgets.QTreeWidgetItem(top, [name, self.text(value, quantity)])
                if e.kind == "point":
                    self.overlay.dot(e.point, self._dot_size(), DOT)
            if len(self.entities) == 2:
                rows, relation = measure.results(self.entities[0], self.entities[1])
                self.relation = relation
                top = QtWidgets.QTreeWidgetItem(["Results", ""])
                self.tree.addTopLevelItem(top)
                for name, value, quantity in rows:
                    QtWidgets.QTreeWidgetItem(top, [name, self.text(value, quantity)])
                a, b = relation["points"]
                self.overlay.line(a, b, LINE, 2.0)
                self.overlay.dot(a, self._dot_size(), DOT)
                self.overlay.dot(b, self._dot_size(), DOT)
                self.overlay.text((a + b) * 0.5, self.text(relation["distance"], "length"))
            self.tree.expandAll()
            self.tree.resizeColumnToContents(0)
            if not self.entities:
                self.say("Click a face, an edge, a corner or a body to measure.")
            elif len(self.entities) == 1:
                self.say("Click a second item to measure between the two.")
            else:
                self.say("")
        except measure.MeasureError as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("Measure: %s" % exc)
            self.say("⚠ %s" % exc)

    def _dot_size(self):
        try:
            body = commands.find_body()
            size = body.Shape.BoundBox.DiagonalLength if body is not None else 50.0
        except Exception:
            size = 50.0
        return max(0.3, size * 0.008)

    def _copy(self, item, column):
        try:
            if item.childCount() or not item.text(1):
                return
            QtWidgets.QApplication.clipboard().setText(item.text(1))
            commands.tell("Copied %s" % item.text(1))
        except Exception as exc:
            warn("Measure copy: %s" % exc)

    def _filter_changed(self, *_):
        try:
            if self.mode() == "component" and self.sketch is not None:
                hole_common.set_combo(self.filter, "sub")  # a sketch has no components
                self.say("Inside a sketch Measure picks its curves and points.")
                return
            self._restart()
            self._snap_toggled(self.snap.isChecked())
        except Exception as exc:
            warn("Measure filter: %s" % exc)

    def _precision_changed(self, *_):
        self._refresh()

    def _restart(self, *_):
        try:
            self.entities = []
            self._sync()
            self._refresh()
        except Exception as exc:
            warn("Measure restart: %s" % exc)

    # -- picks -------------------------------------------------------------------------------
    def allow(self, obj, short):
        if obj is None:
            return False
        key = (obj.Name, short)
        if key in self._shown:
            return True
        if self.mode() == "component":
            # a click anywhere on a component's bodies picks the component (its planes,
            # sketches and axes are no part of it to measure)
            if obj.TypeId in measure.PLANE_TYPES + measure.LINE_TYPES + measure.POINT_TYPES:
                return False
            return obj.TypeId == "App::Part" or measure.body_of(obj) is not None
        if measure.body_of(obj) is not None and obj.TypeId == "PartDesign::Body" and not short:
            return self.mode() == "body"
        if obj.TypeId in measure.PLANE_TYPES + measure.LINE_TYPES + measure.POINT_TYPES:
            return self.mode() == "sub"
        if short.startswith(("Face", "Edge", "Vertex")):
            if self.mode() == "body":
                return measure.body_of(obj) is not None or obj.TypeId != "Sketcher::SketchObject"
            return True
        if not short:  # a loose solid (not in a body)
            return self.mode() == "body"
        return False

    def _add(self, obj, short, point, quiet=False):
        if self.sketch is not None and str(short).startswith("Constraint"):
            return False  # a sketch dimension or constraint symbol: nothing to measure
        try:
            if self.mode() == "component":
                component = measure.component_of(obj)
                if component is None:
                    raise measure.MeasureError(
                        "%s is not in a component (it is at the top of the design): pick a "
                        "component's body, or use the Body filter."
                        % (getattr(measure.body_of(obj), "Label", None) or obj.Label)
                    )
                e = measure.component_entity(component)
            else:
                e = self.entity(obj, short, point, whole_body=self.mode() == "body")
        except measure.MeasureError as exc:
            if not quiet:
                self.say(str(exc))
            return False
        for old in self.entities:
            if old.key() == e.key():
                return False
        if len(self.entities) >= 2:
            self.entities = []  # Fusion: a third pick starts a new measurement
        self.entities.append(e)
        return True

    def add_snap(self, point):
        e = measure.snap_entity(point, "Snap point")
        if len(self.entities) >= 2:
            self.entities = []
        self.entities.append(e)
        self._sync()
        self._refresh()

    def _selection_event(self, cleared):
        if self._syncing or self._closed:
            return
        self._cleared = self._cleared or cleared
        self._events.start()

    def _process_selection(self):
        try:
            if self._closed:
                return
            cleared, self._cleared = self._cleared, False
            for dots in (self.dots, self.com_dots):
                if dots is not None and dots.clicked_recently():
                    self._sync()  # the dot took that click, not what is behind it
                    return
            now = [
                (obj, short, point)
                for obj, short, point in hole_common.picks()
                if obj.Document.Name == self.doc.Name
            ]
            keys = [(obj.Name, short) for obj, short, _p in now]
            changed = False
            if not cleared:
                gone = [k for k in self._shown if k not in keys]
                if gone:
                    before = len(self.entities)
                    self.entities = [e for e in self.entities if self._selection_key(e) not in gone]
                    changed = len(self.entities) != before
            for (obj, short, point), key in zip(now, keys):
                if key in self._shown:
                    continue
                if self._add(obj, short, point):
                    changed = True
            self._sync()
            if changed:
                self._refresh()
        except Exception as exc:
            warn("Measure pick: %s" % exc)

    def _selection_key(self, e):
        if e.obj is None:
            return None
        return (e.obj.Name, e.sub)

    def _sync(self):
        """FreeCAD's selection shows exactly the picked items (whole bodies in Body mode)."""
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            for e in self.entities:
                if e.obj is None or not hole_common.alive(e.obj):
                    continue
                try:
                    if e.sub:
                        Gui.Selection.addSelection(e.obj, [e.sub])
                    else:
                        Gui.Selection.addSelection(e.obj)
                except Exception:
                    continue
            self._shown = [
                (obj.Name, short)
                for obj, short, _p in hole_common.picks()
                if obj.Document.Name == self.doc.Name
            ]
        finally:
            self._syncing = False

    def _hold_delete(self, hold):
        """The picks are a real selection: Delete must not delete the part they are on."""
        try:
            if hold:
                from . import shortcuts

                for key in ("Del", "Backspace"):
                    entry = shortcuts._bound.get(shortcuts.normalise(key))
                    if entry is not None and entry[1].isEnabled():
                        entry[1].setEnabled(False)
                        self._held.append(entry[1])
            else:
                for shortcut in self._held:
                    shortcut.setEnabled(True)
                self._held = []
        except Exception as exc:
            warn("Measure: Delete key: %s" % exc)

    # -- snap points ---------------------------------------------------------------------------
    def _snap_toggled(self, on):
        try:
            if not on or self.mode() != "sub":
                self._drop_dots()
                self._hover_key = None
        except Exception as exc:
            warn("Measure snap: %s" % exc)

    def _moved(self, info):
        try:
            if self._closed or not self.snap.isChecked():
                return
            self._hover_pos = tuple(info["Position"])
            self._hover.start()
        except Exception:
            pass

    def _update_snaps(self):
        """Dots on the ends, middle and centres of the edge or face under the mouse."""
        try:
            if self._closed or not self.snap.isChecked() or self.mode() != "sub":
                return
            if self._hover_pos is None:
                return
            if self.dots is not None and self.dots.dot_at(self._hover_pos) is not None:
                return  # the mouse is on a dot: keep them
            info = self.view.getObjectInfo(self._hover_pos)
            if not info or not info.get("Object"):
                return
            obj = self.doc.getObject(info["Object"])
            short = str(info.get("Component", ""))
            if obj is None or not short.startswith(("Edge", "Face")):
                return
            key = (obj.Name, short)
            if key == self._hover_key:
                return
            self._hover_key = key
            try:
                e = self.entity(obj, short)
            except measure.MeasureError:
                return
            self.snaps = measure.snap_points(e)
            self._drop_dots()
            if self.snaps:
                dots = [(i, p, SNAP) for i, (_n, p) in enumerate(self.snaps)]
                self.dots = handles3d.PointDots(
                    self.view, dots, self._snap_picked, size=self._dot_size() * 4
                )
        except Exception as exc:
            warn("Measure snap: %s" % exc)

    def _snap_picked(self, index):
        try:
            if self._closed or index >= len(self.snaps):
                return
            self.add_snap(self.snaps[index][1])
        except Exception as exc:
            warn("Measure snap: %s" % exc)

    # -- Center of Mass markers -----------------------------------------------------------------
    def _show_com_dots(self):
        """The centre of a Center of Mass analysis can be clicked like a corner (Fusion
        measures from its centre-of-mass sign): a dot at each shown marker."""
        self._drop_com_dots()
        try:
            from . import analysis

            dots = []
            for obj in analysis.of_kind(self.doc, analysis.COM_KIND):
                vobj = obj.ViewObject
                if analysis.problem(obj) or vobj is None or not vobj.Visibility:
                    continue
                dots.append((obj.Name, App.Vector(obj.Position), DOT))
            if dots:
                self.com_dots = handles3d.PointDots(
                    self.view, dots, self._com_picked, size=self._dot_size() * 2.5
                )
        except Exception as exc:
            warn("Measure: centre of mass: %s" % exc)

    def _com_picked(self, name):
        try:
            obj = self.doc.getObject(name)
            if self._closed or obj is None:
                return
            e = measure.snap_entity(obj.Position, obj.Label)
            if len(self.entities) >= 2:
                self.entities = []
            self.entities.append(e)
            self._sync()
            self._refresh()
        except Exception as exc:
            warn("Measure: centre of mass: %s" % exc)

    def _drop_com_dots(self):
        if self.com_dots is not None:
            try:
                self.com_dots.remove()
            except Exception:
                pass
            self.com_dots = None

    def _drop_dots(self):
        if self.dots is not None:
            try:
                self.dots.remove()
            except Exception:
                pass
            self.dots = None

    # -- the document changed under the dialog ------------------------------------------------
    def document_event(self, closing):
        if closing:
            if self.sketch is not None:
                self.close()
            else:
                hole_common.abandon(self)
            return
        QtCore.QTimer.singleShot(0, self._revalidate)

    def _revalidate(self):
        """After an undo the picked items may be gone or moved: measure them again."""
        try:
            if self._closed:
                return
            fresh = []
            for e in self.entities:
                if e.obj is None:
                    fresh.append(e)
                    continue
                if not hole_common.alive(e.obj):
                    continue
                try:
                    fresh.append(self.entity(e.obj, e.sub, e.point, whole_body=e.kind == "body"))
                except measure.MeasureError:
                    continue
            self.entities = fresh
            self._sync()
            self._refresh()
            self._show_com_dots()
        except Exception as exc:
            warn("Measure: %s" % exc)

    # -- task dialog API ---------------------------------------------------------------------
    def getStandardButtons(self):
        buttons = QtWidgets.QDialogButtonBox.Close
        return getattr(buttons, "value", buttons)

    def accept(self):
        return self.close()

    def reject(self):
        return self.close()

    def finish(self):
        self.close()

    def close(self):
        if self._closed:
            return True
        self.cleanup()
        if self.sketch is not None:
            self._unembed()
            try:
                Gui.Selection.clearSelection()
            except Exception:
                pass
            log("Measure closed (the sketch stays open)")
            return True
        if taskui.current() is self:
            taskui.set_current(None)
        try:
            Gui.Control.closeDialog()
        except Exception:
            pass
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        log("Measure closed")
        return True

    def _unembed(self):
        frame, self.frame = self.frame, None
        if frame is None:
            return
        try:
            frame.hide()
            frame.setParent(None)
            frame.deleteLater()
        except RuntimeError:
            pass  # already gone with the sketch's panel

    def cleanup(self):
        self._closed = True
        if self._esc is not None:
            self._esc.remove()
            self._esc = None
        for timer in (self._events, self._hover, self._poll):
            if timer is None:
                continue
            try:
                timer.stop()
            except Exception:
                pass
        for guard in self._guards:
            try:
                guard.remove()
            except Exception:
                pass
        self._guards = []
        if self.watch is not None:
            self.watch.remove()
            self.watch = None
        for kind, callback in self.callbacks:
            try:
                self.view.removeEventCallback(kind, callback)
            except Exception:
                pass
        self.callbacks = []
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        if self.gate is not None:
            hole_common.remove_gate(self.gate)
            self.gate = None
        if self._style is not None:
            try:
                Gui.Selection.setSelectionStyle(self._style)
            except Exception:
                pass
            self._style = None
        self._hold_delete(False)
        self._drop_dots()
        self._drop_com_dots()
        try:
            self.overlay.remove()
        except Exception:
            pass


def start_in_sketch(sketch):
    """Measure in the sketch being edited, which stays open (see the module text)."""
    last = MeasurePanel.last
    if last is not None and not last._closed and last.sketch is sketch:
        last._restart()  # I again: a new measurement
        return last
    picks = [p for p in hole_common.picks(sketch.Document) if p[0] is sketch]
    panel = MeasurePanel(sketch.Document, initial=picks, sketch=sketch)
    log("Measure started in %s" % sketch.Label)
    return panel


def start():
    sketch = editing_sketch()
    if sketch is not None:
        try:
            return start_in_sketch(sketch)
        except Exception as exc:
            warn("Measure in the sketch: %s" % exc)
            return None
    picks = hole_common.picks()
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        commands.tell("Open or start a design to measure it.")
        return None
    panel = MeasurePanel(App.ActiveDocument, initial=picks)
    Gui.Control.showDialog(panel)
    log("Measure started")
    return panel


class MeasureCommand:
    def GetResources(self):
        return {
            "MenuText": "Measure",
            "ToolTip": "Measure lengths, areas, volumes, distances and angles (I)",
            "Pixmap": ui_icon_path("measure"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Measure failed to start: %s" % exc)


COMMANDS = {"SciForge_Measure": MeasureCommand}
