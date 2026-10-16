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
    """local_box of every visible body of the design (the other bodies hide the squares
    too: after a Split Body the piece split off stands where the squares were free), in
    `body`'s axes; the body's own box when the design has nothing else."""
    from . import bodies

    inverse = body.getGlobalPlacement().inverse()
    low = high = None
    for obj in body.Document.Objects:
        try:
            if obj.TypeId != "PartDesign::Body" or not obj.ViewObject.Visibility:
                continue
            shape = obj.Shape
            if shape.isNull() or not shape.Solids:
                continue
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
    the mouse (origin_look). LIVE lists the pickers on show (tests aim at their squares)."""

    LIVE = []

    def __init__(self, view, body, on_pick, on_face=None):
        from pivy import coin

        from . import origin_look

        self.view = view
        self.on_pick = on_pick
        self.on_face = on_face  # (feature, "FaceN"): a flat face behind a clicked edge
        self.placement = body.getGlobalPlacement()
        self.objects = origin_planes(body)
        empty = body.Shape.isNull() or not body.Shape.Solids
        self.center = None  # the part's centre: the labels go to the corners away from it
        if empty:
            self.sizes = dict.fromkeys(("XY", "XZ", "YZ"), origin_look.square_size(0.0, True))
        else:
            box = body.Shape.BoundBox
            self.sizes = origin_look.square_sizes_for(design_box(body))
            # the shape is in the body's parent's frame (a component): to the design's
            self.center = self.placement.multVec(body.Placement.inverse().multVec(box.Center))
        self.size = max(self.sizes.values())  # the largest (each square has its own)
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.root.addChild(coin.SoPolygonOffset())
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
        if empty:  # nothing to look at yet: frame the planes, like a new Fusion design
            view.viewIsometric()
            view.fitAll()

    def _frame(self, role):
        normal, u, v = PLANES[role]
        rot = self.placement.Rotation
        return self.placement.Base, rot.multVec(normal), rot.multVec(u), rot.multVec(v)

    def half_of(self, role):
        """Half the side of the square of `role` (mm)."""
        from . import origin_look

        return self.sizes.get(origin_look.plane_key(role), self.size) / 2.0

    def _square(self, coin, role):
        from . import origin_look

        base, _normal, u, v = self._frame(role)
        h = self.half_of(role)
        signs = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        corners = [base + u * a * h + v * b * h for a, b in signs]
        inset = origin_look.LABEL_INSET
        spots = [base + u * a * h * inset + v * b * h * inset for a, b in signs]
        corner = origin_look.label_corner(corners, self.center)
        look = origin_look.SquareLook(coin, self.squares, role, corners, spots[corner])
        self.looks[role] = look
        return look.material

    def resize(self, sizes):
        """Draw the squares {"XY": side, ...} mm wide (primitives_ui sizes them from the
        whole design)."""
        from pivy import coin

        self.sizes = dict(sizes)
        self.size = max(self.sizes.values())
        self.squares.removeAllChildren()
        self.hovered = None
        self.looks = {}
        self.materials = {role: self._square(coin, role) for role in self.objects}

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
            local = point - base
            h = self.half_of(role)
            if abs(local.dot(u)) <= h and abs(local.dot(v)) <= h:
                if best is None or t < best[1]:
                    best = (role, t)
        return best

    def _geometry_at(self, position):
        """True if the part (not the empty background) is under the mouse and not behind
        the origin square there, or a construction plane in front of the origin squares.
        A square drawn in front of the part takes the click where it is drawn (the squares
        are 0.6 x the part: where one stands up from the part, e.g. the XZ square above a
        thin plate's front edge, the face behind it took every click and the plane could
        not be picked at all); a face the square lies in keeps it (a tie is the part's)."""
        info = self.view.getObjectInfo(tuple(position))
        if not (info and info.get("Object")):
            return False
        component = str(info.get("Component", ""))
        if component.startswith("Face"):
            return self._not_behind(position, info)
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
            return abs((spot - base).dot(normal)) <= tolerance + 0.02 * self.half_of(square[0])
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
        square's half size measured square to the plane (not along the line of sight): a
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
            if abs((spot - base).dot(normal)) <= slack + 0.02 * self.half_of(role):
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
            role = self.plane_at(info["Position"])
            if role is not None:
                self.on_pick(self.objects[role])
        except Exception as exc:
            warn("plane pick: %s" % exc)

    def remove(self):
        if self in PlanePicker.LIVE:
            PlanePicker.LIVE.remove(self)
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
    target = _earliest(target)
    doc = body.Document
    doc.openTransaction("Create Sketch")
    try:
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [target]
        sketch.MapMode = "FlatFace"
        doc.recompute()
        if sketch_auto_project.enabled():
            sketch_auto_project.auto_project(sketch, target)
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


def _earliest(target):
    """A flat face clicked on the part belongs to the step that made it, not to the last
    step that touched the part: a sketch on the top of a block with a hole drilled in it
    hangs on the block, so suppressing or deleting the unrelated hole leaves the sketch
    (and what is built on it) alone, as in Fusion (found by the hole QA). Only the reference
    goes back: while the sketch is open the design is drawn as it is now (show_design_at),
    and what is made from the sketch builds on the body's newest step."""
    obj, name = target
    if not name.startswith("Face"):
        return target
    try:
        from . import hole

        face = obj.Shape.getElement(name)
        point = _point_on(face)
        if point is None:
            return target
        return hole.earliest_face(obj, name, point)
    except Exception:
        return target


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
