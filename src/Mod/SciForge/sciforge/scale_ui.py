# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scale with Fusion's dialog: scale a body about a point.

Pressing Scale with nothing selected opens the dialog, which waits for the body: click
the part (any face, edge or corner of it) or its row in the browser. A body selected
before pressing Scale is taken at once. The Point box then takes the clicks: it starts
at the body's origin; click a corner of the part (or a point in the browser) to scale
about that instead, click it again to go back to the origin. Scale Type Uniform (one
Scale Factor) or Non Uniform (X / Y / Z Scale). The blue arrows sit on the part's far
side and move with it: drag them or type the factors, with a live preview.

Built as SciForge's ScaleFeature in the body's timeline (scale.py); double-click the step
there to edit it. Fusion can also scale sketches and components; SciForge scales bodies.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, hole_common, log, pickpanel, preview, scale, ui_icon_path, warn
from .compat import QtWidgets
from .taskui import ArrowDragger, DistanceField

ENTITY_HELP = "Click the body to scale (any face of it), or its row in the browser."
POINT_HELP = "Scaled about the origin. Click a corner of the part to scale about it."
TYPE_ITEMS = [("Uniform", "uniform"), ("Non Uniform", "non_uniform")]


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


def _factor_field(value, on_change):
    field = DistanceField(value, unit="", on_change=on_change)
    field.widget.setProperty("minimum", 0.0)
    field.widget.setProperty("decimals", 3)
    field.set_value(value)
    return field


class ScalePanel(pickpanel.PickPanel):
    title = "Scale"
    icon = "scale"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, body=None):
        super().__init__(doc, "Scale" if feature is None else "Edit Scale")
        ScalePanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.point_ref = None  # None: the body's origin
        self.active = "entities"
        self.options = scale.default_options()
        self.formulas = {"factor": "", "x": "", "y": "", "z": ""}
        self.formula_errors = {}
        self.arrows = []  # (ArrowDragger, spot, origin, direction)
        if feature is not None:
            self.body = scale.owner_body(feature)
            base, ref, options, formulas = scale.read(feature)
            self.base = base
            self.point_ref = ref
            self.options.update(options)
            self.formulas.update({k: v for k, v in formulas.items() if v})
            self.active = "point"
        elif body is not None:
            self.body = body
            self.base = scale_base(body)
            self.active = "point" if self.base is not None else "entities"
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

    # -- starting -----------------------------------------------------------------------
    def _start(self):
        self.start_picking()
        self._activate(self.active)
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.base is not None:
            self.schedule()

    def activate(self, name):
        if name == "point" and self.base is None:
            return  # pick the body first
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
        if self.base is not None and not self.editing:
            self._drop_body()
            self._sync()
            self._picks_updated()

    # -- the picks (PickPanel calls these) ---------------------------------------------------
    def shown(self):
        if self.point_ref is None or self.base is None:
            return []
        obj, sub = self.point_ref
        return [(obj, [sub] if sub else [])]

    def _body_of(self, obj):
        if obj is None:
            return None
        if obj.TypeId == "PartDesign::Body":
            return obj
        return scale.owner_body(obj)

    def _point_in_body(self, obj):
        if obj is None or self.body is None:
            return False
        if obj.TypeId == "App::Point":
            return any(o is obj for o in self.body.Origin.OriginFeatures)
        return obj.TypeId == "PartDesign::Point" and scale.owner_body(obj) is self.body

    def allow(self, obj, short):
        if obj is None:
            return False
        if self.active == "entities":
            if self.editing:
                return False
            body = self._body_of(obj)
            return body is not None and scale_base(body) is not None
        if not short:
            return scale.is_point_object(obj) and self._point_in_body(obj)
        return self.base is not None and obj.Name == self.base.Name and short.startswith("Vertex")

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if self.point_ref is not None and obj is self.point_ref[0]:
                if short == (self.point_ref[1] or ""):
                    self.point_ref = None
                    changed = True
        for obj, short, _point in added:
            if self.active == "entities":
                body = self._body_of(obj)
                if body is not None and not self.editing:
                    changed = self._pick_body(body) or changed
            elif not short and scale.is_point_object(obj) and self._point_in_body(obj):
                changed = self._set_point((obj, "")) or changed
            elif short.startswith("Vertex") and self.base is not None and obj is self.base:
                changed = self._set_point((obj, short)) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _pick_body(self, body):
        base = scale_base(body)
        if base is None:
            self.help.setText("%s has no solid to scale yet." % body.Label)
            return False
        if body is self.body and self.base is base and self.target is not None:
            self._activate("point")
            return False
        if self.target is not None:
            self._remove_target()
        self.point_ref = None
        if self.body is None:
            self.body, self.base = body, base
            self.prepare_display()
        else:
            self.switch_body(body, base)
        pickpanel.activate(body)
        self._activate("point")
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
        self.entities.set_text(self.body.Label if self.base is not None else "")
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

    def _dragged(self, spot, distance):
        value = max(0.001, round(1.0 + distance / spot["length"], 3))
        what = spot["what"]
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

    def _update_arrows(self):
        self._remove_arrows()
        if self.base is None or self._closed:
            return
        try:
            self._collect()
            placement = self.body.getGlobalPlacement()
            shape = self.base.Shape
            point = scale.point_of(self.point_ref)
            size = max(2.0, min(shape.BoundBox.DiagonalLength * 0.06, 12.0))
            for spot in scale.handle_spots(shape, point, self.options):
                what = spot["what"]
                if what == "factor":
                    value = float(self.options["factor"])
                else:
                    value = float(self.options["factors"]["xyz".index(what)])
                local = spot["origin"] + spot["direction"] * (1.2 * size)
                origin = placement.multVec(local)
                direction = placement.Rotation.multVec(spot["direction"])
                dragger = ArrowDragger(
                    origin,
                    direction,
                    (value - 1.0) * spot["length"],
                    size,
                    on_drag=lambda d, s=spot: self._dragged(s, d),
                    on_release=lambda d, s=spot: self._dragged(s, d),
                )
                hole_common.on_top(dragger.root)
                self.arrows.append((dragger, spot, origin, direction))
        except Exception as exc:
            warn("Scale arrow unavailable: %s" % exc)

    # -- preview --------------------------------------------------------------------------
    def _remove_target(self):
        if self.target is None or self.editing:
            return
        target, self.target = self.target, None
        self._looks.restore()
        self._ghost = False
        scale.remove(target)
        self.quiet_recompute()
        self.prepare_display()

    def _preview(self):
        if self._closed:
            return
        self._collect()
        if self.formula_errors:
            self.show_status()
            return
        if self.base is None:
            self.error = None
            self.show_status()
            return
        try:
            scale.trial(self.base.Shape, self._point_for_trial(), self.options)
        except scale.ScaleError as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.error = None
        if self.target is None:
            self.target = scale.make(
                self.body, self.base, self.point_ref, self.options, formulas=self.formulas
            )
        else:
            scale.apply(self.target, self.base, self.point_ref, self.options, self.formulas)
        self.quiet_recompute()
        self.show_preview(True)
        self.show_status()

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
        broken = self.later_broken()
        if broken:
            self.say("⚠ Later steps no longer work: %s" % ", ".join(broken))
            return
        self.say("")

    # -- OK / Cancel ------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if self.base is None:
                self.say("⚠ Select the body to scale first (click it, or its browser row).")
                return False
            self._preview()
            obj = self.target
            if self.formula_errors or self.error or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state or not obj.Shape.isValid():
                self.show_status()
                return False
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def cleanup(self):
        self._remove_arrows()
        super().cleanup()


def scale_base(body):
    """The step a new scale builds on (the body's current end, if it is a solid)."""
    from . import shelling

    return shelling.solid_base(body)


# -- command -----------------------------------------------------------------------------
class ScaleCommand:
    def GetResources(self):
        return {
            "MenuText": "Scale",
            "ToolTip": "Make a body bigger or smaller about a point: one factor, or one per "
            "direction, with a live preview",
            "Pixmap": ui_icon_path("scale"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Scale could not start: %s" % exc)


def start():
    """Run Scale: a body selected beforehand (or a face of it) is taken at once; with
    nothing selected the dialog opens and waits for the body."""
    picked_body = pickpanel.selected_body()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        return None
    if not any(scale_base(b) for b in doc.findObjects("PartDesign::Body")):
        commands.tell("Scale needs a solid: make one first (Create Sketch, then Extrude).")
        return None
    body = picked_body if picked_body is not None and scale_base(picked_body) else None
    if body is not None:
        pickpanel.activate(body)
    panel = None
    try:
        panel = ScalePanel(doc, body=body)
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


COMMANDS = {"SciForge_Scale": ScaleCommand}
EDITORS = {"SciForge::" + scale.KIND: edit_scale}
