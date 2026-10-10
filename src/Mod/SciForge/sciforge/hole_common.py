# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieces the Hole and Thread dialogs share (hole_ui.py, thread_ui.py).

- SelectionField: Fusion's selection box (blue while it takes the clicks, x to clear).
- combo / set_combo / fill_combo: drop-downs that carry a value per entry.
- Gate: only what the dialog can use lights up under the mouse and can be picked.
- DocumentWatch: Ctrl+Z / Ctrl+Y or closing the document while the dialog is open ends
  the dialog instead of leaving it working on objects that are gone.
- on_top(): draw a handle over the part, as Fusion's manipulators are.
- picks(): what was clicked, with the clicked point.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import warn
from .compat import QtWidgets

ACTIVE_STYLE = "QPushButton { background: #1f6fbf; color: white; border: 1px solid #5aa0e6; }"


def combo(pairs, current=None):
    box = QtWidgets.QComboBox()
    for label, value in pairs:
        box.addItem(label, value)
    set_combo(box, current)
    return box


def set_combo(box, value):
    for i in range(box.count()):
        if box.itemData(i) == value:
            box.setCurrentIndex(i)
            return True
    return False


def fill_combo(box, pairs, current):
    """Replace the entries (without signals) and select `current` (else the first)."""
    box.blockSignals(True)
    try:
        box.clear()
        for label, value in pairs:
            box.addItem(label, value)
        if not set_combo(box, current) and box.count():
            box.setCurrentIndex(0)
    finally:
        box.blockSignals(False)


class SelectionField:
    """Fusion's selection box: shows what is picked, is blue while it takes the clicks in
    the 3D view (click it to make it the one), with an x to clear it."""

    def __init__(self, panel, name, empty):
        self.panel = panel
        self.name = name
        self.empty = empty
        self.widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.button = QtWidgets.QPushButton(empty)
        self.button.setCheckable(True)
        self.button.clicked.connect(self._clicked)
        self.clear = QtWidgets.QToolButton()
        self.clear.setText("✕")
        self.clear.setToolTip("Clear")
        self.clear.clicked.connect(self._cleared)
        row.addWidget(self.button, 1)
        row.addWidget(self.clear)

    def _clicked(self, *_):
        try:
            self.panel.activate(self.name)
        except Exception as exc:
            warn("selection box: %s" % exc)

    def _cleared(self, *_):
        try:
            self.panel.clear_field(self.name)
        except Exception as exc:
            warn("selection box: %s" % exc)

    def set_active(self, active):
        self.button.setChecked(active)
        self.button.setStyleSheet(ACTIVE_STYLE if active else "")

    def set_text(self, text):
        self.button.setText(text or self.empty)


def on_top(root):
    """Draw a handle over the part (Fusion's manipulators are never hidden by it)."""
    try:
        from pivy import coin

        depth = coin.SoDepthBuffer()
        depth.test.setValue(False)
        root.insertChild(depth, 0)
    except Exception:
        pass


def is_dragging(handle):
    try:
        return bool(handle.dragger.isActive.getValue())
    except Exception:
        return False


def resolve(sel_obj, name):
    """(object, short element name) for a selection entry, through "Body.Pad.Face6" paths.
    A face or edge picked on a Body is the Body's Tip's."""
    obj, short = sel_obj, name
    if "." in name:
        path, short = name.rsplit(".", 1)
        try:
            inner = sel_obj.getSubObject(path + ".", retType=1)
        except Exception:
            inner = None
        obj = inner if inner is not None else obj
    if (
        obj is not None
        and obj.TypeId == "PartDesign::Body"
        and short.startswith(("Face", "Edge", "Vertex"))
    ):
        obj = obj.Tip
    return obj, short


def picks():
    """[(object, short name, picked point or None)] of the selection (global point)."""
    found = []
    for sel in Gui.Selection.getSelectionEx():
        points = list(getattr(sel, "PickedPoints", []) or [])
        names = list(sel.SubElementNames) or [""]
        for i, name in enumerate(names):
            obj, short = resolve(sel.Object, name)
            if obj is None:
                continue
            point = App.Vector(points[i]) if i < len(points) else None
            found.append((obj, short, point))
    return found


def global_shape(obj, short):
    """Element `short` of `obj` in global coordinates (a copy), or None."""
    try:
        element = obj.Shape.getElement(short)
    except Exception:
        return None
    element = element.copy()
    try:
        parent = obj.getParentGeoFeatureGroup()
    except Exception:
        parent = None
    if parent is not None and obj.TypeId not in ("App::Plane", "App::Line"):
        place = parent.getGlobalPlacement()
        if not place.isIdentity():
            element.transformShape(place.toMatrix())
    return element


def alive(obj):
    """False for None and for objects an undo (or a closed document) took away."""
    if obj is None:
        return False
    try:
        if hasattr(obj, "isAttachedToDocument"):
            return obj.isAttachedToDocument()
        return bool(obj.Name)
    except Exception:
        return False


class Gate:
    """A selection gate: `allow(obj, element_name)` of the panel decides what lights up
    under the mouse and can be picked while the dialog is open."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed or obj is None:
                return True
            return bool(panel.allow(obj, (sub or "").split(".")[-1]))
        except Exception:
            return False


def install_gate(panel):
    try:
        gate = Gate(panel)
        Gui.Selection.addSelectionGate(gate)
        return gate
    except Exception as exc:
        warn("%s: selection filter unavailable: %s" % (panel.title, exc))
        return None


def remove_gate(gate):
    if gate is None:
        return
    gate.panel = None
    try:
        Gui.Selection.removeSelectionGate()
    except Exception:
        pass


class DocumentWatch:
    """Undo/redo or closing the document while the dialog is open (see module text)."""

    def __init__(self, panel):
        self.panel = panel
        self.name = panel.doc.Name
        App.addDocumentObserver(self)

    def slotUndoDocument(self, doc):
        self._event(doc, False)

    def slotRedoDocument(self, doc):
        self._event(doc, False)

    def slotDeletedDocument(self, doc):
        self._event(doc, True)

    def _event(self, doc, closing):
        try:
            panel = self.panel
            if panel is None or panel._closed or getattr(doc, "Name", None) != self.name:
                return
            panel.document_event(closing)
        except Exception as exc:
            warn("dialog: %s" % exc)

    def remove(self):
        self.panel = None
        try:
            App.removeDocumentObserver(self)
        except Exception:
            pass


def end_after_undo(panel):
    """Ctrl+Z / Ctrl+Y ran while the dialog was open: end it, keeping what undo did."""
    from . import log

    if panel._closed:
        return
    try:
        panel._timer.stop()
        panel.cleanup()
        if panel.doc.HasPendingTransaction:
            panel.doc.abortTransaction()
        panel._close()
        log("%s ended by undo" % panel.title)
    except Exception as exc:
        warn("%s could not end after undo: %s" % (panel.title, exc))


def abandon(panel):
    """The document is closing: let go of everything without touching it."""
    from .compat import QtCore

    try:
        panel.cleanup()
    except Exception:
        pass
    try:
        from . import taskui

        if taskui.current() is panel:
            taskui.set_current(None)
        QtCore.QTimer.singleShot(0, Gui.Control.closeDialog)
    except Exception:
        pass
