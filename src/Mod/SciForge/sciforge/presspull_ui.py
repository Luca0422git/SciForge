# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press/Pull command (Q), its dialog and view provider.

The command looks at what is clicked, like Fusion:
  faces of the body        -> push/pull them (Fusion's Offset Face): drag the arrow or type
                              a distance; the faces next to them are extended to follow
  a face made by a fillet  -> edit that fillet's radius (or a chamfer's size)
  edges                    -> new fillet, the distance is the radius
Nothing selected: the dialog opens and waits. Click more faces (or edges) to add them,
click a picked one again to drop it. Tangent Chain also picks the faces that continue
a picked face smoothly (a filleted run). Problems are shown in the dialog.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, preview, presspull, presspull_core as core, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel


class ViewProviderPressPull:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("press_pull")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        Gui.Control.showDialog(PressPullPanel(vobj.Object.Document, feature=vobj.Object))
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

    found = []
    for sel in Gui.Selection.getSelectionEx():
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


class PressPullPanel(Panel):
    title = "Press Pull"
    icon = "press_pull"
    last = None  # the most recent panel (for tests and diagnostics)

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Press Pull" if feature is None else "Edit Press Pull")
        PressPullPanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.body, self.tip = _body_and_tip()
        self.mode = None  # "faces" | "fillet" | "edit_blend"
        self.target = feature  # the feature being created or edited
        self.base = None  # the feature whose faces are moved
        self.names = []  # picked faces (or edges) on self.base
        self.dragger = None
        self.observer = None
        self.error = ""
        self.editing = feature is not None

        from .extrude_ui import SelectionField

        self.what = QtWidgets.QLabel(
            "Click faces to push or pull, edges to fillet,\n"
            "or a fillet face to change its radius."
        )
        self.what.setWordWrap(True)
        self.layout.addRow(self.what)
        self.selection_field = SelectionField(self, "faces", "Select faces")
        self.selection_field.set_active(True)
        self.layout.addRow("Selection", self.selection_field.widget)
        self.tangent = QtWidgets.QCheckBox("Tangent Chain")
        self.tangent.setChecked(False)
        self.tangent.setToolTip("Also pick the faces that continue a picked face smoothly")
        self.layout.addRow(self.tangent)
        self.field_label = QtWidgets.QLabel("Distance")
        self.field = DistanceField(0.0, on_change=self._typed)
        self.layout.addRow(self.field_label, self.field.widget)
        self.finish_layout()

        if feature is not None:
            self.mode = "faces"
            self.body = feature.getParentGeoFeatureGroup()
            self.base = feature.BaseFeature
            self.names = list(feature.Faces[1]) if feature.Faces else []
            self.field.set_value(feature.Distance.Value)
            self.field.bind(feature, "Distance")
            self._describe()
            self._make_dragger()
        else:
            self._start_from_selection()
        self._watch_selection()

    def feature(self):
        return self.target

    # -- the selection box (SelectionField calls these) ------------------------------------
    def activate(self, name):
        self.selection_field.set_active(True)

    def clear_field(self, name):
        if self.mode in ("faces", "fillet"):
            self.names = []
            self._selection_updated()

    # -- starting --------------------------------------------------------------------------
    def _start_from_selection(self):
        if self.body is None or self.tip is None or self.tip.Shape.isNull():
            self.message.setText("Make a solid first (Create Sketch, then Extrude).")
            return
        picks = _picks()
        if picks:
            self._take(picks)
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass

    def _take(self, picks):
        """Use clicked faces/edges: the first pick decides what Press Pull does."""
        for obj, short, point in picks:
            if short.startswith("Face"):
                self._face_picked(obj, short, point)
            elif short.startswith("Edge"):
                self._edge_picked(obj, short)

    def _face_picked(self, obj, short, point):
        if self.mode == "edit_blend":
            return
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
        if self.mode is None and core.is_round_blend(face):
            blend = core.owning_fillet(self.body, face)
            if blend is not None:
                self._start_blend_edit(blend)
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
        if self.mode in ("faces", "edit_blend"):
            if self.mode == "faces":
                self.message.setText("This Press Pull moves faces; click faces to add or drop.")
            return
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
            self.what.setText(
                "Click faces to push or pull, edges to fillet,\n"
                "or a fillet face to change its radius."
            )
            return
        if self.mode == "faces":
            if self.target is None:
                self.target = presspull.make(self.body, self.base, self.names, self.field.value())
                self.field.bind(self.target, "Distance")
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
                self.field.bind(fillet, "Radius")
            self.target.Base = (self.base, list(self.names))
            self.what.setText("%d edge(s): fillet" % len(self.names))
        self.schedule()

    def _remove_target(self):
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
        except Exception as exc:
            warn("press pull: could not remove the preview: %s" % exc)
        self.field_label.setText("Distance")
        self.schedule()

    def _start_blend_edit(self, blend):
        self.target = blend
        self.mode = "edit_blend"
        prop = "Radius" if blend.TypeId == "PartDesign::Fillet" else "Size"
        self.prop = prop
        self.field_label.setText("Fillet radius" if prop == "Radius" else "Chamfer distance")
        self.field.set_value(getattr(blend, prop).Value)
        self.field.bind(blend, prop)
        self.what.setText("Editing %s (it stays one step in the timeline)" % blend.Label)
        self.selection_field.set_text(blend.Label)

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
                on_release=self._dragged,
            )
        except Exception as exc:
            warn("press pull arrow unavailable: %s" % exc)

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
            picks = _picks()
            if not picks:
                return
            Gui.Selection.clearSelection()
            if self.body is None:
                self.body, self.tip = _body_and_tip()
            if self.tip is None or self.tip.Shape.isNull():
                self.message.setText("Make a solid first (Create Sketch, then Extrude).")
                return
            self._take(picks)
        except Exception as exc:
            warn("press pull pick: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    # -- editing ---------------------------------------------------------------------------
    def _typed(self, value):
        if self.target is None:
            return
        if self.mode == "faces":
            self.target.Distance = value
            if self.dragger:
                self.dragger.set_distance(value)
        elif self.mode == "fillet":
            self.target.Radius = max(value, 0.01)
        else:
            setattr(self.target, self.prop, max(value, 0.01))
        self.schedule()

    def _dragged(self, value):
        value = round(value, 2)
        self.field.set_value(value)
        self._typed(value)

    def _recompute(self):
        try:
            preview.recompute(self.doc)
            self.show_status()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def show_status(self):
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return
        note = getattr(getattr(self.target, "Proxy", None), "note", "") if self.target else ""
        self.message.setText(note)

    def accept(self):
        if self.target is None:
            self.message.setText("⚠ Nothing selected yet: click faces or edges of the part.")
            return False
        if self.mode in ("faces", "fillet") and not self.names:
            self.message.setText("⚠ Pick at least one face or edge.")
            return False
        self._timer.stop()
        preview.recompute(self.doc)
        text = preview.failure(self.target)
        if text:
            self.message.setText("⚠ " + text)
            return False
        self.cleanup()
        self.doc.commitTransaction()
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        self.doc.abortTransaction()
        preview.recompute(self.doc)
        self._close()
        return True

    def cleanup(self):
        self._unwatch()
        self.escape.remove()
        self._remove_dragger()
        super().cleanup()


class PressPullCommand:
    def GetResources(self):
        return {
            "MenuText": "Press Pull",
            "ToolTip": "Push or pull faces (their neighbours follow), fillet edges, or change "
            "a fillet's radius, with a live preview (Q)",
            "Pixmap": ui_icon_path("press_pull"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            doc = App.ActiveDocument
            Gui.Control.showDialog(PressPullPanel(doc))
            log("press pull started")
        except Exception as exc:
            warn("Press Pull failed to start: %s" % exc)


def edit(obj):
    """Timeline double-click: the Press Pull dialog on the existing feature."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        Gui.Control.showDialog(PressPullPanel(obj.Document, feature=obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


EDITORS = {"SciForge::PressPull": edit}
