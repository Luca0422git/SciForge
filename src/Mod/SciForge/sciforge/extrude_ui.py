# SPDX-License-Identifier: LGPL-2.1-or-later
"""Extrude command (E) with Fusion's one-dialog workflow.

Pick a sketch (select it, or the newest unused sketch of the active body is
taken), then drag the arrow or type a distance. Dragging into existing
material switches the operation to Cut automatically, as Fusion does, unless
you picked an operation yourself.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, extrude, log, ui_icon_path, warn
from .compat import QtWidgets
from .taskui import ArrowDragger, DistanceField, Panel

DIRECTION_LABELS = [
    ("One Side", "one_side"),
    ("Two Sides", "two_sides"),
    ("Symmetric", "symmetric"),
]
EXTENT_LABELS = [("Distance", "distance"), ("All", "all")]
OPERATION_LABELS = [("Join", "join"), ("Cut", "cut"), ("New Body", "new_body")]


def _used_profiles(body):
    used = set()
    for obj in body.Group:
        profile = getattr(obj, "Profile", None)
        if isinstance(profile, tuple) and profile:
            profile = profile[0]
        if profile is not None and hasattr(profile, "Name"):
            used.add(profile.Name)
    return used


def pick_sketch(body):
    """The selected sketch, else the newest sketch of the body no feature uses yet."""
    for sel in Gui.Selection.getSelectionEx():
        if sel.Object.TypeId == "Sketcher::SketchObject":
            return sel.Object
    if body is None:
        return None
    used = _used_profiles(body)
    for obj in reversed(body.Group):
        if obj.TypeId == "Sketcher::SketchObject" and obj.Name not in used:
            return obj
    return None


def _combo(pairs, current):
    box = QtWidgets.QComboBox()
    for label, value in pairs:
        box.addItem(label, value)
    box.setCurrentIndex([v for _, v in pairs].index(current))
    return box


class ExtrudePanel(Panel):
    title = "Extrude"
    icon = "extrude"
    last = None

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Extrude" if feature is None else "Edit Extrude")
        ExtrudePanel.last = self
        self.body = (
            commands.active_body() if feature is None else feature.getParentGeoFeatureGroup()
        )
        self.target = feature
        self.sketch = None
        self.dragger = None
        self.observer = None
        self.user_picked_operation = feature is not None
        self.options = {
            "operation": "join",
            "direction": "one_side",
            "extent": "distance",
            "distance": 10.0,
            "distance2": 10.0,
            "taper": 0.0,
        }
        if feature is not None:
            self._read(feature)
        tip = self.body.Tip if self.body is not None else None
        if feature is not None:
            tip = feature.BaseFeature
        self.base_shape = tip.Shape.copy() if tip is not None and not tip.Shape.isNull() else None

        self.profile = QtWidgets.QLabel("Select a sketch to extrude")
        self.layout.addRow("Profile", self.profile)
        self.direction = _combo(DIRECTION_LABELS, self.options["direction"])
        self.layout.addRow("Direction", self.direction)
        self.extent = _combo(EXTENT_LABELS, self.options["extent"])
        self.layout.addRow("Extent", self.extent)
        self.distance = DistanceField(self.options["distance"], on_change=self._distance_typed)
        self.layout.addRow("Distance", self.distance.widget)
        self.distance2 = DistanceField(self.options["distance2"], on_change=self._changed)
        self.distance2_label = QtWidgets.QLabel("Distance 2")
        self.layout.addRow(self.distance2_label, self.distance2.widget)
        self.taper = DistanceField(self.options["taper"], unit="deg", on_change=self._changed)
        self.layout.addRow("Taper Angle", self.taper.widget)
        self.operation = _combo(OPERATION_LABELS, self.options["operation"])
        self.layout.addRow("Operation", self.operation)
        self.finish_layout()
        self.direction.currentIndexChanged.connect(self._changed)
        self.extent.currentIndexChanged.connect(self._changed)
        self.operation.activated.connect(self._operation_picked)
        self._update_visibility()

        if feature is not None:
            self.sketch = (
                feature.Profile[0] if isinstance(feature.Profile, tuple) else feature.Profile
            )
            self.profile.setText(self.sketch.Label)
            if self.body is not None and self.body.Tip is not feature:
                self.operation.setEnabled(False)
                self.operation.setToolTip(
                    "Join/Cut can only be changed on the last step of the "
                    "timeline for now. Roll the timeline marker here first."
                )
            self._make_dragger()
        elif not self._start():
            self._watch_selection()

    def feature(self):
        return self.target

    def _read(self, feature):
        cut = feature.TypeId == "PartDesign::Pocket"
        sign = 1.0 if (feature.Reversed if cut else not feature.Reversed) else -1.0
        self.options.update(
            {
                "operation": "cut" if cut else "join",
                "direction": {"Symmetric": "symmetric", "Two sides": "two_sides"}.get(
                    feature.SideType, "one_side"
                ),
                "extent": "all" if feature.Type in ("ThroughAll", "UpToLast") else "distance",
                "distance": sign * feature.Length.Value,
                "distance2": feature.Length2.Value,
                "taper": feature.TaperAngle.Value,
            }
        )

    # -- start -------------------------------------------------------------------
    def _start(self):
        if self.body is None:
            self.message.setText("Create a sketch first (Create Sketch).")
            return True
        sketch = pick_sketch(self.body)
        if sketch is None:
            return False
        self.sketch = sketch
        self.profile.setText(sketch.Label)
        self._auto_operation()
        try:
            self.target = extrude.make(self.body, sketch, self.options)
        except extrude.ExtrudeError as exc:
            self.message.setText(str(exc))
            return True
        self._make_dragger()
        self.schedule()
        return True

    def _watch_selection(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                if panel.target is None and panel._start():
                    panel._unwatch()

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    def _make_dragger(self):
        try:
            placement = self.sketch.getGlobalPlacement()
            normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
            center = self.sketch.Shape.BoundBox.Center
            size = max(4.0, min(self.sketch.Shape.BoundBox.DiagonalLength * 0.15, 30.0))
            self.dragger = ArrowDragger(
                center,
                normal,
                self.options["distance"],
                size,
                on_drag=self._dragged,
                on_release=self._dragged,
            )
        except Exception as exc:
            warn("extrude arrow unavailable: %s" % exc)

    # -- changes -----------------------------------------------------------------
    def _collect(self):
        self.options["direction"] = self.direction.currentData()
        self.options["extent"] = self.extent.currentData()
        self.options["distance"] = self.distance.value()
        self.options["distance2"] = self.distance2.value()
        self.options["taper"] = self.taper.value()
        self.options["operation"] = self.operation.currentData()

    def _auto_operation(self):
        """Fusion: extruding into material becomes a cut, out of it a join."""
        if self.user_picked_operation:
            return
        into = extrude.goes_into_material(self.base_shape, self.sketch, self.options["distance"])
        wanted = "cut" if into else ("join" if self.base_shape is not None else "new_body")
        if wanted == "new_body":
            wanted = "join"  # the first solid: Fusion says New Body; same result here
        self.options["operation"] = wanted
        self.operation.setCurrentIndex([v for _, v in OPERATION_LABELS].index(wanted))

    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _distance_typed(self, value):
        if self.dragger:
            self.dragger.set_distance(value)
        self._changed()

    def _dragged(self, value):
        value = round(value, 2)
        self.distance.set_value(value)
        self._changed()

    def _update_visibility(self):
        two = self.direction.currentData() == "two_sides"
        self.distance2.widget.setVisible(two)
        self.distance2_label.setVisible(two)
        self.distance.widget.setEnabled(self.extent.currentData() == "distance")

    def _changed(self, *_):
        self._update_visibility()
        if self.target is None:
            return
        self._collect()
        self._auto_operation()
        self._collect()
        try:
            self.target = extrude.switch(self.body, self.target, self.options)
        except Exception as exc:
            self.message.setText(str(exc))
            return
        self.schedule()

    def accept(self):
        if self.target is None:
            self.message.setText("Select a sketch to extrude.")
            return False
        return super().accept()

    def cleanup(self):
        self._unwatch()
        if self.dragger is not None:
            self.dragger.remove()
            self.dragger = None
        super().cleanup()


class ExtrudeCommand:
    def GetResources(self):
        return {
            "MenuText": "Extrude",
            "ToolTip": "Extrude a sketch: join, cut or new body, one side, "
            "two sides or symmetric, with a live preview (E)",
            "Pixmap": ui_icon_path("extrude"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None and not Gui.Control.activeDialog()

    def Activated(self):
        try:
            Gui.Control.showDialog(ExtrudePanel(App.ActiveDocument))
            log("extrude started")
        except Exception as exc:
            warn("Extrude failed to start: %s" % exc)


def edit(feature):
    """Open the Extrude dialog on an existing Pad/Pocket (timeline double-click)."""
    Gui.Control.showDialog(ExtrudePanel(feature.Document, feature=feature))
