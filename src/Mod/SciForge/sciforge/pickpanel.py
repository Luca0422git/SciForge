# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dialog base of SciForge commands that pick faces of a body and preview the result
on it: Shell and Draft (shell_ui.py, draft_ui.py).

Picking works like inside a Fusion command: a click on a face adds it, a click on a
picked face drops it (no Ctrl needed), a click on empty space keeps the picks. Only what
the command can use lights up under the mouse. While the dialog is open, the part
before the step is shown see-through (its picked faces highlighted, still clickable)
and the result is shown solid inside it; nothing about that look is stored in the
document or the undo history.

Keys, like Fusion: Esc cancels, Enter is OK (also with the mouse over the 3D view),
Ctrl+Z cancels the step being made (preview.UndoCancels, which also closes the dialog
when the document is closed under it), Delete does nothing (it would delete the part the
picks belong to). Problems are shown in the dialog, never in the Report view.
"""
import time

import FreeCADGui as Gui

from . import commands, handles3d, hole_common, log, preview, warn
from .compat import QtCore, QtWidgets
from .taskui import Panel

GHOST = 75  # transparency (%) of the part before the step while the preview is shown
PRESSED = {"time": 0.0}  # when an Arrow was last pressed (it may be rebuilt right after)
HANDLE_CLICK_S = 0.6  # a pick this soon after pressing a handle is the handle's click
GREEDY = 1  # FreeCAD selection style where a click toggles a pick, like in Fusion's commands
NORMAL = 0


def alive(obj):
    return hole_common.alive(obj)


def nodes(root, type_name):
    """Every Coin node of a type below `root` (pivy)."""
    from pivy import coin

    search = coin.SoSearchAction()
    search.setType(getattr(coin, type_name).getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL)
    search.setSearchingAll(True)
    search.apply(root)
    paths = search.getPaths()
    return [paths[i].getTail() for i in range(paths.getLength())]


class Looks:
    """Field changes on Coin nodes, remembered so restore() puts every old value back.
    The nodes belong to FreeCAD's view providers, which may delete them (when a recompute
    rebuilds a part's display): a Coin reference keeps each one alive until restore(),
    because writing to a deleted node crashes FreeCAD."""

    def __init__(self):
        self.saved = []  # (node, field name, old value or values)
        self.tags = set()
        self.held = []

    def done(self, tag):
        """True if `tag` was applied already (and marks it applied)."""
        if tag in self.tags:
            return True
        self.tags.add(tag)
        return False

    def set(self, node, field, value):
        if not any(node is n for n in self.held):
            node.ref()
            self.held.append(node)
        fld = getattr(node, field)
        if hasattr(fld, "getNum"):  # a multi-value field (per-face colours)
            old = [fld[i] for i in range(fld.getNum())]
        else:
            old = fld.getValue()
        self.saved.append((node, field, old))
        fld.setValue(value)

    def restore(self):
        for node, field, old in reversed(self.saved):
            try:
                fld = getattr(node, field)
                if isinstance(old, list):
                    fld.setValues(0, len(old), old)
                    fld.setNum(len(old))
                else:
                    fld.setValue(old)
            except Exception:
                pass
        for node in self.held:
            try:
                node.unref()
            except Exception:
                pass
        self.held = []
        self.saved = []
        self.tags = set()


class _Observer:
    """Selection events only queue work; the panel handles them a moment later, outside
    FreeCAD's click handling (feature guide rule 2)."""

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


def show_tip(body):
    """FreeCAD draws a body through its Tip, and a new feature hides the one before it; a
    step removed by code (a cancelled preview) could leave the part looking empty."""
    if body is None or not alive(body):
        return
    tip = body.Tip
    if tip is None:
        return
    try:
        if tip.ViewObject is not None:
            tip.ViewObject.Visibility = True
    except Exception:
        pass


def selection_entries(doc=None):
    """[(object, short element name, picked point or None)] of the selection; "" for a
    whole object. Only objects of `doc` (a click in another open design is no pick)."""
    found = []
    for obj, short, point in hole_common.picks():
        try:
            if doc is not None and obj.Document.Name != doc.Name:
                continue
        except Exception:
            continue
        found.append((obj, short, point))
    return found


def match_face(base, obj, short):
    """Name of the face of `base` that face `short` of `obj` (another step of the same
    body, e.g. picked before the command started) is, matched by its geometry."""
    if obj is base:
        return short
    try:
        item = obj.Shape.getElement(short)
    except Exception:
        return None
    for i, face in enumerate(base.Shape.Faces, start=1):
        if face.isSame(item) or (
            abs(face.Area - item.Area) < 1e-6 * max(1.0, item.Area)
            and (face.CenterOfMass - item.CenterOfMass).Length < 1e-5
        ):
            return "Face%d" % i
    return None


class PickPanel(Panel):
    """Base dialog: subclasses set self.body / self.base / self.target, build their
    fields, call start_picking() and implement:
      allow(obj, short)             may this be picked / light up?
      picks_changed(added, dropped) the user clicked; [(obj, short, point)]; True if the
                                    picks changed
      shown()                       [(obj, [element names])] FreeCAD shows selected
      _preview()                    rebuild the preview (called from schedule())
    """

    def __init__(self, doc, transaction):
        super().__init__(doc, transaction)
        self.body = None
        self.base = None
        self.target = None
        self.editing = False
        self.error = None
        self.view = None
        self.observer = None
        self.gate = None
        self._style = None
        self._shown = []  # [(object name, short)] put into FreeCAD's selection by _sync
        self._cleared = False
        self._syncing = False
        self._looks = Looks()
        self._ghost = False
        self._held = []
        self._later = {}  # what later steps use (follow.py), remembered when picking starts
        self._doc_name = doc.Name
        self._events = QtCore.QTimer()
        self._events.setSingleShot(True)
        self._events.setInterval(30)
        self._events.timeout.connect(self._process_selection)
        self._hint = QtCore.QTimer()
        self._hint.setSingleShot(True)
        self._hint.setInterval(450)
        self._hint.timeout.connect(self._compute_hint)
        self._guards = []
        try:
            self._guards = [
                preview.EscapeCancels(self),
                preview.UndoCancels(self),
                preview.EnterFinishes(self),
            ]
        except Exception as exc:
            warn("%s: keys unavailable: %s" % (self.title, exc))

    # -- starting -----------------------------------------------------------------------
    def start_picking(self):
        """Observer, selection filter, toggling clicks, Delete held, base shown."""
        self.prepare_display()
        Gui.Selection.clearSelection()
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        self.gate = hole_common.install_gate(self)
        try:
            self._style = NORMAL
            Gui.Selection.setSelectionStyle(GREEDY)
        except Exception:
            self._style = None
        try:
            self.view = Gui.ActiveDocument.ActiveView
        except Exception:
            self.view = None
        self._hold_delete(True)
        self._sync()

    def _hold_delete(self, hold):
        """The picks are a real FreeCAD selection: the Delete key would try to delete the
        part they belong to (with a pop-up) and close this dialog's undo step. While the
        dialog is open the key does nothing (typing in a field still works)."""
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
            warn("%s: Delete key: %s" % (self.title, exc))

    # -- the picks ----------------------------------------------------------------------
    def allow(self, obj, short):
        return True

    def picks_changed(self, added, dropped):
        return False

    def shown(self):
        return []

    def _sync(self):
        """Make FreeCAD's selection show exactly the picks. What is remembered as shown is
        read back from the selection: an entry FreeCAD did not take (its selection filter
        said no) must not look like a pick the user clicked away a moment later."""
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            for obj, names in self.shown():
                if not alive(obj):
                    continue
                names = [n for n in names if n]
                try:
                    if names:
                        Gui.Selection.addSelection(obj, names)
                    else:
                        Gui.Selection.addSelection(obj)
                except Exception:
                    continue
            self._shown = [(obj.Name, short) for obj, short, _p in selection_entries(self.doc)]
        finally:
            self._syncing = False

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
            now = selection_entries(self.doc)
            keys = [(obj.Name, short) for obj, short, _p in now]
            dropped = []
            if not cleared:  # a pick that is no longer selected was clicked again
                for name, short in self._shown:
                    if (name, short) not in keys:
                        obj = self.doc.getObject(name)
                        if obj is not None:
                            dropped.append((obj, short, None))
            added = [e for e, k in zip(now, keys) if k not in self._shown]
            changed = False
            if self.handles_busy():
                added = dropped = []  # the press was on a handle: no pick (it is put back)
            if added or dropped:
                changed = self.picks_changed(added, dropped)
            self._sync()
            if changed:
                self.schedule()
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    # -- handles -------------------------------------------------------------------------
    def live_handles(self):
        """The drag handles / clickable arrows shown now (self.arrows by default)."""
        found = []
        for item in getattr(self, "arrows", None) or []:
            found.append(item[0] if isinstance(item, tuple) else item)
        return [x for x in found if x is not None]

    def handles_busy(self):
        """True while a handle is pressed or was just let go: FreeCAD also takes that click
        as a pick of the face behind the handle, which must not count. Also when the
        handle pressed was rebuilt since (a click on the Draft arrow flips it and makes a
        new arrow before the click's pick is looked at)."""
        if time.time() - PRESSED["time"] < HANDLE_CLICK_S:
            return True
        for handle in self.live_handles():
            try:
                if handle.busy():
                    return True
            except Exception:
                continue
        return False

    # -- display -------------------------------------------------------------------------
    # Nothing here changes a document or view property: FreeCAD records those in the undo
    # history. PartDesign shows one feature of a body at a time; makeTemporaryVisible()
    # shows or hides one without touching its Visibility, and the see-through look is set
    # on the Coin nodes.
    def _features(self):
        if self.body is None or not alive(self.body):
            return []
        return [
            o
            for o in self.body.Group
            if o.isDerivedFrom("PartDesign::Feature") and getattr(o, "ViewObject", None)
        ]

    def prepare_display(self):
        """Show the part before the step (the timeline rolled back to it while picking)."""
        if self.base is None:
            return
        for obj in self._features():
            if obj is not self.base:
                obj.ViewObject.makeTemporaryVisible(False)
        self.base.ViewObject.makeTemporaryVisible(True)

    def show_preview(self, on):
        """on: the result solid (not clickable) with the part before it see-through around
        it, so its faces stay clickable and the picks stay highlighted. off: just the part
        before the step."""
        if self.base is None or not alive(self.base):
            return
        if not alive(self.target) or self.target.ViewObject is None:
            on = False
        try:
            if on:
                self.target.ViewObject.makeTemporaryVisible(True)
                self.base.ViewObject.makeTemporaryVisible(True)
                if not self._looks.done("preview:" + self.target.Name):
                    root = self.target.ViewObject.RootNode
                    for node in nodes(root, "SoPickStyle"):
                        self._looks.set(node, "style", node.UNPICKABLE)
                    for node in nodes(root, "SoPolygonOffset"):
                        # behind the see-through faces it shares: a picked face's highlight
                        # then shows cleanly instead of flickering stripes
                        self._looks.set(node, "factor", 3.0)
                        self._looks.set(node, "units", 8.0)
                if not self._looks.done("ghost:" + self.base.Name):
                    for node in nodes(self.base.ViewObject.RootNode, "SoMaterial"):
                        if node.getName().getString() == "ShapeMaterial":
                            self._looks.set(node, "transparency", GHOST / 100.0)
            else:
                self._looks.restore()
                if alive(self.target) and self.target.ViewObject is not None:
                    self.target.ViewObject.makeTemporaryVisible(False)
                self.base.ViewObject.makeTemporaryVisible(True)
            if on != self._ghost:
                self._ghost = on
                self._sync()  # the highlight follows the shape that is displayed now
        except Exception as exc:
            warn("%s preview display: %s" % (self.title, exc))

    def restore_display(self):
        """Undo the look changes and show what the body's Visibility properties say."""
        self._looks.restore()
        for obj in self._features():
            try:
                obj.ViewObject.makeTemporaryVisible(bool(obj.ViewObject.Visibility))
            except Exception:
                pass
        self._ghost = False

    def switch_body(self, body, base):
        """Work on another body (the first pick was on it)."""
        self.restore_display()
        self.body, self.base = body, base
        self.prepare_display()
        self.remember_later(base)

    # -- preview ------------------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            super().schedule()

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        try:
            self._preview()
        except Exception as exc:
            self.error = str(exc)
            self.show_status()

    def _preview(self):
        pass

    def quiet_recompute(self):
        preview.recompute(self.doc)

    def remember_later(self, after):
        """Remember the faces/edges the steps after `after` use (see follow.py)."""
        try:
            from . import follow

            self._later = follow.snapshot(self.body, after)
        except Exception as exc:
            self._later = {}
            warn("%s: later steps not followed: %s" % (self.title, exc))

    def follow_later(self):
        """After a preview recompute: a later step that lost its face/edge (the step
        being edited now makes it another way) gets it back, found by where it is."""
        later = getattr(self, "_later", None)
        if not later or self._closed:
            return
        try:
            from . import follow

            if follow.repair(self.doc, later):
                follow.recompute(self.doc, later, self.quiet_recompute)
        except Exception as exc:
            warn("%s: later steps not followed: %s" % (self.title, exc))

    def _compute_hint(self):
        pass

    def later_broken(self):
        """Labels of later steps of the body that no longer compute."""
        if self.body is None or not alive(self.body):
            return []
        return [
            o.Label
            for o in self.body.Group
            if o is not self.target and "Invalid" in list(getattr(o, "State", []))
        ]

    def feature(self):
        return self.target

    MESSAGE_LINES = 4

    def finish_layout(self):
        """The message area keeps room for a few lines from the start: FreeCAD's task box
        takes its height when it opens and does not grow later, so a longer explanation
        shown afterwards was cut off at the bottom of the panel."""
        super().finish_layout()
        try:
            lines = self.message.fontMetrics().lineSpacing()
            self.message.setMinimumHeight(lines * self.MESSAGE_LINES + 4)
            self.message.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        except Exception:
            pass

    def say(self, text):
        """Show (or clear) the dialog's message."""
        self.message.setText(text)

    # -- OK / Cancel ------------------------------------------------------------------------
    def finish_ok(self):
        """Close as OK (the subclass checked that the step is good)."""
        self._timer.stop()
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        preview.end_transaction(self.doc, abort=True)
        preview.recompute(self.doc)
        self._close()
        show_tip(self.body)
        return True

    def cleanup(self):
        self._closed = True
        for timer in (self._events, self._hint):
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
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        self._hold_delete(False)
        if self.gate is not None:
            hole_common.remove_gate(self.gate)
            self.gate = None
        if self._style is not None:
            try:
                Gui.Selection.setSelectionStyle(self._style)
            except Exception:
                pass
            self._style = None
        try:
            self.restore_display()
        except Exception as exc:
            warn("%s could not restore the view: %s" % (self.title, exc))
        super().cleanup()


class Arrow(handles3d.LinearHandle):
    """Fusion's blue drag arrow for these dialogs: a handles3d.LinearHandle (drawn over
    the part and grabbed by where it is on the screen, so it can be dragged also where it
    is inside the see-through part: a Coin dragger there lost the click to the part's
    face in front of it), with taskui.ArrowDragger's distance() / set_distance().

    The release of the mouse button is read from Qt: while these dialogs make clicks
    toggle picks (FreeCAD's greedy selection), FreeCAD keeps the button-up event from
    the 3D view's callbacks, and the handle stayed "held" after the first drag (every
    later click in the view was then taken as the handle's, not a pick)."""

    def _press(self, position):
        PRESSED["time"] = time.time()
        super()._press(position)

    def _poll(self):
        try:
            held = QtWidgets.QApplication.mouseButtons() & QtCore.Qt.LeftButton
            if self._drag and not held:
                self._drag = False
                self._released = True
                self._last_event = time.time()
        except Exception:
            pass
        super()._poll()

    def distance(self):
        return self.value()

    def set_distance(self, value):
        self.set_value(value)


def combo(items, current=None):
    """Drop-down; items are (label, value) or (label, value, enabled, tooltip). Disabled
    items are kinds Fusion has that SciForge cannot build yet: greyed, with the reason."""
    box = QtWidgets.QComboBox()
    for item in items:
        label, value = item[0], item[1]
        enabled = item[2] if len(item) > 2 else True
        tip = item[3] if len(item) > 3 else ""
        box.addItem(label, value)
        index = box.count() - 1
        if tip:
            box.setItemData(index, tip, QtCore.Qt.ToolTipRole)
        if not enabled:
            model_item = box.model().item(index)
            if model_item is not None:
                model_item.setEnabled(False)
    if current is not None:
        hole_common.set_combo(box, current)
    return box


def capture_selection():
    """[(object, [element names])] selected now (before finish_open_dialog clears it)."""
    return [(s.Object, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]


def reselect(selection):
    """finish_open_dialog() clears the selection; put back what the user had picked."""
    if Gui.Selection.getSelectionEx() or not selection:
        return
    for obj, subs in selection:
        try:
            if subs:
                Gui.Selection.addSelection(obj, subs)
            else:
                Gui.Selection.addSelection(obj)
        except Exception:
            pass


def selected_body():
    """The body the selection belongs to (it may not be the active one), or None."""
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        if obj.TypeId == "PartDesign::Body":
            return obj
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None and parent.TypeId == "PartDesign::Body":
            return parent
    return None


def activate(body):
    if body is not None and body is not commands.active_body():
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
