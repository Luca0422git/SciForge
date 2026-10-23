# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > CREATE > Rest: Fusion's flat landing on a curved wall (plastic_rest.py does the
geometry).

Click a closed sketch profile drawn on a plane that cuts the part. The rest makes the
profile a flat face on that plane, backed by a wall Thickness thick: the material that
bulges past the plane is cut away, a pedestal fills where the part lies below it (its side
walls drafted by the Draft Angle). Flip turns the inside round. Thickness and Draft Angle
come from the plastic rule until you type over them; the blue arrow drags the thickness.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, curve_pick, curves, extrude, log, plastic, plastic_rest as pr
from . import preview, profile_pick, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

safe = curve_pick.safe("rest")


class RestPanel(Panel):
    title = "Rest"
    icon = "pl_rest"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Rest" if feature is None else "Edit Rest")
        RestPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.editing = feature is not None
        self.target = feature
        self.refs = []
        self.error = ""
        self.dirty = False
        self.arrow = None
        self.picker = None
        self.observer = None
        self._quiet = False
        self.value_boxes = ValueBoxes(self, default="thickness")
        self.active_box = "profile"  # the selection box that takes the clicks
        self.picked_body = None  # the body picked in the Body box (else found)
        self.body = commands.find_body() if feature is None else curves.owner_body(feature)
        rule = plastic.rule_for_body(self.body)
        self.rule_body = self.body  # the body whose rule the linked values come from
        self.options = pr.default_options(rule)
        if feature is not None:
            try:
                self.refs, read = pr.read(feature)
                self.options.update(read)
                # the values still linked to the rule show what the rest is built with now
                # (the rule may have changed since the rest was made); without a rule the
                # stored values are what it is built with
                assigned = plastic.rule_for_body(self.body, fallback=False)
                if assigned is not None:
                    self.options = pr.apply_rule(self.options, assigned)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_arrow()
        else:
            self._start()

    def _build_form(self):
        form = self.layout
        self.field = SelectionField(self, "profile", "Select profile")
        self.field.button.setObjectName("SciForgeRest_profile")
        self.field.clear.setObjectName("SciForgeRest_clear_profile")
        self.field.set_active(True)
        form.addRow("Profile", self.field.widget)
        # Fusion's Rest takes a body too: found by itself (the body the profile lies over),
        # or picked (click the box, then the body)
        self.body_field = SelectionField(self, "body", "Auto")
        self.body_field.button.setObjectName("SciForgeRest_pick_body")
        self.body_field.clear.setObjectName("SciForgeRest_clear_body")
        form.addRow("Body", self.body_field.widget)
        self.body_label = QtWidgets.QLabel("")
        self.body_label.setObjectName("SciForgeRest_body")
        form.addRow("Builds in", self.body_label)
        self.thickness = DistanceField(
            self.options["thickness"], on_change=lambda v: self._typed("thickness")
        )
        self.thickness.widget.setObjectName("SciForgeRest_thickness")
        form.addRow("Thickness", self.thickness.widget)
        self.draft = DistanceField(
            self.options["draft"], unit="deg", on_change=lambda v: self._typed("draft")
        )
        self.draft.widget.setObjectName("SciForgeRest_draft")
        form.addRow("Draft Angle", self.draft.widget)
        self.flip = curve_pick.checkbox("Flip", self.options.get("flip", False))
        self.flip.setObjectName("SciForgeRest_flip")
        self.flip.setToolTip("The other side of the sketch plane is the inside of the part")
        self.flip.toggled.connect(lambda *_a: self._typed("flip"))
        form.addRow("", self.flip)
        self.rule_label = QtWidgets.QLabel("")
        self.rule_label.setObjectName("SciForgeRest_rule")
        self.rule_label.setWordWrap(True)
        form.addRow(self.rule_label)
        self.finish_layout()
        lines = self.message.fontMetrics().lineSpacing()
        self.message.setMinimumHeight(lines * 3 + 4)

    def _show_options(self):
        self._quiet = True
        try:
            self.thickness.set_value(float(self.options["thickness"]))
            self.draft.set_value(float(self.options["draft"]))
            self.flip.setChecked(bool(self.options.get("flip")))
        finally:
            self._quiet = False
        self._show_rule()

    def _show_rule(self):
        """Which plastic rule the thickness and draft come from (the library's default
        when the body's component has none, said so)."""
        try:
            component = plastic.components.container_of(self.rule_body) if self.rule_body else None
            name = plastic.assigned_rule_name(self.doc, component)
            rule = name or ("%s (default; no rule assigned)" % plastic.default_rule_name())
            self.rule_label.setText("Plastic rule: %s" % rule)
        except Exception:
            self.rule_label.setText("")

    def _follow_body_rule(self, body):
        """The rest builds in `body`: its values still linked to the rule come from that
        body's rule (the dialog opened with the active body's)."""
        if body is None or body is self.rule_body:
            return
        self.rule_body = body
        self.options = pr.apply_rule(self.options, plastic.rule_for_body(body))
        self._show_options()

    @safe
    def _typed(self, key):
        if self._quiet:
            return
        links = self.options.setdefault("links", {})
        if key == "thickness":
            self.options["thickness"] = float(self.thickness.value())
            links["thickness"] = False
        elif key == "draft":
            self.options["draft"] = float(self.draft.value())
            links["draft"] = False
        else:
            self.options["flip"] = bool(self.flip.isChecked())
        self._changed(arrow=True)

    def _changed(self, arrow=False):
        self.dirty = True
        self._arrow_due = arrow or getattr(self, "_arrow_due", False)
        self.schedule()

    # -- picking -----------------------------------------------------------------------------------
    def activate(self, name):
        self.active_box = name
        self.field.set_active(name == "profile")
        self.body_field.set_active(name == "body")
        if self.picker is not None:
            self.picker.paused = name != "profile"
        if name == "body":
            self.message.setText("Click the body the rest goes on.")

    def clear_field(self, name):
        if name == "body":
            self.picked_body = None
            self.body_field.set_text("")
            self.activate("profile")
            self._changed(arrow=True)
            return
        self.refs = []
        self._picks_changed()

    def _start(self):
        for obj, short in profile_pick.picks():
            if extrude.is_sketch(obj) and short.startswith("Internal"):
                self.refs.append((obj, short))
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self._refresh_picks()
        if self.refs:
            self._picks_changed()

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        try:
            sketches = []
            for body in pr.bodies.list_bodies(self.doc):
                sketches += profile_pick.candidate_sketches(body)
            extra = [o for o, _ in self.refs if extrude.is_sketch(o)]
            seen, unique = set(), []
            for s in sketches + extra:
                if s.Name not in seen:
                    seen.add(s.Name)
                    unique.append(s)
            self.picker = profile_pick.ProfilePicker(
                Gui.ActiveDocument.ActiveView,
                unique,
                lambda obj, sub: QtCore.QTimer.singleShot(0, lambda: self._region(obj, sub)),
                occluder=None,
                clicks_through=True,
            )
            self.picker.set_selected({(o.Name, s) for o, s in self.refs})
        except Exception as exc:
            warn("Rest: profile shading unavailable: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        if self.picker is not None:
            try:
                self.picker.remove()
            except Exception:
                pass
            self.picker = None

    def _selection_changed(self):
        if self._closed:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            Gui.Selection.clearSelection()
            if self.active_box == "body" and picks:
                obj = picks[0][0]
                body = obj if pr.bodies.is_body(obj) else pr.bodies.body_of(obj)
                if body is None or not pr.bodies.has_solid(body):
                    self.message.setText("⚠ Click a solid body for the rest.")
                    return
                self.picked_body = body
                self.body_field.set_text(body.Label)
                self.activate("profile")
                self.message.setText("")
                self._changed(arrow=True)
                return
            for obj, short in picks:
                if extrude.is_sketch(obj) and short.startswith("Internal"):
                    self._region(obj, short)
        except Exception as exc:
            warn("rest pick: %s" % exc)

    @safe
    def _region(self, obj, sub):
        if self._closed:
            return
        if self.arrow is not None and _dragging(self.arrow):
            return
        if not extrude.is_sketch(obj):
            self.message.setText("⚠ A rest needs a closed sketch profile.")
            return
        if self.refs and self.refs[0][0] is not obj:
            self.message.setText(
                "⚠ The profiles must be in one sketch. Clear the box to start with another one."
            )
            return
        key = (obj.Name, sub)
        if key in {(o.Name, s) for o, s in self.refs}:
            self.refs = [r for r in self.refs if (r[0].Name, r[1]) != key]
        else:
            self.refs.append((obj, sub))
        self._picks_changed()

    def _refresh_picks(self):
        n = len(self.refs)
        self.field.set_text("%d profile%s" % (n, "" if n == 1 else "s") if n else "")
        if self.picker is not None:
            try:
                self.picker.set_selected({(o.Name, s) for o, s in self.refs})
            except Exception:
                pass

    def _picks_changed(self):
        self._refresh_picks()
        if not self.refs:
            if self.target is not None and not self.editing:
                pr.bodies.remove_step(self.target)
                self.target = None
                self.schedule()
            self._remove_arrow()
            self.error = "Pick the rest's profile." if self.editing else ""
            self.message.setText(("⚠ " + self.error) if self.error else "")
            return
        self._changed(arrow=True)

    # -- preview -----------------------------------------------------------------------------------
    def _recompute(self):
        if self._closed:
            return
        try:
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            if getattr(self, "_arrow_due", False) and not (
                self.arrow is not None and _dragging(self.arrow)
            ):
                self._arrow_due = False
                self._make_arrow()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.refs:
            return
        try:
            body = curves.owner_body(self.target) if self.target is not None else None
            if self.picked_body is not None and body is not self.picked_body:
                if self.target is not None and not self.editing:
                    pr.bodies.remove_step(self.target)  # the preview moves to that body
                    self.target = None
                    body = None
                elif self.target is None:
                    body = None
                else:
                    raise pr.RestError(
                        "An existing rest stays in its body: clear the Body box, or make a "
                        "new rest."
                    )
            if body is None:
                body = self.picked_body or pr.body_under(self.doc, self.refs) or self.body
            if body is None:
                raise pr.RestError("The profile does not lie over a body.")
            self.body_label.setText(body.Label)
            self._follow_body_rule(body)
            self.target = pr.make(body, self.refs, self.options, feature=self.target)
            self.error = ""
        except pr.RestError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This rest cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = preview.failure(self.target)
        self.message.setText("⚠ " + text if text else "")

    # -- the thickness arrow -----------------------------------------------------------------------
    def _remove_arrow(self):
        if self.arrow is not None:
            try:
                self.arrow.remove()
            except Exception:
                pass
            self.arrow = None

    def _make_arrow(self):
        if self._closed:
            return
        self._remove_arrow()
        if not self.refs or self.target is None or self.error:
            return
        try:
            faces = pr.profile_faces(self.refs)
            _sketch, origin, normal = pr.profile_plane(self.refs)
            base = self.target.BaseFeature
            shape = curves.to_global(base.Shape, base)
            inward = pr.inward_direction(shape, origin, normal, bool(self.options.get("flip")))
            centre = faces[0].CenterOfMass
            size = max(3.0, min(10.0, faces[0].BoundBox.DiagonalLength * 0.3))
            # the arrow points out of the flat face; dragging it in thickens the wall
            self.arrow = ArrowDragger(
                centre,
                inward * -1.0,
                float(self.options["thickness"]),
                size,
                on_drag=self._dragged,
                on_release=self._dragged,
            )
            self.value_boxes.attach(
                self.arrow,
                "thickness",
                lambda: self.thickness.widget.text(),
                lambda text: self._box_typed(text),
            )
        except Exception as exc:
            warn("rest arrow unavailable: %s" % exc)

    def _box_typed(self, text):
        if self._closed:
            return
        try:
            value = self.thickness.parse(text.strip().lstrip("="))
        except ValueError as exc:
            self.message.setText("⚠ " + str(exc))
            return
        self.thickness.take(value)

    @safe
    def _dragged(self, distance):
        value = max(0.1, abs(round(distance, 2)))
        self._quiet = True
        try:
            self.thickness.set_value(value)
        finally:
            self._quiet = False
        self.options["thickness"] = value
        self.options.setdefault("links", {})["thickness"] = False
        self._changed()

    # -- OK / Cancel -------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Rest OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.refs:
            self.message.setText("⚠ Pick a closed sketch profile first.")
            return False
        self._timer.stop()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        for obj, _ in self.refs[:1]:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(curves.owner_body(feature))
        log("Rest done")
        return True

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
            for body in pr.bodies.list_bodies(self.doc):
                extrude.show_tip(body)
        except Exception as exc:
            warn("Rest Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Rest Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_arrow()
        self.value_boxes.discard()
        super().cleanup()


def _dragging(arrow):
    try:
        return bool(arrow.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderRest:
    """View provider of the Rest step (saved as "sciforge.plastic_rest_ui.ViewProviderRest":
    never rename)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("pl_rest")

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


def _start():
    try:
        if not commands.finish_open_dialog():
            return
        if App.ActiveDocument is None:
            commands.tell("Open or create a design first.")
            return
        if not pr.bodies.solid_bodies(App.ActiveDocument):
            commands.tell("Rest needs a part: make the part first, then sketch the profile.")
            return
        Gui.Control.showDialog(RestPanel(App.ActiveDocument))
        log("rest started")
    except Exception as exc:
        warn("Rest failed to start: %s" % exc)


class RestCommand:
    def GetResources(self):
        return {
            "MenuText": "Rest",
            "ToolTip": "A flat landing on a curved wall from a closed sketch profile: cuts "
            "where the part bulges past the plane, fills where it lies below",
            "Pixmap": ui_icon_path("pl_rest"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start()


def edit(feature):
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(RestPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Rest": RestCommand}
EDITORS = {"SciForge::Rest": edit}
