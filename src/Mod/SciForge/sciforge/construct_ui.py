# SPDX-License-Identifier: LGPL-2.1-or-later
"""Construct menu commands (SciForge_Construct_<Key>) and their dialog.

Select the geometry before or after starting the command (Fusion allows
both). Planes that are placed by a distance or angle get a field and, for
distances, the drag arrow.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, construct, log, ui_icon_path, warn
from .compat import QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel

ICONS = {
    "OffsetPlane": "offset_plane",
    "PlaneAtAngle": "plane_angle",
    "TangentPlane": "tangent_plane",
    "Midplane": "midplane",
    "PerpendicularPlane": "plane_perp",
    "PlaneTwoEdges": "plane_two_edges",
    "PlaneThreePoints": "plane_three_points",
    "PlaneAlongPath": "plane_along_path",
    "AxisCylinder": "axis",
    "AxisNormal": "axis",
    "AxisTwoPlanes": "axis",
    "AxisTwoPoints": "axis_two_points",
    "AxisEdge": "axis_edge",
}


def _selected_refs():
    refs = []
    for sel in Gui.Selection.getSelectionEx():
        for name in sel.SubElementNames:
            refs.append((sel.Object, name.split(".")[-1]))
        if not sel.SubElementNames:
            refs.append((sel.Object, ""))
    return refs


class ConstructPanel(Panel):
    last = None

    def __init__(self, doc, key):
        self.key = key
        self.title = construct.PRESETS[key][0]
        self.icon = ICONS.get(key, "point")
        super().__init__(doc, self.title)
        ConstructPanel.last = self
        self.body = commands.ensure_body()
        self.datum = None
        self.dragger = None
        self.observer = None
        self.needed = construct.NEEDS.get(key, 1)
        self.what = QtWidgets.QLabel()
        self.layout.addRow(self.what)
        self.field = None
        if key in construct.DISTANCE:
            self.field = DistanceField(0.0 if key != "OffsetPlane" else 10.0, on_change=self._value)
            self.layout.addRow("Distance", self.field.widget)
        elif key in construct.ANGLE:
            self.field = DistanceField(45.0, unit="deg", on_change=self._value)
            self.layout.addRow("Angle", self.field.widget)
        self.finish_layout()
        refs = _selected_refs()
        if len(refs) >= self.needed:
            self._create(refs[: self.needed])
        else:
            self.refs = refs
            self._prompt()
            self._watch()

    def feature(self):
        return self.datum

    def _prompt(self):
        self.what.setText(
            "Select %d item(s) for %s (%d selected)." % (self.needed, self.title, len(self.refs))
        )

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                if panel.datum is not None:
                    return
                panel.refs = _selected_refs()
                if len(panel.refs) >= panel.needed:
                    panel._unwatch()
                    panel._create(panel.refs[: panel.needed])
                else:
                    panel._prompt()

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    def _create(self, refs):
        try:
            offset = self.field.value() if self.field and self.key in construct.DISTANCE else 0.0
            self.datum = construct.make(self.body, self.key, refs, offset)
            if self.key in construct.ANGLE:
                self._value(self.field.value())
            self.doc.recompute()
            self.what.setText("%s on the selection." % self.title)
            self.show_status()
            if self.key in construct.DISTANCE:
                self._make_dragger()
        except construct.ConstructError as exc:
            self.message.setText(str(exc))
        except Exception as exc:
            self.message.setText("Could not create %s: %s" % (self.title, exc))
        Gui.Selection.clearSelection()

    def _make_dragger(self):
        try:
            base = self.datum.Placement
            normal = base.Rotation.multVec(App.Vector(0, 0, 1))
            origin = base.Base - normal * self.datum.AttachmentOffset.Base.z
            self.dragger = ArrowDragger(
                origin,
                normal,
                self.datum.AttachmentOffset.Base.z,
                8.0,
                on_drag=self._dragged,
                on_release=self._dragged,
            )
        except Exception as exc:
            warn("construct arrow unavailable: %s" % exc)

    def _dragged(self, value):
        value = round(value, 2)
        self.field.set_value(value)
        self._value(value)

    def _value(self, value):
        if self.datum is None:
            return
        offset = self.datum.AttachmentOffset
        if self.key in construct.ANGLE:
            rot = App.Rotation(App.Vector(1, 0, 0), value)
            self.datum.AttachmentOffset = App.Placement(offset.Base, rot)
        else:
            self.datum.AttachmentOffset = App.Placement(App.Vector(0, 0, value), offset.Rotation)
            if self.dragger:
                self.dragger.set_distance(value)
        self.schedule()

    def accept(self):
        if self.datum is None:
            self.message.setText("Select the geometry first.")
            return False
        return super().accept()

    def cleanup(self):
        self._unwatch()
        if self.dragger is not None:
            self.dragger.remove()
            self.dragger = None
        super().cleanup()


def _command_class(key):
    label = construct.PRESETS[key][0]

    class ConstructCommand:
        def GetResources(self):
            return {
                "MenuText": label,
                "ToolTip": label + " (select geometry before or after)",
                "Pixmap": ui_icon_path(ICONS.get(key, "point")),
            }

        def IsActive(self):
            return App.ActiveDocument is not None and not Gui.Control.activeDialog()

        def Activated(self):
            try:
                Gui.Control.showDialog(ConstructPanel(App.ActiveDocument, key))
                log("%s started" % label)
            except Exception as exc:
                warn("%s failed to start: %s" % (label, exc))

    return ConstructCommand


def command_classes():
    return {"SciForge_Construct_" + key: _command_class(key) for key in construct.PRESETS}
