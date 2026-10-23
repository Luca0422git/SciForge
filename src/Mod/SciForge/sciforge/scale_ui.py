# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scale with Fusion's dialog: scale bodies or sketches about a point.

Pressing Scale with nothing selected opens the dialog, which waits for the entities: click
the part (any face, edge or corner of it) or its row in the browser, or a sketch (its row in
the browser, or one of its curves). A body or sketch selected before pressing Scale is taken
at once. The Point box then takes the clicks: it starts at the origin; click a corner of the
part (or a point in the browser) to scale about that instead, click it again to go back to
the origin. Click the Entities box again to add more bodies or sketches (one Scale step
scales them all, like Fusion; click a picked one again to drop it). Scale Type Uniform (one
Scale Factor) or Non Uniform (X / Y / Z Scale; bodies only, as in Fusion). The blue arrows
sit on the part's far side and move with it: drag them or type the factors, with a live
preview.

Bodies: SciForge's ScaleFeature in the first body's timeline, a hidden follower step in each
other body (scale.py, modify_bodies.py). Sketches: their curves are scaled in place and a
"Scale" step records the factor (editing it scales them again, deleting it scales them
back). Double-click the step in the timeline to edit it.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, hole_common, log, modify_bodies, pickpanel, preview, scale
from . import ui_icon_path, warn
from .compat import QtWidgets
from .taskui import DistanceField, ValueBoxes

ENTITY_HELP = (
    "Click the bodies to scale (any face of them) or a sketch (its curves, or its row in the "
    "browser). Click a picked one again to drop it."
)
POINT_HELP = "Scaled about the origin. Click a corner of the part to scale about it."
ARROW_LENGTH = 2.2  # the arrow's length in units of the handle size (ball, shaft, head)
TYPE_ITEMS = [("Uniform", "uniform"), ("Non Uniform", "non_uniform")]
SKETCH_UNIFORM = "Sketches scale the same way in every direction (Uniform), as in Fusion."


class ViewProviderScale:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("scale")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit_scale(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit_scale(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class ViewProviderSketchScale(ViewProviderScale):
    """The view provider of the Scale step of sketches (scale.SketchScaleFeature): nothing
    to draw, the step's icon; a double-click edits it."""

    def claimChildren(self):
        return []


def _factor_field(value, on_change):
    field = DistanceField(value, unit="", on_change=on_change)
    field.widget.setProperty("minimum", 0.0)
    field.widget.setProperty("decimals", 3)
    field.set_value(value)
    return field


def _sketch_of(obj):
    """The sketch a pick belongs to (the sketch itself), or None."""
    return obj if scale.is_sketch(obj) else None


class ScalePanel(pickpanel.PickPanel):
    title = "Scale"
    icon = "scale"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, body=None, sketches=None):
        super().__init__(doc, "Scale" if feature is None else "Edit Scale")
        ScalePanel.last = self
        self.target = None
        self.record = None  # the Scale step of the sketches (scale.SketchScaleFeature)
        self.sketches = []
        self.editing = feature is not None
        self.point_ref = None  # None: the origin
        self.active = "entities"
        self.options = scale.default_options()
        self.formulas = {"factor": "", "x": "", "y": "", "z": ""}
        self.formula_errors = {}
        self.arrows = []  # (pickpanel.Arrow, spot, origin, direction)
        # Fusion shows the scale factor beside the arrow being dragged; typed there it is
        # taken like the dialog's field (a formula too). One box per factor field.
        self.value_boxes = ValueBoxes(self, default="factor")
        if feature is not None and scale.is_sketch_scale(feature):
            self.record = feature
            self.sketches = [s for s in feature.Sketches if scale.is_sketch(s)]
            self.options["factor"] = float(feature.Factor)
            self.active = "point"
        elif feature is not None:
            self.target = feature
            self.body = scale.owner_body(feature)
            base, ref, options, formulas = scale.read(feature)
            self.base = base
            self.point_ref = ref
            self.options.update(options)
            self.formulas.update({k: v for k, v in formulas.items() if v})
            self.active = "point"
            for follower in modify_bodies.followers_of(feature):  # the other bodies
                member = self.add_member(bodies.body_of(follower), follower.BaseFeature)
                member.whole = True
                member.target = follower
        elif body is not None:
            self.body = body
            self.base = scale_base(body)
            self.active = "point" if self.base is not None else "entities"
        for sketch in sketches or []:
            if scale.is_sketch(sketch) and sketch not in self.sketches:
                self.sketches.append(sketch)
                self.active = "point"
        self._build()
        self.finish_layout()
        try:
            self._start()
        except Exception as exc:  # never leave a half-open dialog without a reason
            self.say("⚠ %s" % exc)
            warn("Scale could not start picking: %s" % exc)

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        self.entities = hole_common.SelectionField(self, "entities", "Select")
        self.entities.button.setToolTip(ENTITY_HELP)
        self.layout.addRow("Entities", self.entities.widget)
        self.point_box = hole_common.SelectionField(self, "point", "Origin")
        self.point_box.button.setToolTip(POINT_HELP)
        self.layout.addRow("Point", self.point_box.widget)
        self.help = QtWidgets.QLabel(ENTITY_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.scale_type = pickpanel.combo(
            TYPE_ITEMS, "uniform" if self.options["uniform"] else "non_uniform"
        )
        self.scale_type.currentIndexChanged.connect(self._type_changed)
        self.layout.addRow("Scale Type", self.scale_type)
        self.factor = _factor_field(self.options["factor"], lambda v: self._typed("factor", v))
        self.factor_label = QtWidgets.QLabel("Scale Factor")
        self.layout.addRow(self.factor_label, self.factor.widget)
        self.axis_fields = {}
        self.axis_labels = {}
        for i, axis in enumerate("xyz"):
            field = _factor_field(self.options["factors"][i], lambda v, a=axis: self._typed(a, v))
            label = QtWidgets.QLabel("%s Scale" % axis.upper())
            self.layout.addRow(label, field.widget)
            self.axis_fields[axis] = field
            self.axis_labels[axis] = label
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        self._formula_inputs = [preview.FormulaInput(self, "factor", self.factor)] + [
            preview.FormulaInput(self, a, f) for a, f in self.axis_fields.items()
        ]
        self._rows()
        self._show_formulas()

    def _rows(self):
        uniform = self.scale_type.currentData() == "uniform"
        for widget in (self.factor.widget, self.factor_label):
            widget.setVisible(uniform)
        for axis in "xyz":
            for widget in (self.axis_fields[axis].widget, self.axis_labels[axis]):
                widget.setVisible(not uniform)

    def field_for(self, what):
        return self.factor if what == "factor" else self.axis_fields[what]

    def has_entities(self):
        return self.base is not None or bool(self.sketches)

    # -- starting -----------------------------------------------------------------------
    def _start(self):
        if self.base is not None:
            self.remember_later(self.target if self.editing else self.base)
        self.start_picking()
        self._activate(self.active)
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.has_entities():
            self.schedule()

    def activate(self, name):
        if name == "point" and not self.has_entities():
            return  # pick what to scale first
        self._activate(name)

    def _activate(self, name):
        self.active = name
        self.entities.set_active(name == "entities")
        self.point_box.set_active(name == "point")
        if name == "entities":
            self.help.setText(ENTITY_HELP)
        else:
            self.help.setText(
                POINT_HELP
                if self.point_ref is None
                else "Scaled about %s. Click it again to go back to the origin."
                % scale.point_label(self.point_ref)
            )

    def clear_field(self, name):
        if name == "point":
            if self.point_ref is not None:
                self.point_ref = None
                self._sync()
                self._picks_updated()
            return
        if self.editing:
            return
        if self.base is not None:
            self._drop_body()
        for member in list(self.members):
            self.drop_member(member.body)
        self.sketches = []
        self._sync()
        self._picks_updated()

    # -- the picks (PickPanel calls these) ---------------------------------------------------
    def shown(self):
        entries = []
        if self.point_ref is not None:
            obj, sub = self.point_ref
            entries.append((obj, [sub] if sub else []))
        for sketch in self.sketches:
            entries.append((sketch, []))
        return entries

    def _body_of(self, obj):
        if obj is None:
            return None
        if obj.TypeId == "PartDesign::Body":
            return obj
        return scale.owner_body(obj)

    def _point_in_body(self, obj):
        if obj is None:
            return False
        if self.body is None:
            return scale.is_point_object(obj)
        if obj.TypeId == "App::Point":
            return any(o is obj for o in self.body.Origin.OriginFeatures)
        return obj.TypeId == "PartDesign::Point" and scale.owner_body(obj) is self.body

    def allow(self, obj, short):
        if obj is None:
            return False
        if self.active == "entities":
            if _sketch_of(obj) is not None:
                return not self.editing or self.record is not None
            if self.editing and self.record is not None:
                return False
            body = self._body_of(obj)
            if body is None:
                return False
            if self.editing and body is self.body:
                return False
            return scale_base(body) is not None or self.member(body) is not None
        if not short:
            return scale.is_point_object(obj) and self._point_in_body(obj)
        if not short.startswith("Vertex"):
            return False
        if self.base is not None:
            return obj.Name == self.base.Name
        return _sketch_of(obj) is not None or self._body_of(obj) is not None

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if self.point_ref is not None and obj is self.point_ref[0]:
                if short == (self.point_ref[1] or ""):
                    self.point_ref = None
                    changed = True
            elif _sketch_of(obj) in self.sketches and not short:
                self.sketches.remove(obj)
                changed = True
        for obj, short, _point in added:
            if self.active == "entities":
                sketch = _sketch_of(obj)
                if sketch is not None:
                    changed = self._toggle_sketch(sketch) or changed
                    continue
                body = self._body_of(obj)
                if body is not None:
                    changed = self._pick_body(body) or changed
            elif not short and scale.is_point_object(obj) and self._point_in_body(obj):
                changed = self._set_point((obj, "")) or changed
            elif short.startswith("Vertex") and self.allow(obj, short):
                changed = self._set_point((obj, short)) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _toggle_sketch(self, sketch):
        if sketch in self.sketches:
            self.sketches.remove(sketch)
        else:
            self.sketches.append(sketch)
            if self.base is None and not self.members:
                self._activate("point")
        return True

    def _pick_body(self, body):
        base = scale_base(body)
        if self.body is not None and body is not self.body:
            # Fusion's Entities box takes several bodies: one Scale step scales them all.
            if self.member(body) is not None:
                self.drop_member(body)
                return True
            if base is None:
                self.help.setText("%s has no solid to scale yet." % body.Label)
                return False
            self.add_member(body, modify_bodies.base_for(self.target, body))
            return True
        if base is None:
            self.help.setText("%s has no solid to scale yet." % body.Label)
            return False
        if body is self.body and self.base is base and self.target is not None:
            if self.members and not self.editing:
                return self._promote()  # a picked body clicked again: dropped
            self._activate("point")
            return False
        if self.target is not None:
            self._remove_target()
        self.point_ref = None
        if self.body is None:
            self.body, self.base = body, base
            self.prepare_display()
            self.remember_later(base)
        else:
            self.switch_body(body, base)  # also remembers what later steps use
        pickpanel.activate(body)
        self._activate("point")
        return True

    def _promote(self):
        """The first body is dropped: the next picked body becomes the one the step lives in."""
        self._remove_target()
        self.restore_display()
        member = self.members.pop(0)
        self.body, self.base = member.body, scale_base(member.body)
        self.point_ref = None
        self.prepare_display()
        self.show_members()
        self.remember_later(self.base)
        pickpanel.activate(self.body)
        return True

    def _drop_body(self):
        self._remove_target()
        self.restore_display()
        self.body = self.base = None
        self.point_ref = None
        self._activate("entities")

    def _set_point(self, ref):
        if self.point_ref is not None and self.point_ref[0] is ref[0]:
            if self.point_ref[1] == ref[1]:
                return False
        self.point_ref = ref
        self._activate("point")
        return True

    def _picks_updated(self, schedule=True):
        names = []
        if self.base is not None:
            names.append(self.body.Label)
        names += [m.body.Label for m in self.members]
        names += [s.Label for s in self.sketches]
        if len(names) > 2:
            text = "%d selected" % len(names)
        else:
            text = ", ".join(names)
        self.entities.set_text(text)
        self.point_box.set_text(scale.point_label(self.point_ref))
        if self.active == "point":
            self._activate("point")
        self._update_arrows()
        if schedule:
            self.schedule()

    # -- values -------------------------------------------------------------------------------
    def _type_changed(self, *_):
        self.options["uniform"] = self.scale_type.currentData() == "uniform"
        self._rows()
        self._update_arrows()
        self.schedule()

    def _typed(self, what, value):
        if what == "factor":
            self.options["factor"] = value
        else:
            self.options["factors"]["xyz".index(what)] = value
        for dragger, spot, _origin, _direction in self.arrows:
            if spot["what"] == what:
                dragger.set_distance((value - 1.0) * spot["length"])
        self.schedule()

    def _dragged(self, spot, distance, released=False):
        value = max(0.001, round(1.0 + distance / spot["length"], 3))
        what = spot["what"]
        if released:
            # dragged through the scale point: the arrow goes back to the smallest factor
            wanted = (value - 1.0) * spot["length"]
            if abs(wanted - distance) > 1e-6:
                for dragger, other, _origin, _direction in self.arrows:
                    if other is spot:
                        dragger.set_distance(wanted)
        if what == "factor":
            self.options["factor"] = value
        else:
            self.options["factors"]["xyz".index(what)] = value
        self.field_for(what).set_value(value)
        if self.formulas.get(what):
            self.formulas[what] = ""  # a drag gives a plain number
            self._show_formulas()
        self.schedule()

    def _collect(self):
        self.options["uniform"] = self.scale_type.currentData() == "uniform"
        if not self.formulas.get("factor"):
            self.options["factor"] = self.factor.value()
        for i, axis in enumerate("xyz"):
            if not self.formulas.get(axis):
                self.options["factors"][i] = self.axis_fields[axis].value()

    def formula_typed(self, key, text, value):
        self.formula_errors.pop(key, None)
        self.formulas[key] = text
        self._show_formulas()
        self._typed(key, value)

    def formula_cleared(self, key):
        self.formula_errors.pop(key, None)
        if self.formulas.get(key):
            self.formulas[key] = ""
            self._show_formulas()
        self._typed(key, self.field_for(key).value())

    def formula_failed(self, key, text):
        self.formula_errors[key] = text
        self.show_status()

    def _show_formulas(self):
        names = {"factor": "Scale Factor", "x": "X Scale", "y": "Y Scale", "z": "Z Scale"}
        lines = ["%s = %s" % (names[k], self.formulas[k]) for k in names if self.formulas.get(k)]
        self.formula_label.setText("\n".join(lines))

    # -- arrows ---------------------------------------------------------------------------
    def _remove_arrows(self):
        for dragger, _spot, _origin, _direction in self.arrows:
            dragger.remove()
        self.arrows = []

    def _arrow_shape(self):
        """(shape, placement, point) the arrows sit on: the first body's solid, else the
        first sketch's curves (in the design's coordinates)."""
        if self.base is not None:
            return self.base.Shape, self.body.getGlobalPlacement(), scale.point_of(self.point_ref)
        if self.sketches:
            sketch = self.sketches[0]
            shape = sketch.Shape.copy()
            body = bodies.body_of(sketch)
            place = body.getGlobalPlacement() if body is not None else App.Placement()
            point = self._design_point()
            if point is None:
                point = sketch.Placement.Base
            else:
                point = place.inverse().multVec(point)
            return shape, place, point
        return None, None, None

    def _update_arrows(self):
        self._remove_arrows()
        if self._closed or not self.has_entities():
            return
        try:
            self._collect()
            shape, placement, point = self._arrow_shape()
            if shape is None or shape.isNull():
                return
            size = max(2.0, min(shape.BoundBox.DiagonalLength * 0.06, 12.0))
            for spot in scale.handle_spots(shape, point, self.options):
                what = spot["what"]
                if what == "factor":
                    value = float(self.options["factor"])
                else:
                    value = float(self.options["factors"]["xyz".index(what)])
                # a gap between the corner and the arrow: the corner stays clickable
                local = spot["origin"] + spot["direction"] * (2.2 * size)
                origin = placement.multVec(local)
                direction = placement.Rotation.multVec(spot["direction"])
                dragger = pickpanel.Arrow(
                    origin,
                    direction,
                    (value - 1.0) * spot["length"],
                    size * ARROW_LENGTH,
                    on_drag=lambda d, s=spot: self._dragged(s, d),
                    on_release=lambda d, s=spot: self._dragged(s, d, True),
                )
                self.arrows.append((dragger, spot, origin, direction))
                self._attach_box(dragger, what)
        except Exception as exc:
            warn("Scale arrow unavailable: %s" % exc)

    def _attach_box(self, dragger, what):
        """The value box beside an arrow: its factor field's text; a value or a formula
        typed there goes to that field (Scale Factor, or X / Y / Z Scale)."""
        field = self.field_for(what)
        return self.value_boxes.attach(
            dragger, what, lambda: field.widget.text(), lambda text: self._box_typed(what, text)
        )

    def _box_typed(self, what, text):
        if self._closed:
            return
        for formula in self._formula_inputs:
            if formula.key == what:
                formula.take(text)
                return

    # -- preview --------------------------------------------------------------------------
    def _remove_target(self):
        if self.target is None or self.editing:
            return
        target, self.target = self.target, None
        self._looks.restore()
        self._ghost = False
        scale.remove(target)
        for member in self.members:
            member.target = None
        self.quiet_recompute()
        self.prepare_display()
        self.show_members()

    def _remove_record(self):
        if self.record is None or self.editing:
            return
        record, self.record = self.record, None
        try:
            scale.unscale_sketches(record)
            self.doc.removeObject(record.Name)
        except Exception as exc:
            warn("Scale: %s" % exc)

    def _design_point(self):
        """The scale point in the design's coordinates (None: the origin)."""
        if self.point_ref is None:
            return None
        obj, sub = self.point_ref
        try:
            local = scale.point_of(self.point_ref)
        except scale.ScaleError:
            return None
        body = bodies.body_of(obj)
        place = body.getGlobalPlacement() if body is not None else App.Placement()
        if not sub and obj.TypeId == "App::Point":
            return place.multVec(App.Vector())
        return place.multVec(local)

    def _preview(self):
        if self._closed:
            return
        self._collect()
        if self.formula_errors:
            self.show_status()
            return
        if not self.has_entities():
            self.error = None
            self._remove_record()
            self.show_status()
            return
        self.error = None
        if self.sketches and not self.options["uniform"]:
            self.error = SKETCH_UNIFORM
            self.show_status()
            return
        if self.base is not None:
            try:
                scale.trial(self.base.Shape, self._point_for_trial(), self.options)
            except scale.ScaleError as exc:
                self.error = str(exc)
                self.show_status()
                return
            if self.target is None:
                self.target = scale.make(
                    self.body, self.base, self.point_ref, self.options, formulas=self.formulas
                )
            else:
                scale.apply(self.target, self.base, self.point_ref, self.options, self.formulas)
            self._sync_members()
        self._preview_sketches()
        self.quiet_recompute()
        self.follow_later()
        if self.target is not None:
            self.show_preview(True)
        self.show_status()

    def _sync_members(self):
        try:
            followers = modify_bodies.sync(
                self.target,
                [(m.body, None) for m in self.members],
                modify_bodies.ScaleFollower,
                "Scale",
            )
        except modify_bodies.FollowerError as exc:
            self.error = str(exc)
            return
        for member, follower in zip(self.members, followers):
            member.target = follower

    def _preview_sketches(self):
        if not self.sketches:
            if not self.editing:
                self._remove_record()
            return
        factor = float(self.options["factor"])
        point = self._design_point()
        label = scale.point_label(self.point_ref) if self.point_ref is not None else ""
        try:
            if self.record is not None and list(self.record.Sketches) != self.sketches:
                scale.unscale_sketches(self.record)
                self.record.Sketches = list(self.sketches)
                self.record.Applied = 1.0
            if self.record is None:
                self.record, kept = scale.make_sketch_scale(
                    self.doc, self.sketches, factor, point, label
                )
            else:
                kept = scale.edit_sketch_scale(self.record, factor, point, label, move_point=True)
        except scale.ScaleError as exc:
            self.error = str(exc)
            return
        if kept:
            self.error = None
            self.say("Dimensions that follow a parameter keep their value: %s" % ", ".join(kept))

    def _point_for_trial(self):
        return self.point_ref

    def show_status(self):
        if self.formula_errors:
            self.say("⚠ " + list(self.formula_errors.values())[0])
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        if self.target is None:
            self.say("")
            return
        text = preview.failure(self.target)
        if text:
            self.say("⚠ " + text)
            return
        for member in self.members:
            text = preview.failure(member.target) if member.target is not None else ""
            if text:
                self.say("⚠ %s: %s" % (member.body.Label, text))
                return
        broken = self.later_broken()
        if broken:
            self.say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self.say("")

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if not self.has_entities():
                self.say(
                    "⚠ Select what to scale first: click a body (or its browser row) or a "
                    "sketch."
                )
                return False
            self._preview()
            if self.formula_errors or self.error:
                self.show_status()
                return False
            if self.base is not None:
                obj = self.target
                if obj is None:
                    self.show_status()
                    return False
                state = list(obj.State)
                if "Invalid" in state or "Error" in state or not obj.Shape.isValid():
                    self.show_status()
                    return False
                for member in self.members:
                    state = list(getattr(member.target, "State", ["Invalid"]))
                    if member.target is None or "Invalid" in state or "Error" in state:
                        self.show_status()
                        return False
            if self.sketches and self.record is None:
                self.show_status()
                return False
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def cleanup(self):
        self._remove_arrows()
        self.value_boxes.discard()
        super().cleanup()


def scale_base(body):
    """The step a new scale builds on: the body's current end, if it is a solid or a
    surface body (Fusion's SURFACE > MODIFY > Scale; surface-4)."""
    from . import shelling, surfmod

    base = shelling.solid_base(body)
    if base is None and body is not None and surfmod.is_surface_body(body):
        return body.Tip
    return base


# -- command -----------------------------------------------------------------------------
class ScaleCommand:
    def GetResources(self):
        return {
            "MenuText": "Scale",
            "ToolTip": "Make bodies or sketches bigger or smaller about a point: one factor, or "
            "one per direction, with a live preview",
            "Pixmap": ui_icon_path("scale"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Scale could not start: %s" % exc)


def _selected_sketches():
    found = []
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        if scale.is_sketch(obj) and obj not in found:
            found.append(obj)
    return found


def start():
    """Run Scale: a body (or a face of it) or a sketch selected beforehand is taken at once;
    with nothing selected the dialog opens and waits for what to scale."""
    picked_body = pickpanel.selected_body()
    sketches = _selected_sketches()
    if sketches:
        picked_body = None
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        return None
    has_solid = any(scale_base(b) for b in doc.findObjects("PartDesign::Body"))
    has_sketch = bool(doc.findObjects("Sketcher::SketchObject"))
    if not has_solid and not has_sketch:
        commands.tell("Scale needs a body or a sketch: make one first (Create Sketch).")
        return None
    body = picked_body if picked_body is not None and scale_base(picked_body) else None
    if body is not None:
        pickpanel.activate(body)
    panel = None
    try:
        panel = ScalePanel(doc, body=body, sketches=sketches)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("scale started%s" % (" on %s" % body.Label if body is not None else ""))
    return panel


def edit_scale(obj):
    """Timeline double-click: the Scale dialog on the existing step."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(ScalePanel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


try:
    scale.install_sketch_watch()  # deleting a sketch Scale step scales the sketches back
except Exception as _exc:  # never let an import fail the commands
    warn("sketch scale watch unavailable: %s" % _exc)


COMMANDS = {"SciForge_Scale": ScaleCommand}
EDITORS = {"SciForge::" + scale.KIND: edit_scale, "SciForge::" + scale.SKETCH_KIND: edit_scale}
