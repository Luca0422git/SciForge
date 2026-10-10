# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fillet (F) and Chamfer with Fusion's dialogs.

Picking works like inside a Fusion command:
  * click edges in the 3D view to add them, click a picked one again to drop it
    (no Ctrl needed; clicking empty space does not lose the picks);
  * click a face to round every sharp edge around it;
  * click a feature in the timeline to round the edges that feature made;
  * edges tangent to a picked edge are picked with it (Tangent Chain);
  * press F with edges already selected and the fillet starts at once.
While picking, the part before the fillet is shown see-through with the picks
highlighted, and the result is previewed solid on top. A blue arrow on the first
edge drags the radius (chamfer: the distance; two arrows for two distances).
A size that does not fit is reported in the dialog and OK waits for a fix; nothing
is printed to the Report view.

Built on PartDesign::Fillet / PartDesign::Chamfer (refined), so Press Pull's fillet
editing (presspull_core.owning_fillet) keeps working on these features.
"""
import contextlib
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import blend, commands, log, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel

GHOST = 75  # transparency (%) of the part before the blend while the preview is shown
GREEDY = 1  # FreeCAD selection style where a click toggles a pick, like in Fusion's commands
NORMAL = 0
PICK_HELP = "Click edges or faces of the part (or a feature in the timeline).\nClick a pick again to drop it."


@contextlib.contextmanager
def quiet_errors():
    """While previewing, a failing step is explained in the dialog (Fusion does that)
    instead of in the Report view, the notification pop-ups and the console."""
    muted = []
    try:
        for name in App.Console.GetObservers():
            for kind in ("Err", "Wrn"):
                try:
                    if App.Console.GetStatus(name, kind):
                        App.Console.SetStatus(name, kind, False)
                        muted.append((name, kind))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        yield
    finally:
        for name, kind in muted:
            try:
                App.Console.SetStatus(name, kind, True)
            except Exception:
                pass


def solid_base(body):
    """The feature a new fillet builds on: the body's current end, if it is a solid."""
    if body is None:
        return None
    tip = body.Tip
    if tip is None or not hasattr(tip, "Shape") or tip.Shape.isNull() or not tip.Shape.Solids:
        return None
    return tip


def _resolve(sel):
    """[(object, short element name)] of a selection entry ("" for a whole object)."""
    found = []
    subs = [s for s in sel.SubElementNames if s] or [""]
    for name in subs:
        found.append((sel.Object, name.split(".")[-1] if name else ""))
    return found


def picks_from_selection(body, info, base):
    """What is selected now, as refs on `base` (Fusion: F with edges already selected).
    Edges/faces of another step are matched by their geometry."""
    refs = []
    if base is None or info is None:
        return refs
    for sel in Gui.Selection.getSelectionEx():
        for obj, name in _resolve(sel):
            if obj is None or obj.TypeId == "PartDesign::Body":
                continue
            if not name:
                if body is not None and obj in body.Group:
                    for edge in blend.feature_edges(obj, info):
                        if edge not in refs:
                            refs.append(edge)
                continue
            if obj.Name != base.Name:
                name = _match(obj, name, info)
            if name and info.pickable(name) and name not in refs:
                refs.append(name)
    return refs


def _match(obj, name, info):
    """Name of the same edge/face in info's shape (picked on another feature's shape)."""
    try:
        item = obj.Shape.getElement(name)
    except Exception:
        return None
    if name.startswith("Edge"):
        key = blend._edge_key(item)
        for i, edge in enumerate(info.edges, start=1):
            if blend._edge_key(edge) == key:
                return "Edge%d" % i
    elif name.startswith("Face"):
        for i, face in enumerate(info.faces, start=1):
            if (
                abs(face.Area - item.Area) < 1e-6 * max(1.0, item.Area)
                and (face.CenterOfMass - item.CenterOfMass).Length < 1e-5
            ):
                return "Face%d" % i
    return None


def _combo(items, current=0):
    """Combo box; items are (label, value, enabled, tooltip). Disabled items are kinds
    Fusion has that SciForge cannot build yet: shown greyed with the reason."""
    box = QtWidgets.QComboBox()
    for label, value, enabled, tip in items:
        box.addItem(label, value)
        index = box.count() - 1
        if tip:
            box.setItemData(index, tip, QtCore.Qt.ToolTipRole)
        if not enabled:
            item = box.model().item(index)
            if item is not None:
                item.setEnabled(False)
    box.setCurrentIndex(current)
    return box


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


class _Gate:
    """Only edges/faces that can be rounded (and whole features of the body) can be picked;
    everything else does not even light up under the mouse."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel._closed or panel.base is None or obj is None:
                return True
            name = (sub or "").split(".")[-1]
            if obj.Name == panel.base.Name:
                return panel.info.pickable(name) if name else True
            if name:
                return False
            return panel._is_body_feature(obj)  # a timeline click: round the edges it made
        except Exception:
            return False


class BlendPanel(Panel):
    """Shared dialog of Fillet and Chamfer. Subclasses add their fields (_fields)."""

    kind = "fillet"
    title = "Fillet"
    icon = "fillet"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, refs=None):
        super().__init__(doc, self.title if feature is None else "Edit " + self.title)
        type(self).last = BlendPanel.last = self
        self.target = feature
        self.created = feature is None
        self.body = feature.getParentGeoFeatureGroup() if feature else commands.find_body()
        self.base = None
        self.info = None
        self.refs = []
        self.error = None
        self.options = blend.default_options(self.kind)
        self.arrows = []  # (ArrowDragger, spot, origin, direction) in global coordinates
        self.observer = None
        self.gate = False
        self._style = None
        self._shown = []  # names on base FreeCAD shows selected (the picks + chains)
        self._cleared = False
        self._syncing = False
        self._accepted = False
        self._saved = {}  # view settings to put back: (object name, property) -> value
        self._ghost = False  # the preview is shown (before-shape see-through)
        self._offset = None  # (feature, SoPolygonOffset) pushing the preview's faces back
        self.view = None
        self._keys = None
        self._bound = False
        self._events = QtCore.QTimer()
        self._events.setSingleShot(True)
        self._events.setInterval(30)
        self._events.timeout.connect(self._process_selection)
        self._hint = QtCore.QTimer()
        self._hint.setSingleShot(True)
        self._hint.setInterval(450)
        self._hint.timeout.connect(self._compute_hint)

        if feature is not None:
            self.base, self.refs = blend.refs_of(feature)
            self.options.update(blend.read(feature))
        else:
            self.base = solid_base(self.body)
        if self.base is not None and not self.base.Shape.isNull():
            self.info = blend.ShapeInfo(self.base.Shape)

        self._build()
        self.finish_layout()
        try:
            self._start(refs)
        except Exception as exc:  # never leave a half-open dialog without a reason
            self._say("⚠ %s" % exc)
            warn("%s could not start picking: %s" % (self.title, exc))

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.select_button = QtWidgets.QPushButton("Select")
        self.select_button.setIcon(ui_icon("select"))
        self.select_button.setCheckable(True)
        self.select_button.setChecked(True)
        self.select_button.setToolTip(PICK_HELP)
        self.select_button.setStyleSheet(
            "QPushButton:checked { background: #2f7fd1; color: white; border-radius: 3px; }"
        )
        self.select_button.clicked.connect(lambda *_: self.select_button.setChecked(True))
        self.clear_button = QtWidgets.QToolButton()
        self.clear_button.setText("✕")
        self.clear_button.setToolTip("Drop every pick")
        self.clear_button.clicked.connect(self._clear_picks)
        line.addWidget(self.select_button, 1)
        line.addWidget(self.clear_button)
        self.layout.addRow("Edges/Faces/Features", row)
        self.help = QtWidgets.QLabel(PICK_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.chain = QtWidgets.QCheckBox()
        self.chain.setChecked(True)
        self.chain.setEnabled(False)
        self.chain.setToolTip(
            "Edges tangent to a picked edge are always rounded with it: the geometry kernel "
            "(OpenCASCADE) cannot stop at a tangent edge, so this cannot be switched off yet."
        )
        self.layout.addRow("Tangent Chain", self.chain)
        self._fields()

    def _fields(self):
        raise NotImplementedError

    def _size_field(self, label, what, unit="mm"):
        field = DistanceField(
            self.options.get(what, 1.0),
            unit=unit,
            on_change=lambda value, w=what: self._typed(w, value),
        )
        if unit == "mm":
            field.widget.setProperty("minimum", 0.0)
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        return field, caption

    # -- starting -----------------------------------------------------------------------
    def _start(self, refs):
        if self.base is None or self.info is None:
            self._say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        if self.target is not None:
            missing = [r for r in self.refs if not self.info.pickable(r)]
            if missing:
                self.refs = [r for r in self.refs if r not in missing]
                self._say(
                    "⚠ %d picked edge(s) no longer exist after an earlier change. "
                    "Pick them again." % len(missing)
                )
        elif refs:
            self.refs = [r for r in refs if self.info.pickable(r)]
        self._prepare_display()
        Gui.Selection.clearSelection()
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        try:
            Gui.Selection.addSelectionGate(_Gate(self))
            self.gate = True
        except Exception as exc:
            warn("selection filter unavailable: %s" % exc)
        try:
            self._style = NORMAL
            Gui.Selection.setSelectionStyle(GREEDY)
        except Exception:
            self._style = None
        try:
            self.view = Gui.ActiveDocument.ActiveView
            self._keys = self.view.addEventCallback("SoKeyboardEvent", self._key)
        except Exception as exc:
            warn("%s: Esc key unavailable: %s" % (self.title, exc))
        self._sync()
        self._refs_changed()
        if self.target is not None:
            self._bind()
            self._show_preview(bool(self.refs))

    def _key(self, info):
        """Esc in the 3D view cancels, like in Fusion (FreeCAD only listens to Esc while the
        task panel has the keyboard focus)."""
        try:
            if info.get("Key") != "ESCAPE" or info.get("State") != "UP" or self._closed:
                return
            if QtWidgets.QApplication.mouseButtons() != QtCore.Qt.NoButton:
                return  # never while an arrow is being dragged
            QtCore.QTimer.singleShot(0, self._escape)
        except Exception as exc:
            warn("%s Esc: %s" % (self.title, exc))

    def _escape(self):
        try:
            if not self._closed:
                self.reject()
        except Exception as exc:
            warn("%s could not cancel: %s" % (self.title, exc))

    # -- the picks ----------------------------------------------------------------------
    def _display_of(self, ref):
        if ref.startswith("Edge"):
            return self.info.chain(ref)
        return [ref]

    def _display_set(self):
        names = []
        for ref in self.refs:
            for name in self._display_of(ref):
                if name not in names:
                    names.append(name)
        return names

    def _sync(self):
        """Make FreeCAD's selection show exactly the picks (and their tangent chains)."""
        if self.base is None:
            return
        want = self._display_set()
        self._syncing = True
        try:
            Gui.Selection.clearSelection()
            if want:
                Gui.Selection.addSelection(self.base, want)
        finally:
            self._syncing = False
        self._shown = want

    def _selection_event(self, cleared):
        if self._syncing or self._closed:
            return
        self._cleared = self._cleared or cleared
        self._events.start()

    def _process_selection(self):
        try:
            if self._closed or self.base is None:
                return
            cleared, self._cleared = self._cleared, False
            names, features = [], []
            for sel in Gui.Selection.getSelectionEx():
                for obj, name in _resolve(sel):
                    if obj is None:
                        continue
                    if not name:
                        features.append(obj)
                    elif obj.Name == self.base.Name:
                        names.append(name)
            changed = False
            if not cleared:  # a pick that is no longer selected was clicked again: drop it
                for name in self._shown:
                    if name not in names:
                        changed = self._drop(name) or changed
            for name in names:
                if name not in self._shown:
                    changed = self._add(name) or changed
            for obj in features:
                changed = self._add_feature(obj) or changed
            self._sync()
            if changed:
                self._refs_changed()
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def _add(self, name):
        if name in self.refs or not self.info.pickable(name):
            return False
        self.refs.append(name)
        return True

    def _drop(self, name):
        before = len(self.refs)
        self.refs = [r for r in self.refs if name not in self._display_of(r)]
        return len(self.refs) != before

    def _is_body_feature(self, obj):
        body = self.body
        return (
            body is not None
            and obj is not self.target
            and obj.isDerivedFrom("PartDesign::Feature")
            and any(o.Name == obj.Name for o in body.Group)
        )

    def _add_feature(self, obj):
        if not self._is_body_feature(obj):
            return False
        edges = blend.feature_edges(obj, self.info)
        added = [e for e in edges if e not in self.refs]
        if not added:
            self.help.setText("%s has no sharp edges left to round here." % obj.Label)
            return False
        self.refs.extend(added)
        self.help.setText("%d edge(s) of %s added." % (len(added), obj.Label))
        return True

    def _clear_picks(self):
        if self.refs:
            self.refs = []
            self._sync()
            self._refs_changed()

    def _refs_changed(self):
        count = len(self.refs)
        self.select_button.setText("%d selected" % count if count else "Select")
        self._update_arrows()
        self.schedule()

    # -- values ---------------------------------------------------------------------------
    def _typed(self, what, value):
        self.options[what] = value
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what:
                dragger.set_distance(max(value, 0.0) * spot["per_unit"])
        self.schedule()

    def _dragged(self, spot, distance):
        value = max(0.01, round(distance / spot["per_unit"], 2))
        what = spot["what"]
        self.options[what] = value
        field = self._field_for(what)
        if field is not None:
            field.set_value(value)
        self.schedule()

    def _field_for(self, what):
        return None

    def _collect(self):
        """Read the dialog fields into self.options (subclasses)."""

    # -- arrows ---------------------------------------------------------------------------
    def _remove_arrows(self):
        for dragger, _spot, _origin, _direction in self.arrows:
            dragger.remove()
        self.arrows = []

    def _update_arrows(self):
        self._remove_arrows()
        if not self.refs or self.info is None:
            return
        try:
            view = Gui.ActiveDocument.ActiveView
            toward = -view.getViewDirection()
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            local_toward = placement.Rotation.inverted().multVec(toward)
            spots = blend.arrow_spots(self.kind, self.info, self.refs, self.options, local_toward)
            box = self.info.shape.BoundBox
            size = max(1.5, min(box.DiagonalLength * 0.05, 8.0))
            for spot in spots:
                # The arrow's inner tip sits on the line where the blend starts; it lies on the
                # face (lifted a little) and points away from the edge.
                local = (
                    spot["point"] + spot["lift"] * (0.25 * size) + spot["direction"] * (1.6 * size)
                )
                origin = placement.multVec(local)
                direction = placement.Rotation.multVec(spot["direction"])
                value = float(self.options.get(spot["what"], 1.0))
                dragger = ArrowDragger(
                    origin,
                    direction,
                    value * spot["per_unit"],
                    size,
                    on_drag=lambda d, s=spot: self._dragged(s, d),
                    on_release=lambda d, s=spot: self._dragged(s, d),
                )
                self.arrows.append((dragger, spot, origin, direction))
        except Exception as exc:
            warn("%s arrow unavailable: %s" % (self.title, exc))

    # -- display -------------------------------------------------------------------------
    # PartDesign shows one feature of a body at a time: making one visible hides the others.
    # The see-through "before" shape is therefore shown with makeTemporaryVisible(), which
    # displays it without touching any Visibility property.
    def _remember(self, obj, prop):
        key = (obj.Name, prop)
        if key not in self._saved:
            self._saved[key] = getattr(obj.ViewObject, prop)

    def _set_view(self, obj, prop, value):
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            return
        self._remember(obj, prop)
        if getattr(vo, prop) != value:
            setattr(vo, prop, value)

    def _prepare_display(self):
        """Show the part before the blend (the timeline rolled back to it while picking)."""
        if self.body is None:
            return
        for obj in self.body.Group:
            if obj.isDerivedFrom("PartDesign::Feature") and obj.ViewObject is not None:
                self._remember(obj, "Visibility")
        self._remember(self.base, "Transparency")
        self._set_view(self.base, "Visibility", True)  # hides the other features of the body

    def _show_preview(self, on):
        """on: the result solid (not clickable) with the part before the blend see-through
        around it, so its edges stay clickable and the picks stay highlighted.
        off: just the part before the blend."""
        if self.target is None or self.target.ViewObject is None:
            on = False
        try:
            if on:
                self._set_view(self.target, "Selectable", False)
                self._set_view(self.target, "Visibility", True)
                self._set_view(self.base, "Transparency", GHOST)
                self.base.ViewObject.makeTemporaryVisible(True)
                self._push_back(True)
            else:
                self._set_view(self.base, "Visibility", True)
                self._set_view(
                    self.base, "Transparency", self._saved[(self.base.Name, "Transparency")]
                )
            if on != self._ghost:
                self._ghost = on
                self._sync()  # the highlight follows the shape that is displayed now
        except Exception as exc:
            warn("%s preview display: %s" % (self.title, exc))

    def _push_back(self, on):
        """Draw the preview's faces a hair behind the see-through shape: where both have the
        same face, the picked face's highlight shows cleanly instead of flickering stripes."""
        try:
            if on and self._offset is None and self.target is not None:
                from pivy import coin

                node = coin.SoPolygonOffset()
                node.factor.setValue(1.5)
                node.units.setValue(4.0)
                self.target.ViewObject.RootNode.insertChild(node, 0)
                self._offset = (self.target, node)
            elif not on and self._offset is not None:
                obj, node = self._offset
                self._offset = None
                if obj.ViewObject is not None:
                    obj.ViewObject.RootNode.removeChild(node)
        except Exception as exc:
            warn("%s preview depth: %s" % (self.title, exc))

    def _restore_display(self):
        self._push_back(False)
        doc = self.doc
        visible = []
        for (name, prop), value in self._saved.items():
            obj = doc.getObject(name)
            if obj is None or obj.ViewObject is None:
                continue
            try:
                if prop == "Visibility":
                    if value:
                        visible.append(obj)
                elif getattr(obj.ViewObject, prop) != value:
                    setattr(obj.ViewObject, prop, value)
            except Exception:
                pass
        if self._accepted and self.created and self.target is not None:
            visible = [self.target]  # the new blend is the end of the timeline: the body shows it
        try:
            for obj in visible:
                obj.ViewObject.Visibility = True  # (hides the body's other features)
            if self.base is not None and self.base.ViewObject is not None:
                self.base.ViewObject.makeTemporaryVisible(bool(self.base.ViewObject.Visibility))
        except Exception as exc:
            warn("%s could not restore the view: %s" % (self.title, exc))

    # -- preview --------------------------------------------------------------------------
    def _bind(self):
        """Typed expressions (=Parameters.r) go onto the feature (feature options)."""

    def schedule(self):
        if not self._closed:
            super().schedule()

    def _recompute(self):
        try:
            self._preview()
        except Exception as exc:
            self.error = str(exc)
            self.show_status()

    def _preview(self):
        if self._closed:
            return
        self._collect()
        if not self.refs or self.info is None:
            self.error = None
            self._show_preview(False)
            self.show_status()
            return
        try:
            blend.trial(self.kind, self.info, self.refs, self.options)
        except blend.BlendError as exc:
            self.error = str(exc)
            self.show_status()
            self._hint.start()
            return
        self.error = None
        subs = blend.base_subs(self.info, self.refs)
        if self.target is None:
            self.target = blend.make(self.body, self.base, self.refs, self.kind, self.options)
            self._bind()
        else:
            blend.set_refs(self.target, self.base, subs)
            blend.apply(self.target, self.options)
        with quiet_errors():
            self.doc.recompute()
        self._show_preview(True)
        self.show_status()

    def _compute_hint(self):
        try:
            if self._closed or not self.error or not self.refs:
                return
            what = "radius" if self.kind == "fillet" else "distance"
            size = float(self.options.get(what, 0.0))
            if size <= 0:
                return
            best = blend.max_size(self.kind, self.info, self.refs, self.options, size)
            if best and best < size and self.error:
                shown = math.floor(best * 100.0) / 100.0
                if shown > 0:
                    self._say(
                        "⚠ %s\nThe largest %s that fits here is about %.2f mm."
                        % (self.error, what, shown)
                    )
        except Exception as exc:
            warn("%s size hint: %s" % (self.title, exc))

    def show_status(self):
        if self.error:
            self._say("⚠ " + self.error)
            return
        obj = self.target
        if obj is None or not self.refs:
            self._say("")
            return
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            self._say("⚠ " + blend.friendly(obj.getStatusString()))
            return
        if obj.Shape.isNull() or not obj.Shape.isValid():
            self._say("⚠ The result is not a valid solid. Try a smaller size.")
            return
        broken = [
            o.Label
            for o in (self.body.Group if self.body else [])
            if o is not obj and "Invalid" in list(getattr(o, "State", []))
        ]
        if broken:
            self._say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self._say("")

    def feature(self):
        return self.target

    def _say(self, text):
        """Show (or clear) the dialog's message, growing the panel so no line is cut off."""
        self.message.setText(text)
        width = max(self.message.width(), self.form.width() - 30, 260)
        self.message.setMinimumHeight(self.message.heightForWidth(width) if text else 0)

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if not self.refs or self.info is None:
                self._say(
                    "⚠ Select the edges or faces to %s first." % self.title.lower()
                    if self.info is not None
                    else "⚠ Make a solid first (Create Sketch, then Extrude)."
                )
                return False
            self._preview()
            obj = self.target
            if self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or not obj.Shape.isValid():
                self.show_status()
                return False
            self._accepted = True
            return super().accept()
        except Exception as exc:
            self._accepted = False
            self._say("⚠ %s" % exc)
            return False

    def reject(self):
        self._accepted = False
        return super().reject()

    def cleanup(self):
        self._closed = True
        for timer in (self._events, self._hint):
            try:
                timer.stop()
            except Exception:
                pass
        self._remove_arrows()
        if self._keys is not None:
            try:
                self.view.removeEventCallback("SoKeyboardEvent", self._keys)
            except Exception:
                pass
            self._keys = None
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        if self.gate:
            try:
                Gui.Selection.removeSelectionGate()
            except Exception:
                pass
            self.gate = False
        if self._style is not None:
            try:
                Gui.Selection.setSelectionStyle(self._style)
            except Exception:
                pass
            self._style = None
        try:
            self._restore_display()
        except Exception as exc:
            warn("%s could not restore the view: %s" % (self.title, exc))
        super().cleanup()


class FilletPanel(BlendPanel):
    kind = "fillet"
    title = "Fillet"
    icon = "fillet"

    def _fields(self):
        self.type = _combo(
            [
                ("Fillet", "fillet", True, "Round the picked edges with one radius"),
                ("Rule Fillet", "rule", False, "Not available in SciForge yet"),
                ("Full Round Fillet", "full_round", False, "Not available in SciForge yet"),
            ]
        )
        self.layout.insertRow(0, "Type", self.type)
        self.radius_type = _combo(
            [
                ("Constant", "constant", True, "The same radius along the whole edge"),
                ("Chord Length", "chord", False, "Not available in SciForge yet"),
                ("Variable", "variable", False, "Not available in SciForge yet"),
            ]
        )
        self.layout.addRow("Radius Type", self.radius_type)
        self.radius, _ = self._size_field("Radius", "radius")
        self.continuity = _combo(
            [
                ("Tangent (G1)", "g1", True, "The round meets the faces smoothly (tangent)"),
                ("Curvature (G2)", "g2", False, "Not available: the kernel builds G1 rounds"),
            ]
        )
        self.layout.addRow("Continuity", self.continuity)
        self.corner = _combo(
            [
                ("Rolling Ball", "rolling_ball", True, "Corners where rounds meet are blended"),
                ("Setback", "setback", False, "Not available in SciForge yet"),
            ]
        )
        self.layout.addRow("Corner Type", self.corner)

    def _field_for(self, what):
        return self.radius if what == "radius" else None

    def _collect(self):
        self.options["radius"] = self.radius.value()

    def _bind(self):
        if self.target is not None and not self._bound:
            self.radius.bind(self.target, "Radius")
            self._bound = True


class ChamferPanel(BlendPanel):
    kind = "chamfer"
    title = "Chamfer"
    icon = "chamfer"

    def _fields(self):
        types = [(label, value, True, "") for value, _freecad, label in blend.CHAMFER_TYPES]
        current = [v for v, _f, _l in blend.CHAMFER_TYPES].index(
            self.options.get("chamfer_type", "equal")
        )
        self.ctype = _combo(types, current)
        self.layout.addRow("Chamfer Type", self.ctype)
        self.distance, self.distance_label = self._size_field("Distance", "distance")
        self.distance2, self.distance2_label = self._size_field("Distance 2", "distance2")
        self.angle, self.angle_label = self._size_field("Angle", "angle", unit="deg")
        self.flip = QtWidgets.QToolButton()
        self.flip.setText("⇄ Flip")
        self.flip.setCheckable(True)
        self.flip.setChecked(bool(self.options.get("flip")))
        self.flip.setToolTip("Swap the faces the two sizes are measured on")
        self.flip_label = QtWidgets.QLabel("Flip")
        self.layout.addRow(self.flip_label, self.flip)
        self.corner = _combo(
            [
                ("Chamfer", "chamfer", True, "Corners where chamfers meet get a flat face"),
                ("Miter", "miter", False, "Not available in SciForge yet"),
                ("Blend", "blend", False, "Not available in SciForge yet"),
            ]
        )
        self.layout.addRow("Corner Type", self.corner)
        self.ctype.currentIndexChanged.connect(self._type_changed)
        self.flip.toggled.connect(self._flip_toggled)
        self._update_rows()

    def _update_rows(self):
        ctype = self.ctype.currentData()
        two, angle = ctype == "two", ctype == "angle"
        self.distance_label.setText("Distance 1" if two else "Distance")
        for widget in (self.distance2.widget, self.distance2_label):
            widget.setVisible(two)
        for widget in (self.angle.widget, self.angle_label):
            widget.setVisible(angle)
        for widget in (self.flip, self.flip_label):
            widget.setVisible(two or angle)

    def _type_changed(self, *_):
        self._update_rows()
        self._collect()
        self._update_arrows()
        self.schedule()

    def _flip_toggled(self, *_):
        self._collect()
        self._update_arrows()
        self.schedule()

    def _field_for(self, what):
        return {"distance": self.distance, "distance2": self.distance2}.get(what)

    def _collect(self):
        self.options["chamfer_type"] = self.ctype.currentData()
        self.options["distance"] = self.distance.value()
        self.options["distance2"] = self.distance2.value()
        self.options["angle"] = self.angle.value()
        self.options["flip"] = self.flip.isChecked()

    def _bind(self):
        if self.target is not None and not self._bound:
            self.distance.bind(self.target, "Size")
            self.distance2.bind(self.target, "Size2")
            self.angle.bind(self.target, "Angle")
            self._bound = True


# -- commands ------------------------------------------------------------------------------
class _BlendCommand:
    panel = FilletPanel
    menu = "Fillet"
    tip = ""

    def GetResources(self):
        return {
            "MenuText": self.menu,
            "ToolTip": self.tip,
            "Pixmap": ui_icon_path(self.panel.icon),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start(self.panel)
        except Exception as exc:
            warn("%s could not start: %s" % (self.menu, exc))


def start(panel_class):
    """Run Fillet/Chamfer: with edges/faces already selected it starts with them."""
    selection = [(s.Object, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx()]
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    body = commands.find_body()
    base = solid_base(body)
    if base is None:
        commands.tell(
            "%s needs a solid to round: make one first (Create Sketch, then Extrude)."
            % panel_class.title
        )
        return None
    info = blend.ShapeInfo(base.Shape)
    _reselect(selection)
    refs = picks_from_selection(body, info, base)
    panel = None
    try:
        panel = panel_class(doc, refs=refs)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("%s started with %d pick(s)" % (panel_class.title.lower(), len(refs)))
    return panel


def _reselect(selection):
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


class FilletCommand(_BlendCommand):
    panel = FilletPanel
    menu = "Fillet"
    tip = (
        "Round edges: click edges or faces, drag the arrow or type a radius, "
        "with a live preview (F)"
    )


class ChamferCommand(_BlendCommand):
    panel = ChamferPanel
    menu = "Chamfer"
    tip = "Bevel edges: equal distance, two distances or distance and angle, " "with a live preview"


def edit_fillet(obj):
    """Timeline double-click: the Fillet dialog with the feature's edges picked."""
    Gui.Control.showDialog(FilletPanel(obj.Document, feature=obj))


def edit_chamfer(obj):
    Gui.Control.showDialog(ChamferPanel(obj.Document, feature=obj))


COMMANDS = {"SciForge_Fillet": FilletCommand, "SciForge_Chamfer": ChamferCommand}
EDITORS = {blend.FILLET: edit_fillet, blend.CHAMFER: edit_chamfer}
