# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create Sketch like Fusion: the origin planes appear, you click one of them or a flat
face of the part, and the sketch opens on it. No attachment pop-ups.

FreeCAD 1.1 draws its origin planes small, at a fixed size, so SciForge draws its own
see-through squares for XY, XZ and YZ (coloured and labelled by origin_look); they light
up under the mouse and a click is matched to them geometrically (nearest square along the
mouse ray).

If a plane or flat face is already selected, the sketch opens on it at once.
Esc / Cancel leaves without creating anything.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, taskui, ui_icon, warn
from .compat import QtCore, QtWidgets

PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
# role -> (normal, in-plane u, in-plane v) in body coordinates
PLANES = {
    "XY_Plane": (App.Vector(0, 0, 1), App.Vector(1, 0, 0), App.Vector(0, 1, 0)),
    "XZ_Plane": (App.Vector(0, 1, 0), App.Vector(1, 0, 0), App.Vector(0, 0, 1)),
    "YZ_Plane": (App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)),
}


def origin_planes(body):
    """{role: plane object} for the body's origin planes."""
    found = {}
    for feature in body.Origin.OriginFeatures:
        role = getattr(feature, "Role", "") or feature.Name
        for key in PLANES:
            if role.startswith(key):
                found[key] = feature
    return found


def _same_place(a, b, tol=1e-6):
    """True if two origin features lie at the same place in the design."""
    pa, pb = a.getGlobalPlacement(), b.getGlobalPlacement()
    return (pa.Base - pb.Base).Length <= tol and pa.Rotation.isSame(pb.Rotation, tol)


def local_box(body, shapes=None):
    """(xmin, xmax, ymin, ymax, zmin, zmax) of `shapes` (default: the body's) in the body's
    own axes (its shape is placed in its parent's frame)."""
    inverse = body.Placement.inverse()
    low = high = None
    for shape in shapes or [body.Shape]:
        b = shape.BoundBox
        for x in (b.XMin, b.XMax):
            for y in (b.YMin, b.YMax):
                for z in (b.ZMin, b.ZMax):
                    p = inverse.multVec(App.Vector(x, y, z))
                    if low is None:
                        low, high = App.Vector(p), App.Vector(p)
                    low = App.Vector(min(low.x, p.x), min(low.y, p.y), min(low.z, p.z))
                    high = App.Vector(max(high.x, p.x), max(high.y, p.y), max(high.z, p.z))
    if low is None:
        return (0.0,) * 6
    return (low.x, high.x, low.y, high.y, low.z, high.z)


def design_box(body):
    """local_box of every visible body of the design, solid or surface (the other bodies hide
    the squares too: after a Split Body the piece split off stands where the squares were
    free; a surface body stands in front of them), in
    `body`'s axes; the body's own box when the design has nothing else."""
    from . import bodies

    inverse = body.getGlobalPlacement().inverse()
    low = high = None
    for obj in body.Document.Objects:
        try:
            if obj.TypeId != "PartDesign::Body" or not obj.ViewObject.Visibility:
                continue
            shape = obj.Shape
            if shape.isNull() or not (shape.Solids or shape.Faces):
                continue  # (a surface body hides the squares too)
            b = bodies.global_shape(obj).BoundBox
        except Exception:
            continue
        for x in (b.XMin, b.XMax):
            for y in (b.YMin, b.YMax):
                for z in (b.ZMin, b.ZMax):
                    p = inverse.multVec(App.Vector(x, y, z))
                    if low is None:
                        low, high = App.Vector(p), App.Vector(p)
                    low = App.Vector(min(low.x, p.x), min(low.y, p.y), min(low.z, p.z))
                    high = App.Vector(max(high.x, p.x), max(high.y, p.y), max(high.z, p.z))
    if low is None:
        return local_box(body)
    return (low.x, high.x, low.y, high.y, low.z, high.z)


class PlanePicker:
    """The three origin squares; on_pick(plane object) when one is clicked. Each has the
    colour of the axis it faces (XY blue, XZ green, YZ red), a label, and lights up under
    the mouse (origin_look). Small like Fusion's: in the + quarter of its plane, about
    origin_look.SCREEN_SIDE pixels whatever the zoom (redrawn when the zoom changes), and
    they stay there like Fusion's, whatever the part (origin_look.square_corner): a square
    a part hides is picked in the browser. LIVE lists the pickers on show (tests aim at
    their squares)."""

    LIVE = []

    def __init__(self, view, body, on_pick, on_face=None):
        from pivy import coin

        from . import origin_look

        self.view = view
        self.doc_name = body.Document.Name
        self.gl = taskui.view_widget()  # its window: gone when the view or design closes
        self.on_pick = on_pick
        self.on_face = on_face  # (feature, "FaceN"): a flat face behind a clicked edge
        self.placement = body.getGlobalPlacement()
        self.objects = origin_planes(body)
        self.center = None  # the part's centre: the labels go to the corners away from it
        self.box = design_box(body)  # the design's box in the body's axes (pick tolerances)
        # no solid in the whole design (design_box falls back on the body's own box then)
        empty = (body.Shape.isNull() or not body.Shape.Solids) and self.box == local_box(body)
        if empty:
            self.box = None
        else:
            x0, x1, y0, y1, z0, z1 = self.box
            self.center = self.placement.multVec(
                App.Vector((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
            )
        # what a pick "on the plane" is measured against (the part, not the small squares)
        self.slack_half = origin_look.part_size(self.box) / 2.0
        if empty:  # nothing to look at yet: the origin in view, like a new Fusion design
            view.viewIsometric()
            _show_round_origin(view, self.placement, origin_look.EMPTY_SIZE)
        self.size = self._screen_side()
        # drawn over the part, in the layer the drag arrows use (Luca 2026-10-19: the squares
        # z-fought with faces lying in their planes): never pickable, clicks go by where
        # the squares are on the screen (plane_at), the part under the mouse first
        from . import handle_look

        self.root = handle_look.top_root(coin)
        self.squares = coin.SoSeparator()
        self.root.addChild(self.squares)
        self.materials = {}
        self.looks = {}
        for role in self.objects:
            self.materials[role] = self._square(coin, role)
        self.hovered = None
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        PlanePicker.LIVE.append(self)
        # Fusion: an origin plane can also be picked in the browser (a part may hide its
        # square, the squares do not move)
        picker = self

        class _BrowserPick:
            def addSelection(self, doc, obj, sub, pnt):
                if not sub:
                    QtCore.QTimer.singleShot(0, lambda: picker._browser_pick(doc, obj))

        self.browser_pick = _BrowserPick()
        try:
            Gui.Selection.addObserver(self.browser_pick)
        except Exception as exc:
            self.browser_pick = None
            warn("origin planes: %s" % exc)
        self._zoom = None
        try:
            from .compat import QtCore

            self._zoom = QtCore.QTimer()
            self._zoom.setInterval(250)
            self._zoom.timeout.connect(self._follow_zoom)
            self._zoom.start()
        except Exception as exc:
            warn("origin planes: %s" % exc)

    def _frame(self, role):
        normal, u, v = PLANES[role]
        rot = self.placement.Rotation
        return self.placement.Base, rot.multVec(normal), rot.multVec(u), rot.multVec(v)

    def half_of(self, role):
        """Half the side of the square of `role` (mm)."""
        return self.size / 2.0

    def middle_of(self, role):
        """(u, v) of the middle of the square of `role` in its plane (mm from the origin)."""
        from . import origin_look

        u0, v0 = origin_look.square_corner(role, self.size)
        h = self.half_of(role)
        return u0 + h, v0 + h

    def spot(self, role, a, b):
        """The point of the square of `role` at (a, b) halves of its side from its middle
        along u and v (-1 .. 1 reach its edges)."""
        base, _normal, u, v = self._frame(role)
        mu, mv = self.middle_of(role)
        h = self.half_of(role)
        return base + u * (mu + a * h) + v * (mv + b * h)

    def on_square(self, role, local):
        """True if `local` (a point in the plane of `role`, less the origin) is on its square."""
        _base, _normal, u, v = self._frame(role)
        mu, mv = self.middle_of(role)
        h = self.half_of(role)
        return abs(local.dot(u) - mu) <= h and abs(local.dot(v) - mv) <= h

    def _square(self, coin, role):
        from . import origin_look

        signs = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        corners = [self.spot(role, a, b) for a, b in signs]
        inset = origin_look.LABEL_INSET
        spots = [self.spot(role, a * inset, b * inset) for a, b in signs]
        corner = origin_look.label_corner(corners, self.center)
        look = origin_look.SquareLook(coin, self.squares, role, corners, spots[corner])
        self.looks[role] = look
        return look.material

    def resize(self, side):
        """Draw the squares `side` mm wide (the zoom changed)."""
        from pivy import coin

        lit = self.plane_lit()
        self.size = float(side)
        self.squares.removeAllChildren()
        self.hovered = None
        self.looks = {}
        self.materials = {role: self._square(coin, role) for role in self.objects}
        if lit is not None:
            self.light(lit)

    def plane_lit(self):
        """The role of the square lit under the mouse, or None."""
        for role, material in self.materials.items():
            if material is self.hovered:
                return role
        return None

    def _screen_side(self):
        """origin_look.SCREEN_SIDE pixels in mm, at the origin, at the present zoom."""
        from . import origin_look

        try:
            base = self.placement.Base
            x, y = self.view.getPointOnViewport(base)
            a = self.view.getPoint(int(x), int(y))
            b = self.view.getPoint(int(x) + 100, int(y))
            per_pixel = (b - a).Length / 100.0
            if per_pixel > 1e-9:
                return origin_look.SCREEN_SIDE * per_pixel
        except Exception:
            pass
        return origin_look.square_size(0.0, True)

    def _camera_key(self):
        """Where the camera is and how it looks (changes with every zoom, pan or turn)."""
        try:
            cam = self.view.getCameraNode()
            parts = [cam.position.getValue().getValue(), cam.orientation.getValue().getValue()]
            for name in ("height", "heightAngle"):
                field = getattr(cam, name, None)
                if field is not None:
                    parts.append(round(float(field.getValue()), 9))
            parts.append(tuple(self.view.getSize()))
            return repr(parts)
        except Exception:
            return None

    def _follow_zoom(self):
        """Keep the squares their size on the screen when the view zooms (a timer)."""
        try:
            if not self.callbacks or not self._alive():
                return
            camera = self._camera_key()
            if camera is not None and camera == getattr(self, "_camera", None):
                return  # the view has not moved
            self._camera = camera
            side = self._screen_side()
            if abs(side - self.size) > 0.08 * self.size:
                self.resize(side)
        except Exception as exc:
            warn("origin planes: %s" % exc)

    def light(self, role):
        """Light the square of `role` (None: none) and dim the one lit before."""
        material = self.materials.get(role)
        if material is self.hovered:
            return
        for look in self.looks.values():
            if look.material is self.hovered or look.material is material:
                look.paint(look.material is material)
        self.hovered = material

    def plane_at(self, position):
        """Role of the nearest origin square under the mouse, or None."""
        found = self._square_at(position)
        return found[0] if found else None

    def _square_at(self, position):
        """(role, distance along the mouse ray) of the nearest origin square, or None."""
        from .profile_pick import ray_plane

        best = None
        for role in self.objects:
            base, normal, u, v = self._frame(role)
            hit = ray_plane(self.view, position, base, normal)
            if hit is None:
                continue
            point, t = hit
            if self.on_square(role, point - base):
                if best is None or t < best[1]:
                    best = (role, t)
        return best

    def _geometry_at(self, position):
        """True if the part (not the empty background) is under the mouse, or a construction
        plane in front of the origin squares. A face of the part takes the click also where
        a see-through square is drawn in front of it: on a wide flat part the XZ square stood
        well above it and took every click on the front half of its top face
        (modeling2_bodies, patterns_circ). The squares move beside a part that would hide
        them (origin_look.square_corner), where they can be clicked."""
        info = self.view.getObjectInfo(tuple(position))
        if not (info and info.get("Object")):
            return False
        component = str(info.get("Component", ""))
        if component.startswith("Face"):
            return True
        if component.startswith(("Edge", "Vertex")):
            # An edge or corner of the part hides the squares, as a face does: a click on
            # the edge of a 2 mm rim (lying on the XZ square) took the square and the
            # sketch landed on XZ (the Pi 5 case test). A sketch's curve or a construction
            # line only hides a square it lies in front of (a curve drawn on XY must not
            # keep XY from being clicked).
            try:
                obj = Gui.ActiveDocument.Document.getObject(str(info.get("Object")))
            except Exception:
                obj = None
            if obj is not None and not _curve_object(obj):
                # but only an edge on the square (the rim) or one with the part's face under
                # the mouse in front of the square: FreeCAD picks an edge up to a few pixels
                # away, and a loft's edge passing near the mouse, the plane under it, kept
                # XZ from being clicked (sweep_loft_loft, CI #141)
                return self._on_square(position, info) or self._face_in_front(position)
            return self._in_front(position, info)
        # A construction plane (an Offset Plane for a loft's next profile) is picked as a
        # whole object, not a face: the origin square behind it took the click and the
        # sketch landed on XZ (found by the sweep / loft QA, sweep_loft_qa_loft).
        try:
            doc = Gui.ActiveDocument.Document
            obj = doc.getObject(str(info.get("Object")))
            if obj is None or obj.TypeId not in ("PartDesign::Plane", "App::Plane"):
                return False
            from .profile_pick import mouse_ray

            start, direction = mouse_ray(self.view, position)
            spot = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
            square = self._square_at(position)
            return square is None or (spot - start).dot(direction) <= square[1] + 1e-6
        except Exception:
            return False

    def _on_square(self, position, info, tolerance=1e-3):
        """True if the picked point of `info` lies in the plane of the origin square under
        the mouse (or there is no square there). (The point FreeCAD gives for an edge is the
        edge's point nearest the mouse ray, not where the ray meets the square.)"""
        try:
            square = self._square_at(position)
            if square is None:
                return True
            base, normal, _u, _v = self._frame(square[0])
            spot = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
            return abs((spot - base).dot(normal)) <= tolerance + 0.02 * self.slack_half
        except Exception:
            return True

    def _face_in_front(self, position):
        """True if a face of the part is under the mouse before the origin square there."""
        try:
            from .profile_pick import mouse_ray

            square = self._square_at(position)
            infos = self.view.getObjectsInfo(tuple(position)) or []
            start, direction = mouse_ray(self.view, position)
            for info in infos:
                if not str(info.get("Component", "")).startswith("Face"):
                    continue
                if square is None:
                    return True
                spot = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
                if (spot - start).dot(direction) < square[1] + 1e-3:
                    return True
            return False
        except Exception:
            return True

    def _not_behind(self, position, info, slack=1e-3):
        """True if the picked point of `info` lies before the origin square under the mouse
        or on its plane, or there is no square there. "On its plane" allows 2 % of the
        part's size (origin_look.part_size) measured square to the plane (not along the line of sight): a
        curved face touching the plane (a tube's side on YZ) is drawn as flat facets a
        little inside the true surface, and seen at a grazing angle that is far along the
        line of sight."""
        try:
            from .profile_pick import mouse_ray

            square = self._square_at(position)
            if square is None:
                return True
            role, depth = square
            spot = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
            base, normal, _u, _v = self._frame(role)
            if abs((spot - base).dot(normal)) <= slack + 0.02 * self.slack_half:
                return True  # on the square's plane: the part keeps it
            start, direction = mouse_ray(self.view, position)
            return (spot - start).dot(direction) <= depth + slack + 1e-6 * abs(depth)
        except Exception:
            return True
        except Exception:
            return True

    def _in_front(self, position, info, slack=1e-3):
        """True if the picked point of `info` lies before the origin square under the mouse
        (or there is no square there)."""
        try:
            from .profile_pick import mouse_ray

            square = self._square_at(position)
            if square is None:
                return True
            start, direction = mouse_ray(self.view, position)
            spot = App.Vector(float(info["x"]), float(info["y"]), float(info["z"]))
            return (spot - start).dot(direction) < square[1] - slack
        except Exception:
            return True

    def flat_face_at(self, position):
        """(feature, "FaceN") of the frontmost face under the mouse if it is flat, else None.
        Create Sketch only takes planes and flat faces (Fusion), so a click on an edge goes
        to the face the mouse is over there, never to the edge."""
        try:
            infos = self.view.getObjectsInfo(tuple(position)) or []
        except Exception:
            return None
        doc = Gui.ActiveDocument.Document
        for info in infos:
            component = str(info.get("Component", ""))
            if not component.startswith("Face"):
                continue
            obj = doc.getObject(str(info.get("Object")))
            if obj is None:
                return None
            # the frontmost face decides: a curved one gives None
            return sketch_target([_Pick(obj, component)])
        return None

    def _moved(self, info):
        try:
            # the part under the mouse wins, also where a square is drawn over it (Luca
            # 2026-10-20: a face clicked through a square must be the face, like Fusion)
            role = None
            if not self._geometry_at(info["Position"]):
                role = self.plane_at(info["Position"])
            self.light(role)
        except Exception as exc:
            warn("plane hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            if self._geometry_at(info["Position"]):
                under = self.view.getObjectInfo(tuple(info["Position"])) or {}
                if str(under.get("Component", "")).startswith(("Edge", "Vertex")):
                    face = self.flat_face_at(info["Position"])
                    if face is not None and self.on_face is not None:
                        self.on_face(face)
                return  # a face of the part: the selection observer takes it
            # beside the part a square takes the click (drawn on top, never picked itself)
            role = self.plane_at(info["Position"])
            if role is not None:
                plane = self.objects[role]
                QtCore.QTimer.singleShot(0, lambda: self._take_square(plane))
        except Exception as exc:
            warn("plane pick: %s" % exc)

    def _take_square(self, plane):
        """A square was clicked: its plane, not the face behind it that FreeCAD selected
        with the same click."""
        try:
            if not self.callbacks or not self._alive():
                return
            Gui.Selection.clearSelection()
            self.on_pick(plane)
        except Exception as exc:
            warn("plane pick: %s" % exc)

    def _alive(self):
        """False once the design or its 3D view has closed (the view must not be touched
        then: FreeCAD crashes); the squares are dropped then."""
        try:
            import shiboken6

            alive = self.doc_name in App.listDocuments() and (
                self.gl is None or shiboken6.isValid(self.gl)
            )
        except Exception:
            alive = False
        if not alive:
            self._drop()
        return alive

    def _drop(self):
        """Forget the squares without touching the (closed) view."""
        if self in PlanePicker.LIVE:
            PlanePicker.LIVE.remove(self)
        if getattr(self, "_zoom", None) is not None:
            try:
                self._zoom.stop()
            except Exception:
                pass
            self._zoom = None
        if getattr(self, "browser_pick", None) is not None:
            try:
                Gui.Selection.removeObserver(self.browser_pick)
            except Exception:
                pass
            self.browser_pick = None
        self.callbacks = []

    def _browser_pick(self, doc_name, obj_name):
        """An origin plane selected in the browser: as if its square were clicked. The
        browser shows the component's origin; the squares are the body's, at the same
        place (a plane there counts as the square's)."""
        try:
            if not self.callbacks or not self._alive():
                return  # gone meanwhile (the command took the selection itself)
            obj = App.getDocument(doc_name).getObject(obj_name)
            role = getattr(obj, "Role", "") or ""
            for key, plane in self.objects.items():
                if plane is obj:
                    self.on_pick(plane)
                    return
            for key, plane in self.objects.items():
                if role.startswith(key) and _same_place(obj, plane):
                    self.on_pick(plane)
                    return
        except Exception as exc:
            warn("plane pick: %s" % exc)

    def own_selection(self):
        """The command takes what is selected itself (a plane picked in the browser too):
        the squares leave the browser to it, or the plane was taken twice, which drops it
        again (Boundary Fill's Tools, Luca 2026-10-20)."""
        if getattr(self, "browser_pick", None) is not None:
            try:
                Gui.Selection.removeObserver(self.browser_pick)
            except Exception:
                pass
            self.browser_pick = None

    def remove(self):
        if not self._alive():
            return  # the view has closed: _alive dropped the squares without touching it
        if self in PlanePicker.LIVE:
            PlanePicker.LIVE.remove(self)
        if getattr(self, "browser_pick", None) is not None:
            try:
                Gui.Selection.removeObserver(self.browser_pick)
            except Exception:
                pass
            self.browser_pick = None
        if getattr(self, "_zoom", None) is not None:
            try:
                self._zoom.stop()
            except Exception:
                pass
            self._zoom = None
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


def _show_round_origin(view, placement, size):
    """Frame the view (as it looks now) on the room round the origin a new design starts
    with: the space the old `size` mm squares centred on the origin filled (the zoom a new
    design always had; only the squares are small now). An invisible cube of that size is
    fitted and taken away again."""
    try:
        from pivy import coin

        temp = coin.SoSeparator()
        style = coin.SoDrawStyle()
        style.style = coin.SoDrawStyle.INVISIBLE
        move = coin.SoTransform()
        base = placement.Base
        move.translation.setValue(base.x, base.y, base.z)
        cube = coin.SoCube()
        for field in (cube.width, cube.height, cube.depth):
            field.setValue(float(size))
        for node in (style, move, cube):
            temp.addChild(node)
        root = view.getSceneGraph()
        root.addChild(temp)
        try:
            view.fitAll()
        finally:
            root.removeChild(temp)
    except Exception as exc:
        warn("origin planes: the view was not set: %s" % exc)


def _curve_object(obj):
    """Sketches and construction lines / points: they lie on planes, they are not the part."""
    type_id = getattr(obj, "TypeId", "")
    return (
        type_id.startswith("Sketcher::")
        or type_id in ("PartDesign::Line", "PartDesign::Point", "App::Line", "App::Point")
        or obj.isDerivedFrom("Part::Part2DObject")
    )


class _Pick:
    """A selection entry made by hand (sketch_target reads Object and SubElementNames)."""

    def __init__(self, obj, name):
        self.Object = obj
        self.SubElementNames = [name]


def _resolve(sel_obj, name):
    """(object, short element name) for a selection entry, through "Body.Pad.Face6" paths."""
    obj, short = sel_obj, name
    if "." in name:
        path, short = name.rsplit(".", 1)
        inner = sel_obj.getSubObject(path + ".", retType=1)
        obj = inner if inner is not None else obj
    if obj is not None and obj.TypeId == "PartDesign::Body" and short.startswith("Face"):
        obj = obj.Tip
    return obj, short


def sketch_target(selection=None):
    """What a sketch can be put on from the selection: (plane, "") or (feature, "FaceN")
    for a flat face. None if nothing suitable is selected."""
    if selection is None:
        selection = Gui.Selection.getSelectionEx()
    for sel in selection:
        names = list(sel.SubElementNames) or [""]
        for name in names:
            obj, short = _resolve(sel.Object, name)
            if obj is None:
                continue
            if obj.TypeId in PLANE_TYPES:
                return (obj, "")
            if short.startswith("Face"):
                try:
                    face = obj.Shape.getElement(short)
                except Exception:
                    continue
                if face.Surface.TypeId == "Part::GeomPlane":
                    return (obj, short)
    return None


def create_sketch(body, target):
    """New sketch in `body` attached flat to `target` = (plane or feature, "" or "FaceN").

    A face or plane of another body puts the sketch in that body and makes it active, as
    in Fusion, where Extrude then joins the body that was clicked. (In `body` the sketch
    would reach out of its body, and the extrude would join the wrong one.)"""
    from . import components, sketch_auto_project, timeline_ops

    owner = timeline_ops.body_of(target[0])
    # A face of a surface body (SURFACE tools, surface.py) hosts the sketch but not its
    # solid features: the sketch stays in `body`, attached across to the face.
    if owner is not None and owner is not body and not _surface_body(owner):
        body = owner
        try:
            components.activate_body(body)  # and its component
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
    if target[0].TypeId in PLANE_TYPES and not target[1]:
        # A component's own origin plane (clicked in the browser) lies where the body's
        # plane of the same role lies: the sketch hangs on the body's, inside the body.
        if components.is_component(components.origin_owner(target[0])):
            target = (components.same_role_plane(body, target[0]), "")
    point = _face_point(target)
    shown = _earliest(target, point, same_outline=True)
    target = _earliest(target, point)
    doc = body.Document
    doc.openTransaction("Create Sketch")
    try:
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [target]
        sketch.MapMode = "FlatFace"
        doc.recompute()
        if sketch_auto_project.enabled():
            sketch_auto_project.auto_project(sketch, shown, at=point)
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return sketch


def _surface_body(body):
    try:
        from . import surface

        return surface.is_surface_body(body)
    except Exception:
        return False


def _earliest(target, point=None, same_outline=False):
    """A flat face clicked on the part belongs to the step that made it, not to the last
    step that touched the part: a sketch on the top of a block with a hole drilled in it, or
    with a fillet round it, hangs on the block, so suppressing or deleting the hole or the
    fillet leaves the sketch (and what is built on it) alone, as in Fusion (found by the
    hole QA). Only the reference goes back: while the sketch is open the design is drawn as
    it is now (show_design_at), and what is made from the sketch builds on the body's newest
    step. same_outline: the earliest step whose face has the same outline, the face Auto
    project shows (a face a later Draft or fillet reshaped is projected as it is now, Luca,
    2026-10-23; sketch_auto_project.follow keeps it so)."""
    obj, name = target
    if point is None:
        point = _face_point(target)
    if not name.startswith("Face") or point is None:
        return target
    try:
        from . import hole

        return hole.earliest_face(obj, name, point, same_outline=same_outline)
    except Exception:
        return target


def _face_point(target):
    """A point of the clicked flat face (body coordinates), or None."""
    obj, name = target
    if not name.startswith("Face"):
        return None
    try:
        face = obj.Shape.getElement(name)
        if face.Surface.TypeId != "Part::GeomPlane":
            return None
        return _point_on(face)
    except Exception:
        return None


def _point_on(face):
    """A point that lies on the face (its centre can be in a hole of it)."""
    centre = face.CenterOfMass
    if face.isInside(centre, 1e-6, True):
        return centre
    u0, u1, v0, v1 = face.ParameterRange
    for i in range(1, 8):
        for j in range(1, 8):
            point = face.valueAt(u0 + (u1 - u0) * i / 8.0, v0 + (v1 - v0) * j / 8.0)
            if face.isInside(point, 1e-6, True):
                return point
    return None


def open_sketch(sketch):
    Gui.Selection.clearSelection()
    _no_support_shown(sketch)
    Gui.ActiveDocument.setEdit(sketch.Name)
    show_design_at(sketch)  # (again from sketch_mode for sketches opened elsewhere)
    log("sketch %s opened" % sketch.Label)


def _no_support_shown(sketch):
    """FreeCAD shows the step a sketch is attached to while it is open ("Show support"), and
    a PartDesign body shows one step at a time: a sketch on a face an early step made
    (_earliest) showed the part as it was before every later edit (Luca: "sketching on an
    edited object will revert it to a previous state"). Fusion never shows another state
    of the design than the one at the sketch's place (show_design_at)."""
    try:
        vp = sketch.ViewObject
        if vp is not None and getattr(vp, "ShowSupport", False):
            vp.ShowSupport = False
    except Exception as exc:
        warn("sketch: %s" % exc)


def design_step(sketch):
    """(body, step): the sketch's body and the step whose solid it shows while the sketch is
    open: the design as it is at the sketch's place in the timeline (timeline_core.
    shown_while_sketching). step None: nothing solid there yet. body None: not in a body, or
    its Tip is no solid step (FreeCAD's own "Set tip" on a sketch): left as it is drawn."""
    from . import timeline_core, timeline_ops

    body = sketch.getParentGeoFeatureGroup()
    if body is None or body.TypeId != "PartDesign::Body":
        return None, None
    if body.Tip is not None and "BaseFeature" not in body.Tip.PropertiesList:
        return None, None
    users = {o.Name for o in sketch.InListRecursive}
    try:
        tl = timeline_ops.timeline(sketch.Document, deps=False)
        index = {item.name: item.index for item in tl.items}
    except Exception:
        index = {}
    chain, seen = [], set()
    step = body.Tip
    while step is not None and step.Name not in seen and "BaseFeature" in step.PropertiesList:
        if step.getParentGeoFeatureGroup() is not body:
            break  # a copied body starts from a step outside it
        seen.add(step.Name)
        chain.append((step.Name, index.get(step.Name), step.Name in users))
        step = step.BaseFeature
    name = timeline_core.shown_while_sketching(chain, index.get(sketch.Name))
    return body, (sketch.Document.getObject(name) if name else None)


def show_design_at(sketch):
    """While a sketch is open its body shows the design as it is at the sketch's place in
    the timeline, as Fusion does: a new sketch shows every edit made so far (also when it
    hangs on a face an earlier step made), a sketch edited from the timeline the steps
    before it (FreeCAD already hides the steps that use the sketch). Done through the
    sketch's TempoVis, so Finish Sketch puts every step back as it was shown before."""
    try:
        vp = sketch.ViewObject
        tv = getattr(vp, "TempoVis", None) if vp is not None else None
        if tv is None:
            return  # FreeCAD changed nothing either (its Show module is missing)
        body, step = design_step(sketch)
        if body is None:
            return
        solids = [
            o
            for o in body.Group
            if o.isDerivedFrom("PartDesign::Feature") and o.ViewObject is not None
        ]
        if step is not None and step.ViewObject is not None and not step.ViewObject.Visibility:
            tv.show([step])  # PartDesign hides the step shown before (TempoVis notes it)
        others = [o for o in solids if o is not step and o.ViewObject.Visibility]
        if others:
            tv.hide(others)
    except Exception as exc:
        warn("sketch: could not show the design at the sketch: %s" % exc)


def edit_sketch(sketch):
    """Fusion: double-click a sketch in the browser or timeline to edit it. Its body is
    made active first (a sketch of another body would otherwise open in the wrong one)."""
    body = sketch.getParentGeoFeatureGroup()
    if body is not None and body.TypeId == "PartDesign::Body":
        try:
            from . import components

            components.activate_body(body)  # and its component
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
    open_sketch(sketch)


# Timeline / browser double-click (taskui.edit_object).
EDITORS = {"Sketcher::SketchObject": edit_sketch}


class _EscFilter(QtCore.QObject):
    """Esc on the 3D view cancels Create Sketch while it waits (Fusion does)."""

    def __init__(self, on_escape):
        super().__init__()
        self.on_escape = on_escape

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
                self.on_escape()
                return True
        except Exception as exc:
            warn("Create Sketch Esc: %s" % exc)
        return False


class SketchPicker:
    """The waiting state of Create Sketch (a task dialog with only Cancel). `then(sketch)`
    runs once the sketch is open (SOLID > CREATE > Text opens the Text dialog there)."""

    def __init__(self, body, then=None, title="Create Sketch"):
        self.body = body
        self.then = then
        self.doc = body.Document
        self._closed = False
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(title)
        self.form.setWindowIcon(ui_icon("sketch_create"))
        layout = QtWidgets.QVBoxLayout(self.form)
        label = QtWidgets.QLabel("Click a plane or a flat face to sketch on.")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.planes = None
        try:
            self.planes = PlanePicker(
                Gui.ActiveDocument.ActiveView,
                body,
                lambda plane: QtCore.QTimer.singleShot(0, lambda: self._picked((plane, ""))),
                on_face=lambda face: QtCore.QTimer.singleShot(0, lambda: self._picked(face)),
            )
        except Exception as exc:
            warn("origin planes unavailable: %s" % exc)
        self.observer = None
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        self.esc = _EscFilter(lambda: QtCore.QTimer.singleShot(0, self.reject))
        self.view_widget = None
        try:
            from . import sketch_mode

            self.view_widget = sketch_mode.view_widget()  # where the keyboard goes
            if self.view_widget is not None:
                self.view_widget.installEventFilter(self.esc)
        except Exception as exc:
            warn("Create Sketch: Esc unavailable: %s" % exc)
        taskui.set_current(self)

    def _selection_changed(self):
        if self._closed:
            return
        target = sketch_target()
        if target is not None:
            self._picked(target)
        elif Gui.Selection.getSelectionEx():
            # Fusion only offers flat faces and planes; a curved face or an edge is not
            # taken (and does not stay selected), with the reason next to the mouse.
            Gui.Selection.clearSelection()
            commands.tell("A sketch goes on a flat face or a plane: click one of those.")

    def _picked(self, target):
        if self._closed:
            return
        self._cleanup()
        Gui.Control.closeDialog()
        Gui.Selection.clearSelection()  # an edge clicked on the way to its face stays out
        QtCore.QTimer.singleShot(0, lambda: self._create(target))

    def _create(self, target):
        try:
            sketch = create_sketch(self.body, target)
            open_sketch(sketch)
            _then(self.then, sketch)
        except Exception as exc:
            warn("Create Sketch failed: %s" % exc)

    def _cleanup(self):
        self._closed = True
        if self.view_widget is not None:
            try:
                self.view_widget.removeEventFilter(self.esc)
            except Exception:
                pass
            self.view_widget = None
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.planes is not None:
            self.planes.remove()
            self.planes = None

    # -- task dialog API ------------------------------------------------------
    def getStandardButtons(self):
        buttons = QtWidgets.QDialogButtonBox.Cancel
        return getattr(buttons, "value", buttons)

    def reject(self):
        if self._closed:
            return True
        self._cleanup()
        Gui.Control.closeDialog()
        log("Create Sketch cancelled")
        return True

    def accept(self):
        return self.reject()

    def finish(self):
        self.reject()


def _then(then, sketch):
    if then is None:
        return
    try:
        then(sketch)
    except Exception as exc:
        warn("after Create Sketch: %s" % exc)


def start(then=None, title="Create Sketch"):
    """Create Sketch: on the selected plane/face at once, else let the user click one.
    `then(sketch)` runs once the sketch is open."""
    body = commands.ensure_body()
    if body is None:
        warn("Create Sketch: could not create a body")
        return None
    target = sketch_target()
    if target is not None:
        sketch = create_sketch(body, target)
        open_sketch(sketch)
        _then(then, sketch)
        return sketch
    picker = SketchPicker(body, then, title)
    Gui.Control.showDialog(picker)
    log("create sketch: waiting for a plane or face")
    return picker
