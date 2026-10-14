# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Display Settings, Fusion-style: Visual Style, Environment, Effects,
Object Visibility, Camera and Ground Plane Offset.

  Visual Style      Fusion's six styles on every 3D view: FreeCAD's draw styles (Shaded,
                    Flat Lines, As Is, Wireframe, Hidden Line), and for the two "with Hidden
                    Edges" styles SciForge draws the edges behind the faces dashed (a Coin
                    node per design: lines drawn only where something is in front of them).
  Environment       the background of the 3D views (Fusion's lit scenes: background only).
  Effects           Ground Shadow (the bodies' outline straight below them) and Ground
                    Plane (a light floor under the model), at the Ground Plane Offset.
  Object Visibility kinds of objects hidden in the display only (origins, sketches,
                    construction geometry, analyses, joints, canvases, meshes): a hidden
                    kind is neither drawn nor clickable; the browser's eyes are untouched.
  Camera            Orthographic, Perspective, Perspective with Ortho Faces (orthographic
                    while the view looks straight at a face, e.g. after a ViewCube click).

The choices (not Object Visibility) are remembered (preferences Mod/SciForge/Display). The
scenarios' harness puts them back to Fusion's defaults first (reset()), as a test run shares
one set of preferences. Nothing here goes into a design or its undo history.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import log, nav_core, theme, warn
from . import surface_analysis as sa
from . import ui_icon_path
from .compat import QtCore, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/Display"
DEFAULTS = {
    "VisualStyle": nav_core.DEFAULT_STYLE,
    "Environment": nav_core.DEFAULT_ENVIRONMENT,
    "Camera": nav_core.DEFAULT_CAMERA,
    "GroundShadow": False,
    "GroundPlane": False,
    "GroundOffset": 0,
}
NODE_NAME = "SciForgeDisplay"
HIDE_NAME = "SciForgeObjectVisibility"
HIDDEN_EDGE_COLOR = (0.55, 0.58, 0.62)
# Object Visibility: the kinds in Fusion's order
KINDS = [
    "Origins",
    "Analysis",
    "Joints",
    "Joint Origins",
    "Sketches",
    "Construction Planes",
    "Construction Axes",
    "Construction Points",
    "Canvases",
    "Mesh Bodies",
]
_STATE = {
    "on": False,
    "hidden": set(),  # Object Visibility kinds switched off
    "nodes": {},  # document name -> its Coin node (hidden edges, ground)
    "hides": {},  # (document, object) -> [inserted nodes]
    "observer": None,
    "area": None,
    "camera_timer": None,
    "pending": set(),
    "armed": False,
}


# -- preferences ---------------------------------------------------------------------------------
def get(name):
    default = DEFAULTS[name]
    try:
        group = App.ParamGet(PARAMS)
        if isinstance(default, bool):
            return group.GetBool(name, default)
        if isinstance(default, int):
            return group.GetInt(name, default)
        return group.GetString(name, default) or default
    except Exception:
        return default


def put(name, value):
    try:
        group = App.ParamGet(PARAMS)
        default = DEFAULTS[name]
        if isinstance(default, bool):
            group.SetBool(name, bool(value))
        elif isinstance(default, int):
            group.SetInt(name, int(value))
        else:
            group.SetString(name, str(value))
    except Exception as exc:
        warn("display settings: %s" % exc)


def reset():
    """Fusion's defaults again (the scenarios' harness calls this before each scenario)."""
    for name, value in DEFAULTS.items():
        put(name, value)
    _STATE["hidden"] = set()
    if _STATE["on"]:
        apply_all()


# -- the 3D views --------------------------------------------------------------------------------
def views(doc=None):
    """Every 3D view (of `doc`, or of every design)."""
    found = []
    docs = [doc] if doc is not None else [App.getDocument(n) for n in App.listDocuments()]
    for d in docs:
        try:
            gui = Gui.getDocument(d.Name)
            if gui is None:
                continue
            for view in gui.mdiViewsOfType("Gui::View3DInventor"):
                found.append(view)
        except Exception:
            continue
    return found


def apply_view(view):
    """Visual style, background and camera of one 3D view."""
    mode, _hidden, _fill = nav_core.style(get("VisualStyle"))
    viewer = view.getViewer()
    try:
        viewer.setOverrideMode(mode)
    except Exception as exc:
        warn("visual style: %s" % exc)
    top, bottom = nav_core.environment(get("Environment"))
    try:
        if get("Environment") == "Theme":
            viewer.setGradientBackground("NONE")
            viewer.setBackgroundColor(*nav_core.rgb(theme.VIEW))
        else:
            viewer.setGradientBackground("LINEAR")
            viewer.setGradientBackgroundColor(nav_core.rgb(top), nav_core.rgb(bottom))
    except Exception as exc:
        warn("environment: %s" % exc)
    camera = get("Camera")
    try:
        want = camera
        if camera == "Perspective with Ortho Faces":
            want = (
                "Orthographic" if nav_core.wants_ortho(view.getViewDirection()) else "Perspective"
            )
        if view.getCameraType() != want:
            view.setCameraType(want)
    except Exception as exc:
        warn("camera: %s" % exc)


def apply_all():
    for view in views():
        try:
            apply_view(view)
        except Exception as exc:
            warn("display settings: %s" % exc)
    for name in App.listDocuments():
        try:
            schedule(App.getDocument(name))
        except Exception:
            continue
    _camera_timer()


# -- per design: hidden edges, ground, object visibility -----------------------------------------
def schedule(doc):
    try:
        _STATE["pending"].add(doc.Name)
    except Exception:
        return
    if not _STATE["armed"]:
        _STATE["armed"] = True
        QtCore.QTimer.singleShot(60, _run)


def _run():
    _STATE["armed"] = False
    names, _STATE["pending"] = _STATE["pending"], set()
    for name in names:
        try:
            doc = App.getDocument(name)
        except Exception:
            _forget(name)
            continue
        try:
            if doc.Recomputing:
                schedule(doc)
                continue
            draw(doc)
        except Exception as exc:
            warn("display settings: %s" % exc)


def _owners(doc):
    found = []
    for obj in doc.Objects:
        if sa.owner_of(obj) is not obj:
            continue
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility:
                continue
            if obj.Shape.isNull() or not obj.Shape.Faces:
                continue
        except Exception:
            continue
        found.append(obj)
    return found


def _detach(doc_name):
    node = _STATE["nodes"].pop(doc_name, None)
    if node is None:
        return
    try:
        doc = App.getDocument(doc_name)
    except Exception:
        doc = None
    if doc is not None:
        for view in views(doc):
            try:
                root = view.getSceneGraph()
                index = root.findChild(node)
                if index >= 0:
                    root.removeChild(index)
            except Exception:
                continue
    node.unref()


def _forget(doc_name):
    _detach(doc_name)
    for key in [k for k in _STATE["hides"] if k[0] == doc_name]:
        for node in _STATE["hides"].pop(key):
            node.unref()


def draw(doc):
    """Put the display extras of `doc` in order: hidden edges, ground, object visibility."""
    from pivy import coin

    _detach(doc.Name)
    apply_visibility(doc)
    _draw(doc, coin)
    try:
        from . import surface_analysis_ui as ui

        ui.cover(doc)  # the model's faces under a hidden-line style off, or back on
        ui.redraw_views(doc)
    except Exception as exc:
        warn("display settings: %s" % exc)


def _draw(doc, coin):
    if not _STATE["on"]:
        return
    _mode, hidden_edges, fill = nav_core.style(get("VisualStyle"))
    shadow, plane = get("GroundShadow"), get("GroundPlane")
    if not (hidden_edges or fill or shadow or plane):
        return
    owners = _owners(doc)
    if not owners:
        return
    node = coin.SoSeparator()
    node.setName(NODE_NAME)
    node.ref()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    node.addChild(pick)
    if fill:
        node.addChild(_fill(coin, fill_owners(doc)))
    if hidden_edges:
        node.addChild(_hidden_edges(coin, owners))
    if shadow or plane:
        node.addChild(_ground(coin, owners, shadow, plane))
    _STATE["nodes"][doc.Name] = node
    for view in views(doc):
        try:
            view.getSceneGraph().addChild(node)
        except Exception:
            continue


def filling():
    """True while a hidden-line visual style fills the faces."""
    return bool(_STATE["on"] and nav_core.style(get("VisualStyle"))[2])


def fill_owners(doc):
    """The bodies whose faces a hidden-line style fills with the background colour (not
    those an analysis covers: the analysis shows there)."""
    if not _STATE["on"] or not nav_core.style(get("VisualStyle"))[2]:
        return []
    from . import surface_analysis_ui as ui

    analysed = ui.analysed_owners(doc)
    return [o for o in _owners(doc) if o.Name not in analysed]


def _fill(coin, owners):
    """The faces in the background's colour, where the model's own faces are (switched off
    meanwhile): they hide what is behind them, only the edges show."""
    from . import surface_analysis_ui as ui

    sep = coin.SoSeparator()
    light = coin.SoLightModel()
    light.model = coin.SoLightModel.BASE_COLOR
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*nav_core.background_of(get("Environment")))
    sep.addChild(light)
    sep.addChild(material)
    for owner in owners:
        m = sa.mesh(owner, (), coarse=True)
        if not m.triangles:
            continue
        group = ui.group_for(coin, owner)
        faces, _index = ui.surface_nodes(coin, group, m)
        group.addChild(faces)
        sep.addChild(group)
    return sep


def _hidden_edges(coin, owners):
    """The bodies' edges, drawn dashed only where something is in front of them."""
    from . import surface_analysis_ui as ui

    sep = coin.SoSeparator()
    light = coin.SoLightModel()
    light.model = coin.SoLightModel.BASE_COLOR
    depth = coin.SoDepthBuffer()
    # pivy shows SoNode's write() method under .write: the fields are reached by name
    depth.getField("test").setValue(True)
    depth.getField("write").setValue(False)
    depth.getField("function").setValue(coin.SoDepthBuffer.GREATER)
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(1.0)
    style.linePattern.setValue(0x0F0F)
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*HIDDEN_EDGE_COLOR)
    for item in (light, depth, style, material):
        sep.addChild(item)
    for owner in owners:
        group = ui.group_for(coin, owner)
        size = max(1e-3, owner.Shape.BoundBox.DiagonalLength)
        points, counts = [], []
        for edge in owner.Shape.Edges:
            try:
                pts = edge.discretize(Deflection=size / 1500.0)
            except Exception:
                continue
            if len(pts) < 2:
                continue
            points += [(p.x, p.y, p.z) for p in pts]
            counts.append(len(pts))
        if not counts:
            continue
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        lines = coin.SoLineSet()
        lines.numVertices.setValues(0, len(counts), counts)
        group.addChild(coords)
        group.addChild(lines)
        sep.addChild(group)
    return sep


def ground_box(owners):
    box = None
    for owner in owners:
        try:
            frame = sa.parent_placement(owner)
            shape = owner.Shape
            b = (
                shape.BoundBox
                if frame.isIdentity()
                else shape.transformed(frame.toMatrix()).BoundBox
            )
            box = b if box is None else box.united(b)
        except Exception:
            continue
    return box


def ground_z(owners):
    box = ground_box(owners)
    if box is None:
        return 0.0
    return nav_core.ground_level(box.ZMin, box.DiagonalLength, get("GroundOffset"))


def _ground(coin, owners, shadow, plane):
    """A light floor and / or the bodies' shadow straight below them, at the ground level."""
    sep = coin.SoSeparator()
    box = ground_box(owners)
    if box is None:
        return sep
    z = ground_z(owners)
    light = coin.SoLightModel()
    light.model = coin.SoLightModel.BASE_COLOR
    sep.addChild(light)
    if plane:
        half = box.DiagonalLength * 1.2
        cx, cy = box.Center.x, box.Center.y
        floor = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.82, 0.84, 0.87)
        material.transparency.setValue(0.55)
        coords = coin.SoCoordinate3()
        corners = [
            (cx - half, cy - half, z),
            (cx + half, cy - half, z),
            (cx + half, cy + half, z),
            (cx - half, cy + half, z),
        ]
        coords.point.setValues(0, 4, corners)
        face = coin.SoFaceSet()
        face.numVertices.setValue(4)
        for item in (material, coords, face):
            floor.addChild(item)
        sep.addChild(floor)
    if shadow:
        lift = box.DiagonalLength * 1e-3
        dark = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.05, 0.05, 0.06)
        material.transparency.setValue(0.45)
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(-1.0)
        offset.units.setValue(-1.0)
        dark.addChild(material)
        dark.addChild(offset)
        for owner in owners:
            m = sa.mesh(owner, (), coarse=True)
            if not m.triangles:
                continue
            frame = sa.parent_placement(owner)
            points = []
            for p in m.points:
                q = frame.multVec(App.Vector(*p))
                points.append((q.x, q.y, z + lift))
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(points), points)
            index = []
            for a, b, c in m.triangles:
                index += [a, b, c, -1]
            faces = coin.SoIndexedFaceSet()
            faces.coordIndex.setValues(0, len(index), index)
            dark.addChild(coords)
            dark.addChild(faces)
        sep.addChild(dark)
    return sep


# -- Object Visibility ----------------------------------------------------------------------------
def kind_of(obj):
    """The Object Visibility kind of an object, or ''."""
    try:
        type_id = obj.TypeId
        sf = getattr(obj, "SciForgeType", "") or ""
    except Exception:
        return ""
    if sf.endswith("Analysis"):
        return "Analysis"
    if sf in ("Joint", "AsBuiltJoint", "RigidGroup"):
        return "Joints"
    if sf == "JointOrigin":
        return "Joint Origins"
    if type_id in ("App::Origin", "App::Plane", "App::Line", "App::Point") or getattr(
        obj, "Role", None
    ) in ("Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane"):
        return "Origins"
    if type_id == "Sketcher::SketchObject":
        return "Sketches"
    if type_id in ("PartDesign::Plane", "Part::DatumPlane"):
        return "Construction Planes"
    if type_id in ("PartDesign::Line", "Part::DatumLine"):
        return "Construction Axes"
    if type_id in ("PartDesign::Point", "Part::DatumPoint"):
        return "Construction Points"
    if type_id == "Image::ImagePlane":
        return "Canvases"
    if type_id == "Mesh::Feature":
        return "Mesh Bodies"
    return ""


def kind_shown(kind):
    return kind not in _STATE["hidden"]


def analysis_shown():
    return kind_shown("Analysis")


def _in_edit(obj):
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument else None
        return edit is not None and edit.Object is obj
    except Exception:
        return False


def apply_visibility(doc):
    """Hide the switched-off kinds of `doc` in the display (and from clicks)."""
    from pivy import coin

    for obj in doc.Objects:
        key = (doc.Name, obj.Name)
        kind = kind_of(obj)
        hide = bool(kind) and not kind_shown(kind) and _STATE["on"] and not _in_edit(obj)
        held = _STATE["hides"].get(key)
        if hide and held is None:
            try:
                root = obj.ViewObject.RootNode
            except Exception:
                continue
            style = coin.SoDrawStyle()
            style.setName(HIDE_NAME)
            style.style = coin.SoDrawStyle.INVISIBLE
            style.setOverride(True)
            pick = coin.SoPickStyle()
            pick.setName(HIDE_NAME)
            pick.style = coin.SoPickStyle.UNPICKABLE
            pick.setOverride(True)
            for node in (pick, style):
                node.ref()
                root.insertChild(node, 0)
            _STATE["hides"][key] = [root, style, pick]
            root.ref()
        elif not hide and held is not None:
            _unhide(key)
    for key in [k for k in _STATE["hides"] if k[0] == doc.Name]:
        if doc.getObject(key[1]) is None:
            _unhide(key)


def _unhide(key):
    held = _STATE["hides"].pop(key, None)
    if not held:
        return
    root, nodes = held[0], held[1:]
    for node in nodes:
        try:
            index = root.findChild(node)
            if index >= 0:
                root.removeChild(index)
        except Exception:
            pass
        node.unref()
    root.unref()


def set_kind(kind, shown):
    if shown:
        _STATE["hidden"].discard(kind)
    else:
        _STATE["hidden"].add(kind)
    log("object visibility: %s %s" % (kind, "shown" if shown else "hidden"))
    _visibility_changed()


def _visibility_changed():
    for name in App.listDocuments():
        try:
            doc = App.getDocument(name)
            apply_visibility(doc)
            from . import surface_analysis_ui as ui

            ui.schedule(doc)
        except Exception as exc:
            warn("object visibility: %s" % exc)
    _redraw()


def all_shown():
    return not _STATE["hidden"]


def toggle_all():
    _STATE["hidden"] = set() if _STATE["hidden"] else set(KINDS)
    log("object visibility: %s" % ("all shown" if not _STATE["hidden"] else "all hidden"))
    _visibility_changed()


def _redraw():
    for view in views():
        try:
            view.redraw()
        except Exception:
            continue


# -- the camera ---------------------------------------------------------------------------------
def _camera_timer():
    want = _STATE["on"] and get("Camera") == "Perspective with Ortho Faces"
    timer = _STATE["camera_timer"]
    if want and timer is None:
        timer = QtCore.QTimer()
        timer.setInterval(150)
        timer.timeout.connect(_camera_tick)
        timer.start()
        _STATE["camera_timer"] = timer
    elif not want and timer is not None:
        timer.stop()
        _STATE["camera_timer"] = None


def _camera_tick():
    try:
        for view in views():
            want = (
                "Orthographic" if nav_core.wants_ortho(view.getViewDirection()) else "Perspective"
            )
            if view.getCameraType() != want:
                view.setCameraType(want)
    except Exception as exc:
        warn("camera: %s" % exc)
        timer, _STATE["camera_timer"] = _STATE["camera_timer"], None
        if timer is not None:
            timer.stop()


def set_camera(name):
    put("Camera", name)
    log("camera: %s" % name)
    apply_all()


# -- watching designs ---------------------------------------------------------------------------
class _Watch:
    def slotRecomputedDocument(self, doc):
        schedule(doc)

    def slotCreatedObject(self, obj):
        try:
            schedule(obj.Document)
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        try:
            if prop in ("Visibility", "Placement"):
                schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            _forget(doc.Name)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        schedule(doc)

    def slotRedoDocument(self, doc):
        schedule(doc)


def _area_changed(*_):
    if _STATE["on"]:
        QtCore.QTimer.singleShot(0, apply_all)


def enable():
    """SciForge's interface is on: the remembered display settings on every view."""
    _STATE["on"] = True
    try:
        if _STATE["observer"] is None:
            _STATE["observer"] = _Watch()
            App.addDocumentObserver(_STATE["observer"])
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if area is not None and _STATE["area"] is None:
            area.subWindowActivated.connect(_area_changed)
            _STATE["area"] = area
    except Exception as exc:
        warn("display settings: %s" % exc)
    apply_all()


def disable():
    """Off: FreeCAD's own look again (As Is, its background) and nothing extra drawn."""
    _STATE["on"] = False
    _camera_timer()
    for name in list(_STATE["nodes"]):
        _detach(name)
    for key in list(_STATE["hides"]):
        _unhide(key)
    for view in views():
        try:
            view.getViewer().setOverrideMode("As Is")
        except Exception:
            continue


# -- the Ground Plane Offset slider ----------------------------------------------------------------
class OffsetPopup(QtWidgets.QFrame):
    """A small slider under the navigation bar, like Fusion's: how far below the model the
    ground (shadow, floor) lies, 0 .. 100 % of the model's size."""

    def __init__(self):
        super().__init__(Gui.getMainWindow(), QtCore.Qt.Popup)
        self.setObjectName("SciForgeGroundOffset")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.addWidget(QtWidgets.QLabel("Ground Plane Offset"))
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setObjectName("SciForgeGroundOffset_slider")
        self.slider.setRange(0, 100)
        self.slider.setValue(int(get("GroundOffset")))
        self.slider.setMinimumWidth(160)
        self.value = QtWidgets.QLabel("%d %%" % int(get("GroundOffset")))
        self.slider.valueChanged.connect(self._moved)
        row.addWidget(self.slider)
        row.addWidget(self.value)

    def _moved(self, value):
        try:
            put("GroundOffset", int(value))
            self.value.setText("%d %%" % int(value))
            for name in App.listDocuments():
                schedule(App.getDocument(name))
        except Exception as exc:
            warn("ground plane offset: %s" % exc)


_POPUP = {"widget": None}


def show_offset():
    popup = OffsetPopup()
    _POPUP["widget"] = popup
    try:
        from . import navbar_ui

        bar = navbar_ui.bar()
        if bar is not None:
            pos = bar.mapToGlobal(QtCore.QPoint(0, 0))
            popup.adjustSize()
            popup.move(pos.x() + bar.width() - popup.width(), pos.y() - popup.height() - 6)
    except Exception:
        pass
    popup.show()
    return popup


# -- commands -------------------------------------------------------------------------------------
def _style_checked(name):
    return lambda: get("VisualStyle") == name


def _env_checked(name):
    return lambda: get("Environment") == name


def _camera_checked(name):
    return lambda: get("Camera") == name


def _kind_checked(kind):
    return lambda: kind_shown(kind)


is_shaded = _style_checked("Shaded")
is_shaded_hidden = _style_checked("Shaded with Hidden Edges")
is_shaded_visible = _style_checked("Shaded with Visible Edges Only")
is_wireframe = _style_checked("Wireframe")
is_wireframe_hidden = _style_checked("Wireframe with Hidden Edges")
is_wireframe_visible = _style_checked("Wireframe with Visible Edges Only")
is_env_theme = _env_checked("Theme")
is_env_photo_booth = _env_checked("Photo Booth")
is_env_grey_room = _env_checked("Grey Room")
is_env_dark_sky = _env_checked("Dark Sky")
is_env_infinity_pool = _env_checked("Infinity Pool")
is_env_tranquility_blue = _env_checked("Tranquility Blue")
is_env_warm_light = _env_checked("Warm Light")
is_orthographic = _camera_checked("Orthographic")
is_perspective = _camera_checked("Perspective")
is_ortho_faces = _camera_checked("Perspective with Ortho Faces")
shows_origins = _kind_checked("Origins")
shows_analysis = _kind_checked("Analysis")
shows_joints = _kind_checked("Joints")
shows_joint_origins = _kind_checked("Joint Origins")
shows_sketches = _kind_checked("Sketches")
shows_planes = _kind_checked("Construction Planes")
shows_axes = _kind_checked("Construction Axes")
shows_points = _kind_checked("Construction Points")
shows_canvases = _kind_checked("Canvases")
shows_meshes = _kind_checked("Mesh Bodies")


def ground_shadow_on():
    return get("GroundShadow")


def ground_plane_on():
    return get("GroundPlane")


def _command(text, tip, icon, run):
    class Command:
        def GetResources(self):
            return {"MenuText": text, "ToolTip": tip, "Pixmap": ui_icon_path(icon)}

        def IsActive(self):
            return True

        def Activated(self):
            try:
                run()
            except Exception as exc:
                warn("%s: %s" % (text, exc))

    return Command


def _set_style(name):
    def run():
        put("VisualStyle", name)
        log("visual style: %s" % name)
        apply_all()

    return _command(name, "Visual style: %s" % name, "nav_display", run)


def _set_env(name):
    def run():
        put("Environment", name)
        log("environment: %s" % name)
        apply_all()

    return _command(name, "Environment: %s (the 3D view's background)" % name, "nav_display", run)


def _set_cam(name):
    return _command(name, "Camera: %s" % name, "nav_display", lambda: set_camera(name))


def _toggle_kind(kind):
    return _command(
        kind,
        "Show or hide every %s in the 3D view" % kind.lower(),
        "nav_display",
        lambda: set_kind(kind, not kind_shown(kind)),
    )


def _toggle_pref(name, text):
    def run():
        put(name, not get(name))
        log("%s %s" % (text.lower(), "on" if get(name) else "off"))
        apply_all()

    return _command(text, text, "nav_display", run)


COMMANDS = {
    "SciForge_StyleShaded": _set_style("Shaded"),
    "SciForge_StyleShadedHidden": _set_style("Shaded with Hidden Edges"),
    "SciForge_StyleShadedVisible": _set_style("Shaded with Visible Edges Only"),
    "SciForge_StyleWireframe": _set_style("Wireframe"),
    "SciForge_StyleWireframeHidden": _set_style("Wireframe with Hidden Edges"),
    "SciForge_StyleWireframeVisible": _set_style("Wireframe with Visible Edges Only"),
    "SciForge_EnvTheme": _set_env("Theme"),
    "SciForge_EnvPhotoBooth": _set_env("Photo Booth"),
    "SciForge_EnvGreyRoom": _set_env("Grey Room"),
    "SciForge_EnvDarkSky": _set_env("Dark Sky"),
    "SciForge_EnvInfinityPool": _set_env("Infinity Pool"),
    "SciForge_EnvTranquilityBlue": _set_env("Tranquility Blue"),
    "SciForge_EnvWarmLight": _set_env("Warm Light"),
    "SciForge_GroundShadow": _toggle_pref("GroundShadow", "Ground Shadow"),
    "SciForge_GroundPlane": _toggle_pref("GroundPlane", "Ground Plane"),
    "SciForge_GroundPlaneOffset": _command(
        "Ground Plane Offset",
        "How far below the model the ground lies",
        "nav_display",
        show_offset,
    ),
    "SciForge_ShowAllObjects": _command(
        "Show All", "Show or hide every kind of object", "nav_display", toggle_all
    ),
    "SciForge_ShowOrigins": _toggle_kind("Origins"),
    "SciForge_ShowAnalysis": _toggle_kind("Analysis"),
    "SciForge_ShowJoints": _toggle_kind("Joints"),
    "SciForge_ShowJointOrigins": _toggle_kind("Joint Origins"),
    "SciForge_ShowSketches": _toggle_kind("Sketches"),
    "SciForge_ShowConstructionPlanes": _toggle_kind("Construction Planes"),
    "SciForge_ShowConstructionAxes": _toggle_kind("Construction Axes"),
    "SciForge_ShowConstructionPoints": _toggle_kind("Construction Points"),
    "SciForge_ShowCanvases": _toggle_kind("Canvases"),
    "SciForge_ShowMeshBodies": _toggle_kind("Mesh Bodies"),
    "SciForge_CameraOrthographic": _set_cam("Orthographic"),
    "SciForge_CameraPerspective": _set_cam("Perspective"),
    "SciForge_CameraOrthoFaces": _set_cam("Perspective with Ortho Faces"),
}
