# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Project to Surface in an open sketch: pick faces, then the curves, pick the
projection type, OK (the result: sketch_project.ProjectedCurves).

The picking runs on SciForge's sketch handler (sketch_draw.DrawTool): a click on a face
of a body adds it (again: removes it); after Next (or Enter) a click on a curve of the
sketch or an edge of a body adds the curve. The small panel at the top of the sketch
panel holds the counts, Projection Type (Closest Point / Along Vector), Next and
OK / Cancel; Enter is OK once curves are picked, Esc is Cancel. The picked faces and
curves are shown selected (FreeCAD's selection colour).
"""

import FreeCADGui as Gui

from . import log, warn
from . import sketch_draw as draw
from . import sketch_infer_core as icore
from . import sketch_project
from .compat import QtCore, QtWidgets


class ProjectToSurface(draw.DrawTool):
    title = "Project to Surface"
    command = "SciForge_SketchProjectToSurface"
    repeat = False

    def __init__(self, session):
        super().__init__(session)
        self.faces = []  # (object, "FaceN")
        self.curves = []  # (object, "EdgeN")
        self.kind = sketch_project.TYPES[0]
        self.box = None

    def steps(self):
        return 2

    def prompt(self):
        if self.step == 0:
            return "click the faces to project onto, then Next (or Enter)."
        return "click the sketch curves or edges to project, then OK (or Enter)."

    def start(self):
        super().start()
        try:
            self.box = ProjectBox(self)
        except Exception as exc:
            warn("Project to Surface: %s" % exc)
            self.box = None

    def stop(self):
        box, self.box = self.box, None
        if box is not None:
            box.close_box()
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        super().stop()

    def use_selection(self, selection):
        """Faces selected before the command count (Fusion takes a selection)."""
        try:
            for sel in Gui.Selection.getSelectionEx():
                if sel.Object is self.sketch:
                    continue
                for name in sel.SubElementNames:
                    short = name.rsplit(".", 1)[-1]
                    if short.startswith("Face"):
                        self._toggle(self.faces, sel.Object, short)
        except Exception:
            pass
        self._show()

    # -- picking ---------------------------------------------------------------------------
    def _object_at(self, pos):
        """(object, sub-element) of a body under the widget pixel, or None."""
        gl = self.session.gl
        view = self.session.view
        ratio = gl.devicePixelRatioF() or 1.0
        info = view.getObjectInfo((pos.x() * ratio, (gl.height() - pos.y()) * ratio))
        if not info:
            return None
        doc = self.sketch.Document
        obj = doc.getObject(info.get("Object", ""))
        component = str(info.get("Component", ""))
        if obj is None or obj is self.sketch or not component:
            return None
        return obj, component

    def _sketch_curve(self, snap):
        geo = self.geometry()
        tol = draw.pick_pixels() * self._px()
        best = None
        for index, curve in geo.hits:
            if index < 0 or not icore.near_curve(snap.raw, curve, tol):
                continue
            d = icore.curve_distance(snap.raw, curve)
            if best is None or d < best[1]:
                best = (index, d)
        return best[0] if best else None

    def released(self, press_snap, snap, moved):
        pos = self.press_pos
        if self.step == 0:
            found = self._object_at(pos) if pos is not None else None
            if found is None or not found[1].startswith("Face"):
                self.say("Project to Surface: click a face of the part.")
                return
            self._toggle(self.faces, found[0], found[1])
        else:
            geo = self._sketch_curve(press_snap)
            if geo is not None:
                self._toggle(self.curves, self.sketch, "Edge%d" % (geo + 1))
            else:
                found = self._object_at(pos) if pos is not None else None
                if found is None or not found[1].startswith(("Edge", "Vertex")):
                    self.say("Project to Surface: click a sketch curve or an edge of the part.")
                    return
                self._toggle(self.curves, found[0], found[1])
        self._show()

    @staticmethod
    def _toggle(items, obj, sub):
        item = (obj, sub)
        if item in items:
            items.remove(item)
        else:
            items.append(item)

    def _show(self):
        """The picked faces and curves selected (FreeCAD's selection colour)."""
        try:
            Gui.Selection.clearSelection()
            for obj, sub in self.faces + self.curves:
                Gui.Selection.addSelection(obj.Document.Name, obj.Name, sub)
        except Exception as exc:
            warn("Project to Surface: %s" % exc)
        if self.box is not None:
            self.box.refresh()

    def moved(self, snap):
        pass

    # -- steps -------------------------------------------------------------------------
    def go_on(self):
        """Next: from faces to curves."""
        if not self.faces:
            self.say("Project to Surface: click at least one face first.")
            return
        self.step = 1
        self._tell()
        if self.box is not None:
            self.box.refresh()

    def enter_without_values(self):
        if self.step == 0:
            self.go_on()
        else:
            self.accept_box()
        return True

    def on_finish(self):
        if self.step == 1 and self.curves:
            self.accept_box(stop=False)

    def accept_box(self, stop=True):
        """OK: make the projected curves (one undo step)."""
        if not self.faces:
            self.say("Project to Surface: click at least one face first.")
            return
        if not self.curves:
            self.say("Project to Surface: click the curves to project.")
            return
        faces = _grouped(self.faces)
        curves = _grouped(self.curves)
        direction = None
        if self.kind == sketch_project.TYPES[1]:
            direction = sketch_project.sketch_normal_towards(self.sketch, faces)
        doc = self.doc
        doc.openTransaction("Project to Surface")
        try:
            obj = sketch_project.make(self.sketch, faces, curves, self.kind, direction)
        except Exception as exc:
            doc.abortTransaction()
            self.say("Project to Surface: %s." % exc)
            log("Project to Surface: refused: %s" % exc)
            return
        doc.commitTransaction()
        log("Project to Surface: %s made" % obj.Label)
        if stop:
            self.stop()


def _grouped(items):
    """[(object, [subs])] from [(object, sub)] in pick order."""
    out = []
    for obj, sub in items:
        for entry in out:
            if entry[0] is obj:
                entry[1].append(sub)
                break
        else:
            out.append((obj, [sub]))
    return out


class ProjectBox(QtWidgets.QFrame):
    """The Project to Surface panel at the top of the sketch panel."""

    def __init__(self, tool):
        from . import sketch_palette

        panel = sketch_palette.sketch_panel()
        super().__init__(panel)
        self.tool = tool
        self.setObjectName("SciForgeProjectToSurface")
        self.setStyleSheet(sketch_palette.STYLE.replace("SciForgeSketchPalette", self.objectName()))
        layout = QtWidgets.QFormLayout(self)
        title = QtWidgets.QLabel("PROJECT TO SURFACE")
        title.setProperty("role", "title")
        layout.addRow(title)
        self.faces = QtWidgets.QLabel("")
        self.curves = QtWidgets.QLabel("")
        layout.addRow("Faces", self.faces)
        layout.addRow("Curves", self.curves)
        self.kind = QtWidgets.QComboBox()
        self.kind.setObjectName("SciForgeProjectType")
        self.kind.addItems(list(sketch_project.TYPES))
        self.kind.currentTextChanged.connect(self._kind)
        layout.addRow("Projection Type", self.kind)
        self.hint = QtWidgets.QLabel("")
        self.hint.setWordWrap(True)
        layout.addRow(self.hint)
        row = QtWidgets.QHBoxLayout()
        self.next = QtWidgets.QPushButton("Next")
        self.next.setObjectName("SciForgeProjectNext")
        self.next.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._next))
        self.ok = QtWidgets.QPushButton("OK")
        self.ok.setObjectName("SciForgeProjectOK")
        self.ok.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._ok))
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("SciForgeProjectCancel")
        cancel.clicked.connect(lambda: QtCore.QTimer.singleShot(0, self._cancel))
        for button in (self.next, self.ok, cancel):
            button.setFocusPolicy(QtCore.Qt.NoFocus)
            row.addWidget(button)
        layout.addRow(row)
        if panel is not None and panel.layout() is not None:
            panel.layout().insertWidget(0, self)
        self.show()
        self.refresh()

    def refresh(self):
        tool = self.tool
        self.faces.setText("%d selected" % len(tool.faces))
        self.curves.setText("%d selected" % len(tool.curves))
        self.next.setEnabled(tool.step == 0)
        self.ok.setEnabled(tool.step == 1 and bool(tool.curves))
        self.hint.setText(tool.prompt())

    def _kind(self, text):
        self.tool.kind = text

    def _next(self):
        try:
            self.tool.go_on()
        except Exception as exc:
            warn("Project to Surface: %s" % exc)

    def _ok(self):
        try:
            self.tool.accept_box()
        except Exception as exc:
            warn("Project to Surface: %s" % exc)

    def _cancel(self):
        try:
            self.tool.stop()
        except Exception as exc:
            warn("Project to Surface: %s" % exc)

    def close_box(self):
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass
