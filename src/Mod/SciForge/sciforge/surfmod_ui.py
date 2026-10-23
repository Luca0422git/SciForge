# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on surface bodies (wave 6, surface-4): the dialogs. The document side is
surfmod.py; the rules surfmod_core.py.

Fusion repeats SOLID's MODIFY tools on its SURFACE tab. The ones a solid's own dialog cannot
do on a surface body open these dialogs instead (the solid tools hand over to them):

  Fillet / Chamfer  (F, the SOLID dialogs)  edges of a surface body: fillet_ui.start hands over
                    when the edges picked are on a surface body, or nothing is picked on the
                    SURFACE tab while a surface body is shown
  Press Pull (Q)    a face of a surface body: the face moves, the faces around it follow;
                    an edge of a surface body: Fillet (as Press Pull on a solid's edge)
  Merge             adjacent faces of one surface body that lie on one surface become one face
  Delete            (delete_ui) on the SURFACE tab removes faces without healing; double-clicking
                    that step opens the Delete Face dialog here

Picking works as in Shell and Draft (pickpanel.PickPanel): a click on an edge (face) adds it,
a click on a picked one drops it; while picking, the body before the step is shown and the
result is drawn inside it. One undo step; Esc cancels, Enter is OK.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, log, pickpanel, preview, surfmod, ui_icon_path, warn
from . import surfmod_core as core
from .compat import QtCore, QtWidgets
from .taskui import DistanceField, ValueBoxes

PICKS_EDGES = ("surface_fillet", "surface_chamfer")
# value field -> the step's property it drives (a parameter or formula typed goes on it)
PROPS = {"radius": "Radius", "radius2": "Radius2", "distance": "Distance", "distance2": "Distance2"}
HINTS = {
    "surface_fillet": "Click edges of a surface body (between two of its faces) to round.",
    "surface_chamfer": "Click edges of a surface body (between two of its faces) to bevel.",
    "surface_delete_face": "Click the faces to delete: they go, the hole stays open.",
    "surface_merge": "Click two or more faces next to each other on one surface body.",
    "surface_press_pull": "Click a face of a surface body; drag the arrow or type a "
    "distance (+ along the face's normal, - against it).",
}


# -- timeline / Change Parameters registration (at import, like surface_ui) ----------------------
def _register():
    try:
        from . import timeline_core

        timeline_core.KINDS["surface_merge"] = core.TIMELINE_KINDS["surface_merge"]
        timeline_core.KIND_BY_SCIFORGE_TYPE.update(core.TIMELINE_SHARED)
    except Exception as exc:
        warn("surface modify: timeline names unavailable: %s" % exc)
    try:
        from . import parameters

        parameters.SCIFORGE_PROPS.setdefault("SurfaceFillet", [("Radius", "Radius")])
        parameters.SCIFORGE_PROPS.setdefault(
            "SurfaceChamfer", [("Distance", "Distance"), ("Distance2", "Distance 2")]
        )
        parameters.SCIFORGE_PROPS.setdefault("SurfacePressPull", [("Distance", "Distance")])
    except Exception as exc:
        warn("surface modify: Change Parameters entries unavailable: %s" % exc)


_register()


# -- which body ------------------------------------------------------------------------------
def surface_body_of(obj):
    body = obj if bodies.is_body(obj) else bodies.body_of(obj)
    return body if body is not None and surfmod.is_surface_body(body) else None


def surface_picks(picks):
    """The picks [(obj, short, point)] that are edges or faces of surface bodies."""
    found = []
    for entry in picks:
        obj, short = entry[0], entry[1]
        if obj is None or obj.TypeId == "Sketcher::SketchObject":
            continue
        if short.startswith(("Edge", "Face")) and surface_body_of(obj) is not None:
            found.append(entry)
    return found


def current_tab():
    try:
        from . import shell

        ribbon = shell.ribbon()
        return ribbon.current_tab() if ribbon is not None else None
    except Exception:
        return None


def shown_surface_body(doc):
    """The surface body a command with nothing picked works on: the active body if it is
    one, else the first one shown."""
    try:
        active = commands.active_body()
        if active is not None and surfmod.is_surface_body(active):
            return active
    except Exception:
        pass
    try:
        from . import surface

        found = surface.surface_bodies(doc, visible_only=True)
        return found[0] if found else None
    except Exception:
        return None


def _selection_picks(doc):
    return [(o, s, p) for o, s, p in pickpanel.selection_entries(doc)]


# -- the dialog ---------------------------------------------------------------------------------
class SurfaceModifyPanel(pickpanel.PickPanel):
    icon = "fillet"
    last = None

    def __init__(self, doc, kind, feature=None, body=None, picks=None):
        self.kind = kind
        self.title = core.TITLES[kind]
        self.icon = core.DIALOG_ICONS[kind]
        super().__init__(doc, self.title if feature is None else "Edit %s" % self.title)
        SurfaceModifyPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.picked = []  # element names on self.base
        self.options = core.with_defaults(kind, {})
        self.arrows = []
        self.value_boxes = ValueBoxes(self, default="value")
        self.message_text = ""
        self.formulas = {}  # value field -> the formula typed in it (Fusion's parameters)
        self.formula_errors = {}
        if feature is not None:
            self.body = bodies.body_of(feature)
            base, names, options = surfmod.read(feature)
            self.base = feature.BaseFeature or base
            self.picked = list(names)
            self.options.update(options)
            for key, prop in PROPS.items():
                text = preview.formula_of(feature, prop) if prop in feature.PropertiesList else ""
                if text:
                    self.formulas[key] = text
        else:
            self.body = body
            self.base = body.Tip if body is not None else None
        self._build()
        self.finish_layout()
        try:
            self._start(picks or [])
        except Exception as exc:
            self.say("⚠ %s" % exc)
            warn("%s could not start picking: %s" % (self.title, exc))

    # -- layout ------------------------------------------------------------------------------
    def _build(self):
        what = "Edges" if self.kind in PICKS_EDGES else "Faces"
        self.selection = pickpanel.hole_common.SelectionField(self, "picks", "Select")
        self.selection.set_active(True)
        self.layout.addRow(what, self.selection.widget)
        self.help = QtWidgets.QLabel(HINTS[self.kind])
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.fields = {}
        self.tangent = None
        if self.kind in PICKS_EDGES:
            self.tangent = QtWidgets.QCheckBox()
            self.tangent.setChecked(bool(self.options.get("tangent_chain", True)))
            self.tangent.setToolTip("Also round the edges that continue a picked edge smoothly")
            self.tangent.toggled.connect(lambda *_: self._changed())
            self.layout.addRow("Tangent Chain", self.tangent)
        if self.kind == "surface_fillet":
            self.radius_type = pickpanel.combo(
                [
                    (core.RADIUS_LABELS["constant"], "constant"),
                    (core.RADIUS_LABELS["variable"], "variable"),
                    (
                        core.RADIUS_LABELS["chord"],
                        "chord",
                        False,
                        "Not on surface bodies yet: OpenCASCADE has no chord-length fillet",
                    ),
                ],
                self.options.get("radius_type", "constant"),
            )
            self.radius_type.currentIndexChanged.connect(lambda *_: self._radius_type_changed())
            self.layout.addRow("Radius Type", self.radius_type)
            self._field("radius", "Radius", minimum=0.0)
            self._field("radius2", "End Radius", minimum=0.0)
            self._radius_rows()
        if self.kind == "surface_chamfer":
            self.chamfer_type = pickpanel.combo(
                [(core.CHAMFER_LABELS[k], k) for k in core.CHAMFER_TYPES],
                self.options["chamfer_type"],
            )
            self.chamfer_type.currentIndexChanged.connect(lambda *_: self._type_changed())
            self.layout.addRow("Chamfer Type", self.chamfer_type)
            self._field("distance", "Distance", minimum=0.0)
            self._field("distance2", "Distance 2", minimum=0.0)
            self.angle = QtWidgets.QDoubleSpinBox()
            self.angle.setRange(0.1, 89.9)
            self.angle.setSuffix(" °")
            self.angle.setValue(float(self.options["angle"]))
            self.angle.valueChanged.connect(lambda *_: self._changed())
            self.angle_label = QtWidgets.QLabel("Angle")
            self.layout.addRow(self.angle_label, self.angle)
            self.flip = QtWidgets.QCheckBox()
            self.flip.setChecked(bool(self.options["flip"]))
            self.flip.toggled.connect(lambda *_: self._changed())
            self.flip_label = QtWidgets.QLabel("Flip")
            self.layout.addRow(self.flip_label, self.flip)
            self._chamfer_rows()
        if self.kind == "surface_press_pull":
            self._field("distance", "Distance")
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        # Fusion's value fields take a parameter or a formula ("r", "wall * 2")
        self.formula_inputs = {
            key: preview.FormulaInput(self, key, field) for key, (field, _c) in self.fields.items()
        }
        self._show_formulas()

    # -- formulas (preview.FormulaInput calls these) ----------------------------------------
    def formula_typed(self, key, text, value):
        self.formula_errors.pop(key, None)
        self.formulas[key] = text
        self.options[key] = value
        self._show_formulas()
        self._typed()

    def formula_cleared(self, key):
        self.formula_errors.pop(key, None)
        if self.formulas.pop(key, None):
            self._show_formulas()
        self._typed()

    def formula_failed(self, key, text):
        self.formula_errors[key] = text
        self.show_status()

    def _show_formulas(self):
        rows = []
        for key, (_field, caption) in self.fields.items():
            if self.formulas.get(key):
                rows.append("%s = %s" % (caption.text(), self.formulas[key]))
        self.formula_label.setText("\n".join(rows))

    def _apply_formulas(self):
        if self.target is None:
            return
        for key in self.fields:
            prop = PROPS.get(key)
            if prop and prop in self.target.PropertiesList:
                preview.set_formula(self.target, prop, self.formulas.get(key, ""))

    def _field(self, key, label, minimum=None):
        field = DistanceField(float(self.options.get(key, 0.0)), on_change=lambda v: self._typed())
        if minimum is not None:
            field.widget.setProperty("minimum", minimum)
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        self.fields[key] = (field, caption)
        return field

    def _chamfer_rows(self):
        kind = self.chamfer_type.currentData()
        field, caption = self.fields["distance2"]
        for widget in (field.widget, caption):
            widget.setVisible(kind == "two")
        for widget in (self.angle, self.angle_label):
            widget.setVisible(kind == "angle")
        for widget in (self.flip, self.flip_label):
            widget.setVisible(kind != "equal")

    def _type_changed(self):
        self._chamfer_rows()
        self._changed()

    def _radius_rows(self):
        variable = self.radius_type.currentData() == "variable"
        field, caption = self.fields["radius2"]
        for widget in (field.widget, caption):
            widget.setVisible(variable)
        self.fields["radius"][1].setText("Start Radius" if variable else "Radius")

    def _radius_type_changed(self):
        self._radius_rows()
        self._changed()

    def main_key(self):
        return {"surface_fillet": "radius", "surface_chamfer": "distance"}.get(
            self.kind, "distance"
        )

    # -- starting ----------------------------------------------------------------------------
    def _start(self, picks):
        for obj, short, _point in picks:
            self._add(obj, short)
        if self.base is None:
            self.say("⚠ " + self._no_body())
        self.remember_later(self.target if self.editing else self.base)
        self.start_picking()
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.picked:
            self.schedule()

    def _no_body(self):
        return "Make a surface body first (SURFACE > CREATE: Extrude, Patch, Loft...)."

    # -- picking (PickPanel calls these) -----------------------------------------------------
    def wanted(self):
        return "Edge" if self.kind in PICKS_EDGES else "Face"

    def allow(self, obj, short):
        if obj is None:
            return False
        if not short:
            return False
        if not short.startswith(self.wanted()):
            return False
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        if body is None:
            return False
        if body is self.body:
            return obj is self.base or obj is body or self.base is None
        if self._solid_handback(body):
            return True  # an edge of a solid: the SOLID Fillet / Chamfer takes it
        return not self.picked and not self.editing and self._usable_body(body)

    def _solid_handback(self, body):
        """Fusion's Fillet / Chamfer on the SURFACE tab rounds solids too: a click on a
        solid's edge before anything is picked goes to the SOLID dialog."""
        return (
            self.kind in PICKS_EDGES
            and not self.picked
            and not self.editing
            and bodies.has_solid(body)
        )

    def _usable_body(self, body):
        if self.kind == "surface_delete_face":
            return surfmod.body_has_faces(body)
        return surfmod.is_surface_body(body)

    def shown(self):
        if self.base is None or not self.picked:
            return []
        return [(self.base, list(self.picked))]

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if obj is self.base and short in self.picked:
                self.picked.remove(short)
                changed = True
        for obj, short, _point in added:
            changed = self._add(obj, short) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _add(self, obj, short):
        if not short.startswith(self.wanted()):
            return False
        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
        if body is None:
            return False
        if body is not self.body and self._solid_handback(body):
            QtCore.QTimer.singleShot(0, lambda: self._to_solid(obj, short))
            return False
        if body is not self.body:
            if self.picked or self.editing or not self._usable_body(body):
                self.help.setText("This %s works on %s." % (self.title, self.body.Label))
                return False
            self.switch_body(body, body.Tip)
            pickpanel.activate(body)
        name = self._name_on_base(obj, short)
        if not name:
            self.help.setText("That is not on %s before this step." % self.body.Label)
            return False
        if name in self.picked:
            self.picked.remove(name)  # clicked again: dropped
        else:
            self.picked.append(name)
        return True

    def _to_solid(self, obj, short):
        """Close this dialog and open the SOLID Fillet / Chamfer with the solid's edge."""
        if self._closed:
            return
        try:
            from . import fillet_ui

            panel_class = (
                fillet_ui.ChamferPanel if self.kind == "surface_chamfer" else fillet_ui.FilletPanel
            )
            self.reject()
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(obj, [short])
            fillet_ui.start(panel_class)
        except Exception as exc:
            warn("%s: could not hand the edge to the solid %s: %s" % (self.title, self.title, exc))

    def _name_on_base(self, obj, short):
        base = self.base
        if base is None:
            return None
        if obj is base or obj is self.body:
            try:
                base.Shape.getElement(short)
                return short
            except Exception:
                return None
        try:
            item = obj.Shape.getElement(short)
        except Exception:
            return None
        items = base.Shape.Faces if short.startswith("Face") else base.Shape.Edges
        prefix = "Face" if short.startswith("Face") else "Edge"
        for i, other in enumerate(items, start=1):
            try:
                if other.isSame(item) or (
                    (other.CenterOfMass - item.CenterOfMass).Length < 1e-5
                    and abs(_size(other) - _size(item)) < 1e-6 * max(1.0, _size(item))
                ):
                    return "%s%d" % (prefix, i)
            except Exception:
                continue
        return None

    def activate(self, name):
        self.selection.set_active(True)

    def clear_field(self, name):
        if self.picked:
            self.picked = []
            self._sync()
            self._picks_updated()

    def _picks_updated(self, schedule=True):
        count = len(self.picked)
        what = "edge" if self.kind in PICKS_EDGES else "face"
        self.selection.set_text(
            "%d %s%s" % (count, what, "" if count == 1 else "s") if count else ""
        )
        self.help.setText(
            HINTS[self.kind] if not count else "Click more to add, or a picked one to drop it."
        )
        self._update_arrow()
        if schedule:
            self.schedule()

    # -- values -------------------------------------------------------------------------------
    def _collect(self):
        for key, (field, _caption) in self.fields.items():
            self.options[key] = field.value()
        if self.tangent is not None:
            self.options["tangent_chain"] = self.tangent.isChecked()
        if self.kind == "surface_fillet":
            self.options["radius_type"] = self.radius_type.currentData() or "constant"
        if self.kind == "surface_chamfer":
            self.options["chamfer_type"] = self.chamfer_type.currentData()
            self.options["angle"] = self.angle.value()
            self.options["flip"] = self.flip.isChecked()

    def _typed(self):
        if self._closed:
            return
        key = self.main_key()
        if self.arrows and key in self.fields:
            self.arrows[0].set_distance(self.fields[key][0].value())
        self.schedule()

    def _changed(self):
        if not self._closed:
            self.schedule()

    def _dragged(self, value, released=False):
        key = self.main_key()
        if self.kind != "surface_press_pull":
            value = max(0.01, value)
        value = round(value, 2)
        self.fields[key][0].set_value(value)
        self.options[key] = value
        self.schedule()

    # -- the arrow ----------------------------------------------------------------------------
    def _remove_arrow(self):
        for arrow in self.arrows:
            try:
                arrow.remove()
            except Exception:
                pass
        self.arrows = []

    def _update_arrow(self):
        self._remove_arrow()
        if self._closed or self.base is None or not self.picked or not self.fields:
            return
        try:
            spot = self._arrow_spot()
            if spot is None:
                return
            origin, direction = spot
            place = self.body.getGlobalPlacement()
            origin = place.multVec(origin)
            direction = place.Rotation.multVec(direction)
            key = self.main_key()
            value = float(self.fields[key][0].value())
            view = Gui.ActiveDocument.ActiveView
            from .taskui import handle_size_at

            size = handle_size_at(view, origin)
            arrow = pickpanel.Arrow(
                origin,
                direction,
                value,
                size,
                on_drag=lambda d: self._dragged(d),
                on_release=lambda d: self._dragged(d, True),
            )
            self.arrows.append(arrow)
            field = self.fields[key][0]
            self.value_boxes.attach(
                arrow, "value", lambda: field.widget.text(), lambda text: self._box(text)
            )
        except Exception as exc:
            warn("%s arrow unavailable: %s" % (self.title, exc))

    def _arrow_spot(self):
        """(point, direction) in body coordinates: a picked face's centre and normal, or a
        picked edge's middle, pointing out between its two faces."""
        shape = self.base.Shape
        elem = shape.getElement(self.picked[0])
        if elem.ShapeType == "Face":
            u0, u1, v0, v1 = elem.ParameterRange
            normal = elem.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            point = elem.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            return point, App.Vector(normal).normalize()
        mid = elem.valueAt((elem.FirstParameter + elem.LastParameter) / 2.0)
        direction = App.Vector()
        for face in surfmod.faces_of_edge(shape, elem):
            try:
                u, v = face.Surface.parameter(mid)
                direction = direction + App.Vector(face.normalAt(u, v))
            except Exception:
                pass
        if direction.Length < 1e-9:
            return None
        return mid, direction.normalize()

    def _box(self, text):
        """A value or a formula typed in the box beside the arrow: as if typed in the field."""
        try:
            self.formula_inputs[self.main_key()].take(text)
        except Exception as exc:
            self.error = str(exc)
            self.show_status()

    # -- preview ------------------------------------------------------------------------------
    def _preview(self):
        if self._closed or self.base is None:
            return
        self._collect()
        if not self.picked:
            self.error = None
            if self.target is not None and not self.editing:
                target, self.target = self.target, None
                self._looks.restore()
                self._ghost = False
                bodies.remove_step(target)
                self.quiet_recompute()
                self.prepare_display()
            self.show_preview(False)
            self.show_status()
            return
        try:
            surfmod.check_picks(self.kind, self.base.Shape, self.picked)
            core.check_values(self.kind, self.options)
            result = surfmod.preview(self.kind, self.base.Shape, self.picked, self.options)
            if self.kind == "surface_merge":
                self.message_text = surfmod.merge_faces(self.base.Shape, self.picked)[1]
            del result
        except core.SurfaceModifyError as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.error = None
        if self.target is None:
            self.target = surfmod.make(
                self.kind, self.body, self.base, self.picked, self.options, check=False
            )
        else:
            surfmod.apply(self.target, self.base, self.picked, self.options)
        self._apply_formulas()
        self.quiet_recompute()
        self.follow_later()
        self.show_preview(True)
        self.show_status()

    def show_status(self):
        if self.formula_errors:
            self.say("⚠ " + list(self.formula_errors.values())[0])
            return
        if self.base is None:
            self.say("⚠ " + self._no_body())
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        if self.target is None or not self.picked:
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
        self.say(self.message_text if self.kind == "surface_merge" else "")

    # -- OK / Cancel ----------------------------------------------------------------------------
    def accept(self):
        try:
            self._timer.stop()
            if self.base is None:
                self.say("⚠ " + self._no_body())
                return False
            if not self.picked:
                self.say("⚠ " + HINTS[self.kind])
                return False
            self._preview()
            obj = self.target
            if self.error or self.formula_errors or obj is None:
                self.show_status()
                return False
            state = list(obj.State)
            if "Invalid" in state or "Error" in state:
                self.show_status()
                return False
            return self.finish_ok()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            return False

    def cleanup(self):
        self._remove_arrow()
        self.value_boxes.discard()
        super().cleanup()


def _size(shape):
    try:
        return shape.Area if shape.ShapeType == "Face" else shape.Length
    except Exception:
        return 0.0


# -- starting ---------------------------------------------------------------------------------
def open_panel(kind, body=None, picks=None, doc=None):
    """Open the dialog of `kind` (no transaction is open yet)."""
    doc = doc or App.ActiveDocument
    if doc is None:
        return None
    picks = list(picks or [])
    if body is None:
        for obj, _short, _point in picks:
            body = obj if bodies.is_body(obj) else bodies.body_of(obj)
            if body is not None:
                break
    if body is None:
        body = shown_surface_body(doc)
    if body is None:
        commands.tell(
            "%s works on surface bodies here: make one first (SURFACE > CREATE: Extrude, "
            "Patch, Loft...)." % core.TITLES[kind]
        )
        return None
    pickpanel.activate(body)
    Gui.Selection.clearSelection()
    panel = None
    try:
        panel = SurfaceModifyPanel(doc, kind, body=body, picks=picks)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("%s (surface) started with %d pick(s)" % (core.TITLES[kind].lower(), len(picks)))
    return panel


def start(kind):
    """A command of this module (Merge): the selection made before it are its picks."""
    try:
        doc = App.ActiveDocument
        picks = surface_picks(_selection_picks(doc)) if doc is not None else []
        if not commands.finish_open_dialog():
            return None
        return open_panel(kind, picks=picks)
    except Exception as exc:
        warn("%s could not start: %s" % (core.TITLES[kind], exc))
        return None


def take_blend(kind, selection_picks, solid_ready):
    """fillet_ui.start hands over here (True) when the edges picked are on a surface body,
    or when nothing is picked and the SURFACE tab shows a surface body (or there is no solid
    to round at all). kind: "surface_fillet" | "surface_chamfer"."""
    picks = surface_picks(selection_picks)
    doc = App.ActiveDocument
    if picks:
        open_panel(kind, picks=[p for p in picks if p[1].startswith("Edge")], doc=doc)
        return True
    if selection_picks:
        return False
    body = shown_surface_body(doc) if doc is not None else None
    if body is None:
        return False
    if current_tab() == "surface" or not solid_ready:
        open_panel(kind, body=body, doc=doc)
        return True
    return False


def take_press_pull(doc, picks):
    """Press Pull hands over here when the first picks are on a surface body: faces are
    pushed or pulled (surface_press_pull), edges filleted (as Press Pull does on a solid),
    the face of a surface Fillet / Chamfer opens that step to change its size."""
    picks = surface_picks(picks)
    if not picks:
        return False
    faces = [p for p in picks if p[1].startswith("Face")]
    for obj, short, _point in faces:
        step = surfmod.blend_step_of_face(obj, short)
        if step is not None:  # a fillet's (chamfer's) face: change that fillet (Fusion)
            edit(step)
            return True
    if faces:
        open_panel("surface_press_pull", picks=faces, doc=doc)
    else:
        open_panel("surface_fillet", picks=picks, doc=doc)
    return True


def edit(feature):
    """Timeline double-click on a surface-4 step."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        kind = surfmod.kind_of(feature)
        Gui.Control.showDialog(SurfaceModifyPanel(feature.Document, kind, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


# -- the view provider -------------------------------------------------------------------------
class ViewProviderSurfaceModify:
    """Saved as "sciforge.surfmod_ui.ViewProviderSurfaceModify": never rename."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        try:
            kind = surfmod.kind_of(self.Object)
            return ui_icon_path(core.TIMELINE_KINDS.get(kind, ("", "surface_body"))[1])
        except Exception:
            return ui_icon_path("surface_body")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        QtCore.QTimer.singleShot(0, lambda: edit(vobj.Object))
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


# -- commands ---------------------------------------------------------------------------------
class MergeCommand:
    def GetResources(self):
        return {
            "MenuText": "Merge",
            "ToolTip": "Merge faces next to each other on one surface body into one face "
            "(faces that lie on one surface, like the pieces Split Face leaves)",
            "Pixmap": ui_icon_path("surfmod_merge"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start("surface_merge")
        except Exception as exc:
            warn("Merge could not start: %s" % exc)


COMMANDS = {"SciForge_SurfaceMerge": MergeCommand}
EDITORS = {"SciForge::" + t: edit for t in core.KIND_BY_TYPE}
