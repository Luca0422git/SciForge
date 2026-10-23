# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > INSPECT > Design Advice: checks the bodies of components with a plastic rule against
that rule, like Fusion's Design Advice: wall thickness (the rule's range), thickness
variation, draft against the pull direction (the rule's minimum draft), knife edges and
undercuts.

The dialog starts on the bodies of components with a rule (every shown body when none has
one; the default rule then applies), the pull direction Z (click a plane or a flat face for
another, Flip turns it round) and every check on. The faces are coloured at once (Issues:
green fine, blue too thin, orange too thick, yellow draft or variation, purple undercut,
knife edges drawn red; Thickness: a thickness map from the rule's minimum to its maximum)
and the issues are listed: click one to zoom to it. OK keeps the analysis in the browser's
Analysis folder (eye to show / hide, double-click to open the list again); it checks the
design again whenever a body changes. Cancel / Esc leave nothing. The model never changes.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import bodies, commands, construct, curve_pick, log, plastic, plastic_advice, preview
from . import profile_pick, surface_analysis, ui_icon_path, warn
from . import plastic_advice_core as core
from .compat import QtCore, QtWidgets
from .hole_common import SelectionField
from .taskui import Panel

safe = curve_pick.safe("design advice")
KNIFE_WIDTH = 4.0


# -- drawing --------------------------------------------------------------------------------------
_PENDING = {"names": set(), "armed": False}


def schedule(obj, delay=0):
    try:
        _PENDING["names"].add((obj.Document.Name, obj.Name))
    except Exception:
        return
    if not _PENDING["armed"]:
        _PENDING["armed"] = True
        QtCore.QTimer.singleShot(delay, _run)


def _run():
    _PENDING["armed"] = False
    names, _PENDING["names"] = _PENDING["names"], set()
    for doc_name, name in names:
        try:
            obj = App.getDocument(doc_name).getObject(name)
        except Exception:
            continue
        if obj is None:
            continue
        try:
            if obj.Document.Recomputing:
                schedule(obj, 150)
                continue
        except Exception:
            pass
        try:
            proxy = obj.ViewObject.Proxy if obj.ViewObject is not None else None
            if isinstance(proxy, ViewProviderDesignAdvice):
                proxy.redraw(obj)
        except Exception as exc:
            warn("Design Advice display: %s" % exc)


def face_colors(obj, body_result, rule):
    """{face name: colour} of one body's results."""
    out = {}
    display = getattr(obj, "Display", "Issues")
    for name, data in body_result.get("faces", {}).items():
        if display == "Thickness":
            out[name] = core.heat_color(
                data.get("t_min"), rule["minimum_thickness"], rule["maximum_thickness"]
            )
        else:
            out[name] = core.face_color(data.get("issues", {}))
    return out


def _check_again(obj):
    """An analysis shown again after the design changed while it was hidden: check now."""
    try:
        if not bodies.alive(obj):
            return
        doc = obj.Document
        if doc.Recomputing:
            QtCore.QTimer.singleShot(150, lambda: _check_again(obj))
            return
        obj.touch()
        doc.recompute([obj])  # this analysis (and what it needs), not the whole design
        schedule(obj)
    except Exception as exc:
        warn("Design Advice: %s" % exc)


class ViewProviderDesignAdvice:
    """Draws a Design Advice over its bodies. Saved documents store
    "sciforge.plastic_advice_ui.ViewProviderDesignAdvice": keep the name stable."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        from pivy import coin

        self.Object = vobj.Object
        self.root = coin.SoSeparator()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        self.content = coin.SoSeparator()
        self.root.addChild(self.content)
        vobj.addDisplayMode(self.root, "Analysis")
        self.drawn = {}  # what is drawn: {body name: {"faces": n, "knife": n}}
        schedule(vobj.Object, 60)

    def getDisplayModes(self, vobj):
        return ["Analysis"]

    def getDefaultDisplayMode(self):
        return "Analysis"

    def setDisplayMode(self, mode):
        return mode

    def updateData(self, obj, prop):
        if prop in ("Results", "Display", "Problem"):
            schedule(obj)

    def onChanged(self, vobj, prop):
        if prop == "Visibility":
            obj = vobj.Object
            if vobj.Visibility and getattr(obj, "Stale", False):
                QtCore.QTimer.singleShot(0, lambda: _check_again(obj))
            schedule(obj)

    def getIcon(self):
        return ui_icon_path("pl_design_advice")

    def doubleClicked(self, vobj):
        obj = vobj.Object
        QtCore.QTimer.singleShot(0, lambda: edit(obj))
        return True

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        obj = vobj.Object
        QtCore.QTimer.singleShot(0, lambda: edit(obj))
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads

    def redraw(self, obj):
        content = getattr(self, "content", None)
        if content is None:
            return
        content.removeAllChildren()
        self.drawn = {}
        try:
            if obj.ViewObject is None or not obj.ViewObject.Visibility or obj.Problem:
                return
        except Exception:
            return
        from pivy import coin

        from . import surface_analysis_ui as sau

        results = plastic_advice.results(obj)
        for body_result in results.get("bodies", []):
            body = obj.Document.getObject(body_result.get("name", ""))
            if body is None or not bodies.alive(body) or body.Shape.isNull():
                continue
            try:
                rule = plastic.rule_for_body(body)
            except Exception:
                rule = None
            if rule is None:
                continue
            colors = face_colors(obj, body_result, rule)
            m = surface_analysis.Mesh()
            m.on_mesh = True  # drawn a hair in front of the model's faces
            per_point = []
            tolerance = surface_analysis.display_tolerance(body)
            smooth = getattr(obj, "Display", "Issues") == "Thickness"
            # the samples are in design coordinates, the drawing in the body's component's
            frame = surface_analysis.parent_placement(body)
            faces = body_result.get("faces", {})
            # the map needs points inside the faces too: their triangles split finer
            split = body.Shape.BoundBox.DiagonalLength / 40.0 if smooth else 0.0
            for i, face in enumerate(body.Shape.Faces):
                name = "Face%d" % (i + 1)
                try:
                    pts, tris, normals, _k = surface_analysis.face_mesh(face, tolerance, split)
                except Exception:
                    continue
                m.add(pts, tris, normals, [])
                samples = faces.get(name, {}).get("samples") if smooth else None
                if samples:
                    lo, hi = rule["minimum_thickness"], rule["maximum_thickness"]
                    moved = [tuple(frame.multVec(App.Vector(*q))) for q in pts]
                    for t in core.blended_many(moved, samples):
                        per_point.append(core.heat_color(t, lo, hi))
                else:
                    per_point += [colors.get(name, core.OK)] * len(pts)
            if not m.triangles:
                continue
            group = sau.group_for(coin, body)
            sau.colored_into(coin, group, m, per_point)
            knives = self._knife_lines(coin, group, body, body_result)
            content.addChild(group)
            self.drawn[body.Name] = {"faces": len(colors), "knife": knives}
        sau.redraw_views(obj.Document)

    def _knife_lines(self, coin, group, body, body_result):
        edges = body_result.get("edges", {})
        if not edges:
            return 0
        sep = coin.SoSeparator()
        light = coin.SoLightModel()
        light.model = coin.SoLightModel.BASE_COLOR
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(KNIFE_WIDTH)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*core.KNIFE)
        coords = coin.SoCoordinate3()
        lines = coin.SoLineSet()
        points, counts = [], []
        shape = body.Shape
        for name in edges:
            try:
                edge = shape.getElement(name)
                pts = edge.discretize(24)
            except Exception:
                continue
            points += [(p.x, p.y, p.z) for p in pts]
            counts.append(len(pts))
        if not points:
            return 0
        coords.point.setValues(0, len(points), points)
        lines.numVertices.setValues(0, len(counts), counts)
        for node in (light, style, material, coords, lines):
            sep.addChild(node)
        group.addChild(sep)
        return len(counts)


# -- the dialog ---------------------------------------------------------------------------------
class DesignAdvicePanel(Panel):
    title = "Design Advice"
    icon = "pl_design_advice"
    last = None

    def __init__(self, doc, analysis=None):
        super().__init__(doc, "Design Advice" if analysis is None else "Edit Design Advice")
        DesignAdvicePanel.last = self
        self.escape = preview.EscapeCancels(self)
        self.undo_guard = preview.UndoCancels(self)
        self.enter = preview.EnterFinishes(self)
        self.editing = analysis is not None
        self.active = "bodies"
        self._quiet = False
        self._ignore = False
        self.observer = None
        if analysis is None:
            analysis = plastic_advice.make(doc)
        self.analysis = analysis
        self._build_form()
        self._show()
        self._watch()
        self.schedule()

    def _build_form(self):
        form = self.layout
        self.bodies_field = SelectionField(self, "bodies", "Select bodies")
        self.bodies_field.button.setObjectName("SciForgeAdvice_bodies")
        self.bodies_field.clear.setObjectName("SciForgeAdvice_clear_bodies")
        form.addRow("Bodies", self.bodies_field.widget)
        self.direction_field = SelectionField(self, "direction", "Z (default)")
        self.direction_field.button.setObjectName("SciForgeAdvice_direction")
        self.direction_field.clear.setObjectName("SciForgeAdvice_clear_direction")
        form.addRow("Pull Direction", self.direction_field.widget)
        self.flip = curve_pick.checkbox("Flip", bool(self.analysis.Flip))
        self.flip.setObjectName("SciForgeAdvice_flip")
        form.addRow("", self.flip)
        self.checks = {}
        box = QtWidgets.QGroupBox("Checks")
        layout = QtWidgets.QVBoxLayout(box)
        for check, prop in plastic_advice.CHECK_PROPS.items():
            cb = curve_pick.checkbox(core.CHECK_TITLES[check], bool(getattr(self.analysis, prop)))
            cb.setObjectName("SciForgeAdvice_" + check)
            layout.addWidget(cb)
            cb.toggled.connect(self._changed)
            self.checks[check] = cb
        form.addRow(box)
        self.display = curve_pick.combo([(d, d) for d in plastic_advice.DISPLAYS], "Issues")
        self.display.setObjectName("SciForgeAdvice_display")
        form.addRow("Display", self.display)
        self.rules = QtWidgets.QLabel("")
        self.rules.setObjectName("SciForgeAdvice_rules")
        self.rules.setWordWrap(True)
        form.addRow(self.rules)
        self.summary = QtWidgets.QLabel("")
        self.summary.setObjectName("SciForgeAdvice_summary")
        self.summary.setWordWrap(True)
        form.addRow(self.summary)
        self.issues = QtWidgets.QTreeWidget()
        self.issues.setObjectName("SciForgeAdvice_issues")
        self.issues.setColumnCount(3)
        self.issues.setHeaderLabels(["Check", "Where", "Detail"])
        self.issues.setRootIsDecorated(False)
        self.issues.setMinimumHeight(140)
        self.issues.itemClicked.connect(self._issue_clicked)
        form.addRow(self.issues)
        self.finish_layout()
        self.flip.toggled.connect(self._changed)
        self.display.currentIndexChanged.connect(self._display_changed)
        self.bodies_field.set_active(True)

    def _show(self):
        self._quiet = True
        try:
            curve_pick.set_combo(self.display, self.analysis.Display)
            self.flip.setChecked(bool(self.analysis.Flip))
            for check, prop in plastic_advice.CHECK_PROPS.items():
                self.checks[check].setChecked(bool(getattr(self.analysis, prop)))
        finally:
            self._quiet = False
        self._refresh_fields()

    def _refresh_fields(self):
        owners = plastic_advice.targets(self.analysis)
        self.bodies_field.set_text(
            "%d bod%s" % (len(owners), "y" if len(owners) == 1 else "ies") if owners else ""
        )
        link = self.analysis.PullDirection
        text = ""
        if link:
            target, subs = link if isinstance(link, tuple) else (link, [""])
            sub = (subs[0] if isinstance(subs, (list, tuple)) and subs else subs) or ""
            text = "%s %s" % (target.Label, sub) if sub else target.Label
        self.direction_field.set_text(text)
        lines = []
        for owner in owners:
            try:
                rule = plastic.rule_for_body(owner)
                lines.append("%s: %s" % (owner.Label, rule["name"]))
            except Exception as exc:
                lines.append("%s: %s" % (owner.Label, exc))
        self.rules.setText("Plastic rules: " + ("; ".join(lines) if lines else "-"))

    # -- the selection boxes ---------------------------------------------------------------------
    def activate(self, name):
        self.active = name
        self.bodies_field.set_active(name == "bodies")
        self.direction_field.set_active(name == "direction")

    def clear_field(self, name):
        if name == "bodies":
            plastic_advice.set_targets(self.analysis, [])
        else:
            self.analysis.PullDirection = None
            self.activate("bodies")
        self._changed()

    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _unwatch(self):
        if self.observer is not None:
            Gui.Selection.removeObserver(self.observer)
            self.observer = None

    def _selection_changed(self):
        if self._closed or self._ignore:
            return
        try:
            picks = [(o, s) for o, s in profile_pick.picks() if o.Document is self.doc]
            if not picks:
                return
            Gui.Selection.clearSelection()
            for obj, short in picks:
                self._picked(obj, short)
        except Exception as exc:
            warn("Design Advice pick: %s" % exc)

    def _picked(self, obj, short):
        if self.active == "direction":
            if not surface_analysis.fits_direction(obj, short):
                self.message.setText(
                    "⚠ Pick a plane, a flat face, a straight edge or an axis for the pull."
                )
                return
            ref = construct.normalize_pick(obj, short)
            self.analysis.PullDirection = (ref[0], ref[1] or "")
            self.activate("bodies")
            self._changed()
            return
        body = bodies.body_of(obj) if not bodies.is_body(obj) else obj
        if body is None or not bodies.has_solid(body):
            self.message.setText("⚠ Click a solid body to check it.")
            return
        owners = plastic_advice.targets(self.analysis)
        if body in owners:
            owners.remove(body)
        else:
            owners.append(body)
        plastic_advice.set_targets(self.analysis, owners)
        self._changed()

    # -- changes ---------------------------------------------------------------------------------
    @safe
    def _changed(self, *_):
        if self._quiet or self._closed:
            return
        plastic_advice.apply(
            self.analysis,
            dict(
                {c: bool(cb.isChecked()) for c, cb in self.checks.items()},
                flip=bool(self.flip.isChecked()),
                display=self.display.currentData(),
            ),
        )
        self._refresh_fields()
        self.schedule()

    @safe
    def _display_changed(self, *_):
        """Issues / Thickness: the same results drawn in other colours, no new check."""
        if self._quiet or self._closed:
            return
        plastic_advice.apply(self.analysis, {"display": self.display.currentData()})
        schedule(self.analysis)

    def _recompute(self):
        if self._closed:
            return
        try:
            self.analysis.touch()
            preview.recompute(self.doc)
            self.show_status()
            schedule(self.analysis)
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def feature(self):
        return self.analysis

    def show_status(self):
        obj = self.analysis
        if obj.Problem:
            self.summary.setText("")
            self.message.setText("⚠ " + obj.Problem)
            self.issues.clear()
            return
        self.message.setText("")
        results = plastic_advice.results(obj)
        self.summary.setText(core.summary_text(results))
        self.issues.clear()
        for title, label, element, text, name in core.rows(results):
            item = QtWidgets.QTreeWidgetItem([title, "%s %s" % (label, element), text])
            item.setData(0, QtCore.Qt.UserRole, (name, element))
            self.issues.addTopLevelItem(item)
        for col in range(3):
            self.issues.resizeColumnToContents(col)

    @safe
    def _issue_clicked(self, item, *_):
        name, element = item.data(0, QtCore.Qt.UserRole)
        zoom_to(self.doc, name, element, self)

    # -- OK / Cancel -----------------------------------------------------------------------------
    def accept(self):
        if self._closed:
            return True
        try:
            pending = self._timer.isActive() or getattr(self, "_pending", False)
            self._timer.stop()
            if not plastic_advice.targets(self.analysis):
                self.message.setText("⚠ Pick the bodies to check.")
                return False
            # the preview has checked the design as it is unless a change still waits: OK
            # does not check it all again (seconds on a big part)
            if pending or not self.analysis.Results or self.analysis.Stale:
                self.analysis.touch()
            preview.recompute(self.doc)
            if self.analysis.Problem:
                self.message.setText("⚠ " + self.analysis.Problem)
                return False
            obj = self.analysis
            self.cleanup()
            preview.end_transaction(self.doc)
            self._close()
            schedule(obj)
            log("Design Advice done: %s" % obj.Summary)
            return True
        except Exception as exc:
            warn("Design Advice OK: %s" % exc)
            self.message.setText("⚠ %s" % exc)
            return False

    def reject(self):
        if self._closed:
            return True
        try:
            self._timer.stop()
            self.cleanup()
            preview.end_transaction(self.doc, abort=True)
            preview.recompute(self.doc)
        except Exception as exc:
            warn("Design Advice Cancel: %s" % exc)
        try:
            self._close()
        except Exception as exc:
            warn("Design Advice Cancel: %s" % exc)
        return True

    def cleanup(self):
        self._closed = True
        self._unwatch()
        for guard in (self.escape, self.undo_guard, self.enter):
            try:
                guard.remove()
            except Exception:
                pass
        super().cleanup()


def zoom_to(doc, body_name, element, panel=None):
    """Select the face / edge of an issue and fit the view to it."""
    body = doc.getObject(body_name)
    if body is None or body.Tip is None:
        return
    if panel is not None:
        panel._ignore = True
    try:
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(body.Tip, element)
        Gui.SendMsgToActiveView("ViewSelection")
    finally:
        if panel is not None:
            QtCore.QTimer.singleShot(200, lambda: setattr(panel, "_ignore", False))


def start():
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None or not bodies.solid_bodies(doc):
            commands.tell("Design Advice checks solid bodies: make a part first.")
            return
        Gui.Control.showDialog(DesignAdvicePanel(doc))
        log("Design Advice started")
    except Exception as exc:
        warn("Design Advice failed to start: %s" % exc)


class DesignAdviceCommand:
    def GetResources(self):
        return {
            "MenuText": "Design Advice",
            "ToolTip": "Check plastic parts against their plastic rule: wall thickness, draft, "
            "knife edges and undercuts",
            "Pixmap": ui_icon_path("pl_design_advice"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        start()


def edit(obj):
    """Open the dialog on an existing Design Advice (browser double-click / Edit)."""
    try:
        if Gui.Control.activeDialog():
            if not commands.finish_open_dialog():
                return
        Gui.Control.showDialog(DesignAdvicePanel(obj.Document, obj))
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))


def _register():
    try:
        from . import browser_core

        browser_core.ANALYSIS_ICONS.setdefault(plastic_advice.KIND, "pl_design_advice")
    except Exception as exc:
        warn("Design Advice: browser registration: %s" % exc)


_register()

COMMANDS = {"SciForge_DesignAdvice": DesignAdviceCommand}
EDITORS = {"SciForge::" + plastic_advice.KIND: edit}
