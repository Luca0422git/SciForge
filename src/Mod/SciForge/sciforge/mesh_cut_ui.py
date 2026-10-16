# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Plane Cut and Create Mesh Section Sketch: a mesh body and a plane.

The plane is an origin plane (drawn as a square to click while the Plane box waits: a mesh
design may have no body with an origin of its own), a construction plane or a flat face.
Like Fusion's, the plane then has an arrow to drag it along its normal and two balls to tilt
it about its own axes, each with a value box (Distance, X Angle, Y Angle in the dialog too).
Plane Cut: Type Trim / Split Body / Split Faces, Fill Type No Fill / Uniform / Minimal, Flip
(which side Trim takes away), all previewed as you go. Section Sketch: a sketch on the plane
holding where the plane cuts the mesh. Spec: docs/sciforge/parity/mesh.md."""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, handles3d, insert_ui, log, mesh, mesh_ui, origin_look, taskui
from . import warn
from . import mesh_core as core
from .compat import QtCore

V = App.Vector
# role -> (normal, x axis): FreeCAD's origin planes (the XZ plane faces -Y)
ORIGIN_PLANES = {
    "XY": (V(0, 0, 1), V(1, 0, 0)),
    "XZ": (V(0, -1, 0), V(1, 0, 0)),
    "YZ": (V(1, 0, 0), V(0, 1, 0)),
}
CUT_LOOK = ((0.30, 0.62, 0.95), 0.70)


def origin_frame(role):
    normal, x_axis = ORIGIN_PLANES[role]
    return mesh.frame_placement((0.0, 0.0, 0.0), tuple(normal), tuple(x_axis))


# ============================================================================ origin squares
class OriginSquares:
    """The three origin planes as big squares at the design's origin; on_pick(role) when one
    is clicked (the press, as FreeCAD's selection keeps the release)."""

    def __init__(self, view, size, on_pick):
        from pivy import coin

        self.view = view
        self.size = float(size)
        self.on_pick = on_pick
        self.materials = {}
        self.looks = {}
        self.hovered = None
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.root.addChild(coin.SoPolygonOffset())
        for role in ORIGIN_PLANES:
            self.materials[role] = self._square(coin, role)
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]

    def corners(self, role):
        frame = origin_frame(role)
        u = frame.Rotation.multVec(V(1, 0, 0))
        v = frame.Rotation.multVec(V(0, 1, 0))
        h = self.size / 2.0
        return [u * a * h + v * b * h for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    def point_on(self, role, a=0.35, b=0.35):
        """A point on a square (fractions of its half size along its two axes): tests click
        it there."""
        frame = origin_frame(role)
        u = frame.Rotation.multVec(V(1, 0, 0))
        v = frame.Rotation.multVec(V(0, 1, 0))
        h = self.size / 2.0
        return u * a * h + v * b * h

    def _square(self, coin, role):
        """A square coloured and labelled like Create Sketch's (origin_look)."""
        corners = self.corners(role)
        spot = corners[2] * origin_look.LABEL_INSET
        self.looks[role] = origin_look.SquareLook(coin, self.root, role, corners, spot)
        return self.looks[role].material

    def role_at(self, position):
        from .profile_pick import ray_plane

        best = None
        for role in ORIGIN_PLANES:
            frame = origin_frame(role)
            normal = frame.Rotation.multVec(V(0, 0, 1))
            hit = ray_plane(self.view, position, V(0, 0, 0), normal)
            if hit is None:
                continue
            point, t = hit
            u = frame.Rotation.multVec(V(1, 0, 0))
            v = frame.Rotation.multVec(V(0, 1, 0))
            h = self.size / 2.0
            if abs(point.dot(u)) <= h and abs(point.dot(v)) <= h:
                if best is None or t < best[1]:
                    best = (role, t)
        return best[0] if best else None

    def _moved(self, info):
        try:
            role = self.role_at(info["Position"])
            if role != self.hovered:
                for name, lit in ((self.hovered, False), (role, True)):
                    if name in self.looks:
                        self.looks[name].paint(lit)
                self.hovered = role
        except Exception as exc:
            warn("origin planes: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            if handles3d.just_used():
                return
            role = self.role_at(info["Position"])
            if role is not None:
                QtCore.QTimer.singleShot(0, lambda r=role: self.on_pick(r))
        except Exception as exc:
            warn("origin planes: %s" % exc)

    def remove(self):
        for kind, callback in self.callbacks:
            try:
                self.view.removeEventCallback(kind, callback)
            except Exception:
                pass
        self.callbacks = []
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class PlaneLook:
    """The cut plane drawn as a see-through square where it cuts."""

    def __init__(self, view):
        from pivy import coin

        self.view = view
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.material = coin.SoMaterial()
        self.material.diffuseColor.setValue(*CUT_LOOK[0])
        self.material.emissiveColor.setValue(*[c * 0.4 for c in CUT_LOOK[0]])
        self.material.transparency.setValue(CUT_LOOK[1])
        self.root.addChild(self.material)
        self.coords = coin.SoCoordinate3()
        self.root.addChild(self.coords)
        faces = coin.SoFaceSet()
        faces.numVertices.setValue(4)
        self.root.addChild(faces)
        view.getSceneGraph().addChild(self.root)

    def show(self, frame, size):
        h = size / 2.0
        u = frame.Rotation.multVec(V(1, 0, 0))
        v = frame.Rotation.multVec(V(0, 1, 0))
        corners = [
            frame.Base + u * a * h + v * b * h for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        self.coords.point.setValues(0, 4, [(p.x, p.y, p.z) for p in corners])

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


# ============================================================================ the plane rows
class PlaneRows:
    """What Plane Cut and Section Sketch share: the Plane box (origin squares, construction
    planes, flat faces), Distance / X Angle / Y Angle, the arrow, the two balls and their
    value boxes, the plane drawn."""

    def plane_rows(self, angles=True):
        self.frame = None  # the picked plane (a placement)
        self.reference = None  # (object, [subname]) of a picked construction plane or face
        self.squares = None
        self.handles = {}
        self.look = None
        self.plane_field = self.add_field("plane", "Plane", "Select a plane")
        self.distance = self.number("Distance", 0.0, "mm", lambda: self.plane_changed())
        self.angle_x = self.angle_y = None
        if angles:
            self.angle_x = self.number("X Angle", 0.0, "deg", lambda: self.plane_changed())
            self.angle_y = self.number("Y Angle", 0.0, "deg", lambda: self.plane_changed())
        self.value_boxes = taskui.ValueBoxes(self, default="distance")

    def plane_values(self):
        ax = float(self.angle_x.value()) if self.angle_x is not None else 0.0
        ay = float(self.angle_y.value()) if self.angle_y is not None else 0.0
        return float(self.distance.value()), ax, ay

    def cut_frame(self):
        if self.frame is None:
            return None
        d, ax, ay = self.plane_values()
        return mesh.tilted_frame(self.frame, d, ax, ay)

    def body_size(self):
        try:
            box = mesh.global_mesh(self.body).BoundBox if self.body is not None else None
            if box is not None:
                return max(10.0, box.DiagonalLength)
        except Exception:
            pass
        return 50.0

    # -- the squares while Plane waits ------------------------------------------------------
    def show_squares(self, on):
        if on and self.squares is None and self.view is not None:
            try:
                self.squares = OriginSquares(
                    self.view, origin_look.square_size(self.body_size()), self._square_picked
                )
            except Exception as exc:
                warn("origin planes: %s" % exc)
        elif not on and self.squares is not None:
            self.squares.remove()
            self.squares = None

    def _square_picked(self, role):
        if getattr(self, "_closed", False) or self.active != "plane":
            return
        try:  # called from a timer: nothing may escape
            self.set_plane(origin_frame(role), None)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def pick_plane(self):
        """A construction plane or flat face from the selection (the top object and its full
        path, so the face is found where it is in the design)."""
        import Part

        for sel in Gui.Selection.getSelectionEx("", 0):
            if sel.Document.Name != self.doc.Name:
                continue
            for sub in list(sel.SubElementNames) or [""]:
                ref = (sel.Object, [sub])
                frame = mesh.plane_frame_of(ref)
                if frame is not None:
                    return frame, ref
                try:
                    target = sel.Object.getSubObject(sub, retType=1) if sub else sel.Object
                except Exception:
                    target = None
                if target is not None and target.TypeId in ("PartDesign::Plane", "App::Plane"):
                    ref = (target, [""])
                    frame = mesh.plane_frame_of(ref)
                    if frame is not None:
                        return frame, ref
                _ = Part
        return None

    def set_plane(self, placement, reference):
        self.frame = placement
        self.reference = reference
        self.plane_field.set_text(self._plane_name())
        self.show_squares(False)
        self.plane_changed()
        self.set_active(self.first_waiting())

    def _plane_name(self):
        if self.reference is not None:
            obj, subs = self.reference
            sub = subs[0] if subs else ""
            return "%s %s" % (obj.Label, sub.split(".")[-1]) if sub else obj.Label
        for role in ORIGIN_PLANES:
            if self.frame is not None and self.frame.isSame(origin_frame(role), 1e-9):
                return "%s plane" % role
        return "Plane"

    def plane_changed(self):
        """Distance, an angle or the plane changed (a field, an arrow, a ball)."""
        self.rebuild_handles()
        self.changed()

    # -- the arrow and the balls --------------------------------------------------------------
    def remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def rebuild_handles(self):
        if self.view is None:
            return
        frame = self.cut_frame()
        dragging = [k for k, h in self.handles.items() if getattr(h, "dragging", lambda: False)()]
        if frame is None:
            self.remove_handles()
            if self.look is not None:
                self.look.remove()
                self.look = None
            return
        size = self.body_size()
        if self.look is None:
            try:
                self.look = PlaneLook(self.view)
            except Exception as exc:
                warn("plane: %s" % exc)
        if self.look is not None:
            self.look.show(frame, size * 0.9)
        if dragging:
            return  # the handle being dragged is moved by its own poll
        self.remove_handles()
        d, ax, ay = self.plane_values()
        base = self.frame
        moved = mesh.tilted_frame(base, d, 0.0, 0.0)
        after_x = mesh.tilted_frame(base, d, ax, 0.0)
        n = base.Rotation.multVec(V(0, 0, 1))
        try:
            self.handles["distance"] = handles3d.LinearHandle(
                base.Base,
                n,
                d,
                size * 0.2,
                on_drag=self._dragged_distance,
                on_release=self._released,
            )
            self.value_boxes.attach(
                self.handles["distance"],
                "distance",
                lambda: self.distance.widget.text(),
                self._typed_distance,
            )
            if self.angle_x is not None:
                x_axis = moved.Rotation.multVec(V(1, 0, 0))
                y_axis = moved.Rotation.multVec(V(0, 1, 0))
                self.handles["x"] = handles3d.angle_handle(
                    moved.Base,
                    x_axis,
                    y_axis,
                    size * 0.45,
                    ax,
                    size * 0.08,
                    on_drag=self._dragged_x,
                    on_release=self._released,
                )
                self.value_boxes.attach(
                    self.handles["x"], "x", lambda: self.angle_x.widget.text(), self._typed_x
                )
                y_axis_x = after_x.Rotation.multVec(V(0, 1, 0))
                x_axis_x = after_x.Rotation.multVec(V(1, 0, 0))
                self.handles["y"] = handles3d.angle_handle(
                    moved.Base,
                    y_axis_x,
                    x_axis_x,
                    size * 0.45,
                    ay,
                    size * 0.08,
                    on_drag=self._dragged_y,
                    on_release=self._released,
                )
                self.value_boxes.attach(
                    self.handles["y"], "y", lambda: self.angle_y.widget.text(), self._typed_y
                )
        except Exception as exc:
            warn("%s handles: %s" % (self.title, exc))

    def _set_quiet(self, field, value):
        self._quiet = True
        try:
            field.set_value(value)
        finally:
            self._quiet = False

    def _dragged_distance(self, value):
        try:
            self._set_quiet(self.distance, round(float(value), 3))
            if self.look is not None and self.frame is not None:
                self.look.show(self.cut_frame(), self.body_size() * 0.9)
            self.changed()
        except Exception as exc:
            warn("%s drag: %s" % (self.title, exc))

    def _dragged_x(self, value):
        try:
            self._set_quiet(self.angle_x, round(float(value), 2))
            self.changed()
        except Exception as exc:
            warn("%s drag: %s" % (self.title, exc))

    def _dragged_y(self, value):
        try:
            self._set_quiet(self.angle_y, round(float(value), 2))
            self.changed()
        except Exception as exc:
            warn("%s drag: %s" % (self.title, exc))

    def _released(self, _value=None):
        QtCore.QTimer.singleShot(0, self._after_release)

    def _after_release(self):
        if getattr(self, "_closed", False):
            return
        try:  # called from a timer: nothing may escape
            self.rebuild_handles()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def _typed(self, field, text):
        try:  # typed into a value box over the view (a key event): nothing may escape
            value = field.parse(text)
            if value is None:
                return False
            field.set_value(value)
            self.plane_changed()
            return True
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            return False

    def _typed_distance(self, text):
        return self._typed(self.distance, text)

    def _typed_x(self, text):
        return self._typed(self.angle_x, text)

    def _typed_y(self, text):
        return self._typed(self.angle_y, text)

    def cleanup_plane(self):
        self.show_squares(False)
        self.remove_handles()
        try:
            self.value_boxes.discard()
        except Exception:
            pass
        if self.look is not None:
            self.look.remove()
            self.look = None


# ============================================================================ Plane Cut
class PlaneCutPanel(PlaneRows, mesh_ui.MeshPanel):
    """Fusion's Plane Cut: Body, Plane, Type Trim / Split Body / Split Faces, Fill Type
    (Trim and Split Body) No Fill / Uniform / Minimal, Flip, and the plane's Distance and
    angles with their handles. Trim takes away the side the plane faces (Flip: the other)."""

    title = "Plane Cut"
    icon = "mesh_plane_cut"
    step_kind = "MeshPlaneCut"
    preview_box = False
    wait_text = "Click the mesh body to cut, then a plane."

    def build(self):
        self.plane_rows()
        self.cut_type = self.combo("Type", core.CUT_TYPES, "Trim", self.changed)
        self.fill = self.combo("Fill Type", core.FILL_TYPES, core.DEFAULT_FILL, self.changed)
        self.flip = self.check("Flip", False, self.changed)
        self._rows_for_type()

    def _rows_for_type(self):
        self.fill.setEnabled(self.cut_type.currentText() != "Split Faces")
        self.flip.setEnabled(self.cut_type.currentText() != "Split Faces")

    def changed(self):
        self._rows_for_type()
        mesh_ui.MeshPanel.changed(self)

    def first_waiting(self):
        return "plane" if self.frame is None else None

    def set_active(self, name):
        mesh_ui.MeshPanel.set_active(self, name)
        self.show_squares(name == "plane")

    def picked(self, obj, sub, point):
        if self.active == "plane":
            found = self.pick_plane()
            if found is not None:
                (origin, normal, u), ref = found
                self.set_plane(mesh.frame_placement(origin, normal, u), ref)
            elif obj not in self.own_objects():
                commands.tell(
                    "Click an origin plane (the squares), a construction plane or a flat face."
                )
            return
        mesh_ui.MeshPanel.picked(self, obj, sub, point)

    def selection_changed(self, point=None):
        if getattr(self, "_closed", False):
            return
        if self.active == "plane":
            try:
                if not Gui.Selection.getSelectionEx():
                    return
                found = self.pick_plane()
                Gui.Selection.clearSelection()
                if handles3d.just_used():
                    return
                if found is not None:
                    (origin, normal, u), ref = found
                    self.set_plane(mesh.frame_placement(origin, normal, u), ref)
            except Exception as exc:
                warn("%s: %s" % (self.title, exc))
            return
        if handles3d.just_used():
            Gui.Selection.clearSelection()
            return
        mesh_ui.MeshPanel.selection_changed(self, point)

    def cleared(self, name):
        if name == "plane":
            self.frame = None
            self.reference = None
            self.plane_field.set_text("")
            self.remove_handles()
            if self.look is not None:
                self.look.remove()
                self.look = None
            self.set_active("plane")
            self.changed()

    def write(self, step):
        step.CutType = self.cut_type.currentText()
        step.FillType = self.fill.currentText()
        step.Flip = self.flip.isChecked()
        d, ax, ay = self.plane_values()
        step.Distance = d
        step.AngleX = ax
        step.AngleY = ay
        if self.frame is not None:
            step.PlaneFrame = self.frame
        try:
            step.Plane = (self.reference[0], self.reference[1]) if self.reference else None
        except Exception:
            step.Plane = None
        mesh.hold(step, self.frame is None)  # nothing to cut with yet: the body as it is

    def load(self, feature):
        self._quiet = True
        try:
            self.cut_type.setCurrentText(feature.CutType)
            self.fill.setCurrentText(feature.FillType)
            self.flip.setChecked(bool(feature.Flip))
            self.distance.set_value(float(feature.Distance))
            self.angle_x.set_value(float(feature.AngleX))
            self.angle_y.set_value(float(feature.AngleY))
        finally:
            self._quiet = False
        ref = feature.Plane
        self.reference = (ref[0], list(ref[1])) if ref else None
        frame = mesh.plane_frame_of(self.reference) if self.reference else None
        self.frame = mesh.frame_placement(*frame) if frame else feature.PlaneFrame
        self.plane_field.set_text(self._plane_name())
        self._rows_for_type()
        self.rebuild_handles()

    def _hold_by_preview(self):
        if self.step is not None:
            mesh.hold(self.step, self.frame is None)

    def sync_pieces(self):
        wanted = (
            2 if self.cut_type.currentText() == "Split Body" and not mesh.problem(self.step) else 0
        )
        if self.frame is None:
            wanted = 0
        if len(mesh.pieces_of(self.step)) == wanted:
            return False
        mesh.set_piece_count(self.step, wanted, self.body.Label if self.body else self.step.Label)
        return True

    def report(self):
        mesh_ui.MeshPanel.report(self)
        if self.step is not None and self.frame is None:
            self.say(
                "Click a plane to cut along: an origin plane (the squares), a construction "
                "plane or a flat face."
            )

    def _accept(self):
        if self.step is not None and self.frame is None:
            self.message.setText("⚠ Click a plane to cut along first.")
            return False
        return mesh_ui.MeshPanel._accept(self)

    def cleanup(self):
        self.cleanup_plane()
        mesh_ui.MeshPanel.cleanup(self)


# ============================================================================ Section Sketch
class SectionSketchPanel(PlaneRows, mesh_ui.MeshPanel):
    """Fusion's Create Mesh Section Sketch: a mesh body and a plane (moved by Distance); OK
    makes a sketch on that plane with the line where the plane cuts the mesh (fixed lines,
    green, like an inserted drawing: trace over them or extrude a closed one)."""

    title = "Create Mesh Section Sketch"
    icon = "mesh_section"
    step_kind = None
    preview_box = False
    wait_text = "Click the mesh body, then the plane to cut it with."

    def build(self):
        self.plane_rows(angles=False)
        self.lines = None

    def first_waiting(self):
        return "plane" if self.frame is None else None

    def set_active(self, name):
        mesh_ui.MeshPanel.set_active(self, name)
        self.show_squares(name == "plane")

    def set_body(self, obj):
        # no mesh step: the dialog only remembers the body
        self.body = obj
        self.fields["body"].set_text(obj.Label)
        self.set_active(self.first_waiting())
        self.changed()

    def picked(self, obj, sub, point):
        PlaneCutPanel.picked(self, obj, sub, point)

    def selection_changed(self, point=None):
        PlaneCutPanel.selection_changed(self, point)

    def cleared(self, name):
        if name == "plane":
            self.frame = None
            self.reference = None
            self.plane_field.set_text("")
            self.remove_handles()
            self.set_active("plane")
            self.changed()

    def changed(self):
        self.schedule()

    def own_objects(self):
        return []

    def _recompute(self):
        if getattr(self, "_closed", False):
            return
        self.draw_section()

    def section(self):
        frame = self.cut_frame()
        if frame is None or self.body is None:
            return None
        normal = tuple(frame.Rotation.multVec(V(0, 0, 1)))
        source = mesh.global_mesh(self.body)
        tolerance = max(mesh.size_of(source) * 2e-4, 1e-4)
        return mesh.section_polylines(source, tuple(frame.Base), normal, tolerance)

    def draw_section(self):
        try:
            lines = self.section()
        except Exception as exc:
            log("section: %s" % exc)
            lines = None
        self.lines = lines
        if lines is None:
            self.say(self.wait_text if self.body is None else "Click a plane to cut along.")
            self.message.setText("")
            self._draw([])
            return
        if not lines:
            self.message.setText("⚠ The plane does not cut the body: move it onto the body.")
            self._draw([])
            return
        self.message.setText("")
        count = sum(len(line) - 1 for line in lines)
        self.say(
            "%d section line%s, %d segments" % (len(lines), "" if len(lines) == 1 else "s", count)
        )
        self._draw(lines)

    def _draw(self, lines):
        try:
            if not hasattr(self, "_overlay") or self._overlay is None:
                self._overlay = SectionOverlay(self.view)
            self._overlay.show(lines)
        except Exception as exc:
            log("section overlay: %s" % exc)

    def report(self):
        pass

    def _accept(self):
        if self.body is None:
            self.message.setText("⚠ " + self.wait_text)
            return False
        if self.frame is None:
            self.message.setText("⚠ Click a plane to cut along first.")
            return False
        lines = self.section()
        if not lines:
            self.message.setText("⚠ The plane does not cut the body: move it onto the body.")
            return False
        try:
            sketch = make_section_sketch(self.doc, self.body, self.cut_frame(), self.reference)
        except core.MeshError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        self.cleanup()
        taskui._end_transaction(self.doc)
        self._close()
        log("%s done: %s" % (self.title, sketch.Label))
        return True

    def reject(self):
        self.cleanup()
        taskui._end_transaction(self.doc, abort=True)
        self.doc.recompute()
        self._close()
        return True

    def cleanup(self):
        self.cleanup_plane()
        overlay = getattr(self, "_overlay", None)
        if overlay is not None:
            overlay.remove()
            self._overlay = None
        mesh_ui.MeshPanel.cleanup(self)


class SectionOverlay:
    """The section drawn over the part while the dialog is open."""

    def __init__(self, view):
        from pivy import coin

        self.view = view
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.96, 0.62, 0.20)
        self.root.addChild(material)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(2.5)
        self.root.addChild(style)
        self.coords = coin.SoCoordinate3()
        self.root.addChild(self.coords)
        self.lineset = coin.SoLineSet()
        self.root.addChild(self.lineset)
        view.getSceneGraph().addChild(self.root)

    def show(self, lines):
        points = []
        counts = []
        for line in lines:
            points += [tuple(p) for p in line]
            counts.append(len(line))
        self.coords.point.setNum(0)
        if points:
            self.coords.point.setValues(0, len(points), points)
            self.lineset.numVertices.setValues(0, len(counts), counts)
        else:
            self.lineset.numVertices.setNum(0)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


def make_section_sketch(doc, body_obj, frame, reference):
    """The sketch of Create Mesh Section Sketch, in the active body (made if there is none),
    on the plane `frame` (its own attachment: the picked plane or face, else the body's
    origin plane of the same direction), holding the section lines fixed."""
    from . import sketch_ui

    body = commands.find_body() or commands.ensure_body()
    if body is None:
        raise core.MeshError("A sketch needs a body to belong to, and none could be made.")
    target = None
    offset = App.Placement()
    if reference is not None:
        obj, subs = reference
        sub = subs[0] if subs else ""
        resolved = obj
        short = sub
        if sub and "." in sub:
            try:
                resolved = obj.getSubObject(sub.rsplit(".", 1)[0] + ".", retType=1) or obj
            except Exception:
                resolved = obj
            short = sub.rsplit(".", 1)[1]
        target = (resolved, short)
    else:
        roles = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
        for role, name in roles.items():
            if frame.Rotation.multVec(V(0, 0, 1)).isEqual(
                origin_frame(role).Rotation.multVec(V(0, 0, 1)), 1e-9
            ):
                planes = sketch_ui.origin_planes(body)
                plane = planes.get(name) if isinstance(planes, dict) else None
                if plane is not None:
                    target = (plane, "")
                break
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.Label = "Mesh Section %s" % body_obj.Label
    if target is not None:
        sketch.AttachmentSupport = [target]
        sketch.MapMode = "FlatFace"
        doc.recompute()
        attached = sketch.getGlobalPlacement()
        offset = attached.inverse().multiply(frame)
        sketch.AttachmentOffset = offset
    else:
        sketch.MapMode = "Deactivated"
        sketch.Placement = body.getGlobalPlacement().inverse().multiply(frame)
    doc.recompute()
    mesh.section_into_sketch(sketch, mesh.global_mesh(body_obj))
    doc.recompute()
    return sketch


# ============================================================================ commands
class PlaneCutCommand(mesh_ui._MeshCommand):
    text = "Plane Cut"
    tip = "Trim or split a mesh body with a plane, closing the cut"
    icon = "mesh_plane_cut"
    panel = PlaneCutPanel


class SectionSketchCommand(mesh_ui._MeshCommand):
    text = "Create Mesh Section Sketch"
    tip = "A sketch of where a plane cuts a mesh body"
    icon = "mesh_section"
    panel = SectionSketchPanel


def _edit_cut(obj):
    return insert_ui._edit(PlaneCutPanel, mesh.step_of(obj))


COMMANDS = {
    "SciForge_MeshPlaneCut": PlaneCutCommand,
    "SciForge_MeshSectionSketch": SectionSketchCommand,
}
EDITORS = {"SciForge::MeshPlaneCut": _edit_cut}
_ = bodies
