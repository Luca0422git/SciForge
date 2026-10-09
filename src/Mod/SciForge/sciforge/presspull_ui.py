# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press/Pull command (Q), its dialog and view provider.

The command looks at what is selected, like Fusion:
  faces of the body        -> new Press Pull feature, drag the arrow or type a distance
  a face made by a fillet  -> edit that fillet's radius (or a chamfer's size)
  edges                    -> new fillet, the distance is the radius
Nothing selected: the dialog opens and waits for you to pick faces or edges.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, presspull, presspull_core as core, ui_icon_path, warn
from .compat import QtWidgets
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
        Gui.ActiveDocument.setEdit(vobj.Object.Name)
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
    body = commands.active_body()
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


class PressPullPanel(Panel):
    title = "Press Pull"
    icon = "press_pull"
    last = None  # the most recent panel (for tests and diagnostics)

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Press Pull" if feature is None else "Edit Press Pull")
        PressPullPanel.last = self
        self.body, self.tip = _body_and_tip()
        self.mode = None  # "faces" | "fillet" | "edit_blend"
        self.target = feature  # the feature being created or edited
        self.dragger = None
        self.observer = None

        self.what = QtWidgets.QLabel(
            "Select faces to push or pull, edges to fillet,\n"
            "or a fillet face to change its radius."
        )
        self.layout.addRow(self.what)
        self.field_label = QtWidgets.QLabel("Distance")
        self.field = DistanceField(0.0, on_change=self._typed)
        self.layout.addRow(self.field_label, self.field.widget)
        self.finish_layout()

        if feature is not None:
            self.mode = "faces"
            self.body = feature.getParentGeoFeatureGroup()
            self.field.set_value(feature.Distance.Value)
            self.field.bind(feature, "Distance")
            self._describe()
            self._make_dragger()
        elif not self._start_from_selection():
            self._watch_selection()

    def feature(self):
        return self.target

    # -- starting --------------------------------------------------------------
    def _start_from_selection(self):
        if self.body is None or self.tip is None or self.tip.Shape.isNull():
            self.message.setText("Make a solid first (Create Sketch, then Extrude).")
            return True
        faces, edges = _selection(self.tip)
        if not faces and not edges:
            return False
        shape = self.tip.Shape
        if faces:
            blend = (
                core.owning_fillet(self.body, faces[0]) if core.is_round_blend(faces[0]) else None
            )
            if blend is not None and len(faces) == 1:
                return self._start_blend_edit(blend)
            try:
                names = core.face_names(shape, faces)
            except core.PressPullError as exc:
                self.message.setText(str(exc))
                return True
            self.target = presspull.make(self.body, self.tip, names, 0.0)
            self.mode = "faces"
            self.field.bind(self.target, "Distance")
            self._describe()
            self._make_dragger()
        else:
            names = _edge_names(shape, edges)
            fillet = self.body.newObject("PartDesign::Fillet", "Fillet")
            fillet.Base = (self.tip, names)
            fillet.Radius = 1.0
            fillet.Refine = True
            self.body.Tip = fillet
            self.target = fillet
            self.mode = "fillet"
            self.field_label.setText("Fillet radius")
            self.field.set_value(1.0)
            self.field.bind(fillet, "Radius")
            self.what.setText("%d edge(s): fillet" % len(names))
            self.schedule()
        Gui.Selection.clearSelection()
        return True

    def _start_blend_edit(self, blend):
        self.target = blend
        self.mode = "edit_blend"
        prop = "Radius" if blend.TypeId == "PartDesign::Fillet" else "Size"
        self.prop = prop
        self.field_label.setText("Fillet radius" if prop == "Radius" else "Chamfer distance")
        self.field.set_value(getattr(blend, prop).Value)
        self.field.bind(blend, prop)
        self.what.setText("Editing %s (it stays one step in the timeline)" % blend.Label)
        return True

    def _describe(self):
        count = len(self.target.Faces[1]) if self.target.Faces else 0
        self.what.setText(
            "%d face(s): drag the arrow or type a distance\n"
            "(+ adds material, − removes it)" % count
        )

    def _make_dragger(self):
        try:
            base = self.target.BaseFeature.Shape
            face = base.getElement(self.target.Faces[1][0])
            u0, u1, v0, v1 = face.ParameterRange
            point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
            normal = core.face_normal(face)
            size = max(4.0, min(base.BoundBox.DiagonalLength * 0.08, 30.0))
            self.dragger = ArrowDragger(
                point,
                normal,
                self.target.Distance.Value,
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
                if panel.target is None and panel._start_from_selection():
                    panel._unwatch()

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    # -- editing ---------------------------------------------------------------
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

    def accept(self):
        if self.target is None:
            self.message.setText("Nothing selected yet.")
            return False
        return super().accept()

    def cleanup(self):
        self._unwatch()
        if self.dragger is not None:
            self.dragger.remove()
            self.dragger = None
        super().cleanup()


class PressPullCommand:
    def GetResources(self):
        return {
            "MenuText": "Press Pull",
            "ToolTip": "Push or pull faces, fillet edges, or change a "
            "fillet's radius, with a live preview (Q)",
            "Pixmap": ui_icon_path("press_pull"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None and not Gui.Control.activeDialog()

    def Activated(self):
        try:
            doc = App.ActiveDocument
            Gui.Control.showDialog(PressPullPanel(doc))
            log("press pull started")
        except Exception as exc:
            warn("Press Pull failed to start: %s" % exc)
