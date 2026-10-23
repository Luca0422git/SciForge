# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch > Project / Include > Isoparametric Curve (Fusion, March 2026) in an open sketch:
click a face of the part; its U (or V) curve through the clicked place is drawn at once
(purple preview). The small panel at the top of the sketch panel holds Direction (U / V),
Type (Single: one curve, its Distance from the face's first edge; Distributed: Count curves
spread evenly), OK and Cancel. Enter is OK, Esc is Cancel; a click on another face moves the
curves there. OK keeps them in the sketch (surface_iso.IsoparametricCurves, one undo step).
"""

from . import log, sketch_draw as draw, surface_iso, theme, warn
from . import surface_core as core
from .compat import QtCore, QtWidgets

PURPLE = (0.75, 0.52, 0.99)


class IsoparametricCurve(draw.DrawTool):
    title = "Isoparametric Curve"
    command = "SciForge_SketchIsoparametricCurve"
    repeat = False

    def __init__(self, session):
        super().__init__(session)
        self.face = None  # (object, "FaceN")
        self.direction = "U"
        self.mode = "Single"
        self.distance = 0.0
        self.count = 3
        self.box = None
        self.overlay = None
        self.problem = ""

    def steps(self):
        return 1

    def prompt(self):
        if self.face is None:
            return "click a face of the part: its curve through that place."
        return "OK (or Enter) keeps the curves; a click on a face moves them there."

    def start(self):
        super().start()
        try:
            from .surface_pick import ShapeOverlay

            self.overlay = ShapeOverlay(self.session.view, on_top=True)
        except Exception as exc:
            warn("Isoparametric Curve: preview unavailable: %s" % exc)
        try:
            self.box = IsoBox(self)
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)
            self.box = None

    def stop(self):
        box, self.box = self.box, None
        if box is not None:
            box.close_box()
        overlay, self.overlay = self.overlay, None
        if overlay is not None:
            try:
                overlay.remove()
            except Exception:
                pass
        super().stop()

    def use_selection(self, selection):
        pass

    # -- picking ---------------------------------------------------------------------------
    def _object_at(self, pos):
        gl = self.session.gl
        view = self.session.view
        ratio = gl.devicePixelRatioF() or 1.0
        info = view.getObjectInfo((pos.x() * ratio, (gl.height() - pos.y()) * ratio))
        if not info:
            return None
        obj = self.sketch.Document.getObject(info.get("Object", ""))
        component = str(info.get("Component", ""))
        if obj is None or obj is self.sketch or not component:
            return None
        point = (info.get("x", 0.0), info.get("y", 0.0), info.get("z", 0.0))
        return obj, component, point

    def released(self, press_snap, snap, moved):
        pos = self.press_pos
        found = self._object_at(pos) if pos is not None else None
        if found is None or not found[1].startswith("Face"):
            self.say("Isoparametric Curve: click a face of the part.")
            return
        obj, sub, point = found
        self.face = (obj, sub)
        try:
            face = obj.Shape.getElement(sub)
            self.distance = round(surface_iso.distance_of_point(face, self.direction, point), 3)
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)
        self.refresh()

    def moved(self, snap):
        pass

    # -- the curves --------------------------------------------------------------------------
    def curves(self):
        """The curves the choices give now (raises SurfaceError with the reason)."""
        if self.face is None:
            raise core.NeedsPick("Click a face of the part.")
        face = self.face[0].Shape.getElement(self.face[1])
        values = surface_iso.fractions(face, self.direction, self.mode, self.distance, self.count)
        return surface_iso.iso_edges(face, self.direction, values)

    def refresh(self):
        """Redraw the preview and the panel after a change."""
        self.problem = ""
        edges = []
        try:
            edges = self.curves() if self.face is not None else []
        except core.SurfaceError as exc:
            self.problem = str(exc)
        except Exception as exc:
            self.problem = "These curves cannot be made (%s)." % exc
        if self.overlay is not None:
            try:
                import Part

                shapes = [Part.makeCompound(edges)] if edges else []
                self.overlay.show("iso", shapes, PURPLE, 0.0, 3.0)
            except Exception as exc:
                warn("Isoparametric Curve: %s" % exc)
        self.preview_count = len(edges)
        if self.box is not None:
            self.box.refresh()

    def enter_without_values(self):
        self.accept_box()
        return True

    def on_finish(self):
        if self.face is not None and not self.problem:
            self.accept_box(stop=False)

    def accept_box(self, stop=True):
        """OK: keep the curves (one undo step)."""
        if self.face is None:
            self.say("Isoparametric Curve: click a face of the part first.")
            return
        doc = self.doc
        doc.openTransaction("Isoparametric Curve")
        try:
            obj = surface_iso.make(
                self.sketch, self.face, self.direction, self.mode, self.distance, self.count
            )
        except Exception as exc:
            doc.abortTransaction()
            self.problem = str(exc)
            self.say("Isoparametric Curve: %s" % exc)
            log("Isoparametric Curve: refused: %s" % exc)
            if self.box is not None:
                self.box.refresh()
            return
        doc.commitTransaction()
        self.made = obj
        if stop:
            self.stop()


class IsoBox(theme.OwnBackground, QtWidgets.QFrame):
    """The Isoparametric Curve panel at the top of the sketch panel."""

    def __init__(self, tool):
        from . import sketch_palette

        panel = sketch_palette.sketch_panel()
        super().__init__(panel)
        self.tool = tool
        self.setObjectName("SciForgeIsoCurve")
        self.setStyleSheet(sketch_palette.STYLE.replace("SciForgeSketchPalette", self.objectName()))
        layout = QtWidgets.QFormLayout(self)
        title = QtWidgets.QLabel("ISOPARAMETRIC CURVE")
        title.setProperty("role", "title")
        layout.addRow(title)
        self.face = QtWidgets.QLabel("")
        layout.addRow("Face", self.face)
        self.direction = QtWidgets.QComboBox()
        self.direction.setObjectName("SciForgeIsoDirection")
        self.direction.addItems(list(surface_iso.DIRECTIONS))
        self.direction.currentTextChanged.connect(lambda t: self._set("direction", t))
        layout.addRow("Direction", self.direction)
        self.mode = QtWidgets.QComboBox()
        self.mode.setObjectName("SciForgeIsoType")
        self.mode.addItems(list(surface_iso.MODES))
        self.mode.currentTextChanged.connect(lambda t: self._set("mode", t))
        layout.addRow("Type", self.mode)
        self.distance = QtWidgets.QDoubleSpinBox()
        self.distance.setObjectName("SciForgeIsoDistance")
        self.distance.setRange(0.0, 1e6)
        self.distance.setDecimals(3)
        self.distance.setSuffix(" mm")
        self.distance.valueChanged.connect(lambda v: self._set("distance", float(v)))
        self.distance_caption = QtWidgets.QLabel("Distance")
        layout.addRow(self.distance_caption, self.distance)
        self.count = QtWidgets.QSpinBox()
        self.count.setObjectName("SciForgeIsoCount")
        self.count.setRange(1, core.MAX_ISO_COUNT)
        self.count.setValue(tool.count)
        self.count.valueChanged.connect(lambda v: self._set("count", int(v)))
        self.count_caption = QtWidgets.QLabel("Count")
        layout.addRow(self.count_caption, self.count)
        self.hint = QtWidgets.QLabel("")
        self.hint.setObjectName("SciForgeIsoHint")
        self.hint.setWordWrap(True)
        layout.addRow(self.hint)
        row = QtWidgets.QHBoxLayout()
        self.ok = QtWidgets.QPushButton("OK")
        self.ok.setObjectName("SciForgeIsoOK")
        self.ok.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._ok))
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("SciForgeIsoCancel")
        cancel.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._cancel))
        for button in (self.ok, cancel):
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            row.addWidget(button)
        layout.addRow(row)
        if panel is not None and panel.layout() is not None:
            panel.layout().insertWidget(0, self)
        self.show()
        self.refresh()

    def _set(self, key, value):
        try:
            setattr(self.tool, key, value)
            if key == "direction" and self.tool.face is not None:
                self.tool.distance = min(self.tool.distance, self._width())
            self.tool.refresh()
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)

    def _width(self):
        try:
            obj, sub = self.tool.face
            face = obj.Shape.getElement(sub)
            return surface_iso.lengths(face, self.tool.direction)[-1]
        except Exception:
            return 1e6

    def refresh(self):
        tool = self.tool
        self.face.setText(tool.face[0].Label + " " + tool.face[1] if tool.face else "Select")
        single = tool.mode == "Single"
        for widget in (self.distance, self.distance_caption):
            widget.setVisible(single)
        for widget in (self.count, self.count_caption):
            widget.setVisible(not single)
        self.distance.blockSignals(True)
        self.distance.setValue(tool.distance)
        self.distance.blockSignals(False)
        if tool.problem:
            self.hint.setText("⚠ " + tool.problem)
        else:
            self.hint.setText(tool.prompt())
        self.ok.setEnabled(tool.face is not None and not tool.problem)

    def _ok(self):
        try:
            self.tool.accept_box()
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)

    def _cancel(self):
        try:
            self.tool.stop()
        except Exception as exc:
            warn("Isoparametric Curve: %s" % exc)

    def close_box(self):
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass


def _command(tool, icon, tip):
    from .sketch_draw_ui import _command as make

    return make(tool, icon, tip)


COMMANDS = {
    "SciForge_SketchIsoparametricCurve": _command(
        IsoparametricCurve,
        "isocurve",
        "The U or V curves of a face of the part as sketch curves: click the face",
    ),
}
