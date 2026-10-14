# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Zebra, Draft, Curvature Comb, Curvature Map, Isocurve, Accessibility and Minimum
Radius Analysis, Fusion-style.

Each command opens a dialog: click the bodies (or faces, or edges) to analyse, set the
options, and the analysis shows on the model at once: stripes, colours or combs drawn over
the model's own faces. OK keeps it in the browser's Analysis folder: its eye shows or hides
it, double-click (or right-click > Edit) opens the dialog again, Delete removes it, and it is
saved with the design. Cancel / Esc leave nothing. The model itself never changes: hiding
an analysis shows the model exactly as before.

How it is drawn: each analysis' view provider holds its own Coin nodes, in the coordinates
of the bodies it looks at. Coloured analyses lie on the model's own display triangles (made
finer, never moved) a hair in front of them (polygon offset): the model's edges stay on
top. Zebra stripes are a texture whose coordinates come from what each point reflects
(analysis_core.zebra_parameter); while the camera moves they are worked out again (a timer
looks at the camera), unless Lock Stripes is on. Everything is drawn again a moment after
the design changes (recompute, undo, a body shown or hidden).
"""

import functools

import FreeCAD as App
import FreeCADGui as Gui

from . import analysis_core as core
from . import bodypick, commands, construct, hole_common, log, pickpanel, preview, warn
from . import surface_analysis as sa
from . import ui_icon_path
from .compat import QtCore, QtWidgets
from .taskui import DistanceField

STRIPE_TEXELS = 64


# -- keeping the drawings in step with the design ---------------------------------------------
_PENDING = {"docs": set(), "armed": False}


def schedule(doc, delay=60):
    try:
        _PENDING["docs"].add(doc.Name)
    except Exception:
        return
    if not _PENDING["armed"]:
        _PENDING["armed"] = True
        QtCore.QTimer.singleShot(delay, _run)


def _run():
    _PENDING["armed"] = False
    names, _PENDING["docs"] = _PENDING["docs"], set()
    for name in names:
        try:
            doc = App.getDocument(name)
        except Exception:
            continue
        try:
            if doc.Recomputing:
                schedule(doc, 150)
                continue
        except Exception:
            pass
        try:
            refresh(doc)
        except Exception as exc:
            warn("analysis display: %s" % exc)


def refresh(doc):
    """Draw every analysis of `doc` again (what did not change comes from a cache)."""
    if not App.GuiUp or Gui.getDocument(doc.Name) is None:
        return
    for obj in sa.analyses(doc):
        proxy = _proxy(obj)
        if proxy is not None:
            try:
                proxy.redraw(obj)
            except Exception as exc:
                warn("%s: %s" % (obj.Label, exc))
    tracker().update()
    try:
        cover(doc)
        from . import display_ui

        if display_ui.fill_owners(doc) or display_ui.filling():
            display_ui.schedule(doc)  # a hidden-line style leaves the analysed bodies alone
    except Exception as exc:
        warn("analysis display: %s" % exc)
    redraw_views(doc)


def redraw_views(doc):
    """Ask every 3D view of `doc` to draw again (a change inside a view provider's own Coin
    nodes did not always reach the screen until the next mouse move)."""
    try:
        gui = Gui.getDocument(doc.Name)
        for view in gui.mdiViewsOfType("Gui::View3DInventor") if gui is not None else []:
            try:
                view.redraw()
            except Exception:
                continue
    except Exception:
        pass


def _proxy(obj):
    try:
        proxy = obj.ViewObject.Proxy if obj.ViewObject is not None else None
    except Exception:
        return None
    return proxy if isinstance(proxy, ViewProviderSurfaceAnalysis) else None


class _DocWatch:
    """What can change an analysis' drawing: a recompute (the model changed), a body shown
    or hidden, undo / redo, an analysis or a body deleted."""

    def slotRecomputedDocument(self, doc):
        if sa.analyses(doc):
            schedule(doc)

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Visibility" and obj.Document is not None and sa.analyses(obj.Document):
                schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            if sa.analyses(obj.Document):
                schedule(obj.Document)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        schedule(doc)

    def slotRedoDocument(self, doc):
        schedule(doc)

    def slotDeletedDocument(self, doc):
        try:
            uncover_document(doc.Name)
        except Exception:
            pass


_WATCH = {"observer": None}


def ensure_watch():
    if _WATCH["observer"] is None:
        try:
            _WATCH["observer"] = _DocWatch()
            App.addDocumentObserver(_WATCH["observer"])
        except Exception as exc:
            _WATCH["observer"] = None
            warn("analysis display: %s" % exc)


# -- the camera, for the zebra stripes --------------------------------------------------------
def camera_of(view):
    """(view direction, right, up, height of the view in mm) of a 3D view, global."""
    rot = view.getCameraOrientation()
    d = rot.multVec(App.Vector(0, 0, -1))
    r = rot.multVec(App.Vector(1, 0, 0))
    u = rot.multVec(App.Vector(0, 1, 0))
    height = 100.0
    try:
        cam = view.getCameraNode()
        if hasattr(cam, "height"):
            height = float(cam.height.getValue())
        else:
            import math

            angle = float(cam.heightAngle.getValue())
            height = 2.0 * float(cam.focalDistance.getValue()) * math.tan(angle / 2.0)
    except Exception:
        pass
    return d, r, u, max(1e-6, height)


def _signature(view):
    try:
        d, r, u, height = camera_of(view)
        pos = view.getCameraNode().position.getValue()
        return tuple(round(x, 6) for x in (d.x, d.y, d.z, u.x, u.y, u.z, height)) + tuple(
            round(float(c), 4) for c in pos
        )
    except Exception:
        return None


class _Tracker:
    """Unlocked zebra stripes follow the camera: a timer looks at the active view's camera
    (Coin sensors would call Python without the interpreter lock, see the feature guide)."""

    def __init__(self):
        self.timer = None
        self.last = None

    def update(self):
        want = False
        try:
            doc = App.ActiveDocument
            if doc is not None:
                want = any(_following(o) for o in sa.analyses(doc, sa.ZEBRA))
        except Exception:
            want = False
        if want and self.timer is None:
            self.timer = QtCore.QTimer()
            self.timer.setInterval(90)
            self.timer.timeout.connect(self._tick)
            self.timer.start()
        elif not want and self.timer is not None:
            self.timer.stop()
            self.timer = None
            self.last = None

    def _tick(self):
        try:
            doc = App.ActiveDocument
            gui = Gui.ActiveDocument
            if doc is None or gui is None:
                return
            view = gui.ActiveView
            if not hasattr(view, "getCameraOrientation"):
                return
            sig = _signature(view)
            if sig is None or sig == self.last:
                return
            self.last = sig
            for obj in sa.analyses(doc, sa.ZEBRA):
                if _following(obj):
                    proxy = _proxy(obj)
                    if proxy is not None:
                        proxy.restripe(obj, view)
        except Exception as exc:
            warn("zebra stripes: %s" % exc)
            self.update()


def _following(obj):
    try:
        return (
            obj.ViewObject is not None
            and obj.ViewObject.Visibility
            and not obj.LockStripes
            and not obj.Problem
        )
    except Exception:
        return False


_TRACKER = {"tracker": None}


def tracker():
    if _TRACKER["tracker"] is None:
        _TRACKER["tracker"] = _Tracker()
    return _TRACKER["tracker"]


def active_view():
    try:
        view = Gui.ActiveDocument.ActiveView
        return view if hasattr(view, "getCameraOrientation") else None
    except Exception:
        return None


def lock_view(obj, view=None):
    """Remember the camera the stripes of a zebra analysis stay in (Lock Stripes)."""
    view = view or active_view()
    if view is None:
        return
    d, r, u, height = camera_of(view)
    obj.LockedView = App.Placement(App.Vector(), view.getCameraOrientation())
    obj.LockedHeight = height


# -- the view provider ---------------------------------------------------------------------------
def _vec(v):
    return (float(v[0]), float(v[1]), float(v[2]))


def _rel(rotation, v):
    """A global direction in the coordinates of a body inside a component (`rotation` is the
    component's global rotation)."""
    w = rotation.inverted().multVec(App.Vector(*v))
    return (w.x, w.y, w.z)


def group_for(coin, owner, frame=None):
    group = coin.SoSeparator()
    frame = frame if frame is not None else sa.parent_placement(owner)
    if not frame.isIdentity():
        transform = coin.SoTransform()
        transform.translation.setValue(*_vec(frame.Base))
        q = frame.Rotation.Q
        transform.rotation.setValue(q[0], q[1], q[2], q[3])
        group.addChild(transform)
    return group


def surface_nodes(coin, group, m, alpha=0.0):
    """Shape hints, the polygon offset and the faces of Mesh `m`: the analysis lies on the
    model's own triangles (whose faces are switched off under it, see cover()) with the
    same polygon offset as they have, so the model's edges stay on top."""
    hints = coin.SoShapeHints()
    hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
    hints.shapeType = coin.SoShapeHints.UNKNOWN_SHAPE_TYPE
    offset = coin.SoPolygonOffset()  # like the model's own faces: its edges stay on top
    offset.factor.setValue(1.0)
    offset.units.setValue(1.0)
    group.addChild(hints)
    group.addChild(offset)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(m.points), m.points)
    normals = coin.SoNormal()
    normals.vector.setValues(0, len(m.normals), m.normals)
    binding = coin.SoNormalBinding()
    binding.value = coin.SoNormalBinding.PER_VERTEX_INDEXED
    group.addChild(coords)
    group.addChild(normals)
    group.addChild(binding)
    index = []
    for a, b, c in m.triangles:
        index += [a, b, c, -1]
    faces = coin.SoIndexedFaceSet()
    faces.coordIndex.setValues(0, len(index), index)
    faces.normalIndex.setValues(0, len(index), index)
    return faces, index


def colored_into(coin, group, m, colors, alpha=0.0):
    """Faces of Mesh `m` in per-point colours (lit like the model), in `group`."""
    material = coin.SoMaterial()
    material.diffuseColor.setValues(0, len(colors), colors)
    material.ambientColor.setValue(0.25, 0.25, 0.25)
    material.emissiveColor.setValue(0.18, 0.18, 0.18)
    material.specularColor.setValue(0.1, 0.1, 0.1)
    material.transparency.setValue(alpha)
    bind = coin.SoMaterialBinding()
    bind.value = coin.SoMaterialBinding.PER_VERTEX_INDEXED
    group.addChild(material)
    group.addChild(bind)
    faces, index = surface_nodes(coin, group, m, alpha)
    faces.materialIndex.setValues(0, len(index), index)
    group.addChild(faces)


def model_color(owner):
    """The colour the model of `owner` is drawn in (its displayed step's)."""
    shown = owner.Tip if owner.TypeId == "PartDesign::Body" and owner.Tip else owner
    for obj in (shown, owner):
        try:
            return tuple(float(c) for c in obj.ViewObject.ShapeColor)[:3]
        except Exception:
            continue
    return (0.8, 0.8, 0.8)


# -- the model's own faces under an analysis -----------------------------------------------------
# A shaded analysis covers the faces of its bodies completely: the model's faces underneath
# are switched off (their "FaceStyle" draw style set to invisible: FreeCAD's own node, only
# in the display, never in the design) so they cannot shine through, and come back as soon
# as no shown analysis covers them. The model's edges stay. Opacity below 100 % mixes the
# model's colour into the analysis instead of letting the faces show through.
SHADED = (sa.ZEBRA, sa.DRAFT, sa.CURVATURE_MAP, sa.ACCESSIBILITY, sa.MIN_RADIUS)
_FACES = {"held": {}}  # (document, object) -> [(node, old style)]


def _face_styles(obj):
    from pivy import coin

    try:
        root = obj.ViewObject.RootNode
    except Exception:
        return []
    found = []
    for node in pickpanel.nodes(root, "SoDrawStyle"):
        try:
            if node.getName().getString() == "FaceStyle":
                found.append(node)
        except Exception:
            continue
    _ = coin
    return found


def _displays(owner):
    """The objects whose display shows `owner`'s solid (a body's steps, or the solid)."""
    if owner.TypeId != "PartDesign::Body":
        return [owner]
    found = []
    for obj in owner.Group:
        try:
            if obj.isDerivedFrom("PartDesign::Feature"):
                found.append(obj)
        except Exception:
            continue
    return found


def analysed_owners(doc):
    """Names of the bodies a shown shaded analysis of `doc` covers."""
    try:
        from . import display_ui

        if not display_ui.analysis_shown():  # Object Visibility > Analysis off
            return set()
    except Exception:
        pass
    found = set()
    for obj in sa.analyses(doc):
        if obj.SciForgeType not in SHADED:
            continue
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility or obj.Problem:
                continue
        except Exception:
            continue
        for owner, _names in sa.targets(obj):
            found.add(owner.Name)
    return found


def cover(doc):
    """Model faces off under every shown shaded analysis of `doc` (and under the component
    colours and a hidden-line visual style), back on elsewhere."""
    from pivy import coin

    owners = set(analysed_owners(doc))
    try:
        from . import component_colors_ui, display_ui

        if component_colors_ui.is_on(doc):
            owners |= {o.Name for o in component_colors_ui.owners(doc)}
        owners |= {o.Name for o in display_ui.fill_owners(doc)}
    except Exception as exc:
        warn("display: %s" % exc)
    wanted = set()
    for name in owners:
        owner = doc.getObject(name)
        if owner is None:
            continue
        for shown in _displays(owner):
            wanted.add((doc.Name, shown.Name))
    held = _FACES["held"]
    for key in list(held):
        if key[0] == doc.Name and key not in wanted:
            _restore(key)
    for key in wanted:
        if key in held:
            continue
        shown = doc.getObject(key[1])
        nodes = _face_styles(shown) if shown is not None else []
        saved = []
        for node in nodes:
            node.ref()
            saved.append((node, node.style.getValue()))
            node.style.setValue(coin.SoDrawStyle.INVISIBLE)
        held[key] = saved


def _restore(key):
    # backwards: a node met twice (FreeCAD's face node sits in two display modes) was saved
    # the second time already switched off
    for node, old in reversed(_FACES["held"].pop(key, [])):
        try:
            node.style.setValue(old)
        except Exception:
            pass
        node.unref()


def uncover_document(name):
    for key in [k for k in _FACES["held"] if k[0] == name]:
        _restore(key)


class ViewProviderSurfaceAnalysis:
    """Draws one surface analysis. Saved documents store
    "sciforge.surface_analysis_ui.ViewProviderSurfaceAnalysis": keep the name stable."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.content = coin.SoSeparator()
        self.root.addChild(self.content)
        vobj.addDisplayMode(self.root, "Analysis")
        self.cache = {}
        self.stripes = []  # [(owner name, Mesh, rotation, texcoord node)] of a zebra
        ensure_watch()
        try:
            schedule(vobj.Object.Document)
        except Exception:
            pass

    def getDisplayModes(self, vobj):
        return ["Analysis"]

    def getDefaultDisplayMode(self):
        return "Analysis"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop not in ("Label", "Problem", "PullVector", "LockedView", "LockedHeight"):
            try:
                schedule(obj.Document)
            except Exception:
                pass
        elif prop in ("Problem", "PullVector"):
            schedule(obj.Document)

    def onChanged(self, vobj, prop):
        if prop == "Visibility":
            try:
                schedule(vobj.Object.Document)
            except Exception:
                pass

    def getIcon(self):
        try:
            return ui_icon_path(sa.icon(self.Object.SciForgeType))
        except Exception:
            return ui_icon_path("zebra")

    def doubleClicked(self, vobj):
        obj = vobj.Object
        QtCore.QTimer.singleShot(0, lambda: edit(obj))
        return True

    def onDelete(self, vobj, subelements):
        try:
            schedule(vobj.Object.Document)
        except Exception:
            pass
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads

    # -- drawing ---------------------------------------------------------------------------
    def _mesh(self, owner, names, quality, curvature):
        """The analysed faces' Mesh, from the cache while the body's shape is the same."""
        try:
            key = (owner.Name, tuple(names), bool(quality), bool(curvature))
            stamp = (owner.Shape.hashCode(), sa.display_tolerance(owner))
        except Exception:
            return sa.Mesh()
        found = self.cache.get(key)
        if found is not None and found[0] == stamp:
            return found[1]
        m = sa.mesh(owner, names, quality, curvature)
        self.cache[key] = (stamp, m)
        return m

    def redraw(self, obj):
        content = getattr(self, "content", None)
        if content is None:
            return
        content.removeAllChildren()
        self.stripes = []
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility:
                return
        except Exception:
            return
        if obj.Problem:
            return
        kind = obj.SciForgeType
        entries = sa.targets(obj)
        if not entries:
            return
        from pivy import coin

        if kind in (sa.COMB, sa.ISOCURVE):
            data = sa.comb_data(obj) if kind == sa.COMB else sa.iso_data(obj)
            for owner, curves in data:
                group = group_for(coin, owner)
                self._curves(coin, group, curves, kind == sa.ISOCURVE)
                content.addChild(group)
            return
        need_curvature = kind in (sa.CURVATURE_MAP, sa.MIN_RADIUS)
        quality = bool(getattr(obj, "HighQuality", False))
        opacity = core.clamp(int(getattr(obj, "Opacity", 100)), 0, 100) / 100.0
        view = active_view()
        for owner, names in entries:
            m = self._mesh(owner, names, quality, need_curvature)
            if not m.triangles:
                continue
            frame = sa.parent_placement(owner)
            group = group_for(coin, owner, frame)
            base = model_color(owner)
            if kind == sa.ZEBRA:
                node = self._zebra(coin, group, m, base, opacity)
                self.stripes.append((owner.Name, m, frame.Rotation, node))
            else:
                colors = self._colors(obj, kind, owner, m, frame)
                colors = [core.mix(base, c, opacity) for c in colors]
                colored_into(coin, group, m, colors)
            content.addChild(group)
        if kind == sa.ZEBRA:
            self.restripe(obj, view)

    def _colors(self, obj, kind, owner, m, frame):
        vector = obj.PullVector if "PullVector" in obj.PropertiesList else None
        if vector is None or vector.Length < 1e-9:
            vector = App.Vector(0, 0, 1)
        if kind == sa.DRAFT:
            pull = _rel(frame.Rotation, _vec(vector))
            return sa.draft_colors(obj, m.normals, pull)
        if kind == sa.CURVATURE_MAP:
            size = max(1e-6, owner.Shape.BoundBox.DiagonalLength)
            return sa.map_colors(obj, m, size)
        if kind == sa.MIN_RADIUS:
            return sa.radius_colors(obj, m)
        if kind == sa.ACCESSIBILITY:
            pull = _rel(frame.Rotation, _vec(vector))
            return sa.access_colors(obj, m, owner, pull)
        return [core.NEUTRAL] * len(m.points)

    def _zebra(self, coin, group, m, base, opacity):
        """Stripes: the texture blends between the dark stripe colour (the material) and
        the light one (the blend colour); below 100 % opacity both lean to the model's."""
        light = coin.SoLightModel()
        light.model = coin.SoLightModel.BASE_COLOR
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*core.mix(base, (0.0, 0.0, 0.0), opacity))
        texture = coin.SoTexture2()
        half = STRIPE_TEXELS // 2
        data = bytes([255] * half + [0] * half) * 2
        texture.image.setValue(coin.SbVec2s(STRIPE_TEXELS, 2), 1, data)
        texture.model = coin.SoTexture2.BLEND
        texture.blendColor.setValue(*core.mix(base, (1.0, 1.0, 1.0), opacity))
        texture.wrapS = coin.SoTexture2.REPEAT
        texture.wrapT = coin.SoTexture2.REPEAT
        group.addChild(light)
        group.addChild(material)
        group.addChild(texture)
        texcoords = coin.SoTextureCoordinate2()
        texcoords.point.setValues(0, len(m.points), [(0.5, 0.5)] * len(m.points))
        tbind = coin.SoTextureCoordinateBinding()
        tbind.value = coin.SoTextureCoordinateBinding.PER_VERTEX_INDEXED
        group.addChild(texcoords)
        group.addChild(tbind)
        faces, index = surface_nodes(coin, group, m)
        faces.textureCoordIndex.setValues(0, len(index), index)
        group.addChild(faces)
        return texcoords

    def restripe(self, obj, view=None):
        """Work the zebra stripes out again for the camera (or the locked one)."""
        if not self.stripes:
            return
        if obj.LockStripes and obj.LockedHeight > 0:
            rot = obj.LockedView.Rotation
            d = rot.multVec(App.Vector(0, 0, -1))
            r = rot.multVec(App.Vector(1, 0, 0))
            u = rot.multVec(App.Vector(0, 1, 0))
            height = float(obj.LockedHeight)
        else:
            view = view or active_view()
            if view is None:
                return
            d, r, u, height = camera_of(view)
        box = None
        for name, m, rotation, _node in self.stripes:
            owner = obj.Document.getObject(name)
            if owner is None:
                continue
            frame = sa.parent_placement(owner)
            b = owner.Shape.BoundBox
            if not frame.isIdentity():
                b = owner.Shape.transformed(frame.toMatrix()).BoundBox
            box = b if box is None else box.united(b)
        if box is None:
            return
        centre_g = box.Center
        radius = max(0.75 * box.DiagonalLength, 0.9 * height)
        repeats = int(core.clamp(int(obj.Repeats), 1, 100))
        vertical = obj.Direction == "Vertical"
        for name, m, rotation, node in self.stripes:
            owner = obj.Document.getObject(name)
            frame = sa.parent_placement(owner) if owner is not None else App.Placement()
            local_centre = frame.inverse().multVec(centre_g)
            values = core.zebra_parameters(
                m.points,
                m.normals,
                _rel(rotation, _vec(d)),
                _rel(rotation, _vec(r)),
                _rel(rotation, _vec(u)),
                _vec(local_centre),
                radius,
                vertical,
            )
            points = [(v * repeats, 0.5) for v in values]
            node.point.setValues(0, len(points), points)

    def _curves(self, coin, group, curves, isocurves):
        light = coin.SoLightModel()
        light.model = coin.SoLightModel.BASE_COLOR
        group.addChild(light)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(1.5)
        group.addChild(style)
        for curve in curves:
            if isocurves and curve["base"]:
                self._polyline(coin, group, curve["base"], (0.95, 0.75, 0.25))
            teeth = curve["teeth"]
            if not teeth:
                continue
            points = []
            colors = []
            for point, tip, color in teeth:
                points += [point, tip]
                colors += [color, color]
            sep = coin.SoSeparator()
            material = coin.SoMaterial()
            material.diffuseColor.setValues(0, len(colors), colors)
            bind = coin.SoMaterialBinding()
            bind.value = coin.SoMaterialBinding.PER_VERTEX
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(points), points)
            lines = coin.SoLineSet()
            lines.numVertices.setValues(0, len(teeth), [2] * len(teeth))
            for node in (material, bind, coords, lines):
                sep.addChild(node)
            group.addChild(sep)
            self._polyline(coin, group, curve["tips"], (0.92, 0.92, 0.92))

    def _polyline(self, coin, group, points, color):
        if len(points) < 2:
            return
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        line = coin.SoLineSet()
        line.numVertices.setValue(len(points))
        for node in (material, coords, line):
            sep.addChild(node)
        group.addChild(sep)


def make_view(obj):
    if App.GuiUp and obj.ViewObject is not None:
        ViewProviderSurfaceAnalysis(obj.ViewObject)


# -- the dialog ---------------------------------------------------------------------------------
def _safe(method):
    @functools.wraps(method)
    def wrapper(self, *args):
        try:
            return method(self, *args)
        except (sa.AnalysisError, construct.ConstructError) as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            try:
                self.say("⚠ %s" % exc)
            except Exception:
                pass
        return None

    return wrapper


LABELS = {
    "Direction": "Direction",
    "Repeats": "Repeats",
    "Opacity": "Opacity",
    "LockStripes": "Lock Stripes",
    "HighQuality": "High Quality",
    "DraftStart": "Draft Angle start",
    "DraftStop": "Draft Angle stop",
    "ToleranceZone": "Tolerance Zone",
    "Density": "Density",
    "CombScale": "Scale",
    "MapType": "Type",
    "MapDisplay": "Display",
    "MapScale": "Scale",
    "LimitRadius": "Maximum Limit",
    "IsoType": "Type",
    "IsoCount": "Isocurves",
    "ShowCombs": "Curvature Combs",
    "AccessMode": "Access",
    "MinimumRadius": "Minimum Radius",
    "ToolRadius": "Maximum Tool Radius",
}
# (property, kind of widget, extra) in the dialog's order, after the selection boxes
FIELDS = {
    sa.ZEBRA: [
        ("Direction", "combo", sa.ZEBRA_DIRECTIONS),
        ("Repeats", "int", (1, 100)),
        ("Opacity", "slider", (0, 100)),
        ("LockStripes", "check", None),
        ("HighQuality", "check", None),
    ],
    sa.DRAFT: [
        ("DraftStart", "angle", None),
        ("DraftStop", "angle", None),
        ("ToleranceZone", "check", None),
        ("Opacity", "slider", (0, 100)),
        ("HighQuality", "check", None),
    ],
    sa.COMB: [
        ("Density", "int", (2, 100)),
        ("CombScale", "float", (0.05, 20.0)),
    ],
    sa.CURVATURE_MAP: [
        ("MapType", "combo", core.MAP_TYPES),
        ("MapDisplay", "combo", sa.MAP_DISPLAYS),
        ("MapScale", "float", (0.05, 20.0)),
        ("LimitRadius", "length", None),
        ("Opacity", "slider", (0, 100)),
        ("HighQuality", "check", None),
    ],
    sa.ISOCURVE: [
        ("IsoType", "combo", sa.ISO_TYPES),
        ("IsoCount", "int", (1, 50)),
        ("ShowCombs", "check", None),
        ("Density", "int", (2, 100)),
        ("CombScale", "float", (0.05, 20.0)),
    ],
    sa.ACCESSIBILITY: [
        ("AccessMode", "combo", core.ACCESS_MODES),
        ("Opacity", "slider", (0, 100)),
        ("HighQuality", "check", None),
    ],
    sa.MIN_RADIUS: [
        ("MinimumRadius", "length", None),
        ("ToolRadius", "length", None),
        ("Opacity", "slider", (0, 100)),
        ("HighQuality", "check", None),
    ],
}
DEFAULTS = {}
for _kind, _props in sa.PROPS.items():
    DEFAULTS[_kind] = {}
    for _t, _name, _tip, _default in _props:
        if _name in sa.ENUMS:
            _default = sa.ENUMS[_name][0]
        DEFAULTS[_kind][_name] = _default
WAITING = {
    "bodies": "Click the bodies to analyse.",
    "faces": "Click the faces to analyse.",
    "edges": "Click the edges of a body to analyse.",
}
EMPTY = {"bodies": "Select", "faces": "Select", "edges": "Select"}
BOX = {"bodies": "Bodies", "faces": "Faces", "edges": "Edges"}


def _solid_feature(obj):
    """A step of a body or a loose solid: what a click on a body lands on (not a sketch,
    a construction plane, an analysis...)."""
    try:
        if (
            obj is None
            or construct.is_helper(obj)
            or getattr(obj, "SciForgeType", "").endswith("Analysis")
        ):
            return False
        if obj.TypeId in construct.PLANE_TYPES + construct.LINE_TYPES + construct.POINT_TYPES:
            return False
        if obj.TypeId in construct.SKETCH_TYPES or obj.TypeId == "App::Origin":
            return False
        return obj.isDerivedFrom("Part::Feature") or obj.TypeId == "PartDesign::Body"
    except Exception:
        return False


def _name_on(owner, obj, short):
    """The name element `short` of `obj` (a step of `owner`'s body, usually its Tip) has in
    the body's own shape, or None."""
    if not short:
        return None
    if obj is owner or (owner.TypeId == "PartDesign::Body" and obj is owner.Tip):
        return short
    try:
        item = obj.Shape.getElement(short)
    except Exception:
        return None
    if short.startswith("Face"):
        return pickpanel.match_face(owner, obj, short) if hasattr(owner, "Shape") else None
    if short.startswith("Edge"):
        for i, edge in enumerate(owner.Shape.Edges, start=1):
            try:
                if edge.isSame(item) or (
                    abs(edge.Length - item.Length) < 1e-7 * max(1.0, item.Length)
                    and (edge.CenterOfMass - item.CenterOfMass).Length < 1e-6
                ):
                    return "Edge%d" % i
            except Exception:
                continue
    return None


def _direction_ref(obj, short):
    """(object, element) a direction pick is kept as: a face or edge of a body's Tip is the
    body's (it then follows the body's later steps); None if it gives no direction."""
    obj, short = construct.normalize_pick(obj, short)
    if obj is None or not sa.fits_direction(obj, short):
        return None
    owner = sa.owner_of(obj)
    if owner is not None and short and _name_on(owner, obj, short) == short:
        obj = owner
    return (obj, short)


class _Gate:
    """Only what the blue box can take lights up and can be picked."""

    def __init__(self, panel):
        self.panel = panel

    def allow(self, doc, obj, sub):
        try:
            panel = self.panel
            if panel is None or panel._closed or obj is None:
                return True
            from .construct_ui import _resolve_gate

            leaf, short = _resolve_gate(obj, sub)
            return bool(panel.allow(leaf, short))
        except Exception:
            return False


class AnalysisPanel(bodypick.Tones, pickpanel.PickPanel):
    """The dialog of every surface analysis (FIELDS says which options it has)."""

    last = None

    def __init__(self, doc, kind, analysis=None, initial=()):
        self.kind = kind
        self.title = sa.title(kind)
        self.icon = sa.icon(kind)
        name = ("Edit %s" % analysis.Label) if analysis is not None else self.title
        super().__init__(doc, name)
        AnalysisPanel.last = self
        self.analysis = analysis
        self.editing = analysis is not None
        self.what = sa.picks(kind)
        self.entries = []  # [(owner, [names])]
        self.direction = None  # (obj, sub) or None: +Z
        self.values = dict(DEFAULTS[kind])
        self.active = "targets"
        self.widgets = {}
        if analysis is not None:
            self.entries = [(o, list(n)) for o, n in sa.targets(analysis)]
            self.values.update(sa.read(analysis))
            if sa.has_direction(kind):
                link = analysis.PullDirection
                if link:
                    target, subs = link
                    sub = (subs[0] if isinstance(subs, (list, tuple)) and subs else subs) or ""
                    self.direction = construct.normalize_pick(target, sub)
        else:
            for obj, short, _point in initial:
                if self._fits_target(obj, short):
                    self._toggle_target(obj, short)
        self._build()
        self.start_picking()
        ensure_watch()
        self._show_boxes()
        self._apply_now()

    # -- widgets -------------------------------------------------------------------------
    def _build(self):
        self.box = hole_common.SelectionField(self, "targets", EMPTY[self.what])
        self.box.button.setObjectName("SciForgeAnalysis_targets")
        self.box.clear.setObjectName("SciForgeAnalysis_targets_clear")
        self.layout.addRow(BOX[self.what], self.box.widget)
        self.dir_box = None
        if sa.has_direction(self.kind):
            self.dir_box = hole_common.SelectionField(self, "direction", "Z axis")
            self.dir_box.button.setObjectName("SciForgeAnalysis_direction")
            self.dir_box.button.setToolTip(
                "Click a plane, a flat face, a straight edge or an axis (none: the Z axis)"
            )
            self.dir_box.clear.setObjectName("SciForgeAnalysis_direction_clear")
            self.layout.addRow("Direction", self.dir_box.widget)
            self.flip = QtWidgets.QPushButton("Flip")
            self.flip.setObjectName("SciForgeAnalysis_flip")
            self.flip.setCheckable(True)
            self.flip.setChecked(bool(self.values.get("Flip")))
            self.flip.clicked.connect(self._flipped)
            self.layout.addRow("", self.flip)
        for prop, widget_kind, extra in FIELDS[self.kind]:
            widget = self._widget(prop, widget_kind, extra)
            self.widgets[prop] = (widget_kind, widget)
            holder = widget.widget if isinstance(widget, DistanceField) else widget
            holder.setObjectName("SciForgeAnalysis_" + prop)
            if widget_kind == "check":
                self.layout.addRow(holder)
            else:
                self.layout.addRow(LABELS[prop], holder)
        self._show_fields()
        self.finish_layout()

    def _widget(self, prop, widget_kind, extra):
        value = self.values.get(prop)
        if widget_kind == "combo":
            box = QtWidgets.QComboBox()
            for item in extra:
                box.addItem(item, item)
            index = box.findData(value)
            box.setCurrentIndex(max(0, index))
            box.currentIndexChanged.connect(
                lambda _i, p=prop, b=box: self._changed(p, b.currentData())
            )
            return box
        if widget_kind == "int":
            box = QtWidgets.QSpinBox()
            box.setRange(*extra)
            box.setValue(int(value))
            box.valueChanged.connect(lambda v, p=prop: self._changed(p, int(v)))
            return box
        if widget_kind == "float":
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(*extra)
            box.setDecimals(2)
            box.setSingleStep(0.1)
            box.setValue(float(value))
            box.valueChanged.connect(lambda v, p=prop: self._changed(p, float(v)))
            return box
        if widget_kind == "slider":
            row = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setObjectName("SciForgeAnalysis_%s_slider" % prop)
            slider.setRange(*extra)
            slider.setValue(int(value))
            label = QtWidgets.QLabel("%d %%" % int(value))
            label.setMinimumWidth(40)

            def moved(v, p=prop, text=label):
                text.setText("%d %%" % int(v))
                self._changed(p, int(v))

            slider.valueChanged.connect(moved)
            layout.addWidget(slider, 1)
            layout.addWidget(label)
            row.slider = slider
            return row
        if widget_kind == "check":
            box = QtWidgets.QCheckBox(LABELS[prop])
            box.setChecked(bool(value))
            box.toggled.connect(lambda on, p=prop: self._changed(p, bool(on)))
            return box
        unit = "deg" if widget_kind == "angle" else "mm"
        return DistanceField(
            float(value), unit=unit, on_change=lambda v, p=prop: self._changed(p, v)
        )

    def _show_fields(self):
        """Curvature Map: Display and Scale for Gaussian, the limit for Principal (named
        Maximum / Minimum Limit like Fusion); Isocurve: Density and Scale with combs."""
        if self.kind == sa.CURVATURE_MAP:
            gaussian = self.values.get("MapType") == "Gaussian"
            for prop, show in (
                ("MapDisplay", gaussian),
                ("MapScale", gaussian),
                ("LimitRadius", not gaussian),
            ):
                self._show_row(prop, show)
            name = "Maximum Limit"
            if self.values.get("MapType") == "Principal Maximum":
                name = "Minimum Limit"
            self._label(prop="LimitRadius", text=name)
        elif self.kind == sa.ISOCURVE:
            combs = bool(self.values.get("ShowCombs"))
            self._show_row("Density", combs)
            self._show_row("CombScale", combs)

    def _holder(self, prop):
        kind, widget = self.widgets[prop]
        return widget.widget if isinstance(widget, DistanceField) else widget

    def _show_row(self, prop, show):
        holder = self._holder(prop)
        holder.setVisible(show)
        label = self.layout.labelForField(holder)
        if label is not None:
            label.setVisible(show)

    def _label(self, prop, text):
        label = self.layout.labelForField(self._holder(prop))
        if label is not None:
            label.setText(text)

    def field(self, prop):
        """The widget of an option (the scenarios type into it like a person)."""
        kind, widget = self.widgets[prop]
        if kind == "slider":
            return widget.slider
        return widget.widget if isinstance(widget, DistanceField) else widget

    def _show_boxes(self):
        self.box.set_text(self._targets_text())
        self.box.set_active(not self._closed and self.active == "targets")
        if self.dir_box is not None:
            text = construct.describe(*self.direction) if self.direction else ""
            self.dir_box.set_text(text)
            self.dir_box.set_active(not self._closed and self.active == "direction")

    def _targets_text(self):
        if not self.entries:
            return ""
        if self.what == "bodies":
            if len(self.entries) == 1:
                return self.entries[0][0].Label
            return "%d bodies" % len(self.entries)
        count = sum(len(n) for _o, n in self.entries)
        word = "face" if self.what == "faces" else "edge"
        return "%d %s%s" % (count, word, "" if count == 1 else "s")

    def activate(self, name):
        self.active = name
        self._show_boxes()
        if name == "direction":
            self.hint("Click a plane, a flat face, a straight edge or an axis for the direction.")
        else:
            self.hint(WAITING[self.what])

    @_safe
    def clear_field(self, name):
        if name == "direction":
            self.direction = None
        else:
            self.entries = []
        self.active = name
        self._sync()
        self._show_boxes()
        self.schedule()

    # -- picking -------------------------------------------------------------------------------
    def start_picking(self):
        """As every pick dialog, with a selection filter that looks through components
        ("Part.Body.Pad.Face3" is face 3 of that body)."""
        super().start_picking()
        try:
            if self.gate is not None:
                hole_common.remove_gate(self.gate)
            self.gate = _Gate(self)
            Gui.Selection.addSelectionGate(self.gate)
        except Exception as exc:
            warn("%s: selection filter unavailable: %s" % (self.title, exc))

    def _fits_target(self, obj, short):
        if not _solid_feature(obj):
            return False
        owner = sa.owner_of(obj)
        if owner is None:
            return False
        if self.what == "faces":
            return short.startswith("Face")
        if self.what == "edges":
            return short.startswith("Edge")
        return True

    def allow(self, obj, short):
        if self.active == "direction":
            obj, short = construct.normalize_pick(obj, short)
            if obj is None or construct.is_helper(obj) or sa.is_analysis(obj):
                return False
            return sa.fits_direction(obj, short)
        return self._fits_target(obj, short)

    def _toggle_target(self, obj, short):
        owner = sa.owner_of(obj)
        if owner is None:
            return False
        found = None
        for i, (o, names) in enumerate(self.entries):
            if o is owner:
                found = i
        if self.what == "bodies":
            if found is not None:
                self.entries.pop(found)
            else:
                self.entries.append((owner, []))
            return True
        name = _name_on(owner, obj, short)
        if name is None:
            return False
        if found is None:
            self.entries.append((owner, [name]))
            return True
        names = self.entries[found][1]
        if name in names:
            names.remove(name)
            if not names:
                self.entries.pop(found)
        else:
            names.append(name)
        return True

    def shown(self):
        """Nothing is left selected: the analysis drawn on the model shows what is picked
        (FreeCAD's selection colour drawn over it flickered), the boxes say it in words. A
        click on something picked drops it again all the same."""
        return []

    def picks_changed(self, added, dropped):
        changed = False
        if self.active == "direction":
            for obj, short, _p in dropped:
                ref = _direction_ref(obj, short)
                if self.direction is not None and ref is not None:
                    if ref[0] is self.direction[0] and ref[1] == self.direction[1]:
                        self.direction = None
                        changed = True
            for obj, short, _p in added:
                ref = _direction_ref(obj, short)
                if ref is not None:
                    self.direction = ref
                    self.active = "targets"  # back to the bodies, like the next box
                    changed = True
        else:
            for obj, short, _p in list(dropped) + list(added):
                if self._fits_target(obj, short):
                    changed = self._toggle_target(obj, short) or changed
        if changed:
            self._show_boxes()
        return changed

    # -- values --------------------------------------------------------------------------------
    @_safe
    def _changed(self, prop, value):
        if prop in ("DraftStart", "DraftStop", "LimitRadius", "MinimumRadius", "ToolRadius"):
            value = max(0.0, float(value))
        self.values[prop] = value
        if prop == "LockStripes" and value and self.analysis is not None:
            lock_view(self.analysis)
        self._show_fields()
        self.schedule()

    @_safe
    def _flipped(self, *_):
        self.values["Flip"] = bool(self.flip.isChecked())
        self.schedule()

    # -- the analysis --------------------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            self._timer.start()

    def _preview(self):
        self._apply_now()

    def _recompute(self):
        self._apply_now()

    def _apply_now(self):
        if self._closed:
            return
        if self.doc.Recomputing:
            QtCore.QTimer.singleShot(200, self.schedule)
            return
        try:
            self._apply()
        except (sa.AnalysisError, construct.ConstructError) as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
            self.say("⚠ %s" % exc)

    def _apply(self):
        self.entries = [(o, n) for o, n in self.entries if sa.alive(o)]
        if not self.entries:
            if self.analysis is not None and not self.editing:
                try:
                    self.doc.removeObject(self.analysis.Name)
                except Exception:
                    pass
                self.analysis = None
            self._show_boxes()
            self.hint(WAITING[self.what])
            return
        made = self.analysis is None or not sa.alive(self.analysis)
        if made:
            self.analysis = sa.make(self.doc, self.kind)
            make_view(self.analysis)
        obj = self.analysis
        sa.set_targets(obj, self.entries)
        wanted = [f[0] for f in FIELDS[self.kind]] + (["Flip"] if self.dir_box else [])
        for prop in wanted:
            value = self.values.get(prop)
            if prop not in obj.PropertiesList or value is None:
                continue
            current = getattr(obj, prop)
            current = getattr(current, "Value", current)
            if current != value:
                setattr(obj, prop, value)
        if made and self.kind == sa.ZEBRA and obj.LockStripes:
            lock_view(obj)
        if sa.has_direction(self.kind):
            link = None
            if self.direction is not None and construct.alive(self.direction[0]):
                target, sub = self.direction
                link = (target, [sub] if sub else [""])
            current = obj.PullDirection
            same = (not current and link is None) or (
                current and link and current[0] is link[0] and list(current[1] or [""]) == link[1]
            )
            if not same:
                obj.PullDirection = link
        obj.touch()
        preview.recompute(self.doc)
        try:
            if obj.ViewObject is not None and not obj.ViewObject.Visibility:
                obj.ViewObject.Visibility = True
        except Exception:
            pass
        schedule(self.doc, 0)
        self._show_boxes()
        if obj.Problem:
            self.say(obj.Problem)
        else:
            self.hint("")

    def feature(self):
        return self.analysis

    def accept(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self._apply_now()
            if not self.entries or self.analysis is None:
                self.say(WAITING[self.what])
                return False
            if self.analysis.Problem:
                self.say(self.analysis.Problem)
                return False
            label = self.analysis.Label
            done = self.finish_ok()
            schedule(self.doc)
            log("%s: %s kept" % (self.title, label))
            return done
        except Exception as exc:
            warn("%s OK: %s" % (self.title, exc))
            self.say("⚠ %s" % exc)
            return False

    def reject(self):
        done = super().reject()
        schedule(self.doc)
        return done


# -- commands ----------------------------------------------------------------------------------
def selected_analysis(kind):
    for sel in Gui.Selection.getSelectionEx():
        if sa.is_analysis(sel.Object, kind):
            return sel.Object
    return None


def start(kind):
    """Edit the analysis of this kind selected in the browser, else make a new one (with the
    bodies, faces or edges selected, or wait for clicks)."""
    chosen = selected_analysis(kind)
    picks = hole_common.picks()
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        commands.tell("Open or start a design first.")
        return None
    if chosen is not None:
        return edit(chosen)
    if not [o for o in App.ActiveDocument.Objects if sa.owner_of(o) is o]:
        commands.tell("There is no body to analyse yet: make one first.")
        return None
    panel = AnalysisPanel(App.ActiveDocument, kind, initial=picks)
    Gui.Control.showDialog(panel)
    log("%s started" % sa.title(kind))
    return panel


def edit(obj):
    """Open a stored analysis again (browser double-click, EDITORS). Never raises."""
    try:
        if not commands.finish_open_dialog():
            return None
        kind = sa.kind_of(obj)
        if not kind:
            return None
        panel = AnalysisPanel(obj.Document, kind, analysis=obj)
        Gui.Control.showDialog(panel)
        log("editing %s" % obj.Label)
        return panel
    except Exception as exc:
        warn("the analysis could not open: %s" % exc)
        return None


TIPS = {
    sa.ZEBRA: "Stripes reflected on the bodies: smooth stripes, smooth surfaces",
    sa.DRAFT: "Colours by draft angle against a pull direction",
    sa.COMB: "Curvature combs along the edges you pick",
    sa.CURVATURE_MAP: "Colours by how strongly the surfaces curve",
    sa.ISOCURVE: "Lines of constant U and V on the faces, with combs",
    sa.ACCESSIBILITY: "Where a tool from a direction can reach the bodies",
    sa.MIN_RADIUS: "Concave rounds coloured by whether a tool fits",
}


def _command(kind):
    class Command:
        def GetResources(self):
            return {
                "MenuText": sa.title(kind),
                "ToolTip": TIPS[kind] + " (select an analysis first to edit it)",
                "Pixmap": ui_icon_path(sa.icon(kind)),
            }

        def IsActive(self):
            return True

        def Activated(self):
            try:
                start(kind)
            except Exception as exc:
                warn("%s failed to start: %s" % (sa.title(kind), exc))

    return Command


COMMANDS = {
    "SciForge_ZebraAnalysis": _command(sa.ZEBRA),
    "SciForge_DraftAnalysis": _command(sa.DRAFT),
    "SciForge_CurvatureCombAnalysis": _command(sa.COMB),
    "SciForge_CurvatureMapAnalysis": _command(sa.CURVATURE_MAP),
    "SciForge_IsocurveAnalysis": _command(sa.ISOCURVE),
    "SciForge_AccessibilityAnalysis": _command(sa.ACCESSIBILITY),
    "SciForge_MinimumRadiusAnalysis": _command(sa.MIN_RADIUS),
}
EDITORS = {"SciForge::" + kind: edit for kind in sa.KINDS}
