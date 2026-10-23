# SPDX-License-Identifier: LGPL-2.1-or-later
"""The SURFACE tab (and the SOLID tab's Thicken and Boundary Fill) with Fusion's dialogs.

Every tool opens its dialog with nothing selected and waits for clicks, or takes what was
selected before the command. Selection boxes work as in Fusion: the highlighted box takes
the clicks in the 3D view (or the browser), a click on a picked item drops it, the x
clears the box; with Chain Selection on, one click takes every curve (or face) joined
smoothly to it. Every value updates a live preview; drag handles carry a value box (type
a value or a formula there, or with the mouse over the 3D view). Problems are explained
in the dialog, which stays open; OK / Enter keeps the step (one undo step), Cancel / Esc /
Ctrl+Z leave the design as it was. Double-click the step in the timeline to edit it.

The document side is surface.py, the geometry surface_geom.py, the 3D-view helpers
surface_pick.py.
"""

import FreeCAD as App


from . import bodies, curve_pick, curves, preview, surface, taskui, ui_icon_path, warn
from . import surface_core as core
from .bodies_panel import BodyPanel, edit as _edit, start as _start
from .compat import QtCore, QtWidgets
from .surface_pick import RED, CellPicker, ShapeOverlay

PICKED_COLOR = (0.12, 0.53, 0.90)
GREEN = (0.20, 0.75, 0.35)

DIRECTIONS = [("One Side", "one_side"), ("Two Sides", "two_sides"), ("Symmetric", "symmetric")]


def _pairs(labels, keys):
    return [(labels[k], k) for k in keys]


def _alive(obj):
    return bodies.alive(obj)


def _short(sub):
    return (sub or "").split(".")[-1]


def tangent_faces(shape_obj, sub):
    """Names of the faces of `shape_obj` joined smoothly (tangent) to face `sub`: Fusion's
    Chain Selection for faces."""
    import Part

    try:
        shape = shape_obj.Shape
        faces = list(shape.Faces)
        start = int(sub[4:]) - 1
    except Exception:
        return [sub]
    taken = {start}
    todo = [start]
    while todo:
        i = todo.pop()
        face = faces[i]
        for edge in face.Edges:
            for other in shape.ancestorsOfType(edge, Part.Face):
                j = next((k for k, f in enumerate(faces) if f.isSame(other)), None)
                if j is None or j in taken:
                    continue
                if _smooth(face, other, edge):
                    taken.add(j)
                    todo.append(j)
    return ["Face%d" % (i + 1) for i in sorted(taken)]


def _smooth(a, b, edge):
    try:
        u = (edge.FirstParameter + edge.LastParameter) / 2.0
        p = edge.valueAt(u)
        na = a.normalAt(*a.Surface.parameter(p))
        nb = b.normalAt(*b.Surface.parameter(p))
        return na.dot(nb) > 1.0 - 1e-4
    except Exception:
        return False


def free_chain(obj, sub, tangent=True):
    """Names of the free (boundary) edges of `obj`'s surface joined to edge `sub` (through
    smooth joints only with tangent=True): Chain Selection along a surface's boundary.
    None when `sub` is not on the boundary."""
    from . import surface_geom as g

    try:
        shape = obj.Shape
        free = g.free_edges(shape)
        boundary = {}
        for i, e in enumerate(shape.Edges, 1):
            if any(e.isSame(f) for f in free):
                boundary[i] = e
        start = int(sub[4:])
    except Exception:
        return [sub]
    if start not in boundary:
        return None  # not on the boundary: the caller chains it another way
    # Only the boundary counts: the inner edges meeting it at a corner (a tube's seams)
    # neither stop nor join the chain.
    ends = {i: curves._ends(e) for i, e in boundary.items()}
    taken = {start}
    todo = [start]
    while todo:
        i = todo.pop()
        for point, leaving in ends[i]:
            meeting = []
            for j, pair in ends.items():
                if j == i:
                    continue
                for p, d in pair:
                    if (p - point).Length < 1e-6:
                        meeting.append((j, d))
            if len(meeting) != 1:
                continue  # an open end or a branch
            j, d = meeting[0]
            if j in taken or (tangent and not curves._tangent(leaving, d)):
                continue
            taken.add(j)
            todo.append(j)
    return ["Edge%d" % i for i in sorted(taken)]


# -- the dialog base ----------------------------------------------------------------------------
class SurfacePanel(BodyPanel):
    """One surface tool's dialog. Subclasses set `kind` and `boxes`, build their rows in
    build_rows(), give their handles in handle_specs()."""

    kind = None
    # (name, label, role in surface.build ("refs" / "refs2" / "refs3" / "bodies"),
    #  what a click may be: curve / sketch_curve / edge / free_edge / face / body / plane /
    #  axis / point / sketch, text of the empty box)
    boxes = ()
    single = ()  # boxes that hold one pick (a new pick replaces it)
    chain_boxes = ()  # boxes Chain Selection works in
    # Chain Selection on a profile or boundary takes every curve connected to the clicked
    # one (a rectangle's four sides); on a path, edges and faces only what joins smoothly.
    tangent_boxes = ("path", "edges")
    chain_label = "Chain Selection"
    default_box = None  # the value box a number typed over the view goes to
    needs_pick = (core.NeedsPick,)
    last = None

    def __init__(self, doc, feature=None):
        spec = core.spec(self.kind)
        self.title = spec["title"]
        self.icon = spec["icon"]
        self.options = core.with_defaults(self.kind)
        self.picks = {b[0]: [] for b in self.boxes}
        self.formulas = {}
        self.rows = {}
        self.number_fields = {}
        self.step = None
        self.handles = {}
        self.handle_keys = {}
        self.overlay = None
        self.cells = None
        self.axes = None
        self.planes = None
        self.cell_data = []
        self.cells_key = None
        self._shown_sketches = []
        self.user_operation = feature is not None
        if feature is not None:
            self._load(feature)
        super().__init__(
            doc, ("Edit " if feature is not None else "") + self.title, feature is not None
        )
        type(self).last = self
        SurfacePanel.last = self
        self.step = feature
        self.target = feature
        self.value_boxes = taskui.ValueBoxes(self, default=self.default_box)
        self.formula_inputs = {}
        for key, field in self.number_fields.items():
            if isinstance(field, taskui.DistanceField):
                self.formula_inputs[key] = preview.FormulaInput(self, key, field)
        try:
            self.overlay = ShapeOverlay(self.view)
        except Exception as exc:
            warn("%s: highlight unavailable: %s" % (self.title, exc))
        self.update_visibility()
        if feature is not None:
            self._read_formulas(feature)
            self._show_sketches()
            self.show_picks()
            first = self.boxes[0][0] if self.boxes else None
            if first:
                self.activate(first)
            self.after_recompute()
        else:
            if self.boxes:
                self.activate(self.boxes[0][0])
            self.start_from_selection()
            self.show_picks()
            self.next_box()
            self.dirty = True
            self._timer.stop()
            self._recompute()

    # -- reading an existing step ----------------------------------------------------------
    def _load(self, feature):
        try:
            _kind, refs, options = surface.read(feature)
        except Exception as exc:
            warn("could not read %s: %s" % (feature.Label, exc))
            return
        self.options.update(options)
        for name, _label, role, _accepts, _empty in self.boxes:
            if role in refs:
                self.picks[name] = list(refs[role])
            elif role == "bodies":
                self.picks[name] = [(b, "") for b in options.get("bodies") or []]
        self.load_extra(feature, refs, options)

    def load_extra(self, feature, refs, options):
        pass

    def _read_formulas(self, feature):
        for key, prop in surface.NUMBERS.get(self.kind, {}).items():
            text = preview.formula_of(feature, prop)
            if text:
                self.formulas[key] = text

    # -- the form ------------------------------------------------------------------------------
    def build_form(self):
        self.build_rows()

    def build_rows(self):
        """Fill the form (subclasses): self.box(name), self.chain_row(), self.add_combo(...),
        self.add_number(...), self.add_check(...), self.add_operation()."""
        for name, *_rest in self.boxes:
            self.box(name)
        if self.chain_boxes:
            self.chain_row()
        self.add_operation()

    def _box_spec(self, name):
        for spec in self.boxes:
            if spec[0] == name:
                return spec
        raise KeyError(name)

    def box(self, name):
        _name, label, _role, _accepts, empty = self._box_spec(name)
        field = self.selection_box(name, label, empty)
        field.button.setObjectName("SciForgeSurface_" + name)
        field.clear.setObjectName("SciForgeSurface_clear_" + name)
        return field

    def chain_row(self):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(self.options.get("chain", True)))
        box.setObjectName("SciForgeSurface_chain")
        box.setToolTip("One click takes every curve or face joined smoothly to the clicked one")
        box.toggled.connect(lambda *_: self._guarded(self._chain_toggled))
        caption = QtWidgets.QLabel(self.chain_label)
        self.layout.addRow(caption, box)
        self.rows["chain"] = (box, caption)
        return box

    def _chain_toggled(self):
        self.options["chain"] = bool(self.rows["chain"][0].isChecked())

    def chain_on(self):
        row = self.rows.get("chain")
        return bool(row[0].isChecked()) if row else False

    def add_combo(self, key, label, pairs, tips=None):
        box = curve_pick.combo(pairs, self.options.get(key))
        box.setObjectName("SciForgeSurface_" + key)
        box.currentIndexChanged.connect(lambda *_: self._guarded(lambda: self._combo(key)))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        self.rows[key] = (box, caption)
        return box

    def _combo(self, key):
        box = self.rows[key][0]
        self.options[key] = box.currentData()
        if key == "operation":
            self.user_operation = True
        self.option_changed(key)
        self.update_visibility()
        self.changed()

    def add_check(self, key, label, tip=""):
        box = QtWidgets.QCheckBox()
        box.setChecked(bool(self.options.get(key)))
        box.setObjectName("SciForgeSurface_" + key)
        if tip:
            box.setToolTip(tip)
        box.toggled.connect(lambda *_: self._guarded(lambda: self._checked(key)))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        self.rows[key] = (box, caption)
        return box

    def _checked(self, key):
        self.options[key] = bool(self.rows[key][0].isChecked())
        self.option_changed(key)
        self.update_visibility()
        self.changed()

    def add_number(self, key, label, unit="mm"):
        field = taskui.DistanceField(
            float(self.options.get(key, 0.0)),
            unit=unit,
            on_change=lambda value, k=key: self._number(k, value),
        )
        field.widget.setObjectName("SciForgeSurface_" + key)
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, field.widget)
        self.rows[key] = (field.widget, caption)
        self.number_fields[key] = field
        return field

    def add_ratio(self, key, label):
        box = curve_pick.RatioBox(float(self.options.get(key, 1.0)))
        box.setObjectName("SciForgeSurface_" + key)
        box.valueChanged.connect(lambda value, k=key: self._guarded(lambda: self._number(k, value)))
        caption = QtWidgets.QLabel(label)
        self.layout.addRow(caption, box)
        self.rows[key] = (box, caption)
        self.number_fields[key] = box
        return box

    def _number(self, key, value):
        if self._closed:
            return
        self.options[key] = float(value)
        self.option_changed(key)
        self.changed()

    def add_operation(self):
        ops = core.operations(self.kind)
        if not ops:
            return None
        pairs = [(core.OPERATION_LABELS[op], op) for op in ops]
        return self.add_combo("operation", "Operation", pairs)

    def show_option(self, key, shown):
        row = self.rows.get(key)
        if row is not None:
            self.show_row(row[0], row[1], shown)

    def show_box(self, name, shown):
        field = self.fields.get(name)
        if field is not None:
            self.show_row(field.widget, self.captions.get(name), shown)

    def option_changed(self, key):
        """A choice or value changed (subclasses)."""

    def update_visibility(self):
        """Rows that apply to the choices made (subclasses)."""

    def set_number(self, key, value):
        """Show a value in its field without telling the dialog (a handle being dragged)."""
        field = self.number_fields.get(key)
        if field is None:
            return
        if isinstance(field, taskui.DistanceField):
            field.set_value(value)
        else:
            field.blockSignals(True)
            field.setValue(value)
            field.blockSignals(False)

    # -- formulas (preview.FormulaInput calls these) --------------------------------------------
    def formula_typed(self, key, text, value):
        self.formulas[key] = text
        self._number(key, value)

    def formula_cleared(self, key):
        if self.formulas.pop(key, None) is not None:
            self.changed()

    def formula_failed(self, key, text):
        self.message.setText("⚠ " + text)

    def _apply_formulas(self, step):
        for key, prop in surface.NUMBERS.get(self.kind, {}).items():
            try:
                preview.set_formula(step, prop, self.formulas.get(key, ""))
            except Exception as exc:
                warn("%s formula: %s" % (self.title, exc))

    # -- the boxes -------------------------------------------------------------------------------
    def activated(self, name):
        self.box_activated(name)
        self.paint_picks()

    def box_activated(self, name):
        """A box now takes the clicks (subclasses show pickers)."""

    def cleared(self, name):
        self.picks[name] = []
        self.picks_changed(name)

    def next_box(self):
        """Activate the first box still empty (Fusion moves on after a pick)."""
        for name, *_rest in self.boxes:
            field = self.fields.get(name)
            if field is None or not field.widget.isVisibleTo(self.form):
                continue
            if not self.picks.get(name):
                self.activate(name)
                return
        if self.active is None and self.boxes:
            self.activate(self.boxes[0][0])

    def show_picks(self):
        for name, *_rest in self.boxes:
            field = self.fields.get(name)
            if field is not None:
                field.set_text(self.pick_text(name))

    def pick_text(self, name):
        picks = self.picks.get(name) or []
        if not picks:
            return ""
        counts = {}
        for obj, sub in picks:
            counts[self._noun(obj, sub)] = counts.get(self._noun(obj, sub), 0) + 1
        if len(picks) == 1:
            obj, sub = picks[0]
            noun = self._noun(obj, sub)
            if noun in ("body", "plane"):
                return obj.Label
            if noun == "sketch":
                return obj.Label
        return core.picked_text(len(picks), counts) or "%d selected" % len(picks)

    @staticmethod
    def _noun(obj, sub):
        if sub.startswith("Edge"):
            return "curve" if curves.is_sketch(obj) else "edge"
        if sub.startswith("Face"):
            return "face"
        if sub.startswith("Vertex"):
            return "point"
        if bodies.is_body(obj):
            return "body"
        if obj.TypeId in surface.PLANE_TYPES:
            return "plane"
        if obj.TypeId in surface.LINE_TYPES:
            return "edge"
        if curves.is_sketch(obj):
            return "sketch"
        return "body"

    # -- clicks ----------------------------------------------------------------------------------
    def picked(self, obj, short, point):
        if self.active is None or self.active not in self.picks:
            return
        if not self._box_spec(self.active)[3]:
            return  # a box filled by its own picker (cells): FreeCAD's selection is not a pick
        if self.cells is not None and self.cells.clicked_recently():
            return  # the click went to a cell
        if self.axes is not None and self.axes.clicked_recently():
            return
        if self.handles_busy():
            return
        ref = self.interpret(self.active, obj, short, point)
        if ref is None:
            return
        self.take(self.active, ref)

    def handles_busy(self):
        for handle in self.handles.values():
            try:
                if hasattr(handle, "busy") and handle.busy():
                    return True
                if hasattr(handle, "dragger") and handle.dragger.isActive.getValue():
                    return True
            except Exception:
                pass
        return False

    def own_preview(self, obj):
        """True when `obj` is (in) what this dialog is making (a new body's step)."""
        if self.step is None or not _alive(self.step) or obj is None:
            return False
        made = surface.created_body(self.step)
        mine = [self.step] + surface.followers_of(self.step) + surface.pieces_of(self.step)
        return obj in mine or (made is not None and bodies.body_of(obj) is made)

    def base_of_preview(self, obj, short):
        """A click on this dialog's own result (a MODIFY step in the body being changed):
        the same edge / face as it was before the step, or None."""
        step = None
        for s in [self.step] + (surface.followers_of(self.step) if self.step else []):
            if s is not None and _alive(s) and bodies.body_of(s) is bodies.body_of(obj):
                step = s
        if step is None:
            return (obj, short)
        body = bodies.body_of(step)
        if body is not None and body.Tip is not step and obj is not step:
            # a later step of that body (the timeline was rolled back): keep it as is
            pass
        return curve_pick.base_element(step.BaseFeature, obj, short)

    def interpret(self, name, obj, short, point):
        """What a click on (obj, short) means for box `name`, or None (with a word why)."""
        _n, _label, _role, accepts, _empty = self._box_spec(name)
        short = _short(short)
        if (
            ("curve" in accepts or "sketch_curve" in accepts)
            and point is not None
            and not short.startswith(("Edge", "Vertex"))
        ):
            near = self.sketch_curve_near(point)
            if near is not None:
                obj, short = near
        if self.own_preview(obj) and core.makes_body(self.kind):
            # A sketch curve along the preview's edge (a loft's rail, a sweep's path) is what
            # a person aims at: Fusion picks the curve then.
            near = None
            if ("curve" in accepts or "sketch_curve" in accepts) and point is not None:
                near = self.sketch_curve_near(point)
            if near is None:
                self.message.setText("⚠ That is what this dialog is making. Pick something else.")
                return None
            obj, short = near
        if (
            self.step is not None
            and not core.makes_body(self.kind)
            and short.startswith(("Edge", "Face"))
            and "body" not in accepts
        ):
            mapped = self.base_of_preview(obj, short)
            if mapped is None:
                self.message.setText(
                    "⚠ That is made by this step. Pick it as it was before (Ctrl+Z, then pick)."
                )
                return None
            obj, short = mapped
        sketch = curves.is_sketch(obj)
        for accept in accepts:
            if accept == "curve" and short.startswith("Edge"):
                return (obj, short)
            if accept == "sketch_curve" and sketch and short.startswith("Edge"):
                return (obj, short)
            if accept in ("edge", "free_edge") and short.startswith("Edge") and not sketch:
                return (obj, short)
            if accept == "face" and short.startswith("Face"):
                return (obj, short)
            if accept == "planar_face" and short.startswith("Face") and not sketch:
                if _planar(obj, short):
                    return (obj, short)
            if accept == "face" and bodies.is_body(obj) and not short:
                return (obj, "")
            if accept == "body" and not sketch:
                body = bodies.body_of(obj)
                if body is not None and obj.TypeId not in surface.PLANE_TYPES + surface.LINE_TYPES:
                    if not getattr(obj, "Role", None):
                        return (body, "")
            if accept == "plane":
                if obj.TypeId in surface.PLANE_TYPES:
                    return (obj, "")
                if short.startswith("Face") and _planar(obj, short):
                    return (obj, short)
            if accept == "axis":
                if obj.TypeId in surface.LINE_TYPES:
                    return (obj, "")
                if short.startswith("Edge") and _straight(obj, short):
                    return (obj, short)
            if accept == "point":
                if short.startswith("Vertex"):
                    return (obj, short)
                if obj.TypeId in surface.POINT_TYPES:
                    return (obj, "")
            if accept == "sketch" and sketch and not short:
                return (obj, "")
        self.message.setText("⚠ " + self.wrong_pick(name))
        return None

    def sketch_curve_near(self, point, pixels=6.0):
        """(sketch, "EdgeN") of a shown sketch curve within a few pixels of a click that
        FreeCAD gave as a face: Fusion picks the curve then, but FreeCAD's selection can
        give the face a sketch curve lies on (a sketch on the face's plane)."""
        import math

        import Part

        try:
            point = App.Vector(point)
            here = self.view.getPointOnViewport(point)
            vertex = Part.Vertex(point)
        except Exception:
            return None
        best = None
        for obj in self.doc.Objects:
            if not curves.is_sketch(obj) or not bodies.is_shown(obj):
                continue
            try:
                shape = bodies.global_shape(obj)
            except Exception:
                continue
            for i, edge in enumerate(shape.Edges):
                try:
                    nearest = edge.distToShape(vertex)[1][0][0]
                    there = self.view.getPointOnViewport(nearest)
                except Exception:
                    continue
                gap = math.hypot(there[0] - here[0], there[1] - here[1])
                if gap <= pixels and (best is None or gap < best[0]):
                    best = (gap, obj, "Edge%d" % (i + 1))
        return (best[1], best[2]) if best is not None else None

    def wrong_pick(self, name):
        _n, label, _role, accepts, _empty = self._box_spec(name)
        words = {
            "curve": "sketch curves or edges",
            "sketch_curve": "sketch curves",
            "edge": "edges of a body",
            "free_edge": "edges on the outside of a surface",
            "face": "faces",
            "planar_face": "flat faces",
            "body": "bodies",
            "plane": "planes or flat faces",
            "axis": "a line, a straight edge or an axis",
            "point": "points",
            "sketch": "a sketch",
        }
        allowed = [words[a] for a in accepts if a in words]
        return "%s takes %s." % (label, ", ".join(dict.fromkeys(allowed)))

    def tangent_chain(self, name):
        return name in self.tangent_boxes

    def expand(self, name, ref):
        """A click with Chain Selection on: the picks it stands for."""
        obj, sub = ref
        if name not in self.chain_boxes or not self.chain_on():
            return [ref]
        try:
            if sub.startswith("Edge"):
                if curves.is_sketch(obj):
                    names = curves.chain(obj, sub, tangent=self.tangent_chain(name))
                else:
                    names = free_chain(obj, sub, tangent=self.tangent_chain(name))
                    if names is None:
                        names = curves.chain(obj, sub, tangent=self.tangent_chain(name))
                return [(obj, n) for n in names]
            if sub.startswith("Face"):
                return [(obj, n) for n in tangent_faces(obj, sub)]
        except Exception as exc:
            warn("%s chain: %s" % (self.title, exc))
        return [ref]

    def take(self, name, ref):
        """Add the pick to box `name`, or drop it when it is there already."""
        self.message.setText("")
        current = list(self.picks.get(name) or [])
        if name in self.single:
            same = current and current[0][0] is ref[0] and current[0][1] == ref[1]
            self.picks[name] = [] if same else [ref]
        else:
            group = self.expand(name, ref)
            keys = {(o.Name, s) for o, s in current}
            if (ref[0].Name, ref[1]) in keys:
                drop = {(o.Name, s) for o, s in group}
                current = [p for p in current if (p[0].Name, p[1]) not in drop]
            else:
                current += [p for p in group if (p[0].Name, p[1]) not in keys]
            self.picks[name] = current
        self.picks_changed(name)
        self.after_pick(name)

    def after_pick(self, name):
        """Fusion moves on to the next box once one has its pick (subclasses)."""
        if name in self.single and self.picks.get(name):
            self.next_box()

    def picks_changed(self, name):
        self.show_picks()
        self.paint_picks()
        self.changed()

    # -- what is built ----------------------------------------------------------------------------
    def refs(self):
        refs = {"refs": [], "refs2": [], "refs3": []}
        for name, _label, role, _accepts, _empty in self.boxes:
            if role in refs:
                refs[role] = refs[role] + list(self.picks.get(name) or [])
        return refs

    def build_options(self):
        options = dict(self.options)
        for name, _label, role, _accepts, _empty in self.boxes:
            if role == "bodies":
                options["bodies"] = [o for o, _s in self.picks.get(name) or []]
        return options

    def missing(self):
        """What still has to be picked ('' when the step can be built)."""
        for name, label, _role, _accepts, empty in self.required():
            if not self.picks.get(name):
                return "Select %s." % label.lower()
        return ""

    def required(self):
        return [b for b in self.boxes if self.fields.get(b[0]) is not None and self.is_shown(b[0])]

    def is_shown(self, name):
        field = self.fields.get(name)
        return field is not None and not field.widget.isHidden()

    def drop_preview(self):
        if self.step is not None and not self.editing:
            try:
                surface.remove(self.step)
            except Exception as exc:
                warn("%s: %s" % (self.title, exc))
            self.step = None
            self.target = None

    def apply(self):
        hint = self.missing()
        if hint:
            self.drop_preview()
            raise core.NeedsPick(hint)
        options = self.build_options()
        try:
            core.check_values(self.kind, options)
            self.check(options)
        except core.NeedsPick:
            self.drop_preview()
            raise
        if self.step is not None and _alive(self.step):
            self._apply_formulas(self.step)
        self.step = surface.build(self.kind, self.refs(), options, self.step)
        self.target = self.step
        self._apply_formulas(self.step)

    def check(self, options):
        """More checks before building (subclasses; raise core.SurfaceError / NeedsPick)."""

    def preview_steps(self):
        if self.step is None or not _alive(self.step):
            return []
        steps = [self.step] + surface.followers_of(self.step) + surface.pieces_of(self.step)
        return [s for s in steps if _alive(s)]

    def can_finish(self):
        if self.step is None or not _alive(self.step):
            return self.missing() or "Make the picks the dialog asks for first."
        return ""

    def after_recompute(self):
        try:
            self.paint_picks()
        except Exception as exc:
            warn("%s highlight: %s" % (self.title, exc))
        try:
            self.sync_handles()
        except Exception as exc:
            warn("%s handles: %s" % (self.title, exc))
        try:
            self.refresh_cells()
        except Exception as exc:
            warn("%s cells: %s" % (self.title, exc))
        for step in self.preview_steps():
            body = bodies.body_of(step)
            if body is not None and surface.is_surface_body(body):
                surface.two_sided(body)

    def refresh_cells(self):
        pass

    # -- drawing the picks ----------------------------------------------------------------------
    def paint_picks(self):
        if self.overlay is None:
            return
        for name, *_rest in self.boxes:
            shapes = []
            for obj, sub in self.picks.get(name) or []:
                shape = self._pick_shape(obj, sub)
                if shape is not None:
                    shapes.append(shape)
            color = PICKED_COLOR
            self.overlay.show(name, shapes, color, 0.55, 4.0 if name == self.active else 3.0)

    def _pick_shape(self, obj, sub):
        try:
            if not _alive(obj):
                return None
            if sub.startswith(("Edge", "Face", "Vertex")):
                return surface.element_of(obj, sub)
            if curves.is_sketch(obj):
                return curves.to_global(obj.Shape, obj)
            if obj.TypeId in surface.PLANE_TYPES + surface.LINE_TYPES:
                return None
            if bodies.is_body(obj) and self.kind in ("stitch", "reverse_normal", "boundary_fill"):
                return None  # whole bodies: drawn by FreeCAD's own highlight
            if bodies.is_body(obj):
                return surface.whole_shape(obj)
        except Exception:
            return None
        return None

    # -- handles -----------------------------------------------------------------------------------
    def handle_specs(self):
        """[{key, type: "arrow" | "angle", ...}] (subclasses)."""
        return []

    def sync_handles(self):
        if self._closed:
            return
        try:
            specs = self.handle_specs() if not self.error else []
        except Exception as exc:
            warn("%s handles: %s" % (self.title, exc))
            specs = []
        wanted = {s["key"]: s for s in specs}
        for key in list(self.handles):
            if key not in wanted:
                self._remove_handle(key)
        for key, spec in wanted.items():
            geometry = self._geometry_key(spec)
            handle = self.handles.get(key)
            dragging = handle is not None and self._dragging(handle)
            if handle is None or (self.handle_keys.get(key) != geometry and not dragging):
                self._remove_handle(key)
                self._make_handle(spec)
                self.handle_keys[key] = geometry
            elif not dragging:
                try:
                    if spec["type"] == "arrow":
                        if abs(handle.distance() - spec["value"]) > 1e-9:
                            handle.set_distance(spec["value"])
                    else:
                        if abs(handle.angle() - spec["value"]) > 1e-9:
                            handle.set_angle(spec["value"])
                except Exception:
                    pass

    @staticmethod
    def _geometry_key(spec):
        def r(v):
            return tuple(round(c, 5) for c in v) if v is not None else None

        if spec["type"] == "arrow":
            return ("arrow", r(spec["origin"]), r(spec["dir"]), round(spec["size"], 3))
        return (
            "angle",
            r(spec["center"]),
            r(spec["axis"]),
            r(spec["zero"]),
            round(spec["radius"], 4),
            spec.get("pointing", 1.0),
        )

    @staticmethod
    def _dragging(handle):
        try:
            if hasattr(handle, "dragging"):
                return bool(handle.dragging())
            return bool(handle.dragger.isActive.getValue())
        except Exception:
            return False

    def _make_handle(self, spec):
        key = spec["key"]
        try:
            if spec["type"] == "arrow":
                handle = taskui.ArrowDragger(
                    spec["origin"],
                    spec["dir"],
                    spec["value"],
                    spec["size"],
                    on_drag=lambda d, k=key: self._dragged(k, d),
                    on_release=lambda d, k=key: self._dragged(k, d),
                )
            else:
                from .revolve_ui import AngleHandle

                handle = AngleHandle(
                    spec["center"],
                    spec["axis"],
                    spec["zero"],
                    spec["radius"],
                    spec["value"],
                    spec["size"],
                    pointing=spec.get("pointing", 1.0),
                    on_drag=lambda a, k=key: self._dragged(k, a),
                    on_release=lambda a, k=key: self._dragged(k, a),
                )
        except Exception as exc:
            warn("%s handle unavailable: %s" % (self.title, exc))
            return
        self.handles[key] = handle
        field = self.number_fields.get(spec.get("field", key))
        if isinstance(field, taskui.DistanceField):
            self.value_boxes.attach(
                handle,
                key,
                lambda f=field: f.widget.text(),
                lambda text, k=spec.get("field", key): self._box_typed(k, text),
            )

    def _box_typed(self, key, text):
        if self._closed:
            return
        formula = self.formula_inputs.get(key)
        if formula is not None:
            formula.take(text)
            return
        field = self.number_fields.get(key)
        try:
            field.take(field.parse(text.strip().lstrip("=")))
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _dragged(self, key, value):
        if self._closed:
            return
        try:
            self.busy()
            value = self.handle_value(key, value)
            field_key = key
            self.formulas.pop(field_key, None)
            self.set_number(field_key, value)
            self.options[field_key] = float(value)
            self.option_changed(field_key)
            self.changed()
        except Exception as exc:
            warn("%s drag: %s" % (self.title, exc))

    def handle_value(self, key, raw):
        """The field value a handle at `raw` stands for (subclasses: a symmetric whole
        length is twice the arrow's distance...)."""
        return round(float(raw), 4)

    def _remove_handle(self, key):
        handle = self.handles.pop(key, None)
        self.handle_keys.pop(key, None)
        if handle is not None:
            try:
                handle.remove()
            except Exception:
                pass

    def remove_handles(self):
        for key in list(self.handles):
            self._remove_handle(key)

    def handle_size(self, point, hi=None):
        try:
            return taskui.handle_size_at(self.view, point, hi=hi)
        except Exception:
            return 5.0

    # -- sketches shown while editing ------------------------------------------------------------
    def _show_sketches(self):
        """While a step is edited, the sketches it uses are shown so their curves can be
        clicked (Fusion shows them too); they hide again when the dialog closes."""
        for picks in self.picks.values():
            for obj, _sub in picks:
                if curves.is_sketch(obj) and not bodies.is_shown(obj):
                    bodies.set_shown(obj, True)
                    self._shown_sketches.append(obj)

    def _hide_shown(self):
        for obj in self._shown_sketches:
            if _alive(obj):
                bodies.set_shown(obj, False)
        self._shown_sketches = []

    # -- closing -----------------------------------------------------------------------------------
    def before_close(self, ok):
        self._hide_shown()
        if ok and self.step is not None and _alive(self.step):
            if self.kind in ("extrude", "revolve", "sweep", "loft", "patch", "ruled"):
                surface.hide_sketches(self.step)

    def after_close(self, ok):
        super().after_close(ok)
        if ok and self.step is not None and _alive(self.step):
            surface.log_built(self.step)

    def restore_view(self):
        for attr in ("cells", "axes", "planes", "overlay"):
            item = getattr(self, attr, None)
            setattr(self, attr, None)
            if item is not None:
                try:
                    item.remove()
                except Exception:
                    pass
        try:
            self.value_boxes.discard()
        except Exception:
            pass

    # -- helpers for subclasses -----------------------------------------------------------------
    def edges(self, name):
        try:
            return surface.edges_of(self.picks.get(name) or [])
        except Exception:
            return []

    def faces(self, name):
        try:
            return surface.faces_of(self.picks.get(name) or [])
        except Exception:
            return []

    def show_plane_squares(self, show):
        """Fusion draws the origin planes to click while a box takes planes."""
        from .sketch_ui import PlanePicker

        if not show:
            if self.planes is not None:
                self.planes.remove()
                self.planes = None
            return
        if self.planes is not None:
            return
        body = self._some_body()
        if body is None:
            return
        try:
            # PlanePicker frames the planes when the body has no solid (a new design); a
            # surface body has none either, and the view must stay where the user put it
            camera = self.view.getCamera()
        except Exception:
            camera = None
        try:
            self.planes = PlanePicker(
                self.view,
                body,
                lambda plane: QtCore.QTimer.singleShot(0, lambda: self._plane_clicked(plane)),
            )
            self.planes.own_selection()  # a plane picked in the browser comes as a pick
        except Exception as exc:
            warn("%s planes unavailable: %s" % (self.title, exc))
        if camera is not None and self._has_shape():
            try:
                self.view.setCamera(camera)
            except Exception:
                pass

    def _plane_clicked(self, plane):
        if self._closed or self.active is None:
            return
        _n, _label, _role, accepts, _empty = self._box_spec(self.active)
        if "plane" in accepts:
            self.take(self.active, (plane, ""))

    def show_axis_lines(self, show):
        from . import profile_pick, revolve
        from .revolve_ui import AxisPicker

        if not show:
            if self.axes is not None:
                self.axes.remove()
                self.axes = None
            return
        if self.axes is not None:
            return
        body = self._some_body()
        if body is None:
            return
        try:
            sketches = profile_pick.candidate_sketches(body, [])
            length = 50.0
            box = None
            for b in bodies.list_bodies(self.doc):
                if not b.Shape.isNull():
                    box = b.Shape.BoundBox if box is None else box.united(b.Shape.BoundBox)
            if box is not None:
                length = max(50.0, box.DiagonalLength * 0.8)
            self.axes = AxisPicker(
                self.view,
                revolve.overlay_lines(body, sketches, length),
                lambda ref: QtCore.QTimer.singleShot(0, lambda: self._axis_clicked(ref)),
            )
        except Exception as exc:
            warn("%s axes unavailable: %s" % (self.title, exc))

    def _axis_clicked(self, ref):
        if self._closed or self.active is None:
            return
        _n, _label, _role, accepts, _empty = self._box_spec(self.active)
        if "axis" in accepts:
            self.take(self.active, ref)
            if self.axes is not None:
                self.axes.set_picked(ref)

    def _has_shape(self):
        """True when the design shows something (then the camera is the user's)."""
        try:
            return any(not b.Shape.isNull() and b.Shape.Faces for b in bodies.list_bodies(self.doc))
        except Exception:
            return False

    def _some_body(self):
        body = None
        for picks in self.picks.values():
            for obj, _sub in picks:
                body = bodies.body_of(obj)
                if body is not None:
                    return body
        found = bodies.list_bodies(self.doc)
        return bodies.active_body(self.doc) or (found[0] if found else None)


def _planar(obj, short):
    try:
        return obj.Shape.getElement(short).Surface.TypeId == "Part::GeomPlane"
    except Exception:
        return False


def _straight(obj, short):
    try:
        return obj.Shape.getElement(short).Curve.TypeId in (
            "Part::GeomLine",
            "Part::GeomLineSegment",
        )
    except Exception:
        return False


def _centre(shapes):
    box = None
    for s in shapes:
        if s is None or s.isNull():
            continue
        box = App.BoundBox(s.BoundBox) if box is None else box.united(s.BoundBox)
    return (box.Center, box.DiagonalLength) if box is not None else (None, 0.0)


# -- CREATE: Extrude -------------------------------------------------------------------------------
class ExtrudePanel(SurfacePanel):
    kind = "extrude"
    boxes = (
        ("profile", "Profiles", "refs", ("curve", "sketch", "planar_face"), "Select profiles"),
        (
            "start_object",
            "Start Object",
            "refs3",
            ("plane", "face", "point"),
            "Select a plane, face or point",
        ),
        ("object", "Object", "refs2", ("plane", "face", "body", "point"), "Select an object"),
    )
    single = ("object", "start_object")
    chain_boxes = ("profile",)
    default_box = "distance"

    def load_extra(self, feature, refs, options):
        if options.get("extent") != "to_object":
            self.picks["object"] = []  # All keeps the bodies it goes through there

    def build_rows(self):
        self.box("profile")
        self.chain_row()
        self.add_combo(
            "start",
            "Start",
            [("Profile Plane", "profile"), ("Offset", "offset"), ("From Object", "object")],
        )
        self.box("start_object")
        self.add_number("start_offset", "Offset")
        self.add_combo("direction", "Direction", DIRECTIONS)
        self.add_combo(
            "extent",
            "Extent",
            [("Distance", "distance"), ("To Object", "to_object"), ("All", "all")],
        )
        self.box("object")
        self.add_combo(
            "chain_faces",
            "Faces",
            [("Chain Faces", True), ("Extend Faces", False)],
        )
        self.rows["chain_faces"][0].setToolTip(
            "Chain Faces: the object face and the faces joined smoothly to it stop the "
            "extrusion. Extend Faces: the face alone, carried on past its edges"
        )
        self.add_check("flip", "Flip", "All goes the other way, through what lies behind")
        self.add_combo(
            "measurement", "Measurement", [("Half Length", "half"), ("Whole Length", "whole")]
        )
        self.add_number("distance", "Distance")
        self.add_number("taper", "Taper Angle", "deg")
        self.add_number("distance2", "Distance Two")
        self.add_number("taper2", "Taper Angle Two", "deg")
        self.add_operation()

    def update_visibility(self):
        o = self.options
        extent = o["extent"]
        to_object = extent == "to_object"
        two = o["direction"] == "two_sides"
        from_object = o["start"] == "object"
        self.show_box("start_object", from_object)
        self.show_option("start_offset", o["start"] in ("offset", "object"))
        self.show_box("object", to_object)
        self.show_option("chain_faces", to_object)
        self.show_option("flip", extent == "all" and o["direction"] == "one_side")
        self.show_option("measurement", o["direction"] == "symmetric" and extent == "distance")
        self.show_option("distance", extent == "distance")
        self.show_option("taper", not to_object)
        self.show_option("distance2", two and extent == "distance")
        self.show_option("taper2", two and not to_object)
        if (self.active == "object" and not to_object) or (
            self.active == "start_object" and not from_object
        ):
            self.activate("profile")
        self.show_plane_squares(self.active in ("object", "start_object"))

    def box_activated(self, name):
        self.show_plane_squares(name in ("object", "start_object"))

    def option_changed(self, key):
        if key == "extent" and self.options["extent"] == "to_object":
            self.activate("object")
        if key == "start" and self.options["start"] == "object":
            self.activate("start_object")

    def expand(self, name, ref):
        if name == "profile" and ref[1].startswith("Face"):
            return [ref]  # a flat face is one profile: the curves round it
        return super().expand(name, ref)

    def after_pick(self, name):
        if name == "profile" and self.picks["profile"]:
            if self.options["start"] == "object" and not self.picks["start_object"]:
                self.activate("start_object")
            elif self.options["extent"] == "to_object" and not self.picks["object"]:
                self.activate("object")
            return
        super().after_pick(name)

    def refs(self):
        refs = super().refs()
        if self.options["extent"] == "all":
            refs["refs2"] = self.through_bodies()
        elif self.options["extent"] != "to_object":
            refs["refs2"] = []
        if self.options["start"] != "object":
            refs["refs3"] = []
        return refs

    def through_bodies(self):
        """Extent All: the visible bodies (not the one this dialog makes)."""
        mine = None
        if self.step is not None and _alive(self.step):
            mine = surface.created_body(self.step)
        found = []
        for body in bodies.list_bodies(self.doc):
            if body is mine or not bodies.is_shown(body):
                continue
            try:
                if body.Shape.isNull() or not body.Shape.Faces:
                    continue
            except Exception:
                continue
            found.append((body, ""))
        return found

    def check(self, options):
        if options["extent"] == "all" and not self.through_bodies():
            raise core.SurfaceError(
                "There is no visible body for All to extrude through. Show one, or use Distance."
            )

    def _start_point(self, centre, normal):
        """Where the arrow starts: the profile moved to where the extrusion starts."""
        from . import surface_geom as g

        o = self.options
        lift = float(o["start_offset"]) if o["start"] in ("offset", "object") else 0.0
        if o["start"] != "object" or not self.picks["start_object"]:
            return centre + normal * lift
        try:
            start = surface.target_of_ref(*self.picks["start_object"][0])
            height = g._start_height(start, normal, centre)
            if height is not None:
                return centre + normal * (height + lift)
            face = g._start_face(start, normal, lift, [])
            hit = g._nearest_hit(face, centre, normal, g.reach([face], 0.0))
            if hit is not None:
                return centre + normal * hit
        except Exception:
            pass
        return centre + normal * lift

    def handle_specs(self):
        if self.options["extent"] != "distance":
            return []
        edges = self.edges("profile")
        if not edges:
            return []
        try:
            normal = surface.sketch_normal(self.picks["profile"])
        except Exception:
            return []
        centre, _size = _centre(edges)
        if centre is None:
            return []
        centre = self._start_point(centre, normal)
        size = self.handle_size(centre)
        d1 = float(self.options["distance"])
        specs = []
        if self.options["direction"] == "symmetric" and self.options["measurement"] == "whole":
            d1 = d1 / 2.0
        specs.append(
            {
                "key": "distance",
                "type": "arrow",
                "origin": centre,
                "dir": normal,
                "value": d1,
                "size": size,
            }
        )
        if self.options["direction"] == "two_sides":
            specs.append(
                {
                    "key": "distance2",
                    "type": "arrow",
                    "origin": centre,
                    "dir": normal * -1.0,
                    "value": float(self.options["distance2"]),
                    "size": size,
                }
            )
        return specs

    def handle_value(self, key, raw):
        value = float(raw)
        if (
            key == "distance"
            and self.options["direction"] == "symmetric"
            and self.options["measurement"] == "whole"
        ):
            value *= 2.0
        return round(value, 4)


# -- CREATE: Revolve -------------------------------------------------------------------------------
class RevolvePanel(SurfacePanel):
    kind = "revolve"
    boxes = (
        ("profile", "Profile", "refs", ("curve", "sketch"), "Select curves"),
        ("axis", "Axis", "refs2", ("axis",), "Select an axis"),
        (
            "to_object",
            "Object",
            "refs3",
            ("plane", "point", "curve"),
            "Select a plane, an edge or a point",
        ),
        (
            "to_object2",
            "Object Two",
            "refs3",
            ("plane", "point", "curve"),
            "Select a plane, an edge or a point",
        ),
    )
    single = ("axis", "to_object", "to_object2")
    chain_boxes = ("profile",)
    default_box = "angle"

    def load_extra(self, feature, refs, options):
        found = list(refs.get("refs3") or [])
        self.picks["to_object"] = found[:1]
        self.picks["to_object2"] = found[1:2]

    def build_rows(self):
        self.box("profile")
        self.box("axis")
        self.add_check(
            "project_axis",
            "Project Axis",
            "Lay the axis into the profile's plane (off: the axis stays where it is)",
        )
        self.chain_row()
        self.add_combo("type", "Type", _pairs(core.REVOLVE_LABELS, core.REVOLVE_TYPES))
        self.box("to_object")
        self.add_combo("direction", "Direction", DIRECTIONS)
        self.box("to_object2")
        self.add_number("angle", "Angle", "deg")
        self.add_number("angle2", "Angle Two", "deg")
        self.add_operation()

    def update_visibility(self):
        rtype = self.options["type"]
        angle = rtype == "angle"
        two = self.options["direction"] == "two_sides"
        self.show_box("to_object", rtype == "to")
        self.show_box("to_object2", rtype == "to" and two)
        self.show_option("direction", angle or rtype == "to")
        box = self.rows.get("direction", (None,))[0]
        if box is not None:  # To turns One Side or Two Sides (Fusion offers no Symmetric)
            item = box.model().item(2)
            if item is not None:
                item.setEnabled(rtype != "to")
        self.show_option("angle", angle)
        self.show_option("angle2", angle and two)
        if self.active in ("to_object", "to_object2") and not self.is_shown(self.active):
            self.activate("profile")

    def box_activated(self, name):
        self.show_axis_lines(name == "axis")
        self.show_plane_squares(name in ("to_object", "to_object2"))

    def option_changed(self, key):
        o = self.options
        if key == "type" and o["type"] == "to" and o["direction"] == "symmetric":
            o["direction"] = "one_side"
            box = self.rows["direction"][0]
            box.blockSignals(True)
            curve_pick.set_combo(box, "one_side")
            box.blockSignals(False)
        if key in ("type", "direction") and o["type"] == "to":
            if self.picks["profile"] and self.picks["axis"]:
                if not self.picks["to_object"]:
                    self.activate("to_object")
                elif o["direction"] == "two_sides" and not self.picks["to_object2"]:
                    self.activate("to_object2")

    def refs(self):
        refs = super().refs()
        if self.options["type"] != "to":
            refs["refs3"] = []
        else:
            refs["refs3"] = list(self.picks.get("to_object") or [])
            if self.options["direction"] == "two_sides":
                refs["refs3"] += list(self.picks.get("to_object2") or [])
        return refs

    def after_pick(self, name):
        two = self.options["direction"] == "two_sides"
        if name == "profile" and self.picks["profile"] and not self.picks["axis"]:
            self.activate("axis")
        elif name == "axis" and self.picks["axis"]:
            self.show_axis_lines(False)
            if self.options["type"] == "to" and not self.picks["to_object"]:
                self.activate("to_object")
        elif name == "to_object" and self.picks["to_object"]:
            if self.options["type"] == "to" and two and not self.picks["to_object2"]:
                self.activate("to_object2")
            else:
                self.show_plane_squares(False)
        elif name == "to_object2" and self.picks["to_object2"]:
            self.show_plane_squares(False)

    def handle_specs(self):
        if self.options["type"] != "angle" or not self.picks["axis"]:
            return []
        edges = self.edges("profile")
        if not edges:
            return []
        try:
            point, axis = surface.axis_of_ref(self.picks["axis"][0])
        except Exception:
            return []
        centre, _size = _centre(edges)
        far = max(edges, key=lambda e: _radial(e, point, axis))
        outer = far.valueAt((far.FirstParameter + far.LastParameter) / 2.0)
        r = (outer - point) - axis * (outer - point).dot(axis)
        if r.Length < 1e-6:
            return []
        center = point + axis * (centre - point).dot(axis)
        radius = r.Length
        zero = App.Vector(r)
        zero.normalize()
        size = self.handle_size(center + zero * radius)
        specs = []
        a1 = float(self.options["angle"])
        direction = self.options["direction"]
        specs.append(
            {
                "key": "angle",
                "type": "angle",
                "center": center,
                "axis": axis,
                "zero": zero,
                "radius": radius,
                "value": a1,
                "size": size,
            }
        )
        if direction == "two_sides":
            specs.append(
                {
                    "key": "angle2",
                    "type": "angle",
                    "center": center,
                    "axis": axis * -1.0,
                    "zero": zero,
                    "radius": radius,
                    "value": float(self.options["angle2"]),
                    "size": size,
                }
            )
        return specs

    def handle_value(self, key, raw):
        return round(max(-360.0, min(360.0, float(raw))), 3)


def _radial(edge, point, axis):
    try:
        p = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        r = (p - point) - axis * (p - point).dot(axis)
        return r.Length
    except Exception:
        return 0.0


# -- CREATE: Sweep --------------------------------------------------------------------------------
class SweepPanel(SurfacePanel):
    kind = "sweep"
    boxes = (
        ("profile", "Profile", "refs", ("curve", "sketch"), "Select curves"),
        ("path", "Path", "refs2", ("curve", "sketch"), "Select the path"),
        ("rail", "Guide Rail", "refs3", ("curve", "sketch"), "Select the guide rail"),
        ("guide", "Guide Surface", "refs3", ("face",), "Select faces"),
    )
    chain_boxes = ("profile", "path", "rail", "guide")
    tangent_boxes = ("path", "rail", "edges")

    def load_extra(self, feature, refs, options):
        found = list(refs.get("refs3") or [])
        self.picks["guide"] = [r for r in found if r[1].startswith("Face")]
        self.picks["rail"] = [r for r in found if not r[1].startswith("Face")]

    def build_rows(self):
        self.add_combo("type", "Type", _pairs(core.SWEEP_LABELS, core.SWEEP_TYPES))
        self.box("profile")
        self.box("path")
        self.box("rail")
        self.box("guide")
        self.chain_row()
        self.add_combo("rail_extent", "Extent", _pairs(core.RAIL_EXTENT_LABELS, core.RAIL_EXTENTS))
        self.add_ratio("distance", "Distance")
        self.add_ratio("distance2", "Distance Two")
        self.add_ratio("rail_distance", "Guide Rail Distance")
        self.add_combo(
            "orientation",
            "Orientation",
            [("Perpendicular", "perpendicular"), ("Parallel", "parallel")],
        )
        self.add_combo("scaling", "Profile Scaling", _pairs(core.SCALING_LABELS, core.SCALINGS))
        self.add_number("taper", "Taper Angle", "deg")
        self.add_number("twist", "Twist Angle", "deg")
        self.add_operation()

    def update_visibility(self):
        rail = self.options.get("type") == "rail"
        guided = self.options.get("type") == "surface"
        single = not rail and not guided
        self.show_box("rail", rail)
        self.show_box("guide", guided)
        self.show_option("scaling", rail)
        self.show_option("rail_extent", rail)
        self.show_option("rail_distance", rail)
        self.show_option("orientation", single)
        self.show_option("taper", single)
        self.show_option("twist", single)
        self.show_option("distance2", self._two_sides())
        perpendicular = self.options["orientation"] == "perpendicular"
        for key in ("twist", "taper"):
            row = self.rows.get(key)
            if row is not None:
                row[0].setEnabled(perpendicular)
                row[0].setToolTip(
                    "" if perpendicular else "Twist and taper need Orientation Perpendicular"
                )
        if (self.active == "rail" and not rail) or (self.active == "guide" and not guided):
            self.activate("profile")

    def _two_sides(self):
        try:
            from . import surface_geom as g

            path = curves.Path(self.edges("path"))
            wires = g.wires_of(self.edges("profile"))
            if not wires or path.closed:
                return False
            centre = g.bound_box(wires).Center
            import Part

            point = path.wire().distToShape(Part.Vertex(centre))[1][0][0]
            s = path.length_at(point)
            return 1e-6 < s < path.length - 1e-6
        except Exception:
            return False

    def option_changed(self, key):
        if key != "type" or not (self.picks["profile"] and self.picks["path"]):
            return
        if self.options["type"] == "rail" and not self.picks["rail"]:
            self.activate("rail")
        elif self.options["type"] == "surface" and not self.picks["guide"]:
            self.activate("guide")

    def refs(self):
        refs = super().refs()
        kind = self.options.get("type")
        if kind == "rail":
            refs["refs3"] = list(self.picks.get("rail") or [])
        elif kind == "surface":
            refs["refs3"] = list(self.picks.get("guide") or [])
        else:
            refs["refs3"] = []
        return refs

    def picks_changed(self, name):
        super().picks_changed(name)
        self.update_visibility()

    def after_pick(self, name):
        if name == "profile" and self.picks["profile"] and not self.picks["path"]:
            self.activate("path")
        elif name == "path" and self.picks["path"] and self.options.get("type") == "rail":
            if not self.picks["rail"]:
                self.activate("rail")
        elif name == "path" and self.picks["path"] and self.options.get("type") == "surface":
            if not self.picks["guide"]:
                self.activate("guide")


# -- CREATE: Loft ----------------------------------------------------------------------------------
END_ROWS = (("start", "First Profile"), ("end", "Last Profile"))


class LoftPanel(SurfacePanel):
    kind = "loft"
    boxes = (
        ("sections", "Profiles", "refs", ("curve", "point", "sketch"), "Select profiles"),
        ("rails", "Rails", "refs2", ("curve", "sketch"), "Select rails"),
        ("centerline", "Centerline", "refs3", ("curve", "sketch"), "Select a centerline"),
    )
    chain_boxes = ("sections", "rails", "centerline")
    tangent_boxes = ("rails", "centerline")

    def __init__(self, doc, feature=None):
        self.groups = []  # [[(obj, sub)...] one per profile, in loft order]
        self.end_kinds = {}
        super().__init__(doc, feature)

    def load_extra(self, feature, refs, options):
        self.groups = surface.loft_groups(refs.get("refs") or [], options.get("groups"))

    def build_rows(self):
        self.box("sections")
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeSurface_profiles")
        self.list.setMaximumHeight(110)
        self.layout.addRow(self.list)
        buttons = QtWidgets.QHBoxLayout()
        for text, step in (("Up", -1), ("Down", 1)):
            b = QtWidgets.QPushButton(text)
            b.setObjectName("SciForgeSurface_profile_" + text.lower())
            b.clicked.connect(lambda *_, s=step: self._guarded(lambda: self._move(s)))
            buttons.addWidget(b)
        remove = QtWidgets.QPushButton("Remove")
        remove.setObjectName("SciForgeSurface_profile_remove")
        remove.clicked.connect(lambda *_: self._guarded(self._remove_selected))
        buttons.addWidget(remove)
        holder = QtWidgets.QWidget()
        holder.setLayout(buttons)
        self.layout.addRow(holder)
        self.add_combo("guide", "Guide Type", [("Rails", "rails"), ("Centerline", "centerline")])
        self.box("rails")
        self.box("centerline")
        self.chain_row()
        self.add_check("closed", "Closed", "The last profile lofts back to the first")
        self.add_check(
            "merge",
            "Tangent Edges Merge",
            "Profile curves joined smoothly loft into one side face (off: one face per curve)",
        )
        for end, title in END_ROWS:
            self.add_combo(end + "_condition", title, loft_ends_labels("sketch"))
            self.add_number(end + "_weight", "Takeoff Weight", "")
            self.add_number(end + "_angle", "Takeoff Angle", "deg")
        why = (
            "Not in SciForge yet: OpenCASCADE's loft gives no control of the side curves' "
            "direction at a profile's ends, so the sides leave the edge freely"
        )
        self.add_combo(
            "edge_alignment",
            "Edge Alignment",
            [
                ("Free Edges", "free"),
                ("Align Edges", "align", False, why),
                ("Align to Surface", "surface", False, why),
            ],
        )
        self.add_operation()

    def _flat(self):
        return [p for g in self.groups for p in g]

    def show_picks(self):
        self.picks["sections"] = self._flat()
        super().show_picks()
        try:
            self.list.clear()
            for i, group in enumerate(self.groups, 1):
                obj, sub = group[0]
                what = "point" if sub.startswith("Vertex") else "%d curves" % len(group)
                if len(group) == 1 and not sub.startswith("Vertex"):
                    what = "1 curve"
                self.list.addItem("Profile %d: %s (%s)" % (i, obj.Label, what))
        except Exception:
            pass
        self.fields["sections"].set_text(
            core.count_label(len(self.groups), "profile") if self.groups else ""
        )

    def take(self, name, ref):
        if name != "sections":
            super().take(name, ref)
            return
        self.message.setText("")
        group = self.expand(name, ref)
        key = (ref[0].Name, ref[1])
        for i, existing in enumerate(self.groups):
            if key in {(o.Name, s) for o, s in existing}:
                del self.groups[i]
                break
        else:
            self.groups.append(group)
        self.picks_changed(name)

    def expand(self, name, ref):
        """Chain Selection on an edge of a body takes the edges joined smoothly to it (a
        cylinder's rim, not the four sides of a wall); sketch curves chain as connected."""
        obj, sub = ref
        if (
            name == "sections"
            and sub.startswith("Edge")
            and not curves.is_sketch(obj)
            and self.chain_on()
        ):
            try:
                names = free_chain(obj, sub, tangent=True)
                if names is None:
                    names = curves.chain(obj, sub, tangent=True)
                return [(obj, n) for n in names]
            except Exception as exc:
                warn("%s chain: %s" % (self.title, exc))
                return [ref]
        return super().expand(name, ref)

    def cleared(self, name):
        if name == "sections":
            self.groups = []
        super().cleared(name)

    def picks_changed(self, name):
        super().picks_changed(name)
        self.update_visibility()

    def _move(self, step):
        row = self.list.currentRow()
        other = row + step
        if row < 0 or not 0 <= other < len(self.groups):
            return
        self.groups[row], self.groups[other] = self.groups[other], self.groups[row]
        self.picks_changed("sections")
        self.list.setCurrentRow(other)

    def _remove_selected(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.groups):
            del self.groups[row]
            self.picks_changed("sections")

    def missing(self):
        if len(self.groups) < 2:
            return "Select at least two profiles, in loft order."
        return ""

    def refs(self):
        rails = self.options.get("guide", "rails") == "rails"
        return {
            "refs": self._flat(),
            "refs2": list(self.picks.get("rails") or []) if rails else [],
            "refs3": [] if rails else list(self.picks.get("centerline") or []),
        }

    def build_options(self):
        options = super().build_options()
        options["groups"] = [len(g) for g in self.groups]
        if options.get("closed"):
            options["end_condition"] = "free"  # the loop goes on from the last profile
        return options

    # -- what the boxes and rows show ---------------------------------------------------------
    def _group_kind(self, group):
        """point / sketch / edge: what a profile is (which end conditions it offers)."""
        if not group:
            return None
        obj, sub = group[0]
        if sub.startswith("Vertex") or obj.TypeId in surface.POINT_TYPES:
            return "point"
        if all(curves.is_sketch(o) for o, _s in group):
            return "sketch"
        return "edge"

    def update_visibility(self):
        rails = self.options.get("guide", "rails") == "rails"
        self.show_box("rails", rails)
        self.show_box("centerline", not rails)
        if self.active in ("rails", "centerline") and self.active != (
            "rails" if rails else "centerline"
        ):
            self.activate("sections")
        closed = bool(self.options.get("closed"))
        for end, _title in END_ROWS:
            group = None
            if len(self.groups) >= 2:
                group = self.groups[0] if end == "start" else self.groups[-1]
            kind = self._group_kind(group)
            shown = kind is not None and not (closed and end == "end")
            # Every choice of the profile stays offered (a closed loft refuses the ones it
            # cannot take, with the reason): ticking Closed and back keeps what was chosen.
            choices = loft_ends_labels(kind or "sketch")
            self._refill(end + "_condition", choices)
            condition = self.options.get(end + "_condition", "free")
            self.show_option(end + "_condition", shown)
            self.show_option(end + "_weight", shown and condition != "free")
            self.show_option(end + "_angle", shown and condition == "direction")
            caption = self.rows[end + "_weight"][1]
            caption.setText("Takeoff Weight" if condition == "direction" else "Tangency Weight")
        # Fusion: with a tangent or curvature end on an edge of a body
        smooth = any(
            self.options.get(end + "_condition", "free") in ("tangent", "curvature")
            for end, _title in END_ROWS
        )
        self.show_option("edge_alignment", smooth)

    def _refill(self, key, choices):
        box = self.rows[key][0]
        wanted = [value for _label, value in choices]
        current = [box.itemData(i) for i in range(box.count())]
        condition = self.options.get(key, "free")
        if condition not in wanted:
            condition = "free"
            self.options[key] = "free"
        self._quiet = True
        try:
            if current != wanted:
                box.clear()
                for label, value in choices:
                    box.addItem(label, value)
            curve_pick.set_combo(box, condition)
        finally:
            self._quiet = False

    def option_changed(self, key):
        if key == "guide":
            self.activate("rails" if self.options["guide"] == "rails" else "centerline")


def loft_ends_labels(kind):
    from . import loft_ends_core

    return list(loft_ends_core.LABELS["face" if kind == "edge" else kind])


# -- CREATE: Patch ---------------------------------------------------------------------------------
class PatchPanel(SurfacePanel):
    kind = "patch"
    boxes = (
        ("boundary", "Boundary Edges", "refs", ("curve", "sketch"), "Select edges"),
        ("interior", "Interior Rails / Points", "refs2", ("curve", "point"), "Select"),
    )
    chain_boxes = ("boundary",)
    chain_label = "Enable Chaining"

    def build_rows(self):
        self.box("boundary")
        self.chain_row()
        self.add_check(
            "group_edges",
            "Group Edges",
            "On: one Continuity for every edge. Off: a Continuity for each edge",
        )
        self.add_combo(
            "continuity",
            "Continuity",
            [("Connected", "connected"), ("Tangent", "tangent"), ("Curvature", "curvature")],
        )
        self.edge_rows = QtWidgets.QWidget()
        self.edge_rows.setObjectName("SciForgeSurface_edge_rows")
        self.edge_form = QtWidgets.QFormLayout(self.edge_rows)
        self.edge_form.setContentsMargins(0, 0, 0, 0)
        caption = QtWidgets.QLabel("Edge Continuity")
        self.layout.addRow(caption, self.edge_rows)
        self.rows["edge_rows"] = (self.edge_rows, caption)
        self.edge_combos = []
        weight = self.add_number("weight", "Tangency Weight", "")
        weight.widget.setEnabled(False)
        weight.widget.setToolTip(
            "OpenCASCADE's patch has no tangency weight (its plate surface only matches the "
            "faces' direction), so the weight cannot change the shape in SciForge."
        )
        self.add_check("reverse", "Reverse Normal", "The patch faces the other way")
        flip = QtWidgets.QPushButton("Flip")
        flip.setObjectName("SciForgeSurface_flip")
        flip.setToolTip("Turn the patch over (Reverse Normal)")
        flip.clicked.connect(lambda *_: self._guarded(self._flip))
        self.layout.addRow(QtWidgets.QLabel(""), flip)
        self.rows["flip"] = (flip, None)
        self.box("interior")
        self.add_operation()
        self._refill_edges()

    def _flip(self):
        box = self.rows["reverse"][0]
        box.setChecked(not box.isChecked())  # its toggled signal updates the patch

    def per_edge(self):
        """Each boundary pick's continuity (Group Edges off), as long as the picks."""
        picks = self.picks.get("boundary") or []
        stored = list(self.options.get("edge_continuity") or [])
        group = self.options.get("continuity", "connected")
        return [stored[i] if i < len(stored) else group for i in range(len(picks))]

    def _refill_edges(self):
        while self.edge_form.rowCount():
            self.edge_form.removeRow(0)
        self.edge_combos = []
        pairs = _pairs(core.CONTINUITY_LABELS, ("connected", "tangent", "curvature"))
        values = self.per_edge()
        self.options["edge_continuity"] = values
        for index, (obj, sub) in enumerate(self.picks.get("boundary") or []):
            box = curve_pick.combo(pairs, values[index])
            box.setObjectName("SciForgeSurface_edge_%d" % (index + 1))
            box.currentIndexChanged.connect(
                lambda *_a, i=index: self._guarded(lambda: self._edge_chosen(i))
            )
            noun = "Curve" if curves.is_sketch(obj) else "Edge"
            self.edge_form.addRow(QtWidgets.QLabel("%s %d" % (noun, index + 1)), box)
            self.edge_combos.append(box)

    def _edge_chosen(self, index):
        values = self.per_edge()
        values[index] = self.edge_combos[index].currentData()
        self.options["edge_continuity"] = values
        self.changed()

    def option_changed(self, key):
        if key == "group_edges" and not self.options["group_edges"]:
            self.options["edge_continuity"] = [self.options["continuity"]] * len(
                self.picks.get("boundary") or []
            )
            self._refill_edges()

    def update_visibility(self):
        group = bool(self.options.get("group_edges", True))
        self.show_option("continuity", group)
        self.show_option("edge_rows", not group)

    def picks_changed(self, name):
        super().picks_changed(name)
        if name == "boundary":
            self._refill_edges()

    def build_options(self):
        options = super().build_options()
        options["edge_continuity"] = self.per_edge()
        return options

    def missing(self):
        if not self.picks.get("boundary"):
            return "Select the boundary edges (a closed loop)."
        return ""


# -- CREATE: Ruled ---------------------------------------------------------------------------------
class RuledPanel(SurfacePanel):
    kind = "ruled"
    boxes = (
        ("edges", "Edges", "refs", ("curve", "sketch"), "Select edges"),
        ("direction", "Direction", "refs2", ("axis", "plane"), "Select a direction"),
    )
    single = ("direction",)
    chain_boxes = ("edges",)
    default_box = "distance"

    def build_rows(self):
        self.box("edges")
        self.chain_row()
        self.add_combo(
            "ruled_type",
            "Ruled Type",
            [("Tangent", "tangent"), ("Normal", "normal"), ("Direction", "direction")],
        )
        self.box("direction")
        self.add_number("distance", "Distance")
        self.add_number("angle", "Angle", "deg")
        self.add_check("alternate", "Alternate Faces", "Rule from the edge's other face")
        self.options["corner_type"] = "mitered" if self.options.get("mitered") else "rounded"
        self.add_combo(
            "corner_type", "Corner Type", [("Rounded", "rounded"), ("Mitered", "mitered")]
        )
        self.rows["corner_type"][0].setToolTip(
            "How the bands of two picked edges meet round an outside corner"
        )
        self.add_operation()

    def update_visibility(self):
        self.show_box("direction", self.options["ruled_type"] == "direction")

    def build_options(self):
        options = super().build_options()
        options["mitered"] = options.pop("corner_type", "rounded") == "mitered"
        return options

    def option_changed(self, key):
        if key == "corner_type":
            self.options["mitered"] = self.options["corner_type"] == "mitered"
        if key == "ruled_type" and self.options["ruled_type"] == "direction":
            self.activate("direction")

    def box_activated(self, name):
        self.show_axis_lines(name == "direction")

    def handle_specs(self):
        picks = self.picks.get("edges") or []
        if not picks:
            return []
        try:
            edge = surface.edges_of(picks[:1])[0]
        except Exception:
            return []
        u = (edge.FirstParameter + edge.LastParameter) / 2.0
        mid = edge.valueAt(u)
        direction = self._ruling(picks[0], mid, u, edge)
        if direction is None:
            return []
        return [
            {
                "key": "distance",
                "type": "arrow",
                "origin": mid,
                "dir": direction,
                "value": float(self.options["distance"]),
                "size": self.handle_size(mid),
            }
        ]

    def _ruling(self, ref, mid, u, edge):
        from . import surface_geom as g

        o = self.options
        try:
            obj, sub = ref
            t = g.unit(edge.tangentAt(u))
            if curves.is_sketch(obj):
                n = obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
                away = g.unit(n.cross(t))
            else:
                _e, faces, _s = surface._edge_faces(obj, sub)
                if not faces:
                    return None
                face = faces[1] if o.get("alternate") and len(faces) > 1 else faces[0]
                n = g.face_normal_at(face, mid)
                away = g.away_in_face(face, edge, mid, t)
            direction = None
            if o["ruled_type"] == "direction":
                if not self.picks.get("direction"):
                    return None
                direction = tuple(surface.direction_of_ref(self.picks["direction"][0]))
            out = core.ruling_direction(
                o["ruled_type"], tuple(n), tuple(away), o["angle"], direction
            )
            return App.Vector(*out)
        except Exception:
            return None


# -- CREATE: Offset --------------------------------------------------------------------------------
class OffsetPanel(SurfacePanel):
    kind = "offset"
    boxes = (("faces", "Faces", "refs", ("face",), "Select faces"),)
    chain_boxes = ("faces",)
    default_box = "distance"

    def build_rows(self):
        self.box("faces")
        self.chain_row()
        self.add_combo("offset_type", "Offset Type", _pairs(core.OFFSET_LABELS, core.OFFSET_TYPES))
        self.rows["offset_type"][0].setToolTip(
            "Sharp: the offset faces meet in sharp edges. Rounded: their outside corners "
            "are rounded with the distance as radius"
        )
        self.add_number("distance", "Distance")
        self.add_operation()

    def handle_specs(self):
        faces = self.faces("faces")
        if not faces:
            return []
        from . import surface_geom as g

        face = max(faces, key=lambda f: f.Area)
        p = g.face_point(face)
        n = g.face_normal_at(face, p)
        return [
            {
                "key": "distance",
                "type": "arrow",
                "origin": p,
                "dir": n,
                "value": float(self.options["distance"]),
                "size": self.handle_size(p),
            }
        ]


# -- CREATE: Thicken -------------------------------------------------------------------------------
class ThickenPanel(SurfacePanel):
    kind = "thicken"
    boxes = (("faces", "Faces", "refs", ("face",), "Select faces"),)
    chain_boxes = ("faces",)
    default_box = "thickness"

    def build_rows(self):
        self.box("faces")
        self.chain_row()
        self.add_number("thickness", "Thickness")
        self.add_combo(
            "direction", "Direction", [("One Side", "one_side"), ("Symmetric", "symmetric")]
        )
        self.add_combo("thicken_type", "Thicken Type", [("Sharp", "sharp"), ("Rounded", "rounded")])
        self.add_operation()

    def build_options(self):
        options = super().build_options()
        if core.is_solid_operation(options.get("operation")):
            options["target"] = self.solid_target()
        return options

    def solid_target(self):
        """The solid body a Join / Cut / Intersect acts on: the body the faces belong to when
        it is a solid, else the first solid body the thickened shape touches."""
        for obj, _sub in self.picks.get("faces") or []:
            body = bodies.body_of(obj)
            if body is not None and bodies.has_solid(body) and not self._is_mine(body):
                return body
        try:
            from . import surface_geom as g

            o = self.options
            solid = g.thicken(
                self.faces("faces"), o["thickness"], o["direction"], o["thicken_type"]
            )
        except Exception:
            return None
        for body in bodies.solid_bodies(self.doc, visible_only=True):
            if self._is_mine(body):
                continue
            try:
                if body.Shape.distToShape(solid)[0] < 1e-6:
                    return body
            except Exception:
                pass
        return None

    def _is_mine(self, body):
        return (
            self.step is not None
            and _alive(self.step)
            and bodies.body_of(self.step) is body
            and (surface.created_body(self.step) is body)
        )

    def handle_specs(self):
        faces = self.faces("faces")
        if not faces:
            return []
        from . import surface_geom as g

        face = max(faces, key=lambda f: f.Area)
        p = g.face_point(face)
        n = g.face_normal_at(face, p)
        t = float(self.options["thickness"])
        value = t / 2.0 if self.options["direction"] == "symmetric" else t
        return [
            {
                "key": "thickness",
                "type": "arrow",
                "origin": p,
                "dir": n,
                "value": value,
                "size": self.handle_size(p),
            }
        ]

    def handle_value(self, key, raw):
        value = float(raw)
        if self.options["direction"] == "symmetric":
            value *= 2.0
        return round(value, 4)


# -- MODIFY: Untrim --------------------------------------------------------------------------------
class UntrimPanel(SurfacePanel):
    kind = "untrim"
    boxes = (
        ("faces", "Faces", "refs", ("face",), "Select faces"),
        ("loops", "Loops", "refs", ("free_edge",), "Select loops"),
    )

    def load_extra(self, feature, refs, options):
        found = list(refs.get("refs") or [])
        self.picks["faces"] = [r for r in found if not r[1].startswith("Edge")]
        self.picks["loops"] = [r for r in found if r[1].startswith("Edge")]

    def build_rows(self):
        self.box("faces")
        self.box("loops")
        self.add_combo("loop_type", "Type", _pairs(core.LOOP_LABELS, core.LOOP_TYPES))
        self.rows["loop_type"][0].setToolTip(
            "Manual: click an edge of each loop to remove (a hole or the outer boundary)"
        )
        self.add_check("extend", "Extend", "Push the untrimmed outer boundary out")
        self.add_number("distance", "Extend Distance")
        self.add_check("keep_copy", "Keep Copy", "Keep the surface as it was, as a body of its own")

    def pick_text(self, name):
        if name == "loops":
            return core.count_label(len(self.picks.get("loops") or []), "loop")
        return super().pick_text(name)

    def update_visibility(self):
        manual = self.options["loop_type"] == "manual"
        self.show_box("faces", not manual)
        self.show_box("loops", manual)
        self.show_option("extend", self.options["loop_type"] != "internal")
        self.show_option(
            "distance", self.options["loop_type"] != "internal" and bool(self.options["extend"])
        )
        if self.active is not None and not self.is_shown(self.active):
            self.activate("loops" if manual else "faces")

    def option_changed(self, key):
        if key == "loop_type":
            self.activate("loops" if self.options["loop_type"] == "manual" else "faces")

    def refs(self):
        refs = super().refs()
        manual = self.options["loop_type"] == "manual"
        refs["refs"] = list(self.picks.get("loops" if manual else "faces") or [])
        return refs


# -- MODIFY: Extend --------------------------------------------------------------------------------
class ExtendPanel(SurfacePanel):
    kind = "extend"
    boxes = (("edges", "Edges", "refs", ("free_edge",), "Select edges"),)
    chain_boxes = ("edges",)
    chain_label = "Enable Chaining"
    default_box = "distance"

    def build_rows(self):
        self.box("edges")
        self.chain_row()
        self.add_number("distance", "Distance")
        self.add_combo(
            "extend_type",
            "Extend Type",
            [("Natural", "natural"), ("Perpendicular", "perpendicular"), ("Tangent", "tangent")],
        )
        self.add_combo(
            "alignment",
            "Edge Alignment",
            [
                ("Free Edges", "free"),
                (
                    "Align Edges",
                    "align",
                    False,
                    "Not in SciForge yet: the extension follows the face's own surface, or "
                    "carries it on tangent where it cannot",
                ),
            ],
        )

    def update_visibility(self):
        self.show_option("alignment", self.options["extend_type"] == "natural")

    def handle_specs(self):
        picks = self.picks.get("edges") or []
        if not picks:
            return []
        from . import surface_geom as g

        try:
            obj, sub = picks[0]
            edge, faces, _shape = surface._edge_faces(obj, sub)
            if not faces:
                return []
            u = (edge.FirstParameter + edge.LastParameter) / 2.0
            mid = edge.valueAt(u)
            t = g.unit(edge.tangentAt(u))
            if self.options["extend_type"] == "perpendicular":
                direction = g.face_normal_at(faces[0], mid)
            else:
                direction = g.away_in_face(faces[0], edge, mid, t)
        except Exception:
            return []
        return [
            {
                "key": "distance",
                "type": "arrow",
                "origin": mid,
                "dir": direction,
                "value": float(self.options["distance"]),
                "size": self.handle_size(mid),
            }
        ]


# -- MODIFY: Stitch --------------------------------------------------------------------------------
class StitchPanel(SurfacePanel):
    kind = "stitch"
    boxes = (("bodies", "Stitched Surfaces", "refs", ("body",), "Select bodies"),)

    def build_rows(self):
        self.box("bodies")
        self.add_number("tolerance", "Tolerance")
        self.open_label = QtWidgets.QLabel("")
        self.open_label.setWordWrap(True)
        self.open_label.setObjectName("SciForgeSurface_open_edges")
        self.layout.addRow(self.open_label)
        self.stitched = []  # the open edges the stitch closes (drawn green)
        self.add_operation()

    def missing(self):
        if len(self.picks.get("bodies") or []) < 2:
            return "Select the surface bodies to stitch (two or more)."
        return ""

    def build_options(self):
        options = super().build_options()
        if core.is_solid_operation(options.get("operation")):
            options["target"] = self.solid_target()
        return options

    def solid_target(self):
        """Join / Cut / Intersect: the solid body the closed stitch touches (the one this
        step already acts on while editing)."""
        from . import surface_geom as g

        picked = [b for b, _s in self.picks.get("bodies") or []]
        if self.step is not None and _alive(self.step):
            own = bodies.body_of(self.step)
            if own is not None and own not in picked and bodies.has_solid(own):
                if surface.created_body(self.step) is None:
                    return own
        self.closes = False
        host = None
        if self.step is not None and _alive(self.step):
            host = bodies.body_of(self.step)
        try:
            shapes = []
            for body in picked:
                if not _alive(body):
                    continue
                base = getattr(self.step, "BaseFeature", None) if body is host else None
                # the body this preview sits in, as it was before it (not the preview)
                shapes.append(
                    bodies.global_shape(base) if base is not None else surface.whole_shape(body)
                )
            stitched, _open = g.stitch(shapes, float(self.options["tolerance"]))
        except Exception:
            return None
        if not stitched.Solids:
            return None
        self.closes = True
        for body in bodies.solid_bodies(self.doc, visible_only=True):
            if body in picked:
                continue
            try:
                if body.Shape.distToShape(stitched)[0] < 1e-6:
                    return body
            except Exception:
                pass
        return None

    def check(self, options):
        operation = options.get("operation")
        if core.is_solid_operation(operation) and options.get("target") is None:
            word = core.OPERATION_LABELS[operation]
            if not getattr(self, "closes", False):
                raise core.SurfaceError(
                    "The surfaces do not close into a solid, so the stitch cannot %s. Close the "
                    "gaps (a bigger Tolerance or more surfaces), or use New Body." % word
                )
            raise core.SurfaceError(
                "No solid body touches the closed stitch, so there is nothing to %s it with. "
                "Use New Body, or move it onto a solid." % word
            )
        for obj, _sub in self.picks.get("bodies") or []:
            if bodies.has_solid(obj) and not self._mine(obj):
                raise core.SurfaceError(
                    "%s is a solid: Stitch joins surface bodies. Unstitch it first, or pick "
                    "surfaces." % obj.Label
                )

    def _mine(self, body):
        return self.step is not None and _alive(self.step) and bodies.body_of(self.step) is body

    def interpret(self, name, obj, short, point):
        # The preview draws the stitched surfaces as the first body: a click on a face that
        # came from another picked body means that body (clicking it again drops it).
        if self._mine(bodies.body_of(obj)) and point is not None:
            found = self._source_body(point)
            if found is not None:
                return (found, "")
        ref = super().interpret(name, obj, short, point)
        if ref is not None and self._mine(ref[0]) and bodies.has_solid(ref[0]):
            if core.is_solid_operation(self.options.get("operation")):
                self.message.setText("⚠ That is the solid the stitch acts on. Pick a surface.")
                return None
        if ref is not None and bodies.has_solid(ref[0]) and not self._mine(ref[0]):
            # Fusion's Stitch selects surface bodies only
            self.message.setText(
                "⚠ %s is a solid: Stitch joins surface bodies. Unstitch it first, or pick "
                "surfaces." % ref[0].Label
            )
            return None
        return ref

    def _source_body(self, point):
        import Part

        own = bodies.body_of(self.step)
        try:
            vertex = Part.Vertex(App.Vector(point))
        except Exception:
            return None
        best = None
        for body, _sub in self.picks.get("bodies") or []:
            if body is own or not _alive(body):
                continue
            try:
                shape = surface.whole_shape(body)
                d = shape.distToShape(vertex)[0]
            except Exception:
                continue
            tol = max(1e-4, 1e-4 * shape.BoundBox.DiagonalLength)
            if d <= tol and (best is None or d < best[1]):
                best = (body, d)
        return best[0] if best is not None else None

    def after_recompute(self):
        super().after_recompute()
        try:
            self._show_open_edges()
        except Exception as exc:
            warn("stitch open edges: %s" % exc)

    def _show_open_edges(self):
        from . import surface_geom as g

        step = self.step if self.step is not None and _alive(self.step) else None
        if step is None or step.Shape.isNull() or "Invalid" in step.State:
            self.open_label.setText("")
            self.stitched = []
            if self.overlay is not None:
                self.overlay.clear("open")
                self.overlay.clear("stitched")
            return
        shape = bodies.global_shape(step)
        free = g.free_edges(shape)
        # Fusion draws the edges the stitch closes green and the ones left open red
        self.stitched = self._stitched_edges(step, shape)
        if shape.Solids:
            self.open_label.setText(
                "Closed: the stitched surfaces make a solid body (stitched edges drawn green)."
            )
            self.open_label.setStyleSheet("color: #7fd38f;")
        else:
            self.open_label.setText(
                "%s left open (drawn red), the stitched ones drawn green. Raise the tolerance "
                "to close gaps up to it." % core.count_label(len(free), "edge")
            )
            self.open_label.setStyleSheet("color: #ff8a80;")
        if self.overlay is not None:
            self.overlay.show("open", [g.compound(free)] if free else [], RED, 0.0, 4.0)
            stitched = [g.compound(self.stitched)] if self.stitched else []
            self.overlay.show("stitched", stitched, GREEN, 0.0, 4.0)

    def _stitched_edges(self, step, shape):
        """The open edges of the picked surfaces that the stitch closed."""
        from . import surface_geom as g

        try:
            own = bodies.body_of(step)
            inputs = [surface._base(step)]
            for body, _sub in self.picks.get("bodies") or []:
                if body is not own and _alive(body):
                    inputs.append(surface.whole_shape(body))
            return g.stitched_edges(inputs, shape)
        except Exception as exc:
            warn("stitch stitched edges: %s" % exc)
            return []


# -- MODIFY: Unstitch ------------------------------------------------------------------------------
class UnstitchPanel(SurfacePanel):
    kind = "unstitch"
    boxes = (("faces", "Faces/Bodies", "refs", ("face",), "Select faces"),)
    chain_boxes = ("faces",)

    def build_rows(self):
        self.box("faces")
        self.chain_row()

    def expand(self, name, ref):
        obj, sub = ref
        if sub.startswith("Face") and self.chain_on():
            # Fusion's chain takes every face joined to the clicked one (the whole surface)
            try:
                shape = obj.Shape
                names = []
                import Part

                faces = list(shape.Faces)
                start = int(sub[4:]) - 1
                taken = {start}
                todo = [start]
                while todo:
                    i = todo.pop()
                    for edge in faces[i].Edges:
                        for other in shape.ancestorsOfType(edge, Part.Face):
                            j = next((k for k, f in enumerate(faces) if f.isSame(other)), None)
                            if j is not None and j not in taken:
                                taken.add(j)
                                todo.append(j)
                names = ["Face%d" % (i + 1) for i in sorted(taken)]
                return [(obj, n) for n in names]
            except Exception:
                return [ref]
        return [ref]


# -- MODIFY: Reverse Normal ------------------------------------------------------------------------
class ReverseNormalPanel(SurfacePanel):
    kind = "reverse_normal"
    boxes = (("bodies", "Surfaces", "bodies", ("body",), "Select surfaces"),)

    def build_rows(self):
        self.box("bodies")

    def interpret(self, name, obj, short, point):
        ref = super().interpret(name, obj, short, point)
        if ref is not None and bodies.has_solid(ref[0]) and not self._turned(ref[0]):
            # Fusion's Reverse Normal selects surface bodies only
            self.message.setText(
                "⚠ %s is a solid: a solid's faces always point out of it. Pick a surface "
                "body (in the browser when it lies on a solid's face)." % ref[0].Label
            )
            return None
        return ref

    def _turned(self, body):
        steps = [self.step] + surface.followers_of(self.step) if self.step is not None else []
        return any(_alive(x) and bodies.body_of(x) is body for x in steps)

    def after_recompute(self):
        super().after_recompute()
        try:
            self._show_normals()
        except Exception as exc:
            warn("reverse normal: %s" % exc)

    def _show_normals(self):
        """A short arrow on each surface's biggest face, pointing the way it faces now."""
        import Part

        from . import surface_geom as g

        if self.overlay is None:
            return
        arrows = []
        for body, _sub in self.picks.get("bodies") or []:
            try:
                shape = bodies.global_shape(body.Tip)
                face = max(shape.Faces, key=lambda f: f.Area)
                p = g.face_point(face)
                n = g.face_normal_at(face, p)
                size = self.handle_size(p) * 1.5
                arrows.append(Part.LineSegment(p, p + n * size).toShape())
            except Exception:
                continue
        self.overlay.show("normals", arrows, (0.95, 0.65, 0.2), 0.0, 3.0)


# -- MODIFY: Trim ----------------------------------------------------------------------------------
class TrimPanel(SurfacePanel):
    kind = "trim"
    boxes = (
        ("tool", "Trimming Tool", "refs", ("sketch_curve", "body", "plane"), "Select a tool"),
        ("cells", "Remove", "cells", (), "Click pieces to remove"),
    )
    single = ("tool",)

    def __init__(self, doc, feature=None):
        self.removed = []  # [[body name, [x, y, z]]]
        super().__init__(doc, feature)

    def load_extra(self, feature, refs, options):
        self.removed = [list(c) for c in options.get("cells") or []]

    def interpret(self, name, obj, short, point):
        sub = _short(short)
        if name == "tool" and sub.startswith("Face") and not curves.is_sketch(obj):
            body = bodies.body_of(obj)
            if (
                body is not None
                and obj.TypeId not in surface.CONSTRUCTION_TYPES
                and bodies.has_solid(body)
                and not self.own_preview(obj)
            ):
                return (obj, sub)  # a face of a solid: that face alone is the tool
        return super().interpret(name, obj, short, point)

    def build_rows(self):
        self.box("tool")
        self.box("cells")
        self.cells_note = QtWidgets.QLabel("")
        self.cells_note.setWordWrap(True)
        self.layout.addRow(self.cells_note)

    def missing(self):
        if not self.picks.get("tool"):
            return "Select the trimming tool: a surface, a plane, a sketch curve or a body."
        if not self.removed:
            return "Click the pieces to remove (they turn red)."
        return ""

    def required(self):
        return [b for b in self.boxes if b[0] == "tool"]

    def build_options(self):
        options = super().build_options()
        options["cells"] = [list(c) for c in self.removed]
        return options

    def refs(self):
        tool = list(self.picks.get("tool") or [])
        others = [(b, "") for b in self._candidates(tool)]
        return {"refs": tool, "refs2": others, "refs3": []}

    def show_picks(self):
        super().show_picks()
        field = self.fields.get("cells")
        if field is not None:
            field.set_text(core.count_label(len(self.removed), "piece"))

    def cleared(self, name):
        if name == "cells":
            self.removed = []
            self.show_picks()
            self._paint_cells()
            self.changed()
            return
        super().cleared(name)

    def after_pick(self, name):
        if name == "tool" and self.picks.get("tool"):
            self.activate("cells")

    def box_activated(self, name):
        self.show_plane_squares(name == "tool")

    def _tool_body(self, tool):
        if not tool:
            return None
        obj, sub = tool[0]
        if sub.startswith("Edge") or obj.TypeId in surface.PLANE_TYPES:
            return None
        return bodies.body_of(obj)

    def _base_of(self, body):
        """A body's surface before this Trim (its Trim step's base while previewing)."""
        for step in self.preview_steps():
            if bodies.body_of(step) is body:
                return step.BaseFeature
        return body.Tip

    def _candidates(self, tool):
        """The surface bodies the tool cuts (the tool's own body excluded)."""
        found = []
        tool_body = self._tool_body(tool)
        try:
            around = [bodies.global_shape(self._base_of(b)) for b in self._surfaces()]
            cutter = surface.tool_cutter(self._tool_link(tool), _union(around))
        except Exception:
            return found
        for body in self._surfaces():
            if body is tool_body:
                continue
            try:
                base = bodies.global_shape(self._base_of(body))
                if base.distToShape(cutter)[0] < 1e-6:
                    found.append(body)
            except Exception:
                continue
        return found

    def _tool_link(self, tool):
        obj, sub = tool[0]
        if bodies.is_body(obj):
            return (self._base_of(obj), "")
        return (obj, sub)

    def _surfaces(self):
        found = []
        for body in bodies.list_bodies(self.doc):
            if not bodies.is_shown(body) and not any(
                bodies.body_of(s) is body for s in self.preview_steps()
            ):
                continue
            base = self._base_of(body)
            if base is not None and surface.is_surface_shape(base.Shape):
                found.append(body)
        return found

    def refresh_cells(self):
        tool = self.picks.get("tool") or []
        if not tool:
            self.cell_data = []
            self.cells_key = None
            self._paint_cells()
            return
        key = (self._tool_link(tool)[0].Name, tool[0][1])
        bases = tuple(
            (b.Name, self._base_of(b).Name if self._base_of(b) else "") for b in self._surfaces()
        )
        if (key, bases) == self.cells_key:
            self._paint_cells()
            return
        self.cells_key = (key, bases)
        self.cell_data = self._compute_cells(tool)
        self._paint_cells()

    def _compute_cells(self, tool):
        from . import surface_geom as g

        cells = []
        candidates = self._candidates(tool)
        tool_body = self._tool_body(tool)
        shapes = {b.Name: bodies.global_shape(self._base_of(b)) for b in candidates}
        around = _union(list(shapes.values()))
        try:
            cutter = surface.tool_cutter(self._tool_link(tool), around)
        except Exception as exc:
            self.cells_note.setText("⚠ %s" % exc)
            return []
        for body in candidates:
            try:
                found = g.cells_for_trim(shapes[body.Name], cutter)
            except Exception as exc:
                warn("trim cells: %s" % exc)
                continue
            if len(found) > 1:  # a body the tool only touches has nothing to pick
                cells.extend(dict(cell, body=body.Name) for cell in found)
        if tool_body is not None and surface.is_surface_body(tool_body) and shapes:
            try:
                own = bodies.global_shape(self._base_of(tool_body))
                found = g.cells_for_trim(own, g.compound(list(shapes.values())))
                if len(found) > 1:
                    cells.extend(dict(cell, body=tool_body.Name) for cell in found)
            except Exception as exc:
                warn("trim cells: %s" % exc)
        if not cells:
            self.cells_note.setText(
                "⚠ The tool does not cut any surface into pieces. Pick a tool that crosses a "
                "surface body."
            )
        else:
            self.cells_note.setText("Click the pieces to remove; click a red one to keep it.")
        return cells

    def _paint_cells(self):
        if self.cells is None and self.cell_data:
            try:
                self.cells = CellPicker(self.view, self._cell_clicked, blocked=self._cells_off)
            except Exception as exc:
                warn("trim cells unavailable: %s" % exc)
                return
        if self.cells is None:
            return
        from . import surface_geom as g

        shapes = [g.compound(c["faces"]) for c in self.cell_data]
        states = ["removed" if self._is_removed(i) else "idle" for i in range(len(shapes))]
        self.cells.set_cells(shapes, states)

    def _cells_off(self, position):
        return self.active != "cells"

    def _owner(self, entry):
        """Index of the cell a removed entry names, or None."""
        from . import surface_geom as g

        name, point = entry
        best = None
        for i, cell in enumerate(self.cell_data):
            if cell["body"] != name:
                continue
            d = min(g.distance(f, point) for f in cell["faces"])
            if best is None or d < best[0]:
                best = (d, i)
        return best[1] if best is not None and best[0] < 1e-3 else None

    def _is_removed(self, index):
        return any(self._owner(e) == index for e in self.removed)

    def _cell_clicked(self, index):
        if self._closed or index is None or index >= len(self.cell_data):
            return
        cell = self.cell_data[index]
        kept = [e for e in self.removed if self._owner(e) != index]
        if len(kept) == len(self.removed):
            kept.append([cell["body"], [float(c) for c in cell["point"]]])
        self.removed = kept
        self.show_picks()
        self._paint_cells()
        self.changed()


def _union(shapes):
    from . import surface_geom as g

    return g.compound([s for s in shapes if s is not None and not s.isNull()])


# -- CREATE: Boundary Fill -------------------------------------------------------------------------
class BoundaryFillPanel(SurfacePanel):
    kind = "boundary_fill"
    boxes = (
        ("tools", "Tools", "refs", ("body", "plane"), "Select tools"),
        ("cells", "Cells", "cells", (), "Select cells"),
    )

    def __init__(self, doc, feature=None):
        self.chosen = []  # [[x, y, z]] points inside the chosen cells
        super().__init__(doc, feature)

    def load_extra(self, feature, refs, options):
        meta = bodies.load_meta(feature, surface.META)
        self.chosen = [list(p) for p in meta.get("cells") or []]

    def build_rows(self):
        self.box("tools")
        self.box("cells")
        self.list = QtWidgets.QListWidget()
        self.list.setObjectName("SciForgeSurface_cells")
        self.list.setMaximumHeight(120)
        self.list.itemChanged.connect(lambda item: self._guarded(lambda: self._ticked(item)))
        self.layout.addRow(self.list)
        self.add_check("remove_tools", "Remove Tools", "The tool bodies are used up by the fill")
        self.add_operation()

    def missing(self):
        if not self.picks.get("tools"):
            return "Select the tools: bodies, surfaces and planes that close a space."
        if not self.chosen:
            return "Select the cells to fill (click them, or tick them in the list)."
        return ""

    def required(self):
        return [b for b in self.boxes if b[0] == "tools"]

    def build_options(self):
        options = super().build_options()
        options["cells"] = [list(p) for p in self.chosen]
        if core.is_solid_operation(options.get("operation")):
            options["target"] = self._solid_target()
        return options

    def _solid_target(self):
        for obj, _sub in self.picks.get("tools") or []:
            if bodies.is_body(obj) and bodies.has_solid(obj) and not self._mine(obj):
                return obj
        for body in bodies.solid_bodies(self.doc, visible_only=True):
            if not self._mine(body):
                return body
        return None

    def _mine(self, body):
        return (
            self.step is not None and _alive(self.step) and surface.created_body(self.step) is body
        )

    def box_activated(self, name):
        self.show_plane_squares(name == "tools")
        if self.cells is not None:
            self._paint_cells()

    def show_picks(self):
        super().show_picks()
        field = self.fields.get("cells")
        if field is not None:
            field.set_text(core.count_label(len(self.chosen), "cell"))

    def cleared(self, name):
        if name == "cells":
            self.chosen = []
            self.show_picks()
            self._paint_cells()
            self._fill_list()
            self.changed()
            return
        super().cleared(name)

    def _tool_refs(self):
        """The tools as the fill sees them: a body as it was before this step."""
        out = []
        for obj, sub in self.picks.get("tools") or []:
            if bodies.is_body(obj):
                base = obj.Tip
                for step in self.preview_steps():
                    if bodies.body_of(step) is obj:
                        base = step.BaseFeature
                if base is not None:
                    out.append((base, ""))
            else:
                out.append((obj, sub))
        return out

    def refresh_cells(self):
        tools = self.picks.get("tools") or []
        key = tuple((o.Name, s) for o, s in tools)
        if key == self.cells_key:
            self._paint_cells()
            return
        self.cells_key = key
        self.cell_data = []
        if tools:
            from . import surface_geom as g

            try:
                self.cell_data = g.boundary_cells(surface.tool_shapes(self._tool_refs()))
            except Exception as exc:
                self.message.setText("⚠ %s" % exc)
        # chosen cells that no longer exist are dropped
        self.chosen = [p for p in self.chosen if self._owner(p) is not None]
        self._fill_list()
        self._paint_cells()
        self.show_picks()

    def _fill_list(self):
        self.list.blockSignals(True)
        try:
            self.list.clear()
            for i, cell in enumerate(self.cell_data):
                item = QtWidgets.QListWidgetItem(core.cell_name(i, cell["size"], True))
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if self._is_chosen(i) else QtCore.Qt.Unchecked)
                self.list.addItem(item)
            if not self.cell_data and self.picks.get("tools"):
                self.list.addItem("No closed cell yet: add tools until a space is closed.")
        finally:
            self.list.blockSignals(False)

    def _owner(self, point):
        best = None
        for i, cell in enumerate(self.cell_data):
            solid = cell["solid"]
            try:
                if solid.isInside(App.Vector(*point), 1e-6, True):
                    return i
                d = solid.distToShape(__import__("Part").Vertex(App.Vector(*point)))[0]
            except Exception:
                continue
            if best is None or d < best[0]:
                best = (d, i)
        return best[1] if best is not None and best[0] < 1e-3 else None

    def _is_chosen(self, index):
        return any(self._owner(p) == index for p in self.chosen)

    def _toggle(self, index):
        point = self.cell_data[index]["point"]
        self.chosen = core.toggle_point(self.chosen, index, point, self._owner)
        self.show_picks()
        self._paint_cells()
        self._fill_list()
        self.changed()

    def _ticked(self, item):
        index = self.list.row(item)
        if 0 <= index < len(self.cell_data):
            want = item.checkState() == QtCore.Qt.Checked
            if want != self._is_chosen(index):
                self._toggle(index)

    def _cell_clicked(self, index):
        if self._closed or index is None or index >= len(self.cell_data):
            return
        self._toggle(index)

    def _paint_cells(self):
        if self.cells is None and self.cell_data:
            try:
                self.cells = CellPicker(self.view, self._cell_clicked, blocked=self._cells_off)
            except Exception as exc:
                warn("boundary fill cells unavailable: %s" % exc)
                return
        if self.cells is None:
            return
        shapes = [c["solid"] for c in self.cell_data]
        active = self.active == "cells"
        states = []
        for i in range(len(shapes)):
            if self._is_chosen(i):
                states.append("chosen")
            else:
                states.append("shown" if active else "idle")
        self.cells.set_cells(shapes, states)

    def _cells_off(self, position):
        return self.active != "cells"


# -- the view provider of surface steps ------------------------------------------------------------
class SurfaceViewProvider:
    """Saved in files as "sciforge.surface_ui.SurfaceViewProvider": keep the name."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        kind = surface.kind_of(getattr(self, "Object", None))
        try:
            return ui_icon_path(core.spec(kind)["icon"]) if kind else ui_icon_path("surface_body")
        except Exception:
            return ui_icon_path("surface_body")

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        _edit_later(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        _edit_later(vobj.Object)
        return True

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def _edit_later(obj):
    name, doc = obj.Name, obj.Document.Name

    def run():
        try:
            if doc not in App.listDocuments():
                return
            target = App.getDocument(doc).getObject(name)
            if target is not None:
                taskui.edit_object(target)
        except Exception as exc:
            warn("could not edit %s: %s" % (name, exc))

    QtCore.QTimer.singleShot(0, run)


# -- commands --------------------------------------------------------------------------------------
PANELS = {
    "extrude": ExtrudePanel,
    "revolve": RevolvePanel,
    "sweep": SweepPanel,
    "loft": LoftPanel,
    "patch": PatchPanel,
    "ruled": RuledPanel,
    "offset": OffsetPanel,
    "boundary_fill": BoundaryFillPanel,
    "thicken": ThickenPanel,
    "trim": TrimPanel,
    "untrim": UntrimPanel,
    "extend": ExtendPanel,
    "stitch": StitchPanel,
    "unstitch": UnstitchPanel,
    "reverse_normal": ReverseNormalPanel,
}

TIPS = {
    "extrude": "A surface from sketch curves (open or closed) pushed out: no caps, no solid",
    "revolve": "A surface from curves turned about an axis",
    "sweep": "A surface from curves carried along a path",
    "loft": "A surface through two or more curves, in order",
    "patch": "A surface filling a closed loop of edges or curves (Connected, Tangent, Curvature)",
    "ruled": "A band leaving edges at a distance and angle (Tangent, Normal, Direction)",
    "offset": "A new surface at a distance from faces",
    "boundary_fill": "A solid from the closed cells that bodies, surfaces and planes enclose",
    "thicken": "A solid from faces or a surface given a thickness",
    "trim": "Cut surfaces with a tool and remove the pieces you click",
    "untrim": "Remove holes or the outer boundary of a surface's faces",
    "extend": "Carry a surface on past its outside edges",
    "stitch": "Join surface bodies at their edges; a closed result becomes a solid",
    "unstitch": "Take faces out of a body, each a surface body of its own",
    "reverse_normal": "Turn a surface over (its normal points the other way)",
}

COMMAND_NAMES = {
    "extrude": "SciForge_SurfaceExtrude",
    "revolve": "SciForge_SurfaceRevolve",
    "sweep": "SciForge_SurfaceSweep",
    "loft": "SciForge_SurfaceLoft",
    "patch": "SciForge_Patch",
    "ruled": "SciForge_Ruled",
    "offset": "SciForge_SurfaceOffset",
    "boundary_fill": "SciForge_BoundaryFill",
    "thicken": "SciForge_Thicken",
    "trim": "SciForge_Trim",
    "untrim": "SciForge_Untrim",
    "extend": "SciForge_SurfaceExtend",
    "stitch": "SciForge_Stitch",
    "unstitch": "SciForge_Unstitch",
    "reverse_normal": "SciForge_ReverseNormal",
}


def _command_class(kind):
    spec = core.spec(kind)

    class SurfaceCommand:
        def GetResources(self):
            return {
                "MenuText": spec["title"],
                "ToolTip": TIPS.get(kind, spec["title"]),
                "Pixmap": ui_icon_path(spec["icon"]),
            }

        def IsActive(self):
            return App.ActiveDocument is not None

        def Activated(self):
            try:
                _start(PANELS[kind])
            except Exception as exc:
                warn("%s could not start: %s" % (spec["title"], exc))

    SurfaceCommand.__name__ = "Surface%sCommand" % spec["type"]
    return SurfaceCommand


def edit(feature):
    """Open the dialog of a surface step (timeline double-click). A follower (a Trim or
    Reverse Normal step in another body) opens its leader's."""
    try:
        if surface.kind_of(feature) == "piece":
            source = getattr(feature, "Source", None)
            if source is None:
                return
            feature = source
        leader = surface.leader_of(feature)
        kind = surface.kind_of(leader)
        _edit(PANELS[kind], leader)
    except Exception as exc:
        try:
            label = feature.Label
        except Exception:
            label = "the step"
        warn("could not edit %s: %s" % (label, exc))


# A plain table (the unit tests and the registry read the names from the source).
COMMANDS = {
    "SciForge_SurfaceExtrude": _command_class("extrude"),
    "SciForge_SurfaceRevolve": _command_class("revolve"),
    "SciForge_SurfaceSweep": _command_class("sweep"),
    "SciForge_SurfaceLoft": _command_class("loft"),
    "SciForge_Patch": _command_class("patch"),
    "SciForge_Ruled": _command_class("ruled"),
    "SciForge_SurfaceOffset": _command_class("offset"),
    "SciForge_BoundaryFill": _command_class("boundary_fill"),
    "SciForge_Thicken": _command_class("thicken"),
    "SciForge_Trim": _command_class("trim"),
    "SciForge_Untrim": _command_class("untrim"),
    "SciForge_SurfaceExtend": _command_class("extend"),
    "SciForge_Stitch": _command_class("stitch"),
    "SciForge_Unstitch": _command_class("unstitch"),
    "SciForge_ReverseNormal": _command_class("reverse_normal"),
}
EDITORS = {"SciForge::" + core.sciforge_type(k): edit for k in list(PANELS) + ["piece"]}


# -- deleting a step deletes what it made ----------------------------------------------------------
class _Watch:
    """A Trim or Reverse Normal over several bodies is one timeline step: deleting it
    deletes its steps in the other bodies; deleting an Unstitch deletes the bodies of the
    faces it took out (Fusion). Done inside the delete's own undo step (FreeCAD removes
    nested objects the same way); never during an undo / redo or while a file loads."""

    def slotDeletedObject(self, obj):
        try:
            doc = obj.Document
            if (
                doc is None
                or getattr(doc, "Transacting", False)
                or getattr(doc, "Restoring", False)
            ):
                return
            if not surface.is_surface_step(obj):
                return
            for follower in surface.followers_of(obj):
                surface._remove_step(follower)
            for piece in surface.pieces_of(obj):
                surface._remove_piece(piece)
        except Exception as exc:
            warn("surface delete: %s" % exc)


_WATCH = {"observer": None}


def install():
    if _WATCH["observer"] is None:
        _WATCH["observer"] = _Watch()
        App.addDocumentObserver(_WATCH["observer"])


try:
    install()
except Exception as _exc:  # never let an import fail the commands
    warn("surface delete watch unavailable: %s" % _exc)


# -- Change Parameters lists the surface steps' numbers -------------------------------------------
PARAMETER_WORDS = {
    "distance": "Distance",
    "distance2": "Distance Two",
    "start_offset": "Offset",
    "taper": "Taper Angle",
    "taper2": "Taper Angle Two",
    "angle": "Angle",
    "angle2": "Angle Two",
    "twist": "Twist Angle",
    "rail_distance": "Guide Rail Distance",
    "start_weight": "First Profile Weight",
    "end_weight": "Last Profile Weight",
    "start_angle": "First Profile Takeoff Angle",
    "end_angle": "Last Profile Takeoff Angle",
    "thickness": "Thickness",
    "tolerance": "Tolerance",
}


def register_parameters():
    """Fusion's Change Parameters lists every feature's numbers: the surface steps' too (the
    Patch's Tangency Weight changes nothing in SciForge, so it is left out)."""
    from . import parameters

    for kind, numbers in surface.NUMBERS.items():
        if kind == "patch":
            continue
        rows = [
            (prop, PARAMETER_WORDS.get(key, key.replace("_", " ").title()))
            for key, prop in numbers.items()
        ]
        parameters.SCIFORGE_PROPS.setdefault(core.sciforge_type(kind), rows)


try:
    register_parameters()
except Exception as _exc:  # never let an import fail the commands
    warn("surface parameters unavailable: %s" % _exc)
