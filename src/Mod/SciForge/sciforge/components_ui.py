# SPDX-License-Identifier: LGPL-2.1-or-later
"""Component commands and dialogs, Fusion-style (behaviour spec and sources:
docs/sciforge/parity/components.md).

- New Component (ASSEMBLE > New Component, no key in Fusion): a small dialog with Name,
  Parent, From Bodies and Activate (on by default); the component appears in the browser,
  the active component gets every new sketch, body and feature.
- Activate / Isolate / Exit Isolate / Create Components from Bodies / Move to Component:
  from the browser's right-click menus, the command search, or the ribbon.
- The document model is components.py; the browser rows are browser_ui.py.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, components, log, taskui, ui_icon_path, warn
from .compat import QtCore, QtWidgets

ISOLATED = {}  # document name -> names of the bodies / components Isolate hid


def _browser_refresh():
    try:
        from . import browser_ui

        w = browser_ui.widget()
        if w is not None:
            w.refresh(force=True)
    except Exception as exc:
        warn("browser refresh: %s" % exc)


def _timeline_refresh():
    try:
        from . import timeline_ui

        w = timeline_ui.widget()
        if w is not None:
            w.refresh(force=True)
    except Exception:
        pass


def refresh_panels():
    _browser_refresh()
    _timeline_refresh()


# -- what the browser menus and the commands do ---------------------------------------------
def activate(component, doc=None):
    """Make a component (None: the root) the active one."""
    if not commands.finish_open_dialog():  # a command keeps the component it started in
        return False
    components.set_active(component, doc)
    refresh_panels()
    return True


def isolate(obj):
    """Fusion: isolate a body or component and hide everything else. What was hidden
    before stays hidden after Exit Isolate (only what Isolate hid comes back)."""
    doc = obj.Document
    hidden = []
    for name in components.isolate_hidden(doc, obj):
        other = doc.getObject(name)
        if other is None or other.ViewObject is None:
            continue
        if other.ViewObject.Visibility:
            other.ViewObject.Visibility = False
            hidden.append(name)
    for shown in [obj] + components.ancestors(obj):
        if shown.ViewObject is not None and not shown.ViewObject.Visibility:
            shown.ViewObject.Visibility = True
    ISOLATED[doc.Name] = hidden
    log("%s isolated (%d hidden)" % (obj.Label, len(hidden)))


def unisolate(doc):
    if doc is None:
        return
    for name in ISOLATED.pop(doc.Name, []):
        obj = doc.getObject(name)
        if obj is not None and obj.ViewObject is not None:
            obj.ViewObject.Visibility = True
    log("isolate ended")


def move_objects(doc, objs, target, transaction=True):
    """Move bodies / components into ``target`` (None: the root), one undo step."""
    from . import timeline_ops as ops

    objs = [o for o in objs if components.is_body(o) or components.is_component(o)]
    if not objs:
        return False
    where = target.Label if target is not None else "the root"
    active = components.active_component(doc)
    if transaction:
        ops._transaction(doc, "Move to %s" % where)
    moved = 0
    try:
        for obj in objs:
            if components.place(obj, target):
                moved += 1
        ops.recompute(doc)
    except Exception:
        if transaction:
            doc.abortTransaction()
            ops.recompute(doc)
        raise
    if transaction:
        doc.commitTransaction()
    # The active component stays what it was (the active body may have moved away).
    body = components.active_body(doc)
    if body is not None and components.container_of(body) is not active:
        components.set_active(active, doc)
    if moved:
        log("moved %d to %s" % (moved, where))
    return moved > 0


def create_from_bodies(doc, bodies, parent=components.KEEP, label=None, activate_new=False):
    """Create Components from Bodies: one component per body (named after the body), each
    where its body was. The active component stays as it was unless ``activate_new``."""
    from . import timeline_ops as ops

    bodies = [b for b in bodies if components.is_body(b)]
    if not bodies:
        commands.tell("Pick one or more bodies first (in the browser or the window).")
        return []
    active = components.active_component(doc)
    ops._transaction(doc, "Create Components from Bodies")
    try:
        parts = components.from_bodies(doc, bodies, parent=parent, label=label)
        ops.recompute(doc)
    except Exception:
        doc.abortTransaction()
        ops.recompute(doc)
        raise
    doc.commitTransaction()
    if activate_new and parts:
        components.set_active(parts[-1], doc)
    else:
        body = components.active_body(doc)
        if body is not None and components.container_of(body) is not active:
            components.set_active(active, doc)
    refresh_panels()
    return parts


def delete_components(doc, parts):
    """Delete components with everything inside them (one undo step each)."""
    for part in parts:
        if not components.is_component(part):
            continue
        for names in ISOLATED.values():
            if part.Name in names:
                names.remove(part.Name)
        components.remove(doc, part)
    refresh_panels()


# -- the New Component dialog -------------------------------------------------------------------
class NewComponentPanel(taskui.Panel):
    """Fusion's New Component dialog: Name, Parent, From Bodies, Activate. Nothing is
    previewed; the component appears on OK (Cancel makes nothing)."""

    title = "New Component"
    icon = "new_component"
    last = None

    def __init__(self, doc, parent=None):
        super().__init__(doc, "New Component")
        NewComponentPanel.last = self
        self.bodies = []
        self.name = QtWidgets.QLineEdit(components.next_label(doc))
        self.name.setObjectName("SciForgeComponentName")
        self.name.selectAll()
        self.layout.addRow("Name", self.name)
        # Fusion's Type: Standard / Sheet Metal (a sheet metal component has an active rule;
        # wave 6, sm-forming: sheetmetal_component.py). Standard leaves everything as before.
        self.type_box = QtWidgets.QComboBox()
        self.type_box.setObjectName("SciForgeComponentType")
        self.type_box.addItem("Standard", "standard")
        self.type_box.addItem("Sheet Metal", "sheet_metal")
        self.layout.addRow("Type", self.type_box)
        self.rule_box = QtWidgets.QComboBox()
        self.rule_box.setObjectName("SciForgeComponentRule")
        self.rule_label = QtWidgets.QLabel("Rule")
        self.layout.addRow(self.rule_label, self.rule_box)
        self._fill_rules()
        self.type_box.currentIndexChanged.connect(self._type_changed)
        self._type_changed()
        self.parent_box = QtWidgets.QComboBox()
        self.parent_box.setObjectName("SciForgeComponentParent")
        self.parent_box.addItem("%s (root)" % doc.Label, "")
        for part in components.list_components(doc):
            self.parent_box.addItem(part.Label, part.Name)
        if parent is not None:
            index = self.parent_box.findData(parent.Name)
            if index >= 0:
                self.parent_box.setCurrentIndex(index)
        self.layout.addRow("Parent", self.parent_box)
        self.from_bodies = QtWidgets.QCheckBox("From Bodies")
        self.from_bodies.setObjectName("SciForgeComponentFromBodies")
        self.from_bodies.toggled.connect(self._from_bodies_toggled)
        self.layout.addRow(self.from_bodies)
        self.bodies_label = QtWidgets.QLabel("")
        self.bodies_label.setWordWrap(True)
        self.bodies_label.setStyleSheet("color: #8cc4ff;")
        self.layout.addRow(self.bodies_label)
        self.bodies_label.hide()
        self.activate = QtWidgets.QCheckBox("Activate")
        self.activate.setObjectName("SciForgeComponentActivate")
        self.activate.setChecked(True)
        self.layout.addRow(self.activate)
        self.finish_layout()
        panel = self

        class Observer:
            def addSelection(self, *_args):
                QtCore.QTimer.singleShot(30, panel._selection_changed)

        self.observer = Observer()
        Gui.Selection.addObserver(self.observer)
        QtCore.QTimer.singleShot(0, self._selection_changed)

    def typing_field(self):
        return None

    def _fill_rules(self):
        try:
            from . import sheetmetal_component

            for label, name in sheetmetal_component.rule_choices(self.doc):
                self.rule_box.addItem(label, name)
        except Exception as exc:
            warn("New Component: sheet metal rules: %s" % exc)

    def _type_changed(self, *_):
        sheet = self.type_box.currentData() == "sheet_metal"
        self.rule_box.setVisible(sheet)
        self.rule_label.setVisible(sheet)

    def _from_bodies_toggled(self, on):
        self.bodies_label.setVisible(bool(on))
        if on:
            self._selection_changed(keep=True)
        self._show_bodies()

    def _show_bodies(self):
        if not self.from_bodies.isChecked():
            return
        if self.bodies:
            names = ", ".join(b.Label for b in self.bodies)
            self.bodies_label.setText("%d bodies: %s" % (len(self.bodies), names))
        else:
            self.bodies_label.setText("Click the bodies (in the window or the browser).")

    def _selection_changed(self, keep=False):
        if self._closed:
            return
        try:
            picked = []
            for sel in Gui.Selection.getSelectionEx():
                if sel.Object.Document is not self.doc:
                    continue
                body = sel.Object if components.is_body(sel.Object) else None
                if body is None:
                    from . import timeline_ops as ops

                    body = ops.body_of(sel.Object)
                if body is not None and body not in picked:
                    picked.append(body)
            if not self.from_bodies.isChecked():
                if picked:  # bodies were picked before the dialog opened: From Bodies
                    self.bodies = picked
                    self.from_bodies.setChecked(True)
                return
            for body in picked:  # click again to drop a body
                if body in self.bodies and not keep:
                    self.bodies.remove(body)
                elif body not in self.bodies:
                    self.bodies.append(body)
            if picked:
                Gui.Selection.clearSelection()
            self._show_bodies()
        except Exception as exc:
            warn("New Component: %s" % exc)

    def feature(self):
        return None

    def accept(self):
        self._timer.stop()
        name = self.name.text().strip()
        if not name:
            self.message.setText("⚠ Type a name for the component.")
            return False
        parent = self.doc.getObject(self.parent_box.currentData() or "")
        if parent is not None and not components.is_component(parent):
            parent = None
        active = components.active_component(self.doc)
        try:
            if self.from_bodies.isChecked():
                if not self.bodies:
                    self.message.setText("⚠ Click at least one body, or untick From Bodies.")
                    return False
                parts = components.from_bodies(self.doc, self.bodies, parent=parent, label=name)
            else:
                parts = [components.new_component(self.doc, name, parent)]
            if self.type_box.currentData() == "sheet_metal":
                from . import sheetmetal_component

                for part in parts:
                    sheetmetal_component.make_sheet_metal(part, self.rule_box.currentData())
            self.doc.recompute()
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        self.cleanup()
        taskui._end_transaction(self.doc)
        self._close()
        if self.activate.isChecked() and parts:
            components.set_active(parts[-1], self.doc)
        else:
            body = components.active_body(self.doc)
            if body is not None and components.container_of(body) is not active:
                components.set_active(active, self.doc)
        refresh_panels()
        log("%s done: %s" % (self.title, ", ".join(p.Label for p in parts)))
        return True

    def cleanup(self):
        if getattr(self, "observer", None) is not None:
            try:
                Gui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None
        super().cleanup()


def open_new_component(parent=None, use_active=True):
    """Open the New Component dialog. ``parent``: the component the new one goes into;
    with ``use_active`` the active component is the default (Fusion nests a new component
    under the active one)."""
    if not commands.finish_open_dialog():
        return None
    if App.ActiveDocument is None:
        App.newDocument("Design")
    doc = App.ActiveDocument
    if parent is None and use_active:
        parent = components.active_component(doc)
    panel = NewComponentPanel(doc, parent)
    Gui.Control.showDialog(panel)
    log("New Component: waiting for OK")
    return panel


# -- Move to Component (a small dialog for the command; the browser moves directly) ------------
class MoveToComponentPanel(taskui.Panel):
    title = "Move to Component"
    icon = "new_component"
    last = None

    def __init__(self, doc, objs):
        super().__init__(doc, "Move to Component")
        MoveToComponentPanel.last = self
        self.objs = list(objs)
        what = QtWidgets.QLabel(", ".join(o.Label for o in self.objs))
        what.setWordWrap(True)
        self.layout.addRow("Moving", what)
        self.target = QtWidgets.QComboBox()
        self.target.setObjectName("SciForgeMoveTarget")
        for label, obj in components.move_targets(doc, self.objs):
            self.target.addItem(label, obj.Name if obj is not None else "")
        self.layout.addRow("Into", self.target)
        self.finish_layout()

    def feature(self):
        return None

    def accept(self):
        self._timer.stop()
        if self.target.count() == 0:
            self.message.setText("⚠ There is no component to move this into.")
            return False
        target = self.doc.getObject(self.target.currentData() or "")
        try:
            move_objects(self.doc, self.objs, target, transaction=False)
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
            return False
        self.cleanup()
        taskui._end_transaction(self.doc)
        self._close()
        refresh_panels()
        return True


# -- what the selection means ------------------------------------------------------------------
def _selected_units(doc):
    """Bodies and components in the selection (a face or feature counts as its body)."""
    from . import timeline_ops as ops

    found = []
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        if obj.Document is not doc:
            continue
        unit = obj if (components.is_body(obj) or components.is_component(obj)) else None
        if unit is None:
            unit = ops.body_of(obj)
        if unit is not None and unit not in found:
            found.append(unit)
    return found


def activate_from_timeline(part):
    """Double-click on a component's step in the timeline: activate it (like the
    browser's double-click)."""
    activate(part, part.Document)


# -- commands -------------------------------------------------------------------------------------
class _Command:
    title = ""
    tip = ""
    icon = "new_component"

    def GetResources(self):
        return {"MenuText": self.title, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return App.ActiveDocument is not None or self.title == "New Component"


class NewComponentCommand(_Command):
    title = "New Component"
    tip = "Create a component: a container for bodies, sketches and more components"

    def Activated(self):
        try:
            open_new_component()
        except Exception as exc:
            warn("New Component failed to start: %s" % exc)


class ActivateComponentCommand(_Command):
    title = "Activate Component"
    tip = "Make the selected component the active one (new work goes there)"

    def Activated(self):
        try:
            doc = App.ActiveDocument
            units = _selected_units(doc)
            target = None
            for unit in units:
                target = components.component_of(unit)
                break
            if not units:
                commands.tell("Select a component (or a body in it) to activate it.")
                return
            activate(target, doc)
        except Exception as exc:
            warn("Activate Component: %s" % exc)


class IsolateCommand(_Command):
    title = "Isolate"
    tip = "Show only the selected body or component"

    def Activated(self):
        try:
            doc = App.ActiveDocument
            units = _selected_units(doc)
            if not units:
                commands.tell("Select a body or a component to isolate it.")
                return
            isolate(units[0])
            refresh_panels()
        except Exception as exc:
            warn("Isolate: %s" % exc)


class UnisolateCommand(_Command):
    title = "Exit Isolate"
    tip = "Show again what Isolate hid"

    def Activated(self):
        try:
            unisolate(App.ActiveDocument)
            refresh_panels()
        except Exception as exc:
            warn("Exit Isolate: %s" % exc)


class ComponentsFromBodiesCommand(_Command):
    title = "Create Components from Bodies"
    tip = "Put each selected body into a component of its own"

    def Activated(self):
        try:
            doc = App.ActiveDocument
            if not commands.finish_open_dialog():
                return
            bodies = [u for u in _selected_units(doc) if components.is_body(u)]
            create_from_bodies(doc, bodies)
        except Exception as exc:
            warn("Create Components from Bodies: %s" % exc)


class MoveToComponentCommand(_Command):
    title = "Move to Component"
    tip = "Move the selected bodies or components into another component"

    def Activated(self):
        try:
            doc = App.ActiveDocument
            if not commands.finish_open_dialog():
                return
            units = _selected_units(doc)
            if not units:
                commands.tell("Select the bodies or components to move first.")
                return
            panel = MoveToComponentPanel(doc, units)
            Gui.Control.showDialog(panel)
        except Exception as exc:
            warn("Move to Component: %s" % exc)


COMMANDS = {
    "SciForge_NewComponent": NewComponentCommand,
    "SciForge_ActivateComponent": ActivateComponentCommand,
    "SciForge_Isolate": IsolateCommand,
    "SciForge_Unisolate": UnisolateCommand,
    "SciForge_ComponentsFromBodies": ComponentsFromBodiesCommand,
    "SciForge_MoveToComponent": MoveToComponentCommand,
}
# Double-click on a component's step in the timeline (taskui.edit_object).
EDITORS = {"App::Part": activate_from_timeline, "SciForge::Component": activate_from_timeline}
