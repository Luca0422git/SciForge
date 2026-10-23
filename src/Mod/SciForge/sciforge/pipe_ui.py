# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pipe (SOLID > CREATE > Pipe) with Fusion's dialog.

Path: click sketch curves or edges of the model (with Chain Selection on, the curves
joined to a clicked one without a corner come along); click a picked one again to drop
it. Edges selected before the command are taken at once. The pipe follows the path with
a round, square or triangular section (Section Size: the diameter of the circle round
it), solid or Hollow with a wall Section Thickness. Distance (0..1) is how far along the
path it goes: drag the blue ball along the path or type it. The blue arrow at the start
sets the section size. Operation Join / Cut / Intersect / New Body / New Component; a pipe
that runs mostly inside the part becomes a Cut unless you picked the operation, one that
touches nothing a New Body (also when Join was picked: Fusion never leaves a separate piece).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, handle_look_core, log, pipe, preview, primitives, profile_pick
from . import ui_icon_path, value_limits, warn
from .compat import QtCore, QtWidgets
from .primitives import PrimitiveError
from .primitives_ui import (
    OPERATION_LABELS,
    LinearHandle,
    SelectionField,
    EnterTakesNumber,
    _plain,
    clear_selection_soon,
    combo,
    safe,
    set_combo,
)
from .taskui import DistanceField, Panel, ValueBoxes

SECTION_LABELS = [("Circular", "circular"), ("Square", "square"), ("Triangular", "triangular")]
PATH_COLOR = (0.12, 0.53, 0.90)


class PathHandle(LinearHandle):
    """The Distance handle: a blue ball that slides along the path (0 = start, 1 = end)."""

    SHAPE = "ball"

    def __init__(self, points, fraction, size, on_drag=None, on_release=None):
        self.points = [App.Vector(p) for p in points]
        self.lengths = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.lengths.append(self.lengths[-1] + (b - a).Length)
        self.total = max(self.lengths[-1], 1e-9)
        tangent = self._tangent(fraction)
        super().__init__(
            self.points[0],
            tangent,
            fraction,
            size,
            on_drag=on_drag,
            on_release=on_release,
            name="distance",
        )

    def snap(self, value):
        return value  # a fraction of the path: the dialog rounds it to 0.01

    def _segment(self, fraction):
        goal = max(0.0, min(1.0, float(fraction))) * self.total
        for i in range(1, len(self.lengths)):
            if self.lengths[i] >= goal - 1e-12 or i == len(self.lengths) - 1:
                span = max(self.lengths[i] - self.lengths[i - 1], 1e-12)
                return i, (goal - self.lengths[i - 1]) / span
        return len(self.lengths) - 1, 1.0

    def point_at(self, value):
        i, t = self._segment(value)
        a, b = self.points[i - 1], self.points[i]
        return a + (b - a) * t

    def _tangent(self, value):
        i, _ = self._segment(value)
        d = self.points[i] - self.points[i - 1]
        if d.Length < 1e-12:
            return App.Vector(1, 0, 0)
        d.normalize()
        return d

    def _draw(self):
        if self._shown is not None and abs(self._shown - self._value) < 1e-12:
            return
        self._shown = self._value
        p = self.position()
        self.place.translation.setValue(p.x, p.y, p.z)
        rotation = App.Rotation(App.Vector(0, 1, 0), self._tangent(self._value))
        self.place.rotation.setValue(*rotation.Q)
        self.flip.angle.setValue(0.0)

    def hit(self, position):
        try:
            bx, by = self._screen(self.position())
            reach = handle_look_core.grab_px("ball", at_least=self.GRAB_PIXELS)
            return math.hypot(float(position[0]) - bx, float(position[1]) - by) <= reach
        except Exception:
            return False

    def _along(self, position):
        """The fraction of the path nearest the mouse on screen."""
        mx, my = float(position[0]), float(position[1])
        best = None
        screen = [self._screen(p) for p in self.points]
        for i in range(1, len(screen)):
            (ax, ay), (bx, by) = screen[i - 1], screen[i]
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 < 1e-9 else ((mx - ax) * dx + (my - ay) * dy) / length2
            t = max(0.0, min(1.0, t))
            d = math.hypot(mx - (ax + dx * t), my - (ay + dy * t))
            if best is None or d < best[0]:
                at = self.lengths[i - 1] + (self.lengths[i] - self.lengths[i - 1]) * t
                best = (d, at / self.total)
        return best[1] if best is not None else self._value


class PathLook:
    """The picked path drawn as a thick blue line over the part (the selection itself is
    cleared after every click, like the other SciForge dialogs)."""

    def __init__(self, view):
        from pivy import coin

        self.view = view
        self.root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(4.0)
        self.root.addChild(style)
        color = coin.SoBaseColor()
        color.rgb.setValue(*PATH_COLOR)
        self.root.addChild(color)
        self.coords = coin.SoCoordinate3()
        self.lines = coin.SoLineSet()
        self.lines.numVertices.setValue(0)
        self.root.addChild(self.coords)
        self.root.addChild(self.lines)
        view.getSceneGraph().addChild(self.root)

    def show(self, path):
        points, counts = [], []
        for obj, sub in path:
            try:
                edge = pipe._global_edge(obj, sub)
                pts = edge.discretize(max(2, int(edge.Length / 0.5) + 2))[:200]
            except Exception:
                continue
            points += [(p.x, p.y, p.z) for p in pts]
            counts.append(len(pts))
        self.coords.point.setNum(len(points))
        if points:
            self.coords.point.setValues(0, len(points), points)
        self.lines.numVertices.setNum(len(counts))
        if counts:
            self.lines.numVertices.setValues(0, len(counts), counts)

    def remove(self):
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass


class PipePanel(Panel, value_limits.LimitedValues):
    """Pipe. A Section Thickness typed past what the section can hold (or a Section Size
    dragged or typed under what the wall needs) stops at the value that still works and the
    dialog says so (Luca, 2026-10-21; Fusion refuses it: value_limits.py)."""

    title = "Pipe"
    icon = "pipe"
    last = None
    MESSAGE_LINES = 3

    def __init__(self, doc, feature=None):
        super().__init__(doc, "Pipe" if feature is None else "Edit Pipe")
        PipePanel.last = self
        try:
            primitives.drop_orphans(doc)  # helpers a timeline Delete left behind
        except Exception as exc:
            warn("could not tidy up helpers: %s" % exc)
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        # The value box next to each handle (the ball on the path, the section size arrow).
        self.value_boxes = ValueBoxes(self, default="section_size")
        self._last_handle = None
        self.target = feature
        self.editing = feature is not None
        self.body = commands.find_body() if feature is None else pipe.owner_body(feature)
        self.seeds = []
        self.path = []
        self.options = pipe.with_defaults({})
        self.user_picked_operation = feature is not None
        self.error = ""
        self.dirty = False
        self.handles = {}
        self.observer = None
        self.look = None
        self._quiet = False
        self._geometry_changed = False
        self._shown = []
        self.size_set = feature is not None  # the section size was chosen (not a default)
        self.thickness_set = feature is not None  # the wall was typed (not a default)
        self.limit_init()
        self._limit_next = None  # (value name, "typed" / "dragged") the next _collect() holds
        if feature is not None:
            try:
                self.path, read = pipe.read(feature)
                self.options.update(read)
                self.seeds = list(self.path)
            except Exception as exc:
                warn("could not read %s: %s" % (feature.Label, exc))
            self._show_sketches()
            clear_selection_soon()  # the timeline's click selected the pipe being edited
        self._build_form()
        self._show_fields()
        self._watch()
        if feature is not None:
            self._refresh_path()
            self._make_handles()
        else:
            self._start()

    # -- form --------------------------------------------------------------------------------------------
    def _build_form(self):
        form = self.layout
        self.path_field = SelectionField(self, "path", "Select path")
        form.addRow("Path", self.path_field.widget)
        self.chain = QtWidgets.QCheckBox("Chain Selection")
        self.chain.setObjectName("SciForgePipe_chain")
        form.addRow(self.chain)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #8cc4ff;")
        form.addRow(self.info)
        self.distance = QtWidgets.QDoubleSpinBox()
        self.distance_box = _Field(self.distance)  # where numbers typed over the view go
        self.distance.setObjectName("SciForgePipe_distance")
        self.distance.setDecimals(2)
        self.distance.setRange(0.01, 1.0)
        self.distance.setSingleStep(0.05)
        form.addRow("Distance", self.distance)
        self.section = combo(SECTION_LABELS, self.options["section"], "SciForgePipe_section")
        form.addRow("Section", self.section)
        self.size = DistanceField(self.options["section_size"], on_change=self._size_typed)
        self.size.widget.setObjectName("SciForgePipe_size")
        self.size.enter_filter = EnterTakesNumber(self.size)
        form.addRow("Section Size", self.size.widget)
        self.hollow = QtWidgets.QCheckBox("Hollow")
        self.hollow.setObjectName("SciForgePipe_hollow")
        form.addRow(self.hollow)
        self.thickness = DistanceField(self.options["thickness"], on_change=self._thickness_typed)
        self.thickness.widget.setObjectName("SciForgePipe_thickness")
        self.thickness.enter_filter = EnterTakesNumber(self.thickness)
        self.thickness_label = QtWidgets.QLabel("Section Thickness")
        form.addRow(self.thickness_label, self.thickness.widget)
        self.operation = combo(OPERATION_LABELS, self.options["operation"], "SciForgeOperation")
        form.addRow("Operation", self.operation)
        self.formulas = QtWidgets.QLabel("")  # values that follow a parameter
        self.formulas.setWordWrap(True)
        self.formulas.setStyleSheet("color: #b8c7d9;")
        form.addRow(self.formulas)
        self.finish_layout()
        self.limit_label = value_limits.note_label()  # "Largest that fits here: ..."
        form.addRow(self.limit_label)
        self.formula_error = ""
        self.formula_fields = {"section_size": self.size, "thickness": self.thickness}
        self.formula_inputs = [
            preview.FormulaInput(self, key, field) for key, field in self.formula_fields.items()
        ]
        try:
            lines = self.message.fontMetrics().lineSpacing()
            self.message.setMinimumHeight(lines * self.MESSAGE_LINES + 4)
        except Exception:
            pass
        self.chain.toggled.connect(self._chain_toggled)
        self.distance.valueChanged.connect(self._typed)
        self.section.currentIndexChanged.connect(self._typed)
        self.hollow.toggled.connect(self._typed)
        self.operation.activated.connect(self._operation_picked)

    def _show_fields(self):
        o = self.options
        self._quiet = True
        try:
            self.chain.setChecked(bool(o.get("chain", True)))
            self.distance.setValue(float(o["distance"]))
            set_combo(self.section, o["section"])
            self.size.set_value(o["section_size"])
            self.hollow.setChecked(bool(o["hollow"]))
            self.thickness.set_value(o["thickness"])
            set_combo(self.operation, o["operation"])
        finally:
            self._quiet = False
        self._update_visibility()
        self.show_formulas()

    def _update_visibility(self):
        for widget in (self.thickness.widget, self.thickness_label):
            widget.setVisible(self.hollow.isChecked())

    def _collect(self):
        o = self.options
        o["chain"] = self.chain.isChecked()
        o["distance"] = self.distance.value()
        o["section"] = self.section.currentData()
        o["section_size"] = abs(self.size.value())
        o["hollow"] = self.hollow.isChecked()
        o["thickness"] = abs(self.thickness.value())
        o["operation"] = self.operation.currentData()
        self._hold_collected()

    # -- values past what fits (value_limits.LimitedValues) ---------------------------------------
    def _hold_collected(self):
        """The value just typed or dragged held at its limit (the note says so); the other
        boxes' values held at the limits known for them. Never a formula's value."""
        edited, self._limit_next = self._limit_next, None
        expressions = self.options.get("expressions", {})
        for key, field in self.formula_fields.items():
            if expressions.get(key):
                continue
            value = float(self.options[key])
            if edited is not None and edited[0] == key:
                held = self.limit_edit(key, value, edited[1])
            else:
                held = self.limit_held(key, value)
            if held != value:
                self.options[key] = held
                value_limits.show_held(self.limit_shower, key, field, value, held)
                handle = self.handles.get(key)
                if handle is not None:
                    try:
                        handle.set_value(held)
                    except Exception:
                        pass

    def limit_key(self, what):
        options = {k: v for k, v in self.options.items() if k not in (what, "distance")}
        return value_limits.make_key("pipe", options, what)

    def limit_works(self, what):
        options = dict(self.options)

        def works(value):
            trial = dict(options)
            trial[what] = value
            pipe.check(pipe.with_defaults(trial))
            return True

        return works

    def limit_value(self, what):
        return float(self.options.get(what, 0.0))

    def limit_set(self, what, value):
        self.options[what] = value
        field = self.formula_fields.get(what)
        if field is not None:
            value_limits.show_held(self.limit_shower, what, field, field.value(), value)
        handle = self.handles.get(what)
        if handle is not None:
            try:
                handle.set_value(value)
            except Exception:
                pass

    # -- formulas (preview.FormulaInput calls these) -----------------------------------------------
    def formula_typed(self, key, text, value):
        self.formula_error = ""
        self._limit_next = (key, "formula")
        self.options.setdefault("expressions", {})[key] = text
        if key == "section_size":
            self.size_set = True
        if key == "thickness":
            self.thickness_set = True
        self._quiet = True
        try:
            self.formula_fields[key].set_value(value)
        finally:
            self._quiet = False
        self.show_formulas()
        self._changed(new_geometry=True)

    def formula_cleared(self, key):
        self.formula_error = ""
        if self.options.get("expressions", {}).pop(key, None) is not None:
            self.show_formulas()
            self._changed()

    def formula_failed(self, key, text):
        self.formula_error = text
        self.message.setText("⚠ " + text)

    def show_formulas(self):
        names = {"section_size": "Section Size", "thickness": "Section Thickness"}
        rows = [
            "%s = %s" % (names.get(k, k), v)
            for k, v in sorted(self.options.get("expressions", {}).items())
            if v
        ]
        self.formulas.setText("\n".join(rows))

    def activate(self, name):
        self.path_field.set_active(name == "path")

    def typing_field(self):
        """Where a number typed over the 3D view goes (Fusion's box next to the handle):
        the Distance after its ball was dragged, else the Section Size; none before the
        pipe has a path."""
        if self._closed or self.target is None or not self.path:
            return None
        if self._last_handle == "distance":
            return self.distance_box
        return self.size

    def clear_field(self, name):
        self.seeds = []
        self.path = []
        self._path_changed()
        self.activate("path")

    # -- sketches shown while editing --------------------------------------------------------------------
    def _show_sketches(self):
        for obj, _ in self.path:
            if obj.isDerivedFrom("Sketcher::SketchObject"):
                try:
                    if obj.ViewObject is not None and not obj.ViewObject.Visibility:
                        obj.ViewObject.Visibility = True
                        self._shown.append(obj)
                except Exception:
                    pass

    def _hide_shown(self):
        for obj in self._shown:
            try:
                obj.ViewObject.Visibility = False
            except Exception:
                pass
        self._shown = []

    # -- picking ------------------------------------------------------------------------------------------
    def _start(self):
        picks = [(o, s) for o, s in profile_pick.picks() if pipe.is_path_edge(o, s)]
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        self.activate("path")
        if picks:
            self.seeds = picks
            self._path_changed()
            self._timer.stop()
            self._recompute()
        else:
            self._refresh_path()

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        try:
            self.look = PathLook(Gui.ActiveDocument.ActiveView)
        except Exception as exc:
            warn("path display unavailable: %s" % exc)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None
        if self.look is not None:
            self.look.remove()
            self.look = None

    @safe
    def _selection_changed(self):
        if self._closed:
            return
        picks = [pk for pk in profile_pick.picks() if pk[0].Document.Name == self.doc.Name]
        if not picks:
            return
        Gui.Selection.clearSelection()
        if any(h.busy() for h in self.handles.values()):
            return  # the press grabbed a handle
        changed = False
        for obj, sub in picks:
            if not sub.startswith("Edge"):
                self.message.setText("⚠ Pick sketch curves or edges of the model for the path.")
                continue
            ref = self._base_edge(obj, sub)
            if ref is None:
                self.message.setText("⚠ That edge belongs to this pipe itself. Pick another.")
                continue
            self._toggle(ref)
            changed = True
        if changed:
            self._path_changed()

    def _is_ours(self, obj):
        if self.target is None:
            return False
        if obj is self.target or primitives.is_helper(obj):
            return True
        body = pipe.owner_body(self.target)
        if body is None or pipe.owner_body(obj) is not body:
            return False
        group = list(body.Group)
        try:
            return group.index(obj) > group.index(self.target)
        except ValueError:
            return False

    def _base_edge(self, obj, sub):
        """(feature, "EdgeN") as it was before this pipe, or None if only the pipe has it."""
        if not self._is_ours(obj):
            return (obj, sub)
        base = self.target.BaseFeature
        if base is None or base.Shape.isNull():
            return None
        try:
            edge = pipe._global_edge(obj, sub)
        except Exception:
            return None
        ends = [v.Point for v in edge.Vertexes]
        holding = None
        for i, candidate in enumerate(base.Shape.Edges, start=1):
            try:
                other = pipe._global_edge(base, "Edge%d" % i)
            except Exception:
                continue
            if other.Curve.TypeId != edge.Curve.TypeId:
                continue
            points = [v.Point for v in other.Vertexes]
            if len(points) == len(ends) and abs(other.Length - edge.Length) < 1e-6:
                if all(min((p - q).Length for q in points) < 1e-6 for p in ends):
                    return (base, "Edge%d" % i)
            if holding is None and _holds(other, edge):
                holding = (base, "Edge%d" % i)
        # The pipe itself shortened the edge (its groove took a corner off): the edge of
        # the part it lies on (before, the click said "that edge belongs to this pipe
        # itself": found by the primitives QA).
        return holding

    def _toggle(self, ref):
        key = (ref[0].Name, ref[1])
        in_path = any((o.Name, s) == key for o, s in self.path)
        if not in_path:
            self.seeds.append(ref)
            return
        # Drop the clicked edge's whole run (the seeds whose chain holds it).
        use_chain = self.chain.isChecked()
        keep = []
        for seed in self.seeds:
            group = pipe.chain(*seed) if use_chain else [seed]
            if any((o.Name, s) == key for o, s in group):
                continue
            keep.append(seed)
        self.seeds = keep

    @safe
    def _chain_toggled(self, *_):
        if self._quiet:
            return
        self._path_changed()

    def _path_changed(self):
        self.path = pipe.expand(self.seeds, self.chain.isChecked())
        self._refresh_path()
        if not self.path:
            if self.target is not None and not self.editing:
                pipe.remove(self.target)
                self.target = None
                self._remove_handles()
                self.schedule()
            self.error = "Pick at least one curve for the path." if self.editing else ""
            self.message.setText("⚠ " + self.error if self.error else "")
            return
        try:
            pipe.check_path(self.path)
        except PrimitiveError as exc:
            self.error = str(exc)
            self.message.setText("⚠ " + self.error)
            return
        if not self.size_set:
            # A first section that suits the path (a twentieth of its length), chosen once
            # from the first path: curves picked later keep it, and a wall typed before
            # stays (both changed with every pick before: a typed wall of 0.5 became 0.2
            # when a curve was dropped; found by the primitives QA).
            self.size_set = True
            try:
                length = pipe.path_length(self.path)
                size = primitives.nice(max(length / 20.0, 0.1))
                self.options["section_size"] = size
                self._quiet = True
                try:
                    self.size.set_value(size)
                    if not self.thickness_set:
                        self.options["thickness"] = primitives.nice(size / 10.0)
                        self.thickness.set_value(self.options["thickness"])
                finally:
                    self._quiet = False
            except Exception:
                pass
        self.message.setText("")
        self._changed(new_geometry=True)

    def _refresh_path(self):
        count = len(self.path)
        self.path_field.set_text("%d selected" % count if count else "")
        self.info.setText(
            "" if count else "Click sketch curves or edges of the model for the path."
        )
        if self.look is not None:
            self.look.show(self.path)

    # -- changes ------------------------------------------------------------------------------------------
    @safe
    def _typed(self, *_):
        if self._quiet:
            return
        self._update_visibility()
        self._changed(new_geometry=True)

    @safe
    def _thickness_typed(self, *_):
        if self._quiet:
            return
        self.thickness_set = True
        self._limit_next = ("thickness", "typed")
        self._typed()

    @safe
    def _size_typed(self, *_):
        if self._quiet:
            return
        self.size_set = True
        self._limit_next = ("section_size", "typed")
        self._changed(new_geometry=True)

    @safe
    def _operation_picked(self, _index):
        self.user_picked_operation = True
        self._changed()

    def _source_body(self):
        return pipe.source_body(self.path) or self.body

    def _base_shape(self):
        body = self._source_body()
        if body is None:
            return None
        if self.target is not None and pipe.owner_body(self.target) is body:
            return primitives.base_shape(body, before=self.target)
        return primitives.base_shape(body)

    def _auto_operation(self):
        if self.user_picked_operation or not self.path:
            return
        try:
            tool = pipe.tool_shape(self.path, self.options)
            wanted = primitives.auto_operation(self._base_shape(), tool)
        except Exception:
            return
        if wanted != self.options["operation"]:
            self.options["operation"] = wanted
            self._quiet = True
            set_combo(self.operation, wanted)
            self._quiet = False

    def _changed(self, new_geometry=False):
        self._collect()
        self._auto_operation()
        self.dirty = True
        if new_geometry:
            self._geometry_changed = True
        self.schedule()

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        try:
            if self.doc.Recomputing:
                self._timer.start()
                return
            if self.limit_waits():
                return  # the search of the largest value that fits previews when it ends
            if self.dirty:
                self.dirty = False
                self._apply()
            preview.recompute(self.doc)
            self.show_status()
            if self._geometry_changed or self._handles_wrong():
                self._geometry_changed = False
                self._make_handles()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _apply(self):
        """Build the pipe; a value just typed or dragged past what fits is held at the one
        that still works and built again (value_limits)."""
        self._apply_once()
        if not self.path:
            return
        held = self.limit_refuse(self.error) if self.error else None
        if held == "again":
            self._apply_once()
        elif held == "later":
            # looked for one trial per event-loop turn; its end builds the held value
            self.dirty = True
            self.error = ""
            return
        elif not self.error:
            self.limit_good()
        if self.error:
            self.error = self.limit_hint(self.error)

    def _apply_once(self):
        if not self.path:
            return
        try:
            before = self.target
            self.target = pipe.build(self.path, self.options, feature=self.target, body=self.body)
            self.error = ""
            if before is None or self.target is not before:
                self._geometry_changed = True
        except PrimitiveError as exc:
            self.error = str(exc)
        except Exception as exc:
            self.error = "This pipe cannot be built: %s" % exc
        if self.error and self.target is not None:
            try:
                actual = pipe.read(self.target)[1]["operation"]
            except Exception:
                actual = self.options["operation"]
            if actual != self.options["operation"]:
                self.options["operation"] = actual
                self._quiet = True
                set_combo(self.operation, actual)
                self._quiet = False

    def feature(self):
        return self.target

    def show_status(self):
        value_limits.show_note(getattr(self, "limit_label", None), "")
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return
        if self.error:
            self.message.setText("⚠ " + self.error)
            return
        text = _plain(preview.failure(self.target))
        self.message.setText("⚠ " + text if text else "")
        value_limits.show_note(self.limit_label, "" if text else self.limits.note)

    # -- handles --------------------------------------------------------------------------------------------
    def _remove_handles(self):
        for handle in self.handles.values():
            try:
                handle.remove()
            except Exception:
                pass
        self.handles = {}

    def _handles_wrong(self):
        if any(h.dragging() for h in self.handles.values()):
            return False
        wanted = {"distance", "section_size"} if self.target is not None and self.path else set()
        return set(self.handles) != wanted

    def _make_handles(self):
        if self._closed:
            return
        if any(h.dragging() for h in self.handles.values()):
            return
        self._remove_handles()
        if self.target is None or not self.path or self.error:
            return
        try:
            points, _end, start, tangent = pipe.path_points(self.path, count=120)
            size = max(1.5, min(float(self.options["section_size"]) * 1.2, 20.0))
            self.handles["distance"] = PathHandle(
                points,
                float(self.options["distance"]),
                size,
                on_drag=self._distance_dragged,
                on_release=self._distance_released,
            )
            self.value_boxes.attach(
                self.handles["distance"],
                "distance",
                lambda: self.distance.text(),
                self._box_distance,
            )
            normal = pipe.sketch_normal([o for o, _ in self.path])
            up = pipe.up_vector(tangent, normal, _wire(self.path))
            side = up.cross(tangent)
            if side.Length < 1e-9:
                side = up
            side.normalize()
            self.handles["section_size"] = LinearHandle(
                start,
                side,
                float(self.options["section_size"]),
                size,
                on_drag=self._size_dragged,
                on_release=self._size_released,
                scale=0.5,
                name="section_size",
            )
            self.value_boxes.attach(
                self.handles["section_size"],
                "section_size",
                lambda: self.size.widget.text(),
                self._box_size,
            )
        except Exception as exc:
            warn("pipe handles unavailable: %s" % exc)

    def _box_distance(self, text):
        """A distance (0..1 along the path) typed in the box next to the ball."""
        if self._closed:
            return
        try:
            value = float(text.strip().replace(",", "."))
        except ValueError:
            self.message.setText("⚠ Type a number between 0 and 1 (how far along the path).")
            return
        self._last_handle = "distance"
        self.distance.setValue(max(0.01, min(1.0, value)))

    def _box_size(self, text):
        if self._closed:
            return
        self._last_handle = "section_size"
        for formula in self.formula_inputs:
            if formula.key == "section_size":
                formula.take(text)
                return

    @safe
    def _distance_dragged(self, value):
        self._last_handle = "distance"
        value = max(0.01, min(1.0, round(value, 2)))
        self._quiet = True
        try:
            self.distance.setValue(value)
        finally:
            self._quiet = False
        self._changed()

    @safe
    def _distance_released(self, value):
        self._distance_dragged(value)
        self._changed(new_geometry=True)

    @safe
    def _size_dragged(self, value):
        self._last_handle = "section_size"
        value = max(0.02, round(abs(value), 2))
        if self.options.get("expressions", {}).pop("section_size", None) is not None:
            self.show_formulas()
        self.size_set = True
        self._quiet = True
        try:
            self.size.set_value(value)
        finally:
            self._quiet = False
        self._limit_next = ("section_size", "dragged")
        self._changed()

    @safe
    def _size_released(self, value):
        self._size_dragged(value)
        self._changed(new_geometry=True)

    # -- OK / Cancel ------------------------------------------------------------------------------------------
    def accept(self):
        try:
            return self._accept()
        except Exception as exc:
            warn("Pipe OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def _accept(self):
        self.limit_accept()  # a limit search still running ends now
        try:
            return self._accept_now()
        finally:
            self.limit_accepted()

    def _accept_now(self):
        if self.target is None:
            text = self.error or "Pick the path first: click sketch curves or model edges."
            self.message.setText("⚠ " + text)
            return False
        if self.formula_error:
            self.message.setText("⚠ " + self.formula_error)
            return False
        self._timer.stop()
        if self.dirty:
            self.dirty = False
            self._apply()
        if self.error:
            self.message.setText("⚠ " + self.error)
            return False
        preview.recompute(self.doc)
        text = _plain(preview.failure(self.target))
        if text:
            self.message.setText("⚠ " + text)
            return False
        feature = self.target
        path = list(self.path)
        self._shown = []  # the sketches stay hidden: the pipe uses them now
        pipe.hide_sketches(path)
        self.cleanup()
        preview.end_transaction(self.doc)
        self._close()
        body = pipe.owner_body(feature)
        if body is not None and body is not commands.active_body():
            try:
                from . import components

                components.activate_body(body)  # and its (new) component
            except Exception as exc:
                warn("could not activate %s: %s" % (body.Label, exc))
        log("Pipe done")
        return True

    def reject(self):
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
        except Exception as exc:
            warn("Pipe Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Pipe Cancel: %s" % exc)
        return True

    def cleanup(self):
        self.limit_cancel()
        value_limits.busy(self, False)
        self._unwatch()
        self.escape.remove()
        self.undo_guard.remove()
        self.enter.remove()
        self._remove_typing()
        self._remove_handles()
        self.value_boxes.discard()
        self._hide_shown()
        super().cleanup()


def _holds(longer, edge):
    """True if `edge` lies on `longer` (its ends and middle on it): a piece of it."""
    import Part

    try:
        if longer.Length < edge.Length - 1e-6:
            return False
        middle = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        points = [v.Point for v in edge.Vertexes] + [middle]
        return all(longer.distToShape(Part.Vertex(p))[0] < 1e-6 for p in points)
    except Exception:
        return False


class _Field:
    """A plain Qt number box seen as a dialog field (`.widget`), for TypeOverView."""

    def __init__(self, widget):
        self.widget = widget


def _wire(path):
    import Part

    edges = [pipe._global_edge(obj, sub) for obj, sub in path]
    try:
        return Part.Wire(Part.__sortEdges__(edges))
    except Exception:
        return Part.Wire(edges[:1])


class ViewProviderPipe:
    """View provider of the Intersect pipe (a SciForge feature)."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        return ui_icon_path("pipe")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        edit(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


class PipeCommand:
    def GetResources(self):
        return {
            "MenuText": "Pipe",
            "ToolTip": "Pipe: pick sketch curves or model edges as the path; round, square or "
            "triangular section, hollow, distance along the path",
            "Pixmap": ui_icon_path("pipe"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            if commands.find_body() is None:
                commands.tell("Pipe follows a path: draw one with Create Sketch first.")
                return
            Gui.Control.showDialog(PipePanel(App.ActiveDocument))
            log("pipe started")
        except Exception as exc:
            warn("Pipe failed to start: %s" % exc)


def edit(feature):
    """Open the Pipe dialog on an existing pipe (timeline double-click)."""
    try:
        if Gui.Control.activeDialog() and not commands.finish_open_dialog():
            return
        if not pipe.is_ours(feature):
            Gui.ActiveDocument.setEdit(feature.Name)
            return
        Gui.Control.showDialog(PipePanel(feature.Document, feature=feature))
    except Exception as exc:
        warn("could not edit %s: %s" % (feature.Label, exc))


COMMANDS = {"SciForge_Pipe": PipeCommand}
EDITORS = {"SciForge::" + pipe.KIND: edit}
