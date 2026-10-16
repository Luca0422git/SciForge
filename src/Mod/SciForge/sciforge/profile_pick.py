# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion-style profile picking for Extrude.

Every closed region of a sketch is a profile (a circle inside a rectangle gives the
ring and the disc; crossing curves split regions too). The regions are FreeCAD's own
sketch regions ("InternalFaceN", see extrude.regions), so what is shaded here is
exactly what the extrude links to.

ProfilePicker(view, sketches, on_pick) shades the regions, lights one up under the
mouse and calls on_pick(sketch, "InternalFaceN") when the user clicks inside it. A
region hidden behind a face of the part is not picked (the face is). set_selected()
shows the picked ones in a stronger blue, show_faces() highlights picked body faces.
Mouse events come through FreeCAD's view.addEventCallback, which runs Python safely
(unlike raw pivy callbacks, see taskui.ArrowDragger).
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from . import warn

FILL = (0.45, 0.77, 1.0)  # Fusion-like profile blue
PICKED = (0.12, 0.53, 0.90)
IDLE_TRANSPARENCY = 0.65
HOVER_TRANSPARENCY = 0.35
PICKED_TRANSPARENCY = 0.25
DIMMED_TRANSPARENCY = 0.85  # picked, while a red cut preview must show through


def sketch_faces(sketch):
    """Faces (global coordinates) of every region of a sketch, or []."""
    from . import extrude

    try:
        return [face for _sub, face in extrude.regions(sketch)]
    except Exception as exc:
        warn("no profile for %s: %s" % (sketch.Label, exc))
        return []


def mouse_ray(view, position):
    """(point, direction) of the line under the mouse, pointing into the screen."""
    point = view.getPoint(tuple(position))
    if view.getCameraType() == "Perspective":
        eye = App.Vector(*view.getCameraNode().position.getValue().getValue())
        direction = point - eye
        direction.normalize()
        return point, direction
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
    hit = ray_hit_t(view, position, face)
    return hit[0] if hit else None


def ray_hit_t(view, position, face):
    normal = face.Surface.Axis if hasattr(face.Surface, "Axis") else face.normalAt(0, 0)
    return ray_plane(view, position, face.CenterOfMass, normal)


def inside(face, point, tol=1e-4):
    try:
        return face.isInside(point, tol, True)
    except Exception:
        return False


def hidden_by(shape, point, direction):
    """True if `shape` (a solid) is between the viewer and `point` (looking along
    `direction`): then a click there hits the part, not the sketch area."""
    import Part

    if shape is None or shape.isNull() or not shape.Solids:
        return False
    reach = shape.BoundBox.DiagonalLength + (shape.BoundBox.Center - point).Length + 1.0
    gap = 1e-3 * max(1.0, reach)
    start = point - direction * reach
    end = point - direction * gap
    try:
        common = shape.common(Part.makeLine(start, end))
        return common.Length > gap
    except Exception:
        return False


def handle_at(view, position, radius=3):
    """True if the front-most thing under the mouse is a drag handle (a Coin dragger: the
    blue arrows, the taper disc). A press there drags the handle; it is not a pick."""
    from pivy import coin

    try:
        viewer = view.getViewer()
        manager = viewer.getSoRenderManager()
        action = coin.SoRayPickAction(manager.getViewportRegion())
        action.setPoint(coin.SbVec2s(int(position[0]), int(position[1])))
        action.setRadius(radius)
        action.apply(manager.getSceneGraph())
        point = action.getPickedPoint()
        if point is None:
            return False
        path = point.getPath()  # read now: the path dies with the action
        dragger = coin.SoDragger.getClassTypeId()
        return any(path.getNode(i).isOfType(dragger) for i in range(path.getLength()))
    except Exception:
        return False


class TextArea:
    """A whole sketch text as one pickable area (Fusion picks a text as one profile): its
    letters' faces (global), answering what ProfilePicker asks of a face."""

    def __init__(self, faces):
        self.faces = list(faces)
        self.Surface = self.faces[0].Surface
        self.CenterOfMass = self.faces[0].CenterOfMass
        self.Area = sum(f.Area for f in self.faces)

    def isInside(self, point, tol, check_face):
        return any(f.isInside(point, tol, check_face) for f in self.faces)

    def tessellate(self, tol):
        import FreeCAD as _App

        points, triangles = [], []
        for face in self.faces:
            verts, tris = face.tessellate(tol)
            base = len(points)
            points += [_App.Vector(v) for v in verts]
            triangles += [(base + a, base + b, base + c) for a, b, c in tris]
        return points, triangles


def text_areas(sketch):
    """[(text, TextArea)] of a sketch's texts (global coordinates)."""
    from . import extrude, text

    found = []
    for obj in text.texts_of(sketch):
        try:
            if "Touched" in obj.State or obj.Shape.isNull():
                obj.recompute()
            faces = [extrude._to_global(f, obj) for f in obj.Shape.Faces]
        except Exception as exc:
            warn("no profile for %s: %s" % (obj.Label, exc))
            continue
        if faces:
            found.append((obj, TextArea(faces)))
    return found


class ProfilePicker:
    """A press on a drag handle (an arrow in front of a region) drags the handle: it is no
    pick of the region behind it.

    clicks_through=True (Extrude): while the regions are offered, the sketches' own lines
    and faces let clicks through. The shaded regions here take the clicks, and an arrow
    behind a sketch (a cut going down into the part, with the sketch kept in view until OK)
    stays grabbable, as Fusion's arrows always are. Off for the other dialogs: Sweep and
    Loft pick sketch lines as paths and rails, so FreeCAD must still find them.

    on_curve (a thin extrude): the visible sketches' curves can be clicked too; a click
    within a few pixels of a curve calls on_curve(sketch, "EdgeN") instead of picking the
    area beside it. show_curves() draws the picked curves."""

    CURVE_PIXELS = 6  # a click this close to a sketch curve picks the curve

    def __init__(self, view, sketches, on_pick, occluder=None, clicks_through=False, on_curve=None):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.on_pick = on_pick
        self.on_curve = on_curve
        self.occluder = occluder  # () -> the part (global) that can hide regions
        self.regions = []  # (sketch, sub, face, material)
        self.curves = []  # (sketch, sub, [global points along the curve]) for on_curve
        self.selected = set()  # {(sketch name, sub)}
        self.dimmed = False  # picked profiles faded (a red cut preview is shown over them)
        self.face_materials = []  # materials of the highlighted body faces
        self.unpickable = []  # (sketch's root node, pick style) put in while offered
        self.last_click = 0.0  # time of the last click that picked a region
        self.paused = False  # a dialog's other selection box takes the clicks now
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        # drawn a hair in front of the part's faces: FreeCAD pushes those back with the
        # default offset (factor 1, units 1); the same push here made the shaded areas of
        # a sketch on a face fight the face for the same pixels (Luca: "Faces that are
        # sketched on have z-fighting")
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(-1.0)
        offset.units.setValue(-1.0)
        self.root.addChild(offset)
        self.face_root = coin.SoSeparator()  # picked body faces
        self.root.addChild(self.face_root)
        self.curve_root = coin.SoSeparator()  # picked (and hovered) sketch curves
        self.root.addChild(self.curve_root)
        self.hover_root = coin.SoSeparator()
        self.root.addChild(self.hover_root)
        self.hovered_curve = None
        from . import extrude

        for sketch in sketches:
            try:
                found = extrude.regions(sketch)
            except Exception as exc:
                warn("no profile for %s: %s" % (sketch.Label, exc))
                continue
            for sub, face in found:
                self.regions.append((sketch, sub, face, self._add_face(face, self.root)))
            if on_curve is not None and _visible(sketch):
                self._offer_curves(sketch)
                if not found and clicks_through:
                    self._let_clicks_through(sketch)  # its curves are picked here
            if found and clicks_through:
                self._let_clicks_through(sketch)
            texts = text_areas(sketch)  # a text is one more profile (its sub is "")
            for obj, area in texts:
                self.regions.append((obj, "", area, self._add_face(area, self.root)))
                if clicks_through:
                    self._let_clicks_through(obj)
        self.hovered = None
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]

    def _let_clicks_through(self, sketch):
        """The sketch's own drawing cannot be picked while the picker is on (a Coin pick
        style in the sketch's own scene nodes, taken out again by remove(); nothing about
        the sketch itself changes). Its lines are under RootNode; its shaded areas
        (FreeCAD 1.1's SoSketchFaces) under the separate Annotation node."""
        for attr in ("RootNode", "Annotation"):
            try:
                root = getattr(sketch.ViewObject, attr)
                if root is None:
                    continue
                style = self.coin.SoPickStyle()
                style.style = self.coin.SoPickStyle.UNPICKABLE
                root.insertChild(style, 0)
                self.unpickable.append((root, style))
            except Exception:
                pass  # no view of the sketch: nothing to click there anyway

    # -- sketch curves (thin extrude) ---------------------------------------------------
    def _offer_curves(self, sketch):
        from . import curves

        try:
            count = len(sketch.Shape.Edges)
        except Exception:
            return
        for i in range(1, count + 1):
            edge = curves.edge_of(sketch, "Edge%d" % i)
            if edge is None:
                continue
            try:
                points = edge.discretize(Deflection=0.05) if edge.Length > 0 else []
            except Exception:
                points = []
            if len(points) < 2:
                try:
                    points = edge.discretize(24)
                except Exception:
                    continue
            self.curves.append((sketch, "Edge%d" % i, points))

    def _screen(self, point):
        x, y = self.view.getPointOnViewport(App.Vector(point))
        return float(x), float(y)

    def curve_at(self, position):
        """(sketch, "EdgeN") of the curve within CURVE_PIXELS of the mouse, nearest first;
        None when there is none (or the part hides it)."""
        import math

        if not self.curves:
            return None
        px, py = float(position[0]), float(position[1])
        best = None
        for sketch, sub, points in self.curves:
            try:
                screen = [self._screen(p) for p in points]
            except Exception:
                continue
            for (ax, ay), (bx, by), a, b in zip(screen, screen[1:], points, points[1:]):
                dx, dy = bx - ax, by - ay
                length2 = dx * dx + dy * dy
                t = 0.0 if length2 < 1e-12 else ((px - ax) * dx + (py - ay) * dy) / length2
                t = max(0.0, min(1.0, t))
                d = math.hypot(px - (ax + dx * t), py - (ay + dy * t))
                if d <= self.CURVE_PIXELS and (best is None or d < best[0]):
                    best = (d, sketch, sub, a + (b - a) * t)
        if best is None:
            return None
        if self.occluder is not None:
            try:
                shape = self.occluder()
            except Exception:
                shape = None
            _start, direction = mouse_ray(self.view, position)
            if hidden_by(shape, best[3], direction):
                return None
        return best[1], best[2]

    def _line(self, parent, points, color, width):
        coin = self.coin
        sep = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.lineWidth = width
        sep.addChild(style)
        material = coin.SoBaseColor()
        material.rgb.setValue(*color)
        sep.addChild(material)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        sep.addChild(coords)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        sep.addChild(line)
        parent.addChild(sep)

    def show_curves(self, keys):
        """Draw the picked curves {(sketch name, "EdgeN")} in the picked blue."""
        self.curve_root.removeAllChildren()
        for sketch, sub, points in self.curves:
            if (sketch.Name, sub) in keys:
                self._line(self.curve_root, points, PICKED, 5)

    def _hover_curve(self, hit):
        if hit == self.hovered_curve:
            return
        self.hovered_curve = hit
        self.hover_root.removeAllChildren()
        if hit is None:
            return
        for sketch, sub, points in self.curves:
            if (sketch, sub) == hit:
                self._line(self.hover_root, points, FILL, 4)

    def _add_face(self, face, parent, color=FILL, transparency=IDLE_TRANSPARENCY):
        coin = self.coin
        points, triangles = face.tessellate(0.2)
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(color[0] * 0.4, color[1] * 0.4, color[2] * 0.4)
        material.transparency.setValue(transparency)
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
        parent.addChild(sep)
        return material

    # -- what is under the mouse ------------------------------------------------------
    def region_at(self, position, check_hidden=False):
        """(sketch, sub, face, material) under the mouse; the smallest region wins (a hole
        inside a plate). With check_hidden, a region behind the part is not returned."""
        best = None
        for region in self.regions:
            face = region[2]
            hit = ray_hit_t(self.view, position, face)
            if hit is None:
                continue
            point, _t = hit
            if inside(face, point) and (best is None or face.Area < best[0][2].Area):
                best = (region, point)
        if best is None:
            return None
        if check_hidden and self.occluder is not None:
            try:
                shape = self.occluder()
            except Exception:
                shape = None
            _start, direction = mouse_ray(self.view, position)
            if hidden_by(shape, best[1], direction):
                return None  # the part is in front of the region: the face gets the click
        return best[0]

    # -- looks --------------------------------------------------------------------------
    def _picked_transparency(self):
        return DIMMED_TRANSPARENCY if self.dimmed else PICKED_TRANSPARENCY

    def _paint(self, region, hovered=False):
        material = region[3]
        if (region[0].Name, region[1]) in self.selected:
            color, transparency = PICKED, self._picked_transparency()
        else:
            color = FILL
            transparency = HOVER_TRANSPARENCY if hovered else IDLE_TRANSPARENCY
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(color[0] * 0.4, color[1] * 0.4, color[2] * 0.4)
        material.transparency.setValue(transparency)

    def set_selected(self, keys):
        """Show these regions {(sketch name, sub)} as picked."""
        self.selected = set(keys)
        for region in self.regions:
            self._paint(region, region is self.hovered)

    def show_faces(self, faces):
        """Highlight picked body faces (global coordinates)."""
        self.face_root.removeAllChildren()
        self.face_materials = []
        for face in faces:
            try:
                self.face_materials.append(
                    self._add_face(face, self.face_root, PICKED, self._picked_transparency())
                )
            except Exception as exc:
                warn("could not highlight a face: %s" % exc)

    def dim_picked(self, dim):
        """Fade the picked profiles' blue (while the dialog shows a cut in red: the strong
        blue on the profile plane hid the red), or bring it back."""
        dim = bool(dim)
        if dim == self.dimmed:
            return
        self.dimmed = dim
        for region in self.regions:
            self._paint(region, region is self.hovered)
        for material in self.face_materials:
            try:
                material.transparency.setValue(self._picked_transparency())
            except Exception:
                pass

    # -- events -------------------------------------------------------------------------
    def _moved(self, info):
        try:
            if self.on_curve is not None and not self.paused:
                curve = self.curve_at(info["Position"])
                self._hover_curve(curve)
                if curve is not None:
                    info = None  # on a curve: no area lights up under it
            hit = None if (self.paused or info is None) else self.region_at(info["Position"])
            if hit is not self.hovered:
                previous, self.hovered = self.hovered, hit
                if previous is not None:
                    self._paint(previous)
                if hit is not None:
                    self._paint(hit, hovered=True)
        except Exception as exc:
            warn("profile hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN" or self.paused:
                return
            # (On the press: FreeCAD's selection takes the release and stops it there.)
            position = tuple(info["Position"])
            if handle_at(self.view, position):
                return  # a drag handle sits in front of the region: the press drags it
            if self.on_curve is not None:
                curve = self.curve_at(position)
                if curve is not None:
                    self.last_click = time.time()
                    self.on_curve(curve[0], curve[1])
                    return
            hit = self.region_at(position, check_hidden=True)
            if hit is not None:
                self.last_click = time.time()
                self.on_pick(hit[0], hit[1])
        except Exception as exc:
            warn("profile pick: %s" % exc)

    def clicked_region_recently(self, seconds=0.6):
        return time.time() - self.last_click < seconds

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
        for root, style in self.unpickable:
            try:
                index = root.findChild(style)
                if index >= 0:
                    root.removeChild(index)
            except Exception:
                pass  # the sketch was deleted with its scene
        self.unpickable = []
        self.regions = []


def _visible(sketch):
    try:
        view = sketch.ViewObject
        return bool(view.Visibility) if view is not None else bool(sketch.Visibility)
    except Exception:
        return False


# -- which sketches can be extruded ------------------------------------------------------------
def used_sketches(doc):
    """Names of sketches some extrude-like feature already uses as its profile."""
    used = set()
    for obj in doc.Objects:
        # Sections: the other profiles of FreeCAD's Loft (they were offered again as unused)
        for prop in ("Profile", "Profiles", "Sections", "Support"):
            if prop not in obj.PropertiesList:
                continue
            value = getattr(obj, prop)
            for linked in _linked_objects(value):
                if linked.isDerivedFrom("Sketcher::SketchObject") and obj is not linked:
                    used.add(linked.Name)
    return used


def _linked_objects(value):
    if value is None:
        return []
    if hasattr(value, "Name"):
        return [value]
    found = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if hasattr(item, "Name"):
                found.append(item)
            elif isinstance(item, (list, tuple)) and item and hasattr(item[0], "Name"):
                found.append(item[0])
    return found


def candidate_sketches(body, extra=()):
    """Sketches whose profiles are offered: the body's unused sketches, every visible
    sketch of the document, and `extra` (the sketches of the extrude being edited)."""
    doc = body.Document if body is not None else App.ActiveDocument
    if doc is None:
        return []
    used = used_sketches(doc)
    found, seen = [], set()

    def add(obj):
        if obj.Name not in seen:
            seen.add(obj.Name)
            found.append(obj)

    for obj in extra:
        add(obj)
    if body is not None:
        for obj in body.Group:
            if obj.isDerivedFrom("Sketcher::SketchObject") and obj.Name not in used:
                add(obj)
    for obj in doc.Objects:
        if not obj.isDerivedFrom("Sketcher::SketchObject"):
            continue
        try:
            visible = obj.ViewObject.Visibility if obj.ViewObject is not None else obj.Visibility
        except Exception:
            visible = getattr(obj, "Visibility", False)
        if visible:
            add(obj)
    return found


# -- faces picked in the 3D view ----------------------------------------------------------------
def same_face(a, b, tol=1e-6):
    """Geometric identity check that survives re-computation (same surface, size, position)."""
    if a.isSame(b):
        return True
    if a.Surface.TypeId != b.Surface.TypeId:
        return False
    if abs(a.Area - b.Area) > tol * max(1.0, a.Area):
        return False
    return (a.CenterOfMass - b.CenterOfMass).Length < 1e-5


def face_name_in(feature, face_global):
    """ "FaceN" of `feature`'s shape that is the same as the picked face, or None."""
    shape = feature.Shape
    face = face_global
    body = feature.getParentGeoFeatureGroup()
    if body is not None:
        face = face_global.copy()
        face.transformShape(body.getGlobalPlacement().inverse().toMatrix())
    for i, candidate in enumerate(shape.Faces, start=1):
        if same_face(face, candidate):
            return "Face%d" % i
    return None


def resolve(sel_obj, name):
    """(object, short element name) for a selection entry, through "Body.Pad.Face6" paths.
    A face picked on a Body is resolved to the Body's Tip."""
    obj, short = sel_obj, name
    if "." in name:
        path, short = name.rsplit(".", 1)
        inner = sel_obj.getSubObject(path + ".", retType=1)
        obj = inner if inner is not None else obj
    if (
        obj is not None
        and obj.TypeId == "PartDesign::Body"
        and short.startswith(("Face", "Edge", "Vertex"))
    ):
        obj = obj.Tip
    return obj, short


def picks():
    """[(object, short element name)] of the current selection ("" = the whole object)."""
    found = []
    for sel in Gui.Selection.getSelectionEx():
        for name in list(sel.SubElementNames) or [""]:
            obj, short = resolve(sel.Object, name)
            if obj is not None:
                found.append((obj, short))
    return found


def global_face(obj, short):
    """The face `short` of `obj` in global coordinates, or None."""
    from . import extrude

    try:
        face = obj.Shape.getElement(short)
    except Exception:
        return None
    return extrude._to_global(face, obj)
