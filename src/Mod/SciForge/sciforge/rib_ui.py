# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rib and Web commands with Fusion's dialogs (one dialog class for both).

Rib: click an open sketch curve (Chain Selection takes the curves joined smoothly to it).
The rib is the Thickness thick across the sketch plane (Symmetric, or One Side with Flip
Side) and fills, in the sketch plane, from the curve to the part (Depth Options To Next) or
the Depth. Web: click open sketch curves (a network); each is the Thickness thick in the
sketch plane and grows down to the next faces or the Depth; Extend Curves carries free ends
on to the part. Flip Direction turns the growing side round. The blue arrows set the
thickness and (with Depth) the depth by dragging. Problems are shown in the dialog.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, curve_pick, curves, extrude, log, preview, profile_pick, rib
from . import ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("rib")

SIDE_LABELS = [("Symmetric", "symmetric"), ("One Side", "one_side")]
DEPTH_LABELS = [("To Next", "to_next"), ("Depth", "depth")]


def selected():
    """Sketch curves selected before the command starts."""
    found = []
    for obj, short in profile_pick.picks():
        if not extrude.is_sketch(obj):
            continue
        if short.startswith("Edge"):
            found.append((obj, short))
        elif not short:
            try:
                if not extrude.regions(obj) and obj.Shape.Edges:
                    found += [(obj, "Edge%d" % (i + 1)) for i in range(len(obj.Shape.Edges))]
            except Exception:
                pass
    return curves.normalize(found)


class RibPanel(Panel):
    last = None

    def __init__(self, doc, kind="rib", feature=None):
        self.kind = kind
        self.title = "Web" if kind == "web" else "Rib"
        self.icon = "web" if kind == "web" else "rib"
        super().__init__(doc, self.title if feature is None else "Edit " + self.title)
        RibPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else rib.owner_body(feature)
        self.refs = []
        self.options = dict(rib.DEFAULTS)
        self.options["kind"] = kind
        self.error = ""
        self.dirty = False
        self.arrows = {}
        # The value box next to each arrow; a number typed over the view goes to the arrow
        # used last, else to the thickness.
        self.value_boxes = ValueBoxes(self, default="thickness")
        self.overlay = None
        self.observer = None
        self._quiet = False
        self._shown = []
        if feature is not None:
            try:
                self.refs, read = rib.read(feature)
                self.options.update(read)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
            self._show_sketches()
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_arrows()
        else:
            self._start()

    def _show_sketches(self):
        for obj, _ in self.refs:
            if not extrude.is_sketch(obj):
                continue
            try:
                if obj.ViewObject is not None and not obj.ViewObject.Visibility:
                    obj.ViewObject.Visibility = True
                    self._shown.append(obj)
            except Exception:
                pass

    def _hide_shown(self):
        for obj in self._shown:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    # -- form ----------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        word = "Curves" if self.kind == "web" else "Curve"
        self.field = SelectionField(
            self, "curves", "Select curve" + ("s" if self.kind == "web" else "")
        )
        self.field.button.setObjectName("SciForgeRib_curves")
        self.field.clear.setObjectName("SciForgeRib_clear_curves")
        self.field.set_active(True)
        form.addRow(word, self.field.widget)
        self.chain = curve_pick.checkbox("Chain Selection", self.options["chain"])
        self.chain.setObjectName("SciForgeRib_chain")
        form.addRow("", self.chain)
        self.hint = QtWidgets.QLabel(
            "Click open sketch lines or arcs for the web."
            if self.kind == "web"
            else "Click an open sketch line or arc for the rib."
        )
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.side = curve_pick.combo(SIDE_LABELS, self.options["thickness_side"])
        self.side.setObjectName("SciForgeRib_side")
        form.addRow("Thickness Options", self.side)
        self.flip_side = curve_pick.checkbox("Flip Side", self.options["flip_side"])
        self.flip_side.setObjectName("SciForgeRib_flip_side")
        form.addRow("", self.flip_side)
        self.thickness = DistanceField(self.options["thickness"], on_change=self._value_typed)
        self.thickness.widget.setObjectName("SciForgeRib_thickness")
        form.addRow("Thickness", self.thickness.widget)
        self.depth_type = curve_pick.combo(DEPTH_LABELS, self.options["depth_type"])
        self.depth_type.setObjectName("SciForgeRib_depth_type")
        form.addRow("Depth Options", self.depth_type)
        self.depth = DistanceField(self.options["depth"], on_change=self._value_typed)
        self.depth.widget.setObjectName("SciForgeRib_depth")
        self.depth_label = QtWidgets.QLabel("Depth")
        form.addRow(self.depth_label, self.depth.widget)
        self.flip = curve_pick.checkbox("Flip Direction", self.options["flip"])
        self.flip.setObjectName("SciForgeRib_flip")
        form.addRow("", self.flip)
        self.extend = curve_pick.checkbox("Extend Curves", self.options["extend"])
        self.extend.setObjectName("SciForgeRib_extend")
        self.extend.setToolTip("Carry the free ends of the curves on until they meet the part")
        form.addRow("", self.extend)
        self.finish_layout()
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)
        self.side.currentIndexChanged.connect(self._value_typed)
        self.depth_type.currentIndexChanged.connect(self._value_typed)
        for box in (self.flip_side, self.flip, self.extend):
            box.toggled.connect(self._value_typed)

    def _show_options(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.side, self.options["thickness_side"])
            curve_pick.set_combo(self.depth_type, self.options["depth_type"])
            self.thickness.set_value(self.options["thickness"])
            self.depth.set_value(self.options["depth"])
            self.flip_side.setChecked(self.options["flip_side"])
            self.flip.setChecked(self.options["flip"])
            self.extend.setChecked(self.options["extend"])
            self.chain.setChecked(self.options["chain"])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        depth = self.depth_type.currentData() == "depth"
        for widget, show in (
            (self.flip_side, self.side.currentData() == "one_side"),
            (self.depth_label, depth),
            (self.depth.widget, depth),
            (self.extend, self.kind == "web"),
        ):
            widget.setVisible(show)

    def _collect(self):
        self.options["thickness_side"] = self.side.currentData()
        self.options["flip_side"] = bool(self.flip_side.isChecked())
        self.options["thickness"] = float(self.thickness.value())
        self.options["depth_type"] = self.depth_type.currentData()
        self.options["depth"] = float(self.depth.value())
        self.options["flip"] = bool(self.flip.isChecked())
        self.options["extend"] = bool(self.extend.isChecked())
        self.options["chain"] = bool(self.chain.isChecked())
        self.options["kind"] = self.kind

    # -- the selection box -------------------------------------------------------------------------
    def activate(self, name):
        self.field.set_active(True)

    def clear_field(self, name):
        self.refs = []
        self._picks_changed()

    # -- start --------------------------------------------------------------------------------------------
    def _start(self):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return
        self.refs = selected()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self._refresh_picks()
        self._collect()
        if self.refs:
            self._picks_changed()
            self._timer.stop()
            self._recompute()

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        try:
            self.overlay = curve_pick.CurveOverlay(Gui.ActiveDocument.ActiveView)
        except Exception as exc:
            warn("%s: curve highlight unavailable: %s" % (self.title, exc))

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.overlay is not None:
            self.overlay.remove()
            self.overlay = None

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(_dragging(a) for a in self.arrows.values()):
                return
            for obj, short in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("%s pick: %s" % (self.title, exc))

    def _picked(self, obj, short):
        if not short.startswith("Edge"):
            return  # faces of the part are not curves: the click does nothing (Fusion)
        if not extrude.is_sketch(obj):
            self.message.setText(
                "⚠ A %s is drawn as a sketch curve. Click a line or arc of a sketch."
                % self.title.lower()
            )
            return
        if self.refs and self.refs[0][0] is not obj:
            self.message.setText(
                "⚠ The curves must lie in one sketch. Clear the box to start with another one."
            )
            return
        names = curves.chain(obj, short) if self.chain.isChecked() else [short]
        keys = {(o.Name, s) for o, s in self.refs}
        if (obj.Name, short) in keys:
            drop = {(obj.Name, n) for n in names}
            self.refs = [r for r in self.refs if (r[0].Name, r[1]) not in drop]
        else:
            self.refs = self.refs + [(obj, n) for n in names if (obj.Name, n) not in keys]
        self._picks_changed()

    def _refresh_picks(self):
        self.field.set_text(curves.label(self.refs))
        if self.overlay is not None:
            try:
                edges = curves.refs_edges(self.refs)
            except curves.CurveError:
                edges = []
            self.overlay.show("curves", edges, curve_pick.PATH_COLOR)

    def _picks_changed(self):
        self._refresh_picks()
        if not self.refs:
            if self.target is not None and not self.editing:
                rib.remove(self.target)
                self.target = None
                self.schedule()
            self._remove_arrows()
            text = "Pick the %s's curve." % self.title.lower()
            self.error = text if self.editing else ""
            self.message.setText(("⚠ " + text) if self.editing else "")
            return
        self._changed(new_geometry=True)

    # -- changes ------------------------------------------------------------------------------------
    @safe
    def _value_typed(self, *_):
        if self._quiet:
            return
        self._changed(new_geometry=True)

    def _changed(self, new_geometry=False):
        self._update_visibility()
        self._collect()
        self.dirty = True
        self._arrows_due = new_geometry or getattr(self, "_arrows_due", False)
        self.schedule()

    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            if getattr(self, "_arrows_due", False) and not any(
                _dragging(a) for a in self.arrows.values()
            ):
                self._arrows_due = False
                self._make_arrows()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.refs:
            return
        try:
            self.target = rib.build(self.refs, self.options, feature=self.target, hide=False)
            self.error = ""
        except (rib.RibError, curves.CurveError) as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This %s cannot be built: %s" % (self.title.lower(), exc)

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = preview.failure(self.target)
        self.message.setText("⚠ " + text if text else "")

    # -- the blue arrows ------------------------------------------------------------------------------
    def _remove_arrows(self):
        for arrow in self.arrows.values():
            try:
                arrow.remove()
            except Exception:
                pass
        self.arrows = {}

    def _frame(self):
        """(a point on the curve, growing direction, thickness direction, size), global."""
        sketch = rib.sketch_of(self.refs)
        _origin, normal = rib.plane_of(sketch)
        edges = curves.refs_edges(self.refs)
        edge = edges[0]
        mid = edge.valueAt(edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) / 2)
        tangent = App.Vector(
            edge.tangentAt(edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) / 2)
        )
        tangent.normalize()
        base = self._base_shape()
        reach = 200.0
        if self.kind == "web":
            grow = rib._toward_part(base, mid, normal * -1.0, reach)
            across = normal.cross(tangent)
        else:
            path = curves.Path(edges)
            chord = path.end - path.start
            chord.normalize()
            side = normal.cross(chord)
            side.normalize()
            mid = path.point_at(path.length / 2.0)
            grow = rib._toward_part(base, mid, side, reach)
            across = App.Vector(normal)
        if self.options["flip"]:
            grow = grow * -1.0
        across.normalize()
        if self.options["thickness_side"] == "one_side" and self.options["flip_side"]:
            across = across * -1.0
        size = 4.0
        try:
            size = max(2.5, min(8.0, sum(e.Length for e in edges) * 0.15))
        except Exception:
            pass
        return mid, grow, across, size

    def _base_shape(self):
        if self.target is not None:
            base = self.target.BaseFeature
        else:
            base = self.body.Tip if self.body is not None else None
        if base is None or base.Shape.isNull() or not base.Shape.Solids:
            return None
        return curves.to_global(base.Shape, base)

    def _make_arrows(self):
        if self._closed:
            return
        self._remove_arrows()
        if not self.refs or self.target is None or self.error:
            return
        try:
            mid, grow, across, size = self._frame()
            t = self.options["thickness"]
            half = t / 2.0 if self.options["thickness_side"] == "symmetric" else t
            gap = 0.4 * size
            # Both arrows sit just outside the rib / web: an arrow inside the part cannot be
            # grabbed (the part's face in front takes the click).
            self.arrows["thickness"] = ArrowDragger(
                mid - grow * gap,
                across,
                half,
                size,
                on_drag=self._thickness_dragged,
                on_release=self._thickness_dragged,
            )
            self._attach_box("thickness")
            if self.options["depth_type"] == "depth":
                self.arrows["depth"] = ArrowDragger(
                    mid + across * (half + gap),
                    grow,
                    self.options["depth"],
                    size,
                    on_drag=self._depth_dragged,
                    on_release=self._depth_dragged,
                )
                self._attach_box("depth")
        except Exception as exc:
            warn("%s arrows unavailable: %s" % (self.title, exc))

    def _attach_box(self, key):
        """The value box next to the arrow `key`: the field's text, and a value typed in it
        goes to that field."""
        field = getattr(self, key)
        return self.value_boxes.attach(
            self.arrows.get(key),
            key,
            lambda: field.widget.text(),
            lambda text: self._box_typed(key, text),
        )

    def _box_typed(self, key, text):
        if self._closed:
            return
        field = getattr(self, key)
        try:
            value = field.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        field.take(value)

    @safe
    def _thickness_dragged(self, distance):
        distance = abs(round(distance, 2))
        value = distance * 2.0 if self.options["thickness_side"] == "symmetric" else distance
        value = max(0.1, value)
        self._quiet = True
        try:
            self.thickness.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    @safe
    def _depth_dragged(self, distance):
        value = max(0.1, abs(round(distance, 2)))
        self._quiet = True
        try:
            self.depth.set_value(value)
        finally:
            self._quiet = False
        self._changed()

    # -- OK / Cancel -----------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("%s OK: %s" % (self.title, exc))
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.refs:
            self.message.setText("⚠ Pick the %s's curve first." % self.title.lower())
            return False
        self._timer.stop()
        self._collect()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        if self.target is None:
            self.message.setText("⚠ This %s cannot be built." % self.title.lower())
            return False
        preview.recompute(self.doc)
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        rib.hide_sketches(self.refs)
        self._shown = []
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(rib.owner_body(feature))
        log("%s done" % self.title)
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            body = self.body
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            if body is not None and curves.owner_body(body) is not None:
                extrude.show_tip(body)
        except Exception as exc:
            warn("%s Cancel: %s" % (self.title, exc))
        try:
            self._close()
        except Exception as exc:
            warn("%s Cancel: %s" % (self.title, exc))
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_arrows()
        self.value_boxes.discard()
        self._hide_shown()
        super().cleanup()


def _dragging(arrow):
    try:
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderRib:
    """View provider of SciForge's Rib / Web feature."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = getattr(getattr(self, "Object", None), "SciForgeType", "Rib")
        return ui_icon_path("web" if kind == "Web" else "rib")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _start(kind):
    try:
        if not commands.finish_open_dialog():
            return
        if commands.find_body() is None:
            commands.tell(
                "%s needs a part and a sketch curve: make the part first."
                % ("Web" if kind == "web" else "Rib")
            )
            return
        Gui.Control.showDialog(RibPanel(App.ActiveDocument, kind))
        log("%s started" % kind)
    except Exception as exc:
        warn("%s failed to start: %s" % (kind.capitalize(), exc))


class RibCommand:
    def GetResources(self):
        return {
            "MenuText": "Rib",
            "ToolTip": "A thin support from an open sketch curve: grows in the sketch plane "
            "to the next faces or a depth",
            "Pixmap": ui_icon_path("rib"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start("rib")


class WebCommand:
    def GetResources(self):
        return {
            "MenuText": "Web",
            "ToolTip": "Thin supports from a network of open sketch curves: grow down to the "
            "next faces or a depth",
            "Pixmap": ui_icon_path("web"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start("web")


def edit(feature):
    """Open the Rib / Web dialog on an existing one (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        kind = "web" if getattr(feature, "SciForgeType", "") == "Web" else "rib"
        Gui.Control.showDialog(RibPanel(feature.Document, kind, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Rib": RibCommand, "SciForge_Web": WebCommand}
EDITORS = {"SciForge::Rib": edit, "SciForge::Web": edit}
