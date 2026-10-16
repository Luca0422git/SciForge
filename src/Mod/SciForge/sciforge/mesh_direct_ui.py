# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > MODIFY > Direct Edit: Fusion's Direct Mesh Editing environment.

Pick a mesh body; the dialog is Fusion's Mesh Selection Palette with the environment's
tools under it. Faces (triangles) are picked on the body:

* Selection Paint (a brush the size of Brush Size, click or drag over the body), Window
  (drag a box: left to right takes the faces wholly inside, right to left the faces it
  touches) or Free Form (draw round the faces); Ctrl takes faces off again; a click on
  the empty background clears the pick;
* Select Faces or Face Groups (a pick takes the whole face group); Select Back Faces (off:
  only faces turned towards you, and not hidden behind others, are taken);
* Grow (Shift+Up), Shrink (Shift+Down), Invert (Alt+N), Expand To Face Group (Alt+G),
  Expand To Connected (Alt+C), Clear.

Then Delete (Del), Erase and Fill, Create Face Group, Reverse Normal, Move (an arrow, a
Distance along the faces' normal or X / Y / Z, Apply Move) or Smooth the picked faces. Each
edit shows at once and is listed; Remove Last Edit takes the last one back. Finish Direct
Edit (or OK) keeps them all as one timeline step, a Mesh Base Feature; Cancel or Esc leaves
the body as it was. Double-clicking the step in the timeline opens it again with its edits.

The edits live in mesh_edit_core (no Qt, unit tested) and mesh.py (the step); the faces are
picked with SciForge's own rays through the body, so no FreeCAD selection is involved. Spec
and sources: docs/sciforge/parity/mesh.md, "Direct Edit"."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from . import insert_ui, log, mesh, mesh_pick_ui, mesh_ui, taskui, warn
from . import mesh_core as core
from . import mesh_edit_core as ec
from .compat import QtCore, QtGui, QtWidgets

V = App.Vector
LEFT = QtCore.Qt.LeftButton
CTRL = QtCore.Qt.ControlModifier
CLICK_SLOP = 5  # pixels: moving further is a drag (a box, a lasso, a paint stroke)
GROUP_STYLE = "QGroupBox { font-weight: bold; margin-top: 6px; }"


def _view_for(gl):
    from .orbit_ui import _view_for as view_for

    return view_for(gl)


def _coin_pixel(gl, pos):
    ratio = gl.devicePixelRatioF()
    return pos.x() * ratio, (gl.height() - pos.y()) * ratio


class _Stroke:
    """One left-button press on the 3D view being followed."""

    def __init__(self, pos, modifiers, mode):
        self.start = QtCore.QPointF(pos)
        self.remove = bool(modifiers & CTRL)
        self.mode = mode
        self.moved = False
        self.hit_body = False
        self.band = None


class _ViewMouse(QtCore.QObject):
    """The left button over the 3D view while Direct Edit picks faces: SciForge's own
    strokes (FreeCAD and SciForge's box selection never see them). The middle and right
    buttons, and a press on the Move arrow, go on as always."""

    def __init__(self, panel, gl):
        super().__init__()
        self.panel = panel
        self.gl = gl
        self.stroke = None
        gl.installEventFilter(self)

    def remove(self):
        try:
            if self.stroke is not None and self.stroke.band is not None:
                self.stroke.band.stop()
        except Exception:
            pass
        self.stroke = None
        try:
            self.gl.removeEventFilter(self)
        except Exception:
            pass
        self.panel = None

    def _is_gl(self, obj):
        try:
            return obj is self.gl or obj.metaObject().className() == "QOpenGLWidget"
        except Exception:
            return False

    def eventFilter(self, obj, event):
        try:
            panel = self.panel
            if panel is None or getattr(panel, "_closed", True) or not panel.taking_strokes():
                return False
            kind = event.type()
            if kind not in (
                QtCore.QEvent.MouseButtonPress,
                QtCore.QEvent.MouseMove,
                QtCore.QEvent.MouseButtonRelease,
                QtCore.QEvent.MouseButtonDblClick,
            ):
                return False
            if not self._is_gl(obj):
                return False
            if kind == QtCore.QEvent.MouseButtonPress:
                return self._pressed(event)
            if kind == QtCore.QEvent.MouseMove:
                return self._moved(event)
            if kind == QtCore.QEvent.MouseButtonRelease:
                return self._released(event)
            if kind == QtCore.QEvent.MouseButtonDblClick:
                return event.button() == LEFT
        except Exception as exc:
            self.stroke = None
            warn("Direct Edit: %s" % exc)
        return False

    def _pressed(self, event):
        if event.button() != LEFT:
            return False
        pos = QtCore.QPointF(event.position())
        if self.panel.on_handle(self.gl, pos):
            return False  # the Move arrow's drag
        self.stroke = _Stroke(pos, event.modifiers(), self.panel.selection_type())
        if self.stroke.mode == "Paint":
            self.stroke.hit_body = self.panel.paint_at(self.gl, pos, self.stroke.remove)
        return True

    def _moved(self, event):
        stroke = self.stroke
        if stroke is None:
            return False
        if not (event.buttons() & LEFT):
            self.stroke = None
            return False
        pos = QtCore.QPointF(event.position())
        if not stroke.moved:
            if math.hypot(pos.x() - stroke.start.x(), pos.y() - stroke.start.y()) <= CLICK_SLOP:
                return True
            stroke.moved = True
            if stroke.mode != "Paint":
                from . import selection_ui

                stroke.band = selection_ui.band_of(self.gl)
                stroke.band.start(stroke.start)
        if stroke.mode == "Paint":
            stroke.hit_body = self.panel.paint_at(self.gl, pos, stroke.remove) or stroke.hit_body
        else:
            from . import selection_core

            crossing = selection_core.box_mode(stroke.start.x(), pos.x()) == "crossing"
            stroke.band.follow(pos, crossing, stroke.mode == "Free Form")
        return True

    def _released(self, event):
        if event.button() != LEFT:
            return False
        stroke, self.stroke = self.stroke, None
        if stroke is None:
            return False
        pos = QtCore.QPointF(event.position())
        panel = self.panel
        if stroke.band is not None:
            polygon = stroke.band.shape()
            crossing = stroke.band.crossing
            stroke.band.stop()
            gl = self.gl
            QtCore.QTimer.singleShot(
                0, lambda: panel.guarded(panel.select_polygon, gl, polygon, crossing, stroke.remove)
            )
            return True
        if stroke.mode == "Paint":
            if not stroke.moved and not stroke.hit_body and not stroke.remove:
                QtCore.QTimer.singleShot(0, lambda: panel.guarded(panel.clear_selection))
            else:
                panel.painted()
            return True
        gl = self.gl
        QtCore.QTimer.singleShot(0, lambda: panel.guarded(panel.pick_at, gl, pos, stroke.remove))
        return True


class _Keys(QtCore.QObject):
    """The environment's keys while the dialog is open: Del deletes the picked faces,
    Shift+Up / Shift+Down grow / shrink the pick, Alt+N inverts it, Alt+G and Alt+C expand
    it to its face groups / to everything joined to it. Not while typing in a field."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        QtWidgets.QApplication.instance().installEventFilter(self)

    def remove(self):
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        self.panel = None

    def action(self, event):
        key = event.key()
        mods = event.modifiers() & (
            QtCore.Qt.ShiftModifier | QtCore.Qt.AltModifier | QtCore.Qt.ControlModifier
        )
        if key == QtCore.Qt.Key_Delete and not mods:
            return "delete"
        if mods == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Up:
            return "grow"
        if mods == QtCore.Qt.ShiftModifier and key == QtCore.Qt.Key_Down:
            return "shrink"
        if mods == QtCore.Qt.AltModifier:
            return {
                QtCore.Qt.Key_N: "invert",
                QtCore.Qt.Key_G: "expand_groups",
                QtCore.Qt.Key_C: "expand_connected",
            }.get(key)
        return None

    def eventFilter(self, obj, event):
        try:
            panel = self.panel
            kind = event.type()
            if panel is None or getattr(panel, "_closed", True):
                return False
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if not isinstance(event, QtGui.QKeyEvent):
                return False
            name = self.action(event)
            if name is None or panel.body is None:
                return False
            focus = QtWidgets.QApplication.focusWidget()
            editors = (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QTextEdit)
            if isinstance(focus, editors):
                return False
            event.accept()  # FreeCAD's own Del / Alt shortcuts do not fire meanwhile
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                QtCore.QTimer.singleShot(0, lambda: panel.guarded(panel.key_action, name))
            return True
        except Exception as exc:
            warn("Direct Edit keys: %s" % exc)
            return False


class DirectEditPanel(mesh_ui.MeshPanel):
    """Fusion's Direct Edit of a mesh body: the Mesh Selection Palette and the tools."""

    title = "Direct Edit"
    icon = "mesh_direct_edit"
    step_kind = "MeshDirectEdit"
    preview_box = False
    wait_text = "Click the mesh body to edit directly."

    # -- rows ---------------------------------------------------------------------------
    def build(self):
        self.selected = []  # facet indices of the step's current mesh
        self.edits = []
        self.marks = None
        self.mouse = None
        self.keys = None
        self.move_handle = None
        self._work = None  # (stamp, EditState, neighbours, FreeCAD mesh) of the step's mesh
        self._move_on = False
        self._move_picks = None  # the moved faces' centres before the move being set up
        self._base_centre = self._base_normal = None  # where the arrow starts, the normal
        self.value_boxes = taskui.ValueBoxes(self, default="move")

        # The Mesh Selection Palette
        palette = self._group("Selection")
        form = palette.layout()
        self.selection = QtWidgets.QComboBox()
        self.selection.setObjectName("SciForgeDirectEdit_selection")
        self.selection.addItems(ec.SELECTION_TYPES)
        self.selection.setCurrentText(ec.DEFAULT_SELECTION)
        self.selection.currentIndexChanged.connect(lambda *_: self.guarded(self._mode_changed))
        form.addRow("Selection", self.selection)
        self.brush = taskui.DistanceField(2.0, "mm", lambda _v: None)
        self.brush.widget.setObjectName("SciForgeDirectEdit_brush")
        form.addRow("Brush Size", self.brush.widget)
        self.select_filter = QtWidgets.QComboBox()
        self.select_filter.setObjectName("SciForgeDirectEdit_filter")
        self.select_filter.addItems(ec.SELECT_FILTERS)
        self.select_filter.currentIndexChanged.connect(
            lambda *_: self.guarded(self._filter_changed)
        )
        form.addRow("Select", self.select_filter)
        self.back_faces = QtWidgets.QCheckBox("Select Back Faces")
        self.back_faces.setObjectName("SciForgeDirectEdit_back_faces")
        form.addRow(self.back_faces)
        self.layout.addRow(palette)
        self.faces_field = self.add_field("faces", "Faces", "Select faces")
        self.faces_field.button.setObjectName("SciForgeDirectEdit_faces")
        self._buttons(
            ("Grow", "grow", "Shift+Up"),
            ("Shrink", "shrink", "Shift+Down"),
            ("Invert", "invert", "Alt+N"),
        )
        self._buttons(
            ("Expand To Face Group", "expand_groups", "Alt+G"),
            ("Expand To Connected", "expand_connected", "Alt+C"),
            ("Clear", "clear", ""),
        )

        # The environment's tools
        tools = self._group("Edit")
        form = tools.layout()
        row = QtWidgets.QWidget()
        box = QtWidgets.QGridLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        self.tool_buttons = {}
        for n, (text, name, tip) in enumerate(
            (
                ("Delete", "delete", "Delete the picked faces (Del); the hole stays open"),
                ("Erase and Fill", "erase_fill", "Erase the picked faces and fill the gap"),
                ("Create Face Group", "group", "Make the picked faces one face group"),
                ("Reverse Normal", "reverse", "Turn the picked faces over"),
            )
        ):
            button = QtWidgets.QPushButton(text)
            button.setObjectName("SciForgeDirectEdit_" + name)
            button.setToolTip(tip)
            button.clicked.connect(lambda _=False, op=name: self.guarded(self.do_edit, op))
            box.addWidget(button, n // 2, n % 2)
            self.tool_buttons[name] = button
        form.addRow(row)
        self.fill = QtWidgets.QComboBox()
        self.fill.setObjectName("SciForgeDirectEdit_fill")
        self.fill.addItems(core.ERASE_FILL_TYPES)
        self.fill.currentIndexChanged.connect(lambda *_: self.guarded(self._fill_changed))
        form.addRow("Erase and Fill Type", self.fill)
        self.density = QtWidgets.QDoubleSpinBox()
        self.density.setObjectName("SciForgeDirectEdit_density")
        self.density.setRange(0.0, 1.0)
        self.density.setSingleStep(0.05)
        self.density.setValue(core.ERASE_DENSITY)
        form.addRow("Density", self.density)
        # Move
        self.move_button = QtWidgets.QPushButton("Move")
        self.move_button.setObjectName("SciForgeDirectEdit_move")
        self.move_button.setCheckable(True)
        self.move_button.setToolTip("Move the picked faces: drag the arrow or type a Distance")
        self.move_button.clicked.connect(lambda on=False: self.guarded(self.set_move, bool(on)))
        form.addRow(self.move_button)
        self.direction = QtWidgets.QComboBox()
        self.direction.setObjectName("SciForgeDirectEdit_direction")
        self.direction.addItems(ec.MOVE_DIRECTIONS)
        self.direction.currentIndexChanged.connect(lambda *_: self.guarded(self._direction_changed))
        form.addRow("Direction", self.direction)
        self.distance = taskui.DistanceField(
            0.0, "mm", lambda _v: self.guarded(self._distance_changed)
        )
        self.distance.widget.setObjectName("SciForgeDirectEdit_distance")
        form.addRow("Distance", self.distance.widget)
        self.apply_move = QtWidgets.QPushButton("Apply Move")
        self.apply_move.setObjectName("SciForgeDirectEdit_apply_move")
        self.apply_move.clicked.connect(lambda _=False: self.guarded(self.commit_move))
        form.addRow(self.apply_move)
        # Smooth
        self.smoothness = QtWidgets.QDoubleSpinBox()
        self.smoothness.setObjectName("SciForgeDirectEdit_smoothness")
        self.smoothness.setRange(0.0, 1.0)
        self.smoothness.setDecimals(2)
        self.smoothness.setSingleStep(0.05)
        self.smoothness.setValue(ec.DEFAULT_SMOOTHNESS)
        form.addRow("Smoothness", self.smoothness)
        self.smooth_button = QtWidgets.QPushButton("Smooth")
        self.smooth_button.setObjectName("SciForgeDirectEdit_smooth")
        self.smooth_button.setToolTip("Smooth the picked faces (their rim stays where it is)")
        self.smooth_button.clicked.connect(lambda _=False: self.guarded(self.do_edit, "smooth"))
        form.addRow(self.smooth_button)
        self.layout.addRow(tools)

        # The edits made so far
        done = self._group("Edits")
        form = done.layout()
        self.edit_list = QtWidgets.QListWidget()
        self.edit_list.setObjectName("SciForgeDirectEdit_edits")
        self.edit_list.setMinimumHeight(70)
        form.addRow(self.edit_list)
        self.undo_button = QtWidgets.QPushButton("Remove Last Edit")
        self.undo_button.setObjectName("SciForgeDirectEdit_remove_last")
        self.undo_button.clicked.connect(lambda _=False: self.guarded(self.remove_last))
        form.addRow(self.undo_button)
        self.layout.addRow(done)
        self.finish_button = QtWidgets.QPushButton("Finish Direct Edit")
        self.finish_button.setObjectName("SciForgeDirectEdit_finish")
        self.finish_button.clicked.connect(
            lambda _=False: QtCore.QTimer.singleShot(0, self._finish)
        )
        self.layout.addRow(self.finish_button)
        self._fill_changed()
        self._show_move_rows()

    def _group(self, title):
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(GROUP_STYLE)
        group.setLayout(QtWidgets.QFormLayout())
        return group

    def _buttons(self, *entries):
        row = QtWidgets.QWidget()
        box = QtWidgets.QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        for text, name, key in entries:
            button = QtWidgets.QPushButton(text)
            button.setObjectName("SciForgeDirectEdit_" + name)
            if key:
                button.setToolTip("%s (%s)" % (text, key))
            button.clicked.connect(lambda _=False, n=name: self.guarded(self.key_action, n))
            box.addWidget(button)
        self.layout.addRow(row)

    def first_waiting(self):
        return "faces"

    def after_body(self):
        self._work = None
        if not self.editing:
            try:
                size = mesh.size_of(mesh.global_mesh(self.body))
                self.brush.set_value(round(max(size * ec.BRUSH_FRACTION, 0.1), 2))
            except Exception:
                pass
        self._install_input()

    def _install_input(self):
        if self.mouse is None:
            gl = taskui.view_widget()
            if gl is not None:
                self.mouse = _ViewMouse(self, gl)
        if self.keys is None:
            self.keys = _Keys(self)

    def load(self, feature):
        self.edits = mesh.direct_edits(feature)
        self._show_edits()

    def write(self, step):
        mesh.set_direct_edits(step, self.edits)

    def taking_strokes(self):
        return self.body is not None and self.step is not None and self.active == "faces"

    def selection_type(self):
        return self.selection.currentText()

    def cleared(self, name):
        if name == "faces":
            self.clear_selection()

    # -- the working mesh ---------------------------------------------------------------
    def work(self):
        """(EditState, facet neighbours, FreeCAD mesh) of the body as the step shows it now
        (every edit so far, and a move being dragged)."""
        if self.step is None:
            return None
        try:
            fc = self.step.Mesh
            stamp = (fc.CountFacets, fc.CountPoints, round(fc.Area, 9), round(fc.BoundBox.ZMax, 9))
        except Exception:
            return None
        if self._work is None or self._work[0] != stamp:
            shown = mesh.global_mesh(self.step)
            groups = list(getattr(self.step, "FaceGroups", []) or [])
            state = mesh.edit_state(shown, groups)
            self._work = (stamp, state, core.facet_neighbours(state.facets), shown)
        return self._work[1:]

    def _facet_under(self, gl, pos):
        """The face of the body under widget pixel `pos` (the nearest along the mouse ray),
        or None."""
        from .profile_pick import mouse_ray

        work = self.work()
        view = _view_for(gl)
        if work is None or view is None:
            return None
        state, _near, shown = work
        x, y = _coin_pixel(gl, pos)
        point, ray = mouse_ray(view, (int(round(x)), int(round(y))))
        if ray.Length < 1e-12:
            return None
        ray = V(ray)
        ray.normalize()
        size = shown.BoundBox.DiagonalLength
        start = point - ray * (size * 4.0 + 1.0)
        rot = view.getCameraOrientation()
        right, up = rot.multVec(V(1, 0, 0)), rot.multVec(V(0, 1, 0))
        # A ray right through a corner (a sphere's pole) can slip between the faces there
        # (FreeCAD's float test) and meet the far side first: four rays a hair apart, and the
        # nearest face any of them meets is the one under the pointer.
        nudge = max(size * 2e-5, 1e-6)
        best = None
        for dx, dy in ((0.0, 0.0), (1.0, 0.6), (-0.8, 1.0), (0.6, -1.0)):
            origin = start + right * (dx * nudge) + up * (dy * nudge)
            try:
                hit = shown.nearestFacetOnRay(tuple(origin), tuple(ray))
            except Exception:
                hit = None
            if not hit:
                continue
            index, where = list(hit.items())[0]
            depth = (V(*where) - origin).Length
            if best is None or depth < best[0] - 1e-9:
                best = (depth, int(index))
        if best is None:
            return None
        index = best[1]
        if not self.back_faces.isChecked():
            look, eye = self._camera(view)
            if not ec.facing(state.points, state.facets, [index], look, eye):
                return None
        return index

    def _camera(self, view):
        look = tuple(view.getViewDirection())
        eye = None
        try:
            if view.getCameraType() == "Perspective":
                eye = tuple(view.getCameraNode().position.getValue().getValue())
        except Exception:
            eye = None
        return look, eye

    # -- picking ------------------------------------------------------------------------
    def paint_at(self, gl, pos, remove):
        """Paint selection: the faces within the Brush Size around the face under the mouse
        join the pick (Ctrl: leave it). True when the mouse is over the body."""
        seed = self._facet_under(gl, pos)
        if seed is None:
            return False
        state, near, _shown = self.work()
        radius = max(float(self.brush.value()), 0.0)
        found = core.facets_near(state.points, state.facets, seed, radius, near)
        if not self.back_faces.isChecked():
            look, eye = self._camera(_view_for(gl))
            found = ec.facing(state.points, state.facets, found, look, eye) or [seed]
        self._take(found, remove, quiet=True)
        return True

    def painted(self):
        """A paint stroke ended: the dialog says what is picked."""
        self._selection_changed()

    def pick_at(self, gl, pos, remove):
        """A click in Window or Free Form selection: the face under the mouse."""
        seed = self._facet_under(gl, pos)
        if seed is None:
            if not remove:
                self.clear_selection()
            return
        self._take([seed], remove)

    def select_polygon(self, gl, polygon, crossing, remove):
        """A Window box or a Free Form lasso (widget pixels): the faces inside it (a box
        drawn right to left: the faces it touches). With Select Back Faces off only faces
        turned towards you and in view are taken."""
        view = _view_for(gl)
        work = self.work()
        if view is None or work is None or len(polygon) < 3:
            return
        state, _near, shown = work
        ratio = gl.devicePixelRatioF()
        coin_polygon = [(x * ratio, (gl.height() - y) * ratio) for x, y in polygon]
        screen = self._project(view, state.points)
        found = ec.in_polygon(screen, state.facets, coin_polygon, crossing)
        if not self.back_faces.isChecked():
            look, eye = self._camera(view)
            found = ec.facing(state.points, state.facets, found, look, eye)
            found = self._in_view(state, shown, found, look, eye)
        self._take(found, remove)
        log("Direct Edit: %s took %d faces" % ("crossing" if crossing else "window", len(found)))

    def _project(self, view, points):
        """Coin pixel of every point (an orthographic view: one exact affine map)."""
        if not points:
            return []
        try:
            orthographic = view.getCameraType() != "Perspective"
        except Exception:
            orthographic = True
        if not orthographic:
            out = []
            for p in points:
                try:
                    x, y = view.getPointOnViewport(V(*p))
                    out.append((float(x), float(y)))
                except Exception:
                    out.append(None)
            return out
        c = core.scale(core.add(*core.bounds(points)), 0.5)
        base = view.getPointOnViewport(V(*c))
        cols = []
        for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
            q = view.getPointOnViewport(V(*core.add(c, axis)))
            cols.append((q[0] - base[0], q[1] - base[1]))
        bx, by = float(base[0]), float(base[1])
        out = []
        for p in points:
            dx, dy, dz = p[0] - c[0], p[1] - c[1], p[2] - c[2]
            out.append(
                (
                    bx + cols[0][0] * dx + cols[1][0] * dy + cols[2][0] * dz,
                    by + cols[0][1] * dx + cols[1][1] * dy + cols[2][1] * dz,
                )
            )
        return out

    def _in_view(self, state, shown, found, look, eye):
        """The faces of `found` nothing of the body hides (the first face the line of sight
        to its centre meets is the face itself)."""
        size = shown.BoundBox.DiagonalLength
        tol = max(size * 1e-4, 1e-6)
        out = []
        for i in found:
            centre = core.centroid(state.points, state.facets[i])
            if eye is not None:
                ray = core.sub(centre, eye)
            else:
                ray = look
            try:
                ray = core.unit(ray)
            except core.MeshError:
                continue
            start = core.sub(centre, core.scale(ray, size * 2.0 + 1.0))
            try:
                hit = shown.nearestFacetOnRay(start, ray)
            except Exception:
                hit = None
            if not hit:
                out.append(i)
                continue
            index, point = list(hit.items())[0]
            if int(index) == i:
                out.append(i)
                continue
            depth = core.dot(core.sub(tuple(point), centre), ray)
            if depth >= -tol:
                out.append(i)  # the hit lies at the centre's depth: a neighbour, not in front
        return out

    def _take(self, found, remove, quiet=False):
        if self._move_on:
            self.commit_move()
        if self.select_filter.currentText() == "Face Groups":
            state = self.work()[0]
            found = ec.expand_to_groups(state.groups, found)
        current = set(self.selected)
        if remove:
            current -= set(found)
        else:
            current |= set(found)
        self.set_selection(sorted(current), quiet)

    def set_selection(self, indices, quiet=False):
        self.selected = list(indices)
        count = len(self.selected)
        self.faces_field.set_text("%d face%s" % (count, "" if count == 1 else "s") if count else "")
        self.draw_marks()
        if not quiet:
            self._selection_changed()

    def _selection_changed(self):
        if self._move_on:
            self._place_handle()
        self.report()

    def clear_selection(self):
        if self._move_on:
            self.commit_move()
        self.set_selection([])

    def key_action(self, name):
        """A palette button or key: Grow, Shrink, Invert, the expands, Clear, Delete."""
        if name == "delete":
            self.do_edit("delete")
            return
        if name == "clear":
            self.clear_selection()
            return
        work = self.work()
        if work is None:
            return
        state, near, _shown = work
        if name == "invert":
            found = ec.invert(len(state.facets), self.selected)
        elif not self.selected:
            self.message.setText("⚠ Pick faces first (click or paint them on the body).")
            return
        elif name == "grow":
            found = ec.grow(state.facets, self.selected)
        elif name == "shrink":
            found = ec.shrink(state.facets, self.selected)
        elif name == "expand_groups":
            if core.group_count(state.groups) < 2:
                self.message.setText(
                    "⚠ The body has no face groups yet: Create Face Group, or PREPARE > "
                    "Generate Face Groups."
                )
                return
            found = ec.expand_to_groups(state.groups, self.selected)
        elif name == "expand_connected":
            found = ec.expand_connected(state.facets, self.selected, near)
        else:
            return
        if self._move_on:
            self.commit_move()
        self.message.setText("")
        self.set_selection(found)

    def draw_marks(self):
        if self.view is None:
            return
        try:
            if self.marks is None:
                self.marks = mesh_pick_ui.FacetMarks(self.view)
            work = self.work()
            if work is not None:
                state = work[0]
                self.marks.show(state.points, state.facets, self.selected)
        except Exception as exc:
            log("face marks: %s" % exc)

    def picked_centres(self):
        work = self.work()
        if work is None:
            return []
        return work[0].centres(self.selected)

    # -- the tools ----------------------------------------------------------------------
    def do_edit(self, op):
        """Delete, Erase and Fill, Create Face Group, Reverse Normal or Smooth the picked
        faces: one edit, shown at once."""
        if self.step is None:
            self.message.setText("⚠ " + self.wait_text)
            return
        if self._move_on:
            self.commit_move()
        if not self.selected:
            self.message.setText(
                "⚠ Pick the faces first: paint over them, or drag a box (Selection Window)."
            )
            return
        params = {}
        if op == "erase_fill":
            params = {"fill": self.fill.currentText(), "density": float(self.density.value())}
        elif op == "smooth":
            params = {"smoothness": float(self.smoothness.value())}
        edit = ec.make_edit(op, self.picked_centres(), **params)
        if not self._can_do(edit):
            return
        keep = op in ("group", "reverse", "smooth")
        self._add_edit(edit, keep_selection=keep)

    def _can_do(self, edit):
        """Try the edit on a copy first: one that cannot be done says why and is left out."""
        work = self.work()
        trial = work[0].copy()
        try:
            ec.apply(trial, edit)
        except core.MeshError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        return True

    def _add_edit(self, edit, keep_selection=False):
        kept = list(self.selected) if keep_selection else []
        self.edits.append(edit)
        self.message.setText("")
        self._commit_step()
        self._show_edits()
        self.set_selection(kept, quiet=True)
        log("Direct Edit: %s" % ec.describe(edit))

    def _commit_step(self):
        if self.step is None:
            return
        self.write(self.step)
        self.step.touch()
        self._work = None
        self._recompute_now()

    def _recompute_now(self):
        self._timer.stop()
        self._recompute()
        self._work = None
        self.draw_marks()

    def remove_last(self):
        if self._move_on:
            self.set_move(False)
        if not self.edits:
            self.message.setText("⚠ There is no edit to take back.")
            return
        gone = self.edits.pop()
        self._commit_step()
        self._show_edits()
        self.set_selection([], quiet=True)
        self.report()
        log("Direct Edit: took back %s" % ec.describe(gone))

    def _show_edits(self):
        self.edit_list.clear()
        for n, edit in enumerate(self.edits, start=1):
            self.edit_list.addItem("%d  %s" % (n, ec.describe(edit)))
        self.undo_button.setEnabled(bool(self.edits))

    def _fill_changed(self):
        self.density.setEnabled(self.fill.currentText() == "Uniform")

    def _mode_changed(self):
        self.brush.widget.setEnabled(self.selection_type() == "Paint")

    def _filter_changed(self):
        if self.select_filter.currentText() == "Face Groups" and self.selected:
            state = self.work()[0]
            self.set_selection(ec.expand_to_groups(state.groups, self.selected))

    # -- Move -----------------------------------------------------------------------------
    def _show_move_rows(self):
        on = self._move_on
        for widget in (self.direction, self.distance.widget, self.apply_move):
            widget.setEnabled(on)
        self.move_button.setChecked(on)

    def set_move(self, on):
        """Move on: an arrow on the picked faces, Distance and Direction; off: the move not
        applied yet is dropped."""
        if on and not self.selected:
            self.move_button.setChecked(False)
            self.message.setText("⚠ Pick the faces to move first.")
            return
        if not on and self._move_on:
            self._drop_pending()
        self._move_on = bool(on)
        self.message.setText("")
        if on:
            self._set_distance_quiet(0.0)
            self._place_handle()
        else:
            self._remove_handle()
        self._show_move_rows()

    def _move_normal(self):
        work = self.work()
        if work is None or not self.selected:
            return None
        state = work[0]
        return ec.mean_normal(state.points, state.facets, self.selected)

    def _direction_vector(self, normal=None):
        """The unit direction of the move: the picked faces' mean normal (as they were
        before the move), or X / Y / Z. None when the faces have no common normal."""
        name = self.direction.currentText()
        if name == "Normal":
            return normal if normal is not None else self._base_normal
        return {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}[name]

    def _place_handle(self):
        """The arrow at the picked faces (as they were before the move being set up),
        along the Direction."""
        self._remove_handle()
        if not self._move_on or not self.selected or self.view is None:
            return
        work = self.work()
        if work is None:
            return
        state = work[0]
        distance = float(self.distance.value())
        centre = ec.centre_of(state.points, state.facets, self.selected)
        normal = ec.mean_normal(state.points, state.facets, self.selected)
        if self._pending_edit() is None:
            self._base_centre, self._base_normal = centre, normal
        direction = self._direction_vector(self._base_normal)
        if direction is None or self._base_centre is None:
            self.message.setText(
                "⚠ The picked faces have no common direction: move them along X, Y or Z."
            )
            return
        from . import handles3d

        try:
            origin = V(*self._base_centre)
            size = taskui.handle_size_at(self.view, origin, hi=mesh.size_of(work[2]) * 0.6)
            self.move_handle = handles3d.LinearHandle(
                origin,
                V(*direction),
                distance,
                size,
                on_drag=self._dragged,
                on_release=self._released,
            )
            self.value_boxes.attach(
                self.move_handle, "move", lambda: self.distance.widget.text(), self._typed
            )
        except Exception as exc:
            warn("Direct Edit arrow: %s" % exc)

    def _remove_handle(self):
        if self.move_handle is not None:
            try:
                self.move_handle.remove()
            except Exception:
                pass
            self.move_handle = None

    def on_handle(self, gl, pos):
        """A press on the Move arrow (or any handle of the dialog): its drag."""
        if self.move_handle is not None:
            try:
                if self.move_handle.hit(_coin_pixel(gl, pos)):
                    return True
            except Exception:
                pass
        try:
            from . import selection_ui

            return bool(selection_ui._handle_under(gl, pos))
        except Exception:
            return False

    def _set_distance_quiet(self, value):
        self._quiet = True
        try:
            self.distance.set_value(value)
        finally:
            self._quiet = False

    def _dragged(self, value):
        try:
            self._set_distance_quiet(round(float(value), 3))
            self._preview_move()
        except Exception as exc:
            warn("Direct Edit drag: %s" % exc)

    def _released(self, _value=None):
        pass

    def _typed(self, text):
        try:
            value = self.distance.parse(text)
            self.distance.set_value(value)
            if self.move_handle is not None:
                self.move_handle.set_value(value)
            self._preview_move()
            return True
        except ValueError as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        except Exception as exc:
            warn("Direct Edit: %s" % exc)
            return False

    def _distance_changed(self):
        if not self._move_on:
            return
        if self.move_handle is not None:
            self.move_handle.set_value(float(self.distance.value()))
        self._preview_move()

    def _direction_changed(self):
        if self._move_on:
            self._place_handle()
            self._preview_move()

    def _pending_edit(self):
        return mesh.pending(self.step) if self.step is not None else None

    def _move_edit(self):
        distance = float(self.distance.value())
        if abs(distance) < 1e-9 or not self.selected:
            return None
        direction = self._direction_vector(self._base_normal)
        if direction is None:
            return None
        vector = core.scale(core.unit(direction), distance)
        picks = self._move_picks
        if self._pending_edit() is None or picks is None:
            picks = self.picked_centres()
            self._move_picks = picks
        return ec.make_edit("move", picks, vector=vector)

    def _preview_move(self):
        """The move being set up shows on the body (not yet one of the edits)."""
        if self.step is None:
            return
        edit = self._move_edit()
        mesh.set_pending(self.step, edit)
        if edit is None:
            self._move_picks = None
        self.step.touch()
        self.schedule()

    def _drop_pending(self):
        if self.step is not None and self._pending_edit() is not None:
            mesh.set_pending(self.step, None)
            self.step.touch()
            self._move_picks = None
            self._recompute_now()

    def commit_move(self):
        """Apply Move: the move set up becomes one of the edits; the faces stay picked."""
        edit = self._move_edit()
        mesh.set_pending(self.step, None)
        self._move_picks = None
        self._move_on = False
        self._remove_handle()
        self._show_move_rows()
        if edit is None:
            self._recompute_now()
            return
        self._add_edit(edit, keep_selection=True)

    def _recompute(self):
        super()._recompute()
        if not getattr(self, "_closed", False):
            self._work = None
            self.draw_marks()

    # -- finishing ----------------------------------------------------------------------
    def _finish(self):
        try:
            if not getattr(self, "_closed", False) and self.accept():
                return
        except Exception as exc:
            warn("Direct Edit: %s" % exc)

    def _accept(self):
        if self.step is not None and self._move_on:
            self.commit_move()
        if self.step is not None and not self.edits:
            self.message.setText(
                "⚠ No edit yet: pick faces and Delete, Move, Smooth... them (or Cancel)."
            )
            return False
        return mesh_ui.MeshPanel._accept(self)

    def report(self):
        mesh_ui.MeshPanel.report(self)
        if self.step is not None and not self.edits and not self.selected:
            self.say(
                "Paint over the faces to edit (Selection: Window to drag a box, Free Form "
                "to draw round them), then Delete, Move, Smooth..."
            )

    def cleanup(self):
        try:
            if self.step is not None:
                mesh.set_pending(self.step, None)
        except Exception:
            pass
        for holder in ("mouse", "keys"):
            item = getattr(self, holder, None)
            if item is not None:
                try:
                    item.remove()
                except Exception:
                    pass
                setattr(self, holder, None)
        self._remove_handle()
        try:
            self.value_boxes.discard()
        except Exception:
            pass
        if self.marks is not None:
            self.marks.remove()
            self.marks = None
        mesh_ui.MeshPanel.cleanup(self)


class DirectEditCommand(mesh_ui._MeshCommand):
    text = "Direct Edit"
    tip = "Edit the faces of a mesh body directly: delete, fill, group, turn, move, smooth"
    icon = "mesh_direct_edit"
    panel = DirectEditPanel


def _edit(obj):
    return insert_ui._edit(DirectEditPanel, mesh.step_of(obj))


COMMANDS = {"SciForge_MeshDirectEdit": DirectEditCommand}
EDITORS = {"SciForge::MeshDirectEdit": _edit}
_ = Gui
