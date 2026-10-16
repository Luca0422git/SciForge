# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's INSERT menu: Insert Mesh, Convert Mesh, Insert STEP, Insert SVG, Insert DXF,
Canvas (with Edit Canvas and Calibrate). The dialogs; the document work is in insert.py.
Spec and sources: docs/sciforge/parity/insert-export.md."""

import os

import FreeCAD as App
import FreeCADGui as Gui

from . import (
    bodies,
    commands,
    hole_common,
    insert,
    log,
    preview,
    taskui,
    ui_icon_path,
    warn,
)
from .compat import QtCore, QtGui, QtWidgets

# Tests put a function(kind) -> path here instead of the file dialog.
FILE_PICKER = None
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge"

FILTERS = {
    "mesh": "Mesh files (*.stl *.obj *.3mf *.STL *.OBJ *.3MF);;All files (*)",
    "step": "STEP and IGES files (*.step *.stp *.STEP *.STP *.iges *.igs *.IGES *.IGS);;"
    "All files (*)",
    "svg": "SVG files (*.svg *.SVG);;All files (*)",
    "dxf": "DXF files (*.dxf *.DXF);;All files (*)",
    "image": "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff);;All files (*)",
}
TITLES = {
    "mesh": "Insert Mesh",
    "step": "Insert STEP",
    "svg": "Insert SVG",
    "dxf": "Insert DXF",
    "image": "Insert Canvas",
}
INFO_STYLE = "color: #9fb3c8;"


def pick_file(kind):
    """The file dialog of an Insert command (remembers the folder). None when cancelled."""
    if FILE_PICKER is not None:
        return FILE_PICKER(kind)
    try:
        prefs = App.ParamGet(PREFS)
        start = prefs.GetString("LastInsertFolder", "")
        if not start or not os.path.isdir(start):
            doc = App.ActiveDocument
            start = (
                os.path.dirname(doc.FileName) if doc and doc.FileName else os.path.expanduser("~")
            )
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            Gui.getMainWindow(), TITLES[kind], start, FILTERS[kind]
        )
        if path:
            prefs.SetString("LastInsertFolder", os.path.dirname(path))
            return path
    except Exception as exc:
        warn("file dialog: %s" % exc)
    return None


def _open(panel_class, *args, **kwargs):
    """Open a dialog the way every SciForge command does: the open one is finished first;
    one that fails half way leaves nothing behind."""
    if App.ActiveDocument is None:
        App.newDocument("Design")
    if not commands.finish_open_dialog():
        return None
    doc = App.ActiveDocument
    try:
        panel = panel_class(doc, *args, **kwargs)
    except insert.InsertError as exc:
        _undo_half_open(doc)
        commands.tell(str(exc))
        return None
    except Exception:
        _undo_half_open(doc)
        raise
    try:
        Gui.Control.showDialog(panel)
    except Exception:
        try:
            panel.reject()
        except Exception:
            _undo_half_open(doc)
        raise
    return panel


def _undo_half_open(doc):
    try:
        doc.abortTransaction()
        App.closeActiveTransaction(True)
    except Exception:
        pass
    current = taskui._OPEN.get("dialog")
    if current is not None and getattr(current, "doc", None) is doc:
        taskui.set_current(None)


def _edit(panel_class, feature, **kwargs):
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return None
        panel = panel_class(feature.Document, feature=feature, **kwargs)
        Gui.Control.showDialog(panel)
        return panel
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))
        return None


# -- the dialog base ---------------------------------------------------------------------------
class _InsertPanel(taskui.Panel):
    """A SciForge task dialog with Fusion's keys (Esc cancels, Enter is OK, Ctrl+Z cancels,
    Ctrl+S finishes first) and helpers for its rows."""

    last = None

    def __init__(self, doc, transaction):
        super().__init__(doc, transaction)
        type(self).last = self
        _InsertPanel.last = self
        self.view = None
        try:
            self.view = Gui.ActiveDocument.ActiveView
        except Exception:
            pass
        self.target = None
        self._quiet = False
        self.guards = []
        try:
            self.guards = [
                preview.EscapeCancels(self),
                preview.UndoCancels(self),
                preview.EnterFinishes(self),
            ]
        except Exception as exc:
            warn("%s: keys unavailable: %s" % (self.title, exc))
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet(INFO_STYLE)

    def finish_layout(self):
        self.layout.addRow(self.info)
        super().finish_layout()

    def say(self, text):
        try:
            self.info.setText(text or "")
        except RuntimeError:
            pass

    def guarded(self, fn, *args):
        if self._quiet or getattr(self, "_closed", False):
            return
        try:
            fn(*args)
        except insert.InsertError as exc:
            self.message.setText("⚠ %s" % exc)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def combo(self, label, items, current, on_change):
        box = QtWidgets.QComboBox()
        box.addItems(list(items))
        if current in items:
            box.setCurrentText(current)
        box.currentIndexChanged.connect(lambda *_: self.guarded(on_change))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        return box

    def check(self, label, checked, on_change):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(checked))
        box.toggled.connect(lambda *_: self.guarded(on_change))
        self.layout.addRow(QtWidgets.QLabel(label), box)
        return box

    def number(self, label, value, unit, on_change):
        field = taskui.DistanceField(value, unit, lambda _v: self.guarded(on_change))
        self.layout.addRow(QtWidgets.QLabel(label), field.widget)
        return field

    def spin(self, label, value, lo, hi, on_change, decimals=3, step=0.1):
        box = QtWidgets.QDoubleSpinBox()
        box.setDecimals(decimals)
        box.setRange(lo, hi)
        box.setSingleStep(step)
        box.setValue(value)
        box.setKeyboardTracking(False)
        box.valueChanged.connect(lambda *_: self.guarded(on_change))
        self.layout.addRow(QtWidgets.QLabel(label), box)
        return box

    def button_row(self, *buttons):
        row = QtWidgets.QWidget()
        box = QtWidgets.QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        for text, fn in buttons:
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(lambda _=False, f=fn: self.guarded(f))
            box.addWidget(button)
        self.layout.addRow(row)
        return row

    def show_status(self):
        obj = self.feature()
        if obj is None:
            return
        text = preview.failure(obj)
        self.message.setText(("⚠ " + _plain(text)) if text else "")

    def cleanup(self):
        for guard in self.guards:
            try:
                guard.remove()
            except Exception:
                pass
        self.guards = []
        super().cleanup()


def _plain(text):
    text = str(text or "").strip()
    for prefix in ("Exception: ", "<Exception> ", "InsertError: "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


# -- plane picking (origin squares + flat faces), shared by SVG / DXF / Canvas -------------
class _PlanePick:
    """Waits for a plane: the origin squares light up (sketch_ui.PlanePicker) and a flat
    face can be clicked; on_pick((plane, "") or (feature, "FaceN")) once."""

    def __init__(self, panel, on_pick):
        from . import sketch_ui

        self.panel = panel
        self.on_pick = on_pick
        self.done = False
        self.planes = None
        body = commands.find_body() or _any_body(panel.doc)
        if body is None:  # an empty design: the body the curves / canvas will belong to
            body = commands.ensure_body()
        try:
            if body is not None and panel.view is not None:
                self.planes = sketch_ui.PlanePicker(
                    panel.view,
                    body,
                    lambda plane: QtCore.QTimer.singleShot(0, lambda: self._picked((plane, ""))),
                )
        except Exception as exc:
            warn("origin planes unavailable: %s" % exc)
        picker = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, picker._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _selection_changed(self):
        from . import sketch_ui

        if self.done:
            return
        try:
            target = sketch_ui.sketch_target()
        except Exception:
            target = None
        if target is not None:
            self._picked(target)
        elif Gui.Selection.getSelectionEx():
            Gui.Selection.clearSelection()
            commands.tell("Click a flat face or one of the origin planes.")

    def _picked(self, target):
        if self.done:
            return
        self.done = True
        self.remove()
        Gui.Selection.clearSelection()
        try:
            self.on_pick(target)
        except insert.InsertError as exc:
            self.panel.message.setText("⚠ %s" % exc)
        except Exception as exc:
            warn("%s: %s" % (self.panel.title, exc))

    def remove(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        if self.planes is not None:
            try:
                self.planes.remove()
            except Exception:
                pass
            self.planes = None


def _any_body(doc):
    found = bodies.list_bodies(doc)
    return found[0] if found else None


# -- the manipulator on a plane (Insert SVG / DXF, Canvas) -----------------------------------
class _PlaneHandles:
    """Fusion's manipulator for curves or a picture on a plane, drawn at its middle (help
    "Insert SVG": "the manipulator handles allow you to move, rotate, and scale the SVG image
    on the active sketch plane"; forum: the canvas manipulator "stays anchored to the
    image's center"): two arrows along the plane's X and Y (X / Y Distance), a curved handle
    that turns it about the plane's normal (Z Angle) and an arrow at its right edge that
    scales it (Scale), each with its value box. The dialog has the fields self.dx, self.dy,
    self.angle (taskui.DistanceField) and implements handle_frame(), handle_half(),
    scale_value(), scale_by(start, factor) and handles_moved()."""

    angle_sign = 1.0  # +1: the field turns counter-clockwise; -1: clockwise (SVG)

    def init_handles(self):
        self.handles = []
        self.handle_by = {}
        self._drag_start = None
        self.value_boxes = taskui.ValueBoxes(self, default="x")

    # -- the dialog's side (override) -----------------------------------------------------
    def handle_frame(self):
        """The plane's placement (its X, Y and normal), or None while there is no plane."""
        return None

    def handle_half(self):
        """Half the width of what is placed (mm), where the scale arrow sits."""
        return 10.0

    def scale_value(self):
        return 1.0

    def scale_by(self, start, factor):
        """Scale what is placed to `factor` times what it was when the drag started."""

    def handles_moved(self):
        """The fields changed from a handle: update the preview."""

    # -- the handles ------------------------------------------------------------------------
    def handle_point(self):
        frame = self.handle_frame()
        if frame is None:
            return None
        return frame.multVec(App.Vector(self.dx.value(), self.dy.value(), 0.0))

    def make_handles(self):
        import math

        self.remove_handles()
        frame = self.handle_frame()
        if frame is None or self.view is None or getattr(self, "_closed", False):
            return
        from . import extrude_ui

        rot = frame.Rotation
        x = rot.multVec(App.Vector(1, 0, 0))
        y = rot.multVec(App.Vector(0, 1, 0))
        z = rot.multVec(App.Vector(0, 0, 1))
        point = self.handle_point()
        size = taskui.handle_size_at(self.view, point)
        ccw = self.angle_sign * self.angle.value()
        a = math.radians(ccw)
        xr = x * math.cos(a) + y * math.sin(a)
        half = max(self.handle_half(), size * 1.2)
        try:
            move_x = taskui.ArrowDragger(
                point, x, 0.0, size, lambda d: self._handle_drag("x", d), self._handle_release
            )
            move_y = taskui.ArrowDragger(
                point, y, 0.0, size, lambda d: self._handle_drag("y", d), self._handle_release
            )
            scale = taskui.ArrowDragger(
                point + xr * half,
                xr,
                0.0,
                size * 0.8,
                lambda d: self._handle_drag("scale", d),
                self._handle_release,
            )
            turn = extrude_ui.AngleDragger(
                point,
                z,
                x,
                ccw,
                max(half * 0.7, size * 1.5),
                size * 0.35,
                lambda deg: self._handle_drag("angle", deg),
                self._handle_release,
            )
        except Exception as exc:
            warn("%s handles: %s" % (self.title, exc))
            return
        self.handles = [move_x, move_y, scale, turn]
        self.handle_by = {"x": move_x, "y": move_y, "scale": scale, "angle": turn}
        boxes = self.value_boxes
        boxes.attach(move_x, "x", lambda: self.dx.widget.text(), self._typed(self.dx))
        boxes.attach(move_y, "y", lambda: self.dy.widget.text(), self._typed(self.dy))
        boxes.attach(turn, "angle", lambda: self.angle.widget.text(), self._typed(self.angle))
        boxes.attach(scale, "scale", lambda: "%g" % round(self.scale_value(), 4), self._typed_scale)

    def _typed(self, field):
        def commit(text):
            field.take(field.parse(text))

        return commit

    def _typed_scale(self, text):
        try:
            value = float(str(text).replace(",", ".").strip().split()[0])
        except (ValueError, IndexError):
            self.message.setText("⚠ The scale is a number, like 2 or 0.5.")
            return
        if value <= 0:
            self.message.setText("⚠ The scale must be more than 0.")
            return
        now = self.scale_value()
        if now > 0:
            self._quiet = True
            try:
                self.scale_by(self._scale_start(), value / now)
            finally:
                self._quiet = False
            self.handles_moved()

    def _scale_start(self):
        return {"scale": self.scale_value()}

    def _handle_drag(self, kind, value):
        if getattr(self, "_closed", False):
            return
        if self._drag_start is None:
            self._drag_start = dict(
                dx=self.dx.value(),
                dy=self.dy.value(),
                half=max(1e-6, self.handle_half()),
                **self._scale_start()
            )
        start = self._drag_start
        self._quiet = True
        try:
            if kind == "x":
                self.dx.set_value(start["dx"] + value)
            elif kind == "y":
                self.dy.set_value(start["dy"] + value)
            elif kind == "angle":
                self.angle.set_value(self.angle_sign * value)
            elif kind == "scale":
                factor = max(0.01, (start["half"] + value) / start["half"])
                self.scale_by(start, factor)
        finally:
            self._quiet = False
        try:
            self.handles_moved()
        except insert.InsertError as exc:
            self.message.setText("⚠ %s" % exc)
        except Exception as exc:
            warn("%s drag: %s" % (self.title, exc))

    def _handle_release(self, _value=None):
        self._drag_start = None
        # The handles go to the new middle (later: never inside the dragger's poll).
        QtCore.QTimer.singleShot(0, lambda: self.guarded(self.make_handles))

    def remove_handles(self):
        handles, self.handles = getattr(self, "handles", []), []
        self.handle_by = {}
        for handle in handles:
            try:
                handle.remove()
            except Exception:
                pass

    def handles_after_recompute(self):
        if self._drag_start is None:  # never under a handle being dragged
            self.make_handles()

    def drop_handles(self):
        self.remove_handles()
        try:
            self.value_boxes.discard()
        except Exception:
            pass


def _preselected_plane():
    from . import sketch_ui

    try:
        return sketch_ui.sketch_target()
    except Exception:
        return None


# ============================================================================ Insert Mesh
class InsertMeshPanel(_InsertPanel):
    """Fusion's Insert Mesh dialog: Unit Type, Flip Up Direction, Center, Move to Ground,
    X / Y / Z distance and angle, a move manipulator (arrows and turn handles), Reset."""

    title = "Insert Mesh"
    icon = "insert_mesh"

    def __init__(self, doc, path=None, feature=None):
        super().__init__(doc, "Edit Insert Mesh" if feature is not None else "Insert Mesh")
        self.editing = feature is not None
        self.triad = None
        self._start = None
        if feature is None:
            mesh = insert.read_mesh(path)
            unit = insert.design_unit(doc)
            self.obj = insert.make_mesh_body(doc, mesh, path, unit=unit)
            self.obj.Placement = App.Placement()
        else:
            self.obj = feature
            path = getattr(feature, "SourceFile", "") or ""
            unit = getattr(feature, "UnitType", "") or insert.design_unit(doc)
        self.target = self.obj
        self._restore = (
            self.obj.Mesh.copy(),
            self.obj.Placement,
            getattr(self.obj, "UnitType", unit),
            bool(getattr(self.obj, "FlipUp", False)),
        )
        name = QtWidgets.QLabel(os.path.basename(path) if path else "(mesh body)")
        name.setToolTip(path)
        self.layout.addRow(QtWidgets.QLabel("File"), name)
        self.unit = self.combo("Unit Type", insert.UNIT_NAMES, unit, self._unit_changed)
        self.flip = self.check(
            "Flip Up Direction", bool(getattr(self.obj, "FlipUp", False)), self._flip_changed
        )
        self.button_row(("Center", self.center), ("Move to Ground", self.move_to_ground))
        position = self.obj.Placement.Base
        angles = insert.angles_of(self.obj.Placement)
        self.x = self.number("X Distance", position.x, "mm", self._fields_changed)
        self.y = self.number("Y Distance", position.y, "mm", self._fields_changed)
        self.z = self.number("Z Distance", position.z, "mm", self._fields_changed)
        self.ax = self.number("X Angle", angles[0], "deg", self._fields_changed)
        self.ay = self.number("Y Angle", angles[1], "deg", self._fields_changed)
        self.az = self.number("Z Angle", angles[2], "deg", self._fields_changed)
        self.button_row(("Reset", self.reset))
        self.finish_layout()
        self._describe()
        self._make_triad()
        doc.recompute()
        Gui.Selection.clearSelection()

    # -- state --------------------------------------------------------------------------
    def feature(self):
        return self.obj if bodies.alive(self.obj) else None

    def position(self):
        return (self.x.value(), self.y.value(), self.z.value())

    def angles(self):
        return (self.ax.value(), self.ay.value(), self.az.value())

    def _describe(self):
        try:
            info = insert.mesh_info(insert.kernel_copy(self.obj))
            size = info["size"]
            text = "%d triangles, %.1f x %.1f x %.1f mm%s" % (
                info["facets"],
                size[0],
                size[1],
                size[2],
                "" if info["solid"] else "; the mesh is not watertight (open edges)",
            )
            self.say(text)
        except Exception:
            pass

    def _apply(self):
        if not bodies.alive(self.obj):
            return
        placement = insert.placement_of(self.position(), self.angles())
        if not self.obj.Placement.isSame(placement, 1e-9):
            self.obj.Placement = placement
        self._place_triad()
        self.schedule()

    def _set_fields(self, position, angles):
        self._quiet = True
        try:
            for field, value in zip((self.x, self.y, self.z), position):
                field.set_value(value)
            for field, value in zip((self.ax, self.ay, self.az), angles):
                field.set_value(value)
        finally:
            self._quiet = False

    # -- the rows -----------------------------------------------------------------------
    def _unit_changed(self):
        if insert.update_mesh_body(self.obj, self.unit.currentText(), self.flip.isChecked()):
            self._describe()
            self._place_triad()
            self.schedule()

    def _flip_changed(self):
        self._unit_changed()

    def _fields_changed(self):
        self._apply()

    def _placed_bounds(self):
        """Bounds of the mesh as it stands (turned, not yet moved)."""
        return insert.placed_bounds(self.obj, rotation_only=True)

    def center(self):
        position = insert.center_offset(self._placed_bounds())
        self._set_fields(position, self.angles())
        self._apply()

    def move_to_ground(self):
        position = insert.ground_offset(self._placed_bounds(), self.position())
        self._set_fields(position, self.angles())
        self._apply()

    def reset(self):
        self._set_fields((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        self._quiet = True
        try:
            self.unit.setCurrentText(
                self._restore[2] if self.editing else insert.design_unit(self.doc)
            )
            self.flip.setChecked(self._restore[3] if self.editing else False)
        finally:
            self._quiet = False
        self._unit_changed()
        self._apply()

    # -- the manipulator ----------------------------------------------------------------
    def _make_triad(self):
        if self.view is None:
            return
        try:
            from . import move_ui

            centre = self._centre()
            size = taskui.handle_size_at(self.view, centre, hi=60.0)
            self.triad = move_ui.Triad(
                self.view,
                centre,
                size,
                turns=True,
                on_drag=self._dragged,
                on_release=self._released,
            )
        except Exception as exc:
            warn("Insert Mesh: manipulator unavailable: %s" % exc)
            self.triad = None

    def _centre(self):
        (x0, y0, z0), (x1, y1, z1) = insert.placed_bounds(self.obj)
        return App.Vector((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)

    def _place_triad(self):
        if self.triad is not None and not self.triad.dragging():
            try:
                self.triad.set_center(self._centre())
            except Exception:
                pass

    def _dragged(self, kind, index, value):
        try:
            if self._start is None:
                self._start = (App.Placement(self.obj.Placement), self._centre())
            start, centre = self._start
            axis = [App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)][index]
            if kind == "move":
                placement = App.Placement(start.Base + axis * value, start.Rotation)
            else:
                turn = App.Placement(centre, App.Rotation(axis, value)).multiply(
                    App.Placement(-centre, App.Rotation())
                )
                placement = turn.multiply(start)
            self.obj.Placement = placement
            self._set_fields(tuple(placement.Base), insert.angles_of(placement))
            self.schedule()
        except Exception as exc:
            warn("Insert Mesh drag: %s" % exc)

    def _released(self):
        self._start = None
        self._place_triad()

    # -- finishing ----------------------------------------------------------------------
    def accept(self):
        if not super().accept():
            return False
        _refresh_browser()
        return True

    def reject(self):
        if self.editing and bodies.alive(self.obj):
            try:  # the transaction puts it back too; this keeps the view in step at once
                mesh, placement, unit, flip = self._restore
                self.obj.Mesh = mesh
                self.obj.Placement = placement
            except Exception:
                pass
        result = super().reject()
        _refresh_browser()
        return result

    def cleanup(self):
        if self.triad is not None:
            try:
                self.triad.remove()
            except Exception:
                pass
            self.triad = None
        super().cleanup()


def _refresh_browser():
    try:
        from . import browser_ui

        widget = browser_ui.widget()
        if widget is not None:
            widget.refresh(force=True)
    except Exception:
        pass


# ============================================================================ Convert Mesh
class ConvertMeshPanel(_InsertPanel):
    """Fusion's Convert Mesh: Body (a mesh body), Operation Parametric / Base Feature, Method
    Faceted / Prismatic. The solid body is built live; OK keeps it, the mesh body is hidden."""

    title = "Convert Mesh"
    icon = "convert_mesh"

    def __init__(self, doc, mesh_obj=None, feature=None):
        super().__init__(doc, "Edit Convert Mesh" if feature is not None else "Convert Mesh")
        self.editing = feature is not None
        self.step = feature
        self.body = bodies.body_of(feature) if feature is not None else None
        self.mesh_obj = feature.Source if feature is not None else mesh_obj
        self._hidden = None
        self.fields = {}
        self.field = hole_common.SelectionField(self, "body", "Select a mesh body")
        self.fields["body"] = self.field
        self.layout.addRow(QtWidgets.QLabel("Body"), self.field.widget)
        self.operation = self.combo(
            "Operation",
            insert.OPERATIONS,
            "Parametric" if feature is None or feature.Parametric else "Base Feature",
            self._changed,
        )
        self.method = self.combo(
            "Method",
            insert.METHODS,
            feature.Method if feature is not None else "Prismatic",
            self._changed,
        )
        self.finish_layout()
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        self.field.set_active(True)
        if self.mesh_obj is not None:
            self._set_mesh(self.mesh_obj)
        else:
            self.say("Click the mesh body to convert.")
        Gui.Selection.clearSelection()

    # -- picking ------------------------------------------------------------------------
    def activate(self, name):
        self.field.set_active(True)

    def clear_field(self, name):
        self._drop_step()
        self.mesh_obj = None
        self.field.set_text("")
        self.say("Click the mesh body to convert.")
        self.schedule()

    def _selection_changed(self):
        if getattr(self, "_closed", False):
            return
        try:
            found = None
            other = None
            for sel in Gui.Selection.getSelectionEx():
                if sel.Document.Name != self.doc.Name:
                    continue
                if insert.is_mesh_body(sel.Object):
                    found = sel.Object
                    break
                other = sel.Object
            Gui.Selection.clearSelection()
            if found is None:
                if other is not None:
                    commands.tell(
                        "That is not a mesh body: click a mesh body (INSERT > Insert Mesh)."
                    )
                return
            self._set_mesh(found)
        except Exception as exc:
            warn("Convert Mesh: %s" % exc)

    def _set_mesh(self, mesh_obj):
        self.mesh_obj = mesh_obj
        self.field.set_text(mesh_obj.Label)
        info = insert.mesh_info(insert.kernel_copy(mesh_obj))
        note = "%d triangles" % info["facets"]
        if info["facets"] > insert.FACET_WARNING:
            note += ": a big mesh, the conversion can take a while"
        if not info["solid"]:
            note += "; not watertight: repair the mesh first (MESH tab > Repair)"
        self.say(note)
        if self.step is None:
            self.body, self.step = insert.convert_mesh(
                mesh_obj, self.method.currentText(), self.operation.currentText() == "Parametric"
            )
        elif self.step.Source is not mesh_obj:
            self.step.Source = mesh_obj
            self.step.Shape = __import__("Part").Shape()
        self.target = self.step
        self._hide_mesh(mesh_obj)
        self.schedule()

    def _hide_mesh(self, mesh_obj):
        try:
            if self._hidden is None:
                self._hidden = (mesh_obj.Name, bool(mesh_obj.ViewObject.Visibility))
            mesh_obj.ViewObject.Visibility = False
        except Exception:
            pass

    def _show_mesh_again(self):
        if self._hidden is None:
            return
        name, was = self._hidden
        self._hidden = None
        obj = self.doc.getObject(name)
        try:
            if obj is not None and obj.ViewObject is not None:
                obj.ViewObject.Visibility = was
        except Exception:
            pass

    def _drop_step(self):
        if self.step is not None and not self.editing:
            body = self.body
            self.step = self.body = None
            self.target = None
            try:
                bodies.remove_body(body)
            except Exception as exc:
                warn("Convert Mesh: %s" % exc)
        self._show_mesh_again()

    def _changed(self):
        if self.step is None:
            return
        self.step.Method = self.method.currentText()
        self.step.Parametric = self.operation.currentText() == "Parametric"
        if self.step.Parametric or self.step.Shape.isNull():
            self.step.touch()
        else:
            # Base Feature: rebuilt once with the new method, then frozen
            self.step.Shape = __import__("Part").Shape()
            self.step.touch()
        self.schedule()

    def feature(self):
        return self.step if self.step is not None and bodies.alive(self.step) else None

    def _recompute(self):
        super()._recompute()
        if self.step is not None and bodies.alive(self.step):
            try:
                bodies.show_tip(self.body)
            except Exception:
                pass

    # -- finishing ----------------------------------------------------------------------
    def accept(self):
        if self.step is None:
            self.message.setText("⚠ Click the mesh body to convert.")
            return False
        self.doc.recompute()
        if "Invalid" in list(self.step.State):
            self.show_status()
            return False
        if not super().accept():
            return False
        try:
            bodies.set_active_body(self.body)
        except Exception:
            pass
        _refresh_browser()
        return True

    def reject(self):
        self._show_mesh_again()
        result = super().reject()
        _refresh_browser()
        return result

    def cleanup(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        super().cleanup()


# ============================================================================ SVG / DXF
class InsertCurvesPanel(_PlaneHandles, _InsertPanel):
    """Fusion's Insert SVG / Insert DXF: a plane or flat face (or the open sketch), the
    file, X / Y distance, Z angle, scale, horizontal / vertical flip, and the manipulator on
    the plane (arrows, turn and scale handles with value boxes); DXF adds Units, Insert Mode
    (one sketch, or one per layer) and the layer list. An SVG is centred on the sketch
    origin and its Z Angle turns clockwise (help "Insert SVG"); a DXF's origin is the
    sketch origin (help "Insert DXF"). The curves are fixed sketch geometry; OK keeps the
    sketch(es)."""

    icon = "insert_svg"

    def __init__(self, doc, kind, path=None, sketch=None):
        self.kind = kind
        self.title = "Insert SVG" if kind == "svg" else "Insert DXF"
        self.icon = "insert_svg" if kind == "svg" else "insert_dxf"
        self.angle_sign = -1.0 if kind == "svg" else 1.0
        super().__init__(doc, self.title)
        self.init_handles()
        raw = insert.read_curves(path)
        box = insert.curves_bounds([e for _name, edges in raw for e in edges])
        self.extent = box or ((0.0, 0.0), (0.0, 0.0))
        (x0, y0), (x1, y1) = self.extent
        self.origin = ((x0 + x1) / 2.0, (y0 + y1) / 2.0) if kind == "svg" else (0.0, 0.0)
        self.layers = [(name, insert.curves_to_geometry(edges)) for name, edges in raw]
        self.layers = [(name, geos) for name, geos in self.layers if geos]
        if not self.layers:
            raise insert.InsertError("The file holds no curves that can go into a sketch.")
        self.path = path
        self.sketches = {}  # layer name (or "*") -> (sketch, [geometry ids])
        self.made = []  # sketches this dialog created
        self.pick = None
        self.body = None
        self.target = None
        self.open_sketch = None
        self._pending = False
        name = QtWidgets.QLabel(os.path.basename(path))
        name.setToolTip(path)
        self.layout.addRow(QtWidgets.QLabel("File"), name)
        self.plane_label = QtWidgets.QLabel("")
        self.layout.addRow(QtWidgets.QLabel("Plane"), self.plane_label)
        self.units = None
        self.mode = None
        self.layer_list = None
        if kind == "dxf":
            file_unit = insert.dxf_file_unit(path)
            self.file_unit = file_unit
            self.units = self.combo(
                "Units", ["As in the file"] + insert.UNIT_NAMES, "As in the file", self.rebuild
            )
            self.mode = self.combo(
                "Insert Mode",
                ["Single Sketch", "One Sketch per Layer"],
                "Single Sketch",
                self._mode_changed,
            )
            self.layer_list = QtWidgets.QListWidget()
            for layer, geos in self.layers:
                item = QtWidgets.QListWidgetItem("%s (%d curves)" % (layer, len(geos)))
                item.setData(QtCore.Qt.UserRole, layer)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.layer_list.addItem(item)
            self.layer_list.setMaximumHeight(90)
            self.layer_list.itemChanged.connect(lambda *_: self.guarded(self.rebuild))
            self.layout.addRow(QtWidgets.QLabel("DXF Layers"), self.layer_list)
        self.dx = self.number("X Distance", 0.0, "mm", self.rebuild)
        self.dy = self.number("Y Distance", 0.0, "mm", self.rebuild)
        self.angle = self.number("Z Angle", 0.0, "deg", self.rebuild)
        self.scale = self.spin("Scale Plane XY", 1.0, 0.0001, 100000.0, self.rebuild, 4, 0.1)
        self.flip_h = self.check("Horizontal Flip", False, self.rebuild)
        self.flip_v = self.check("Vertical Flip", False, self.rebuild)
        self.finish_layout()
        total = sum(len(geos) for _l, geos in self.layers)
        self.say(
            "%d curves in %d layer%s"
            % (total, len(self.layers), "" if len(self.layers) == 1 else "s")
        )
        edited = sketch if sketch is not None and bodies.alive(sketch) else _edited_sketch()
        if edited is not None:
            self.open_sketch = edited
            if _edited_sketch() is edited:
                commands.leave_edit()  # the dialog works on the closed sketch; OK opens it again
            self._use_sketch(edited)
        else:
            target = _preselected_plane()
            if target is not None:
                self._plane_picked(target)
            else:
                self.plane_label.setText("Click a plane or a flat face")
                self.pick = _PlanePick(self, self._plane_picked)
        Gui.Selection.clearSelection()

    # -- where the curves go ----------------------------------------------------------
    def _use_sketch(self, sketch):
        self.body = bodies.body_of(sketch)
        self.target = sketch
        self.plane_label.setText("Sketch: %s" % sketch.Label)
        self.sketches = {"*": (sketch, [])}
        if self.mode is not None:
            self.mode.setEnabled(False)  # the curves go into the open sketch
        self.rebuild()

    def _plane_picked(self, target):
        self.body = commands.ensure_body()
        self.target = target
        label = target[0].Label + (" " + target[1] if target[1] else "")
        self.plane_label.setText(label)
        self.rebuild()

    def _per_layer(self):
        return (
            self.mode is not None
            and self.mode.currentText() == "One Sketch per Layer"
            and self.open_sketch is None
        )

    def _selected_layers(self):
        if self.layer_list is None:
            return [name for name, _ in self.layers]
        chosen = []
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                chosen.append(item.data(QtCore.Qt.UserRole))
        return chosen

    def _unit_factor(self):
        if self.units is None or self.units.currentText() == "As in the file":
            return 1.0
        wanted = insert.unit_scale(self.units.currentText())
        return wanted / (self.file_unit or 1.0)

    def _moved(self, geos):
        return insert.transformed_geometry(
            geos,
            self.dx.value(),
            self.dy.value(),
            self.angle_sign * self.angle.value(),
            self.scale.value() * self._unit_factor(),
            self.flip_h.isChecked(),
            self.flip_v.isChecked(),
            self.origin,
        )

    # -- the manipulator (_PlaneHandles) ------------------------------------------------
    def handle_frame(self):
        for sketch, _ids in self.sketches.values():
            if sketch is not None and bodies.alive(sketch):
                try:
                    return sketch.getGlobalPlacement()
                except Exception:
                    return App.Placement(sketch.Placement)
        return None

    def handle_half(self):
        (x0, _y0), (x1, _y1) = self.extent
        factor = self.scale.value() * self._unit_factor()
        if self.kind == "svg":
            return 0.5 * (x1 - x0) * factor
        return max(abs(x0), abs(x1)) * factor

    def scale_value(self):
        return self.scale.value()

    def scale_by(self, start, factor):
        self.scale.setValue(start["scale"] * factor)

    def handles_moved(self):
        self.rebuild()

    def _recompute(self):
        super()._recompute()
        self.handles_after_recompute()

    def _mode_changed(self):
        self._clear_sketches()
        self.rebuild()

    def _clear_sketches(self):
        for key, (sketch, ids) in list(self.sketches.items()):
            if sketch is self.open_sketch:
                insert.remove_geometry(sketch, ids)
                self.sketches[key] = (sketch, [])
                continue
            try:
                bodies.remove_step(sketch)
            except Exception:
                pass
        self.sketches = {"*": (self.open_sketch, [])} if self.open_sketch is not None else {}
        self.made = []

    def _sketch_for(self, key, label):
        if key in self.sketches:
            return self.sketches[key][0]
        sketch = insert.new_sketch(self.body, self.target, label)
        self.sketches[key] = (sketch, [])
        self.made.append(sketch)
        return sketch

    def rebuild(self):
        if self.target is None or getattr(self, "_closed", False):
            return
        chosen = set(self._selected_layers())
        wanted = {}
        if self._per_layer():
            for layer, geos in self.layers:
                if layer in chosen:
                    wanted[layer] = [(layer, geos)]
        else:
            wanted["*"] = [(layer, geos) for layer, geos in self.layers if layer in chosen]
        # sketches no longer wanted (a layer unticked in per-layer mode)
        for key in [k for k in self.sketches if k not in wanted]:
            sketch, ids = self.sketches.pop(key)
            if sketch is self.open_sketch:
                insert.remove_geometry(sketch, ids)
            else:
                bodies.remove_step(sketch)
        base_label = os.path.splitext(os.path.basename(self.path))[0]
        for key, groups in wanted.items():
            label = None if key == "*" else "%s %s" % (base_label, key)
            sketch = self._sketch_for(key, label)
            _old, ids = self.sketches[key]
            insert.remove_geometry(sketch, ids)
            geos = [g for _layer, group in groups for g in group]
            new_ids = insert.add_geometry(sketch, self._moved(geos))
            self.sketches[key] = (sketch, new_ids)
        self.schedule()

    def feature(self):
        for sketch, _ids in self.sketches.values():
            if sketch is not None and bodies.alive(sketch):
                return sketch
        return None

    # -- finishing ----------------------------------------------------------------------
    def accept(self):
        if self.target is None:
            self.message.setText("⚠ Click a plane or a flat face first.")
            return False
        if not any(ids for _s, ids in self.sketches.values()):
            self.message.setText("⚠ Nothing to insert: tick at least one layer.")
            return False
        sketches = [s for s, _ids in self.sketches.values() if bodies.alive(s)]
        reopen = (
            self.open_sketch
            if self.open_sketch is not None
            else (sketches[0] if len(sketches) == 1 else None)
        )
        if not super().accept():
            return False
        _refresh_browser()
        if reopen is not None and bodies.alive(reopen):
            from . import sketch_ui

            QtCore.QTimer.singleShot(0, lambda: _reopen(reopen, sketch_ui))
        return True

    def reject(self):
        reopen = self.open_sketch
        result = super().reject()
        _refresh_browser()
        if reopen is not None and bodies.alive(reopen):
            from . import sketch_ui

            QtCore.QTimer.singleShot(0, lambda: _reopen(reopen, sketch_ui))
        return result

    def cleanup(self):
        if self.pick is not None:
            self.pick.remove()
            self.pick = None
        self.drop_handles()
        super().cleanup()


def _reopen(sketch, sketch_ui):
    try:
        if bodies.alive(sketch):
            sketch_ui.open_sketch(sketch)
    except Exception as exc:
        warn("could not open %s again: %s" % (sketch.Label, exc))


def _edited_sketch():
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument else None
        obj = edit.Object if edit is not None else None
        if obj is not None and obj.TypeId == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass
    return None


# ============================================================================ Canvas
def image_pixels(path):
    image = QtGui.QImage(path)
    if image.isNull():
        raise insert.InsertError("The image could not be read: %s" % os.path.basename(path))
    return (image.width(), image.height())


def apply_canvas_view(obj, selectable=None):
    """The view side of a canvas: opacity, Display Through, Selectable."""
    try:
        vobj = obj.ViewObject
        if vobj is None:
            return
        opacity = int(getattr(obj, "CanvasOpacity", 50))
        wanted = max(0, min(100, 100 - opacity))
        if vobj.Transparency != wanted:
            vobj.Transparency = wanted
        if selectable is not None and vobj.Selectable != bool(selectable):
            vobj.Selectable = bool(selectable)
        display_through(obj, bool(getattr(obj, "DisplayThrough", True)))
    except Exception as exc:
        warn("canvas view: %s" % exc)


def display_through(obj, on):
    """Display Through: the image is drawn after everything else, without the depth test
    (a Coin annotation), so bodies in front of it never hide it."""
    try:
        from pivy import coin

        vobj = obj.ViewObject
        root = vobj.RootNode
        count = root.getNumChildren()
        first = root.getChild(0) if count else None
        wrapped = (
            first is not None
            and first.getTypeId() == coin.SoAnnotation.getClassTypeId()
            and count == 1
        )
        if on and not wrapped:
            annotation = coin.SoAnnotation()
            for i in range(count):
                annotation.addChild(root.getChild(i))
            root.removeAllChildren()
            root.addChild(annotation)
        elif not on and wrapped:
            annotation = first
            annotation.ref()
            root.removeAllChildren()
            for i in range(annotation.getNumChildren()):
                root.addChild(annotation.getChild(i))
            annotation.unref()
    except Exception as exc:
        warn("canvas display through: %s" % exc)


class CanvasPanel(_PlaneHandles, _InsertPanel):
    """Fusion's Insert Canvas / Edit Canvas dialog: the face or plane, Canvas Opacity,
    Display Through, Selectable, horizontal / vertical flip, X / Y distance, Z angle,
    Scale X / Y / Plane XY, and the manipulator at the picture's middle (arrows, turn and
    scale handles with value boxes)."""

    title = "Canvas"
    icon = "canvas"

    def __init__(self, doc, path=None, feature=None):
        super().__init__(doc, "Edit Canvas" if feature is not None else "Canvas")
        self.init_handles()
        self.editing = feature is not None
        self.obj = feature
        self.pick = None
        self.pixels = None
        self.path = path
        if feature is None:
            self.pixels = image_pixels(path)
        else:
            self.title = "Edit Canvas"
            self.form.setWindowTitle(self.title)
        self._view_restore = None
        if feature is not None:
            try:
                self._view_restore = (
                    feature.ViewObject.Transparency,
                    feature.ViewObject.Selectable,
                )
            except Exception:
                pass
        options = (
            insert.canvas_options(feature)
            if feature is not None
            else dict(
                opacity=50,
                display_through=True,
                flip_h=False,
                flip_v=False,
                dx=0.0,
                dy=0.0,
                angle=0.0,
                scale_x=1.0,
                scale_y=1.0,
            )
        )
        shown = os.path.basename(path or (getattr(feature, "ImageFile", "") or ""))
        self.layout.addRow(QtWidgets.QLabel("Image"), QtWidgets.QLabel(shown))
        self.plane_label = QtWidgets.QLabel("")
        if feature is None:
            self.layout.addRow(QtWidgets.QLabel("Face"), self.plane_label)
        self.opacity = QtWidgets.QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setValue(options["opacity"])
        self.opacity.setKeyboardTracking(False)
        self.opacity.valueChanged.connect(lambda *_: self.guarded(self.apply))
        self.layout.addRow(QtWidgets.QLabel("Canvas Opacity"), self.opacity)
        self.through = self.check("Display Through", options["display_through"], self.apply)
        selectable = True
        if feature is not None:
            try:
                selectable = bool(feature.ViewObject.Selectable)
            except Exception:
                pass
        self.selectable = self.check("Selectable", selectable, self.apply)
        self.flip_h = self.check("Horizontal Flip", options["flip_h"], self.apply)
        self.flip_v = self.check("Vertical Flip", options["flip_v"], self.apply)
        self.dx = self.number("X Distance", options["dx"], "mm", self.apply)
        self.dy = self.number("Y Distance", options["dy"], "mm", self.apply)
        self.angle = self.number("Z Angle", options["angle"], "deg", self.apply)
        self.scale_x = self.spin("Scale X", options["scale_x"], 0.0001, 100000.0, self.apply, 4)
        self.scale_y = self.spin("Scale Y", options["scale_y"], 0.0001, 100000.0, self.apply, 4)
        self.scale_xy = self.spin("Scale Plane XY", 1.0, 0.0001, 100000.0, self._scale_both, 4)
        self.finish_layout()
        if feature is None:
            target = _preselected_plane()
            if target is not None:
                self._plane_picked(target)
            else:
                self.plane_label.setText("Click a plane or a flat face")
                self.pick = _PlanePick(self, self._plane_picked)
        else:
            self.target = feature
            self.say(
                "%d x %d pixels, %.1f x %.1f mm. Drag the arrows to move it, the curved "
                "handle to turn it, the right arrow to scale it."
                % (feature.PixelWidth, feature.PixelHeight, feature.XSize, feature.YSize)
            )
            self.make_handles()
        Gui.Selection.clearSelection()

    # -- the manipulator (_PlaneHandles) ------------------------------------------------
    def handle_frame(self):
        if self.obj is None or not bodies.alive(self.obj):
            return None
        return App.Placement(self.obj.PlaneFrame)

    def handle_half(self):
        return 0.5 * float(self.obj.BaseWidth) * self.scale_x.value()

    def scale_value(self):
        return self.scale_x.value()

    def _scale_start(self):
        return {"scale": self.scale_x.value(), "scale_y": self.scale_y.value()}

    def scale_by(self, start, factor):
        self.scale_x.setValue(start["scale"] * factor)
        self.scale_y.setValue(start.get("scale_y", start["scale"]) * factor)

    def handles_moved(self):
        self.apply()

    def _recompute(self):
        super()._recompute()
        self.handles_after_recompute()

    def _plane_picked(self, target):
        frame = insert.plane_frame(target)
        size = insert.default_canvas_size(self.pixels, insert.design_extent(self.doc))
        self.obj = insert.make_canvas(self.doc, self.path, self.pixels, frame, size)
        self.target = self.obj
        label = target[0].Label + (" " + target[1] if target[1] else "")
        self.plane_label.setText(label)
        self.apply()
        self.say(
            "%d x %d pixels, %.1f x %.1f mm. Drag the arrows to move it, the curved handle "
            "to turn it, the right arrow to scale it. To size it exactly: right-click the "
            "canvas in the browser > Calibrate."
            % (self.pixels[0], self.pixels[1], size[0], size[1])
        )
        _refresh_browser()
        self.make_handles()

    def _scale_both(self):
        value = self.scale_xy.value()
        self._quiet = True
        try:
            self.scale_x.setValue(value)
            self.scale_y.setValue(value)
        finally:
            self._quiet = False
        self.apply()

    def apply(self):
        if self.obj is None or not bodies.alive(self.obj):
            return
        insert.set_canvas_options(
            self.obj,
            opacity=self.opacity.value(),
            display_through=self.through.isChecked(),
            flip_h=self.flip_h.isChecked(),
            flip_v=self.flip_v.isChecked(),
            dx=self.dx.value(),
            dy=self.dy.value(),
            angle=self.angle.value(),
            scale_x=self.scale_x.value(),
            scale_y=self.scale_y.value(),
        )
        apply_canvas_view(self.obj, self.selectable.isChecked())
        self.schedule()

    def feature(self):
        return self.obj if self.obj is not None and bodies.alive(self.obj) else None

    def accept(self):
        if self.obj is None:
            self.message.setText("⚠ Click a plane or a flat face first.")
            return False
        if not super().accept():
            return False
        _refresh_browser()
        return True

    def reject(self):
        if self.editing and self.obj is not None and bodies.alive(self.obj) and self._view_restore:
            try:
                self.obj.ViewObject.Transparency, self.obj.ViewObject.Selectable = (
                    self._view_restore
                )
            except Exception:
                pass
        result = super().reject()
        if self.editing and self.obj is not None and bodies.alive(self.obj):
            apply_canvas_view(self.obj)
        _refresh_browser()
        return result

    def cleanup(self):
        if self.pick is not None:
            self.pick.remove()
            self.pick = None
        self.drop_handles()
        super().cleanup()


class CalibratePanel(_InsertPanel):
    """Fusion's Calibrate: click two points on the canvas, type the distance between them,
    Enter: the image is scaled so they are that far apart."""

    title = "Calibrate"
    icon = "calibrate"

    def __init__(self, doc, canvas):
        super().__init__(doc, "Calibrate")
        if not insert.is_canvas(canvas):
            raise insert.InsertError("Pick a canvas to calibrate (right-click it in the browser).")
        self.obj = canvas
        self.target = canvas
        self.points = []
        self.callback = None
        self.line = None
        self.layout.addRow(QtWidgets.QLabel("Canvas"), QtWidgets.QLabel(canvas.Label))
        self.distance = self.number("Distance", 10.0, "mm", lambda: None)
        self.distance.widget.setEnabled(False)
        self.finish_layout()
        self.say("Click the first point on the image.")
        if self.view is not None:
            try:
                self.callback = self.view.addEventCallback("SoMouseButtonEvent", self._button)
            except Exception as exc:
                warn("Calibrate: clicks unavailable: %s" % exc)
        self._was_selectable = None
        try:
            self._was_selectable = bool(canvas.ViewObject.Selectable)
            canvas.ViewObject.Selectable = False  # the clicks are picks, not selections
        except Exception:
            pass
        Gui.Selection.clearSelection()

    def typing_field(self):
        return self.distance.widget if len(self.points) == 2 else None

    def _button(self, info):
        try:
            if info.get("Button") != "BUTTON1" or info.get("State") != "DOWN":
                return
            if len(self.points) >= 2:
                return
            position = info.get("Position")
            QtCore.QTimer.singleShot(0, lambda: self._clicked(position))
        except Exception as exc:
            warn("Calibrate: %s" % exc)

    def _clicked(self, position):
        try:
            from .profile_pick import ray_plane

            placement = self.obj.Placement
            normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
            hit = ray_plane(self.view, position, placement.Base, normal)
            if hit is None:
                commands.tell("Click on the image.")
                return
            point = hit[0]
            self.points.append(point)
            if len(self.points) == 1:
                self.say("Click the second point on the image.")
                self._draw()
                return
            length = (self.points[1] - self.points[0]).Length
            if length < 1e-6:
                self.points.pop()
                commands.tell("Click a second, different point.")
                return
            self.distance.widget.setEnabled(True)
            self.distance.set_value(length)
            self._draw()
            self.say("Type the real distance between the two points and press Enter.")
            try:
                self.distance.widget.setFocus()
                self.distance.widget.selectAll()
            except Exception:
                pass
        except Exception as exc:
            warn("Calibrate: %s" % exc)

    def _draw(self):
        try:
            from pivy import coin

            if self.view is None:
                return
            if self.line is None:
                self.line = coin.SoAnnotation()
                material = coin.SoMaterial()
                material.diffuseColor.setValue(0.98, 0.84, 0.25)
                material.emissiveColor.setValue(0.98, 0.84, 0.25)
                style = coin.SoDrawStyle()
                style.lineWidth = 2
                style.pointSize = 8
                self.coords = coin.SoCoordinate3()
                self.line.addChild(material)
                self.line.addChild(style)
                self.line.addChild(self.coords)
                self.line.addChild(coin.SoPointSet())
                self.lines = coin.SoLineSet()
                self.line.addChild(self.lines)
                self.view.getSceneGraph().addChild(self.line)
            self.coords.point.setValues(0, len(self.points), [(p.x, p.y, p.z) for p in self.points])
            self.lines.numVertices.setValue(len(self.points) if len(self.points) > 1 else 0)
        except Exception as exc:
            warn("Calibrate: %s" % exc)

    def feature(self):
        return self.obj if bodies.alive(self.obj) else None

    def accept(self):
        if len(self.points) < 2:
            self.message.setText("⚠ Click two points on the image first.")
            return False
        try:
            factor = insert.calibrate_canvas(
                self.obj, self.points[0], self.points[1], self.distance.value()
            )
        except insert.InsertError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        log("Calibrate: %s scaled by %.4f" % (self.obj.Label, factor))
        return super().accept()

    def cleanup(self):
        if self.callback is not None and self.view is not None:
            try:
                self.view.removeEventCallback("SoMouseButtonEvent", self.callback)
            except Exception:
                pass
            self.callback = None
        if self.line is not None and self.view is not None:
            try:
                self.view.getSceneGraph().removeChild(self.line)
            except Exception:
                pass
            self.line = None
        if self._was_selectable is not None and bodies.alive(self.obj):
            try:
                self.obj.ViewObject.Selectable = self._was_selectable
            except Exception:
                pass
        super().cleanup()


# -- designs opened again: images from the file, Display Through back on ---------------------
def restore_canvases(doc):
    try:
        insert.restore_canvas_images(doc)
        for obj in insert.canvases(doc):
            apply_canvas_view(obj)
    except Exception as exc:
        warn("canvases: %s" % exc)


class _CanvasWatch:
    """FreeCAD rebuilds a canvas's view when a design is opened or an undo brings it back:
    the image inside the design and Display Through are put back a moment later."""

    def _later(self, doc):
        try:
            name = doc.Name
        except Exception:
            return
        QtCore.QTimer.singleShot(400, lambda: self._run(name))

    def _run(self, name):
        try:
            if name not in App.listDocuments():
                return
            doc = App.getDocument(name)
            if getattr(doc, "Restoring", False):
                QtCore.QTimer.singleShot(300, lambda: self._run(name))
                return
            if insert.canvases(doc):
                restore_canvases(doc)
        except Exception as exc:
            warn("canvases: %s" % exc)

    def slotCreatedDocument(self, doc):
        self._later(doc)

    def slotUndoDocument(self, doc):
        self._later(doc)

    def slotRedoDocument(self, doc):
        self._later(doc)


_WATCH = {"observer": None}


def install_watch():
    if _WATCH["observer"] is None and App.GuiUp:
        _WATCH["observer"] = _CanvasWatch()
        App.addDocumentObserver(_WATCH["observer"])


# ============================================================================ commands
class _Command:
    text = ""
    tip = ""
    icon = "insert_mesh"

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return True

    def Activated(self):
        try:
            self.run()
        except insert.InsertError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("%s failed: %s" % (self.text, exc))

    def run(self):
        pass


class InsertMeshCommand(_Command):
    text = "Insert Mesh"
    tip = "An STL, OBJ or 3MF file as a mesh body"
    icon = "insert_mesh"

    def run(self):
        if not commands.finish_open_dialog():
            return
        path = pick_file("mesh")
        if path:
            _open(InsertMeshPanel, path)


class ConvertMeshCommand(_Command):
    text = "Convert Mesh"
    tip = "A mesh body into a solid body (faceted or prismatic)"
    icon = "convert_mesh"

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or start a design first.")
            return
        chosen = None
        for sel in Gui.Selection.getSelectionEx():
            if insert.is_mesh_body(sel.Object):
                chosen = sel.Object
                break
        if chosen is None and not insert.mesh_bodies(doc):
            commands.tell("There is no mesh body to convert yet (INSERT > Insert Mesh first).")
            return
        _open(ConvertMeshPanel, chosen)


class InsertStepCommand(_Command):
    text = "Insert STEP"
    tip = "A STEP or IGES file as a component: its parts, copies, names and colours"
    icon = "insert_step"

    def run(self):
        if not commands.finish_open_dialog():
            return
        path = pick_file("step")
        if not path:
            return
        insert_step_file(path)


def insert_step_file(path):
    """Insert STEP (or IGES) into the active design: one component named after the file
    with its components and copies, then Fusion's Initial Position (exchange_ui)."""
    from . import exchange_core, exchange_ui

    try:
        return exchange_ui.insert_cad_file(path).bodies
    except exchange_core.ExchangeError as exc:
        raise insert.InsertError(str(exc))


class InsertSVGCommand(_Command):
    text = "Insert SVG"
    tip = "The curves of an SVG file into a sketch"
    icon = "insert_svg"
    kind = "svg"

    def run(self):
        # Fusion inserts into the sketch that is open: remember it before the open command
        # (the sketch session) is finished, as every SciForge command does on starting.
        sketch = _edited_sketch()
        if not commands.finish_open_dialog():
            return
        path = pick_file(self.kind)
        if path:
            _open(InsertCurvesPanel, self.kind, path, sketch)


class InsertDXFCommand(InsertSVGCommand):
    text = "Insert DXF"
    tip = "The curves of a DXF file into a sketch (layers kept apart if you like)"
    icon = "insert_dxf"
    kind = "dxf"


class InsertCanvasCommand(_Command):
    text = "Canvas"
    tip = "A reference picture on a plane or a flat face"
    icon = "canvas"

    def run(self):
        if not commands.finish_open_dialog():
            return
        path = pick_file("image")
        if path:
            _open(CanvasPanel, path)


def _selected_canvas():
    for sel in Gui.Selection.getSelectionEx():
        if insert.is_canvas(sel.Object):
            return sel.Object
    doc = App.ActiveDocument
    found = insert.canvases(doc) if doc is not None else []
    return found[0] if len(found) == 1 else None


class CalibrateCommand(_Command):
    text = "Calibrate"
    tip = "Two points on the canvas and their real distance size the picture"
    icon = "calibrate"

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        canvas = _selected_canvas()
        if canvas is None:
            commands.tell("Pick the canvas first (right-click it in the browser > Calibrate).")
            return
        if not commands.finish_open_dialog():
            return
        _open(CalibratePanel, canvas)


class EditCanvasCommand(_Command):
    text = "Edit Canvas"
    tip = "Opacity, Display Through, position and scale of a canvas"
    icon = "canvas"

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        canvas = _selected_canvas()
        if canvas is None:
            commands.tell("Pick the canvas first (right-click it in the browser > Edit Canvas).")
            return
        _edit(CanvasPanel, canvas)


def edit_mesh(obj):
    return _edit(InsertMeshPanel, obj)


def edit_convert(obj):
    return _edit(ConvertMeshPanel, obj)


def edit_canvas(obj):
    return _edit(CanvasPanel, obj)


COMMANDS = {
    "SciForge_InsertMesh": InsertMeshCommand,
    "SciForge_ConvertMesh": ConvertMeshCommand,
    "SciForge_InsertSTEP": InsertStepCommand,
    "SciForge_InsertSVG": InsertSVGCommand,
    "SciForge_InsertDXF": InsertDXFCommand,
    "SciForge_InsertCanvas": InsertCanvasCommand,
    "SciForge_CalibrateCanvas": CalibrateCommand,
    "SciForge_EditCanvas": EditCanvasCommand,
}
EDITORS = {
    "SciForge::" + insert.TYPE_MESH: edit_mesh,
    "SciForge::" + insert.TYPE_CONVERT: edit_convert,
    "SciForge::" + insert.TYPE_CANVAS: edit_canvas,
}

try:
    install_watch()
except Exception as _exc:  # pragma: no cover - only without a GUI
    warn("canvas watch not installed: %s" % _exc)
