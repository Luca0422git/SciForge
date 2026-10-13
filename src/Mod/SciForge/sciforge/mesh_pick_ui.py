# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Erase and Fill and Delete: faces of a mesh body picked with a brush.

Fusion does these in Direct Edit (its Mesh Selection Palette starts in paint selection): a
click takes the faces around it within the Brush Size (Ctrl+click takes them off again),
the picked faces are shown in red. Erase and Fill closes the gap they leave (Type Uniform
with a Density, or Minimal: no new points); Delete leaves it open. Each is one timeline
step; the picks are kept as the faces' centres, so they are found again when the body is
rebuilt by an earlier step (a face that is no longer there is reported). Spec:
docs/sciforge/parity/mesh.md."""

import FreeCAD as App
import FreeCADGui as Gui

from . import insert_ui, log, mesh, mesh_ui, warn
from . import mesh_core as core
from .compat import QtCore, QtWidgets


class FacetMarks:
    """The picked faces drawn in red over the body."""

    def __init__(self, view):
        from pivy import coin

        self.view = view
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(-2.0)
        offset.units.setValue(-2.0)
        self.root.addChild(offset)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.94, 0.34, 0.30)
        material.emissiveColor.setValue(0.45, 0.10, 0.08)
        material.transparency.setValue(0.25)
        self.root.addChild(material)
        self.coords = coin.SoCoordinate3()
        self.root.addChild(self.coords)
        self.faces = coin.SoFaceSet()
        self.root.addChild(self.faces)
        view.getSceneGraph().addChild(self.root)

    def show(self, points, facets, picked):
        coords = []
        for index in picked:
            for i in facets[index]:
                coords.append(tuple(points[i]))
        self.coords.point.setNum(0)
        if coords:
            self.coords.point.setValues(0, len(coords), coords)
            self.faces.numVertices.setValues(0, len(picked), [3] * len(picked))
        else:
            self.faces.numVertices.setNum(0)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class FacePickPanel(mesh_ui.MeshPanel):
    """What Erase and Fill and Delete share: the Faces box, Brush Size, Clear."""

    preview_box = False

    def build(self):
        self.picked_faces = []  # facet indices of the body's mesh
        self.faces_field = self.add_field("faces", "Faces", "Select faces")
        self.brush = self.number("Brush Size", 2.0, "mm", lambda: None)
        self.button_row(("Clear Faces", self.clear_faces))
        self.marks = None
        self._topology = None
        self._neighbours = None

    def first_waiting(self):
        return "faces"

    def after_body(self):
        self._topology = None
        self._neighbours = None
        if not self.editing:
            try:
                size = mesh.size_of(mesh.global_mesh(self.body))
                self._quiet = True
                try:
                    self.brush.set_value(round(max(size * 0.05, 0.1), 2))
                finally:
                    self._quiet = False
            except Exception:
                pass

    def topology(self):
        if self._topology is None and self.body is not None:
            self._topology = mesh.topology(mesh.global_mesh(self.body))
            self._neighbours = None
        return self._topology

    def pick_other(self, name, obj, sub, point):
        if name != "faces" or point is None:
            return
        if obj is not self.body and obj not in self.own_objects():
            if mesh_ui.body_end(obj) and not self.picked_faces:
                self.pick_body(obj)
            return
        seed = mesh_ui.facet_at(self.body, point)
        if seed is None:
            return
        points, facets = self.topology()
        if self._neighbours is None:
            self._neighbours = core.facet_neighbours(facets)
        radius = max(float(self.brush.value()), 0.0)
        found = core.facets_near(points, facets, seed, radius, self._neighbours)
        remove = bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier)
        current = set(self.picked_faces)
        if remove:
            current -= set(found)
        else:
            current |= set(found)
        self.set_faces(sorted(current))

    def set_faces(self, indices):
        self.picked_faces = list(indices)
        count = len(self.picked_faces)
        self.faces_field.set_text("%d face%s" % (count, "" if count == 1 else "s") if count else "")
        self.draw_marks()
        self.changed()

    def clear_faces(self):
        self.set_faces([])

    def cleared(self, name):
        if name == "faces":
            self.clear_faces()

    def draw_marks(self):
        if self.view is None:
            return
        try:
            if self.marks is None:
                self.marks = FacetMarks(self.view)
            topology = self.topology()
            if topology is not None:
                self.marks.show(topology[0], topology[1], self.picked_faces)
        except Exception as exc:
            log("face marks: %s" % exc)

    def picks(self):
        topology = self.topology()
        if topology is None:
            return []
        points, facets = topology
        return [App.Vector(*core.centroid(points, facets[i])) for i in self.picked_faces]

    def load(self, feature):
        try:
            source = mesh.global_mesh(feature.Source)
            points, facets = mesh.topology(source)
            quantum = max(1e-6 * mesh.size_of(source), 1e-9)
            found, _lost = core.find_facets(
                points, facets, [tuple(p) for p in feature.Picks], quantum
            )
            self._topology = (points, facets)
            self.picked_faces = found
            self.faces_field.set_text("%d faces" % len(found) if found else "")
            QtCore.QTimer.singleShot(0, self.draw_marks)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def write(self, step):
        step.Picks = self.picks()
        mesh.hold(step, not self.picked_faces)  # nothing picked yet: the body as it is

    def _hold_by_preview(self):
        if self.step is not None:
            mesh.hold(self.step, not self.picked_faces)

    def report(self):
        mesh_ui.MeshPanel.report(self)
        if self.step is not None and not self.picked_faces:
            self.message.setText("")
            self.say(
                "Click the faces on the body (each click takes the faces within the "
                "Brush Size; Ctrl+click takes them off)."
            )

    def accept(self):
        if self.step is not None and not self.picked_faces:
            self.message.setText("⚠ Pick the faces first (click them on the body).")
            return False
        return mesh_ui.MeshPanel.accept(self)

    def cleanup(self):
        if self.marks is not None:
            self.marks.remove()
            self.marks = None
        mesh_ui.MeshPanel.cleanup(self)


class EraseFillPanel(FacePickPanel):
    """Fusion's Erase and Fill: the picked faces erased and the gap filled; Type Uniform
    (even faces, Density) or Minimal (fewest faces)."""

    title = "Erase and Fill"
    icon = "mesh_erase_fill"
    step_kind = "MeshEraseFill"
    wait_text = "Click the mesh body, then the faces to erase."

    def build(self):
        super().build()
        self.fill = self.combo("Type", core.ERASE_FILL_TYPES, "Uniform", self.changed)
        self.density = self.spin("Density", core.ERASE_DENSITY, 0.0, 1.0, self.changed, 2, 0.05)

    def changed(self):
        self.density.setEnabled(self.fill.currentText() == "Uniform")
        super().changed()

    def load(self, feature):
        super().load(feature)
        self._quiet = True
        try:
            self.fill.setCurrentText(feature.FillType)
            self.density.setValue(float(feature.Density))
        finally:
            self._quiet = False

    def write(self, step):
        super().write(step)
        step.FillType = self.fill.currentText()
        step.Density = float(self.density.value())


class DeleteFacesPanel(FacePickPanel):
    """Fusion's Delete in Direct Edit: the picked faces removed, the hole left open (Repair
    or Erase and Fill close it again)."""

    title = "Delete Faces"
    icon = "mesh_delete_faces"
    step_kind = "MeshDeleteFaces"
    wait_text = "Click the mesh body, then the faces to delete."


class EraseFillCommand(mesh_ui._MeshCommand):
    text = "Erase and Fill"
    tip = "Erase faces of a mesh body and fill the gap"
    icon = "mesh_erase_fill"
    panel = EraseFillPanel


class DeleteFacesCommand(mesh_ui._MeshCommand):
    text = "Delete Faces"
    tip = "Delete faces of a mesh body (the hole stays open)"
    icon = "mesh_delete_faces"
    panel = DeleteFacesPanel


def _edit(panel_class):
    def edit(obj):
        return insert_ui._edit(panel_class, mesh.step_of(obj))

    return edit


COMMANDS = {
    "SciForge_MeshEraseFill": EraseFillCommand,
    "SciForge_MeshDeleteFaces": DeleteFacesCommand,
}
EDITORS = {
    "SciForge::MeshEraseFill": _edit(EraseFillPanel),
    "SciForge::MeshDeleteFaces": _edit(DeleteFacesPanel),
}
_ = Gui
