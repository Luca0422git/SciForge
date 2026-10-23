# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > CREATE > Lip, with Fusion's dialog: Lip, Groove or Lip And Groove.

Click the edges where the two halves of an enclosure meet (the inside edge of the rim, so
the reveal shows on the outside; Tangent Chain takes the edges joined smoothly to the one
clicked; a click on the rim's flat face takes its inside edge). Lip stands a lip on the rim;
Groove cuts a groove into it; Lip And Groove puts the lip on this body and the matching
groove (the lip grown by the clearance) in the body that touches it, Swap the other way
round. Guide Type: Pull Direction (the rim's normal, the
section kept upright) or Face Guide. The Advanced sizes start from the component's plastic
rule (lip width = Thickness / 2, lip height = Reveal Height, Clearance, Draft Angle) and
follow it until a value is typed. The blue arrows drag the lip's height and width. One
timeline step; double-click it to edit.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, components, curve_pick, extrude, log, plastic, plastic_lip
from . import plastic_core, preview, profile_pick, ui_icon_path, warn
from . import plastic_lip_core as core
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("lip")

TYPE_LABELS = [(core.TYPE_TITLES[k], k) for k in core.TYPES]
GUIDE_LABELS = [(core.GUIDE_TITLES[k], k) for k in core.GUIDES]
FIELDS = [
    ("lip_width", "mm"),
    ("lip_height", "mm"),
    ("inner_draft", "deg"),
    ("outer_draft", "deg"),
    ("clearance", "mm"),
    ("clearance_height", "mm"),
    ("groove_width", "mm"),
    ("groove_depth", "mm"),
    ("tip_radius", "mm"),
    ("root_radius", "mm"),
]
EDGE_COLOR = (0.35, 0.75, 1.0)


def _rule_here(doc, body=None):
    try:
        if body is not None:
            return plastic.rule_for_body(body)
        return plastic.rule_for_component(doc, components.active_component(doc), fallback=True)
    except Exception as exc:
        warn("Lip: plastic rule: %s" % exc)
        return None


class LipPanel(Panel):
    title = "Lip"
    icon = "pl_lip"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Lip" if feature is None else "Edit Lip")
        LipPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.source = None  # the step the edges are picked on
        self.names = []
        self.rule = _rule_here(doc, bodies.body_of(feature) if feature is not None else None)
        self.options = core.defaults(self.rule)
        self.error = ""
        self.dirty = False
        self.find_mate = False
        self.arrows = {}
        self.value_boxes = ValueBoxes(self, default="lip_height")
        self.observer = None
        self.overlay = None
        self._quiet = False
        if feature is not None:
            try:
                self.names, read, _mate = plastic_lip.read(feature)
                self.options = core.follow_rule(read, self.rule)
                self.source = feature.BaseFeature
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_arrows()
            self.show_status()
        else:
            self._start()

    # -- form ----------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.type = curve_pick.combo(TYPE_LABELS, self.options["type"])
        self.type.setObjectName("SciForgeLip_type")
        form.addRow("Type", self.type)
        self.field = SelectionField(self, "edges", "Select edges")
        self.field.button.setObjectName("SciForgeLip_edges")
        self.field.clear.setObjectName("SciForgeLip_clear_edges")
        self.field.set_active(True)
        form.addRow("Edges", self.field.widget)
        self.chain = curve_pick.checkbox("Tangent Chain", True)
        self.chain.setObjectName("SciForgeLip_chain")
        form.addRow("", self.chain)
        self.guide = curve_pick.combo(GUIDE_LABELS, self.options["guide"])
        self.guide.setObjectName("SciForgeLip_guide")
        form.addRow("Guide Type", self.guide)
        self.direction_field = SelectionField(self, "direction", "Rim normal")
        self.direction_field.button.setObjectName("SciForgeLip_direction")
        self.direction_field.clear.setObjectName("SciForgeLip_clear_direction")
        self.direction_label = QtWidgets.QLabel("Direction")
        form.addRow(self.direction_label, self.direction_field.widget)
        self.active = "edges"
        self.swap = curve_pick.checkbox("Swap Lip and Groove", self.options["swap"])
        self.swap.setObjectName("SciForgeLip_swap")
        self.swap.setToolTip("Lip And Groove: the lip on the other body, the groove on this one")
        form.addRow("", self.swap)
        self.mate_label = QtWidgets.QLabel("")
        self.mate_label.setObjectName("SciForgeLip_mate")
        self.mate_field = SelectionField(self, "mate", "Found")
        self.mate_field.button.setObjectName("SciForgeLip_mate_body")
        self.mate_field.clear.setObjectName("SciForgeLip_clear_mate")
        self.mate_title = QtWidgets.QLabel("Other Body")
        form.addRow(self.mate_title, self.mate_field.widget)
        form.addRow("", self.mate_label)
        self.mate_pick = None
        box = QtWidgets.QGroupBox("Advanced")
        advanced = QtWidgets.QFormLayout(box)
        self.fields = {}
        self.labels = {}
        for key, unit in FIELDS:
            field = DistanceField(self.options[key], unit=unit, on_change=self._typed(key))
            field.widget.setObjectName("SciForgeLip_" + key)
            label = QtWidgets.QLabel(core.LABELS[key])
            advanced.addRow(label, field.widget)
            self.fields[key] = field
            self.labels[key] = label
        # the wall at the edges and the shoulder (reveal) left beside the lip: read only
        self.shoulder = QtWidgets.QLabel("")
        self.shoulder.setObjectName("SciForgeLip_shoulder")
        self.shoulder.setWordWrap(True)
        advanced.addRow(self.shoulder)
        form.addRow(box)
        rule = self.rule or {}
        self.rule_label = QtWidgets.QLabel(
            "Plastic rule: %s (%s)"
            % (rule.get("name", plastic_core.DEFAULT_RULE), rule.get("material", "ABS"))
        )
        self.rule_label.setObjectName("SciForgeLip_rule")
        form.addRow(self.rule_label)
        self.finish_layout()
        for combo in (self.type, self.guide):
            combo.currentIndexChanged.connect(self._choice_changed)
        self.swap.toggled.connect(self._choice_changed)

    def _show_options(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.type, self.options["type"])
            curve_pick.set_combo(self.guide, self.options["guide"])
            self.swap.setChecked(self.options["swap"])
            for key, field in self.fields.items():
                field.set_value(self.options[key])
        finally:
            self._quiet = False
        self._update_visibility()

    def _update_visibility(self):
        kind = self.options["type"]
        groove_only = kind == "groove"
        lip = kind != "groove"
        rows = {
            "lip_width": lip,
            "lip_height": lip,
            "tip_radius": lip,
            "root_radius": lip,
            "clearance": kind == "lip_and_groove",
            "clearance_height": kind == "lip_and_groove",
            "groove_width": groove_only,
            "groove_depth": groove_only,
        }
        for key, show in rows.items():
            self.fields[key].widget.setVisible(show)
            self.labels[key].setVisible(show)
        self.swap.setVisible(kind == "lip_and_groove")
        self.mate_label.setVisible(kind == "lip_and_groove")
        self.mate_title.setVisible(kind == "lip_and_groove")
        self.mate_field.widget.setVisible(kind == "lip_and_groove")
        pull = self.options["guide"] == "pull"
        self.direction_label.setVisible(pull)
        self.direction_field.widget.setVisible(pull)
        self.direction_field.set_text("Picked direction" if self.options.get("direction") else "")

    def _typed(self, key):
        def typed(value):
            if self._quiet or self._closed:
                return
            try:
                self.options[key] = float(value)
                if key in core.RULE_FIELDS:
                    self.options = core.unlink(self.options, key)
                self._changed()
            except Exception as exc:
                warn("Lip: %s" % exc)

        return typed

    @safe
    def _choice_changed(self, *_):
        if self._quiet:
            return
        old = self.options["type"]
        self.options["type"] = self.type.currentData()
        self.options["guide"] = self.guide.currentData()
        self.options["swap"] = bool(self.swap.isChecked())
        if old != self.options["type"]:
            self.find_mate = True
        self._update_visibility()
        self._changed()

    def _changed(self):
        self.dirty = True
        self.schedule()

    # -- picking -----------------------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self.field.set_active(name == "edges")
        self.direction_field.set_active(name == "direction")
        self.mate_field.set_active(name == "mate")

    def clear_field(self, name):
        if name == "mate":
            self.mate_pick = None
            self.mate_field.set_text("")
            self.find_mate = True
            self.activate("edges")
            self._changed()
            return
        if name == "direction":
            self.options.pop("direction", None)
            self.activate("edges")
            self._update_visibility()
            self._changed()
            return
        self.names = []
        self._picks_changed()

    def _mate_picked(self, obj):
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        own = bodies.body_of(self.source) if self.source is not None else None
        if body is None or not bodies.has_solid(body):
            self.message.setText("⚠ Click the solid body that touches the rim.")
            return
        if body is own:
            self.message.setText("⚠ The other body cannot be the one the edges are on.")
            return
        self.mate_pick = body
        self.mate_field.set_text(body.Label)
        self.activate("edges")
        self._changed()

    def _direction_picked(self, obj, short):
        from . import construct, surface_analysis

        if not surface_analysis.fits_direction(obj, short):
            self.message.setText("⚠ Pick a plane, a flat face or a straight edge for the pull.")
            return
        try:
            vector = surface_analysis.direction_of(construct.normalize_pick(obj, short))
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return
        self.options["direction"] = (vector.x, vector.y, vector.z)
        self.activate("edges")
        self._update_visibility()
        self._changed()

    def _start(self):
        if not bodies.solid_bodies(self.doc):
            self.message.setText("⚠ Make the enclosure first: a Lip goes on a solid body's rim.")
            return
        picks = [(o, s) for o, s in profile_pick.picks() if s.startswith("Edge")]
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        for obj, short in picks:
            self._picked(obj, short, refresh=False)
        if self.names:
            self._picks_changed()
        else:
            self.message.setText(
                "Click the inside edges of the rim where the halves meet (or the rim's flat face)."
            )

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
            warn("Lip: edge highlight unavailable: %s" % exc)

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
            picks = [p for p in _picks() if p[0].Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if any(_dragging(a) for a in self.arrows.values()):
                return
            for obj, short, point in picks:
                self._picked(obj, short, point=point)
        except Exception as exc:
            warn("Lip pick: %s" % exc)

    def _picked(self, obj, short, refresh=True, point=None):
        if getattr(self, "active", "edges") == "direction":
            self._direction_picked(obj, short)
            return
        if getattr(self, "active", "edges") == "mate":
            self._mate_picked(obj)
            return
        face = short.startswith("Face")
        if not short.startswith("Edge") and not face:
            self.message.setText("⚠ A lip runs along edges: click the rim's inside edges.")
            return
        body = bodies.body_of(obj)
        if body is None:
            self.message.setText("⚠ Click an edge of a body.")
            return
        if self.target is not None:
            base = self.target.BaseFeature
            if bodies.body_of(base) is not body:
                if bodies.body_of(self.target) is not body:
                    self.message.setText("⚠ The edges must lie on one body (the Lip's).")
                    return
        else:
            base = self.source if self.source is not None else body.Tip
            if self.source is not None and bodies.body_of(self.source) is not body:
                if self.names:
                    self.message.setText(
                        "⚠ The edges must lie on one body: clear the box to start on another."
                    )
                    return
                base = body.Tip
        if face:
            self._rim_face_picked(base, obj, short)
            return
        found = curve_pick.base_element(base, obj, short)
        if found is None:
            found = _within(base, obj, short) or _nearest(base, point)
        if found is None:
            self.message.setText("⚠ That edge was made by the Lip itself: click the rim's edges.")
            return
        base, name = found
        self.source = base
        names = plastic_lip.tangent_chain(base.Shape, name) if self.chain.isChecked() else [name]
        if name in self.names:
            self.names = [n for n in self.names if n not in names]
        else:
            self.names = self.names + [n for n in names if n not in self.names]
        if refresh:
            self._picks_changed()

    def _rim_face_picked(self, base, obj, short):
        """A click on the rim's flat face takes its inside edge (the face's inner loop), as
        if each of its edges had been clicked (SciForge's shortcut)."""
        found = curve_pick.base_element(base, obj, short)
        names = plastic_lip.inner_loop(found[0].Shape, found[1]) if found is not None else None
        if not names:
            self.message.setText(
                "⚠ Click the rim's flat face (a face with an inside edge) or the inside edges."
            )
            return
        self.source = found[0]
        self.names = names
        self._picks_changed()

    def _edges(self):
        if self.source is None or not self.names:
            return []
        try:
            shape = bodies.global_shape(self.source)
            return [shape.getElement(n) for n in self.names]
        except Exception:
            return []

    def _refresh_picks(self):
        n = len(self.names)
        self.field.set_text("%d edge%s" % (n, "" if n == 1 else "s") if n else "")
        if self.overlay is not None:
            self.overlay.show("edges", self._edges(), EDGE_COLOR)

    def _picks_changed(self):
        self._refresh_picks()
        if not self.names:
            if self.target is not None and not self.editing:
                plastic_lip.remove(self.target)
                self.target = None
                self.schedule()
            self._remove_arrows()
            self.error = "Pick the rim's edges." if self.editing else ""
            self.message.setText(("⚠ " + self.error) if self.error else "")
            return
        self.find_mate = self.find_mate or not self.editing
        self._changed()

    # -- building ----------------------------------------------------------------------------------
    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            self._refresh_picks()
            if not any(_dragging(a) for a in self.arrows.values()):
                self._make_arrows()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if self.source is None or not self.names:
            return
        try:
            mate = self.mate_pick if bodies.alive(self.mate_pick) else None
            if self.target is None:
                self.target = plastic_lip.make(
                    self.source, list(self.names), dict(self.options), mate=mate
                )
            else:
                keep = mate if mate is not None else (None if self.find_mate else False)
                plastic_lip.update(
                    self.target,
                    names=list(self.names),
                    options=dict(self.options),
                    mate=keep,
                )
            self.find_mate = False
            self.error = ""
        except plastic_lip.LipError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This lip cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        mate = plastic_lip.mate_of(self.target) if self.target is not None else None
        self.mate_label.setText(mate.Label if mate is not None else "(none)")
        self.shoulder.setText(self._shoulder_text())
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = failure(self.target)
        if not text and self.target is not None:
            from . import modify_bodies

            notes = [getattr(self.target, "SciForgeWarning", "")]
            notes += [
                getattr(f, "SciForgeWarning", "") for f in modify_bodies.followers_of(self.target)
            ]
            notes = [n for n in notes if n]
            if notes:
                self.message.setText("Note: " + "; ".join(notes))
                return
        self.message.setText("⚠ " + text if text else "")

    def _shoulder_text(self):
        """ "Wall at the edges: 2.00 mm; shoulder beside the lip: 1.00 mm" (the reveal width
        when the lip is on the edges' body), or "" when there is nothing to measure."""
        try:
            if self.target is None or self.error:
                return ""
            wall = plastic_lip.rim_of(self.target).wall
            if not wall:
                return ""
            text = "Wall at the edges: %.2f mm" % wall
            kind = self.options["type"]
            if kind == "lip" or (kind == "lip_and_groove" and not self.options["swap"]):
                text += "; shoulder beside the lip: %.2f mm" % (wall - self.options["lip_width"])
            return text
        except Exception:
            return ""

    # -- arrows ------------------------------------------------------------------------------------
    def _remove_arrows(self):
        for arrow in self.arrows.values():
            try:
                arrow.remove()
            except Exception:
                pass
        self.arrows = {}

    def _make_arrows(self):
        if self._closed:
            return
        self._remove_arrows()
        if self.target is None or self.error or self.options["type"] == "groove":
            return
        try:
            rim = plastic_lip.rim_of(self.target)
            edge = rim.wire.Edges[0]
            t = 0.5 * (edge.FirstParameter + edge.LastParameter)
            mid = edge.valueAt(t)
            tangent = App.Vector(edge.tangentAt(t))
            tangent.normalize()
            across = rim.normal.cross(tangent)
            across.normalize()
            probe = __import__("Part").Vertex(mid + across * 0.05)
            if rim.face.distToShape(probe)[0] > 1e-3:
                across = across * -1.0
            up = rim.normal * (-1.0 if self.options["swap"] else 1.0)
            size = 4.0
            self.arrows["lip_height"] = ArrowDragger(
                mid + across * (0.5 * self.options["lip_width"]),
                up,
                self.options["lip_height"],
                size,
                on_drag=self._dragged("lip_height"),
                on_release=self._dragged("lip_height"),
            )
            self._attach_box("lip_height")
            self.arrows["lip_width"] = ArrowDragger(
                mid + up * self.options["lip_height"],
                across,
                self.options["lip_width"],
                size,
                on_drag=self._dragged("lip_width"),
                on_release=self._dragged("lip_width"),
            )
            self._attach_box("lip_width")
        except Exception as exc:
            warn("Lip arrows unavailable: %s" % exc)

    def _attach_box(self, key):
        field = self.fields[key]
        return self.value_boxes.attach(
            self.arrows.get(key),
            key,
            lambda: field.widget.text(),
            lambda text: self._box_typed(key, text),
        )

    def _box_typed(self, key, text):
        if self._closed:
            return
        field = self.fields[key]
        try:
            value = field.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        field.take(value)

    def _dragged(self, key):
        @safe
        def dragged(distance):
            value = max(0.05, abs(round(distance, 2)))
            self._quiet = True
            try:
                self.fields[key].set_value(value)
            finally:
                self._quiet = False
            self.options[key] = value
            self.options = core.unlink(self.options, key)
            self._changed()

        return dragged

    # -- OK / Cancel -------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Lip OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.names:
            self.message.setText("⚠ Pick the rim's edges first.")
            return False
        self._timer.stop()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        if self.target is None:
            self.message.setText("⚠ This lip cannot be built.")
            return False
        preview.recompute(self.doc)
        text = failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(bodies.body_of(feature))
        log("Lip done")
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            for body in bodies.solid_bodies(self.doc):
                extrude.show_tip(body)
        except Exception as exc:
            warn("Lip Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Lip Cancel: %s" % exc)
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
        super().cleanup()


def failure(feature):
    """The error of the Lip step or of its hidden step in the other body, or "" (OK must not
    leave a failed step behind, even a hidden one)."""
    from . import modify_bodies

    text = preview.failure(feature)
    if text or feature is None:
        return text
    for follower in modify_bodies.followers_of(feature):
        text = preview.failure(follower)
        if text:
            break
    return text


def _picks():
    """[(object, short element name, picked point or None)] of the selection."""
    found = []
    for sel in Gui.Selection.getSelectionEx():
        names = list(sel.SubElementNames) or [""]
        points = list(getattr(sel, "PickedPoints", []) or [])
        for i, name in enumerate(names):
            obj, short = profile_pick.resolve(sel.Object, name)
            if obj is not None:
                found.append((obj, short, points[i] if i < len(points) else None))
    return found


def _nearest(base, point, tol=0.05):
    """(base, name) of the edge of `base` passing within `tol` of the clicked point (design
    coordinates), or None."""
    import Part

    if point is None:
        return None
    try:
        shape = bodies.global_shape(base)
        probe = Part.Vertex(point)
        best = None
        for i, edge in enumerate(shape.Edges, start=1):
            d = edge.distToShape(probe)[0]
            if d < tol and (best is None or d < best[0]):
                best = (d, i)
        return (base, "Edge%d" % best[1]) if best is not None else None
    except Exception:
        return None


def _within(base, obj, short):
    """(base, name) of the edge of `base` that lies along the picked edge of the preview
    (the lip standing on the rim can lengthen a rim edge: its end face is flush with the
    wall), or None."""
    import Part

    try:
        picked = obj.Shape.getElement(short)
    except Exception:
        return None
    for i, edge in enumerate(base.Shape.Edges, start=1):
        try:
            mid = edge.valueAt(0.5 * (edge.FirstParameter + edge.LastParameter))
            points = [v.Point for v in edge.Vertexes] + [mid]
            if all(picked.distToShape(Part.Vertex(q))[0] < 1e-6 for q in points):
                return (base, "Edge%d" % i)
        except Exception:
            continue
    return None


def _dragging(arrow):
    try:
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderLip:
    """View provider of the Lip step. Saved documents store
    "sciforge.plastic_lip_ui.ViewProviderLip": keep the name stable."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("pl_lip")

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


def start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None or not bodies.solid_bodies(doc):
            commands.tell("A Lip goes on the rim of a solid body: make the enclosure first.")
            return
        Gui.Control.showDialog(LipPanel(doc))
        log("Lip started")
    except Exception as exc:
        warn("Lip failed to start: %s" % exc)


class LipCommand:
    def GetResources(self):
        return {
            "MenuText": "Lip",
            "ToolTip": "A lip, a groove, or a lip and its matching groove where the two halves "
            "of an enclosure meet",
            "Pixmap": ui_icon_path("pl_lip"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        start()


def edit(feature):
    """Open the Lip dialog on an existing one (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(LipPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


def _register():
    try:
        from . import parameters, timeline_core

        timeline_core.KINDS.setdefault("lip", ("Lip", "pl_lip"))
        parameters.SCIFORGE_PROPS.setdefault(
            "Lip",
            [
                ("LipWidth", "Lip Width"),
                ("LipHeight", "Lip Height"),
                ("Clearance", "Clearance"),
                ("GrooveWidth", "Groove Width"),
                ("GrooveDepth", "Groove Depth"),
            ],
        )
    except Exception as exc:
        warn("Lip: timeline registration: %s" % exc)


_register()

COMMANDS = {"SciForge_Lip": LipCommand}
EDITORS = {"SciForge::Lip": edit}
