# SPDX-License-Identifier: LGPL-2.1-or-later
"""The MESH tab's dialogs and commands: Repair (and Make Closed Mesh), Remesh, Reduce, Smooth,
Shell, Reverse Normal, Separate, Combine, Generate Face Groups and Tessellate. Plane Cut and
Create Mesh Section Sketch are in mesh_cut_ui.py, Erase and Fill and Delete in
mesh_pick_ui.py. The document work is in mesh.py; spec and sources: docs/sciforge/parity/
mesh.md.

Every dialog works like Fusion's: the body box waits blue for a click on a mesh body (one
picked before the command is taken), the options are Fusion's with its defaults, the
dialogs Fusion gives a Preview box have one (off at first, as in Fusion: mesh work can be
slow), the others preview as you go; OK adds one step to the timeline (one undo step),
Cancel or Esc leaves the body as it was, and a step that cannot be done says why in the
dialog and keeps it open."""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, hole_common, insert_ui, log, mesh, warn
from . import mesh_core as core
from .compat import QtCore, QtWidgets

INFO_STYLE = "color: #9fb3c8;"


def _later(fn, ms=30):
    QtCore.QTimer.singleShot(ms, fn)


def body_end(obj):
    """A mesh body a click can pick: a mesh object no later step uses up."""
    if not mesh.is_mesh(obj):
        return False
    try:
        return obj.Name not in bodies.consumed(obj.Document)
    except Exception:
        return True


def selected_mesh_bodies(doc):
    found = []
    for sel in Gui.Selection.getSelectionEx():
        try:
            if sel.Document.Name != doc.Name:
                continue
        except Exception:
            continue
        if body_end(sel.Object) and sel.Object not in found:
            found.append(sel.Object)
    return found


def _refresh_browser():
    try:
        from . import browser_ui

        widget = browser_ui.widget()
        if widget is not None:
            widget.refresh(force=True)
    except Exception:
        pass


class _Observer:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, doc, obj, sub, pnt):
        panel = self.panel
        try:
            # the keys held at the click itself (Ctrl+click takes faces off)
            panel.pick_modifiers = QtWidgets.QApplication.keyboardModifiers()
        except Exception:
            pass
        QtCore.QTimer.singleShot(30, lambda p=pnt: panel.selection_changed(p))


# ============================================================================ the base
class MeshPanel(insert_ui._InsertPanel):
    """A MESH dialog: the Body box, the options (build()), Fusion's Preview box when it has
    one, and the step it adds (mesh.new_step)."""

    title = "Mesh"
    icon = "insert_mesh"
    step_kind = None
    preview_box = True  # Fusion's Preview check box (off at first)
    body_label = "Body"
    wait_text = "Click the mesh body."
    solid_source = False  # Tessellate: the body is a solid body

    def __init__(self, doc, body=None, feature=None, **options):
        super().__init__(doc, ("Edit " if feature is not None else "") + self.title)
        self.editing = feature is not None
        self.step = feature
        self.body = None
        self.options = options
        self._shown_before = {}  # name -> visibility before the dialog hid / showed it
        self._before_text = ""
        self.fields = {}
        self.active = None
        self.preview = None
        self.observer = None
        try:
            self._start(body, feature)
        except Exception:
            # half open: nothing may stay behind (the selection observer, the keys)
            try:
                self.cleanup()
            except Exception as exc:
                log("%s: %s" % (self.title, exc))
            raise

    def _start(self, body, feature):
        self.add_field(
            "body", self.body_label, "Select a body" if self.solid_source else "Select a mesh body"
        )
        self.build()
        if self.preview_box:
            self.preview = self.check("Preview", False, self._preview_toggled)
        self.finish_layout()
        self.observer = _Observer(self)
        Gui.Selection.addObserver(self.observer)
        if feature is not None:
            self.body = getattr(feature, "Source", None)
            self.load(feature)
            if self.body is not None:
                self.fields["body"].set_text(self.body.Label)
                self._before_text = self.describe_source()
            self._hold_by_preview()
            self.after_body()
            self.set_active(self.first_waiting())
            self.schedule()
        elif body is not None:
            self.set_body(body)
        else:
            self.set_active("body")
            self.say(self.wait_text)
        Gui.Selection.clearSelection()

    # -- rows ---------------------------------------------------------------------------
    def build(self):
        """Add the dialog's rows (override)."""

    def load(self, feature):
        """Put an existing step's values into the rows (override)."""

    def write(self, step):
        """Put the rows' values on the step (override)."""

    def after_body(self):
        """A body was picked, or the step is edited (override: more fields)."""

    def add_field(self, name, label, empty):
        field = hole_common.SelectionField(self, name, empty)
        self.fields[name] = field
        self.layout.addRow(QtWidgets.QLabel(label), field.widget)
        return field

    def first_waiting(self):
        return None

    def set_active(self, name):
        self.active = name
        for key, field in self.fields.items():
            field.set_active(key == name)

    def activate(self, name):
        self.set_active(name)

    def clear_field(self, name):
        if name == "body" and not self.editing:
            self._drop_step()
            self.body = None
            self.fields["body"].set_text("")
            self.set_active("body")
            self.say(self.wait_text)
        else:
            self.cleared(name)

    def cleared(self, name):
        """A field's x was clicked (override for other fields)."""

    # -- picking ------------------------------------------------------------------------
    def selection_changed(self, point=None):
        if getattr(self, "_closed", False):
            return
        try:
            picks = list(Gui.Selection.getSelectionEx())
            if not picks:
                return
            Gui.Selection.clearSelection()
            for sel in picks:
                if sel.Document.Name != self.doc.Name:
                    continue
                obj = sel.Object
                subs = list(sel.SubElementNames) or [""]
                self.picked(obj, subs[0], point)
                return
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def own_objects(self):
        found = [self.step] if self.step is not None else []
        if self.step is not None:
            found += mesh.pieces_of(self.step)
        return [o for o in found if o is not None]

    def picked(self, obj, sub, point):
        """A click on `obj` in the 3D view or the browser (override for other fields)."""
        if self.active in (None, "body") or self.active == "body":
            self.pick_body(obj)
        else:
            self.pick_other(self.active, obj, sub, point)

    def pick_other(self, name, obj, sub, point):
        """A click while another field waits (override)."""

    def pick_body(self, obj):
        if obj in self.own_objects():
            return  # the preview of this step: the body is picked already
        if self.solid_source:
            body = bodies.body_of(obj)
            if body is None or not bodies.has_solid(body):
                commands.tell("Click a solid body (Tessellate makes a mesh body of it).")
                return
            obj = body
        elif not body_end(obj):
            commands.tell("That is not a mesh body: click a mesh body (INSERT > Insert Mesh).")
            return
        if obj is self.body:
            self.set_active(self.first_waiting())
            return
        self.set_body(obj)

    def set_body(self, obj):
        self.body = obj
        self.fields["body"].set_text(obj.Label)
        self._before_text = self.describe_source()
        if self.step is None:
            self.step = mesh.new_step(self.doc, self.step_kind, obj)
            self.target = self.step
        else:
            self._show(self.step.Source, self._shown_before.get(self.step.Source.Name, True))
            self.step.Source = obj
        self.write(self.step)
        self._hold_by_preview()
        self.after_body()
        self._show_preview_objects()
        self.set_active(self.first_waiting())
        self.schedule()

    def describe_source(self):
        try:
            if self.solid_source:
                return ""
            return mesh.describe(mesh.global_mesh(self.body))
        except Exception as exc:
            log("%s: %s" % (self.title, exc))
            return ""

    # -- the preview --------------------------------------------------------------------
    def _remember(self, obj):
        if obj is not None and obj.Name not in self._shown_before:
            self._shown_before[obj.Name] = bodies.is_shown(obj)

    def _show(self, obj, on):
        if obj is None or not bodies.alive(obj):
            return
        self._remember(obj)
        bodies.set_shown(obj, on)

    def _show_preview_objects(self):
        """The body is replaced by the step (or by the step's pieces) while the dialog is
        open, as the step will replace it."""
        if self.step is None:
            return
        source = getattr(self.step, "Source", None)
        if source is not None and source not in self.kept_sources():
            self._show(source, False)
        pieces = mesh.pieces_of(self.step)
        self._show(self.step, not pieces)
        for piece in pieces:
            self._show(piece, True)
        for tool in self.hidden_tools():
            self._show(tool, False)

    def kept_sources(self):
        """Bodies the step keeps on show (Separate's Keep Body)."""
        return []

    def hidden_tools(self):
        return []

    def _preview_on(self):
        return self.preview is None or self.preview.isChecked()

    def _hold_by_preview(self):
        if self.step is not None:
            mesh.hold(self.step, not self._preview_on())

    def _preview_toggled(self):
        self._hold_by_preview()
        if self.step is not None:
            self.step.touch()
        self.schedule()

    def changed(self):
        """A row changed: the step takes the values and the preview follows."""
        if self.step is None:
            return
        self.write(self.step)
        self.step.touch()
        self.schedule()

    def feature(self):
        return self.step if self.step is not None and bodies.alive(self.step) else None

    def _recompute(self):
        if getattr(self, "_closed", False):
            return
        super()._recompute()
        try:
            if self.step is not None and bodies.alive(self.step):
                if self.sync_pieces():
                    super()._recompute()
                self._show_preview_objects()
                for obj in [self.step] + mesh.pieces_of(self.step):
                    mesh.apply_colours(obj)
            self.report()
        except Exception as exc:
            warn("%s preview: %s" % (self.title, exc))

    def sync_pieces(self):
        """Make the step's pieces (override: Separate, Split Body). True if they changed."""
        return False

    def report(self):
        """The info line under the options and the message when the step cannot be done."""
        if self.step is None:
            return
        failed = mesh.problem(self.step)
        if failed:
            self.message.setText("⚠ " + failed)
        else:
            self.message.setText("")
        lines = []
        if self._before_text:
            lines.append("Before: " + self._before_text)
        if not self._preview_on():
            lines.append("Tick Preview to see the result here, or press OK.")
        elif not failed and self.step.StepInfo:
            lines.append("After: " + self.step.StepInfo + self.result_health())
        self.say("\n".join(lines))

    def result_health(self):
        """', closed' or what is wrong with the result (Repair says it itself; pieces are
        bodies of their own)."""
        if self.step_kind == "MeshRepair" or self.step is None or mesh.pieces_of(self.step):
            return ""
        try:
            info = mesh.analyze(self.step.Mesh)
        except Exception:
            return ""
        problems = core.analysis_lines(info)
        if problems:
            return "; " + ", ".join(problems)
        return ", closed" if info.get("closed") else "; not closed"

    def show_status(self):
        self.report()

    # -- finishing ----------------------------------------------------------------------
    def accept(self):
        try:
            return self._accept()
        except Exception as exc:  # OK must never throw: say it, keep the dialog
            warn("%s: %s" % (self.title, exc))
            self.message.setText(
                "⚠ This could not be finished (%s). Cancel leaves the body as it was." % exc
            )
            return False

    def _accept(self):
        if self.step is None or not bodies.alive(self.step):
            self.message.setText("⚠ " + self.wait_text)
            return False
        mesh.hold(self.step, False)
        self.step.touch()
        self.doc.recompute()
        if self.sync_pieces():
            self.doc.recompute()
        failed = mesh.problem(self.step)
        if failed:
            self._hold_by_preview()
            self.message.setText("⚠ " + failed)
            self.report()
            return False
        step = self.step
        if not super().accept():
            return False
        for obj in [step] + mesh.pieces_of(step):
            mesh.apply_colours(obj)
        try:
            bodies.sync_consumed(self.doc)
        except Exception:
            pass
        _refresh_browser()
        return True

    def reject(self):
        try:
            if self.step is not None and bodies.alive(self.step):
                mesh.hold(self.step, False)
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))
        result = super().reject()
        for name, was in self._shown_before.items():
            obj = self.doc.getObject(name)
            if obj is not None:
                bodies.set_shown(obj, was)
        try:
            bodies.sync_consumed(self.doc)
        except Exception:
            pass
        _refresh_browser()
        return result

    def _drop_step(self):
        if self.step is None or self.editing:
            return
        step, self.step = self.step, None
        self.target = None
        try:
            mesh.hold(step, False)
            for piece in mesh.pieces_of(step):
                self.doc.removeObject(piece.Name)
            source = step.Source
            self.doc.removeObject(step.Name)
            if source is not None:
                self._show(source, self._shown_before.get(source.Name, True))
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    def cleanup(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        if self.step is not None:
            try:
                mesh.hold(self.step, False)
            except Exception:
                pass
        super().cleanup()


# ============================================================================ Repair
class RepairPanel(MeshPanel):
    """Fusion's Repair: Repair Type Close Holes / Stitch and Remove / Wrap / Rebuild (with a
    Rebuild Type, Density and, for Accurate, an Offset). The body's problems are listed
    before, and after the repair either 'closed' or what to try next."""

    title = "Repair"
    icon = "mesh_repair"
    step_kind = "MeshRepair"
    wait_text = "Click the mesh body to repair."

    def build(self):
        start = self.options.get("repair_type", core.DEFAULT_REPAIR)
        self.repair_type = self.combo("Repair Type", core.REPAIR_TYPES, start, self.changed)
        self.rebuild_type = self.combo(
            "Rebuild Type",
            core.REBUILD_TYPES,
            self.options.get("rebuild_type", core.DEFAULT_REBUILD),
            self.changed,
        )
        lo, hi, default = core.REBUILD_DENSITY
        self.density = self.spin("Density", default, lo, hi, self.changed, decimals=0, step=8)
        self.offset = self.number("Offset", 0.0, "mm", lambda: self.changed())
        self._rows_for_type()

    def _rows_for_type(self):
        rebuild = self.repair_type.currentText() == "Rebuild"
        self.rebuild_type.setEnabled(rebuild)
        self.density.setEnabled(rebuild)
        self.offset.widget.setEnabled(rebuild and self.rebuild_type.currentText() == "Accurate")

    def changed(self):
        self._rows_for_type()
        super().changed()

    def load(self, feature):
        self._quiet = True
        try:
            self.repair_type.setCurrentText(feature.RepairType)
            self.rebuild_type.setCurrentText(feature.RebuildType)
            self.density.setValue(int(feature.Density))
            self.offset.set_value(float(feature.Offset))
        finally:
            self._quiet = False
        self._rows_for_type()

    def write(self, step):
        step.RepairType = self.repair_type.currentText()
        step.RebuildType = self.rebuild_type.currentText()
        step.Density = int(self.density.value())
        step.Offset = float(self.offset.value())


# ============================================================================ Remesh
class RemeshPanel(MeshPanel):
    """Fusion's Remesh: Remesh Type Adaptive / Uniform, Density, Shape Preservation (Adaptive),
    Preserve Sharp Edges, Preserve Boundaries."""

    title = "Remesh"
    icon = "mesh_remesh"
    step_kind = "MeshRemesh"
    wait_text = "Click the mesh body to remesh."

    def build(self):
        self.remesh_type = self.combo("Remesh Type", core.REMESH_TYPES, "Adaptive", self.changed)
        self.density = self.spin("Density", core.REMESH_DENSITY, 0.0, 1.0, self.changed, 2, 0.05)
        self.shape = self.spin(
            "Shape Preservation", core.SHAPE_PRESERVATION, 0.0, 1.0, self.changed, 2, 0.05
        )
        self.sharp = self.check("Preserve Sharp Edges", False, self.changed)
        self.boundaries = self.check("Preserve Boundaries", False, self.changed)

    def changed(self):
        self.shape.setEnabled(self.remesh_type.currentText() == "Adaptive")
        super().changed()

    def load(self, feature):
        self._quiet = True
        try:
            self.remesh_type.setCurrentText(feature.RemeshType)
            self.density.setValue(float(feature.Density))
            self.shape.setValue(float(feature.ShapePreservation))
            self.sharp.setChecked(bool(feature.PreserveSharpEdges))
            self.boundaries.setChecked(bool(feature.PreserveBoundaries))
        finally:
            self._quiet = False
        self.shape.setEnabled(self.remesh_type.currentText() == "Adaptive")

    def write(self, step):
        step.RemeshType = self.remesh_type.currentText()
        step.Density = float(self.density.value())
        step.ShapePreservation = float(self.shape.value())
        step.PreserveSharpEdges = self.sharp.isChecked()
        step.PreserveBoundaries = self.boundaries.isChecked()


# ============================================================================ Reduce
class ReducePanel(MeshPanel):
    """Fusion's Reduce: Reduce Target Tolerance / Proportion / Face Count, its value, and Reduce
    Type Adaptive / Uniform (Proportion and Face Count; Tolerance is always adaptive)."""

    title = "Reduce"
    icon = "mesh_reduce"
    step_kind = "MeshReduce"
    wait_text = "Click the mesh body to reduce."

    def build(self):
        self.reduce_target = self.combo(
            "Reduce Target", core.REDUCE_TARGETS, "Tolerance", self.changed
        )
        self.tolerance = self.number(
            "Tolerance", core.DEFAULT_TOLERANCE, "mm", lambda: self.changed()
        )
        self.proportion = self.spin(
            "Proportion", core.DEFAULT_PROPORTION, 0.0, 100.0, self.changed, 1, 5.0
        )
        self.proportion.setSuffix(" %")
        self.face_count = self.spin("Face Count", 0, 4, 100000000, self.changed, 0, 100)
        self.reduce_type = self.combo("Reduce Type", core.REDUCE_TYPES, "Adaptive", self.changed)
        self._rows_for_target()

    def _rows_for_target(self):
        target = self.reduce_target.currentText()
        self.tolerance.widget.setEnabled(target == "Tolerance")
        self.proportion.setEnabled(target == "Proportion")
        self.face_count.setEnabled(target == "Face Count")
        self.reduce_type.setEnabled(target != "Tolerance")

    def after_body(self):
        try:
            count = self.body.Mesh.CountFacets if self.body is not None else 0
            if count and int(self.face_count.value()) <= 4 and not self.editing:
                self._quiet = True
                try:
                    self.face_count.setValue(max(4, count // 2))
                finally:
                    self._quiet = False
                if self.step is not None:
                    self.write(self.step)
        except Exception:
            pass

    def changed(self):
        self._rows_for_target()
        super().changed()

    def load(self, feature):
        self._quiet = True
        try:
            self.reduce_target.setCurrentText(feature.Target)
            self.tolerance.set_value(float(feature.Tolerance))
            self.proportion.setValue(float(feature.Proportion))
            self.face_count.setValue(int(feature.FaceCount))
            self.reduce_type.setCurrentText(feature.ReduceType)
        finally:
            self._quiet = False
        self._rows_for_target()

    def write(self, step):
        step.Target = self.reduce_target.currentText()
        step.Tolerance = max(1e-6, float(self.tolerance.value()))
        step.Proportion = float(self.proportion.value())
        step.FaceCount = int(self.face_count.value())
        step.ReduceType = self.reduce_type.currentText()


# ============================================================================ Smooth
class SmoothPanel(MeshPanel):
    """Fusion's Smooth: Smoothness 0 (barely) .. 1 (strongly)."""

    title = "Smooth"
    icon = "mesh_smooth"
    step_kind = "MeshSmooth"
    wait_text = "Click the mesh body to smooth."

    def build(self):
        self.smoothness = self.spin(
            "Smoothness", core.DEFAULT_SMOOTHNESS, 0.0, 1.0, self.changed, 2, 0.05
        )

    def load(self, feature):
        self._quiet = True
        try:
            self.smoothness.setValue(float(feature.Smoothness))
        finally:
            self._quiet = False

    def write(self, step):
        step.Smoothness = float(self.smoothness.value())


# ============================================================================ Shell
class ShellPanel(MeshPanel):
    """Fusion's mesh Shell: the body hollowed, the walls Thickness thick (3D prints use less
    material and time)."""

    title = "Shell"
    icon = "mesh_shell"
    step_kind = "MeshShell"
    wait_text = "Click the closed mesh body to hollow."

    def build(self):
        self.thickness = self.number("Thickness", core.DEFAULT_SHELL, "mm", lambda: self.changed())

    def load(self, feature):
        self._quiet = True
        try:
            self.thickness.set_value(float(feature.Thickness))
        finally:
            self._quiet = False

    def write(self, step):
        step.Thickness = max(1e-6, float(self.thickness.value()))


# ============================================================================ Reverse Normal
class ReverseNormalPanel(MeshPanel):
    """Fusion's Reverse Normal: every face of the body turned over, or only the face groups
    clicked (when the body has face groups)."""

    title = "Reverse Normal"
    icon = "mesh_reverse_normal"
    step_kind = "MeshReverseNormal"
    preview_box = False
    wait_text = "Click the mesh body whose faces point the wrong way."

    def build(self):
        self.groups = []
        self.groups_field = self.add_field("groups", "Face Groups", "All faces")

    def after_body(self):
        has_groups = bool(self._source_groups())
        self.groups_field.widget.setEnabled(has_groups)

    def _source_groups(self):
        src = self.body
        return list(getattr(src, "FaceGroups", []) or []) if src is not None else []

    def first_waiting(self):
        return "groups" if self._source_groups() else None

    def pick_other(self, name, obj, sub, point):
        if name != "groups":
            return
        if obj not in self.own_objects() and obj is not self.body:
            self.pick_body(obj)
            return
        group = facet_group_at(self.body, point)
        if group is None:
            return
        if group in self.groups:
            self.groups.remove(group)
        else:
            self.groups.append(group)
        self._show_groups()
        self.changed()

    def cleared(self, name):
        if name == "groups":
            self.groups = []
            self._show_groups()
            self.changed()

    def _show_groups(self):
        text = (
            "All faces"
            if not self.groups
            else "%d face group%s" % (len(self.groups), "" if len(self.groups) == 1 else "s")
        )
        self.groups_field.set_text(text)

    def load(self, feature):
        self.groups = list(feature.Groups)
        self._show_groups()

    def write(self, step):
        step.Groups = list(self.groups)


def facet_group_at(body, point):
    """The face group of `body`'s face under a picked point (None without face groups)."""
    if body is None or point is None:
        return None
    groups = list(getattr(body, "FaceGroups", []) or [])
    if not groups:
        return None
    index = facet_at(body, point)
    if index is None or index >= len(groups):
        return None
    return groups[index]


def facet_at(body, point):
    """Index of the face of `body` under a point picked in the 3D view (global)."""
    try:
        view = Gui.ActiveDocument.ActiveView
        direction = view.getViewDirection()
        local = mesh.global_mesh(body)
        start = App.Vector(point) - direction * (local.BoundBox.DiagonalLength + 1.0)
        hit = local.nearestFacetOnRay(tuple(start), tuple(direction))
        if hit:
            return int(list(hit.keys())[0])
    except Exception as exc:
        log("face pick: %s" % exc)
    return None


# ============================================================================ Separate
class SeparatePanel(MeshPanel):
    """Fusion's Separate: Separate Type Mesh Shells / All Face Groups / Select Face Groups,
    Keep Body. Each piece becomes a mesh body; the Separate step is one timeline step."""

    title = "Separate"
    icon = "mesh_separate"
    step_kind = "MeshSeparate"
    preview_box = False
    wait_text = "Click the mesh body to separate."

    def build(self):
        self.separate_type = self.combo(
            "Separate Type", core.SEPARATE_TYPES, "Mesh Shells", self.changed
        )
        self.groups = []
        self.groups_field = self.add_field("groups", "Face Groups", "Select face groups")
        self.keep = self.check("Keep Body", False, self.changed)
        self._rows_for_type()

    def _rows_for_type(self):
        self.groups_field.widget.setEnabled(
            self.separate_type.currentText() == "Select Face Groups"
        )

    def changed(self):
        self._rows_for_type()
        if not self._quiet and self.active != self.first_waiting():
            self.set_active(self.first_waiting())  # Select Face Groups: the box waits for clicks
        super().changed()

    def first_waiting(self):
        return "groups" if self.separate_type.currentText() == "Select Face Groups" else None

    def pick_other(self, name, obj, sub, point):
        if name != "groups":
            return
        group = (
            facet_group_at(self.body, point)
            if obj is self.body or obj in self.own_objects()
            else None
        )
        if group is None:
            commands.tell("Click a face group of the body (Generate Face Groups first).")
            return
        if group in self.groups:
            self.groups.remove(group)
        else:
            self.groups.append(group)
        self.groups_field.set_text(
            "%d face group%s" % (len(self.groups), "" if len(self.groups) == 1 else "s")
        )
        self.changed()

    def cleared(self, name):
        if name == "groups":
            self.groups = []
            self.groups_field.set_text("")
            self.changed()

    def kept_sources(self):
        return [self.body] if self.keep.isChecked() and self.body is not None else []

    def _show_preview_objects(self):
        super()._show_preview_objects()
        if self.body is not None and self.keep.isChecked():
            self._show(self.body, True)

    def sync_pieces(self):
        pieces = mesh._cache(self.step).get("pieces") or []
        wanted = len(pieces) if not mesh.problem(self.step) else 0
        before = len(mesh.pieces_of(self.step))
        if wanted == before:
            return False
        mesh.set_piece_count(self.step, wanted, self.body.Label if self.body else self.step.Label)
        return True

    def load(self, feature):
        self._quiet = True
        try:
            self.separate_type.setCurrentText(feature.SeparateType)
            self.keep.setChecked(bool(feature.KeepBody))
            self.groups = list(feature.Groups)
        finally:
            self._quiet = False
        self._rows_for_type()

    def write(self, step):
        step.SeparateType = self.separate_type.currentText()
        step.KeepBody = self.keep.isChecked()
        step.Groups = list(self.groups)


# ============================================================================ Combine
class CombinePanel(MeshPanel):
    """Fusion's mesh Combine: Target Body, Tool Bodies, Operation Join / Cut / Intersect /
    Merge, Keep Tools."""

    title = "Combine"
    icon = "mesh_combine"
    step_kind = "MeshCombine"
    preview_box = False
    body_label = "Target Body"
    wait_text = "Click the target mesh body, then the tool bodies."

    def build(self):
        self.tools = []
        self.tools_field = self.add_field("tools", "Tool Bodies", "Select tool bodies")
        self.operation = self.combo("Operation", core.COMBINE_OPERATIONS, "Join", self.changed)
        self.keep = self.check("Keep Tools", False, self.changed)

    def first_waiting(self):
        return "tools"

    def pick_other(self, name, obj, sub, point):
        if name != "tools":
            return
        if obj in self.own_objects() or obj is self.body:
            return
        if not body_end(obj):
            commands.tell("Click a mesh body to combine with.")
            return
        if obj in self.tools:
            self.tools.remove(obj)
            self._show(obj, self._shown_before.get(obj.Name, True))
        else:
            self.tools.append(obj)
        self._show_tools()
        self.changed()

    def cleared(self, name):
        if name == "tools":
            for tool in self.tools:
                self._show(tool, self._shown_before.get(tool.Name, True))
            self.tools = []
            self._show_tools()
            self.changed()

    def _show_tools(self):
        self.tools_field.set_text(", ".join(t.Label for t in self.tools))

    def hidden_tools(self):
        return [] if self.keep.isChecked() else list(self.tools)

    def _show_preview_objects(self):
        super()._show_preview_objects()
        if self.keep.isChecked():
            for tool in self.tools:
                self._show(tool, True)

    def load(self, feature):
        self.tools = [t for t in feature.Tools if t is not None]
        self._show_tools()
        self._quiet = True
        try:
            self.operation.setCurrentText(feature.Operation)
            self.keep.setChecked(bool(feature.KeepTools))
        finally:
            self._quiet = False

    def write(self, step):
        step.Tools = list(self.tools)
        step.Operation = self.operation.currentText()
        step.KeepTools = self.keep.isChecked()

    def report(self):
        super().report()
        if self.step is not None and not self.tools and not mesh.problem(self.step):
            self.message.setText("")
            self.say(
                "Click the tool bodies to combine with %s."
                % (self.body.Label if self.body else "it")
            )

    def _accept(self):
        if self.step is not None and not self.tools:
            self.message.setText("⚠ Pick at least one tool body to combine with.")
            return False
        return super()._accept()


# ============================================================================ Generate Face Groups
class FaceGroupsPanel(MeshPanel):
    """Fusion's Generate Face Groups: Method Fast (Angle Threshold, Minimum Face Group Size)
    or Accurate (Boundary Tolerance). Each group is shown in its own colour."""

    title = "Generate Face Groups"
    icon = "mesh_face_groups"
    step_kind = "MeshFaceGroups"
    wait_text = "Click the mesh body to find face groups on."

    def build(self):
        self.method = self.combo("Method", core.FACE_GROUP_METHODS, "Fast", self.changed)
        self.angle = self.spin(
            "Angle Threshold", core.ANGLE_THRESHOLD, 0.0, 90.0, self.changed, 1, 1
        )
        self.angle.setSuffix(" deg")
        self.min_size = self.spin(
            "Minimum Face Group Size", core.MIN_GROUP_SIZE, 0.0, 1.0, self.changed, 3, 0.005
        )
        self.tolerance = self.spin(
            "Boundary Tolerance", core.BOUNDARY_TOLERANCE, 0.0, 0.01, self.changed, 4, 0.0005
        )
        self._rows_for_method()

    def _rows_for_method(self):
        fast = self.method.currentText() == "Fast"
        self.angle.setEnabled(fast)
        self.min_size.setEnabled(fast)
        self.tolerance.setEnabled(not fast)

    def changed(self):
        self._rows_for_method()
        super().changed()

    def load(self, feature):
        self._quiet = True
        try:
            self.method.setCurrentText(feature.Method)
            self.angle.setValue(float(feature.AngleThreshold))
            self.min_size.setValue(float(feature.MinimumGroupSize))
            self.tolerance.setValue(float(feature.BoundaryTolerance))
        finally:
            self._quiet = False
        self._rows_for_method()

    def write(self, step):
        step.Method = self.method.currentText()
        step.AngleThreshold = float(self.angle.value())
        step.MinimumGroupSize = float(self.min_size.value())
        step.BoundaryTolerance = float(self.tolerance.value())


# ============================================================================ Tessellate
class TessellatePanel(MeshPanel):
    """Fusion's Tessellate: a solid body into a mesh body. Refinement Low / Medium / High /
    Custom (Surface Deviation, Normal Deviation, Maximum Edge Length), the number of
    triangles; face groups made from the solid's faces."""

    title = "Tessellate"
    icon = "mesh_tessellate"
    step_kind = "Tessellate"
    solid_source = True
    wait_text = "Click the solid body to turn into a mesh body."

    def build(self):
        from . import export

        self.refinement = self.combo(
            "Refinement", core.TESSELLATE_REFINEMENTS, "Medium", self._preset
        )
        surface, normal = export.REFINEMENT["Medium"]
        self.surface = self.number("Surface Deviation", surface, "mm", lambda: self._custom())
        self.normal = self.spin("Normal Deviation", normal, 0.5, 90.0, self._custom, 1, 1)
        self.normal.setSuffix(" deg")
        self.max_edge = self.number("Maximum Edge Length", 0.0, "mm", lambda: self._custom())
        self.triangles = QtWidgets.QLabel("")
        self.layout.addRow(QtWidgets.QLabel("Number of Triangles"), self.triangles)

    def _preset(self):
        from . import export

        level = self.refinement.currentText()
        if level in export.REFINEMENT:
            surface, normal = export.REFINEMENT[level]
            self._quiet = True
            try:
                self.surface.set_value(surface)
                self.normal.setValue(normal)
                self.max_edge.set_value(0.0)
            finally:
                self._quiet = False
        self.changed()

    def _custom(self):
        if self._quiet:
            return
        if self.refinement.currentText() != "Custom":
            self._quiet = True
            try:
                self.refinement.setCurrentText("Custom")  # Fusion: a changed value is Custom
            finally:
                self._quiet = False
        self.changed()

    def load(self, feature):
        self._quiet = True
        try:
            self.refinement.setCurrentText(feature.Refinement)
            self.surface.set_value(float(feature.SurfaceDeviation))
            self.normal.setValue(float(feature.NormalDeviation))
            self.max_edge.set_value(float(feature.MaximumEdgeLength))
        finally:
            self._quiet = False

    def write(self, step):
        step.Refinement = self.refinement.currentText()
        step.SurfaceDeviation = max(1e-6, float(self.surface.value()))
        step.NormalDeviation = max(0.5, float(self.normal.value()))
        step.MaximumEdgeLength = max(0.0, float(self.max_edge.value()))

    def report(self):
        super().report()
        try:
            if self.step is not None and self._preview_on() and not mesh.problem(self.step):
                self.triangles.setText(str(self.step.Mesh.CountFacets))
            else:
                self.triangles.setText("")
        except Exception:
            pass

    def accept(self):
        ok = super().accept()
        if ok and self.body is not None:
            try:
                bodies.leave_used_up(self.doc)
            except Exception:
                pass
        return ok


# ============================================================================ commands
def _open(panel_class, *args, **kwargs):
    return insert_ui._open(panel_class, *args, **kwargs)


def _edit(panel_class, feature):
    return insert_ui._edit(panel_class, feature)


class _MeshCommand:
    text = ""
    tip = ""
    icon = "insert_mesh"
    panel = None
    options = {}

    def GetResources(self):
        from . import ui_icon_path

        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            self.run()
        except core.MeshError as exc:
            commands.tell(str(exc))
        except Exception as exc:
            warn("%s failed: %s" % (self.text, exc))

    def preselected(self, doc):
        found = selected_mesh_bodies(doc)
        return found[0] if found else None

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or start a design first.")
            return
        body = self.preselected(doc)
        if body is None and not mesh.mesh_bodies(doc):
            commands.tell(
                "There is no mesh body yet: INSERT > Insert Mesh, or MESH > Tessellate a body."
            )
            return
        _open(self.panel, body, **dict(self.options))


class RepairCommand(_MeshCommand):
    text = "Repair"
    tip = "Close holes, turn flipped faces round, stitch cracks, or rebuild a closed mesh"
    icon = "mesh_repair"
    panel = RepairPanel


class MakeClosedCommand(_MeshCommand):
    text = "Make Closed Mesh"
    tip = "Rebuild a closed (watertight) mesh body from a broken one (Repair > Rebuild)"
    icon = "mesh_repair"
    panel = RepairPanel
    options = {"repair_type": "Rebuild", "rebuild_type": "Accurate"}


class RemeshCommand(_MeshCommand):
    text = "Remesh"
    tip = "New faces of an even or adaptive size"
    icon = "mesh_remesh"
    panel = RemeshPanel


class ReduceCommand(_MeshCommand):
    text = "Reduce"
    tip = "Fewer faces, within a tolerance or to a number of faces"
    icon = "mesh_reduce"
    panel = ReducePanel


class SmoothCommand(_MeshCommand):
    text = "Smooth"
    tip = "Smooth rough or creased areas of a mesh body"
    icon = "mesh_smooth"
    panel = SmoothPanel


class ShellCommand(_MeshCommand):
    text = "Shell"
    tip = "Hollow a closed mesh body with walls of a thickness"
    icon = "mesh_shell"
    panel = ShellPanel


class ReverseNormalCommand(_MeshCommand):
    text = "Reverse Normal"
    tip = "Turn the faces of a mesh body (or of face groups) the other way"
    icon = "mesh_reverse_normal"
    panel = ReverseNormalPanel


class SeparateCommand(_MeshCommand):
    text = "Separate"
    tip = "One mesh body per shell or per face group"
    icon = "mesh_separate"
    panel = SeparatePanel


class CombineCommand(_MeshCommand):
    text = "Combine"
    tip = "Join, cut, intersect or merge mesh bodies"
    icon = "mesh_combine"
    panel = CombinePanel

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or start a design first.")
            return
        picked = selected_mesh_bodies(doc)
        if len(mesh.mesh_bodies(doc)) < 2 and len(picked) < 2:
            commands.tell("Combine needs two mesh bodies: insert or tessellate another one.")
            return
        panel = _open(CombinePanel, picked[0] if picked else None)
        if panel is not None:
            for tool in picked[1:]:
                panel.pick_other("tools", tool, "", None)


class FaceGroupsCommand(_MeshCommand):
    text = "Generate Face Groups"
    tip = "Group the faces of a mesh body by the way they face"
    icon = "mesh_face_groups"
    panel = FaceGroupsPanel


class TessellateCommand(_MeshCommand):
    text = "Tessellate"
    tip = "A solid body into a mesh body"
    icon = "mesh_tessellate"
    panel = TessellatePanel

    def preselected(self, doc):
        for sel in Gui.Selection.getSelectionEx():
            body = bodies.body_of(sel.Object)
            if body is not None and bodies.has_solid(body):
                return body
        return None

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or start a design first.")
            return
        body = self.preselected(doc)
        if body is None and not bodies.solid_bodies(doc):
            commands.tell("There is no solid body to tessellate yet.")
            return
        _open(TessellatePanel, body)


def _editor(panel_class):
    def edit(obj):
        step = mesh.step_of(obj)
        return _edit(panel_class, step)

    return edit


PANELS = {
    "MeshRepair": RepairPanel,
    "MeshRemesh": RemeshPanel,
    "MeshReduce": ReducePanel,
    "MeshSmooth": SmoothPanel,
    "MeshShell": ShellPanel,
    "MeshReverseNormal": ReverseNormalPanel,
    "MeshSeparate": SeparatePanel,
    "MeshCombine": CombinePanel,
    "MeshFaceGroups": FaceGroupsPanel,
    "Tessellate": TessellatePanel,
}


def edit_piece(obj):
    """A piece (a Separate's or Split Body's body) opens its step's dialog."""
    step = mesh.step_of(obj)
    if step is None:
        return None
    try:
        from . import taskui

        taskui.edit_object(step)
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))
    return None


COMMANDS = {
    "SciForge_MeshRepair": RepairCommand,
    "SciForge_MeshMakeClosed": MakeClosedCommand,
    "SciForge_MeshRemesh": RemeshCommand,
    "SciForge_MeshReduce": ReduceCommand,
    "SciForge_MeshSmooth": SmoothCommand,
    "SciForge_MeshShell": ShellCommand,
    "SciForge_MeshReverseNormal": ReverseNormalCommand,
    "SciForge_MeshSeparate": SeparateCommand,
    "SciForge_MeshCombine": CombineCommand,
    "SciForge_MeshFaceGroups": FaceGroupsCommand,
    "SciForge_MeshTessellate": TessellateCommand,
}
EDITORS = {"SciForge::" + kind: _editor(panel) for kind, panel in PANELS.items()}
EDITORS["SciForge::" + mesh.PIECE] = edit_piece

try:
    mesh.register_consumers()
    mesh.install_watch()
except Exception as _exc:  # pragma: no cover - only without FreeCAD
    warn("mesh steps not watched: %s" % _exc)
