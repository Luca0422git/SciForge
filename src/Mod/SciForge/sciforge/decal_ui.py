# SPDX-License-Identifier: LGPL-2.1-or-later
"""Decal (INSERT > Decal), Fusion-style: pick the picture, click a face of a body (flat or
curved), then place it with the dialog's values or the handles on the face: two blue arrows
move it, the curved handle turns it, the arrow at its right edge scales it; Opacity, Chain
Faces (wrap onto the faces tangent to it), Horizontal / Vertical Flip. A step in the timeline
(double-click to edit), a row in the browser's Decals folder (eye, Edit Decal, Delete).
The document side is decal.py; sources: docs/sciforge/parity/misc.md.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, decal, insert_ui, log, preview, taskui, ui_icon_path, warn
from . import decal_core as core
from .compat import QtCore, QtGui, QtWidgets

# Tests put a function(kind) -> path here instead of the file dialog.
FILE_PICKER = None
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"


def pick_image():
    if FILE_PICKER is not None:
        return FILE_PICKER("decal")
    try:
        prefs = App.ParamGet(PREFS)
        start = prefs.GetString("LastInsertFolder", "") or os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            Gui.getMainWindow(),
            "Insert Decal",
            start,
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All files (*)",
        )
        if path:
            prefs.SetString("LastInsertFolder", os.path.dirname(path))
            return path
    except Exception as exc:
        warn("file dialog: %s" % exc)
    return None


def image_pixels(path):
    image = QtGui.QImage(path)
    if image.isNull():
        raise decal.DecalError("The image could not be read: %s" % os.path.basename(path))
    return image.width(), image.height()


# -- the drawing -----------------------------------------------------------------------------------
def texture(coin, path):
    """A Coin texture of the picture (at most decal_core.MAX_TEXTURE pixels wide), or None."""
    image = QtGui.QImage(path)
    if image.isNull():
        return None
    w, h = core.texture_size((image.width(), image.height()))
    if (w, h) != (image.width(), image.height()):
        image = image.scaled(w, h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
    # OpenGL's rows run from the bottom: the picture's top row goes last.
    image = image.convertToFormat(QtGui.QImage.Format_RGBA8888).mirrored(False, True)
    data = bytes(image.constBits())[: image.width() * image.height() * 4]
    tex = coin.SoTexture2()
    tex.image.setValue(coin.SbVec2s(image.width(), image.height()), 4, data)
    tex.model = coin.SoTexture2.MODULATE
    tex.wrapS = coin.SoTexture2.CLAMP
    tex.wrapT = coin.SoTexture2.CLAMP
    return tex


class ViewProviderDecal:
    """The picture drawn on the face: the decal's mesh with the picture as its texture, a
    little in front of the face. Never picked (clicks go to the body under it). Saved
    documents store "sciforge.decal_ui.ViewProviderDecal"."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        # The mesh lies where the body was when it was computed: drawn moved the way the body
        # moved by its own placement since (decal.drawn_place), so a joint or a drag that
        # moves a body without recomputing it carries the picture along at once.
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        offset = coin.SoPolygonOffset()  # in front of the face it lies on
        offset.factor = -2.0
        offset.units = -2.0
        self.root.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        self.root.addChild(hints)
        self.material = coin.SoMaterial()
        self.material.diffuseColor.setValue(1.0, 1.0, 1.0)
        self.root.addChild(self.material)
        self.texture_group = coin.SoGroup()
        self.root.addChild(self.texture_group)
        self.uv = coin.SoTextureCoordinate2()
        self.root.addChild(self.uv)
        binding = coin.SoTextureCoordinateBinding()
        binding.value = coin.SoTextureCoordinateBinding.PER_VERTEX_INDEXED
        self.root.addChild(binding)
        self.normals = coin.SoNormal()
        self.root.addChild(self.normals)
        nbind = coin.SoNormalBinding()
        nbind.value = coin.SoNormalBinding.PER_VERTEX_INDEXED
        self.root.addChild(nbind)
        self.coords = coin.SoCoordinate3()
        self.root.addChild(self.coords)
        self.faces = coin.SoIndexedFaceSet()
        self.root.addChild(self.faces)
        self._image = None
        vobj.addDisplayMode(self.root, "Decal")
        self._update(vobj.Object)

    def place(self, obj=None):
        """Put the drawing where the decal's body is now (its placement)."""
        obj = obj if obj is not None else self.Object
        try:
            plc = decal.drawn_place(obj)
            self.transform.translation.setValue(tuple(plc.Base))
            self.transform.rotation.setValue(tuple(plc.Rotation.Q))
        except Exception as exc:
            warn("decal drawing: %s" % exc)

    def _update(self, obj):
        from pivy import coin

        self.place(obj)
        try:
            path = getattr(obj, "ImageFile", "")
            if path != self._image:
                self.texture_group.removeAllChildren()
                tex = texture(coin, path) if path and os.path.isfile(path) else None
                if tex is not None:
                    self.texture_group.addChild(tex)
                self._image = path
            self.material.transparency = 1.0 - max(0, min(100, int(obj.Opacity))) / 100.0
            points = [(p.x, p.y, p.z) for p in obj.MeshPoints]
            uvs = [(p.x, p.y) for p in obj.MeshUV]
            normals = [(p.x, p.y, p.z) for p in obj.MeshNormals]
            flat = list(obj.MeshTriangles)
            index = []
            for i in range(0, len(flat) - 2, 3):
                index += [flat[i], flat[i + 1], flat[i + 2], -1]
            self.faces.coordIndex.setNum(0)
            self.coords.point.setNum(0)
            self.uv.point.setNum(0)
            self.normals.vector.setNum(0)
            if points and index:
                self.coords.point.setValues(0, len(points), points)
                self.uv.point.setValues(0, len(uvs), uvs)
                self.normals.vector.setValues(0, len(normals), normals)
                self.faces.coordIndex.setValues(0, len(index), index)
        except Exception as exc:
            warn("decal drawing: %s" % exc)

    def drawn(self):
        """(points, triangles, has a picture) as Coin draws them now (for the tests)."""
        return (
            self.coords.point.getNum(),
            self.faces.coordIndex.getNum() // 4,
            self.texture_group.getNumChildren() == 1,
        )

    def updateData(self, obj, prop):
        if prop in ("MeshPoints", "MeshTriangles", "Opacity", "ImageFile", "MeshUV"):
            self._update(obj)
        elif prop in ("Body", "BodyPlace"):
            self.place(obj)

    def getDisplayModes(self, vobj):
        return ["Decal"]

    def getDefaultDisplayMode(self):
        return "Decal"

    def setDisplayMode(self, mode):
        return mode

    def onChanged(self, vobj, prop):
        return None

    def getIcon(self):
        return ui_icon_path("decal")

    def doubleClicked(self, vobj):
        try:
            edit_decal(vobj.Object)
        except Exception as exc:
            warn("Edit Decal: %s" % exc)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def attach_view(obj):
    try:
        if App.GuiUp and obj.ViewObject is not None:
            ViewProviderDecal(obj.ViewObject)
    except Exception as exc:
        warn("decal drawing: %s" % exc)


# -- the dialog ---------------------------------------------------------------------------------
def _container_place(obj):
    try:
        from . import components

        container = components.container_of(obj)
        if container is not None:
            return container.getGlobalPlacement()
    except Exception:
        pass
    return App.Placement()


class _FacePick:
    """Waits for a click on a face of a body: on_pick(body, face name, point in the body's
    component's coordinates) once."""

    def __init__(self, panel, on_pick):
        self.panel = panel
        self.on_pick = on_pick
        self.done = False
        picker = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, picker._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _selection_changed(self):
        if self.done:
            return
        try:
            target = selected_face()
            if target is None:
                if Gui.Selection.getSelectionEx():
                    Gui.Selection.clearSelection()
                    commands.tell("Click a face of a body (flat or curved).")
                return
            self.done = True
            self.remove()
            Gui.Selection.clearSelection()
        except Exception as exc:
            warn("Decal: face pick: %s" % exc)
            return
        self.panel.guarded(self.on_pick, *target)

    def remove(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None


def selected_face():
    """(body, face name in the body's shape, point) of the face picked, or None."""
    for sel in Gui.Selection.getSelectionEx():
        names = [n for n in sel.SubElementNames if n.startswith("Face")]
        if not names:
            continue
        body = bodies.body_of(sel.Object)
        if body is None or not bodies.has_solid(body):
            continue
        place = _container_place(body).inverse()
        try:
            point = sel.PickedPoints[0]
        except Exception:
            point = sel.Object.Shape.getElement(names[0]).CenterOfMass
        point = place.multVec(point)
        name = names[0]
        if sel.Object is not body and sel.Object is not body.Tip:
            name = _nearest_face(body.Shape, point) or name
        return body, name, point
    return None


def _nearest_face(shape, point):
    import Part

    best, best_d = None, None
    vertex = Part.Vertex(point)
    for i, face in enumerate(shape.Faces):
        try:
            d = face.distToShape(vertex)[0]
        except Exception:
            continue
        if best_d is None or d < best_d:
            best, best_d = "Face%d" % (i + 1), d
    return best


class DecalPanel(insert_ui._InsertPanel):
    """Fusion's Decal dialog."""

    title = "Decal"
    icon = "decal"

    def __init__(self, doc, path=None, feature=None):
        super().__init__(doc, "Edit Decal" if feature is not None else "Decal")
        self.editing = feature is not None
        self.obj = feature
        self.path = path
        self.pick = None
        self.handles = []
        self.value_boxes = taskui.ValueBoxes(self, default="x")
        self._drag_start = None
        if feature is None:
            self.pixels = image_pixels(path)
        else:
            self.title = "Edit Decal"
            self.form.setWindowTitle(self.title)
        values = (
            decal.option_values(feature)
            if feature is not None
            else {
                "opacity": 100,
                "chain": True,
                "dx": 0.0,
                "dy": 0.0,
                "angle": 0.0,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "flip_h": False,
                "flip_v": False,
            }
        )
        shown = os.path.basename(path or "") if feature is None else feature.Label
        self.layout.addRow(QtWidgets.QLabel("Image"), QtWidgets.QLabel(shown))
        self.face_label = QtWidgets.QLabel("")
        self.face_label.setObjectName("SciForgeDecalFace")
        self.face_button = None
        if feature is None:
            self.layout.addRow(QtWidgets.QLabel("Face"), self.face_label)
        else:  # Edit: another face can be clicked (its own one deleted, or elsewhere wanted)
            row = QtWidgets.QWidget()
            box = QtWidgets.QHBoxLayout(row)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(self.face_label, 1)
            self.face_button = QtWidgets.QPushButton("Select Face")
            self.face_button.setObjectName("SciForgeDecalFaceButton")
            self.face_button.setToolTip("Click it, then a face: the decal goes there")
            self.face_button.clicked.connect(lambda _=False: self.guarded(self._wait_for_face))
            box.addWidget(self.face_button)
            self.layout.addRow(QtWidgets.QLabel("Face"), row)
        self.chain = self.check("Chain Faces", values["chain"], self.apply)
        self.opacity = QtWidgets.QSpinBox()
        self.opacity.setObjectName("SciForgeDecalOpacity")
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setValue(int(values["opacity"]))
        self.opacity.setKeyboardTracking(False)
        self.opacity.valueChanged.connect(lambda *_: self.guarded(self.apply))
        self.layout.addRow(QtWidgets.QLabel("Opacity"), self.opacity)
        self.dx = self.number("X Distance", values["dx"], "mm", self.apply)
        self.dy = self.number("Y Distance", values["dy"], "mm", self.apply)
        self.angle = self.number("Z Angle", values["angle"], "deg", self.apply)
        self.scale_x = self.spin("Scale X", values["scale_x"], 0.001, 10000.0, self.apply, 4)
        self.scale_y = self.spin("Scale Y", values["scale_y"], 0.001, 10000.0, self.apply, 4)
        self.scale_xy = self.spin("Scale Plane XY", 1.0, 0.001, 10000.0, self._scale_both, 4)
        self.flip_h = self.check("Horizontal Flip", values["flip_h"], self.apply)
        self.flip_v = self.check("Vertical Flip", values["flip_v"], self.apply)
        self.finish_layout()
        if feature is None:
            target = selected_face()
            if target is not None:
                Gui.Selection.clearSelection()
                self.guarded(self._face_picked, *target)
            else:
                self.face_label.setText("Click a face of a body")
                self.say("Click the face to put the picture on (flat or curved).")
                self.pick = _FacePick(self, self._face_picked)
        else:
            self.target = feature
            self._show_face()
            self._show_size()
            self._make_handles()
        Gui.Selection.clearSelection()
        if feature is not None and not feature.MeshPoints:
            # its face is gone: the dialog waits for the face to put it on
            self.guarded(self._wait_for_face)
            self.say("The face this decal was on is gone. Click a face to put the picture there.")

    # -- placing -----------------------------------------------------------------------------
    def _show_face(self):
        obj = self.feature()
        if obj is None or self.pick is not None:
            return
        body = obj.Body
        gone = not obj.MeshPoints and "Invalid" in list(obj.State)
        self.face_label.setText(
            "%s %s%s" % (body.Label if body is not None else "?", obj.FaceName, " (gone)" * gone)
        )

    def _wait_for_face(self):
        if self.pick is not None:
            self.pick.remove()
        Gui.Selection.clearSelection()
        self.face_label.setText("Click a face of a body")
        self.pick = _FacePick(self, self._face_repicked)

    def _face_repicked(self, body, face_name, point):
        """Edit: a face clicked: the decal goes onto it (X / Y Distance back to 0)."""
        self.pick = None
        obj = self.feature()
        if obj is None:
            return
        decal.relay(obj, body, face_name, point)
        self._quiet = True
        try:
            self.dx.set_value(0.0)
            self.dy.set_value(0.0)
        finally:
            self._quiet = False
        self.apply()
        self._show_face()
        _refresh_browser()

    def _face_picked(self, body, face_name, point):
        self.pick = None
        self.obj = decal.make(body, face_name, point, self.path, self.pixels)
        attach_view(self.obj)
        self.target = self.obj
        self.face_label.setText("%s %s" % (body.Label, face_name))
        self.apply()
        self._show_size()
        _refresh_browser()

    def _show_size(self):
        obj = self.obj
        if obj is None:
            return
        self.say(
            "%d x %d pixels, %.1f x %.1f mm on a %s face. Drag the arrows to move it, the "
            "curved handle to turn it, the right arrow to scale it."
            % (
                obj.PixelWidth,
                obj.PixelHeight,
                obj.BaseWidth * obj.ScaleX,
                obj.BaseHeight * obj.ScaleY,
                {"Plane": "flat", "Cylinder": "cylindrical"}.get(obj.Surface, "curved"),
            )
        )

    def _scale_both(self):
        value = self.scale_xy.value()
        self._quiet = True
        try:
            self.scale_x.setValue(value)
            self.scale_y.setValue(value)
        finally:
            self._quiet = False
        self.apply()

    def values(self):
        return dict(
            opacity=self.opacity.value(),
            chain=self.chain.isChecked(),
            dx=self.dx.value(),
            dy=self.dy.value(),
            angle=self.angle.value(),
            scale_x=self.scale_x.value(),
            scale_y=self.scale_y.value(),
            flip_h=self.flip_h.isChecked(),
            flip_v=self.flip_v.isChecked(),
        )

    def apply(self):
        if self.obj is None or not bodies.alive(self.obj):
            return
        decal.set_options(self.obj, **self.values())
        self.schedule()

    def _recompute(self):
        super()._recompute()
        if self._drag_start is None:  # never under a handle being dragged
            self._make_handles()
        self._show_size()
        self._show_face()

    def feature(self):
        return self.obj if self.obj is not None and bodies.alive(self.obj) else None

    def show_status(self):
        obj = self.feature()
        if obj is None:
            return
        state = list(obj.State)
        if "Invalid" in state or "Error" in state:
            self.message.setText("⚠ " + insert_ui._plain(obj.getStatusString()))
        else:
            self.message.setText("")

    # -- handles ----------------------------------------------------------------------------
    def _make_handles(self):
        self._remove_handles()
        obj = self.feature()
        if obj is None or self.view is None or not obj.MeshPoints:
            return
        import math

        from . import extrude_ui

        place = decal.global_place(obj)  # the decal's coordinates are its body's own
        point, x, y, z = decal.centre(obj)
        point = place.multVec(point)
        rot = place.Rotation
        x, y, z = rot.multVec(x), rot.multVec(y), rot.multVec(z)
        size = taskui.handle_size_at(self.view, point)
        a = math.radians(obj.ZAngle)
        xr = x * math.cos(a) + y * math.sin(a)
        half = 0.5 * obj.BaseWidth * obj.ScaleX
        try:
            move_x = taskui.ArrowDragger(
                point, x, 0.0, size, lambda d: self._dragged("x", d), lambda d: self._released()
            )
            move_y = taskui.ArrowDragger(
                point, y, 0.0, size, lambda d: self._dragged("y", d), lambda d: self._released()
            )
            scale = taskui.ArrowDragger(
                point + xr * half,
                xr,
                0.0,
                size * 0.8,
                lambda d: self._dragged("scale", d),
                lambda d: self._released(),
            )
            turn = extrude_ui.AngleDragger(
                point,
                z,
                x,
                obj.ZAngle,
                max(half * 0.7, size * 1.5),
                size * 0.35,
                lambda deg: self._dragged("angle", deg),
                lambda deg: self._released(),
            )
        except Exception as exc:
            warn("decal handles: %s" % exc)
            return
        self.handles = [move_x, move_y, scale, turn]
        self.handle_by = {"x": move_x, "y": move_y, "scale": scale, "angle": turn}
        boxes = self.value_boxes
        boxes.attach(move_x, "x", lambda: self.dx.widget.text(), self._typed(self.dx))
        boxes.attach(move_y, "y", lambda: self.dy.widget.text(), self._typed(self.dy))
        boxes.attach(turn, "angle", lambda: self.angle.widget.text(), self._typed(self.angle))

    def _typed(self, field):
        def commit(text):
            field.take(field.parse(text))

        return commit

    def _dragged(self, kind, value):
        if getattr(self, "_closed", False) or self.obj is None:
            return
        if self._drag_start is None:
            self._drag_start = decal.option_values(self.obj)
        start = self._drag_start
        self._quiet = True
        try:
            if kind == "x":
                self.dx.set_value(start["dx"] + value)
            elif kind == "y":
                self.dy.set_value(start["dy"] + value)
            elif kind == "angle":
                self.angle.set_value(value)
            elif kind == "scale":
                width0 = max(1e-6, self.obj.BaseWidth * start["scale_x"])
                factor = max(0.01, (width0 + 2.0 * value) / width0)
                self.scale_x.setValue(start["scale_x"] * factor)
                self.scale_y.setValue(start["scale_y"] * factor)
        finally:
            self._quiet = False
        self.apply()

    def _released(self):
        self._drag_start = None
        # The handles go to the decal's new middle (later: never inside the dragger's poll).
        QtCore.QTimer.singleShot(0, lambda: self.guarded(self._make_handles))

    def _remove_handles(self):
        handles, self.handles = self.handles, []
        self.handle_by = {}
        for handle in handles:
            try:
                handle.remove()
            except Exception:
                pass

    # -- OK / Cancel -------------------------------------------------------------------------
    def accept(self):
        if self.obj is None:
            self.message.setText("⚠ Click a face of a body first.")
            return False
        if not super().accept():
            return False
        _refresh_browser()
        return True

    def reject(self):
        result = super().reject()
        _refresh_browser()
        return result

    def cleanup(self):
        if self.pick is not None:
            self.pick.remove()
            self.pick = None
        self._remove_handles()
        try:
            self.value_boxes.discard()
        except Exception:
            pass
        super().cleanup()


def _refresh_browser():
    try:
        from . import browser_ui

        widget = browser_ui.widget()
        if widget is not None:
            widget.refresh(force=True)
    except Exception:
        pass


# -- designs opened again: the pictures drawn ---------------------------------------------------
class _Watch:
    """A design opened, or an undo / redo that brought a decal back: its drawing is put back
    (FreeCAD makes a plain view for it until the proxy is there)."""

    def _later(self, doc):
        try:
            name = doc.Name
        except Exception:
            return
        QtCore.QTimer.singleShot(400, lambda: self._run(name))

    def _run(self, name):
        try:
            if name not in App.listDocuments():
                return
            doc = App.getDocument(name)
            if getattr(doc, "Restoring", False):
                QtCore.QTimer.singleShot(300, lambda: self._run(name))
                return
            for obj in decal.decals(doc):
                vobj = obj.ViewObject
                if vobj is not None and not isinstance(
                    getattr(vobj, "Proxy", None), ViewProviderDecal
                ):
                    attach_view(obj)
            # a design saved before decals went with their body into its component
            owners = {o.Body.Name: o.Body for o in decal.decals(doc) if o.Body is not None}
            for body in owners.values():
                decal.carry(body)
            # an undo / redo that brought a body back without its decal's own change (a
            # step recomputed after its undo step was closed): the decal follows its face now
            for obj in decal.decals(doc):
                if decal.stale(obj):
                    log("decal %s follows its face again" % obj.Label)
                    with preview.quiet():  # a red one says why in the timeline
                        obj.recompute()
            place_drawings(doc)
        except Exception as exc:
            warn("decals: %s" % exc)

    def slotChangedObject(self, obj, prop):
        """A body or component moved (a joint, Component Drag, a component Move, an undo):
        the decals on it are drawn where it is now, at once."""
        if prop not in ("Placement", "Group"):
            return
        try:
            if obj.TypeId not in ("PartDesign::Body", "App::Part"):
                return
            place_drawings(obj.Document)
        except Exception as exc:
            warn("decals: %s" % exc)

    def slotCreatedDocument(self, doc):
        self._later(doc)

    def slotUndoDocument(self, doc):
        self._later(doc)

    def slotRedoDocument(self, doc):
        self._later(doc)


def place_drawings(doc):
    """Every decal of `doc` drawn where its body is now."""
    for obj in decal.decals(doc):
        proxy = getattr(getattr(obj, "ViewObject", None), "Proxy", None)
        if isinstance(proxy, ViewProviderDecal):
            proxy.place(obj)


_WATCH = {"observer": None}


def install_watch():
    if _WATCH["observer"] is None and App.GuiUp:
        _WATCH["observer"] = _Watch()
        App.addDocumentObserver(_WATCH["observer"])


# -- commands -------------------------------------------------------------------------------------
def insert_decal(path=None):
    if App.ActiveDocument is None:
        commands.tell("Open a design with a body first: a decal goes on a face of a body.")
        return None
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    if not bodies.solid_bodies(doc):
        commands.tell("A decal goes on a face of a body: this design has no body yet.")
        return None
    path = path or pick_image()
    if not path:
        return None
    return insert_ui._open(DecalPanel, path)


def edit_decal(obj):
    return insert_ui._edit(DecalPanel, obj)


class DecalCommand:
    def GetResources(self):
        return {
            "MenuText": "Decal",
            "ToolTip": "A picture on a face of a body, flat or curved (labels, logos, markings)",
            "Pixmap": ui_icon_path("decal"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            insert_decal()
        except decal.DecalError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("Decal: %s" % exc)


class EditDecalCommand:
    def GetResources(self):
        return {
            "MenuText": "Edit Decal",
            "ToolTip": "Opacity, position, angle and scale of a decal",
            "Pixmap": ui_icon_path("decal"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            for sel in Gui.Selection.getSelectionEx():
                if decal.is_decal(sel.Object):
                    edit_decal(sel.Object)
                    return
            commands.tell("Pick the decal first (right-click it in the browser > Edit Decal).")
        except Exception as exc:
            warn("Edit Decal: %s" % exc)


COMMANDS = {"SciForge_Decal": DecalCommand, "SciForge_EditDecal": EditDecalCommand}
EDITORS = {"SciForge::" + decal.TYPE: edit_decal}

try:
    install_watch()
except Exception as _exc:  # pragma: no cover - only without a GUI
    warn("decal watch not installed: %s" % _exc)
