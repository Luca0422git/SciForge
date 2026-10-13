# SPDX-License-Identifier: LGPL-2.1-or-later
"""Emboss with Fusion's dialog (SOLID > CREATE > Emboss).

Sketch Profiles: click closed sketch areas or texts (shaded blue, like in Extrude); a text
is one profile. Faces: click the faces of the part to emboss on (Tangent Chain takes the
faces joined smoothly to it too). Effect Emboss raises the profile out of the face,
Deboss sinks it in; a negative Depth swaps them, like Fusion. Alignment: Horizontal
Distance and Vertical Distance move the profile on the face along its own axes,
Rotation Angle turns it there. The blue arrow at the profile sets the depth, the two
smaller arrows the distances, the ball the angle; each has its value box. Live preview;
problems are said in the dialog; OK makes one timeline step (double-click it to change
it), Cancel or Esc leaves the part as it was.

The geometry: emboss.py (flat faces, cylinders and cones are wrapped, other faces
projected and said so).
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, emboss, extrude, handles3d, log, preview, profile_pick, text
from . import ui_icon_path, warn
from . import emboss_core as core
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes

PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Emboss"
EFFECT_LABELS = [("Emboss", "emboss"), ("Deboss", "deboss")]
PROFILE_HELP = "Click closed sketch areas or texts (shaded blue)."
FACE_HELP = "Click the faces of the part to emboss on."


def _safe(method):
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            warn("Emboss: %s" % exc)
            try:
                self.message.setText("⚠ %s" % exc)
            except Exception:
                pass
        return None

    wrapper.__name__ = method.__name__
    return wrapper


def remembered_depth():
    try:
        value = App.ParamGet(PREFS).GetFloat("Depth", core.DEFAULT_DEPTH)
        return value if value >= core.MIN_DEPTH else core.DEFAULT_DEPTH
    except Exception:
        return core.DEFAULT_DEPTH


def remember_depth(value):
    try:
        App.ParamGet(PREFS).SetFloat("Depth", float(value))
    except Exception:
        pass


class _Observer:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, doc, obj, sub, pnt):
        point = App.Vector(*pnt) if pnt else None
        self.panel._events.append((doc, obj, sub, point))
        QtCore.QTimer.singleShot(30, self.panel._selection_changed)


class EmbossPanel(Panel):
    title = "Emboss"
    icon = "emboss"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Emboss" if feature is None else "Edit Emboss")
        EmbossPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else emboss.owner_body(feature)
        self.base = None
        self.profiles = []
        self.face_names = []
        self.options = core.default_options()
        self.options["depth"] = remembered_depth()
        self.formulas = {"depth": "", "h": "", "v": "", "angle": ""}
        self.error = ""
        self.dirty = False
        self.active = "profiles"
        self.handles = {}
        self.value_boxes = ValueBoxes(self, default="depth")
        self.picker = None
        self.observer = None
        self._events = []
        self._quiet = False
        self._shown = []
        if feature is not None:
            try:
                self.base, self.profiles, self.face_names, read, formulas = emboss.read(feature)
                self.options.update(read)
                self.formulas.update({k: v for k, v in formulas.items() if v})
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
        else:
            self.base = self.body.Tip if self.body is not None else None
        self._show_sketches()
        self._build_form()
        self._show_options()
        self._watch()
        if feature is not None:
            self._refresh_picks()
            self._make_handles()
        else:
            self._start()

    # -- the profile's sketch stays in view while the dialog is open -------------------------
    def _show_sketches(self):
        for obj, _sub in self.profiles:
            sketch = text.sketch_of(obj) or obj
            try:
                if extrude.is_sketch(sketch) and sketch.ViewObject is not None:
                    if not sketch.ViewObject.Visibility and sketch not in self._shown:
                        sketch.ViewObject.Visibility = True
                        self._shown.append(sketch)
            except Exception:
                pass

    def _hide_shown(self):
        for obj in self._shown:
            try:
                if obj.Document.getObject(obj.Name) is not None:
                    obj.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    # -- form -------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.fields = {
            "profiles": SelectionField(self, "profiles", "Select"),
            "faces": SelectionField(self, "faces", "Select"),
        }
        self.fields["profiles"].button.setObjectName("SciForgeEmboss_profiles")
        self.fields["faces"].button.setObjectName("SciForgeEmboss_faces")
        form.addRow("Sketch Profiles", self.fields["profiles"].widget)
        form.addRow("Faces", self.fields["faces"].widget)
        self.tangent = QtWidgets.QCheckBox("Tangent Chain")
        self.tangent.setObjectName("SciForgeEmboss_tangent")
        self.tangent.setChecked(bool(self.options["tangent_chain"]))
        self.tangent.toggled.connect(self._typed)
        form.addRow("", self.tangent)
        self.hint = QtWidgets.QLabel(PROFILE_HELP)
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #8cc4ff;")
        form.addRow(self.hint)
        self.effect = QtWidgets.QComboBox()
        self.effect.setObjectName("SciForgeEmboss_effect")
        for label, key in EFFECT_LABELS:
            self.effect.addItem(label, key)
        self.effect.currentIndexChanged.connect(self._typed)
        form.addRow("Effect", self.effect)
        self.depth = DistanceField(self.options["depth"], on_change=self._depth_typed)
        self.depth.widget.setObjectName("SciForgeEmboss_depth")
        form.addRow("Depth", self.depth.widget)
        title = QtWidgets.QLabel("<b>Alignment</b>")
        form.addRow(title)
        self.h = DistanceField(self.options["h"], on_change=self._typed)
        self.h.widget.setObjectName("SciForgeEmboss_h")
        form.addRow("Horizontal Distance", self.h.widget)
        self.v = DistanceField(self.options["v"], on_change=self._typed)
        self.v.widget.setObjectName("SciForgeEmboss_v")
        form.addRow("Vertical Distance", self.v.widget)
        self.angle = DistanceField(self.options["angle"], unit="deg", on_change=self._typed)
        self.angle.widget.setObjectName("SciForgeEmboss_angle")
        form.addRow("Rotation Angle", self.angle.widget)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.note)
        self.finish_layout()
        self.formula_inputs = [
            preview.FormulaInput(self, key, field)
            for key, field in (
                ("depth", self.depth),
                ("h", self.h),
                ("v", self.v),
                ("angle", self.angle),
            )
        ]
        self._show_active()

    def _show_options(self):
        self._quiet = True
        try:
            index = self.effect.findData(self.options["effect"])
            self.effect.setCurrentIndex(max(index, 0))
            self.depth.set_value(self.options["depth"])
            self.h.set_value(self.options["h"])
            self.v.set_value(self.options["v"])
            self.angle.set_value(self.options["angle"])
            self.tangent.setChecked(bool(self.options["tangent_chain"]))
        finally:
            self._quiet = False

    def _collect(self):
        self.options["effect"] = self.effect.currentData()
        self.options["depth"] = abs(self.depth.value())
        self.options["h"] = self.h.value()
        self.options["v"] = self.v.value()
        self.options["angle"] = self.angle.value()
        self.options["tangent_chain"] = self.tangent.isChecked()

    # -- formulas (preview.FormulaInput calls these) ---------------------------------------
    def formula_typed(self, key, text_value, value):
        self.formulas[key] = text_value
        self._typed()

    def formula_cleared(self, key):
        if self.formulas.get(key):
            self.formulas[key] = ""
            self._typed()

    def formula_failed(self, key, msg):
        self.message.setText("⚠ " + msg)

    # -- selection boxes --------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self._show_active()

    def _show_active(self):
        for name, field in self.fields.items():
            field.set_active(name == self.active)
        self.hint.setText(PROFILE_HELP if self.active == "profiles" else FACE_HELP)
        picker = getattr(self, "picker", None)
        if picker is not None:
            # while Faces takes the clicks, the faces under the sketch areas can be picked
            picker.paused = self.active != "profiles"

    def clear_field(self, name):
        if name == "profiles":
            self.profiles = []
        else:
            self.face_names = []
        self.activate(name)
        self._picks_changed()

    # -- start -----------------------------------------------------------------------------------
    def _start(self):
        if self.body is None or self.base is None or self.base.Shape.isNull():
            self.message.setText("⚠ Emboss needs a part: make a solid first.")
            return
        for obj, short in profile_pick.picks():
            self._take(obj, short, None, region=False)
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self._refresh_picks()
        if self.profiles and not self.face_names:
            self.activate("faces")
        if self.profiles or self.face_names:
            self._picks_changed()

    def _watch(self):
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        extra = [text.sketch_of(o) or o for o, _ in self.profiles]
        extra = [o for o in extra if extrude.is_sketch(o)]
        try:
            self.picker = profile_pick.ProfilePicker(
                Gui.ActiveDocument.ActiveView,
                profile_pick.candidate_sketches(self.body, extra),
                lambda obj, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._region_clicked(obj, sub)
                ),
                occluder=None,  # a profile inside the part (its middle plane) can be picked
                clicks_through=True,
            )
            self.picker.paused = self.active != "profiles"
        except Exception as exc:
            warn("Emboss: profile shading unavailable: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.picker is not None:
            self.picker.remove()
            self.picker = None

    # -- picks ---------------------------------------------------------------------------------
    @_safe
    def _region_clicked(self, obj, sub):
        if self._closed or self._handle_busy():
            return
        self._toggle_profile((obj, sub))

    def _handle_busy(self):
        if handles3d.just_used():
            return True
        for handle in self.handles.values():
            try:
                if handle.busy():
                    return True
            except Exception:
                try:
                    if handle.dragger.isActive.getValue():
                        return True
                except Exception:
                    pass
        return False

    @_safe
    def _selection_changed(self):
        if self._closed:
            return
        events, self._events = self._events, []
        if not events:
            return
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        if self._handle_busy():
            return
        recent = self.picker is not None and self.picker.clicked_region_recently()
        for doc, name, sub, point in events:
            if doc != self.doc.Name:
                continue
            obj = self.doc.getObject(name)
            if obj is None:
                continue
            resolved, short = profile_pick.resolve(obj, sub)
            self._take(resolved, short, point, region=recent)

    def _take(self, obj, short, point, region=False):
        """One pick: a text or a sketch area is a profile, a face of the part a face. A
        click the shaded areas took (`region`) is theirs alone (FreeCAD also selected the
        face behind them)."""
        if obj is None or region:
            return
        if text.is_text(obj):
            self._toggle_profile((obj, ""))
            return
        if extrude.is_sketch(obj):
            if short.startswith("InternalFace"):
                self._toggle_profile((obj, short))
            return
        if not short.startswith("Face"):
            return
        name = self._base_face(obj, short, point)
        if name is None:
            self.message.setText(
                "⚠ Pick a face of %s." % (self.body.Label if self.body else "the part")
            )
            return
        self._toggle_face(name)

    def _base_face(self, obj, short, point):
        """The name of the clicked face on the part before this step (a click on the
        preview is looked up there by the point clicked)."""
        base = self.base
        if base is None:
            return None
        if extrude.owner_body(obj) is not self.body:
            return None
        if obj is base and point is None:
            return short
        if obj is base:
            return short
        try:
            face = obj.Shape.getElement(short)
        except Exception:
            face = None
        import Part

        probe = None
        if point is not None:
            local = self.body.getGlobalPlacement().inverse().multVec(point)
            probe = Part.Vertex(local)
        elif face is not None:
            probe = Part.Vertex(face.CenterOfMass)
        if probe is None:
            return None
        best = None
        for i, candidate in enumerate(base.Shape.Faces, start=1):
            d = candidate.distToShape(probe)[0]
            if best is None or d < best[0]:
                best = (d, "Face%d" % i)
        if best is not None and best[0] < 1e-3:
            return best[1]
        return None

    def _toggle_profile(self, ref):
        keys = [extrude.key(p) for p in self.profiles]
        if extrude.key(ref) in keys:
            self.profiles = [p for p in self.profiles if extrude.key(p) != extrude.key(ref)]
        else:
            self.profiles = self.profiles + [ref]
        if self.profiles and not self.face_names:
            self.activate("faces")
        self._picks_changed()

    def _toggle_face(self, name):
        names = [name]
        if self.tangent.isChecked() and self.base is not None:
            names = emboss.tangent_chain(self.base.Shape, name)
        if name in self.face_names:
            self.face_names = [n for n in self.face_names if n not in names]
        else:
            self.face_names = self.face_names + [n for n in names if n not in self.face_names]
        self._picks_changed()

    def _refresh_picks(self):
        count = len(self.profiles)
        self.fields["profiles"].set_text("%d selected" % count if count else "")
        faces = len(self.face_names)
        self.fields["faces"].set_text("%d selected" % faces if faces else "")
        if self.picker is not None:
            self.picker.set_selected(
                [
                    extrude.key(p)
                    for p in self.profiles
                    if extrude.is_sketch(p[0]) or text.is_text(p[0])
                ]
            )
            shown = []
            if self.base is not None:
                for name in self.face_names:
                    face = profile_pick.global_face(self.base, name)
                    if face is not None:
                        shown.append(face)
            self.picker.show_faces(shown)

    def _picks_changed(self):
        self._refresh_picks()
        if not self.profiles or not self.face_names:
            if self.target is not None and not self.editing:
                emboss.remove(self.target)
                self.target = None
                self._remove_handles()
                self.schedule()
            self.error = ""
            if self.editing:
                self.error = (
                    "Pick a sketch profile."
                    if not self.profiles
                    else "Pick the faces to emboss on."
                )
                self.message.setText("⚠ " + self.error)
            else:
                self.message.setText("")
            return
        self._changed()

    # -- changes -----------------------------------------------------------------------------
    @_safe
    def _typed(self, *_):
        if self._quiet or self._closed:
            return
        self._changed()

    @_safe
    def _depth_typed(self, value):
        if self._quiet or self._closed:
            return
        if value < 0:  # Fusion: a negative depth swaps Emboss and Deboss
            self._quiet = True
            try:
                self.depth.set_value(-value)
                other = "deboss" if self.effect.currentData() == "emboss" else "emboss"
                self.effect.setCurrentIndex(self.effect.findData(other))
            finally:
                self._quiet = False
        self._changed()

    def _changed(self):
        self._collect()
        self.dirty = True
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
            if not any(_dragging(h) for h in self.handles.values()):
                self._make_handles()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        if not self.profiles or not self.face_names or self.base is None:
            return
        try:
            if self.target is None:
                self.target = emboss.make(
                    self.body,
                    self.base,
                    self.profiles,
                    self.face_names,
                    self.options,
                    formulas=self.formulas,
                )
            else:
                emboss.apply(
                    self.target,
                    self.base,
                    self.profiles,
                    self.face_names,
                    self.options,
                    self.formulas,
                )
            self.error = ""
        except core.EmbossError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This emboss cannot be built: %s" % exc

    def feature(self):
        return self.target

    def show_status(self):
        if self.error:
            self.message.setText("⚠ " + self.error)
            self.note.setText("")
            return
        failure = preview.failure(self.target)
        self.message.setText("⚠ " + failure if failure else "")
        wrap = self._wrap()
        self.note.setText(wrap.note if wrap is not None and not failure else "")

    def _wrap(self):
        try:
            proxy = self.target.Proxy if self.target is not None else None
            return getattr(proxy, "wrap", None)
        except Exception:
            return None

    # -- handles --------------------------------------------------------------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _make_handles(self):
        if self._closed:
            return
        self._remove_handles()
        wrap = self._wrap()
        if wrap is None or self.target is None or preview.failure(self.target) or self.error:
            return
        try:
            point, normal, x_axis, y_axis = wrap.frame()
            place = self.body.getGlobalPlacement()
            point = place.multVec(point)
            rot = place.Rotation
            normal, x_axis, y_axis = rot.multVec(normal), rot.multVec(x_axis), rot.multVec(y_axis)
            box = None
            for obj, sub in self.profiles:
                try:
                    for face in extrude.global_faces([(obj, sub)]):
                        box = face.BoundBox if box is None else box.united(face.BoundBox)
                except Exception:
                    continue
            span = box.DiagonalLength if box is not None else 10.0
            size = max(2.0, min(12.0, span * 0.18))
            depth = core.signed(self.options["depth"], self.options["effect"])
            self.handles["depth"] = ArrowDragger(
                point,
                normal,
                depth,
                size,
                on_drag=self._depth_dragged,
                on_release=self._depth_dragged,
            )
            self._attach_box("depth", self.depth)
            anchor = place.multVec(wrap.anchor)
            base_x = rot.multVec(wrap.tx)
            base_y = rot.multVec(wrap.ty)
            gap = size * 1.6
            self.handles["h"] = handles3d.LinearHandle(
                anchor + base_y * (-gap),
                base_x,
                self.options["h"],
                size * 0.6,
                on_drag=self._h_dragged,
                on_release=self._h_dragged,
            )
            self._attach_box("h", self.h)
            self.handles["v"] = handles3d.LinearHandle(
                anchor + base_x * (-gap),
                base_y,
                self.options["v"],
                size * 0.6,
                on_drag=self._v_dragged,
                on_release=self._v_dragged,
            )
            self._attach_box("v", self.v)
            self.handles["angle"] = handles3d.angle_handle(
                point,
                normal,
                x_axis,
                span * 0.6 + size,
                self.options["angle"],
                size * 0.5,
                on_drag=self._angle_dragged,
                on_release=self._angle_dragged,
            )
            self._attach_box("angle", self.angle)
        except Exception as exc:
            warn("Emboss handles unavailable: %s" % exc)

    def _attach_box(self, key, field):
        inputs = {f.key: f for f in self.formula_inputs}
        return self.value_boxes.attach(
            self.handles.get(key),
            key,
            lambda: field.widget.text(),
            lambda typed: inputs[key].take(typed),
        )

    @_safe
    def _depth_dragged(self, distance):
        value = round(float(distance), 2)
        effect = "emboss" if value >= 0 else "deboss"
        self._quiet = True
        try:
            self.depth.set_value(max(abs(value), core.MIN_DEPTH))
            self.effect.setCurrentIndex(self.effect.findData(effect))
        finally:
            self._quiet = False
        self.formulas["depth"] = ""
        self._changed()

    @_safe
    def _h_dragged(self, value):
        self._set_dragged(self.h, "h", value)

    @_safe
    def _v_dragged(self, value):
        self._set_dragged(self.v, "v", value)

    @_safe
    def _angle_dragged(self, value):
        self._set_dragged(self.angle, "angle", value)

    def _set_dragged(self, field, key, value):
        self._quiet = True
        try:
            field.set_value(round(float(value), 2))
        finally:
            self._quiet = False
        self.formulas[key] = ""
        self._changed()

    # -- OK / Cancel ------------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            return self._accept()
        except Exception as exc:
            warn("Emboss OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        if not self.profiles:
            self.message.setText("⚠ Pick a sketch profile first.")
            return False
        if not self.face_names:
            self.message.setText("⚠ Pick the faces of the part to emboss on.")
            return False
        self._timer.stop()
        self._collect()
        if self.dirty or self.target is None:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        failure = preview.failure(self.target)
        if failure:
            self.message.setText("⚠ " + failure)
            return False
        feature = self.target
        remember_depth(self.options["depth"])
        emboss.hide_sketches(self.profiles)
        self._shown = []
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        extrude.show_tip(emboss.owner_body(feature))
        log("emboss done (%s %s mm)" % (self.options["effect"], self.options["depth"]))
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
            if body is not None:
                extrude.show_tip(body)
        except Exception as exc:
            warn("Emboss Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Emboss Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        self._remove_handles()
        self.value_boxes.discard()
        self._hide_shown()
        super().cleanup()


def _dragging(handle):
    try:
        if hasattr(handle, "dragging"):
            return bool(handle.dragging())
        return bool(handle.dragger.isActive.getValue())
    except Exception:
        return False


class ViewProviderEmboss:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("emboss")

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


class EmbossCommand:
    def GetResources(self):
        return {
            "MenuText": "Emboss",
            "ToolTip": "Raise or sink sketch profiles or text into faces of the part: flat, "
            "round (wrapped like a label) or conical faces",
            "Pixmap": ui_icon_path("emboss"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            body = commands.find_body()
            if body is None or body.Tip is None or body.Tip.Shape.isNull():
                commands.tell("Emboss needs a part and a sketch profile: make the part first.")
                return
            Gui.Control.showDialog(EmbossPanel(App.ActiveDocument))
            log("emboss started")
        except Exception as exc:
            warn("Emboss failed to start: %s" % exc)


def edit(feature):
    """Open the Emboss dialog on an existing emboss (timeline double-click)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(EmbossPanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Emboss": EmbossCommand}
EDITORS = {"SciForge::Emboss": edit}
