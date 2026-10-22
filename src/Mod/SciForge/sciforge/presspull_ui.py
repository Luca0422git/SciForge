# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press/Pull command (Q), its dialog and view provider.

The command looks at what is clicked, like Fusion:
  faces of the body        -> push/pull them (Fusion's Offset Face): drag the arrow or type
                              a distance (in the dialog or in the box next to the arrow);
                              the faces next to them are extended to follow. Material
                              pushed away shows in red while the dialog is open. It starts
                              at 0, and OK at 0 waits for a distance (no empty step)
  a face made by a fillet  -> edit that fillet's radius (or a chamfer's size)
  edges                    -> new fillet, the distance is the radius
  sketch areas (profiles)  -> Extrude of all of them (also areas picked inside the open
                              sketch, or a shaded area clicked while the dialog waits)
Nothing selected: the dialog opens and waits. Click more faces (or edges) to add them,
click a picked one again to drop it. Tangent Chain also picks the faces that continue
a picked face smoothly (a filleted run). Problems are shown in the dialog. A distance (or
radius) dragged or typed past what works stops at the furthest one that does, and the dialog
says so (Luca, 2026-10-21; Fusion refuses it: value_limits.py): a push into the part stops
before it would remove the body or cut it in two.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, cut_preview, log, offset_type, preview, presspull
from . import presspull_core as core, taskui
from . import ui_icon_path, value_limits, warn
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel, ValueBoxes


class ViewProviderPressPull:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        obj = getattr(self, "Object", None)
        return ui_icon_path(
            "offset_face" if presspull.kind_of(obj) == "OffsetFace" else "press_pull"
        )

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        obj = vobj.Object
        panel = OffsetFacePanel if presspull.kind_of(obj) == "OffsetFace" else PressPullPanel
        Gui.Control.showDialog(panel(obj.Document, feature=obj))
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


def restore_view_providers(doc):
    """Saved documents: give Press Pull features their view provider back."""
    for obj in doc.Objects:
        if presspull.is_press_pull(obj) and obj.ViewObject is not None:
            if not isinstance(getattr(obj.ViewObject, "Proxy", None), ViewProviderPressPull):
                ViewProviderPressPull(obj.ViewObject)


# -- selection helpers -----------------------------------------------------
def _body_and_tip():
    body = commands.find_body()
    if body is None:
        return None, None
    return body, body.Tip


def _selection(tip):
    """(faces, edges) as Part objects from the 3D selection, on the body's current end."""
    faces, edges = [], []
    for sel in Gui.Selection.getSelectionEx():
        for name, sub in zip(sel.SubElementNames, sel.SubObjects):
            short = name.split(".")[-1]
            if short.startswith("Face"):
                faces.append(sub)
            elif short.startswith("Edge"):
                edges.append(sub)
    return faces, edges


def _picks():
    """[(object, short name, picked point or None)] of the selection, through body paths."""
    from . import profile_pick
    from . import text as sketch_text

    found = []
    for sel in Gui.Selection.getSelectionEx():
        if not sel.SubElementNames and sketch_text.is_text(sel.Object):
            found.append((sel.Object, "", None))  # a sketch text picked as a whole
            continue
        points = list(getattr(sel, "PickedPoints", []) or [])
        for i, name in enumerate(sel.SubElementNames):
            obj, short = profile_pick.resolve(sel.Object, name)
            if obj is None:
                continue
            point = App.Vector(points[i]) if i < len(points) else None
            found.append((obj, short, point))
    return found


def _edge_names(shape, edges):
    names = []
    for edge in edges:
        for i, candidate in enumerate(shape.Edges, start=1):
            if candidate.isSame(edge) or (
                abs(candidate.Length - edge.Length) < 1e-6
                and (candidate.CenterOfMass - edge.CenterOfMass).Length < 1e-5
            ):
                names.append("Edge%d" % i)
                break
    return names


def _local(obj, point):
    """A global point in the coordinates of obj's body."""
    if point is None:
        return None
    body = obj.getParentGeoFeatureGroup() if obj is not None else None
    if body is None:
        return point
    return body.getGlobalPlacement().inverse().multVec(point)


WIP_NOTE = (
    "\u26a0 Work in progress: on complex shapes (curved or freeform faces, many faces at once) "
    "Press Pull can be slow and give odd results."
)


class PressPullPanel(Panel, value_limits.LimitedValues):
    title = "Press Pull"
    icon = "press_pull"
    last = None  # the most recent panel (for tests and diagnostics)
    faces_only = False  # Offset Face: faces only (no fillets, no sketch areas)
    step_type = "PressPull"  # SciForgeType of the step made
    hint = "Click faces to push or pull, edges to fillet,\nor a fillet face to change its radius."

    def __init__(self, doc, feature=None):
        super().__init__(doc, self.title if feature is None else "Edit %s" % self.title)
        PressPullPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.body, self.tip = _body_and_tip()
        self.mode = None  # "faces" | "fillet" | "edit_blend"
        self.target = feature  # the feature being created or edited
        self.base = None  # the feature whose faces are moved
        self.names = []  # picked faces (or edges) on self.base
        self.dragger = None
        self.observer = None
        self.error = ""
        self.editing = feature is not None
        self.value_boxes = ValueBoxes(self, default="distance")  # the box next to the arrow
        self.cut_view = None  # the red preview of the material taken away
        self._adopted = []  # plain solids made bodies by a pick (shown again on Cancel)
        self.limit_init()  # a distance past what works stops at the furthest that does

        from .extrude_ui import SelectionField

        self.what = QtWidgets.QLabel(self.hint)
        self.what.setWordWrap(True)
        self.layout.addRow(self.what)
        # Luca (2026-10-16): on complex shapes the program froze for a while and the result
        # was odd; mark the command as work in progress until the face-editing engine
        # (outline 9.1) handles them.
        self.wip_note = QtWidgets.QLabel(WIP_NOTE)
        self.wip_note.setObjectName("SciForgeWorkInProgress")
        self.wip_note.setWordWrap(True)
        self.wip_note.setStyleSheet("color: #ffcc66;")
        self.layout.addRow(self.wip_note)
        self.selection_field = SelectionField(self, "faces", "Select faces")
        self.selection_field.set_active(True)
        self.layout.addRow("Selection", self.selection_field.widget)
        self.tangent = QtWidgets.QCheckBox("Tangent Chain")
        self.tangent.setChecked(False)
        self.tangent.setToolTip("Also pick the faces that continue a picked face smoothly")
        self.layout.addRow(self.tangent)
        # Fusion's Offset Type (faces): Automatic, Modify Existing Feature, New Offset
        self.offset_type = QtWidgets.QComboBox()
        for key in offset_type.TYPES:
            self.offset_type.addItem(offset_type.LABELS[key], key)
            self.offset_type.setItemData(
                self.offset_type.count() - 1, offset_type.TIPS[key], QtCore.Qt.ToolTipRole
            )
        self.offset_type_label = QtWidgets.QLabel("Offset Type")
        self.layout.addRow(self.offset_type_label, self.offset_type)
        self._modify = None  # (feature, property, sign, value before) for Modify Existing
        if self.faces_only or feature is not None:
            # Offset Face always adds its step; an existing Press Pull step is a New Offset
            self.offset_type.setCurrentIndex(offset_type.TYPES.index("new"))
            self.offset_type.setVisible(False)
            self.offset_type_label.setVisible(False)
        self.offset_type.currentIndexChanged.connect(self._offset_type_changed)
        self.field_label = QtWidgets.QLabel("Distance")
        self.field = DistanceField(0.0, on_change=self._typed)
        self.layout.addRow(self.field_label, self.field.widget)
        self.formula = ""  # the value as a formula of parameters ("wall * 2"), or ""
        self.formula_error = ""  # a formula typed that is no value (OK waits)
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setWordWrap(True)
        self.formula_label.setStyleSheet("color: #b8c7d9;")
        self.layout.addRow(self.formula_label)
        self.finish_layout()
        self.limit_label = value_limits.note_label()  # a value held at its limit
        self.layout.addRow(self.limit_label)
        # Fusion: a parameter or formula typed in the field; a number typed over it wins.
        # (FreeCAD's own expression binding made the field read-only once a formula was set.)
        self.formula_input = preview.FormulaInput(self, "value", self.field)

        if feature is not None:
            self.mode = "faces"
            self.body = feature.getParentGeoFeatureGroup()
            self.base = feature.BaseFeature
            self.names = list(feature.Faces[1]) if feature.Faces else []
            self.field.set_value(feature.Distance.Value)
            self._show_formula(preview.formula_of(feature, "Distance"))
            self._describe()
            self._make_dragger()
            # A push into the part shows the material it takes away in red at once (R7),
            # not only after the first change.
            self._update_cut_preview()
        else:
            self._start_from_selection()
        self.picker = None
        if self.mode is None and not self.faces_only:
            self._shade_profiles()
            self._say_what_to_click()
        self._watch_selection()

    def _say_what_to_click(self):
        """Nothing picked yet. With no solid, sketch areas are all Press Pull can use: say
        so (they are shaded, a click extrudes one) instead of asking for a solid."""
        if self.mode is not None or self._closed:
            return
        if self.body is not None and self.tip is not None and not self.tip.Shape.isNull():
            return
        if self.picker is not None and self.picker.regions:
            self.message.setText("")
            self.what.setText("Click a sketch area (shaded blue) to extrude it.")
        else:
            self.message.setText("Make a solid first (Create Sketch, then Extrude).")

    # a click on a sketch area only the face's projected edges bound (Auto project) is
    # a click on the face (sketch_area_pick lets it through)
    face_areas_are_faces = True

    def picks_sketch_areas(self):
        """Sketch areas (profiles) can be clicked until faces or edges are picked; otherwise a click
        goes through them to what is behind (sketch_area_pick)."""
        return not self._closed and self.mode is None

    def feature(self):
        return self.target

    def _shade_profiles(self):
        """Visible sketch areas are shaded; clicking one starts Extrude on it (Fusion)."""
        from . import profile_pick

        sketches = []
        for obj in profile_pick.candidate_sketches(self.body):
            try:
                if obj.ViewObject is not None and obj.ViewObject.Visibility:
                    sketches.append(obj)
            except Exception:
                pass
        if not sketches:
            return
        tip = self.tip

        def occluder():
            if tip is None or tip.Shape.isNull():
                return None
            from . import extrude

            return extrude._to_global(tip.Shape, tip)

        try:
            self.picker = profile_pick.ProfilePicker(
                Gui.ActiveDocument.ActiveView,
                sketches,
                lambda sketch, sub: QtCore.QTimer.singleShot(
                    0, lambda: self._to_extrude([(sketch, sub)])
                ),
                occluder=occluder,
            )
        except Exception as exc:
            warn("profile shading unavailable: %s" % exc)

    def _unshade(self):
        if getattr(self, "picker", None) is not None:
            self.picker.remove()
            self.picker = None

    # -- the selection box (SelectionField calls these) ------------------------------------
    def activate(self, name):
        self.selection_field.set_active(True)

    def clear_field(self, name):
        if self.mode in ("faces", "fillet"):
            self.names = []
            self._selection_updated()

    # -- starting --------------------------------------------------------------------------
    def _start_from_selection(self):
        picks = _picks()
        if picks:
            self._take(picks)
        # (nothing picked and no solid: _say_what_to_click, once the sketch areas are shaded)
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass

    def _take(self, picks):
        """Use clicked faces/edges: the first pick decides what Press Pull does."""
        from . import text as sketch_text

        if self.mode is None and not self.faces_only:
            areas = [
                (obj, short)
                for obj, short, _point in picks
                if obj.isDerivedFrom("Sketcher::SketchObject") and short.startswith("InternalFace")
            ]
            for obj, _short, _point in picks:  # a sketch text is one profile, as a whole
                if sketch_text.is_text(obj) and (obj, "") not in areas:
                    areas.append((obj, ""))
            if areas:
                # Fusion: Press Pull on sketch profiles is an Extrude of all of them.
                QtCore.QTimer.singleShot(0, lambda: self._to_extrude(areas))
                return
        for obj, short, point in picks:
            if obj.isDerivedFrom("Sketcher::SketchObject") or sketch_text.is_text(obj):
                continue  # sketch lines and texts are not part of the solid
            if short.startswith("Face"):
                self._face_picked(obj, short, point)
            elif short.startswith("Edge"):
                self._edge_picked(obj, short)

    def _to_extrude(self, profiles):
        """Close Press Pull and start Extrude on the sketch areas [(sketch, "InternalFaceN")]
        (a sketch text: (text, ""))."""
        if self._closed:
            return
        try:
            from .extrude_ui import ExtrudePanel

            doc = self.doc
            self.reject()
            Gui.Control.showDialog(ExtrudePanel(doc, profiles=list(profiles)))
            log("press pull on %d sketch area(s): extrude started" % len(profiles))
        except Exception as exc:
            warn("press pull on a sketch: %s" % exc)

    def _follow_body(self, obj):
        """The first pick decides the body (Fusion: Press Pull works on any body, not only
        the active one); the feature goes into that body's timeline. A solid without history
        (a STEP part FreeCAD opened, a converted mesh) becomes a body built on it first: its
        base feature holds the solid, the Press Pull comes after it (in a design without
        history it is baked into it at OK)."""
        if self.mode is not None or self.editing:
            return
        from . import direct, extrude

        body = extrude.owner_body(obj)
        if body is None and direct.is_adoptable(obj):
            body = direct.adopt(obj)
            self._adopted.append(obj)
        if body is None or body is self.body or body.Tip is None or body.Tip.Shape.isNull():
            return
        self.body, self.tip, self.base = body, body.Tip, None

    def _face_picked(self, obj, short, point):
        if self.mode == "edit_blend":
            return
        self._follow_body(obj)
        if self.mode == "fillet":
            self.message.setText(
                "This Press Pull rounds edges; click edges, or OK and start again."
            )
            return
        base = self.base or self.tip
        if base is None:
            return
        try:
            face = obj.Shape.getElement(short)
        except Exception:
            return
        if (
            self.mode is None
            and not self.faces_only
            and self.offset_kind() != "new"
            and core.is_round_blend(face)
        ):
            blend = core.owning_fillet(self.body, face, sciforge=True)
            if blend is not None and self._start_blend_edit(blend, face):
                return
        distance = self.field.value() if self.mode == "faces" else 0.0
        name = core.match_pick(base.Shape, face, _local(obj, point), self.names, distance)
        if name is None:
            self.message.setText("That face is not on the part before this Press Pull.")
            return
        chain = [name]
        if self.tangent.isChecked():
            chain = core.tangent_chain(base.Shape, [name])
        if name in self.names:
            self.names = [n for n in self.names if n not in chain]
        else:
            self.names = self.names + [n for n in chain if n not in self.names]
        self.base = base
        self.mode = "faces"
        self._selection_updated()

    def _edge_picked(self, obj, short):
        if self.faces_only:
            self.message.setText("%s moves faces: click faces of the body." % self.title)
            return
        if self.mode in ("faces", "edit_blend"):
            if self.mode == "faces":
                self.message.setText("This Press Pull moves faces; click faces to add or drop.")
            return
        self._follow_body(obj)
        base = self.base or self.tip
        if base is None:
            return
        try:
            edge = obj.Shape.getElement(short)
        except Exception:
            return
        names = _edge_names(base.Shape, [edge])
        if not names:
            self.message.setText("That edge is not on the part before this fillet.")
            return
        name = names[0]
        if name in self.names:
            self.names = [n for n in self.names if n != name]
        else:
            self.names = self.names + [name]
        self.base = base
        self.mode = "fillet"
        self._selection_updated()

    def _selection_updated(self):
        """Create, change or remove the feature after the picked faces/edges changed."""
        self.message.setText("")
        self.limits.note = ""  # a limit found for the old picks no longer applies
        value_limits.show_note(self.limit_label, "")
        count = len(self.names)
        self.selection_field.set_text(
            ("%d face(s)" if self.mode == "faces" else "%d edge(s)") % count if count else ""
        )
        if not self.names:
            if self.editing:
                self.message.setText("⚠ Pick at least one face.")
                return
            self._remove_target()
            self.mode = None
            self.what.setText(self.hint)
            return
        if self.mode == "faces" and self.offset_kind() == "modify":
            self._update_modify()
            return
        if self.mode == "faces":
            if self.target is None:
                self.target = presspull.make(
                    self.body,
                    self.base,
                    self.names,
                    self.field.value(),
                    kind=self.step_type,
                )
                self._apply_formula()
            else:
                self.target.Faces = (self.base, list(self.names))
            self._describe()
            self._make_dragger()
        else:
            if self.target is None:
                fillet = self.body.newObject("PartDesign::Fillet", "Fillet")
                fillet.Radius = 1.0
                fillet.Refine = True
                self.body.Tip = fillet
                self.target = fillet
                self.field_label.setText("Fillet radius")
                self.field.set_value(1.0)
                self._show_formula("")
            self.target.Base = (self.base, list(self.names))
            self.what.setText("%d edge(s): fillet" % len(self.names))
        self.schedule()

    def _remove_target(self):
        if self._modify is not None:
            self._end_modify()
            return
        if self.target is None or self.editing:
            return
        target, self.target = self.target, None
        self._remove_dragger()
        try:
            body = target.getParentGeoFeatureGroup()
            if body is not None:
                body.removeObject(target)
                if self.base is not None:
                    body.Tip = self.base
            self.doc.removeObject(target.Name)
            from . import extrude

            extrude.show_tip(body)  # the part before it was hidden by the new feature
        except Exception as exc:
            warn("press pull: could not remove the preview: %s" % exc)
        self.field_label.setText("Distance")
        self.schedule()

    def _start_blend_edit(self, blend, face=None):
        """Edit the size of the fillet / chamfer that made the clicked face; False when it
        has none to edit (a variable round, a full round: the face is pushed instead)."""
        label = None
        if blend.TypeId == "PartDesign::Fillet":
            prop = "Radius"
        elif blend.TypeId == "PartDesign::Chamfer":
            prop = "Size"
        else:  # SciForge's fillet step: the size of the set that made the face
            from . import fillet_sets

            prop, label = fillet_sets.size_of_face(blend, face)
            if prop is None:
                return False
        self.target = blend
        self.mode = "edit_blend"
        self.prop = prop
        if label is None:
            label = "Fillet radius" if prop == "Radius" else "Chamfer distance"
        self.field_label.setText(label)
        self.field.set_value(getattr(blend, prop).Value)
        self._show_formula(preview.formula_of(blend, prop))
        self.what.setText("Editing %s (it stays one step in the timeline)" % blend.Label)
        self.selection_field.set_text(blend.Label)
        return True

    def _describe(self):
        count = len(self.names)
        self.selection_field.set_text("%d face(s)" % count if count else "")
        self.what.setText(
            "%d face(s): drag the arrow or type a distance\n"
            "(+ adds material, − removes it). Click faces to add or drop them." % count
        )

    def _remove_dragger(self):
        if self.dragger is not None:
            self.dragger.remove()
            self.dragger = None

    def _make_dragger(self):
        self._remove_dragger()
        try:
            base = self.base.Shape
            face = base.getElement(self.names[0])
            u0, u1, v0, v1 = face.ParameterRange
            point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            normal = core.face_normal(face)
            body = self.base.getParentGeoFeatureGroup()
            if body is not None:
                placement = body.getGlobalPlacement()
                point = placement.multVec(point)
                normal = placement.Rotation.multVec(normal)
            size = max(4.0, min(base.BoundBox.DiagonalLength * 0.08, 30.0))
            self.dragger = ArrowDragger(
                point,
                normal,
                self.field.value(),
                size,
                on_drag=self._dragged,
                on_release=self._released,
            )
            self._value_box()
        except Exception as exc:
            warn("press pull arrow unavailable: %s" % exc)

    def _value_box(self):
        """The box next to the arrow: shows the distance and takes one typed in it. Kept by
        the dialog (the arrow is rebuilt when faces are added)."""
        return self.value_boxes.attach(
            self.dragger,
            "distance",
            lambda: self.field.widget.text(),
            lambda text: self.formula_input.take(text),
        )

    @property
    def value_box(self):
        return self.value_boxes.boxes.get("distance")

    def _discard_value_box(self):
        self.value_boxes.discard()

    def _watch_selection(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                # Deferred: nothing is built inside FreeCAD's click handling.
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _selection_changed(self):
        if self._closed:
            return
        try:
            # Only this design's objects: a click in another open document is not a pick.
            picks = [pk for pk in _picks() if pk[0].Document.Name == self.doc.Name]
            if not picks:
                return
            Gui.Selection.clearSelection()
            if taskui.box_click_taken():
                return  # the click that left the arrow's value box: not a pick
            if self.body is None:
                self.body, self.tip = _body_and_tip()
            if self.picker is not None and self.picker.clicked_region_recently():
                return  # the click was on a sketch area: Extrude takes over
            self._take(picks)  # a face of any body, also when the active body is empty
            if self.mode is None and (self.tip is None or self.tip.Shape.isNull()):
                self._say_what_to_click()
            if self.mode is not None:
                self._unshade()  # faces or edges chosen: sketch areas no longer apply
        except Exception as exc:
            warn("press pull pick: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    # -- editing ---------------------------------------------------------------------------
    def _typed(self, value):
        """A value from the box (typed, a formula, its arrows): held at the furthest one known
        to work for these picks (not a formula's: it is never rewritten)."""
        if self.target is None:
            return
        held = self.limit_edit("value", value, "formula" if self.formula else "typed")
        if held != value:
            value_limits.show_held(self.limit_shower, "value", self.field, value, held)
            value = held
        self._apply_value(value)

    def _apply_value(self, value):
        if self.target is None:
            return
        if self._modify is not None:
            self._apply_modify(value)
            if self.dragger:
                self.dragger.set_distance(value)
        elif self.mode == "faces":
            self.target.Distance = value
            if self.dragger:
                self.dragger.set_distance(value)
        elif self.mode == "fillet":
            self.target.Radius = max(value, 0.01)
        else:
            setattr(self.target, self.prop, max(value, 0.01))
        self.schedule()

    def _released(self, value):
        """The arrow let go. At the value of its last drag step that step did everything
        already (the rebuild waiting for it runs now: taskui.handle_released); taking it again
        rebuilt the same value a second time, 1.2 s on a part of 180 faces (review finding
        DRAFT-2-F6)."""
        try:
            last = getattr(self, "_drag_last", None)
            if last is not None and abs(round(value, 2) - last) < 1e-12:
                return
            self._dragged(value)
        except Exception as exc:
            warn("press pull arrow: %s" % exc)
        finally:
            self._drag_last = None

    def _dragged(self, value):
        self.formula_cleared("value")  # a drag gives a plain number
        value = round(value, 2)
        self._drag_last = value
        held = self.limit_edit("value", value, "dragged")
        if held != value:
            value = held
            if self.dragger is not None:
                self.dragger.set_distance(value)  # the arrow stops at the limit
            if abs(self.field.value() - value) < 1e-12:
                if self.limits.note and not self.error:
                    self.show_status()  # held at the limit: nothing to rebuild
                return
        self.field.set_value(value)
        self._apply_value(value)

    # -- values past what works (value_limits.LimitedValues) ------------------------------------
    def _limit_blend(self):
        """(info, refs, options, kind, option name) of the FreeCAD Fillet / Chamfer whose
        size is changed (fillet mode or a fillet face clicked), or None (SciForge's own step:
        its own refusal stays)."""
        from . import blend as blends

        if self.mode == "fillet" and self.base is not None:
            info = blends.ShapeInfo(self.base.Shape)
            return info, list(self.names), {"radius": 1.0}, "fillet", "radius"
        target = self.target
        if self.mode != "edit_blend" or target is None or not target.Base:
            return None
        if target.TypeId not in (blends.FILLET, blends.CHAMFER) or self.prop not in (
            "Radius",
            "Size",
        ):
            return None
        source, subs = target.Base[0], list(target.Base[1])
        info = blends.ShapeInfo(source.Shape)
        if target.TypeId == blends.FILLET:
            return info, subs, {"radius": 1.0}, "fillet", "radius"
        types = {freecad: option for option, freecad, _label in blends.CHAMFER_TYPES}
        options = {
            "chamfer_type": types.get(target.ChamferType, "equal"),
            "distance": target.Size.Value,
            "distance2": target.Size2.Value,
            "angle": target.Angle.Value,
            "flip": bool(target.FlipDirection),
        }
        return info, subs, options, "chamfer", "distance"

    def limit_key(self, what):
        target = self.target
        extra = None
        if self.mode == "edit_blend" and target is not None:
            extra = (
                target.Name,
                self.prop,
                [
                    (p, str(getattr(target, p)))
                    for p in ("ChamferType", "Size2", "Angle", "FlipDirection")
                    if p in target.PropertiesList
                ],
            )
        base = self.base.Shape if self.base is not None else None
        return value_limits.make_key("presspull", self.mode, base, list(self.names), extra)

    def limit_works(self, what):
        if self._modify is not None:
            return lambda value: False  # Modify Existing: the extrude's own limits apply
        if self.mode == "faces":
            shape = self.base.Shape
            faces = [shape.getElement(n) for n in self.names]
            return lambda value: core.press_pull(shape, faces, value) is not None
        found = self._limit_blend()
        if found is None:
            return lambda value: False
        info, refs, options, kind, key = found
        from . import blend as blends

        def works(value):
            trial = dict(options)
            trial[key] = value
            blends.check_build(kind, info, refs, trial)
            return True

        return works

    def limit_value(self, what):
        return float(self.field.value())

    def limit_start(self, what, value):
        if self.mode == "faces":
            return 0.01 if value > 0 else -0.01
        return 0.1  # a fillet radius / chamfer size

    def limit_set(self, what, value):
        value_limits.show_held(self.limit_shower, what, self.field, self.field.value(), value)
        if self.dragger is not None:
            self.dragger.set_distance(value)
        if self.mode == "faces":
            self.target.Distance = value
        elif self.mode == "fillet":
            self.target.Radius = value
        elif self.mode == "edit_blend":
            setattr(self.target, self.prop, value)

    def limit_keep(self):
        return self.base.Shape if self.base is not None else None

    # -- formulas (preview.FormulaInput calls the first three) --------------------------------
    def formula_typed(self, key, text, value):
        self.error = ""
        self.formula_error = ""
        self._show_formula(text)
        self._typed(value)
        self._apply_formula()

    def formula_cleared(self, key):
        self.formula_error = ""
        if self.formula:
            self._show_formula("")
            self._apply_formula()
            self._typed(self.field.value())  # the number typed, not the formula's last value

    def formula_failed(self, key, text):
        self.formula_error = text
        self.message.setText("⚠ " + text)

    def _show_formula(self, text):
        self.formula = text or ""
        name = self.field_label.text()
        self.formula_label.setText("%s = %s" % (name, self.formula) if self.formula else "")

    def _value_property(self):
        if self.mode == "faces":
            return "Distance"
        if self.mode == "fillet":
            return "Radius"
        if self.mode == "edit_blend":
            return self.prop
        return None

    def _apply_formula(self):
        prop = self._value_property()
        if self.target is None or prop is None or self._modify is not None:
            return  # Modify Existing: the value is how far the extrude's end moves
        try:
            preview.set_formula(self.target, prop, self.formula)
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        try:
            preview.recompute(self.doc)
            text = preview.failure(self.target) if self._modify is None else ""
            if text and self.limit_refused(text):
                preview.recompute(self.doc)  # held at the furthest value that works
            elif not text:
                self.limit_good()
            self.show_status()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
        self._update_cut_preview()

    # -- the red preview of material taken away ----------------------------------------------
    def _removed(self):
        """The material a face push takes away (global coordinates), or None."""
        target = self.target
        if self.mode != "faces" or target is None or preview.failure(target):
            return None
        tool = presspull.removed_material(target)
        if tool is None or tool.isNull() or not tool.Solids:
            return None
        shape = tool.copy()
        body = target.getParentGeoFeatureGroup()
        if body is not None:
            shape.Placement = body.getGlobalPlacement().multiply(shape.Placement)
        return shape

    def _update_cut_preview(self):
        """Pushing a face into the part shows the material it takes away in red (like a cut
        in Fusion's Extrude); a picture only, the features keep their colours."""
        if self._closed:
            return
        try:
            shape = self._removed()
        except Exception:
            shape = None
        try:
            if shape is None:
                if self.cut_view is not None:
                    self.cut_view.clear()
                return
            if self.cut_view is None:
                self.cut_view = cut_preview.CutPreview(Gui.getDocument(self.doc.Name).ActiveView)
            self.cut_view.show(shape)
        except Exception as exc:
            warn("cut preview: %s" % exc)

    def _remove_cut_preview(self):
        view, self.cut_view = self.cut_view, None
        if view is not None:
            view.clear()

    def show_status(self):
        value_limits.show_note(self.limit_label, "")
        if self.formula_error:  # stays until the field gets a value again
            self.message.setText("⚠ " + self.formula_error)
            return
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = preview.failure(self.target)
        if text:
            if self._modify is None:
                text = self.limit_hint(text)  # a formula is not held: say what fits
            self.message.setText("⚠ " + text)
            return
        note = getattr(getattr(self.target, "Proxy", None), "note", "") if self.target else ""
        self.message.setText(note)
        # a distance held at its limit: "Furthest that fits here: -9.99 mm"
        value_limits.show_note(self.limit_label, self.limits.note)

    def accept(self):
        if self._timer.isActive():
            # A value typed and Enter (or OK) at once: build it before deciding. Left to the
            # timer, that rebuild came ~60 ms later and wiped the message said below.
            self._timer.stop()
            self._recompute()
        if self.target is None:
            if self.error:
                self.message.setText("⚠ " + self.error)
                return False
            self.message.setText("⚠ Nothing selected yet: click faces or edges of the part.")
            return False
        if self.formula_error:  # Enter right after a typo: Fusion keeps the dialog open
            self.message.setText("⚠ " + self.formula_error)
            return False
        if self.mode in ("faces", "fillet") and not self.names:
            self.message.setText("⚠ Pick at least one face or edge.")
            return False
        if self.mode == "faces" and abs(self.field.value()) < 1e-6:
            # A push of 0 changes nothing: Fusion makes no step of it. Stay open and say why.
            self.message.setText(
                "⚠ The distance must not be zero: drag the arrow or type a distance."
            )
            return False
        self._timer.stop()
        preview.recompute(self.doc)
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
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
        self._show_adopted()
        self._close()
        return True

    def _show_adopted(self):
        """Cancel took away the body a plain solid was made into: the solid shows again."""
        from . import bodies

        for obj in self._adopted:
            try:
                if bodies.alive(obj) and not any(bodies.is_body(u) for u in obj.InList):
                    bodies.set_shown(obj, True)
            except Exception:
                pass
        self._adopted = []

    # -- Offset Type: Modify Existing Feature (offset_type.py) -------------------------------
    def offset_kind(self):
        return self.offset_type.currentData() or "automatic"

    def _offset_type_changed(self, *_):
        try:
            if self._closed or self.mode != "faces" or not self.names:
                return
            self.error = ""
            if self.offset_kind() == "modify":
                if self._modify is None:
                    self._drop_step()
                    self._update_modify()
            else:
                if self._modify is not None:
                    self._end_modify()
                    self._selection_updated()
        except Exception as exc:
            warn("press pull offset type: %s" % exc)

    def _drop_step(self):
        """The Press Pull step made so far goes (Modify Existing changes the extrude)."""
        if self.target is None or self.editing or self._modify is not None:
            return
        target, self.target = self.target, None
        self._remove_dragger()
        try:
            body = target.getParentGeoFeatureGroup()
            if body is not None:
                body.removeObject(target)
                if self.base is not None:
                    body.Tip = self.base
            self.doc.removeObject(target.Name)
            from . import extrude

            extrude.show_tip(body)
        except Exception as exc:
            warn("press pull: could not remove the preview: %s" % exc)

    def _update_modify(self):
        """Faces picked with Modify Existing Feature: find the extrude, move its end."""
        self.error = ""
        try:
            feature, prop, sign = offset_type.modify_target(self.body, self.base, self.names)
        except offset_type.OffsetTypeError as exc:
            if self._modify is not None:
                self._end_modify()
            self.error = str(exc)
            self.what.setText("Modify Existing Feature")
            self.show_status()
            return
        if self._modify is None or self._modify[0] is not feature:
            if self._modify is not None:
                self._end_modify()
            start = getattr(feature, prop).Value
            self._modify = (feature, prop, sign, start)
            self.target = feature
        self._describe()
        try:
            from . import timeline_ops

            title = timeline_ops.display_names(self.doc, self.doc.Objects).get(feature.Name)
        except Exception:
            title = None
        self.what.setText(
            "%d face(s): %s changes, no new step. Drag the arrow or type a distance."
            % (len(self.names), title or feature.Label)
        )
        self._make_dragger()
        self._apply_modify(self.field.value())

    def _apply_modify(self, value):
        feature, prop, sign, start = self._modify
        try:
            offset_type.apply(feature, prop, start, sign, value)
            self.error = ""
        except offset_type.OffsetTypeError as exc:
            self.error = str(exc)
            self.show_status()
            return
        self.schedule()

    def _end_modify(self):
        """The extrude back to its length before the dialog (the faces were dropped or the
        Offset Type changed)."""
        modify, self._modify = self._modify, None
        if modify is None:
            return
        feature, prop, _sign, start = modify
        try:
            if abs(getattr(feature, prop).Value - start) > 1e-12:
                setattr(feature, prop, start)
        except Exception as exc:
            warn("press pull: %s" % exc)
        if self.target is feature:
            self.target = None
        self._remove_dragger()
        self.schedule()

    def cleanup(self):
        self._unwatch()
        self._unshade()
        self.escape.remove()
        self.undo_guard.remove()
        self.enter.remove()
        self._remove_dragger()
        self._discard_value_box()
        try:
            self._remove_cut_preview()
        except Exception as exc:
            warn("cut preview: %s" % exc)
        super().cleanup()


class PressPullCommand:
    def GetResources(self):
        return {
            "MenuText": "Press Pull",
            "ToolTip": "Push or pull faces (their neighbours follow), fillet edges, or change "
            "a fillet's radius, with a live preview (Q). " + WIP_NOTE,
            "Pixmap": ui_icon_path("press_pull"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            from . import extrude_ui

            # Q in a sketch with areas picked in it (Fusion): Press Pull on sketch profiles
            # is an Extrude of exactly those (read before the sketch closes).
            sketch = extrude_ui._sketch_in_edit()
            picked = extrude_ui.sketch_areas_picked(sketch)
            if not commands.finish_open_dialog():
                return
            doc = App.ActiveDocument
            profiles = extrude_ui.sketch_areas_profiles(sketch, picked)
            if sketch is not None:
                # Q left a sketch: the dialog opens right after this command returns, in an
                # undo step of its own. FreeCAD keeps the step of leaving the sketch open
                # until then, and a dialog opened inside it would undo that too on Cancel
                # (the sketch hidden) and share one Undo with it after OK. As E does.
                QtCore.QTimer.singleShot(0, lambda: _open_after_sketch(doc, sketch, profiles))
                return
            Gui.Control.showDialog(PressPullPanel(doc))
            log("press pull started")
        except Exception as exc:
            warn("Press Pull failed to start: %s" % exc)


def _open_after_sketch(doc, sketch, profiles):
    """Q pressed in a sketch: Extrude of the areas picked in it (Press Pull on sketch
    profiles is an Extrude), else Press Pull."""
    try:
        from . import extrude_ui

        if doc is None or doc.Name not in App.listDocuments():
            return
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        if profiles:
            Gui.Control.showDialog(extrude_ui.ExtrudePanel(doc, profiles=profiles, sketch=sketch))
            log("press pull on %d picked sketch area(s): extrude started" % len(profiles))
        else:
            Gui.Control.showDialog(PressPullPanel(doc))
            log("press pull started")
    except Exception as exc:
        warn("Press Pull failed to start: %s" % exc)


def edit(obj):
    """Timeline double-click: the Press Pull dialog on the existing feature."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        panel = OffsetFacePanel if presspull.kind_of(obj) == "OffsetFace" else PressPullPanel
        Gui.Control.showDialog(panel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


# -- Offset Face (Modify > Offset Face) --------------------------------------------------------
class OffsetFacePanel(PressPullPanel):
    """Fusion's Offset Face: pick faces, drag the arrow or type a distance, OK: an Offset Face
    step in the timeline (Press Pull's faces mode without its fillet and sketch-area modes).
    Works on bodies without history too (their base feature holds the solid)."""

    title = "Offset Face"
    icon = "offset_face"
    faces_only = True
    step_type = "OffsetFace"
    hint = "Click faces to offset (+ adds material, − removes it)."


class OffsetFaceCommand:
    def GetResources(self):
        return {
            "MenuText": "Offset Face",
            "ToolTip": "Move faces along their normals by a distance; the faces around them "
            "follow (an Offset Face step in the timeline)",
            "Pixmap": ui_icon_path("offset_face"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            Gui.Control.showDialog(OffsetFacePanel(App.ActiveDocument))
            log("offset face started")
        except Exception as exc:
            warn("Offset Face failed to start: %s" % exc)


COMMANDS = {"SciForge_OffsetFace": OffsetFaceCommand}
EDITORS = {"SciForge::PressPull": edit, "SciForge::OffsetFace": edit}
