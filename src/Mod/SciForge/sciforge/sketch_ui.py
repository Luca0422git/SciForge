# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create Sketch like Fusion: the origin planes appear, you click one of them or a flat
face of the part, and the sketch opens on it. No attachment pop-ups.

FreeCAD 1.1 draws its origin planes small, at a fixed size, so SciForge draws its own
large see-through squares for XY, XZ and YZ; they light up under the mouse and a
click is matched to them geometrically (nearest square along the mouse ray).

If a plane or flat face is already selected, the sketch opens on it at once.
Esc / Cancel leaves without creating anything.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, taskui, ui_icon, warn
from .compat import QtCore, QtWidgets

PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
IDLE = ((0.96, 0.74, 0.38), 0.72)  # (colour, transparency)
HOVER = ((0.45, 0.77, 1.0), 0.45)
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


class PlanePicker:
    """The three big origin squares; on_pick(plane object) when one is clicked."""

    def __init__(self, view, body, on_pick):
        from pivy import coin

        self.view = view
        self.on_pick = on_pick
        self.placement = body.getGlobalPlacement()
        self.objects = origin_planes(body)
        empty = body.Shape.isNull() or not body.Shape.Solids
        if empty:
            self.size = 100.0
        else:
            box = body.Shape.BoundBox
            self.size = max(20.0, 1.3 * max(box.XLength, box.YLength, box.ZLength))
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.root.addChild(coin.SoPolygonOffset())
        self.materials = {}
        for role in self.objects:
            self.materials[role] = self._square(coin, role)
        self.hovered = None
        view.getSceneGraph().addChild(self.root)
        self.callbacks = [
            ("SoMouseButtonEvent", view.addEventCallback("SoMouseButtonEvent", self._button)),
            ("SoLocation2Event", view.addEventCallback("SoLocation2Event", self._moved)),
        ]
        if empty:  # nothing to look at yet: frame the planes, like a new Fusion design
            view.viewIsometric()
            view.fitAll()

    def _frame(self, role):
        normal, u, v = PLANES[role]
        rot = self.placement.Rotation
        return self.placement.Base, rot.multVec(normal), rot.multVec(u), rot.multVec(v)

    def _square(self, coin, role):
        base, _normal, u, v = self._frame(role)
        h = self.size / 2.0
        corners = [base + u * a * h + v * b * h for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*IDLE[0])
        material.emissiveColor.setValue(*[c * 0.5 for c in IDLE[0]])
        material.transparency.setValue(IDLE[1])
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 4, [(p.x, p.y, p.z) for p in corners])
        faces = coin.SoFaceSet()
        faces.numVertices.setValue(4)
        outline = coin.SoLineSet()
        coords_line = coin.SoCoordinate3()
        loop = corners + [corners[0]]
        coords_line.point.setValues(0, 5, [(p.x, p.y, p.z) for p in loop])
        outline.numVertices.setValue(5)
        sep.addChild(material)
        sep.addChild(coords)
        sep.addChild(faces)
        sep.addChild(coords_line)
        sep.addChild(outline)
        self.root.addChild(sep)
        return material

    def plane_at(self, position):
        """Role of the nearest origin square under the mouse, or None."""
        from .profile_pick import ray_plane

        best = None
        for role in self.objects:
            base, normal, u, v = self._frame(role)
            hit = ray_plane(self.view, position, base, normal)
            if hit is None:
                continue
            point, t = hit
            local = point - base
            h = self.size / 2.0
            if abs(local.dot(u)) <= h and abs(local.dot(v)) <= h:
                if best is None or t < best[1]:
                    best = (role, t)
        return best[0] if best else None

    def _geometry_at(self, position):
        """True if the part (not the empty background) is under the mouse."""
        info = self.view.getObjectInfo(tuple(position))
        return bool(info and info.get("Object") and info.get("Component", "").startswith("Face"))

    def _moved(self, info):
        try:
            role = None
            if not self._geometry_at(info["Position"]):
                role = self.plane_at(info["Position"])
            material = self.materials.get(role)
            if material is not self.hovered:
                for m, look in ((self.hovered, IDLE), (material, HOVER)):
                    if m is not None:
                        m.diffuseColor.setValue(*look[0])
                        m.emissiveColor.setValue(*[c * 0.5 for c in look[0]])
                        m.transparency.setValue(look[1])
                self.hovered = material
        except Exception as exc:
            warn("plane hover: %s" % exc)

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            if self._geometry_at(info["Position"]):
                return  # a face of the part: the selection observer takes it
            role = self.plane_at(info["Position"])
            if role is not None:
                self.on_pick(self.objects[role])
        except Exception as exc:
            warn("plane pick: %s" % exc)

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
    """New sketch in `body` attached flat to `target` = (plane or feature, "" or "FaceN")."""
    doc = body.Document
    doc.openTransaction("Create Sketch")
    try:
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = [target]
        sketch.MapMode = "FlatFace"
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        raise
    doc.commitTransaction()
    return sketch


def open_sketch(sketch):
    Gui.Selection.clearSelection()
    Gui.ActiveDocument.setEdit(sketch.Name)
    log("sketch %s opened" % sketch.Label)


class SketchPicker:
    """The waiting state of Create Sketch (a task dialog with only Cancel)."""

    def __init__(self, body):
        self.body = body
        self.doc = body.Document
        self._closed = False
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Create Sketch")
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
        taskui.set_current(self)

    def _selection_changed(self):
        if self._closed:
            return
        target = sketch_target()
        if target is not None:
            self._picked(target)

    def _picked(self, target):
        if self._closed:
            return
        self._cleanup()
        Gui.Control.closeDialog()
        QtCore.QTimer.singleShot(0, lambda: self._create(target))

    def _create(self, target):
        try:
            open_sketch(create_sketch(self.body, target))
        except Exception as exc:
            warn("Create Sketch failed: %s" % exc)

    def _cleanup(self):
        self._closed = True
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
        self._cleanup()
        Gui.Control.closeDialog()
        return True

    def accept(self):
        return self.reject()

    def finish(self):
        self.reject()


def start():
    """Create Sketch: on the selected plane/face at once, else let the user click one."""
    body = commands.ensure_body()
    if body is None:
        warn("Create Sketch: could not create a body")
        return None
    target = sketch_target()
    if target is not None:
        sketch = create_sketch(body, target)
        open_sketch(sketch)
        return sketch
    picker = SketchPicker(body)
    Gui.Control.showDialog(picker)
    log("create sketch: waiting for a plane or face")
    return picker
