# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Interference, Fusion-style.

Click two or more bodies (a click on a picked body drops it), tick Include Coincident Faces to
also list bodies that only touch, press Compute: every pair that overlaps is listed with the
volume they share, and the shared volume is shown in red (seen through the parts). OK keeps
the result in the browser's Analysis folder (eye to show / hide); it is computed again when
the model changes. Select it in the browser and run Interference again to change it. Cancel /
Esc leave nothing.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import analysis, bodypick, commands, hole_common, log, measure, preview, warn
from . import ui_icon_path
from .compat import QtCore, QtWidgets

RED = (0.92, 0.20, 0.18)
CONTACT = (0.98, 0.65, 0.20)


def _units(doc):
    try:
        from . import browser_ui

        return browser_ui.units(doc)
    except Exception:
        return "mm"


class ViewProviderInterference:
    """Draws the overlaps in red over the parts. Saved documents store
    "sciforge.interference_ui.ViewProviderInterference"."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        bodypick.on_top(self.root)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.content = coin.SoSeparator()
        self.root.addChild(self.content)
        vobj.addDisplayMode(self.root, "Overlap")
        self._update(vobj.Object)

    def _update(self, obj):
        from pivy import coin

        try:
            self.content.removeAllChildren()
            shape = obj.Overlap
            if shape is None or shape.isNull():
                return
            for solid in shape.Solids:
                for face in solid.Faces:
                    self._face(coin, face, RED, 0.35)
            if not shape.Solids:
                for face in shape.Faces:
                    self._face(coin, face, CONTACT, 0.2)
        except Exception as exc:
            warn("Interference display: %s" % exc)

    def _face(self, coin, face, color, transparency):
        points, triangles = face.tessellate(max(0.01, face.BoundBox.DiagonalLength / 300.0))
        if not triangles:
            return
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.5 for c in color])
        material.transparency.setValue(transparency)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
        faces = coin.SoIndexedFaceSet()
        index = []
        for a, b, c in triangles:
            index += [a, b, c, -1]
        faces.coordIndex.setValues(0, len(index), index)
        sep.addChild(material)
        sep.addChild(hints)
        sep.addChild(coords)
        sep.addChild(faces)
        self.content.addChild(sep)

    def getDisplayModes(self, vobj):
        return ["Overlap"]

    def getDefaultDisplayMode(self):
        return "Overlap"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop == "Overlap":
            self._update(obj)

    def onChanged(self, vobj, prop):
        pass

    def getIcon(self):
        return ui_icon_path("interference")

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def make_view(obj):
    if App.GuiUp and obj.ViewObject is not None:
        ViewProviderInterference(obj.ViewObject)


class InterferencePanel(bodypick.BodyPickPanel):
    title = "Interference"
    icon = "interference"
    last = None

    def __init__(self, doc, target=None, initial=()):
        name = ("Edit %s" % target.Label) if target is not None else self.title
        super().__init__(doc, name)
        InterferencePanel.last = self
        self.target = target
        self.editing = target is not None
        self.unit = _units(doc)
        self.computed = target is not None
        if target is not None:
            self.picked = [o for o in target.Bodies if o is not None]
        else:
            for obj, _short, _point in initial:
                body = analysis.body_of(obj)
                if body is not None and body not in self.picked:
                    self.picked.append(body)
        self.box = hole_common.SelectionField(self, 0, "Select")
        self.box.button.setObjectName("SciForgeInterference_bodies")
        self.box.button.setToolTip("Click the bodies to compare (two or more)")
        self.box.clear.setObjectName("SciForgeInterference_clear")
        self.layout.addRow("Bodies", self.box.widget)
        self.coincident = QtWidgets.QCheckBox("Include Coincident Faces")
        self.coincident.setObjectName("SciForgeInterference_coincident")
        self.coincident.setChecked(bool(target.IncludeCoincident) if target is not None else False)
        self.coincident.toggled.connect(self._coincident_toggled)
        self.layout.addRow(self.coincident)
        self.compute = QtWidgets.QPushButton("Compute")
        self.compute.setObjectName("SciForgeInterference_compute")
        self.compute.clicked.connect(self._compute_clicked)
        self.layout.addRow(self.compute)
        self.table = QtWidgets.QTreeWidget()
        self.table.setObjectName("SciForgeInterference_results")
        from .measure_ui import RESULTS_STYLE

        self.table.setStyleSheet(RESULTS_STYLE)
        self.table.setColumnCount(5)
        self.table.setHeaderLabels(["#", "Body 1", "Body 2", "Volume", "Create Body"])
        self.table.setRootIsDecorated(False)
        self.table.setMinimumHeight(140)
        self.table.itemChanged.connect(self._row_ticked)
        self.layout.addRow(self.table)
        # Fusion: the overlaps can be kept as bodies of their own (each row, or all)
        self.create_all = QtWidgets.QCheckBox("Create Bodies From Interferences")
        self.create_all.setObjectName("SciForgeInterference_create_all")
        self.create_all.setToolTip(
            "On OK, each ticked overlap becomes a new body (a body without history)"
        )
        self.create_all.toggled.connect(self._create_all_toggled)
        self.layout.addRow(self.create_all)
        self._ticking = False
        self.finish_layout()
        self.start_picking()
        self.box.set_active(True)
        if target is not None:
            self.box.set_text(self.picked_text("Select"))
            self._show_results()
        else:
            self.bodies_changed()

    def activate(self, _index):
        self.box.set_active(True)

    def clear_field(self, _index):
        try:
            self.picked = []
            self._sync()
            self.bodies_changed()
        except Exception as exc:
            warn("Interference: %s" % exc)

    def bodies_changed(self):
        self.box.set_text(self.picked_text("Select"))
        self.computed = False
        self.table.clear()
        if len(self.picked) < 2:
            self.hint("Click two or more bodies, then Compute.")
        else:
            self.hint("Press Compute to look for overlaps.")

    def _coincident_toggled(self, _on):
        self.computed = False
        self.table.clear()
        if len(self.picked) >= 2:
            self.hint("Press Compute to look for overlaps.")

    def _compute_clicked(self, *_):
        try:
            self.run()
        except Exception as exc:
            warn("Interference: %s" % exc)
            self.say("⚠ %s" % exc)

    def run(self):
        """Compare the picked bodies (the Compute button)."""
        if len(self.picked) < 2:
            self.say("Click two or more bodies, then Compute.")
            return False
        if self.target is None or not hole_common.alive(self.target):
            self.target = analysis.make_interference(
                self.doc, self.picked, self.coincident.isChecked()
            )
            make_view(self.target)
        else:
            analysis.set_bodies(self.target, self.picked)
            if bool(self.target.IncludeCoincident) != self.coincident.isChecked():
                self.target.IncludeCoincident = self.coincident.isChecked()
        preview.recompute(self.doc)
        problem = analysis.problem(self.target) or preview.failure(self.target)
        if problem:
            self.table.clear()
            self.say(problem)
            return False
        self.computed = True
        self._show_results()
        return True

    def _show_results(self):
        self._ticking = True
        try:
            self.table.clear()
            found = analysis.results(self.target) if self.target is not None else []
            for i, (a, b, volume) in enumerate(found, start=1):
                text = measure.fmt(volume, "volume", 3, self.unit) if volume > 0 else "touching"
                row = QtWidgets.QTreeWidgetItem(self.table, [str(i), a, b, text, ""])
                if volume > 0:  # a body can only be made of a shared volume
                    row.setFlags(row.flags() | QtCore.Qt.ItemIsUserCheckable)
                    on = self.create_all.isChecked()
                    row.setCheckState(4, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
            for column in range(5):
                self.table.resizeColumnToContents(column)
        finally:
            self._ticking = False
        problem = analysis.problem(self.target) if self.target is not None else ""
        if problem:
            self.say(problem)
        elif found:
            self.hint("%d interference%s found." % (len(found), "" if len(found) == 1 else "s"))
        else:
            self.hint("No interference: the bodies do not overlap.")

    def rows(self):
        return [
            [self.table.topLevelItem(i).text(c) for c in range(4)]
            for i in range(self.table.topLevelItemCount())
        ]

    def _checkable(self):
        """The table rows that can become a body (the overlapping pairs), in order."""
        found = []
        for i in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(i)
            if row.flags() & QtCore.Qt.ItemIsUserCheckable:
                found.append(row)
        return found

    def ticked(self):
        """Indices (among the overlapping pairs) of the rows ticked to become bodies."""
        return [
            n for n, row in enumerate(self._checkable()) if row.checkState(4) == QtCore.Qt.Checked
        ]

    def tick_row(self, index, on=True):
        """Tick the Create Body box of overlap `index` (the scenarios click like a person
        would through this)."""
        rows = self._checkable()
        if 0 <= index < len(rows):
            rows[index].setCheckState(4, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)

    def _row_ticked(self, item, column):
        if self._ticking or column != 4:
            return
        try:
            rows = self._checkable()
            every = bool(rows) and all(r.checkState(4) == QtCore.Qt.Checked for r in rows)
            if self.create_all.isChecked() != every:
                self._ticking = True
                try:
                    self.create_all.setChecked(every)
                finally:
                    self._ticking = False
            self._say_bodies()
        except Exception as exc:
            warn("Interference: %s" % exc)

    def _create_all_toggled(self, on):
        if self._ticking:
            return
        try:
            self._ticking = True
            try:
                for row in self._checkable():
                    row.setCheckState(4, QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
            finally:
                self._ticking = False
            self._say_bodies()
        except Exception as exc:
            warn("Interference: %s" % exc)

    def _say_bodies(self):
        count = len(self.ticked())
        if count:
            self.hint(
                "OK makes %d bod%s of the shared volume." % (count, "y" if count == 1 else "ies")
            )
        elif self.computed:
            self._show_results_hint()

    def _show_results_hint(self):
        found = analysis.results(self.target) if self.target is not None else []
        if found:
            self.hint("%d interference%s found." % (len(found), "" if len(found) == 1 else "s"))
        else:
            self.hint("No interference: the bodies do not overlap.")

    def schedule(self):
        pass  # nothing previews by itself: Compute does

    def accept(self):
        if self._closed:
            return True
        try:
            if not self.computed and len(self.picked) >= 2:
                if not self.run():
                    return False
            if self.target is None or not self.computed:
                self.say("Click two or more bodies, then Compute.")
                return False
            label = self.target.Label
            rows = self.ticked()
            made = []
            if rows:
                try:
                    made = analysis.create_bodies(self.target, rows)
                except analysis.AnalysisError as exc:
                    self.say(str(exc))
                    return False
                preview.recompute(self.doc)
            done = self.finish_ok()
            if made:
                log(
                    "%s: %s made of the interference%s"
                    % (label, ", ".join(b.Label for b in made), "" if len(rows) == 1 else "s")
                )
            log("%s kept" % label)
            return done
        except Exception as exc:
            warn("Interference OK: %s" % exc)
            self.say("⚠ %s" % exc)
            return False


def selected_analysis():
    for sel in Gui.Selection.getSelectionEx():
        if analysis.is_kind(sel.Object, analysis.INTERFERENCE_KIND):
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
    panel = InterferencePanel(App.ActiveDocument, initial=picks)
    Gui.Control.showDialog(panel)
    log("Interference started")
    return panel


def edit(target):
    """Open a stored Interference again (browser double-click, EDITORS). Never raises."""
    try:
        if not commands.finish_open_dialog():
            return None
        panel = InterferencePanel(target.Document, target=target)
        Gui.Control.showDialog(panel)
        return panel
    except Exception as exc:
        warn("Interference could not open: %s" % exc)
        return None


class InterferenceCommand:
    def GetResources(self):
        return {
            "MenuText": "Interference",
            "ToolTip": "Find where the bodies you pick overlap",
            "Pixmap": ui_icon_path("interference"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            start()
        except Exception as exc:
            warn("Interference failed to start: %s" % exc)


COMMANDS = {"SciForge_Interference": InterferenceCommand}
EDITORS = {"SciForge::" + analysis.INTERFERENCE_KIND: edit}
