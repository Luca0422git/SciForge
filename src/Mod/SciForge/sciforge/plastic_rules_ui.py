# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > SETUP: Assign Plastic Rule and Manage Plastic Rules (Fusion's two rule
dialogs), on the contract in plastic.py / plastic_core.py.

Assign Plastic Rule: pick a component (the list, or click a body or component in the
canvas / browser: a body stands for its component, rules are never per body), then a rule
from "In This Design" or the "Library" (each row opens to show its values). OK assigns it:
a library rule is copied into the design first, the component's bodies take the rule's
physical material, and every rule-linked step of the component follows the rule.

Manage Plastic Rules: the same two lists, with New, Edit, Copy, Delete, Copy to Library /
Copy to Design and Set As Default (library rules only). Edit opens the rule's fields under
the lists (Name, Units, Material, Thickness, Draft Angle, Nominal Radius, Reveal Height,
Clearance and the Design Advice limits); lengths may be expressions in Thickness
("Thickness / 2"). Design rules are part of the design (OK keeps the changes, Cancel drops
them); the library is the user's own, kept in SciForge's settings, like Fusion's library
is the user's.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, components, log, plastic, plastic_core as core, ui_icon_path, warn
from .compat import QtCore, QtWidgets
from .taskui import Panel

DESIGN = "In This Design"
LIBRARY = "Library"


def _component_label(doc, component):
    return doc.Label if component is None else component.Label


def _units_of(doc):
    return "mm"


class RuleTree:
    """The two rule lists (In This Design / Library) as one tree; a rule row opens to show
    its values."""

    def __init__(self, panel, name):
        self.panel = panel
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName(name)
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setMinimumHeight(220)
        self.tree.setRootIsDecorated(True)
        self.design = None
        self.library = None

    def fill(self, doc, select=None, source=None):
        self.tree.clear()
        self.design = QtWidgets.QTreeWidgetItem([DESIGN, ""])
        self.library = QtWidgets.QTreeWidgetItem([LIBRARY, ""])
        self.tree.addTopLevelItem(self.design)
        self.tree.addTopLevelItem(self.library)
        default = plastic.default_rule_name()
        chosen = None
        for parent, rules, where in (
            (self.design, plastic.design_rules(doc), "design"),
            (self.library, plastic.library_rules(), "library"),
        ):
            for rule in rules:
                note = ""
                if where == "library" and rule["name"] == default:
                    note = "default"
                elif where == "design" and plastic.is_used(doc, rule["name"]):
                    note = "in use"
                row = QtWidgets.QTreeWidgetItem([rule["name"], note])
                row.setData(0, QtCore.Qt.UserRole, (where, rule["name"]))
                for label, text in core.describe(rule):
                    child = QtWidgets.QTreeWidgetItem([label, text])
                    child.setData(0, QtCore.Qt.UserRole, (where, rule["name"]))
                    row.addChild(child)
                parent.addChild(row)
                if rule["name"] == select and (source is None or source == where):
                    if chosen is None:
                        chosen = row
        self.design.setExpanded(True)
        self.library.setExpanded(True)
        if chosen is not None:
            self.tree.setCurrentItem(chosen)
        try:
            self.tree.resizeColumnToContents(0)
        except Exception:
            pass

    def current(self):
        """(where, name) of the picked rule, or (None, None)."""
        item = self.tree.currentItem()
        if item is None:
            return None, None
        data = item.data(0, QtCore.Qt.UserRole)
        if not data:
            return None, None
        return tuple(data)

    def select(self, where, name):
        parent = self.design if where == "design" else self.library
        if parent is None:
            return False
        for i in range(parent.childCount()):
            row = parent.child(i)
            if row.text(0) == name:
                self.tree.setCurrentItem(row)
                return True
        return False


# -- Assign Plastic Rule ---------------------------------------------------------------------------
class AssignPanel(Panel):
    title = "Assign Plastic Rule"
    icon = "pl_assign"
    last = None

    def __init__(self, doc):
        super().__init__(doc, "Assign Plastic Rule")
        AssignPanel.last = self
        from . import preview

        self.escape = preview.EscapeCancels(self)
        self.observer = None
        self.components = [None] + list(components.list_components(doc))
        self.component = components.active_component(doc)
        form = self.layout
        self.combo = QtWidgets.QComboBox()
        self.combo.setObjectName("SciForgePlastic_component")
        for c in self.components:
            self.combo.addItem(_component_label(doc, c))
        self.combo.setCurrentIndex(self._index(self.component))
        form.addRow("Component", self.combo)
        self.hint = QtWidgets.QLabel(
            "Click a component (or one of its bodies) to pick it. Rules are assigned to "
            "components, never to single bodies."
        )
        self.hint.setWordWrap(True)
        form.addRow(self.hint)
        self.rules = RuleTree(self, "SciForgePlastic_rules")
        form.addRow(self.rules.tree)
        self.info = QtWidgets.QLabel("")
        self.info.setObjectName("SciForgePlastic_info")
        self.info.setWordWrap(True)
        form.addRow(self.info)
        self.finish_layout()
        self._fill()
        self.combo.currentIndexChanged.connect(self._component_changed)
        self.rules.tree.currentItemChanged.connect(lambda *a: self._show_info())
        self._watch()

    def _index(self, component):
        for i, c in enumerate(self.components):
            if c is component:
                return i
        return 0

    def _fill(self):
        name = plastic.assigned_rule_name(self.doc, self.component)
        select = name or plastic.default_rule_name()
        self.rules.fill(self.doc, select, "design" if name else "library")
        self._show_info()

    def _component_changed(self, index):
        try:
            self.component = self.components[index]
            self._fill()
        except Exception as exc:
            warn("assign plastic rule: %s" % exc)

    def _show_info(self):
        where, name = self.rules.current()
        now = plastic.assigned_rule_name(self.doc, self.component)
        lines = ["Assigned now: %s" % (now or "none")]
        if name:
            rule = plastic.find_rule(self.doc, name) if where == "design" else None
            if where == "library" and plastic.find_rule(self.doc, name) is not None:
                # assign_rule keeps the design's copy (a library edit never changes a
                # design silently): say so rather than show the library's values only
                rule = plastic.find_rule(self.doc, name)
                lines.append(
                    "This design has its own '%s': the component takes the design's values." % name
                )
            rule = rule or plastic.library_rule(name)
            if rule is not None:
                key = plastic.material_key(rule)
                if key:
                    lines.append("The bodies of this component take %s." % rule["material"])
                else:
                    lines.append(
                        "SciForge has no physical material for %s yet: the bodies keep theirs."
                        % rule.get("material", "")
                    )
        self.info.setText("\n".join(lines))

    # picking a component in the canvas / browser
    def _watch(self):
        panel = self

        class Observer:
            def addSelection(self, doc, obj, sub, pnt):
                QtCore.QTimer.singleShot(30, panel._picked)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)

    def _picked(self):
        if self._closed:
            return
        try:
            sel = Gui.Selection.getSelection(self.doc.Name)
            if not sel:
                return
            obj = sel[-1]
            component = components.component_of(obj)
            Gui.Selection.clearSelection()
            if components.is_component(obj) or obj.TypeId == "PartDesign::Body":
                pass
            else:
                from . import bodies

                body = bodies.body_of(obj)
                component = components.container_of(body) if body is not None else component
            self.combo.setCurrentIndex(self._index(component))
            self.message.setText("")
        except Exception as exc:
            warn("assign plastic rule pick: %s" % exc)

    def accept(self):
        if self._closed:
            return True
        try:
            where, name = self.rules.current()
            if not name:
                self.message.setText("⚠ Pick a rule from In This Design or the Library.")
                return False
            # A library rule is copied into the design; when the design holds a rule of
            # that name already, the component takes the design's copy (a library edit
            # never changes a design silently: Copy to Design brings the new values in).
            plastic.assign_rule(self.doc, name, self.component)
            plastic.apply_material(self.doc, self.component)
            self.doc.recompute()
            log(
                "plastic rule '%s' assigned to %s"
                % (name, _component_label(self.doc, self.component))
            )
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        return super().accept()

    def reject(self):
        return super().reject()

    def cleanup(self):
        if self.observer is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        try:
            self.escape.remove()
        except Exception:
            pass
        super().cleanup()


# -- Manage Plastic Rules --------------------------------------------------------------------------
class ManagePanel(Panel):
    title = "Manage Plastic Rules"
    icon = "pl_manage"
    last = None

    def __init__(self, doc):
        super().__init__(doc, "Manage Plastic Rules")
        ManagePanel.last = self
        from . import preview

        self.escape = preview.EscapeCancels(self)
        self.editing = None  # (where, old name or None for a new rule)
        form = self.layout
        self.rules = RuleTree(self, "SciForgePlastic_manage_rules")
        form.addRow(self.rules.tree)
        row = QtWidgets.QWidget()
        buttons = QtWidgets.QGridLayout(row)
        buttons.setContentsMargins(0, 0, 0, 0)
        self.buttons = {}
        for i, (key, text) in enumerate(
            (
                ("new", "New"),
                ("edit", "Edit"),
                ("copy", "Copy"),
                ("delete", "Delete"),
                ("to_library", "Copy to Library"),
                ("to_design", "Copy to Design"),
                ("default", "Set As Default"),
            )
        ):
            button = QtWidgets.QPushButton(text)
            button.setObjectName("SciForgePlastic_" + key)
            button.clicked.connect(lambda _=False, k=key: self._button(k))
            buttons.addWidget(button, i // 4, i % 4)
            self.buttons[key] = button
        form.addRow(row)
        self.editor = QtWidgets.QGroupBox("Edit Plastic Rule")
        self.editor.setObjectName("SciForgePlastic_editor")
        grid = QtWidgets.QFormLayout(self.editor)
        self.fields = {}
        for key in core.FIELDS:
            if key == "units":
                widget = QtWidgets.QComboBox()
                widget.addItems(list(core.UNITS))
            elif key == "material":
                widget = QtWidgets.QComboBox()
                widget.setEditable(True)
                widget.addItems(list(core.MATERIALS))
            else:
                widget = QtWidgets.QLineEdit()
            widget.setObjectName("SciForgePlastic_field_" + key)
            grid.addRow(core.LABELS[key], widget)
            self.fields[key] = widget
        actions = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(actions)
        lay.setContentsMargins(0, 0, 0, 0)
        self.save_button = QtWidgets.QPushButton("Save Rule")
        self.save_button.setObjectName("SciForgePlastic_save")
        self.save_button.clicked.connect(lambda: self._save())
        self.discard_button = QtWidgets.QPushButton("Discard")
        self.discard_button.setObjectName("SciForgePlastic_discard")
        self.discard_button.clicked.connect(lambda: self._close_editor())
        lay.addWidget(self.save_button)
        lay.addWidget(self.discard_button)
        grid.addRow(actions)
        self.editor.setVisible(False)
        form.addRow(self.editor)
        # a new rule's numbers follow a change of its Units (2 mm -> 0.0787 in)
        self._units_shown = None
        self._loading = False
        self.fields["units"].currentTextChanged.connect(self._units_changed)
        self.finish_layout()
        self.rules.fill(doc)
        self.rules.tree.currentItemChanged.connect(lambda *a: self._enable())
        self._enable()

    def _enable(self):
        where, name = self.rules.current()
        self.buttons["edit"].setEnabled(bool(name))
        self.buttons["copy"].setEnabled(bool(name))
        self.buttons["delete"].setEnabled(bool(name))
        self.buttons["to_library"].setEnabled(where == "design")
        self.buttons["to_design"].setEnabled(where == "library")
        self.buttons["default"].setEnabled(where == "library")

    def _rule(self, where, name):
        if where == "design":
            return plastic.find_rule(self.doc, name)
        return plastic.library_rule(name)

    def _button(self, key):
        try:
            self.message.setText("")
            where, name = self.rules.current()
            if key == "new":
                base = (
                    self._rule(where, name)
                    if name
                    else plastic.library_rule(plastic.default_rule_name())
                )
                rule = dict(base)
                rule["name"] = plastic.unique_name(self.doc, "New rule", where == "library")
                self._open_editor(where or "design", None, rule)
            elif key == "edit" and name:
                self._open_editor(where, name, self._rule(where, name))
            elif key == "copy" and name:
                rule = dict(self._rule(where, name))
                rule["name"] = plastic.unique_name(self.doc, name, where == "library")
                self._store(where, rule)
                self.rules.fill(self.doc, rule["name"], where)
            elif key == "delete" and name:
                if where == "design":
                    plastic.delete_rule(self.doc, name)
                else:
                    plastic.delete_library_rule(name)
                self.rules.fill(self.doc)
                log("plastic rule '%s' deleted" % name)
            elif key == "to_library" and name:
                rule = dict(self._rule(where, name))
                rule["name"] = plastic.unique_name(self.doc, name, True)
                plastic.save_library_rule(rule)
                self.rules.fill(self.doc, rule["name"], "library")
            elif key == "to_design" and name:
                rule = dict(self._rule(where, name))
                rule["name"] = plastic.unique_name(self.doc, name, False)
                plastic.save_rule(self.doc, rule)
                self.rules.fill(self.doc, rule["name"], "design")
            elif key == "default" and name:
                plastic.set_default_rule(name)
                self.rules.fill(self.doc, name, "library")
            self._enable()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def _store(self, where, rule):
        if where == "design":
            plastic.save_rule(self.doc, rule)
            self.doc.recompute()
        else:
            plastic.save_library_rule(rule)

    def _open_editor(self, where, old, rule):
        self.editing = (where, old)
        self._loading = True
        self.editor.setTitle(
            "%s Plastic Rule (%s)"
            % ("Edit" if old else "New", DESIGN if where == "design" else LIBRARY)
        )
        for key, widget in self.fields.items():
            value = str(rule.get(key, core.FIELDS[key][1]))
            if isinstance(widget, QtWidgets.QComboBox):
                i = widget.findText(value)
                if i >= 0:
                    widget.setCurrentIndex(i)
                elif widget.isEditable():
                    widget.setEditText(value)
            else:
                widget.setText(value)
        self._loading = False
        self._units_shown = self.fields["units"].currentText()
        # Units are fixed when a rule is made (Fusion)
        self.fields["units"].setEnabled(old is None)
        self.editor.setVisible(True)

    def _units_changed(self, text):
        """A new rule's Units changed: its plain lengths are converted (an expression in
        Thickness follows the thickness by itself)."""
        try:
            if self._loading or self.editing is None or self.editing[1] is not None:
                return
            old, self._units_shown = self._units_shown, text
            if not old or old == text or text not in core.MM_PER_UNIT:
                return
            factor = core.MM_PER_UNIT[old] / core.MM_PER_UNIT[text]
            for key in core.LENGTH_FIELDS:
                widget = self.fields[key]
                try:
                    value = float(widget.text())
                except ValueError:
                    continue
                widget.setText("%g" % round(value * factor, 4))
        except Exception as exc:
            warn("plastic rule units: %s" % exc)

    def _close_editor(self):
        self.editing = None
        self.editor.setVisible(False)

    def editor_rule(self):
        rule = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QtWidgets.QComboBox):
                rule[key] = widget.currentText().strip()
            else:
                rule[key] = widget.text().strip()
        return rule

    def _save(self):
        try:
            if self.editing is None:
                return
            where, old = self.editing
            rule = self.editor_rule()
            problems = core.validate(rule)
            if problems:
                self.message.setText("⚠ " + problems[0])
                return
            if not rule["name"]:
                self.message.setText("⚠ The rule needs a name.")
                return
            taken = {
                r["name"]
                for r in (
                    plastic.design_rules(self.doc) if where == "design" else plastic.library_rules()
                )
            }
            if rule["name"] != old and rule["name"] in taken:
                self.message.setText("⚠ A rule named '%s' exists already." % rule["name"])
                return
            if where == "design":
                plastic.save_rule(self.doc, rule)
                if old and old != rule["name"]:
                    # a renamed design rule: its components follow the new name
                    for component, name in plastic.plastic_components(self.doc):
                        if name == old:
                            plastic.assign_rule(self.doc, rule["name"], component)
                    plastic.delete_rule(self.doc, old)
                for component, name in plastic.plastic_components(self.doc):
                    if name == rule["name"]:
                        plastic.apply_material(self.doc, component)
                self.doc.recompute()
            else:
                plastic.save_library_rule(rule)
                if old and old != rule["name"]:
                    try:
                        plastic.delete_library_rule(old)
                    except ValueError:
                        pass
            self.message.setText("")
            self._close_editor()
            self.rules.fill(self.doc, rule["name"], where)
            self._enable()
            log("plastic rule '%s' saved (%s)" % (rule["name"], where))
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)

    def accept(self):
        if self._closed:
            return True
        if self.editing is not None:
            self._save()
            if self.editing is not None:
                return False
        return super().accept()

    def cleanup(self):
        try:
            self.escape.remove()
        except Exception:
            pass
        super().cleanup()


# -- commands --------------------------------------------------------------------------------------
def _start(cls, what):
    try:
        if not commands.finish_open_dialog():
            return
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or create a design first.")
            return
        Gui.Control.showDialog(cls(doc))
        log("%s started" % what)
    except Exception as exc:
        warn("%s failed to start: %s" % (what, exc))


class AssignCommand:
    def GetResources(self):
        return {
            "MenuText": "Assign Plastic Rule",
            "ToolTip": "Give a component a plastic rule: its wall thickness, draft, radius and "
            "material become the defaults of the plastic tools",
            "Pixmap": ui_icon_path("pl_assign"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start(AssignPanel, "Assign Plastic Rule")


class ManageCommand:
    def GetResources(self):
        return {
            "MenuText": "Manage Plastic Rules",
            "ToolTip": "Make, edit, copy and delete plastic rules, in this design and in your "
            "library",
            "Pixmap": ui_icon_path("pl_manage"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        _start(ManagePanel, "Manage Plastic Rules")


def start_rule_fillet():
    """PLASTIC > MODIFY > Rule Fillet: SciForge's Fillet dialog, switched to its Rule
    Fillet type, the radius the plastic rule's Nominal Radius (the component's rule, else
    the library's default rule). Returns the dialog or None."""
    from . import fillet_ui

    panel = fillet_ui.start(fillet_ui.FilletPanel)
    if panel is None:
        return None
    try:
        if panel.mode != "rule":
            # the dialog's own Type change (as a click on the Type list does)
            panel.type.setCurrentIndex(panel.type.findData("rule"))
        rule = plastic.rule_for_body(panel.body)
        radius = round(float(rule["nominal_radius"]), 4)
        panel.spec["radius"] = radius
        field = panel.fields.get("radius")
        if field is not None:
            field.field.set_value(radius)
        panel._load_row()
        panel._refs_changed()
        log("rule fillet: radius %.3g mm from the plastic rule" % radius)
    except Exception as exc:
        warn("Rule Fillet: %s" % exc)
    return panel


class RuleFilletCommand:
    def GetResources(self):
        return {
            "MenuText": "Rule Fillet",
            "ToolTip": "Round every edge of the picked faces or features (or only the edges "
            "between two sets), with the plastic rule's nominal radius",
            "Pixmap": ui_icon_path("pl_rule_fillet"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start_rule_fillet()
        except Exception as exc:
            warn("Rule Fillet failed to start: %s" % exc)


COMMANDS = {
    "SciForge_AssignPlasticRule": AssignCommand,
    "SciForge_ManagePlasticRules": ManageCommand,
    "SciForge_RuleFillet": RuleFilletCommand,
}
