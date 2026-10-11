# SPDX-License-Identifier: LGPL-2.1-or-later
"""Draft with Fusion's dialog (type Fixed Plane).

Pressing Draft with nothing selected opens the dialog, which waits for the fixed plane:
click a flat face of the part, or one of the big origin squares shown while the Plane
box is blue (or a plane in the browser). The pull direction is shown as a blue arrow
across the plane; Flip turns it round. The Faces box then takes the clicks: click the
faces to tilt (click one again to drop it); Tangent Chain picks the faces that continue a
picked one smoothly. Drag the blue curved handle or type the angle; a positive angle
makes the part narrower toward the pull direction. Faces that cannot be tilted do not
light up; a draft that cannot be made is explained in the dialog and OK waits.

Built on FreeCAD's PartDesign::Draft (see drafting.py). Double-click the step in the
timeline to edit it. Fusion's Parting Line type and two-sided drafts split faces, which
FreeCAD's Draft cannot do: those choices are shown greyed with the reason.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, drafting, hole_common, log, pickpanel, preview, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .taskui import DistanceField

PLANE_HELP = "Click a flat face or an origin plane: the faces turn about it."
FACES_HELP = "Click the faces to draft (click one again to drop it)."
NO_SPLIT = "FreeCAD's draft cannot split faces at a line, so this is not available yet"


class PullArrow:
    """A blue arrow (not draggable) showing the pull direction, like Fusion's."""

    def __init__(self, origin, direction, length):
        from pivy import coin

        self.view = Gui.ActiveDocument.ActiveView
        self.root = coin.SoSeparator()
        place = coin.SoTransform()
        place.translation.setValue(origin.x, origin.y, origin.z)
        rot = App.Rotation(App.Vector(0, 1, 0), direction)  # cylinders/cones run along +Y
        place.rotation.setValue(*rot.Q)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.30, 0.62, 0.95)
        material.emissiveColor.setValue(0.10, 0.25, 0.45)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        shaft = coin.SoSeparator()
        move = coin.SoTranslation()
        move.translation.setValue(0, length * 0.4, 0)
        cylinder = coin.SoCylinder()
        cylinder.radius = length * 0.03
        cylinder.height = length * 0.8
        shaft.addChild(move)
        shaft.addChild(cylinder)
        head = coin.SoSeparator()
        move2 = coin.SoTranslation()
        move2.translation.setValue(0, length * 0.9, 0)
        cone = coin.SoCone()
        cone.bottomRadius = length * 0.09
        cone.height = length * 0.2
        head.addChild(move2)
        head.addChild(cone)
        for node in (pick, place, material, shaft, head):
            self.root.addChild(node)
        hole_common.on_top(self.root)
        self.view.getSceneGraph().addChild(self.root)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class DraftPanel(pickpanel.PickPanel):
    title = "Draft"
    icon = "draft"
    last = None  # the most recent panel (tests and diagnostics)

    def __init__(self, doc, feature=None, picks=None, body=None):
        super().__init__(doc, "Draft" if feature is None else "Edit Draft")
        DraftPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.plane_ref = None  # (object, element name or "")
        self.picked = []  # faces the user clicked, on self.base
        self.active = "plane"
        self.options = drafting.default_options()
        self.formula = ""
        self.formula_error = ""
        self.handle = None
        self.arrow = None
        self.planes = None  # the origin squares while the Plane box takes the clicks
        self._chains = {}
        if feature is not None:
            self.body = drafting.owner_body(feature)
            base, plane_ref, names, options, formula = drafting.read(feature)
            self.base = base
            self.plane_ref = plane_ref
            self.picked = list(names)
            self.options.update(options)
            self.formula = formula or ""
            self.active = "faces" if plane_ref is not None else "plane"
        else:
            from . import shell_ui

            self.body, self.base = shell_ui.start_body(body)
        self._build()
        self.finish_layout()
        try:
            self._start(picks or [])
        except Exception as exc:  # never leave a half-open dialog without a reason
            self.say("⚠ %s" % exc)
            warn("Draft could not start picking: %s" % exc)

    # -- layout -------------------------------------------------------------------------
    def _build(self):
        self.type = pickpanel.combo(
            [
                ("Fixed Plane", "fixed", True, "The faces turn about a plane you pick"),
                ("Parting Line", "parting", False, NO_SPLIT),
            ],
            "fixed",
        )
        self.layout.addRow("Type", self.type)
        row = QtWidgets.QWidget()
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(4)
        self.plane_box = hole_common.SelectionField(self, "plane", "Select")
        self.flip = QtWidgets.QToolButton()
        self.flip.setText("⇅")
        self.flip.setCheckable(True)
        self.flip.setChecked(bool(self.options.get("flip")))
        self.flip.setToolTip("Flip the pull direction")
        self.flip.toggled.connect(self._flipped)
        line.addWidget(self.plane_box.widget, 1)
        line.addWidget(self.flip)
        self.layout.addRow("Plane", row)
        self.faces_box = hole_common.SelectionField(self, "faces", "Select")
        self.layout.addRow("Faces", self.faces_box.widget)
        self.help = QtWidgets.QLabel(PLANE_HELP)
        self.help.setWordWrap(True)
        self.help.setStyleSheet("color: #9aa4b1;")
        self.layout.addRow(self.help)
        self.tangent = QtWidgets.QCheckBox()
        self.tangent.setChecked(bool(self.options.get("tangent", True)))
        self.tangent.setToolTip("Also draft the faces that continue a picked face smoothly")
        self.tangent.toggled.connect(self._tangent_toggled)
        self.layout.addRow("Tangent Chain", self.tangent)
        self.sides = pickpanel.combo(
            [
                ("One Side", "one", True, "Every picked face turns the same way"),
                ("Two Sides", "two", False, NO_SPLIT),
                ("Symmetric", "symmetric", False, NO_SPLIT),
            ],
            "one",
        )
        self.layout.addRow("Draft Sides", self.sides)
        self.angle = DistanceField(self.options["angle"], unit="deg", on_change=self._typed)
        self.angle.widget.setProperty("minimum", -89.9)
        self.angle.widget.setProperty("maximum", 89.9)
        self.layout.addRow("Angle", self.angle.widget)
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        self._formula_input = preview.FormulaInput(self, "angle", self.angle)
        self._show_formula()

    # -- starting -----------------------------------------------------------------------
    def _start(self, picks):
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        planes = [(o, s) for o, s in picks if not s and drafting.is_plane_object(o)]
        faces = [(o, s) for o, s in picks if s.startswith("Face")]
        for obj, short in planes[:1]:
            self._set_plane((obj, ""))
        for obj, short in faces:
            self._add_face(obj, short)
        self.start_picking()
        self._activate(self.active if self.plane_ref is not None else "plane", schedule=False)
        self._picks_updated(schedule=False)
        if self.target is not None:
            self.show_preview(True)
        if self.plane_ref is not None and self.picked:
            self.schedule()

    # -- boxes ----------------------------------------------------------------------------
    def activate(self, name):
        self._activate(name)

    def _activate(self, name, schedule=True):
        self.active = name
        self.plane_box.set_active(name == "plane")
        self.faces_box.set_active(name == "faces")
        self.help.setText(PLANE_HELP if name == "plane" else FACES_HELP)
        if name == "plane":
            self._show_planes()
        else:
            self._hide_planes()

    def clear_field(self, name):
        if name == "plane":
            if self.plane_ref is not None:
                self.plane_ref = None
                self._activate("plane")
        elif self.picked:
            self.picked = []
        self._sync()
        self._picks_updated()

    def _show_planes(self):
        if self.planes is not None or self.body is None or self._closed:
            return
        try:
            from . import sketch_ui

            self.planes = sketch_ui.PlanePicker(
                Gui.ActiveDocument.ActiveView,
                self.body,
                lambda plane: QtCore.QTimer.singleShot(0, lambda: self._square_clicked(plane)),
            )
        except Exception as exc:
            self.planes = None
            warn("Draft: origin planes unavailable: %s" % exc)

    def _hide_planes(self):
        if self.planes is not None:
            self.planes.remove()
            self.planes = None

    def _square_clicked(self, plane):
        try:
            if self._closed or self.active != "plane":
                return
            self._set_plane((plane, ""))
            self._sync()
            self._picks_updated()
        except Exception as exc:
            warn("Draft plane: %s" % exc)

    # -- the picks (PickPanel calls these) ---------------------------------------------------
    def chain(self, name):
        if not self.tangent.isChecked() or self.base is None:
            return [name]
        if name not in self._chains:
            try:
                self._chains[name] = drafting.tangent_faces(self.base.Shape, [name])
            except Exception:
                self._chains[name] = [name]
        return self._chains[name]

    def names(self):
        """The faces drafted: the picks with their tangent chains (never the plane face)."""
        found = []
        plane_face = self.plane_ref[1] if self.plane_ref is not None else None
        for pick in self.picked:
            for name in self.chain(pick):
                if name not in found and name != plane_face:
                    found.append(name)
        return found

    def shown(self):
        entries = []
        if self.base is None:
            return entries
        names = list(self.names())
        if self.plane_ref is not None:
            obj, sub = self.plane_ref
            if sub and obj is self.base:
                names = [sub] + names
            elif not sub:
                entries.append((obj, []))
        if names:
            entries.insert(0, (self.base, names))
        return entries

    def _pull(self):
        if self.plane_ref is None:
            return None
        try:
            return drafting.pull_direction(self.plane_ref, self.flip.isChecked())
        except drafting.DraftError:
            return None

    def _in_body(self, obj):
        if obj is None or self.body is None:
            return False
        if obj.TypeId == "App::Plane":
            return any(o is obj for o in self.body.Origin.OriginFeatures)
        return drafting.owner_body(obj) is self.body

    def _flat(self, obj, short):
        try:
            return obj.Shape.getElement(short).Surface.__class__.__name__ == "Plane"
        except Exception:
            return False

    def allow(self, obj, short):
        if self.base is None or obj is None:
            return False
        if not short:
            return drafting.is_plane_object(obj) and self._in_body(obj)
        if not short.startswith("Face") or obj.Name != self.base.Name:
            return False
        if self.active == "plane":
            return self._flat(obj, short)
        pull = self._pull()
        if pull is None:
            return True
        return not drafting.why_not(self.base.Shape, short, pull, self.plane_ref)

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _point in dropped:
            if (
                self.plane_ref is not None
                and obj is self.plane_ref[0]
                and short == (self.plane_ref[1] or "")
            ):
                if short:  # a whole plane object stays (it is only shown selected)
                    self.plane_ref = None
                    self._activate("plane", schedule=False)
                    changed = True
            elif obj is self.base and short.startswith("Face"):
                changed = self._drop(short) or changed
        for obj, short, _point in added:
            if not short:
                if drafting.is_plane_object(obj) and self._in_body(obj):
                    changed = self._set_plane((obj, "")) or changed
            elif short.startswith("Face") and obj is self.base:
                if self.active == "plane":
                    if self._flat(obj, short):
                        changed = self._set_plane((obj, short)) or changed
                else:
                    changed = self._add_face(obj, short) or changed
        if changed:
            self._picks_updated(schedule=False)
        return changed

    def _set_plane(self, ref):
        obj, sub = ref
        if obj is not self.base and sub:
            return False
        if self.plane_ref is not None and self.plane_ref[0] is obj and self.plane_ref[1] == sub:
            return False
        self.plane_ref = ref
        self.picked = [p for p in self.picked if p != sub]
        if self.active == "plane":
            self._activate("faces", schedule=False)
        return True

    def _add_face(self, obj, short):
        name = pickpanel.match_face(self.base, obj, short) if obj is not self.base else short
        if not name:
            return False
        pull = self._pull()
        if pull is not None:
            reason = drafting.why_not(self.base.Shape, name, pull, self.plane_ref)
            if reason:
                self.help.setText(reason)
                return False
        if name in self.picked or name in self.names():
            return False
        self.picked.append(name)
        return True

    def _drop(self, name):
        before = len(self.picked)
        self.picked = [p for p in self.picked if name not in self.chain(p)]
        return len(self.picked) != before

    def _picks_updated(self, schedule=True):
        if self.plane_ref is not None:
            self.plane_box.set_text(drafting.plane_label(self.plane_ref))
        else:
            self.plane_box.set_text("")
        count = len(self.names())
        self.faces_box.set_text("%d face%s" % (count, "" if count == 1 else "s") if count else "")
        self._update_handles()
        if schedule:
            self.schedule()

    def _tangent_toggled(self, *_):
        self.options["tangent"] = self.tangent.isChecked()
        self._chains = {}
        self._sync()
        self._picks_updated()

    def _flipped(self, *_):
        self.options["flip"] = self.flip.isChecked()
        self._update_handles()
        self.schedule()

    # -- values -------------------------------------------------------------------------------
    def _typed(self, value):
        self.options["angle"] = value
        if self.handle is not None:
            try:
                self.handle.set_angle(value)
            except Exception:
                pass
        self.schedule()

    def _turned(self, degrees):
        value = round(max(-89.9, min(89.9, degrees)), 1)
        self.options["angle"] = value
        self.angle.set_value(value)
        if self.formula:
            self.formula = ""  # a drag gives a plain number
            self._show_formula()
        self.schedule()

    def _collect(self):
        self.options["flip"] = self.flip.isChecked()
        self.options["tangent"] = self.tangent.isChecked()
        if not self.formula:
            self.options["angle"] = self.angle.value()

    def formula_typed(self, key, text, value):
        self.formula_error = ""
        self.formula = text
        self._show_formula()
        self._typed(value)

    def formula_cleared(self, key):
        self.formula_error = ""
        if self.formula:
            self.formula = ""
            self._show_formula()
        self._typed(self.angle.value())

    def formula_failed(self, key, text):
        self.formula_error = text
        self.show_status()

    def _show_formula(self):
        self.formula_label.setText("Angle = %s" % self.formula if self.formula else "")

    # -- handles ----------------------------------------------------------------------------
    def _remove_handles(self):
        for item in (self.handle, self.arrow):
            if item is not None:
                try:
                    item.remove()
                except Exception:
                    pass
        self.handle = self.arrow = None

    @property
    def arrows(self):
        return [self.handle] if self.handle is not None else []

    def _update_handles(self):
        self._remove_handles()
        if self.base is None or self.plane_ref is None or self._closed:
            return
        try:
            self._collect()
            placement = self.body.getGlobalPlacement() if self.body else App.Placement()
            shape = self.base.Shape
            diag = shape.BoundBox.DiagonalLength
            pull = drafting.pull_direction(self.plane_ref, self.options["flip"])
            point, _axis, _out = drafting.plane_frame(self.plane_ref)
            if not self.plane_ref[1]:
                center = shape.BoundBox.Center
                point = center - pull * (center - point).dot(pull)
            self.arrow = PullArrow(
                placement.multVec(point),
                placement.Rotation.multVec(pull),
                max(4.0, min(diag * 0.25, 40.0)),
            )
            frame = drafting.handle_frame(shape, self.plane_ref, self.names(), self.options)
            if frame is None:
                return
            pivot, axis, zero = frame
            from .extrude_ui import AngleDragger

            radius = max(3.0, min(diag * 0.18, 30.0))
            self.handle = AngleDragger(
                placement.multVec(pivot),
                placement.Rotation.multVec(axis),
                placement.Rotation.multVec(zero),
                float(self.options.get("angle", 0.0)),
                radius,
                radius * 0.12,
                on_drag=self._turned,
                on_release=self._turned,
            )
            hole_common.on_top(self.handle.root)
        except Exception as exc:
            warn("Draft handles unavailable: %s" % exc)

    # -- preview --------------------------------------------------------------------------
    def _preview(self):
        if self._closed or self.base is None:
            return
        self._collect()
        if self.formula_error:
            self.show_status()
            return
        names = self.names()
        if self.plane_ref is None or not names:
            self.error = None
            if self.target is not None and not self.editing:
                target, self.target = self.target, None
                self._looks.restore()
                self._ghost = False
                drafting.remove(target)
                self.quiet_recompute()
                self.prepare_display()
            self.show_preview(False)
            self.show_status()
            return
        try:
            drafting.check(self.base.Shape, self.plane_ref, names, self.options)
        except drafting.DraftError as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.error = None
        if self.target is None:
            self.target = drafting.make(
                self.body, self.base, self.plane_ref, names, self.options, formula=self.formula
            )
        else:
            drafting.apply(
                self.target, self.base, self.plane_ref, names, self.options, self.formula
            )
        self.quiet_recompute()
        if _failed(self.target):
            self.error = drafting.friendly(_status(self.target))
        else:
            left = drafting.undrafted(self.base.Shape, self.target.Shape, names)
            if left:
                self.error = (
                    "%s could not be tilted with this plane and angle. Drop %s or try "
                    "another angle." % (", ".join(left), "it" if len(left) == 1 else "them")
                )
        self.show_preview(True)
        self.show_status()

    def show_status(self):
        if self.formula_error:
            self.say("⚠ " + self.formula_error)
            return
        if self.base is None:
            self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
            return
        if self.error:
            self.say("⚠ " + self.error)
            return
        if self.target is None or self.plane_ref is None or not self.picked:
            self.say("")
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
                self.say("⚠ Make a solid first (Create Sketch, then Extrude).")
                return False
            if self.plane_ref is None:
                self.say("⚠ Pick the fixed plane first: a flat face or an origin plane.")
                return False
            if not self.names():
                self.say("⚠ Pick the faces to draft.")
                return False
            self._preview()
            obj = self.target
            if self.formula_error or self.error or obj is None:
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
        self._remove_handles()
        self._hide_planes()
        super().cleanup()


def _failed(obj):
    try:
        state = list(obj.State)
    except Exception:
        return False
    return "Invalid" in state or "Error" in state


def _status(obj):
    """FreeCAD's error text of a failed step ('' when it gives none: Draft often does)."""
    try:
        return obj.getStatusString() or ""
    except Exception:
        return ""


# -- command -----------------------------------------------------------------------------
class DraftCommand:
    def GetResources(self):
        return {
            "MenuText": "Draft",
            "ToolTip": "Tilt faces so a mould can be pulled off: pick the fixed plane, then "
            "the faces, drag or type the angle, with a live preview",
            "Pixmap": ui_icon_path("draft"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Draft could not start: %s" % exc)


def start():
    """Run Draft: a plane / faces selected beforehand are taken at once; with nothing
    selected the dialog opens and waits for the fixed plane."""
    selection = pickpanel.capture_selection()
    picked_body = pickpanel.selected_body()
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if doc is None:
        return None
    from . import shell_ui

    body, base = shell_ui.start_body(picked_body)
    if base is None:
        commands.tell("Draft needs a solid: make one first (Create Sketch, then Extrude).")
        return None
    pickpanel.activate(body)
    pickpanel.reselect(selection)
    picks = [(obj, short) for obj, short, _p in pickpanel.selection_entries(doc)]
    panel = None
    try:
        panel = DraftPanel(doc, picks=picks, body=body)
        Gui.Control.showDialog(panel)
    except Exception:
        if panel is not None and not panel._closed:
            try:
                panel.reject()
            except Exception:
                pass
        raise
    log("draft started with %d pick(s)" % len(picks))
    return panel


def edit_draft(obj):
    """Timeline double-click: the Draft dialog on the existing draft."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(DraftPanel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


COMMANDS = {"SciForge_Draft": DraftCommand}
EDITORS = {drafting.NATIVE: edit_draft}
