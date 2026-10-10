# SPDX-License-Identifier: LGPL-2.1-or-later
"""SKETCH tab commands that FreeCAD's Sketcher does not do the Fusion way.

- Finish Sketch: always closes the sketch, also with a drawing tool running.
- Circumscribed / Inscribed Polygon: 6 sides, no "how many sides?" pop-up; the
  number of sides is changed in the panel on the right (or U / J) while drawing.
- Offset (O): with nothing selected it waits for you to click a curve; the whole
  connected chain is offset, like Fusion's chain selection.
- Include 3D Geometry: brings part edges into the sketch as reference curves.

Every command explains next to the mouse when it cannot start (no sketch open).
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, sketch_mode, ui_icon_path, warn
from .compat import QtCore

NO_SKETCH = "%s works inside a sketch: click Create Sketch (or edit a sketch) first."


def _in_sketch(title):
    sketch = sketch_mode.editing_sketch()
    if sketch is None:
        commands.tell(NO_SKETCH % title)
    return sketch


class _SketchCommand:
    title = ""
    tip = ""
    icon = ""

    def GetResources(self):
        res = {"MenuText": self.title, "ToolTip": self.tip}
        if self.icon:
            res["Pixmap"] = ui_icon_path(self.icon)
        return res

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s failed: %s" % (self.title, exc))

    def run(self):
        raise NotImplementedError


class FinishSketch(_SketchCommand):
    title = "Finish Sketch"
    tip = "Close the sketch and go back to the 3D model (also with a drawing tool running)"
    icon = "finish_sketch"

    def run(self):
        if not sketch_mode.finish_sketch():
            commands.tell("No sketch is open.")


class SketchLine(_SketchCommand):
    title = "Line"
    tip = (
        "Lines joined end to end: click point after point; Esc (or a click on the "
        "start point) ends the chain (L)"
    )
    icon = "sk_line"

    def run(self):
        if _in_sketch(self.title) is None:
            return
        # Fusion's Line keeps going from the last point: FreeCAD's polyline tool
        Gui.runCommand("Sketcher_CreatePolyline")


class _Polygon(_SketchCommand):
    circumscribed = True

    def run(self):
        if _in_sketch(self.title) is None:
            return
        sketch_mode.start_polygon(self.circumscribed)
        log(
            "%s: click the centre, then %s (6 sides; change them in the panel or U / J)"
            % (self.title, "the middle of an edge" if self.circumscribed else "a corner")
        )


class PolygonCircumscribed(_Polygon):
    title = "Circumscribed Polygon"
    tip = (
        "Polygon around a circle: click the centre, then the middle of an edge. "
        "6 sides; change the number in the panel on the right or with U / J"
    )
    icon = "sk_polygon"
    circumscribed = True


class PolygonInscribed(_Polygon):
    title = "Inscribed Polygon"
    tip = (
        "Polygon inside a circle: click the centre, then a corner. "
        "6 sides; change the number in the panel on the right or with U / J"
    )
    icon = "sk_polygon"
    circumscribed = False


# -- Offset -------------------------------------------------------------------------
def selected_curves(sketch):
    """0-based indices of the sketch's own curves that are selected."""
    ids = []
    for sel in Gui.Selection.getSelectionEx():
        if sel.Object is not sketch:
            continue
        for name in sel.SubElementNames:
            short = name.rsplit(".", 1)[-1]
            if short.startswith("Edge"):
                try:
                    ids.append(int(short[4:]) - 1)
                except ValueError:
                    pass
    return ids


def run_offset(sketch, ids):
    """Select the whole chain of the picked curves and start FreeCAD's offset tool
    (drag or type the distance, click to place)."""
    from . import sketch_regions

    chain = sketch_regions.connected_chain(sketch, ids)
    Gui.Selection.clearSelection()
    for index in chain:
        Gui.Selection.addSelection(sketch.Document.Name, sketch.Name, "Edge%d" % (index + 1))
    Gui.runCommand("Sketcher_Offset")
    log("offset: %d curve(s); move the mouse or type the distance, then click" % len(chain))


class _WaitForCurve:
    """Offset with nothing selected: wait for a click on a sketch curve."""

    current = None

    def __init__(self, sketch):
        if _WaitForCurve.current is not None:
            _WaitForCurve.current.stop()
        _WaitForCurve.current = self
        self.sketch = sketch
        self.active = True
        Gui.Selection.addObserver(self)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    def addSelection(self, doc, obj, sub, pnt):
        QtCore.QTimer.singleShot(30, self._picked)

    def _check(self):
        # stop waiting when the sketch closes or another tool starts
        if sketch_mode.editing_sketch() is not self.sketch:
            self.stop()

    def _picked(self):
        if not self.active:
            return
        try:
            ids = selected_curves(self.sketch)
            if not ids:
                return
            self.stop()
            run_offset(self.sketch, ids)
        except Exception as exc:
            self.stop()
            warn("Offset failed: %s" % exc)

    def stop(self):
        self.active = False
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            Gui.Selection.removeObserver(self)
        except Exception:
            pass
        if _WaitForCurve.current is self:
            _WaitForCurve.current = None


def stop_waiting():
    if _WaitForCurve.current is not None:
        _WaitForCurve.current.stop()


class SketchOffset(_SketchCommand):
    title = "Offset"
    tip = "Offset curves: click a curve (its connected chain is used), then drag or type the distance (O)"
    icon = "sk_offset"

    def run(self):
        sketch = _in_sketch(self.title)
        if sketch is None:
            return
        if not sketch.Geometry:
            commands.tell("Offset: draw some curves first.")
            return
        ids = selected_curves(sketch)
        if ids:
            run_offset(sketch, ids)
            return
        _WaitForCurve(sketch)
        commands.tell("Offset: click a curve of the sketch.")


# -- Project / Include -----------------------------------------------------------------
class SketchProject(_SketchCommand):
    title = "Project"
    tip = "Project edges or faces of the part onto the sketch: click them (P)"
    icon = "sk_project"

    def run(self):
        if _in_sketch(self.title) is None:
            return
        stop_waiting()
        Gui.runCommand("Sketcher_Projection")
        commands.tell("Project: click edges or faces of the part. Esc when done.")


class SketchInclude3D(_SketchCommand):
    title = "Include 3D Geometry"
    tip = (
        "Bring edges or points of the part into the sketch as reference curves "
        "(they do not make profiles). SciForge sketches are flat, so edges that are "
        "not in the sketch plane are projected onto it."
    )
    icon = "sk_project"

    def run(self):
        if _in_sketch(self.title) is None:
            return
        stop_waiting()
        path = sketch_mode.SKETCHER_GENERAL
        group = App.ParamGet(path)
        before = group.GetBool("AlwaysExtGeoReference", False)
        group.SetBool("AlwaysExtGeoReference", True)  # read once when the tool starts
        try:
            Gui.runCommand("Sketcher_Projection")
        finally:
            group.SetBool("AlwaysExtGeoReference", before)
        commands.tell("Include 3D Geometry: click edges or points of the part. Esc when done.")


COMMANDS = {
    "SciForge_FinishSketch": FinishSketch,
    "SciForge_SketchLine": SketchLine,
    "SciForge_PolygonCircumscribed": PolygonCircumscribed,
    "SciForge_PolygonInscribed": PolygonInscribed,
    "SciForge_SketchOffset": SketchOffset,
    "SciForge_SketchProject": SketchProject,
    "SciForge_SketchInclude3D": SketchInclude3D,
}
