# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style profile picking: closed sketch shapes are shaded, light up under the
mouse and are picked by clicking anywhere inside them (FreeCAD can only pick a
sketch by its lines).

ProfilePicker(view, sketches, on_pick) shows the shading and calls
on_pick(sketch) when the user clicks inside one. remove() takes it all away.
Mouse events come through FreeCAD's view.addEventCallback, which runs Python
safely (unlike raw pivy callbacks, see taskui.ArrowDragger).
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import warn

FILL = (0.45, 0.77, 1.0)  # Fusion-like profile blue
IDLE_TRANSPARENCY = 0.65
HOVER_TRANSPARENCY = 0.25


def sketch_faces(sketch):
    """Faces (global coordinates) made from the closed wires of a sketch, or []."""
    import Part

    try:
        shape = sketch.Shape.copy()
        shape.Placement = sketch.getGlobalPlacement()
        wires = [w for w in shape.Wires if w.isClosed()]
        if not wires:
            return []
        made = Part.makeFace(wires, "Part::FaceMakerBullseye")
        return list(made.Faces)
    except Exception as exc:
        warn("no profile for %s: %s" % (sketch.Label, exc))
        return []


def mouse_ray(view, position):
    """(point, direction) of the line under the mouse, pointing into the screen."""
    point = view.getPoint(tuple(position))
    if view.getCameraType() == "Perspective":
        eye = App.Vector(*view.getCameraNode().position.getValue().getValue())
        return point, point - eye
    return point, view.getViewDirection()


def ray_plane(view, position, base, normal):
    """(hit point, distance along the ray) where the mouse ray meets a plane, or None."""
    point, direction = mouse_ray(view, position)
    denom = direction.dot(normal)
    if abs(denom) < 1e-9:
        return None
    t = (base - point).dot(normal) / denom
    return point + direction * t, t


def ray_hit(view, position, face):
    """Point where the mouse ray at `position` crosses the plane of `face`, or None."""
    normal = face.Surface.Axis if hasattr(face.Surface, "Axis") else face.normalAt(0, 0)
    hit = ray_plane(view, position, face.CenterOfMass, normal)
    return hit[0] if hit else None


def inside(face, point, tol=1e-4):
    try:
        return face.isInside(point, tol, True)
    except Exception:
        return False


class ProfilePicker:
    def __init__(self, view, sketches, on_pick):
        from pivy import coin

        self.view = view
        self.on_pick = on_pick
        self.regions = []  # (sketch, face, material node)
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        offset = coin.SoPolygonOffset()
        self.root.addChild(offset)
        for sketch in sketches:
            for face in sketch_faces(sketch):
                self.regions.append((sketch, face, self._add_face(coin, face)))
        self.hovered = None
        self.callbacks = []
        if self.regions:
            view.getSceneGraph().addChild(self.root)
            self.callbacks = [
                ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
                ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
            ]

    def _add_face(self, coin, face):
        points, triangles = face.tessellate(0.2)
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*FILL)
        material.emissiveColor.setValue(FILL[0] * 0.4, FILL[1] * 0.4, FILL[2] * 0.4)
        material.transparency.setValue(IDLE_TRANSPARENCY)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        faces = coin.SoIndexedFaceSet()
        index = []
        for a, b, c in triangles:
            index += [a, b, c, -1]
        faces.coordIndex.setValues(0, len(index), index)
        sep.addChild(material)
        sep.addChild(coords)
        sep.addChild(faces)
        self.root.addChild(sep)
        return material

    def region_at(self, position):
        """(sketch, face) under the mouse; the smallest region wins (a hole inside a plate)."""
        best = None
        for sketch, face, material in self.regions:
            point = ray_hit(self.view, position, face)
            if point is not None and inside(face, point):
                if best is None or face.Area < best[1].Area:
                    best = (sketch, face, material)
        return best

    def _moved(self, info):
        try:
            hit = self.region_at(info["Position"])
            material = hit[2] if hit else None
            if material is not self.hovered:
                if self.hovered is not None:
                    self.hovered.transparency.setValue(IDLE_TRANSPARENCY)
                if material is not None:
                    material.transparency.setValue(HOVER_TRANSPARENCY)
                self.hovered = material
        except Exception as exc:
            warn("profile hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            hit = self.region_at(info["Position"])
            if hit is not None:
                self.on_pick(hit[0])
        except Exception as exc:
            warn("profile pick: %s" % exc)

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
        self.regions = []


def candidate_sketches(body):
    """Sketches of the body that can be extruded: unused ones and visible ones."""
    from .extrude_ui import _used_profiles

    if body is None:
        return []
    used = _used_profiles(body)
    found = []
    for obj in body.Group:
        if obj.TypeId != "Sketcher::SketchObject":
            continue
        visible = getattr(obj, "Visibility", False)
        if obj.Name not in used or visible:
            found.append(obj)
    return found
