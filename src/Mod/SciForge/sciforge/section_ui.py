# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Section Analysis, Fusion-style.

Click an origin plane (drawn as big squares while the dialog waits), a construction plane or a
flat face: the part is shown cut there, the cut faces filled in the body's colour (or a custom
one) with diagonal hatch lines. Drag the blue arrow (or type a Distance) to move the cut, the
two blue balls (or X Angle / Y Angle) to tilt it, Flip to look at the other half. OK keeps the
analysis in the browser's Analysis folder: its eye shows or hides the cut, Delete removes it.
To change it later, select it in the browser and run Section Analysis again. Cancel / Esc leave
nothing behind. The bodies themselves never change: only their display is cut.

How the cut is shown: every visible section adds a Coin clip plane (named
SciForgeSectionClip) at the top of each body's display; the cut faces are drawn by the
analysis' own view provider. refresh(doc) puts both in order again after anything changes
(recompute, a body shown or hidden, an analysis shown, hidden, made or deleted); nodes of
FreeCAD's view providers are looked up fresh every time, never kept.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodypick, commands, construct, handles3d, hole_common, log, pickpanel
from . import preview, section, warn
from . import ui_icon_path
from .compat import QtCore, QtGui, QtWidgets
from .taskui import DistanceField, ValueBoxes

CLIP_NAME = "SciForgeSectionClip"
HATCH = (0.08, 0.08, 0.08)
SWATCHES = [
    (0.85, 0.35, 0.30),
    (0.95, 0.65, 0.20),
    (0.95, 0.85, 0.30),
    (0.45, 0.75, 0.40),
    (0.30, 0.60, 0.90),
    (0.60, 0.45, 0.85),
    (0.80, 0.80, 0.80),
]
# value box -> the analysis property its formula goes on, and the box's name
FORMULA_PROPS = {"distance": "Distance", "x_angle": "XAngle", "y_angle": "YAngle"}
FORMULA_NAMES = {"distance": "Distance", "x_angle": "X Angle", "y_angle": "Y Angle"}


# -- keeping the cut display in order ----------------------------------------------------------
_PENDING = {"docs": set(), "armed": False}


def schedule(doc):
    """Put the cut display of `doc` in order a moment later (never inside FreeCAD's own
    callbacks)."""
    try:
        _PENDING["docs"].add(doc.Name)
    except Exception:
        return
    if not _PENDING["armed"]:
        _PENDING["armed"] = True
        QtCore.QTimer.singleShot(40, _run)


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
                schedule(doc)
                continue
        except Exception:
            pass
        try:
            refresh(doc)
        except Exception as exc:
            warn("section display: %s" % exc)


class _DocWatch:
    """Anything that can change what a section shows schedules a refresh."""

    def slotRecomputedDocument(self, doc):
        if section.sections(doc):
            schedule(doc)

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Visibility" and obj.Document is not None:
                if section.sections(obj.Document) or _has_clips(obj):
                    schedule(obj.Document)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            if section.is_section(obj) or obj.TypeId == "PartDesign::Body":
                schedule(obj.Document)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        schedule(doc)

    def slotRedoDocument(self, doc):
        schedule(doc)


_WATCH = {"observer": None}


def ensure_watch():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = _DocWatch()
        App.addDocumentObserver(_WATCH["observer"])


def _root(obj):
    try:
        vobj = obj.ViewObject
        return vobj.RootNode if vobj is not None else None
    except Exception:
        return None


def _clip_nodes(root):
    found = []
    if root is None:
        return found
    for i in range(root.getNumChildren()):
        child = root.getChild(i)
        try:
            if child.getName().getString() == CLIP_NAME:
                found.append(child)
        except Exception:
            continue
    return found


def _has_clips(obj):
    return bool(_clip_nodes(_root(obj)))


def _clip_node(place):
    from pivy import coin

    n = section.normal_of(place)
    o = place.Base
    node = coin.SoClipPlane()
    node.setName(CLIP_NAME)
    # Coin keeps the side the plane's normal points to: keep the side away from the cut's Z
    node.plane.setValue(coin.SbPlane(coin.SbVec3f(-n.x, -n.y, -n.z), coin.SbVec3f(o.x, o.y, o.z)))
    return node


def visible_sections(doc):
    found = []
    for obj in section.sections(doc):
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility:
                continue
            if "Invalid" in list(obj.State):
                continue
            found.append(obj)
        except Exception:
            continue
    return found


def solid_displays(obj):
    """The objects whose display shows the solid of `obj`: a body's solid features (one of
    them is shown, the Tip or the step the timeline is rolled back to), or a loose solid
    itself. Only these are cut: a body's sketches, construction planes, axes and points stay
    whole, as in Fusion (a construction plane lying in the cut was drawn half-clipped)."""
    if obj.TypeId != "PartDesign::Body":
        return [obj]
    found = []
    for feature in obj.Group:
        try:
            if feature.isDerivedFrom("PartDesign::Feature"):
                found.append(feature)
        except Exception:
            continue
    return found


def clips_on(obj):
    """Clip nodes cutting the displayed solid of a body (its Tip) or of a loose solid."""
    shown = obj.Tip if obj.TypeId == "PartDesign::Body" else obj
    return _clip_nodes(_root(shown)) if shown is not None else []


def _parent_frame(obj):
    """Global -> the coordinates obj's display is drawn in (its body's, or a container's)."""
    try:
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            return parent.getGlobalPlacement().inverse()
    except Exception:
        pass
    return App.Placement()


def refresh(doc):
    """Clip planes on every body's solid for the visible sections, cut faces drawn again."""
    if App.GuiUp is False or Gui.getDocument(doc.Name) is None:
        return
    shown = visible_sections(doc)
    for obj in section.clipped_objects(doc):
        own = _root(obj)
        for node in _clip_nodes(own):  # an earlier SciForge clipped the whole body
            own.removeChild(node)
        cut = bool(obj.ViewObject is not None and obj.ViewObject.Visibility)
        for target in solid_displays(obj):
            root = _root(target)
            if root is None:
                continue
            for node in _clip_nodes(root):
                root.removeChild(node)
            if not cut:
                continue
            # The clip goes first in the step's own display, which is drawn inside its
            # body's placement: give it the cut in the body's coordinates (a body that was
            # moved by its Placement was cut in the wrong place).
            frame = _parent_frame(target)
            for analysis in shown:
                root.insertChild(_clip_node(frame.multiply(analysis.CutPlacement)), 0)
    for analysis in section.sections(doc):
        proxy = getattr(analysis.ViewObject, "Proxy", None) if analysis.ViewObject else None
        if isinstance(proxy, ViewProviderSection):
            proxy.redraw(analysis, shown)


def cut_shapes(doc):
    """(object, global solid shape) of what the sections cut and is shown."""
    found = []
    for obj in section.clipped_objects(doc):
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility:
                continue
            shape = obj.Shape
            if shape.isNull() or not shape.Solids:
                continue
            found.append((obj, shape))
        except Exception:
            continue
    return found


def _body_color(obj):
    try:
        color = obj.ViewObject.ShapeColor
        return tuple(color)[:3]
    except Exception:
        return (0.8, 0.8, 0.8)


class ViewProviderSection:
    """Draws the cut faces (caps) and hatch of one section analysis. Saved documents store
    "sciforge.section_ui.ViewProviderSection": keep the name stable."""

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
        vobj.addDisplayMode(self.root, "Section")
        ensure_watch()
        try:
            schedule(vobj.Object.Document)
        except Exception:
            pass

    def getDisplayModes(self, vobj):
        return ["Section"]

    def getDefaultDisplayMode(self):
        return "Section"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop in ("CutPlacement", "SectionColor", "CustomColor", "ShowHatch"):
            schedule(obj.Document)

    def onChanged(self, vobj, prop):
        if prop == "Visibility":
            try:
                schedule(vobj.Object.Document)
            except Exception:
                pass

    def getIcon(self):
        return ui_icon_path("section")

    def doubleClicked(self, vobj):
        QtCore.QTimer.singleShot(0, lambda: edit(vobj.Object))
        return True

    def redraw(self, obj, shown):
        """Fill the cut faces of every shown body (clipped by the other shown sections)."""
        from pivy import coin

        content = getattr(self, "content", None)
        if content is None:
            return
        content.removeAllChildren()
        if obj not in shown:
            return
        place = obj.CutPlacement
        n = section.normal_of(place)
        doc = obj.Document
        for other in shown:
            if other is not obj:
                content.addChild(_clip_node(other.CutPlacement))
        size = 1.0
        for _o, shape in cut_shapes(doc):
            size = max(size, shape.BoundBox.DiagonalLength)
        lift = n * (size * 1e-4)
        for target, shape in cut_shapes(doc):
            faces = section.cap_faces(shape, place)
            if not faces:
                continue
            if obj.SectionColor == "Custom":
                color = tuple(obj.CustomColor)[:3]
            else:
                color = _body_color(target)
            for face in faces:
                self._face(coin, content, face, color, lift)
            if obj.ShowHatch:
                spacing = max(0.5, size / 45.0)
                for a, b in section.hatch_lines(faces, place, spacing):
                    self._line(coin, content, a + lift * 2, b + lift * 2)

    def _face(self, coin, parent, face, color, lift):
        points, triangles = face.tessellate(max(0.01, face.BoundBox.DiagonalLength / 400.0))
        if not triangles:
            return
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.35 for c in color])
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        coords = coin.SoCoordinate3()
        coords.point.setValues(
            0, len(points), [(p.x + lift.x, p.y + lift.y, p.z + lift.z) for p in points]
        )
        faces = coin.SoIndexedFaceSet()
        index = []
        for a, b, c in triangles:
            index += [a, b, c, -1]
        faces.coordIndex.setValues(0, len(index), index)
        # The hatch lines lie a hair above the cut face; that alone lost to the depth
        # buffer's rounding on a cut seen at a slant (bands of the hatch went missing).
        # Push the filled face back a little, as decals are drawn.
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(1.0)
        offset.units.setValue(2.0)
        sep.addChild(material)
        sep.addChild(hints)
        sep.addChild(offset)
        sep.addChild(coords)
        sep.addChild(faces)
        parent.addChild(sep)

    def _line(self, coin, parent, a, b):
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*HATCH)
        material.emissiveColor.setValue(*HATCH)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, 2, [(a.x, a.y, a.z), (b.x, b.y, b.z)])
        lines = coin.SoLineSet()
        lines.numVertices.setValue(2)
        sep.addChild(material)
        sep.addChild(coords)
        sep.addChild(lines)
        parent.addChild(sep)

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


def make_view(obj):
    if App.GuiUp and obj.ViewObject is not None:
        ViewProviderSection(obj.ViewObject)


# -- the dialog ----------------------------------------------------------------------------------
def _safe(method):
    import functools

    @functools.wraps(method)
    def wrapper(self, *args):
        try:
            return method(self, *args)
        except (section.SectionError, construct.ConstructError) as exc:
            self.say(str(exc))
        except Exception as exc:
            warn("Section Analysis: %s" % exc)
            try:
                self.say("⚠ %s" % exc)
            except Exception:
                pass
        return None

    return wrapper


class _Gate:
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


class SectionPanel(bodypick.Tones, pickpanel.PickPanel):
    title = "Section Analysis"
    icon = "section"
    last = None

    def __init__(self, doc, analysis=None, initial=()):
        name = ("Edit %s" % analysis.Label) if analysis is not None else self.title
        super().__init__(doc, name)
        SectionPanel.last = self
        self.analysis = analysis
        self.editing = analysis is not None
        self.ref = None
        self.options = {
            "distance": 0.0,
            "x_angle": 0.0,
            "y_angle": 0.0,
            "flip": False,
            "color_mode": "From Body",
            "color": SWATCHES[0],
            "hatch": True,
            "pivot": (0.0, 0.0),
        }
        # Values typed as a parameter or formula ("-gap", "depth / 2") follow it, as in every
        # Fusion value box: kept as expressions on the analysis' Distance / XAngle / YAngle.
        self.formulas = {}
        self.formula_errors = {}  # value box -> why what was typed there is no value
        if analysis is not None:
            ref, options = section.read(analysis)
            self.ref = ref
            self.options.update(options)
            for key, prop in FORMULA_PROPS.items():
                text = preview.formula_of(analysis, prop)
                if text:
                    self.formulas[key] = text
        self.handles = {}
        # Fusion shows the value beside each handle (the offset, X and Y Angle); typed
        # there it is taken like the dialog's field. One box per field, made once.
        self.value_boxes = ValueBoxes(self, default="distance")
        self.planes = None
        self.repick = False
        self.error = ""
        self._build()
        if analysis is None:
            for obj, short, _point in initial:
                if self._fits(obj, short):
                    self._set_ref(construct.normalize_pick(obj, short))
                    break
        self.start_picking()
        try:
            if self.gate is not None:
                hole_common.remove_gate(self.gate)
            self.gate = _Gate(self)
            Gui.Selection.addSelectionGate(self.gate)
        except Exception as exc:
            warn("Section Analysis: selection filter unavailable: %s" % exc)
        ensure_watch()
        self._show_box()
        self._update_planes()
        self._apply_now()

    # -- widgets -------------------------------------------------------------------------------
    def _build(self):
        self.box = hole_common.SelectionField(self, 0, "Select")
        self.box.button.setObjectName("SciForgeSection_plane")
        self.box.button.setToolTip("Click a plane or a flat face to cut along")
        self.box.clear.setObjectName("SciForgeSection_clear")
        self.layout.addRow("Faces", self.box.widget)
        self.distance = DistanceField(self.options["distance"], on_change=self._typed_distance)
        self.distance.widget.setObjectName("SciForgeSection_distance")
        self.layout.addRow("Distance", self.distance.widget)
        self.x_angle = DistanceField(self.options["x_angle"], unit="deg", on_change=self._typed_x)
        self.x_angle.widget.setObjectName("SciForgeSection_xangle")
        self.layout.addRow("X Angle", self.x_angle.widget)
        self.y_angle = DistanceField(self.options["y_angle"], unit="deg", on_change=self._typed_y)
        self.y_angle.widget.setObjectName("SciForgeSection_yangle")
        self.layout.addRow("Y Angle", self.y_angle.widget)
        self._formula_inputs = [
            preview.FormulaInput(self, key, field)
            for key, field in (
                ("distance", self.distance),
                ("x_angle", self.x_angle),
                ("y_angle", self.y_angle),
            )
        ]
        self.formula_label = QtWidgets.QLabel("")
        self.formula_label.setObjectName("SciForgeSection_formulas")
        self.formula_label.setWordWrap(True)
        self.layout.addRow(self.formula_label)
        self._show_formulas()
        self.flip = QtWidgets.QPushButton("Flip")
        self.flip.setObjectName("SciForgeSection_flip")
        self.flip.setCheckable(True)
        self.flip.setChecked(self.options["flip"])
        self.flip.setToolTip("Cut away the other side")
        self.flip.clicked.connect(self._flipped)
        self.layout.addRow("Flip", self.flip)
        self.color_mode = pickpanel.combo(
            [(m, m) for m in section.COLOR_MODES], self.options["color_mode"]
        )
        self.color_mode.setObjectName("SciForgeSection_color")
        self.color_mode.currentIndexChanged.connect(self._color_mode_changed)
        self.layout.addRow("Section Color", self.color_mode)
        self.swatch_row = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.swatch_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        self.swatches = []
        for i, color in enumerate(SWATCHES):
            button = QtWidgets.QToolButton()
            button.setObjectName("SciForgeSection_swatch%d" % i)
            button.setCheckable(True)
            button.setFixedSize(22, 22)
            rgb = "rgb(%d, %d, %d)" % tuple(int(c * 255) for c in color)
            button.setStyleSheet(
                "QToolButton { background: %s; border: 1px solid #555; }"
                "QToolButton:checked { border: 2px solid white; }" % rgb
            )
            button.clicked.connect(lambda _=False, c=color: self._swatch(c))
            self.swatches.append((button, color))
            row.addWidget(button)
        row.addStretch(1)
        self.layout.addRow("", self.swatch_row)
        self.hatch = QtWidgets.QCheckBox("Show Hatch")
        self.hatch.setObjectName("SciForgeSection_hatch")
        self.hatch.setChecked(self.options["hatch"])
        self.hatch.toggled.connect(self._hatch_toggled)
        self.layout.addRow(self.hatch)
        self._show_swatches()
        from .construct_ui import EnterAfterSum

        self._enter_sum = EnterAfterSum(self, [self.distance, self.x_angle, self.y_angle])
        self.finish_layout()

    def _show_box(self):
        text = construct.describe(*self.ref) if self.ref else ""
        self.box.set_text(text)
        self.box.set_active(not self._closed and (self.ref is None or self.repick))

    def _show_swatches(self):
        custom = self.options["color_mode"] == "Custom"
        for button, color in self.swatches:
            same = all(abs(a - b) < 1e-3 for a, b in zip(color, self.options["color"]))
            button.setChecked(custom and same)

    def activate(self, _index):
        self.repick = True
        self._show_box()
        self._update_planes()
        self.hint("Click a plane or a flat face to cut along.")

    @_safe
    def clear_field(self, _index):
        self.ref = None
        self.repick = False
        self._sync()
        self._show_box()
        self._update_planes()
        self.schedule()

    # -- picking ---------------------------------------------------------------------------------
    def _fits(self, obj, short):
        obj, short = construct.normalize_pick(obj, short)
        return obj is not None and "plane" in construct.kinds_of(obj, short)

    def allow(self, obj, short):
        obj, short = construct.normalize_pick(obj, short)
        if obj is None or construct.is_helper(obj) or section.is_section(obj):
            return False
        if self.ref is not None and obj is self.ref[0] and short == self.ref[1]:
            return True
        return self._fits(obj, short)

    def shown(self):
        if self.ref is None or not construct.alive(self.ref[0]):
            return []
        return [(self.ref[0], [self.ref[1]] if self.ref[1] else [])]

    def picks_changed(self, added, dropped):
        # A handle's press or release is not a pick: FreeCAD also selected the face under
        # the mouse then. Letting go of the arrow far down selected the bottom face (seen
        # from inside the cut) and the section jumped onto it; the handles are made anew
        # when a drag ends, so ask handles3d (it remembers it for every handle).
        if handles3d.just_used() or any(h.busy() for h in self.handles.values()):
            return False
        if self.planes is not None and self.planes.clicked_recently():
            added = []
        changed = False
        for obj, short, _p in dropped:
            obj, short = construct.normalize_pick(obj, short)
            if self.ref is not None and obj is self.ref[0] and short == self.ref[1]:
                self.ref = None
                changed = True
        for obj, short, _p in added:
            if self._fits(obj, short):
                self._set_ref(construct.normalize_pick(obj, short))
                changed = True
        if changed:
            self._show_box()
            self._update_planes()
        return changed

    @_safe
    def _plane_clicked(self, plane):
        if self._closed:
            return
        self._set_ref((plane, ""))
        self._sync()
        self._show_box()
        self._update_planes()
        self.schedule()

    def _update_planes(self):
        want = not self._closed and (self.ref is None or self.repick)
        if want and self.planes is None:
            try:
                from .construct_ui import _origin_planes_class

                cls = _origin_planes_class()
                body = commands.find_body()
                if body is not None:
                    self.planes = cls(Gui.ActiveDocument.ActiveView, body, self._plane_clicked)
                    self.planes.takes = self._takes_under
            except Exception as exc:
                warn("Section Analysis: origin planes unavailable: %s" % exc)
        elif not want and self.planes is not None:
            self.planes.remove()
            self.planes = None

    def _takes_under(self, position):
        """True when what FreeCAD picks under the mouse can be cut along (it then gets the
        click); anything else lets the origin square behind it take it, like Fusion."""
        try:
            from .construct_ui import _resolve_gate

            info = Gui.ActiveDocument.ActiveView.getObjectInfo(tuple(position))
            if not info or not info.get("Object"):
                return False
            top = self.doc.getObject(info["Object"])
            if top is None:
                return False
            obj, short = _resolve_gate(top, str(info.get("Component", "")))
            return bool(self.allow(obj, short))
        except Exception:
            return False

    # -- values ------------------------------------------------------------------------------
    def _plain_value(self, key, value):
        """A number typed or dragged: the box no longer follows a formula."""
        self.options[key] = float(value)
        self.formulas.pop(key, None)
        self.formula_errors.pop(key, None)
        self._show_formulas()

    @_safe
    def _typed_distance(self, value):
        self._plain_value("distance", value)
        self._move_handles()
        self.schedule()

    @_safe
    def _typed_x(self, value):
        self._plain_value("x_angle", value)
        self._rebuild_handles()
        self.schedule()

    @_safe
    def _typed_y(self, value):
        self._plain_value("y_angle", value)
        self._move_handles()
        self.schedule()

    # preview.FormulaInput calls these
    def formula_typed(self, key, text, value):
        self.formula_errors.pop(key, None)
        self.formulas[key] = text
        self.options[key] = float(value)
        self._show_formulas()
        if key == "x_angle":
            self._rebuild_handles()
        else:
            self._move_handles()
        self.schedule()

    def formula_cleared(self, key):
        self.formula_errors.pop(key, None)
        if self.formulas.pop(key, None) is not None:
            self._show_formulas()
        self.schedule()

    def formula_failed(self, key, message):
        """Something that is no value ("gap +"): the dialog stays open (also on Enter and
        OK) and says so; the cut keeps the last good value."""
        self.formula_errors[key] = message
        self._show_status("")

    def _show_formulas(self):
        label = getattr(self, "formula_label", None)
        if label is None:
            return
        rows = [
            "%s = %s" % (FORMULA_NAMES[k], self.formulas[k])
            for k in FORMULA_PROPS
            if self.formulas.get(k)
        ]
        label.setText("\n".join(rows))
        label.setVisible(bool(rows))

    def _show_status(self, problem):
        if self.formula_errors:
            self.say("⚠ %s" % next(iter(self.formula_errors.values())))
        elif problem:
            self.say(problem)
        else:
            self.hint("")

    @_safe
    def _flipped(self, *_):
        self.options["flip"] = bool(self.flip.isChecked())
        self.schedule()

    @_safe
    def _color_mode_changed(self, *_):
        self.options["color_mode"] = self.color_mode.currentData()
        self._show_swatches()
        self.schedule()

    @_safe
    def _swatch(self, color):
        self.options["color"] = tuple(color)
        if self.options["color_mode"] != "Custom":
            hole_common.set_combo(self.color_mode, "Custom")
        self.options["color_mode"] = "Custom"
        self._show_swatches()
        self.schedule()

    @_safe
    def _hatch_toggled(self, on):
        self.options["hatch"] = bool(on)
        self.schedule()

    # -- handles: an arrow for the distance, two balls for the angles ---------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _frames(self):
        """(base, after_x) placements: the picked plane moved by the distance, and that
        turned by X Angle (the Y ball turns about its Y axis)."""
        base = section.base_frame(self.ref, self.options["pivot"])
        moved = base.multiply(
            App.Placement(App.Vector(0, 0, self.options["distance"]), App.Rotation())
        )
        after_x = moved.multiply(
            App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), self.options["x_angle"]))
        )
        return base, moved, after_x

    def _size(self):
        """How big the handles are drawn: from the biggest body the section cuts."""
        sizes = [shape.BoundBox.DiagonalLength for _o, shape in cut_shapes(self.doc)]
        return max([10.0] + sizes) if sizes else 50.0

    def _rebuild_handles(self):
        self._remove_handles()
        if self.ref is None or self.error:
            return
        size = self._size()
        base, moved, after_x = self._frames()
        n = base.Rotation.multVec(App.Vector(0, 0, 1))
        self.handles["distance"] = handles3d.LinearHandle(
            base.Base,
            n,
            self.options["distance"],
            size * 0.2,
            on_drag=self._dragged_distance,
            on_release=self._dragged_distance,
        )
        x_axis = moved.Rotation.multVec(App.Vector(1, 0, 0))
        y_axis = moved.Rotation.multVec(App.Vector(0, 1, 0))
        self.handles["x"] = handles3d.angle_handle(
            moved.Base,
            x_axis,
            y_axis,
            size * 0.45,
            self.options["x_angle"],
            size * 0.1,
            on_drag=self._dragged_x,
            on_release=self._dragged_x,
        )
        y_axis_x = after_x.Rotation.multVec(App.Vector(0, 1, 0))
        x_axis_x = after_x.Rotation.multVec(App.Vector(1, 0, 0))
        self.handles["y"] = handles3d.angle_handle(
            moved.Base,
            y_axis_x,
            x_axis_x,
            size * 0.45,
            self.options["y_angle"],
            size * 0.1,
            on_drag=self._dragged_y,
            on_release=self._dragged_y,
        )
        for key, name, field in (
            ("distance", "distance", self.distance),
            ("x", "x_angle", self.x_angle),
            ("y", "y_angle", self.y_angle),
        ):
            self.value_boxes.attach(
                self.handles.get(key),
                name,
                lambda f=field: f.widget.text(),
                lambda text, n=name: self._box_typed(n, text),
            )

    def _box_typed(self, key, text):
        if self._closed:
            return
        for formula in getattr(self, "_formula_inputs", []):
            if formula.key == key:
                formula.take(text)
                return

    def _move_handles(self):
        if not self.handles:
            return
        self._rebuild_handles()

    @_safe
    def _dragged_distance(self, value):
        value = round(float(value), 3)
        self._plain_value("distance", value)
        self.distance.set_value(value)
        handle = self.handles.get("distance")
        if handle is not None and not handle.dragging():
            self._rebuild_handles()
        self.schedule()

    @_safe
    def _dragged_x(self, value):
        value = round(float(value), 2)
        self._plain_value("x_angle", value)
        self.x_angle.set_value(value)
        handle = self.handles.get("x")
        if handle is not None and not handle.dragging():
            self._rebuild_handles()
        self.schedule()

    @_safe
    def _dragged_y(self, value):
        value = round(float(value), 2)
        self._plain_value("y_angle", value)
        self.y_angle.set_value(value)
        self.schedule()

    # -- the analysis ------------------------------------------------------------------------
    def schedule(self):
        if not self._closed:
            super().schedule()  # the shared pace: a drag shows its cut while it moves

    def _preview(self):
        self._apply_now()

    def _apply_now(self):
        if self._closed:
            return
        if self.doc.Recomputing:
            QtCore.QTimer.singleShot(200, self.schedule)
            return
        if self.ref is None:
            self.error = ""
            self._remove_handles()
            if self.analysis is not None and not self.editing:
                try:
                    self.doc.removeObject(self.analysis.Name)
                except Exception:
                    pass
                self.analysis = None
                schedule(self.doc)
            gone = section.problem(self.analysis) if self.analysis is not None else ""
            if gone:
                self.say(gone)
            else:
                self.hint("Click a plane or a flat face to cut along.")
            return
        try:
            section.cut_frame(self.ref, **self._frame_options())
        except section.SectionError as exc:
            self.error = str(exc)
            self._remove_handles()
            self.say(self.error)
            return
        self.error = ""
        if self.analysis is None or not construct.alive(self.analysis):
            self.analysis = section.make(self.doc, self.ref, self.options)
            make_view(self.analysis)
        else:
            section.update(self.analysis, self.ref, self.options)
        for key, prop in FORMULA_PROPS.items():
            preview.set_formula(self.analysis, prop, self.formulas.get(key, ""))
        preview.recompute(self.doc)
        try:
            if self.analysis.ViewObject is not None and not self.analysis.ViewObject.Visibility:
                self.analysis.ViewObject.Visibility = True
        except Exception:
            pass
        schedule(self.doc)
        if not any(h.dragging() for h in self.handles.values()):
            self._rebuild_handles()
        self._show_status(section.problem(self.analysis) or preview.failure(self.analysis))

    def _frame_options(self):
        return {
            "distance": self.options["distance"],
            "x_angle": self.options["x_angle"],
            "y_angle": self.options["y_angle"],
            "flip": self.options["flip"],
            "pivot": self.options["pivot"],
        }

    def _set_ref(self, ref):
        """A new plane: the cut turns about (and the handles sit at) the middle of the part."""
        self.ref = ref
        self.repick = False
        try:
            shapes = [shape for _o, shape in cut_shapes(self.doc)]
            self.options["pivot"] = section.pivot_for(ref, shapes)
        except Exception:
            self.options["pivot"] = (0.0, 0.0)

    def feature(self):
        return self.analysis

    def accept(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self._apply_now()
            if self.ref is None or self.analysis is None:
                self.say("Click a plane or a flat face to cut along.")
                return False
            if self.error:
                self.say(self.error)
                return False
            if self.formula_errors:  # Fusion does not take a value it cannot read
                self._show_status("")
                return False
            label = self.analysis.Label
            done = self.finish_ok()
            schedule(self.doc)
            log("Section Analysis: %s kept" % label)
            return done
        except Exception as exc:
            warn("Section Analysis OK: %s" % exc)
            self.say("⚠ %s" % exc)
            return False

    def reject(self):
        done = super().reject()
        schedule(self.doc)
        return done

    def cleanup(self):
        self._remove_handles()
        self.value_boxes.discard()
        enter = getattr(self, "_enter_sum", None)
        if enter is not None:
            enter.remove()
            self._enter_sum = None
        for formula in getattr(self, "_formula_inputs", []):
            formula.panel = None
        self._formula_inputs = []
        if self.planes is not None:
            try:
                self.planes.remove()
            except Exception:
                pass
            self.planes = None
        super().cleanup()


# -- commands ------------------------------------------------------------------------------------
def selected_section():
    for sel in Gui.Selection.getSelectionEx():
        if section.is_section(sel.Object):
            return sel.Object
    return None


def start():
    """Section Analysis: edit the analysis selected in the browser, else make a new one
    (on the plane or face selected, or wait for one)."""
    chosen = selected_section()
    picks = hole_common.picks()
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        commands.tell("Open or start a design first.")
        return None
    if chosen is not None:
        return edit(chosen)
    commands.ensure_body()
    panel = SectionPanel(App.ActiveDocument, initial=picks)
    Gui.Control.showDialog(panel)
    log("Section Analysis started")
    return panel


def edit(analysis):
    """Open a stored section again (browser double-click, EDITORS). Never raises."""
    try:
        if not commands.finish_open_dialog():
            return None
        panel = SectionPanel(analysis.Document, analysis=analysis)
        Gui.Control.showDialog(panel)
        log("editing %s" % analysis.Label)
        return panel
    except Exception as exc:
        warn("Section Analysis could not open: %s" % exc)
        return None


class SectionCommand:
    def GetResources(self):
        return {
            "MenuText": "Section Analysis",
            "ToolTip": "Show the design cut along a plane (select an analysis first to edit it)",
            "Pixmap": ui_icon_path("section"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Section Analysis failed to start: %s" % exc)


COMMANDS = {"SciForge_SectionAnalysis": SectionCommand}
EDITORS = {"SciForge::SectionAnalysis": edit}
