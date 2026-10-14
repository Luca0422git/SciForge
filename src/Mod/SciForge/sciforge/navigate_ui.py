# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Pan, Zoom and Zoom Window, Fusion-style: commands for people without a
middle mouse button.

  Pan          drag with the left button to move the view; the hand stays until Esc
               (or another command).
  Zoom         drag up to zoom in, down to zoom out; until Esc.
  Zoom Window  drag a box: what is inside fills the view. Then it ends.

While one of them runs the left button belongs to it (no picks, no selection box); the
cursor says which one runs. The camera is moved directly (FreeCAD's own camera node), like
the mouse's middle button does.
"""

import FreeCADGui as Gui

from . import commands, log, nav_core, warn
from . import ui_icon_path
from .compat import QtCore, QtWidgets

_STATE = {"mode": None, "widgets": [], "filter": None, "view": None, "gl": None, "dialog": None}
HINTS = {
    "pan": "Drag to pan. Esc ends.",
    "zoom": "Drag up to zoom in, down to zoom out. Esc ends.",
    "window": "Drag a box round what should fill the view.",
}
CURSORS = {
    "pan": QtCore.Qt.OpenHandCursor,
    "zoom": QtCore.Qt.SizeVerCursor,
    "window": QtCore.Qt.CrossCursor,
}


def mode():
    return _STATE["mode"]


def _view_parts():
    """(the active 3D view, its drawing area, the viewer widget round it) or Nones."""
    try:
        view = Gui.ActiveDocument.ActiveView
        if not hasattr(view, "getCameraNode"):
            return None, None, None
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        sub = area.activeSubWindow() if area is not None else None
        if sub is None:
            return None, None, None
        gl = None
        for widget in sub.findChildren(QtWidgets.QWidget):
            if widget.metaObject().className() == "QOpenGLWidget":
                gl = widget
                break
        viewer = gl.parentWidget() if gl is not None else None
        while viewer is not None and viewer.metaObject().className() != (
            "Gui::View3DInventorViewer"
        ):
            viewer = viewer.parentWidget()
        return view, gl, viewer
    except Exception:
        return None, None, None


def _camera_size(view, gl):
    """(view height in mm, the drawing area's width and height in pixels)."""
    from . import grid_ui

    height = grid_ui.view_height(view)
    return height, max(1, gl.width()), max(1, gl.height())


def pan_by(view, gl, dx, dy):
    """Move the view so the model follows a drag of (dx, dy) pixels."""
    height, _w, h = _camera_size(view, gl)
    right_mm, up_mm = nav_core.pan_shift(dx, dy, h, height)
    rot = view.getCameraOrientation()
    shift = rot.multVec(_vec(1, 0, 0)) * right_mm + rot.multVec(_vec(0, 1, 0)) * up_mm
    cam = view.getCameraNode()
    p = cam.position.getValue()
    cam.position.setValue(p[0] + shift.x, p[1] + shift.y, p[2] + shift.z)


def zoom_by(view, factor):
    """Make the view `factor` times as big (below 1: zoom in)."""
    cam = view.getCameraNode()
    if hasattr(cam, "height"):
        cam.height.setValue(max(1e-6, float(cam.height.getValue()) * factor))
        return
    focal = float(cam.focalDistance.getValue())
    rot = view.getCameraOrientation()
    forward = rot.multVec(_vec(0, 0, -1))
    move = forward * (focal * (1.0 - factor))
    p = cam.position.getValue()
    cam.position.setValue(p[0] + move.x, p[1] + move.y, p[2] + move.z)
    cam.focalDistance.setValue(max(1e-6, focal * factor))


def zoom_window(view, gl, x0, y0, x1, y1):
    """The box (widget pixels) fills the view. False for a box too small (a click)."""
    height, w, h = _camera_size(view, gl)
    found = nav_core.zoom_window(x0, y0, x1, y1, w, h)
    if found is None:
        return False
    cx, cy, factor = found
    width = height * w / float(h)
    rot = view.getCameraOrientation()
    shift = rot.multVec(_vec(1, 0, 0)) * (cx * width) + rot.multVec(_vec(0, 1, 0)) * (cy * height)
    cam = view.getCameraNode()
    p = cam.position.getValue()
    cam.position.setValue(p[0] + shift.x, p[1] + shift.y, p[2] + shift.z)
    zoom_by(view, factor)
    return True


def _vec(x, y, z):
    import FreeCAD as App

    return App.Vector(x, y, z)


class _Filter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.press = None
        self.last = None
        self.band = None

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
                QtCore.QTimer.singleShot(0, stop)
                return True
            if kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick):
                if event.button() == QtCore.Qt.RightButton:
                    QtCore.QTimer.singleShot(0, stop)
                    return True
                if event.button() != QtCore.Qt.LeftButton:
                    return False
                if _dialog_key() != _STATE["dialog"]:
                    # a command was started (or ended) meanwhile: Pan / Zoom give way to it
                    QtCore.QTimer.singleShot(0, stop)
                    return False
                self.press = QtCore.QPointF(event.position())
                self.last = QtCore.QPointF(event.position())
                if _STATE["mode"] == "pan":
                    obj.setCursor(QtCore.Qt.ClosedHandCursor)
                if _STATE["mode"] == "window":
                    self._band(obj)
                return True
            if kind == QtCore.QEvent.MouseMove:
                if self.press is None:
                    return False
                if not (event.buttons() & QtCore.Qt.LeftButton):
                    return False
                self._moved(QtCore.QPointF(event.position()))
                return True
            if kind == QtCore.QEvent.MouseButtonRelease:
                if event.button() != QtCore.Qt.LeftButton or self.press is None:
                    return False
                self._released(QtCore.QPointF(event.position()))
                return True
        except Exception as exc:
            warn("navigation: %s" % exc)
            self.press = None
        return False

    def _band(self, widget):
        if self.band is None:
            self.band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, widget)
            self.band.setObjectName("SciForgeZoomWindowBand")
        self.band.setGeometry(QtCore.QRect(self.press.toPoint(), QtCore.QSize()))
        self.band.show()

    def _moved(self, pos):
        view, gl = _STATE["view"], _STATE["gl"]
        if _STATE["mode"] == "pan":
            dx, dy = pos.x() - self.last.x(), pos.y() - self.last.y()
            pan_by(view, gl, dx, dy)
        elif _STATE["mode"] == "zoom":
            zoom_by(view, nav_core.zoom_factor(pos.y() - self.last.y()))
        elif _STATE["mode"] == "window" and self.band is not None:
            self.band.setGeometry(QtCore.QRect(self.press.toPoint(), pos.toPoint()).normalized())
        self.last = pos

    def _released(self, pos):
        press, self.press = self.press, None
        if _STATE["mode"] == "pan":
            gl = _STATE["gl"]
            if gl is not None:
                gl.setCursor(CURSORS["pan"])
        if _STATE["mode"] == "window":
            if self.band is not None:
                self.band.hide()
            done = zoom_window(_STATE["view"], _STATE["gl"], press.x(), press.y(), pos.x(), pos.y())
            if done:
                log("zoom window")
                QtCore.QTimer.singleShot(0, stop)


def _dialog_key():
    """What is open: a command's dialog, a sketch or other edit (Pan and Zoom work inside
    them, like Fusion's navigation; a different one opening ends Pan / Zoom)."""
    current = edit = None
    try:
        from . import taskui

        current = taskui.current()
    except Exception:
        current = None
    try:
        gui = Gui.ActiveDocument
        vp = gui.getInEdit() if gui is not None else None
        edit = vp.Object.Name if vp is not None else None
    except Exception:
        edit = None
    try:
        open_dialog = bool(Gui.Control.activeDialog())
    except Exception:
        open_dialog = False
    return open_dialog, id(current) if current is not None else None, edit


def start(which):
    """Pan, Zoom or Zoom Window on the active 3D view. An open command or sketch stays open
    (the navigation bar is used in the middle of a command)."""
    stop()
    view, gl, viewer = _view_parts()
    if view is None or gl is None:
        commands.tell("Open or start a design first.")
        return False
    _STATE["filter"] = _Filter()
    _STATE["widgets"] = [w for w in (gl, viewer) if w is not None]
    for widget in _STATE["widgets"]:
        widget.installEventFilter(_STATE["filter"])
    _STATE.update(mode=which, view=view, gl=gl, dialog=_dialog_key())
    gl.setCursor(CURSORS[which])
    commands.tell(HINTS[which])
    log("%s: on" % {"pan": "Pan", "zoom": "Zoom", "window": "Zoom Window"}[which])
    return True


def stop():
    """End Pan / Zoom / Zoom Window (Esc, a right click, another command)."""
    try:
        _stop()
    except Exception as exc:
        warn("navigation: %s" % exc)
        _STATE.update(mode=None, widgets=[], filter=None, view=None, gl=None, dialog=None)


def _stop():
    if _STATE["mode"] is None:
        return
    which = _STATE["mode"]
    for widget in _STATE["widgets"]:
        try:
            widget.removeEventFilter(_STATE["filter"])
        except RuntimeError:
            pass
    try:
        if _STATE["gl"] is not None:
            _STATE["gl"].unsetCursor()
    except RuntimeError:
        pass
    filt = _STATE["filter"]
    if filt is not None and filt.band is not None:
        try:
            filt.band.hide()
            filt.band.deleteLater()
        except RuntimeError:
            pass
    _STATE.update(mode=None, widgets=[], filter=None, view=None, gl=None, dialog=None)
    log("%s: off" % {"pan": "Pan", "zoom": "Zoom", "window": "Zoom Window"}[which])


def _command(text, tip, icon, which):
    class Command:
        def GetResources(self):
            return {"MenuText": text, "ToolTip": tip, "Pixmap": ui_icon_path(icon)}

        def IsActive(self):
            return True

        def Activated(self):
            try:
                start(which)
            except Exception as exc:
                warn("%s: %s" % (text, exc))

    return Command


COMMANDS = {
    "SciForge_Pan": _command("Pan", "Drag to move the view (Esc ends)", "nav_pan", "pan"),
    "SciForge_Zoom": _command("Zoom", "Drag up or down to zoom (Esc ends)", "nav_zoom", "zoom"),
    "SciForge_ZoomWindow": _command(
        "Zoom Window", "Drag a box: it fills the view", "nav_zoom_window", "window"
    ),
}
