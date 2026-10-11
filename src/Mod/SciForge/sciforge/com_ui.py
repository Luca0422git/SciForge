# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Center of Mass, Fusion-style.

Click the bodies to measure (a click on a picked body drops it; with none picked, every
visible body counts). The centre of mass is marked in the 3D view (a black-and-white ball,
seen through the part) and its X / Y / Z are shown in the dialog. OK keeps it in the
browser's Analysis folder (eye to show / hide); it follows the model when it changes. Select
it in the browser and run Center of Mass again to change it. Cancel / Esc leave nothing.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import analysis, bodypick, commands, hole_common, log, measure, preview, warn
from . import ui_icon_path
from .compat import QtCore, QtWidgets


def _units(doc):
    try:
        from . import browser_ui

        return browser_ui.units(doc)
    except Exception:
        return "mm"


_FOLLOW = {"observer": None, "docs": set(), "armed": False}


def _follow_now():
    _FOLLOW["armed"] = False
    names, _FOLLOW["docs"] = _FOLLOW["docs"], set()
    for name in names:
        try:
            doc = App.getDocument(name)
        except Exception:
            continue
        try:
            if doc.Recomputing:
                _follow_later(doc)
                continue
            analysis.follow(doc)
        except Exception as exc:
            warn("Center of Mass: %s" % exc)


def _follow_later(doc):
    """Measure the "all visible bodies" analyses of `doc` again a moment later (never inside
    FreeCAD's own callbacks)."""
    try:
        if not analysis.of_kind(doc, analysis.COM_KIND):
            return
        _FOLLOW["docs"].add(doc.Name)
    except Exception:
        return
    if not _FOLLOW["armed"]:
        _FOLLOW["armed"] = True
        QtCore.QTimer.singleShot(30, _follow_now)


class _FollowWatch:
    """What can move an "all visible bodies" centre of mass: a recompute, a body shown,
    hidden or deleted, undo / redo."""

    def slotRecomputedDocument(self, doc):
        _follow_later(doc)

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Visibility" and analysis.body_of(obj) is obj:
                _follow_later(obj.Document)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            if obj.TypeId == "PartDesign::Body":
                _follow_later(obj.Document)
        except Exception:
            pass

    def slotUndoDocument(self, doc):
        _follow_later(doc)

    def slotRedoDocument(self, doc):
        _follow_later(doc)


def ensure_follow():
    if _FOLLOW["observer"] is None:
        try:
            _FOLLOW["observer"] = _FollowWatch()
            App.addDocumentObserver(_FOLLOW["observer"])
        except Exception as exc:
            _FOLLOW["observer"] = None
            warn("Center of Mass: %s" % exc)


class ViewProviderCenterOfMass:
    """The marker. Saved documents store "sciforge.com_ui.ViewProviderCenterOfMass"."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        ensure_follow()
        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        bodypick.on_top(self.root)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.place = coin.SoTranslation()
        self.root.addChild(self.place)
        self.scale = coin.SoScale()
        self.root.addChild(self.scale)
        self.root.addChild(self._marker(coin))
        vobj.addDisplayMode(self.root, "Marker")
        self._update(vobj.Object)

    def _marker(self, coin):
        """Fusion's centre-of-mass sign: a ball in black and white quarters, unit size."""
        sep = coin.SoSeparator()
        for i in range(8):
            octant = coin.SoSeparator()
            material = coin.SoMaterial()
            dark = (i + (i // 2) + (i // 4)) % 2 == 0
            color = (0.05, 0.05, 0.05) if dark else (0.95, 0.95, 0.95)
            material.diffuseColor.setValue(*color)
            material.emissiveColor.setValue(*[c * 0.6 for c in color])
            octant.addChild(material)
            sx = 1 if i & 1 else -1
            sy = 1 if i & 2 else -1
            sz = 1 if i & 4 else -1
            move = coin.SoTranslation()
            move.translation.setValue(0.25 * sx, 0.25 * sy, 0.25 * sz)
            octant.addChild(move)
            ball = coin.SoSphere()
            ball.radius.setValue(0.36)
            octant.addChild(ball)
            sep.addChild(octant)
        ring = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(0.98, 0.78, 0.25)
        material.emissiveColor.setValue(0.98, 0.78, 0.25)
        ring.addChild(material)
        coords = coin.SoCoordinate3()
        import math

        points = [
            (1.2 * math.cos(a / 24.0 * 2 * math.pi), 1.2 * math.sin(a / 24.0 * 2 * math.pi), 0)
            for a in range(25)
        ]
        coords.point.setValues(0, len(points), points)
        ring.addChild(coords)
        lines = coin.SoLineSet()
        lines.numVertices.setValue(len(points))
        ring.addChild(lines)
        sep.addChild(ring)
        return sep

    def _size(self, obj):
        size = 50.0
        try:
            box = None
            for body in analysis.bodies(obj.Document):
                shape = body.Shape
                if shape.isNull():
                    continue
                box = shape.BoundBox if box is None else box.united(shape.BoundBox)
            if box is not None:
                size = box.DiagonalLength
        except Exception:
            pass
        return max(0.5, size * 0.025)

    def _update(self, obj):
        try:
            p = obj.Position
            self.place.translation.setValue(p.x, p.y, p.z)
            s = self._size(obj)
            self.scale.scaleFactor.setValue(s, s, s)
        except Exception as exc:
            warn("Center of Mass marker: %s" % exc)

    def getDisplayModes(self, vobj):
        return ["Marker"]

    def getDefaultDisplayMode(self):
        return "Marker"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop in ("Position", "Volume"):
            self._update(obj)

    def onChanged(self, vobj, prop):
        pass

    def getIcon(self):
        return ui_icon_path("center_of_mass")

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def make_view(obj):
    if App.GuiUp and obj.ViewObject is not None:
        ViewProviderCenterOfMass(obj.ViewObject)


class CenterOfMassPanel(bodypick.BodyPickPanel):
    title = "Center of Mass"
    icon = "center_of_mass"
    last = None

    def __init__(self, doc, target=None, initial=()):
        name = ("Edit %s" % target.Label) if target is not None else self.title
        super().__init__(doc, name)
        CenterOfMassPanel.last = self
        self.target = target
        self.editing = target is not None
        self.unit = _units(doc)
        if target is not None:
            self.picked = [o for o in target.Bodies if o is not None]
        else:
            for obj, _short, _point in initial:
                body = analysis.body_of(obj)
                if body is not None and body not in self.picked:
                    self.picked.append(body)
        self.box = hole_common.SelectionField(self, 0, "All visible bodies")
        self.box.button.setObjectName("SciForgeCOM_bodies")
        self.box.button.setToolTip("Click the bodies to measure (none: all visible bodies)")
        self.box.clear.setObjectName("SciForgeCOM_clear")
        self.layout.addRow("Selection", self.box.widget)
        self.coords = {}
        for axis in ("X", "Y", "Z"):
            label = QtWidgets.QLabel("")
            label.setObjectName("SciForgeCOM_" + axis)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.coords[axis] = label
            self.layout.addRow(axis, label)
        self.finish_layout()
        self.start_picking()
        self.box.set_active(True)
        self._apply_now()

    def activate(self, _index):
        self.box.set_active(True)

    def clear_field(self, _index):
        try:
            self.picked = []
            self._sync()
            self.bodies_changed()
            self.schedule()
        except Exception as exc:
            warn("Center of Mass: %s" % exc)

    def bodies_changed(self):
        self.box.set_text(self.picked_text("All visible bodies"))

    def schedule(self):
        if not self._closed:
            self._timer.start()

    def _preview(self):
        self._apply_now()

    def _apply_now(self):
        if self._closed:
            return
        try:
            self.box.set_text(self.picked_text("All visible bodies"))
            if self.target is None or not hole_common.alive(self.target):
                self.target = analysis.make_com(self.doc, self.picked)
                make_view(self.target)
            else:
                analysis.set_bodies(self.target, self.picked)
            preview.recompute(self.doc)
            problem = preview.failure(self.target)
            if problem:
                for label in self.coords.values():
                    label.setText("")
                self.say(problem)
                return
            p = self.target.Position
            for axis, value in (("X", p.x), ("Y", p.y), ("Z", p.z)):
                self.coords[axis].setText(measure.fmt(value, "coordinate", 3, self.unit))
            self.hint("")
        except Exception as exc:
            warn("Center of Mass: %s" % exc)
            self.say("⚠ %s" % exc)

    def position(self):
        return self.target.Position if self.target is not None else None

    def accept(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self._apply_now()
            problem = (
                preview.failure(self.target) if self.target is not None else "Nothing to measure."
            )
            if problem:
                self.say(problem)
                return False
            label = self.target.Label
            done = self.finish_ok()
            log("%s kept" % label)
            return done
        except Exception as exc:
            warn("Center of Mass OK: %s" % exc)
            self.say("⚠ %s" % exc)
            return False


def selected_analysis():
    for sel in Gui.Selection.getSelectionEx():
        if analysis.is_kind(sel.Object, analysis.COM_KIND):
            return sel.Object
    return None


def start():
    chosen = selected_analysis()
    picks = hole_common.picks()
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        commands.tell("Open or start a design first.")
        return None
    if chosen is not None:
        return edit(chosen)
    panel = CenterOfMassPanel(App.ActiveDocument, initial=picks)
    Gui.Control.showDialog(panel)
    log("Center of Mass started")
    return panel


def edit(target):
    """Open a stored Center of Mass again (browser double-click, EDITORS). Never raises."""
    try:
        if not commands.finish_open_dialog():
            return None
        panel = CenterOfMassPanel(target.Document, target=target)
        Gui.Control.showDialog(panel)
        return panel
    except Exception as exc:
        warn("Center of Mass could not open: %s" % exc)
        return None


class CenterOfMassCommand:
    def GetResources(self):
        return {
            "MenuText": "Center of Mass",
            "ToolTip": "Mark the centre of mass of the bodies you pick",
            "Pixmap": ui_icon_path("center_of_mass"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Center of Mass failed to start: %s" % exc)


COMMANDS = {"SciForge_CenterOfMass": CenterOfMassCommand}
EDITORS = {"SciForge::" + analysis.COM_KIND: edit}
